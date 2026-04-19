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

# libmagic 预留给 WS3 文件头校验；tzdata 设置时区；gosu 供 entrypoint 降权
# 健康检查改用 Python stdlib，省去 curl 依赖 + 减小镜像体积
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 tzdata gosu \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 运行用户（UID 固定便于 volume 权限匹配）
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home-dir /app --shell /sbin/nologin app

# 复制 builder 阶段已安装好的 Python 依赖
COPY --from=builder /install /usr/local

# 源码 & 启动脚本：直接以 app:app 为所有者拷入
COPY --chown=app:app . .
COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p uploads \
    && chown -R app:app /app

# 注意：不在此处 USER app。
# entrypoint 以 root 进入，先修正挂载卷所有权（bind mount 会继承宿主 UID），
# 再用 gosu 降权到 app 运行 alembic 与 uvicorn，避免容器内以 root 执行业务代码。

EXPOSE 8000

# 非 root 友好：用 Python stdlib 探活，非 0 退出即视为不健康
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
