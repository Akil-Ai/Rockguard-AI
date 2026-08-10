#!/usr/bin/env bash
# RockGuard AI - one-command demo launcher (macOS / Linux / Git Bash)
set -euo pipefail

cd "$(dirname "$0")"
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python

echo "============================================"
echo "  RockGuard AI - starting demo environment"
echo "============================================"

if [ ! -f backend/app/ml/artifacts/risk_model.joblib ]; then
  echo "[1/3] No trained model found - training now (about 30s)..."
  (cd backend && "$PY" -m app.ml.train_model)
else
  echo "[1/3] Trained model found."
fi

if [ ! -d frontend/node_modules ]; then
  echo "[2/3] Installing frontend packages..."
  (cd frontend && npm install)
else
  echo "[2/3] Frontend packages present."
fi

echo "[3/3] Launching backend and frontend..."
(cd backend && "$PY" -m uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!
(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Make Ctrl-C bring both processes down together.
trap 'echo; echo "Stopping..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM

echo
echo "  Console : http://localhost:5173"
echo "  API docs: http://127.0.0.1:8000/docs"
echo
echo "Press Ctrl-C to stop."
wait
