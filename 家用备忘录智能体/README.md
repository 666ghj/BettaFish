# 家用备忘录智能体

夫妻共享的家庭备忘录智能体，支持自然语言创建提醒、购物清单、收支记录、车辆管理、纪念日提醒等功能。

## MVP 功能

| 模块 | 说明 |
|------|------|
| **F1 缴费提醒** | 水费/电费/燃气费(每月) + 物业费(每半年)，逾期升级策略 |
| **F2 购物清单** | 家用(同意/待商榷) + 个人(老公/老婆)，评论机制 |
| **F3 收支记录** | 月度统计图表，自动关联 F1/F2/F4 消费 |
| **F4 车辆管理** | 车辆信息、保险/保养/年检提醒、用车支出、驾驶分 |
| **F7 纪念日** | 纪念日/生日提醒、安排项、喜好愿望记录 |
| **基础能力** | 微信登录、邀请码绑定、NLU 自然语言理解、提醒调度 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI + SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 |
| 缓存/队列 | Redis |
| LLM | OpenAI 兼容 API（Moonshot / DeepSeek / OpenAI） |
| 前端 | 微信小程序 |

## 快速开始

### 1. 后端

```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写数据库、微信小程序、LLM 等配置

# 初始化数据库
# 确保 MySQL 已运行，创建 family_memo 数据库
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload
```

### 2. Docker 部署

```bash
docker-compose up -d
```

### 3. 微信小程序

用微信开发者工具打开 `miniprogram/` 目录，修改 `utils/api.js` 中的 `BASE_URL` 为实际后端地址。

## 项目结构

```
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/          # API 路由（auth/family/chat/payment/shopping/finance/vehicle/anniversary）
│   │   ├── models/       # SQLAlchemy 模型（15张表）
│   │   ├── schemas/      # Pydantic 请求/响应
│   │   ├── services/     # 业务逻辑（NLU/时间解析/提醒调度/推送）
│   │   └── core/         # 基础设施（JWT/依赖注入/异常处理）
│   ├── alembic/          # 数据库迁移
│   └── requirements.txt
├── miniprogram/          # 微信小程序
│   ├── pages/            # 8个页面
│   └── utils/            # API 封装
├── docker-compose.yml
└── 家用备忘录智能体设计文档.md
```

## API 文档

启动后端后访问 `http://localhost:8000/docs` 查看 Swagger 文档。