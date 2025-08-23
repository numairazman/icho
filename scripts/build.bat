@echo off
REM =====================================================
REM Build portable Windows executable for Icho
REM =====================================================

REM Jump to project root (one level up from scripts/)
cd /d "%~dp0.."

REM Activate venv
call ".venv\Scripts\activate"

REM Ensure pyinstaller is installed
pip install --upgrade pyinstaller

REM Build the portable .exe
pyinstaller --onefile --windowed main.py --name IchoPortable

REM Output will be in dist\IchoPortable.exe
echo [Icho] Portable executable built: dist\IchoPortable.exe
pause