#!/bin/bash
set -e
cd /app
exec uvicorn agent.main:app --host 0.0.0.0 --port 8080