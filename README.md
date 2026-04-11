# 基于 AI OCR 的药品信息识别与智能管理系统

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3.x-brightgreen.svg)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)

> 通过 AI OCR 技术自动识别药品包装图片，提取药品名称、规格、批号、有效期等关键信息，并提供完整的药品档案管理、库存管理、批次追踪、过期预警功能的智能化药品管理平台。

## ✨ 功能特性

- **OCR 智能识别** — 调用百度 OCR API 识别药品包装，正则引擎自动提取结构化字段
- **药品档案管理** — 药品信息 CRUD，支持按名称/批准文号/生产企业搜索
- **库存管理** — 入库/出库/盘点，实时追踪库存数量
- **批次管理** — 多批次追踪，自动计算有效期状态
- **过期预警** — 定时扫描临期/过期药品，分级预警通知
- **数据可视化** — ECharts 图表展示出入库趋势、过期分布
- **权限管理** — Admin / 药师 / 普通用户三级 RBAC

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 / FastAPI / SQLAlchemy 2.0 (async) |
| 数据库 | MySQL 8.0 / Alembic 迁移 |
| 认证 | JWT (python-jose + bcrypt) |
| OCR | 百度 OCR API |
| 定时任务 | APScheduler |
| 前端 | Vue 3 + TypeScript + Vite |
| UI | Element Plus + ECharts |
| 状态管理 | Pinia |

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example .env
# 编辑 .env，填写 DB_PASSWORD 和 BAIDU_OCR_API_KEY

# 初始化数据库
python init_db.py --password 你的MySQL密码

# 执行迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload
# 访问 http://localhost:8000/docs
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

## 📁 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # 路由层 (auth/drugs/ocr/inventory...)
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── services/       # 业务逻辑层
│   │   ├── ocr/            # OCR 识别引擎
│   │   └── tasks/          # APScheduler 定时任务
│   └── alembic/            # 数据库迁移
└── frontend/               # Vue 3 前端
    └── src/
        ├── views/          # 页面组件
        ├── components/     # 通用组件
        ├── stores/         # Pinia 状态
        └── api/            # Axios 封装
```

## 📄 License

[MIT](LICENSE)
