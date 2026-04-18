# Docker Compose 启动指南

> 本文档适用于本地冒烟测试与后续生产部署（WS2）。生产上线的完整步骤见 `docs/DEPLOY.md`（WS2 产出）。

## 前置条件

- Docker Desktop ≥ 24.x（Windows/macOS）或 Docker Engine ≥ 24.x（Linux）
- Docker Compose v2
- 空闲磁盘 ≥ 5GB（镜像 + MySQL 初始数据）
- 端口 80、443 未被占用

## 准备环境变量

```bash
cp .env.production.example .env.production
```

编辑 `.env.production`，**必须**修改以下项：

| 变量 | 生成方式 |
|------|---------|
| `MYSQL_ROOT_PASSWORD` | 任意强密码 |
| `DB_PASSWORD` | 任意强密码（业务账号，非 root） |
| `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `REDIS_PASSWORD` | 任意强密码（可为空，但生产强烈建议设置） |
| `INITIAL_ADMIN_PASSWORD` | 至少 8 位，含大小写 + 数字 + 符号 |
| `ALIYUN_OCR_ACCESS_KEY_ID` / `ALIYUN_OCR_ACCESS_KEY_SECRET` | 阿里云 RAM 子账号 |
| `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `FRONTEND_URL` | 阿里云邮件推送（可选） |

## 启动

```bash
# 首次启动（构建镜像）
docker compose --env-file .env.production up -d --build

# 后续启动（复用已构建镜像）
docker compose --env-file .env.production up -d

# 查看日志
docker compose logs -f backend

# 停止
docker compose --env-file .env.production down

# 完全清理（含数据卷 —— 慎用）
docker compose --env-file .env.production down -v
```

## 验证

启动后依次验证：

1. **容器状态**：`docker compose ps` 全部 `running (healthy)`
2. **后端健康**：浏览器访问 `http://localhost/health` 返回 `{"status":"ok"}`
3. **前端登录**：浏览器打开 `http://localhost`，用 `.env.production` 中的 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 登录
4. **OCR 流程**：上传药品图片 → 识别 → 确认入库
5. **预警扫描**：登录后访问预警中心，或重启后观察 APScheduler 日志

## 常见问题

### JWT 密钥校验失败

启动日志出现 `JWT_SECRET_KEY 长度不能少于 32 个字符` —— 用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 重新生成。

### 端口冲突

`Error: port 80 already in use` —— Windows 上通常是 IIS 或 Skype 占用，也可以修改 `docker-compose.yml` 里 `nginx` 服务的端口映射为 `"8080:80"`。

### MySQL 首次启动慢

MySQL 容器首次启动需创建系统表，耗时 20-40 秒，`healthcheck` 会等待 `start_period: 30s`，这段时间后端会处于 `waiting`，属正常现象。

### 重新构建某个服务

```bash
docker compose --env-file .env.production build backend
docker compose --env-file .env.production up -d backend
```

## 数据持久化

- `./volumes/mysql` — MySQL 数据目录
- `./volumes/redis` — Redis AOF 持久化
- `./volumes/backend-uploads` — OCR 上传图片
- `./volumes/letsencrypt` — HTTPS 证书（WS2 上线时填充）

这些目录已加入 `.gitignore`，不会进入 Git 仓库。备份时只需打包整个 `volumes/` 即可。
