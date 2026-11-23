@echo off
echo Starting FinBridge Backend and Frontend in development mode...

start "FinBridge Backend (FastAPI)" cmd /k "cd backend && call .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
start "FinBridge Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo Both services launched in separate windows!
echo Backend: http://localhost:8000 (API Docs: http://localhost:8000/docs)
echo Frontend: http://localhost:5173
