@echo off
REM Start the RutaSegura API on http://127.0.0.1:8000
call .venv\Scripts\activate
python -m uvicorn app.main:app --reload
pause
