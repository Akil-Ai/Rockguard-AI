@echo off
REM RockGuard AI - one-command demo launcher (Windows)
REM Opens two windows: the FastAPI backend and the Vite frontend.

echo ============================================
echo   RockGuard AI - starting demo environment
echo ============================================
echo.

cd /d "%~dp0"

if not exist "backend\app\ml\artifacts\risk_model.joblib" (
    echo [1/3] No trained model found - training now ^(about 30s^)...
    pushd backend
    python -m app.ml.train_model
    popd
) else (
    echo [1/3] Trained model found.
)

if not exist "frontend\node_modules" (
    echo [2/3] Installing frontend packages...
    pushd frontend
    call npm install
    popd
) else (
    echo [2/3] Frontend packages present.
)

echo [3/3] Launching backend and frontend...
start "RockGuard API"      cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --port 8000"
start "RockGuard Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo   Console : http://localhost:5173
echo   API docs: http://127.0.0.1:8000/docs
echo.
echo Close the two spawned windows to stop the demo.
pause
