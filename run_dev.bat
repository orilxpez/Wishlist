@echo off
REM Ejecuta la app sin empaquetar (para desarrollo). Ejecuta build.bat una vez antes.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python app.py
