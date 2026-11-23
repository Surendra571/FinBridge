@echo off
echo ===================================================
echo Running FinBridge Test Suite
echo ===================================================

echo [1/2] Running Backend Tests...
cd backend
call .venv\Scripts\activate
pytest
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Backend tests failed!
    exit /b %ERRORLEVEL%
)
cd ..

echo [2/2] Running Smoke Tests...
pytest tests/
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Smoke tests failed!
    exit /b %ERRORLEVEL%
)

echo ===================================================
echo All tests passed successfully!
echo ===================================================
