# 多阶段构建：builder 装依赖，runtime 精简镜像体积
# =============== Stage 1: builder ===============
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# 编译工具仅存在于 builder 阶段
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 将依赖安装到独立前缀，便于 runtime 阶段整体拷贝
RUN pip install --prefix=/install -r requirements.txt


# =============== Stage 2: runtime ===============
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# libmagic 预留给 WS3 文件头校验；curl 供容器内健康检查使用
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 curl tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && rm -rf /var/lib/apt/lists/*

# 复制 builder 阶段已安装好的 Python 依赖
COPY --from=builder /install /usr/local

COPY . .

# 启动脚本：先执行 Alembic 迁移，再拉起 uvicorn
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
