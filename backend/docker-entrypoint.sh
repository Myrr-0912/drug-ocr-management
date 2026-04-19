#!/bin/sh
# 后端容器启动脚本：
#   阶段 1（root）：修正挂载卷所有权，再 gosu 降权为 app 重新进入本脚本
#   阶段 2（app） ：执行 Alembic 迁移 + 启动 uvicorn
set -e

if [ "$(id -u)" = "0" ]; then
    # bind mount 的 /app/uploads 继承宿主目录 UID，需要修正给 app 才能写入
    chown -R app:app /app/uploads 2>/dev/null || true
    exec gosu app "$0" "$@"
fi

echo "[entrypoint] 运行 Alembic 数据库迁移..."
alembic upgrade head

echo "[entrypoint] 启动主进程：$*"
exec "$@"
