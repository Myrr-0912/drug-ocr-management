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

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0
- Redis 6+

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，至少填写：
#   DB_PASSWORD          — MySQL 密码
#   JWT_SECRET_KEY       — 随机强密钥（≥32位）
#   ALIYUN_OCR_ACCESS_KEY_ID / ALIYUN_OCR_ACCESS_KEY_SECRET — 阿里云 AccessKey

# 执行数据库迁移
alembic upgrade head

# 启动服务（首次启动自动创建 admin 账号）
uvicorn app.main:app --reload
# API 文档：http://localhost:8000/docs
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
# 访问 http://localhost:5173
```

### 环境变量说明

| 变量 | 说明 | 必填 |
|------|------|------|
| `DB_PASSWORD` | MySQL 密码 | ✅ |
| `JWT_SECRET_KEY` | JWT 签名密钥（≥32位随机字符串） | ✅ |
| `ALIYUN_OCR_ACCESS_KEY_ID` | 阿里云 RAM AccessKey ID | ✅ |
| `ALIYUN_OCR_ACCESS_KEY_SECRET` | 阿里云 RAM AccessKey Secret | ✅ |
| `REDIS_HOST` | Redis 地址，默认 `localhost` | — |
| `SMTP_USER` / `SMTP_PASSWORD` | 阿里云 SMTP 账号（忘记密码功能） | — |
| `INITIAL_ADMIN_PASSWORD` | 首次启动创建的 admin 密码 | — |

## 📁 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # 路由层（auth/drugs/ocr/inventory/alerts/users）
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── services/       # 业务逻辑层
│   │   ├── ocr/            # OCR 识别引擎（阿里云客户端 + 文本解析器）
│   │   ├── core/           # 认证、异常、Redis、邮件工具
│   │   └── tasks/          # APScheduler 定时预警任务
│   └── alembic/            # 数据库迁移脚本
└── frontend/               # Vue 3 前端
    └── src/
        ├── views/          # 页面组件（登录/仪表盘/药品/OCR/预警/用户管理）
        ├── components/     # 通用组件
        ├── stores/         # Pinia 状态（auth/drug/alert）
        └── api/            # Axios 封装
```

## 📄 License

[MIT](LICENSE)
