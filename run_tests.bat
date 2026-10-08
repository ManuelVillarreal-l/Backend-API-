@echo off
REM Run the automated tests
call .venv\Scripts\activate
python -m pytest -v
pause
