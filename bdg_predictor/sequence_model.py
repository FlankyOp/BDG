"""
Deep Sequence Model (LSTM)
===========================
A persistent PyTorch LSTM network that learns draw-number transitions
from the live API history and improves on every polling cycle.

Architecture
------------
Embedding(10 → 32) → LSTM(2 layers, 256 hidden) → Dropout → Linear(256 → 10)
Input : sequence of the last SEQ_LEN draw numbers  (0-9 each)
Output: logits for the next draw number            (0-9)

How it learns
-------------
1. First run  → cold-start training on all available API draws (EPOCHS_INIT epochs)
2. Each poll  → incremental update with the latest window  (EPOCHS_UPDATE epochs)
3. Weights saved to disk after every training pass
   → model keeps accumulating knowledge across process restarts

Fallback
--------
If PyTorch is not installed the module silently disables itself.
Install once with:  pip install torch  (~2 GB on Windows)
"""

# pyright: reportPossiblyUnboundVariable=false, reportOptionalCall=false
import os
import logging
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional torch import – module works without it (Markov fallback takes over)
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning(
        "PyTorch not installed – DeepSequenceModel disabled.\n"
        "  Install with: pip install torch\n"
        "  Falling back to Markov-chain LLMSequenceAI."
    )


# ---------------------------------------------------------------------------
# Neural network definition
# ---------------------------------------------------------------------------
if TORCH_AVAILABLE:
    class _LSTMNet(nn.Module):
        """
        2-layer LSTM that embeds draw numbers and predicts the next one.

        Parameters
        ----------
        vocab_size  : number of distinct tokens (10 for digits 0-9)
        embed_dim   : embedding dimension per token
        hidden_size : LSTM hidden state width
        num_layers  : stacked LSTM depth
        dropout     : dropout probability (applied between LSTM layers and
                      before the final linear projection)
        """

        def __init__(
            self,
            vocab_size: int = 10,
            embed_dim: int = 32,
            hidden_size: int = 256,
            num_layers: int = 2,
            dropout: float = 0.25,
        ) -> None:
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embed_dim)
            self.lstm = nn.LSTM(
                embed_dim,
                hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_size, vocab_size)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            # x: (batch, seq_len)  int64
            emb = self.embedding(x)            # (batch, seq_len, embed_dim)
            out, _ = self.lstm(emb)            # (batch, seq_len, hidden)
            out = self.dropout(out[:, -1, :])  # last timestep  (batch, hidden)
            return self.fc(out)                # (batch, vocab_size) logits


# ---------------------------------------------------------------------------
# High-level model manager  (training / inference / persistence)
# ---------------------------------------------------------------------------
class DeepSequenceModel:
    """
    Manages an _LSTMNet: training, incremental updates, persistence,
    and probability inference.

    Usage (inside pattern_detector / main)
    ----------------------------------------
    model = get_global_model()          # singleton

    # Full training (first run or explicit refresh)
    model.train_full(draws)             # draws: list[int], newest-first

    # Incremental update after each poll
    model.update(draws)

    # Inference
    probs = model.predict(recent_context)   # -> {0:0.12, 1:0.08, ...}
    summary = model.get_summary(recent_context)
    """

    # Hyper-parameters
    SEQ_LEN: int = 20        # how many previous draws feed each prediction
    BATCH_SIZE: int = 32
    EPOCHS_INIT: int = 30    # cold-start training epochs
    EPOCHS_UPDATE: int = 5   # epochs per incremental update
    LR: float = 1e-3

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._device = torch.device("cpu") if TORCH_AVAILABLE else None
        self._net: Optional[Any] = None
        self._optimizer: Optional[Any] = None
        self.trained_draws: int = 0
        self.loss_history: List[float] = []

        if TORCH_AVAILABLE:
            self._build()
            if os.path.isfile(model_path):
                self._load()
                logger.info(
                    f"[LSTM] Loaded weights from {model_path}  "
                    f"(trained on {self.trained_draws} draws, "
                    f"last loss={self._last_loss():.4f})"
                )
            else:
                logger.info("[LSTM] No saved weights found – model will train from scratch.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self._net = _LSTMNet().to(self._device)
        self._optimizer = optim.Adam(self._net.parameters(), lr=self.LR)

    def _last_loss(self) -> float:
        return self.loss_history[-1] if self.loss_history else float("nan")

    def _save(self) -> None:
        if not TORCH_AVAILABLE or self._net is None:
            return
        dir_ = os.path.dirname(self.model_path)
        if dir_:
            os.makedirs(dir_, exist_ok=True)
        torch.save(
            {
                "model_state": self._net.state_dict(),
                "optimizer_state": self._optimizer.state_dict(),  # type: ignore[union-attr]
                "trained_draws": self.trained_draws,
                "loss_history": self.loss_history[-500:],
            },
            self.model_path,
        )

    def _load(self) -> None:
        ckpt = torch.load(self.model_path, map_location=self._device, weights_only=False)
        self._net.load_state_dict(ckpt["model_state"])  # type: ignore[union-attr]
        self._optimizer.load_state_dict(ckpt["optimizer_state"])  # type: ignore[union-attr]
        self.trained_draws = int(ckpt.get("trained_draws", 0))
        self.loss_history = list(ckpt.get("loss_history", []))

    def _make_samples(self, draws: List[int]):
        """
        Convert a newest-first draw list into supervised (input_seq, label) pairs.

        Input  : the SEQ_LEN draws before position i  (chronological order)
        Label  : the draw at position i
        """
        chron = list(reversed(draws))   # oldest-first
        samples = []
        for i in range(self.SEQ_LEN, len(chron)):
            x = chron[i - self.SEQ_LEN : i]
            y = chron[i]
            samples.append((x, y))
        return samples

    def _run_training(self, draws: List[int], epochs: int) -> None:
        """Core training loop."""
        if not TORCH_AVAILABLE or self._net is None:
            return
        samples = self._make_samples(draws)
        if len(samples) < self.BATCH_SIZE:
            logger.warning(
                f"[LSTM] Not enough samples ({len(samples)}) for a full batch – skipping."
            )
            return

        criterion = nn.CrossEntropyLoss()
        self._net.train()
        final_loss = 0.0

        for _epoch in range(epochs):
            random.shuffle(samples)
            epoch_loss = 0.0
            n_batches = 0

            for i in range(0, len(samples), self.BATCH_SIZE):
                batch = samples[i : i + self.BATCH_SIZE]
                xs = torch.tensor(
                    [s[0] for s in batch], dtype=torch.long, device=self._device
                )
                ys = torch.tensor(
                    [s[1] for s in batch], dtype=torch.long, device=self._device
                )

                self._optimizer.zero_grad()           # type: ignore[union-attr]
                logits = self._net(xs)
                loss = criterion(logits, ys)
                loss.backward()
                nn.utils.clip_grad_norm_(self._net.parameters(), 1.0)
                self._optimizer.step()               # type: ignore[union-attr]

                epoch_loss += loss.item()
                n_batches += 1

            final_loss = epoch_loss / max(n_batches, 1)
            self.loss_history.append(final_loss)

        self.trained_draws = len(draws)
        self._save()
        logger.info(
            f"[LSTM] Training done – draws={len(draws)}, epochs={epochs}, "
            f"samples={len(samples)}, final_loss={final_loss:.4f}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def is_ready(self) -> bool:
        """True when the model has been trained on at least SEQ_LEN+1 draws."""
        return TORCH_AVAILABLE and self._net is not None and self.trained_draws > self.SEQ_LEN

    @property
    def model_available(self) -> bool:
        """True when PyTorch is installed (model can actually train)."""
        return TORCH_AVAILABLE and self._net is not None

    def train_full(self, draws: List[int]) -> None:
        """Cold-start full training on all available draws."""
        if not TORCH_AVAILABLE:
            return
        logger.info(f"[LSTM] Cold-start training on {len(draws)} draws …")
        self._run_training(draws, self.EPOCHS_INIT)

    def update(self, draws: List[int]) -> None:
        """Incremental update on the latest draw window (called every poll)."""
        if not TORCH_AVAILABLE:
            return
        self._run_training(draws, self.EPOCHS_UPDATE)

    def predict(self, recent_context: List[int]) -> Dict[int, float]:
        """
        Return a probability distribution {0: p0, 1: p1, …, 9: p9} for the
        next draw given the most-recent draws in *recent_context* (newest-first).
        """
        if not self.is_ready:
            return {i: 0.1 for i in range(10)}

        # Build a SEQ_LEN window in chronological order
        chron = list(reversed(recent_context[: self.SEQ_LEN]))
        # Pad with median value (5) if context is shorter than SEQ_LEN
        while len(chron) < self.SEQ_LEN:
            chron.insert(0, 5)

        self._net.eval()  # type: ignore[union-attr]
        with torch.no_grad():
            x = torch.tensor(
                [chron[-self.SEQ_LEN :]], dtype=torch.long, device=self._device
            )
            logits = self._net(x)                         # (1, 10)
            probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()

        return {i: float(probs[i]) for i in range(10)}

    def get_summary(self, recent_context: List[int]) -> Dict[str, Any]:
        """Return inference results + model diagnostics for logging / scoring."""
        probs = self.predict(recent_context)
        top = max(probs.items(), key=lambda kv: kv[1])
        return {
            "scores": probs,
            "top_prediction": top[0],
            "top_confidence": top[1],
            "trained_draws": self.trained_draws,
            "is_trained": self.is_ready,
            "last_loss": self._last_loss(),
            "model_available": TORCH_AVAILABLE,
        }


# ---------------------------------------------------------------------------
# Module-level singleton  (one model shared across all imports)
# ---------------------------------------------------------------------------
_GLOBAL_MODEL: Optional["DeepSequenceModel"] = None


def get_global_model(model_path: Optional[str] = None) -> "DeepSequenceModel":
    """
    Return (and lazily create) the process-wide DeepSequenceModel singleton.

    Parameters
    ----------
    model_path : path to save/load weights.  Defaults to Config.LSTM_MODEL_PATH
                 but Config is imported lazily to avoid circular imports.
    """
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is None:
        if model_path is None:
            from config import Config  # lazy – avoids circular import at module load
            model_path = Config.LSTM_MODEL_PATH
        _GLOBAL_MODEL = DeepSequenceModel(model_path)
    return _GLOBAL_MODEL
