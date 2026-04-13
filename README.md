# 基于 AI OCR 的药品信息识别与智能管理系统

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3.x-brightgreen.svg)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)

> 通过阿里云 OCR 技术自动识别药品包装图片，提取药品名称、规格、批号、有效期等关键信息，并提供完整的药品档案管理、库存管理、批次追踪、过期预警及用户权限管理功能的智能化药品管理平台。

## ✨ 功能特性

- **OCR 智能识别** — 调用阿里云文字识别 API（RecognizeGeneral），正则引擎自动提取结构化字段
- **药品档案管理** — 药品信息 CRUD，支持按名称/批准文号/生产企业搜索
- **库存管理** — 入库/出库/盘点，实时追踪库存数量
- **批次管理** — 多批次追踪，自动计算有效期状态
- **过期预警** — 定时扫描临期/过期药品，分级预警通知
- **数据可视化** — ECharts 图表展示出入库趋势、过期分布
- **用户权限管理** — Admin / 药师 / 普通用户三级 RBAC，支持用户封禁与密码重置
- **安全加固** — JWT Access + Refresh Token 双令牌、Redis Token 黑名单、登录限流、邮件密码重置

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) |
| 数据库 | MySQL 8.0 / Alembic 迁移 |
| 缓存 | Redis（Token 黑名单 + 登录限流） |
| 认证 | JWT (python-jose + bcrypt) + Refresh Token 旋转 |
| OCR | 阿里云文字识别 API（alibabacloud_ocr_api20210707） |
| 邮件 | 阿里云 SMTP（aiosmtplib 异步发送） |
| 定时任务 | APScheduler |
| 前端 | Vue 3 + TypeScript + Vite |
| UI | Element Plus + ECharts |
| 状态管理 | Pinia |

---

## 🚀 快速开始

### 环境要求

| 服务 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行后端 |
| Node.js | 18+ | 运行前端 |
| MySQL | 8.0 | 主数据库 |
| Redis | 6+ | Token 管理 + 登录限流 |

先在 MySQL 中建库：

```sql
CREATE DATABASE drug_ocr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 启动后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # 编辑 .env，填写必填项（见下方环境变量说明）
alembic upgrade head        # 初始化数据库表结构
uvicorn app.main:app --reload
# API 文档：http://localhost:8000/docs
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 环境变量说明

| 变量 | 说明 | 必填 |
|------|------|------|
| `DB_PASSWORD` | MySQL 密码 | ✅ |
| `JWT_SECRET_KEY` | JWT 签名密钥（≥32位，可用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成） | ✅ |
| `ALIYUN_OCR_ACCESS_KEY_ID` | 阿里云 RAM AccessKey ID | ✅ |
| `ALIYUN_OCR_ACCESS_KEY_SECRET` | 阿里云 RAM AccessKey Secret | ✅ |
| `REDIS_HOST` | Redis 地址，默认 `localhost` | — |
| `SMTP_USER` / `SMTP_PASSWORD` | 阿里云 SMTP 账号（忘记密码功能） | — |
| `INITIAL_ADMIN_PASSWORD` | 首次启动创建的 admin 密码，默认 `Admin@2026!` | — |
| `EXPIRY_WARNING_DAYS` | 临期预警提前天数，默认 `30` | — |
| `LOW_STOCK_THRESHOLD` | 低库存预警阈值（件），默认 `10` | — |

---

## 👋 使用指南

首次启动后端时会自动创建管理员账号，使用以下信息登录：

- **用户名**：`admin`
- **密码**：`.env` 中 `INITIAL_ADMIN_PASSWORD` 的值（默认 `Admin@2026!`）

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
        ├─ 启动 APScheduler：每天 00:05 执行预警扫描
        └─ 挂载路由 /api/v1/* 及静态文件 /uploads/*
```

### 2. 认证流程

```
登录 POST /api/v1/auth/login
        ├─ 校验密码（bcrypt）+ 检查封禁状态 + 登录限流（Redis 计数）
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
        ├─ 调用阿里云 OCR（线程池中执行，不阻塞事件循环）
        │       └─ 返回 raw_text + confidence
        ├─ 正则解析：药品名称 / 批准文号 / 规格 / 生产企业 / 批号 / 有效期
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
│   │   ├── ocr/            # OCR 识别引擎（阿里云客户端 + 文本解析器）
│   │   ├── core/           # 认证、异常、Redis、邮件工具
│   │   └── tasks/          # APScheduler 定时预警任务
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
