#!/bin/bash
# 启动 Python 后端（Flask/FastAPI 等）
python3 /app/backend/app.py &

# 启动 Nginx
nginx -g "daemon off;"
