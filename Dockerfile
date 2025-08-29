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
FROM nginx:stable

# 安装 python runtime
RUN apt-get update && apt-get install -y procps python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# 安装前端构建结果到 nginx 静态目录
RUN mkdir -p /var/www/html
COPY --from=frontend-build /app/frontend/dist /var/www/html

# 拷贝 nginx 配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN chown -R nginx:nginx /var/log

# 启动脚本（前后端都跑）
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
