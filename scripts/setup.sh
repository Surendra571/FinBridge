#!/usr/bin/env bash
set -e

echo "==================================================="
echo "FinBridge - Development Setup Script (POSIX)"
echo "==================================================="

echo "[1/3] Setting up Backend environment..."
cd backend
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
cd ..

echo "[2/3] Setting up Frontend environment..."
cd frontend
echo "Installing Node dependencies..."
npm install
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
cd ..

echo "[3/3] Setting up root environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

echo "==================================================="
echo "Setup complete! Run ./scripts/run_dev.sh to start."
echo "==================================================="
