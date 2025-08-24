# 1. 使用 Node.js 镜像来构建 Vue.js 应用
FROM node:16 AS build

# 设置工作目录
WORKDIR /app

# 复制 Vue.js 项目文件
COPY . .

# 安装依赖并构建 Vue.js 应用
RUN npm install
RUN npm run build

# 2. 使用 Nginx 镜像来提供静态资源
FROM nginx:alpine

# 复制 Vue.js 构建后的文件到 Nginx 的 web 根目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露 6080 端口
EXPOSE 6080

# 启动 Nginx 服务
CMD ["nginx", "-g", "daemon off;"]
