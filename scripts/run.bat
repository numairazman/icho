@echo off
REM =====================================================
REM Icho launcher for Windows
REM - Ensures local venv (.venv) exists
REM - Installs requirements if needed
REM - Runs main.py
REM =====================================================

REM Jump to project root (one level up from scripts/)
cd /d "%~dp0.."

REM ---------- Detect or create venv ----------
if exist ".venv\Scripts\python.exe" (
    echo [Icho] Using existing venv: .venv
) else (
    echo [Icho] Creating virtual environment (.venv)...
    where py >nul 2>&1
    if %ERRORLEVEL%==0 (
        py -3 -m venv .venv || (
            echo [Icho] Failed to create venv with py.
            exit /b 1
        )
    ) else (
        python -m venv .venv || (
            echo [Icho] Failed to create venv with python.
            exit /b 1
        )
    )
)

REM ---------- Activate venv ----------
call ".venv\Scripts\activate"

REM ---------- Ensure pip & deps ----------
echo [Icho] Upgrading pip (safe to skip if offline)...
python -m pip install --upgrade pip >nul 2>&1

if exist "requirements.txt" (
    echo [Icho] Installing/upgrading dependencies from requirements.txt...
    pip install -r requirements.txt
) else (
    echo [Icho] WARNING: requirements.txt not found; continuing...
)

REM ---------- Run the app ----------
echo [Icho] Launching Icho...
python main.py

REM Keep terminal open if run by double-click
if /i "%CMDCMDLINE%" neq "" pause