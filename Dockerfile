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
FROM nginx:alpine

# 安装 python runtime
COPY backend/ /app/backend
RUN apk add --no-cache python3 py3-pip procps \
    && pip3 install --break-system-packages --no-cache-dir -r /app/backend/requirements.txt

# 安装前端构建结果到 nginx 静态目录
RUN mkdir -p /var/www/html
COPY --from=frontend-build /app/frontend/dist /var/www/html

# 拷贝 nginx 配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN chown -R nginx:nginx /var/log

# 启动脚本（前后端都跑）
COPY start.sh /app/backend/start.sh
RUN chmod +x /app/backend/start.sh
ENTRYPOINT /app/backend/start.sh
