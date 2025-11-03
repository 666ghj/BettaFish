# Next.js 适配层

这是一个专门为 Next.js 项目提供 API 接口的适配层，不会破坏 BettaFish 原有的项目结构。

## 目录说明

```
NextJSAdapter/
├── __init__.py                  # 包初始化
├── query_engine_server.py       # QueryEngine Flask API 服务 (端口 8503)
├── report_engine_server.py      # ReportEngine Flask API 服务 (端口 8502)
├── start_all_services.py        # 统一启动脚本
├── check_config.py              # 配置检查工具
├── verify_services.py           # 服务验证工具
└── README.md                    # 本文档
```

## 为什么需要适配层？

BettaFish 原项目主要使用 Streamlit 作为界面，而 Next.js 项目需要 REST API 接口。这个适配层提供了：

1. **QueryEngine Flask API** (端口 8503)
   - 独立的 Flask 服务
   - 提供 RESTful API 接口
   - 不影响原有 QueryEngine 功能

2. **ReportEngine Flask API** (端口 8502)
   - 独立的 Flask 服务
   - 封装 ReportEngine 的 Blueprint
   - 不依赖完整的 BettaFish app.py

## 快速启动

### 前置检查（重要！）

在启动服务前，先检查配置是否正确：

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python check_config.py
```

如果配置有问题，脚本会提供详细的修复建议。

### 方法 1: 使用统一启动脚本（推荐）

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python start_all_services.py
```

这会同时启动：
- QueryEngine 服务 (端口 8503)
- ReportEngine 服务 (端口 8502)

### 方法 2: 分别启动

#### 启动 QueryEngine
```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python query_engine_server.py
```

#### 启动 ReportEngine（新窗口）
```powershell
cd d:\myReact\BettaFish
python app.py
```

## API 端点

### QueryEngine API (端口 8503)

#### 健康检查
```
GET http://localhost:8503/health
```

#### 获取状态
```
GET http://localhost:8503/api/status
```

#### 开始搜索
```
POST http://localhost:8503/api/search
Content-Type: application/json

{
  "query": "搜索关键词",
  "toolName": "general_search",
  "kwargs": {}
}
```

#### 获取进度
```
GET http://localhost:8503/api/progress/{task_id}
```

#### 获取结果
```
GET http://localhost:8503/api/result/{task_id}
```

### ReportEngine API (端口 8502)

详见 BettaFish 项目的 `ReportEngine/flask_interface.py`

## 验证服务

启动后，在浏览器中访问：

- QueryEngine: http://localhost:8503/api/status
- ReportEngine: http://localhost:8502/api/report/status

应该都返回 JSON 格式的状态信息。

## 依赖要求

确保已安装：

```bash
pip install flask flask-cors
```

其他依赖与 BettaFish 项目相同。

## 与 Next.js 集成

Next.js 项目通过 API Routes 代理这两个服务：

```
Next.js (localhost:3000)
  ↓
API Routes (/api/query/*, /api/report/*)
  ↓
QueryEngine (localhost:8503) & ReportEngine (localhost:8502)
```

## 故障排查

### 问题: 端口被占用

**Windows PowerShell:**
```powershell
# 查看端口占用
netstat -ano | findstr "8503"
netstat -ano | findstr "8502"

# 结束进程
taskkill /PID <进程ID> /F
```

### 问题: 返回 HTML 而不是 JSON

这通常意味着服务未正确启动或路由配置错误。确保：

1. 使用本适配层的启动脚本
2. 检查服务是否正常运行
3. 访问正确的 API 路径

### 问题: QueryEngine 初始化失败

检查 BettaFish 项目的配置文件：
- `config.py` 是否存在
- API Key 是否配置正确

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Project                      │
│                  (localhost:3000)                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ HTTP Requests
                  │
    ┌─────────────┴──────────────┐
    │                            │
    ▼                            ▼
┌──────────────────┐    ┌──────────────────┐
│  QueryEngine API │    │ ReportEngine API │
│  (port 8503)     │    │  (port 8502)     │
│                  │    │                  │
│  Flask Server    │    │  Flask Server    │
│  (适配层)         │    │  (原项目)         │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │                       │
         ▼                       ▼
    ┌──────────────────────────────┐
    │     QueryEngine Module       │
    │     (原项目核心逻辑)           │
    └──────────────────────────────┘
```

## 注意事项

1. **不修改原项目**: 所有适配代码都在 `NextJSAdapter` 目录中
2. **独立运行**: 可以独立于 BettaFish 原界面运行
3. **CORS 支持**: 已配置 CORS，支持跨域请求
4. **线程安全**: 使用锁机制保证任务安全

## 更新日志

### v1.0.0 (2025-11-06)
- 初始版本
- 提供 QueryEngine Flask API
- 统一启动脚本

---

**维护者**: BettaFish & Next.js 集成项目
**最后更新**: 2025年11月6日
