"""
Lightweight HTTP inference server for advanced BDG checkpoints.

Exposes:
- POST /api/advanced/predict

Request JSON:
{
  "game_code": "WinGo_30S",
  "draws": [
    {"issueNumber": "202603180001", "number": 5},
    ...
  ]
}

Response JSON:
{
  "status": "ok",
  "model": "WinGo_30S",
  "checkpoint": ".../best.pt",
  "seq_len": 24,
  "rows": 120,
  "top1_number": 5,
  "top1_prob": 0.16,
  "top3": [{"number": 5, "prob": 0.16}, ...]
}
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

try:
    import torch
    import torch.nn as nn
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PyTorch is required for model inference. Install with: pip install torch") from exc


MODE_TO_ID = {
    "WinGo_30S": 0,
    "WinGo_1M": 1,
    "WinGo_3M": 2,
    "WinGo_5M": 3,
    "unknown": 4,
}

FEATURE_COLS = [
    "is_big",
    "is_green_base",
    "is_red_base",
    "is_violet",
    "period_last2_norm",
    "period_last3_norm",
    "roll_big_10",
    "roll_green_10",
    "roll_big_30",
    "roll_green_30",
    "repeat_streak_norm",
    "self_freq_30",
]


class RichLSTMModel(nn.Module):
    def __init__(self, feature_dim: int, num_modes: int = 5):
        super().__init__()
        self.num_emb = nn.Embedding(10, 32)
        self.mode_emb = nn.Embedding(num_modes, 8)

        inp_dim = 32 + 8 + feature_dim
        self.lstm = nn.LSTM(inp_dim, 256, num_layers=2, batch_first=True, dropout=0.25)
        self.dropout = nn.Dropout(0.25)
        self.head = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 10),
        )

    def forward(self, x_num: torch.Tensor, x_mode: torch.Tensor, x_feat: torch.Tensor) -> torch.Tensor:
        z_num = self.num_emb(x_num)
        z_mode = self.mode_emb(x_mode)
        z = torch.cat([z_num, z_mode, x_feat], dim=-1)
        out, _ = self.lstm(z)
        out = self.dropout(out[:, -1, :])
        return self.head(out)


def _safe_int_tail(value: Optional[str], tail_len: int, default: int = 0) -> int:
    raw = "" if value is None else str(value)
    tail_digits = "".join(ch for ch in raw[-tail_len:] if ch.isdigit())
    return int(tail_digits) if tail_digits else default


def _normalize_draws(draws: Sequence[Any], game_code: str) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row_any in draws:
        if not isinstance(row_any, dict):
            continue
        row = cast(Dict[str, Any], row_any)
        period = row.get("issueNumber") or row.get("period")
        number = row.get("number")
        if period in (None, "") or number in (None, ""):
            continue
        try:
            n = int(number)
        except (TypeError, ValueError):
            continue
        if n < 0 or n > 9:
            continue
        normalized.append({
            "period": str(period),
            "number": n,
            "game_code": str(game_code or "unknown"),
        })

    # API payload is newest-first; convert to chronological order.
    normalized.reverse()
    return normalized


def _build_feature_rows(rows: Sequence[Dict[str, Any]]) -> Tuple[List[int], List[int], List[List[float]]]:
    numbers: List[int] = [int(row["number"]) for row in rows]
    modes: List[int] = [MODE_TO_ID.get(str(row.get("game_code", "unknown")), MODE_TO_ID["unknown"]) for row in rows]

    is_big = [1.0 if n >= 5 else 0.0 for n in numbers]
    is_green = [1.0 if n in (1, 3, 5, 7, 9) else 0.0 for n in numbers]
    is_red = [1.0 if n in (0, 2, 4, 6, 8) else 0.0 for n in numbers]
    is_violet = [1.0 if n in (0, 5) else 0.0 for n in numbers]

    feat_rows: List[List[float]] = []
    repeat_streak = 1

    for idx, row in enumerate(rows):
        period = str(row.get("period", ""))
        p2 = float(_safe_int_tail(period, 2)) / 99.0
        p3 = float(_safe_int_tail(period, 3)) / 999.0

        if idx > 0 and numbers[idx] == numbers[idx - 1]:
            repeat_streak += 1
        else:
            repeat_streak = 1
        repeat_streak_norm = min(max(repeat_streak, 1), 10) / 10.0

        start10 = max(0, idx - 9)
        start30 = max(0, idx - 29)

        win10_count = float(idx - start10 + 1)
        win30_count = float(idx - start30 + 1)

        roll_big_10 = sum(is_big[start10 : idx + 1]) / max(win10_count, 1.0)
        roll_green_10 = sum(is_green[start10 : idx + 1]) / max(win10_count, 1.0)
        roll_big_30 = sum(is_big[start30 : idx + 1]) / max(win30_count, 1.0)
        roll_green_30 = sum(is_green[start30 : idx + 1]) / max(win30_count, 1.0)

        window30 = numbers[start30 : idx + 1]
        self_freq_30 = window30.count(numbers[idx]) / max(float(len(window30)), 1.0)

        feat_rows.append([
            is_big[idx],
            is_green[idx],
            is_red[idx],
            is_violet[idx],
            p2,
            p3,
            float(roll_big_10),
            float(roll_green_10),
            float(roll_big_30),
            float(roll_green_30),
            float(repeat_streak_norm),
            float(self_freq_30),
        ])

    return numbers, modes, feat_rows


@dataclass
class LoadedCheckpoint:
    model: RichLSTMModel
    seq_len: int
    checkpoint_path: str
    model_name: str


class ModelRepository:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._cache: Dict[str, LoadedCheckpoint] = {}

    def _resolve_checkpoint(self, model_name: str) -> Optional[str]:
        model_dir = os.path.join(self.base_dir, "advanced", model_name)
        best_path = os.path.join(model_dir, "best.pt")
        latest_path = os.path.join(model_dir, "latest.pt")
        if os.path.exists(best_path):
            return best_path
        if os.path.exists(latest_path):
            return latest_path
        return None

    def _load_checkpoint(self, model_name: str) -> Optional[LoadedCheckpoint]:
        cached = self._cache.get(model_name)
        if cached:
            return cached

        checkpoint_path = self._resolve_checkpoint(model_name)
        if not checkpoint_path:
            return None

        payload = torch.load(checkpoint_path, map_location=self.device)
        state_raw = payload.get("model_state")
        if not isinstance(state_raw, dict):
            return None
        state = cast(Dict[str, torch.Tensor], state_raw)

        model = RichLSTMModel(feature_dim=len(FEATURE_COLS)).to(self.device)
        model.load_state_dict(state)
        model.eval()
        loaded = LoadedCheckpoint(
            model=model,
            seq_len=int(payload.get("seq_len", 40)),
            checkpoint_path=checkpoint_path,
            model_name=model_name,
        )
        self._cache[model_name] = loaded
        return loaded

    def predict(self, game_code: str, draws: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        requested = str(game_code or "unknown")
        resolved = requested if requested in MODE_TO_ID else "global"

        loaded = self._load_checkpoint(resolved)
        if loaded is None and resolved != "global":
            resolved = "global"
            loaded = self._load_checkpoint("global")

        if loaded is None:
            return {
                "status": "error",
                "error": "No usable checkpoint found for requested model or global fallback.",
                "requested_model": requested,
            }

        rows = _normalize_draws(draws, game_code=requested)
        if len(rows) < loaded.seq_len:
            return {
                "status": "not_enough_rows_for_inference",
                "model": loaded.model_name,
                "checkpoint": loaded.checkpoint_path,
                "rows": len(rows),
                "required_seq_len": loaded.seq_len,
            }

        numbers, modes, feat_rows = _build_feature_rows(rows)
        tail_num = numbers[-loaded.seq_len :]
        tail_mode = modes[-loaded.seq_len :]
        tail_feat = feat_rows[-loaded.seq_len :]

        x_num = torch.tensor([tail_num], dtype=torch.long, device=self.device)
        x_mode = torch.tensor([tail_mode], dtype=torch.long, device=self.device)
        x_feat = torch.tensor([tail_feat], dtype=torch.float32, device=self.device)

        with torch.no_grad():
            logits = loaded.model(x_num, x_mode, x_feat)
            probs = torch.softmax(logits, dim=1).squeeze(0).cpu()
            topk = torch.topk(probs, k=3)

        top3: List[Dict[str, Any]] = []
        for idx_tensor, prob_tensor in zip(topk.indices, topk.values):
            top3.append({"number": int(idx_tensor.item()), "prob": float(prob_tensor.item())})

        top1_number = int(top3[0]["number"])
        top1_prob = float(top3[0]["prob"])

        return {
            "status": "ok",
            "model": loaded.model_name,
            "checkpoint": loaded.checkpoint_path,
            "seq_len": loaded.seq_len,
            "rows": len(rows),
            "top1_number": top1_number,
            "top1_prob": top1_prob,
            "top3": top3,
        }


def resolve_default_model_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "models"),
        os.path.join(here, "models"),
    ]
    for candidate in candidates:
        advanced_dir = os.path.join(candidate, "advanced")
        if os.path.isdir(advanced_dir):
            return os.path.abspath(candidate)
    return os.path.abspath(candidates[0])


class InferenceHandler(BaseHTTPRequestHandler):
    repo: ModelRepository

    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests (health checks, etc)."""
        if self.path == "/health":
            from datetime import datetime
            health_payload = {
                "status": "healthy",
                "service": "BDG Prediction API Server",
                "timestamp": datetime.now().isoformat(),
                "endpoints": [
                    "/api/advanced/predict (POST)",
                    "/health (GET)"
                ]
            }
            self._send_json(200, health_payload)
            return
        
        self._send_json(404, {"status": "error", "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/advanced/predict":
            self._send_json(404, {"status": "error", "error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = cast(Dict[str, Any], json.loads(raw.decode("utf-8")))
            game_code = str(payload.get("game_code", "unknown"))
            draws_raw: Any = payload.get("draws") or []
            if not isinstance(draws_raw, list):
                raise ValueError("draws must be a list")
            draws = cast(List[Dict[str, Any]], draws_raw)

            result = self.repo.predict(game_code=game_code, draws=draws)
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(400, {"status": "error", "error": str(exc)})


def run_server(host: str, port: int, model_dir: str) -> None:
    handler = InferenceHandler
    handler.repo = ModelRepository(model_dir)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Model API listening on http://{host}:{port}")
    print("POST /api/advanced/predict")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run advanced model inference HTTP server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8787, help="Bind port")
    parser.add_argument("--model-dir", default=resolve_default_model_dir(), help="Base models directory")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_server(host=args.host, port=args.port, model_dir=args.model_dir)
