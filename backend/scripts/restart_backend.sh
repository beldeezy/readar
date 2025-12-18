#!/usr/bin/env bash
set -e

PORT=8000

echo "Killing anything on port $PORT..."
PID=$(lsof -ti tcp:$PORT || true)
if [ ! -z "$PID" ]; then
    kill -9 $PID
    echo "Killed process $PID"
else
    echo "No process found on port $PORT"
fi

echo "Starting backend..."
source venv/bin/activate
uvicorn app.main:app --reload --port $PORT

