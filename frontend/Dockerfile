# 多阶段构建：node 打包静态资源，nginx 托管 SPA
# =============== Stage 1: builder ===============
FROM node:20-alpine AS builder

WORKDIR /build

# 先拷贝锁文件以最大化利用 Docker 层缓存
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build


# =============== Stage 2: runtime ===============
FROM nginx:alpine AS runtime

# 移除官方默认站点配置，使用 SPA 专用配置
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
