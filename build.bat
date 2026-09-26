@echo off
REM Crea el entorno, instala dependencias y genera dist\Wishlist.exe
cd /d "%~dp0"

if not exist .venv (
    REM Busca Python: PATH, lanzador "py" o el instalador nuevo de python.org
    set "PY="
    where python >nul 2>&1 && set "PY=python"
    if not defined PY where py >nul 2>&1 && set "PY=py -3"
    if not defined PY for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-3*") do set "PY=%%D\python.exe"
    if not defined PY (echo No se encuentra Python 3.10+ & pause & exit /b 1)
    call %%PY%% -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || (pause & exit /b 1)

if not exist icon.ico python make_icon.py

pyinstaller --noconfirm --onefile --windowed ^
  --name Wishlist ^
  --icon icon.ico ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "icon.ico;." ^
  app.py || (pause & exit /b 1)

echo.
echo Listo: dist\Wishlist.exe
pause
