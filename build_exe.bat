@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   Image Compressor - Build EXE (Windows)
echo ===============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan. Install Python 3.10+ dari python.org
    echo         lalu centang "Add python.exe to PATH" saat instalasi.
    pause
    exit /b 1
)

if not exist venv (
    echo Membuat virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Menginstall dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Membangun file EXE...
pyinstaller --onefile --windowed --name ImageCompressor main.py

echo.
if exist dist\ImageCompressor.exe (
    echo SELESAI! File EXE ada di: dist\ImageCompressor.exe
) else (
    echo [ERROR] Build gagal, periksa pesan error di atas.
)
pause
