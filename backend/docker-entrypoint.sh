#!/bin/sh
# 后端容器启动脚本：迁移数据库后执行主进程
set -e

echo "[entrypoint] 运行 Alembic 数据库迁移..."
alembic upgrade head

echo "[entrypoint] 启动主进程：$*"
exec "$@"
