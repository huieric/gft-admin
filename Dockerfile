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
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# 安装 nginx
RUN apt-get update && apt-get install -y procps nginx && rm -rf /var/lib/apt/lists/*

# 安装前端构建结果到 nginx 静态目录
RUN mkdir -p /var/www/html
COPY --from=frontend-build /app/frontend/dist /var/www/html

# 拷贝 nginx 配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# 启动脚本（前后端都跑）
COPY start.sh /start.sh
RUN chmod +x /start.sh

RUN useradd -ms /bin/bash -u 2000 admin && \
    adduser admin sudo && \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER admin
CMD ["/start.sh"]
