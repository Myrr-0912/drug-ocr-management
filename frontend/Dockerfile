# 多阶段构建：node 打包静态资源，nginx 托管 SPA
# =============== Stage 1: builder ===============
FROM node:20-alpine AS builder

# 国内构建默认走 npmmirror（阿里云同步镜像），CI/海外可通过
#   --build-arg NPM_REGISTRY=https://registry.npmjs.org 回切官方源
ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /build

# 先拷贝锁文件以最大化利用 Docker 层缓存
COPY package.json package-lock.json ./
RUN npm ci --registry=${NPM_REGISTRY} --no-audit --no-fund

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
    CMD wget -qO- http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
