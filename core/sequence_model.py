import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

if TORCH_AVAILABLE:
    class _LSTMNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(10, 32)
            self.lstm = nn.LSTM(32, 128, num_layers=2, batch_first=True)
            self.fc = nn.Linear(128, 10)
        def forward(self, x):
            x = self.embedding(x)
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])

class DeepSequenceModel:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._net = None
        self.is_ready = False
        if TORCH_AVAILABLE:
            self._net = _LSTMNet()
            if os.path.exists(model_path):
                try:
                    self._net.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True)["model_state"])
                    self.is_ready = True
                except: pass

    def predict(self, recent_context: List[int]) -> Dict[int, float]:
        if not self.is_ready: return {i: 0.1 for i in range(10)}
        self._net.eval()
        with torch.no_grad():
            x = torch.tensor([recent_context[-20:] if len(recent_context) >= 20 else ([5]*(20-len(recent_context)) + recent_context)], dtype=torch.long)
            logits = self._net(x)
            probs = torch.softmax(logits, dim=1).squeeze().tolist()
        return {i: probs[i] for i in range(10)}

    def get_summary(self, context: List[int]) -> Dict[str, Any]:
        p = self.predict(context)
        top = max(p.items(), key=lambda x: x[1])
        return {"scores": p, "top_prediction": top[0], "top_confidence": top[1], "source": "lstm", "is_ready": self.is_ready}

_GLOBAL_MODEL = None
def get_global_model():
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is None:
        from .config import Config
        _GLOBAL_MODEL = DeepSequenceModel(Config.LSTM_MODEL_PATH)
    return _GLOBAL_MODEL
