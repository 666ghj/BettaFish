# BettaFish 前端 HTTP / 实时接口说明

面向主 Web 界面（`templates/index.html`）及同源前端，基础地址为 Flask 服务根路径（默认 `http://<host>:9458`）。Report Engine 蓝图挂载在 `url_prefix='/api/report'`。

---

## 主应用（`app.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 主页面 |
| GET | `/auto-dashboard` | 自动仪表盘页 |
| GET | `/api/status` | 各子应用运行状态 |
| GET | `/api/start/<app_name>` | 启动指定应用 |
| GET | `/api/stop/<app_name>` | 停止指定应用 |
| GET | `/api/output/<app_name>` | 拉取控制台输出 |
| GET | `/api/test_log/<app_name>` | 测试日志推送 |
| GET | `/api/forum/start` | 启动论坛引擎 |
| GET | `/api/forum/stop` | 停止论坛引擎 |
| GET | `/api/forum/log` | 论坛日志 |
| POST | `/api/forum/log/history` | 论坛历史日志 |
| POST | `/api/search` | 搜索（联动各引擎） |
| GET | `/api/config` | 读取配置 |
| POST | `/api/config` | 保存配置 |
| GET | `/api/system/status` | 系统是否已启动等 |
| POST | `/api/system/start` | 保存配置并启动整套系统 |
| POST | `/api/system/shutdown` | 关闭系统 |
| GET | `/api/graph/<report_id>` | 指定报告图谱数据 |
| GET | `/api/graph/latest` | 最新报告图谱 |
| POST | `/api/graph/query` | 图谱查询（GraphRAG） |
| GET | `/graph-viewer` | 图谱查看页（含 `/graph-viewer/`、`/graph-viewer/<report_id>`） |

---

## Report Engine（前缀 `/api/report`，`ReportEngine/flask_interface.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/report/status` | 报告任务状态（支持心跳等查询参数） |
| POST | `/api/report/generate` | 触发生成报告 |
| GET | `/api/report/progress/<task_id>` | 任务进度 |
| GET | `/api/report/stream/<task_id>` | SSE 流式日志/事件 |
| GET | `/api/report/result/<task_id>` | 任务结果 |
| GET | `/api/report/result/<task_id>/json` | 结果 JSON |
| GET | `/api/report/download/<task_id>` | 下载结果 |
| POST | `/api/report/cancel/<task_id>` | 取消任务 |
| GET | `/api/report/templates` | 模板列表 |
| GET | `/api/report/log` | 报告引擎日志 |
| POST | `/api/report/log/clear` | 清空日志 |
| GET | `/api/report/export/md/<task_id>` | 导出 Markdown |
| GET | `/api/report/export/pdf/<task_id>` | 导出 PDF（如 `?optimize=true`） |
| POST | `/api/report/export/pdf-from-ir` | 从 IR 导出 PDF |

---

## Socket.IO（非 REST）

与 Flask 同源（默认与页面同一 `host:port`）。连接后可向服务端发送 `request_status`，服务端会推送 `status_update`、`console_output` 等事件。详见 `app.py` 中 `@socketio.on` 定义。

---

## 子引擎 Streamlit（非 Flask 路由）

主界面嵌入 iframe 时访问 `http://<host>:8501` / `8502` / `8503`（Insight / Media / Query），由独立 Streamlit 进程提供，不属于上表 REST 接口。
