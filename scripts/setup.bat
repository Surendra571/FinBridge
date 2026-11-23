@echo off
echo ===================================================
echo FinBridge - Development Setup Script (Windows)
echo ===================================================

echo [1/3] Setting up Backend environment...
cd backend
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate
echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if not exist .env (
    echo Copying .env.example to .env...
    copy .env.example .env
)
cd ..

echo [2/3] Setting up Frontend environment...
cd frontend
echo Installing Node dependencies...
call npm install
if not exist .env (
    echo Copying .env.example to .env...
    copy .env.example .env
)
cd ..

echo [3/3] Setting up root environment...
if not exist .env (
    copy .env.example .env
)

echo ===================================================
echo Setup complete! Run scripts\run_dev.bat to start.
echo ===================================================
