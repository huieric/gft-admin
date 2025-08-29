# ---------------------------
# Stage 1: Build Vue frontend
# ---------------------------
FROM node:18 AS frontend-build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build:prod

# ---------------------------
# Stage 2: Build Python backend
# ---------------------------
FROM python:3.12-slim AS backend-build
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# ---------------------------
# Stage 3: Final runtime image
# ---------------------------
FROM debian:bookworm-slim

# 安装 nginx 和 python runtime
RUN apt-get update && apt-get install -y nginx python3 python3-pip && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖（如果用虚拟环境，可以在 backend-build stage 里做）
WORKDIR /app/backend
COPY --from=backend-build /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=backend-build /app/backend /app/backend

# 安装前端构建结果到 nginx 静态目录
RUN mkdir -p /var/www/html
COPY --from=frontend-build /app/frontend/dist /var/www/html

# 拷贝 nginx 配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# 启动脚本（前后端都跑）
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
