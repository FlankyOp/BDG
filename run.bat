@echo off
REM Launch model API server and dashboard HTML
cd bdg_predictor
start /B python model_api_server.py
start index.html
cd ..
