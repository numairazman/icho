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

REM ----------- Copy VLC DLLs and plugins for python-vlc portability -----------
set VLC_PATH="C:\Program Files\VideoLAN\VLC"
if exist %VLC_PATH%\libvlc.dll copy /Y %VLC_PATH%\libvlc.dll dist\
if exist %VLC_PATH%\libvlccore.dll copy /Y %VLC_PATH%\libvlccore.dll dist\
if exist %VLC_PATH%\plugins xcopy /E /I /Y %VLC_PATH%\plugins dist\plugins

REM Inform user
if exist dist\libvlc.dll echo [Icho] Copied VLC DLLs to dist\
if exist dist\plugins echo [Icho] Copied VLC plugins to dist\plugins

echo [Icho] Portable executable built: dist\IchoPortable.exe
pause