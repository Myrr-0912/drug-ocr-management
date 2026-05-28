# 基于 AI OCR 的药品信息识别与智能管理系统

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3.x-brightgreen.svg)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)

> 通过 Qwen-OCR 视觉文字识别模型自动识别药品包装图片，提取药品名称、规格、批号、有效期等关键信息，并提供完整的药品档案管理、库存管理、批次追踪、过期预警及用户权限管理功能的智能化药品管理平台。

## ✨ 功能特性

- **OCR 智能识别** — 调用通义千问 Qwen-OCR 模型（qwen-vl-ocr-latest），模型抽取与正则兜底双路提取结构化字段
- **药品档案管理** — 药品信息 CRUD，支持按名称/批准文号/生产企业搜索
- **库存管理** — 入库/出库/盘点，实时追踪库存数量
- **批次管理** — 多批次追踪，自动计算有效期状态
- **过期预警** — 定时扫描临期/过期药品，分级预警通知
- **数据可视化** — ECharts 图表展示出入库趋势、过期分布
- **用户权限管理** — Admin / 药师 / 普通用户三级 RBAC，支持用户封禁与密码重置
- **安全加固** — JWT Access + Refresh Token 双令牌、Redis Token 黑名单、登录限流、邮件密码重置
- **账号系统** — 注册强制绑定邮箱（数据库唯一索引）、支持用户名或邮箱双方式登录、精确区分「账号不存在」与「密码错误」提示

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) |
| 数据库 | MySQL 8.0 / Alembic 迁移 |
| 缓存 | Redis（Token 黑名单 + 登录限流） |
| 认证 | JWT (python-jose + bcrypt) + Refresh Token 旋转 |
| OCR | 通义千问 Qwen-OCR（qwen-vl-ocr-latest，阿里云百炼） |
| 邮件 | 阿里云 SMTP（aiosmtplib 异步发送） |
| 定时任务 | asyncio 后台任务（每天 00:05 执行） |
| 前端 | Vue 3 + TypeScript + Vite |
| UI | Element Plus + ECharts |
| 状态管理 | Pinia |

---

## 🚀 快速开始

项目提供两条启动路线：

- **Docker 部署**：一条命令拉起 MySQL、Redis、后端、前端和 Nginx，适合完整部署或本地冒烟。
- **本地开发**：Docker 只启动 Redis，本机 MySQL + 本机后端 + 本机前端，适合热更新调试。

### 路线一：Docker 部署

一条命令拉起前后端全栈（MySQL + Redis + FastAPI 后端 + Vue 前端 + Nginx 反代），宿主机无需安装 Python / Node / 数据库。

**前置条件**

- Docker Desktop ≥ 24（Windows / macOS）或 Docker Engine ≥ 24（Linux），含 Docker Compose v2
- 宿主机端口 `18080`、`18443` 空闲

**启动命令**

```bash
# 1. 准备环境变量：复制模板后编辑，至少填写所有 REPLACE_* 项（密钥 / 密码）
cp .env.example .env

# 2. 一键启动（首次会构建镜像，耗时数分钟）
docker compose up -d --build

# 3. 浏览器访问 http://localhost:18080
```

启动完成后，用 `.env` 中的 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 登录。

**常用命令**

```bash
docker compose ps               # 查看容器状态（应全部 healthy）
docker compose logs -f backend  # 跟踪后端日志
docker compose down             # 停止全部服务
docker compose up -d --build    # 修改代码后重建并重启
```

> Compose 会自动加载项目根目录的 `.env`，无需 `--env-file` 等额外参数。
> `.env` 各项含义与必填项见模板文件 `.env.example`；完整部署与排错说明见 [docs/DOCKER.md](docs/DOCKER.md)。

---

### 路线二：本地开发

这条路线只用 Docker 启动 Redis，MySQL、后端和前端都在宿主机运行。环境变量写在 `backend/.env`（与 Docker 部署使用的根目录 `.env` 相互独立、互不影响）。

#### 环境要求

| 服务 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行后端 |
| Node.js | 18+ | 运行前端 |
| MySQL | 8.0 | 本机主数据库 |
| Docker | 20+ | 启动 Redis 容器 |

#### 首次准备

1. 启动本机 MySQL，并创建数据库：

```sql
CREATE DATABASE drug_ocr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 准备后端虚拟环境和配置：

```bash
cd backend
python -m venv .venv
```

**激活虚拟环境** —— 按操作系统二选一：

| 系统 | 激活命令 |
|------|---------|
| Windows（PowerShell） | `.\.venv\Scripts\Activate.ps1` |
| macOS / Linux | `source .venv/bin/activate` |

> Windows 首次激活若提示「禁止运行脚本」，先执行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 放行后重试。

激活虚拟环境后安装依赖并初始化数据库：

```bash
pip install -r requirements.txt
cp .env.example .env        # 编辑 .env，填写本机 MySQL、JWT、OCR 等配置
alembic upgrade head
```

3. 准备前端依赖：

```bash
cd ../frontend
npm install
```

#### 日常启动

如需热更新开发，分别在三个终端启动 Redis、后端和前端：

```powershell
# 1. Redis（在项目根目录执行，复用唯一的 docker-compose.yml）
docker compose up -d redis

# 2. 后端（端口 8000；使用项目虚拟环境，避免调用全局 uvicorn）
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 3. 前端（Vite 热更新，已代理 /api 和 /uploads 到 localhost:8000）
cd frontend
npm run dev
```

> 后端必须通过虚拟环境里的 Python 启动；如果直接运行全局 `uvicorn`，可能会找不到 `cv2` 等已安装在项目虚拟环境中的依赖。

访问地址：

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |

常用命令：

```bash
docker compose ps redis
docker compose logs -f redis
docker compose down
```

#### 环境变量说明

| 变量 | 说明 | 必填 |
|------|------|------|
| `DB_PASSWORD` | MySQL 密码 | ✅ |
| `JWT_SECRET_KEY` | JWT 签名密钥（≥32位，可用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成） | ✅ |
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（qwen-vl-ocr） | ✅ |
| `REDIS_HOST` | Redis 地址，默认 `localhost` | — |
| `REDIS_PASSWORD` | 本地开发 Redis 密码；如根目录 `.env` 配了 `REDIS_PASSWORD`，这里需保持一致，否则留空 | — |
| `SMTP_USER` / `SMTP_PASSWORD` | 阿里云 SMTP 账号（忘记密码功能） | — |
| `INITIAL_ADMIN_PASSWORD` | 首次启动创建的 admin 密码，默认 `Admin@2026!` | — |
| `EXPIRY_WARNING_DAYS` | 临期预警提前天数，默认 `30` | — |
| `LOW_STOCK_THRESHOLD` | 低库存预警阈值（件），默认 `10` | — |

---

## 👋 使用指南

首次启动后端时会自动创建管理员账号，使用以下信息登录：

- **用户名**：`admin`（或注册时绑定的邮箱）
- **密码**：`.env` 中 `INITIAL_ADMIN_PASSWORD` 的值（默认 `Admin@2026!`）

> 注册新账号时**邮箱为必填项**（全局唯一），用于「忘记密码」邮件找回；登录时可输入用户名或邮箱。

### 角色与权限

| 角色 | 可访问页面 |
|------|-----------|
| 所有登录用户 | 仪表盘、药品档案、批次管理、库存流水、预警中心、个人中心 |
| 药师及以上 | OCR 识别上传、入库操作 |
| 仅管理员 | 用户管理（创建/封禁/重置密码）、登录审计日志 |

### 典型操作流程

**新药入库（药师）**
```
OCR 识别 → 上传药品包装图片
        → 系统自动提取药品名称 / 批号 / 有效期等字段
        → 核对后点击「确认入库」（自动创建药品档案与批次）
        → 库存管理 → 入库，录入实际数量
```

**日常库存管理**
```
药品列表 → 进入药品详情 → 查看各批次状态与库存数量
库存管理 → 出库 / 盘点调整 → 生成流水记录
```

**预警处理**
```
预警中心 → 查看临期 / 过期 / 低库存预警
        → 处理完毕后标记「已解决」
```

**忘记密码**
```
登录页「忘记密码」→ 填写注册邮箱 → 收取重置邮件 → 设置新密码
```

**管理员创建新用户**
```
用户管理 → 新建用户 → 分配角色（药师 / 普通用户）→ 告知初始密码
```

---

## 🏗 系统运行逻辑

### 1. 后端启动流程

```
uvicorn app.main:app
        │
        ├─ 创建 uploads/ 目录（存储上传图片）
        ├─ 初始化 Redis 连接池（失败则终止启动）
        ├─ 首次启动自动创建 admin 账号（users 表为空时生效）
        ├─ 启动后台定时任务：每天 00:05 执行预警扫描
        └─ 挂载路由 /api/v1/* 及静态文件 /uploads/*
```

### 2. 认证流程

```
登录 POST /api/v1/auth/login
        ├─ 支持用户名或邮箱作为登录凭证
        ├─ 账号不存在 → 返回「该账号未注册，请先注册」
        ├─ 密码错误  → 返回「密码错误，请重新输入」
        ├─ 检查封禁状态 + 登录限流（Redis 计数）
        ├─ 签发 Access Token（60 分钟）
        └─ 签发 Refresh Token（7 天，存入 Redis 白名单）

后续请求：Header 携带 Bearer <AccessToken>
        └─ JWT 解码 → 校验 Redis 黑名单 → 注入 current_user

Token 续期 POST /api/v1/auth/refresh
        ├─ 验证 Refresh Token 在白名单中
        ├─ 签发新 Access Token + 新 Refresh Token（旋转刷新）
        └─ 旧 Refresh Token 立即失效（防重放）

登出 POST /api/v1/auth/logout
        ├─ Access Token 加入 Redis 黑名单
        └─ Refresh Token 从白名单删除

忘记密码 POST /api/v1/auth/forgot-password
        ├─ 生成重置 Token 存入 Redis（15 分钟有效）
        └─ 阿里云 SMTP 发送含重置链接的邮件
                └─ 用户点击 → POST /api/v1/auth/reset-password → 更新密码
```

### 3. OCR 识别入库流程

```
上传 POST /api/v1/ocr/upload
        ├─ 校验文件类型（JPG/PNG/BMP/WebP）及大小（≤10MB）
        ├─ 保存图片到 uploads/ocr/<uuid>.jpg
        ├─ 创建 OcrRecord（status: pending）
        ├─ 图像预处理 + 调用 qwen-vl-ocr 识别（异步 httpx）
        │       └─ 返回 raw_text + 模型结构化字段 + 完整度置信度
        ├─ 模型抽取 + 正则兜底合并：药品名称 / 批准文号 / 规格 / 生产企业 / 批号 / 有效期
        └─ 更新 OcrRecord（status: success，存储 extracted_data）

确认入库 POST /api/v1/ocr/{id}/confirm
        ├─ 按药品名+批准文号查重，不存在则创建 Drug 记录
        ├─ 根据有效期计算批次状态（normal / near_expiry / expired）
        ├─ 创建 DrugBatch 记录，关联 source_ocr_id
        └─ OcrRecord 状态更新为 confirmed
```

### 4. 库存与预警流程

```
入库/出库/盘点
        ├─ 变更 DrugBatch.quantity
        └─ 写入 InventoryLog 流水（类型 / 数量 / 操作人 / 时间）

预警扫描（每天 00:05 自动 或 管理员手动触发）
        ├─ expiry_date < today       → 已过期预警
        ├─ expiry_date ≤ today+30天  → 临期预警
        ├─ quantity ≤ 10             → 库存不足预警
        └─ 同批次同类型去重写入 Alert 表
```

### 5. API 端点总览

| 模块 | 前缀 | 主要端点 |
|------|------|---------|
| 认证 | `/api/v1/auth` | login / logout / refresh / register / forgot-password / reset-password |
| 药品 | `/api/v1/drugs` | CRUD + 分页搜索 |
| OCR | `/api/v1/ocr` | upload / confirm / list / delete |
| 批次 | `/api/v1/batches` | CRUD + 状态筛选 |
| 库存 | `/api/v1/inventory` | stock-in / stock-out / adjust / 流水查询 |
| 预警 | `/api/v1/alerts` | list / scan / read / resolve / stats |
| 统计 | `/api/v1/stats` | overview / inventory-trend / expiry-distribution |
| 管理员 | `/api/v1/admin` | 用户 CRUD / 重置密码 / 登录日志 |

---

## 📁 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # 路由层（auth/drugs/ocr/inventory/alerts/stats/admin）
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── services/       # 业务逻辑层
│   │   ├── ocr/            # OCR 识别引擎（图像预处理 + Qwen-OCR 客户端 + 流水线 + 文本解析）
│   │   ├── core/           # 认证、异常、Redis、邮件工具
│   │   └── tasks/          # asyncio 后台定时预警任务
│   └── alembic/            # 数据库迁移脚本
└── frontend/
    └── src/
        ├── views/          # 页面组件
        ├── components/     # 通用组件
        ├── stores/         # Pinia 状态管理
        └── api/            # Axios 封装
```

## 📄 License

[MIT](LICENSE)
