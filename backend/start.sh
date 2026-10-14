#!/bin/bash
# Backend startup script with environment loading

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/Scripts/activate

# Export environment variables from .env
export $(grep -v '^#' .env | xargs)

# Start uvicorn
exec uvicorn server:app --host 0.0.0.0 --port 8000 --reload
