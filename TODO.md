# BDG Pylance Type Error Fix - TODO List

## Status: [IN PROGRESS] ✅ Plan Approved

### 1. [TODO] Setup Types 📝
- [ ] Create `bdg_predictor/types.py` with TypedDicts (PredictionDict, DrawRowDict, etc.)
- [ ] Update imports in main.py, telegram_sender.py, predictor.py

### 2. [✅] Fix main.py 🔧
- ✅ Rename _LSTM_IMPORT_OK → lstm_import_ok
- ✅ Add type annotations for row, prediction
- ✅ Fix _get_lstm_model → get_global_model
- ✅ Test: python main.py

### 3. [✅] Fix telegram_sender.py 📱
- [✅] Add PredictionDict annotations
- [✅] Fix all get() type issues
- [✅] Test: python telegram_sender.py

### 4. [TODO] Minor Fixes 🛠️
- [ ] health_monitor.py: status Dict[str, str]
- [ ] model_api_server.py: top3 types

### 5. [TODO] Validation & Testing ✅
- [ ] Run main.py 3x: cd bdg_predictor && python main.py
- [ ] search_files for remaining "Type of|unknown" → confirm 0 results
- [ ] Pylance diagnostics clean
- [ ] Update this TODO.md: mark complete

### 6. [LATER] Notebook 🗒️
- Colab notebook torch/FB types

**Next Step**: types.py → main.py → test → telegram_sender.py → test → validate

**Commands Ready**:
- `cd bdg_predictor && python main.py`
- `cd bdg_predictor && python telegram_sender.py`

