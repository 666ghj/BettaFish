# agno-mirofish

> 基于 [agno](https://github.com/agno-agi/agno) 框架重构的多 Agent 舆情分析系统，迁移自 [BettaFish (微舆)](https://github.com/666ghj/BettaFish)。

三个专业 Agent 并发工作，通过共享论坛 + 主持人引导实现段落级反馈，最终由 ReportAgent 综合产出含 Chart.js 图表、KPI 卡片、信息源矩阵等可视化组件的专业 HTML 报告。

---

## ✨ 核心特性

- **三 Agent 并发协作**：InsightAgent（社交媒体舆情）、MediaAgent（多模态网页）、QueryAgent（新闻深度调查）异步并行
- **段落级 Forum 反馈**：每个 agent 产出一段总结后写入共享 ForumState，达到阈值自动触发 ForumHost 主持人发言，反向引导下一段写作（保留 BettaFish 的核心反馈循环）
- **18 个工具开箱即用**：本地 SQLite 数据库（mock）、Tavily 新闻、Bocha 多模态、Hacker News、GitHub、YouTube、Reddit
- **海外平台动态裁剪**：根据 `.env` 中实际配置的 key 自动裁剪可用工具，未配置的不会进入 prompt 也不会被调用
- **专业可视化报告**：6 种自定义可视化组件（KPI 卡片、Chart.js 图表、信息源矩阵、事件时间线、Callout、Quote 卡片）+ 响应式 HTML
- **真正的 agno 集成**：核心 LLM 调用走 agno Agent，自动处理重试/日志/异步

---

## 🏗 架构

```
                         用户输入: "Claude Code 在中文程序员社区的舆情分析"
                                              │
                                              ▼
       ┌──────────────────────── opinion_team.py (asyncio.gather) ────────────────────────┐
       │                                                                                  │
       ▼                          ▼                                ▼                       │
┌──────────────┐         ┌──────────────┐                ┌──────────────┐                 │
│ InsightAgent │         │  MediaAgent  │                │  QueryAgent  │                 │
│              │         │              │                │              │                 │
│ • 6 国内DB工具│         │ • 5 Bocha工具│                │ • 6 Tavily工具│                 │
│ • 12 海外工具 │         │              │                │              │                 │
│ • 多步流程    │         │ • 多步流程   │                │ • 多步流程    │                 │
│ • 段落总结   │         │ • 段落总结   │                │ • 段落总结    │                 │
└──────┬───────┘         └──────┬───────┘                └──────┬───────┘                 │
       │ 段落写入               │ 段落写入                       │ 段落写入                  │
       └────────────────┬───────┴────────────────────────────────┘                          │
                        ▼                                                                   │
              ┌──────────────────┐                                                          │
              │   ForumState     │ ◄── 累计 N 条触发                                         │
              │ (asyncio Lock)   │                                                          │
              └────────┬─────────┘                                                          │
                       │                                                                    │
                       ▼                                                                    │
              ┌──────────────────┐                                                          │
              │   ForumHost      │ ── 主持人发言 ──┐                                         │
              │  (agno Agent)    │                │                                         │
              └──────────────────┘                │                                         │
                                                  │                                         │
                                  ◄───────────────┘                                         │
                                  下一段写作时 agent 读取 HOST 引导，调整写作方向                │
                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                          三份 agent 报告 + forum_log + host_speeches
                                              │
                                              ▼
                                ┌─────────────────────────┐
                                │      ReportAgent        │
                                │   (4 个 agno Agent)     │
                                │                         │
                                │ Stage 1: 大纲规划       │
                                │ Stage 2: 6章节并发写作  │
                                │ Stage 3: 跨源验证       │
                                │ Stage 4: 执行摘要       │
                                │ Stage 5: HTML 渲染      │
                                └─────────────┬───────────┘
                                              │
                                              ▼
                          final_report.md + final_report.html (含 36+ 可视化组件)
```

---

## 📦 安装

### 1. 环境要求

- Python 3.10+
- conda 推荐（项目用 `agno_mirofish` 环境名）
- macOS / Linux（Windows 未测试）

### 2. 克隆并安装依赖

```bash
git clone https://github.com/NextE-Moffatt/agno-mirofish.git
cd agno-mirofish

conda create -n agno_mirofish python=3.10
conda activate agno_mirofish

pip install -r requirements.txt
```

### 3. 配置 `.env`

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

**最低可用配置**（只跑 QueryAgent）：

```env
QUERY_ENGINE_API_KEY=sk-xxx
QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat
TAVILY_API_KEY=tvly-xxx
```

**完整配置**（三个 agent + ReportAgent + ForumHost）：

```env
# 三个核心 Agent 的 LLM
INSIGHT_ENGINE_API_KEY=sk-xxx
INSIGHT_ENGINE_BASE_URL=https://api.deepseek.com
INSIGHT_ENGINE_MODEL_NAME=deepseek-chat

MEDIA_ENGINE_API_KEY=sk-xxx
MEDIA_ENGINE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MEDIA_ENGINE_MODEL_NAME=qwen3-vl-plus

QUERY_ENGINE_API_KEY=sk-xxx
QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat

# ForumHost 主持人（推荐 qwen-plus）
FORUM_HOST_API_KEY=sk-xxx
FORUM_HOST_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FORUM_HOST_MODEL_NAME=qwen-plus

# ReportAgent 综合报告生成（推荐 gemini-2.5-pro 或 qwen-plus）
REPORT_ENGINE_API_KEY=sk-xxx
REPORT_ENGINE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
REPORT_ENGINE_MODEL_NAME=qwen-plus

# 搜索 API
TAVILY_API_KEY=tvly-xxx                  # QueryAgent 必需
BOCHA_WEB_SEARCH_API_KEY=sk-xxx          # MediaAgent 必需

# 海外数据源（可选，未配置时自动跳过）
GITHUB_TOKEN=ghp_xxx                     # 可选，无 token 限速 60/h
YOUTUBE_API_KEY=AIzaSy-xxx               # 可选
REDDIT_CLIENT_ID=xxx                     # 可选
REDDIT_CLIENT_SECRET=xxx                 # 可选

# InsightAgent 本地数据库（用 mock 时填这两行）
DB_DIALECT=sqlite
DB_NAME=/绝对路径/agno-mirofish/data/mock_yuqing.db
```

### 4. 初始化 Mock 数据库（首次运行 InsightAgent 必做）

```bash
python scripts/init_mock_db.py
```

这会创建 `data/mock_yuqing.db`，包含 14 张表（7 内容表 + 7 评论表）和约 100 条围绕"Claude Code"主题的假数据。

如果你想跑真实数据，需要自己部署 MediaCrawler PostgreSQL 数据库（参考 [BettaFish 文档](https://github.com/666ghj/BettaFish)）。

---

## 🚀 使用

### 完整流程：三 Agent 并发 + ForumHost + ReportAgent

```bash
python run_full_pipeline.py "你的分析主题"
```

**示例**：

```bash
python run_full_pipeline.py "Claude Code 在中文程序员社区的舆情分析"
python run_full_pipeline.py "2026 美国大选舆情走势"
python run_full_pipeline.py "苹果 Vision Pro 中国市场反响"
```

**可选参数**：

```bash
# 调整 Host 触发阈值（默认 5 条 agent 段落触发一次）
python run_full_pipeline.py "..." --threshold 3

# 跳过 ReportAgent 综合报告生成（节省时间）
python run_full_pipeline.py "..." --no-report

# 自定义输出目录
python run_full_pipeline.py "..." --output reports/my_reports
```

**输出**（保存在 `reports/full_pipeline/{主题}_{时间戳}/`）：

| 文件 | 说明 |
|---|---|
| `insight_report.md` | InsightAgent 独立报告 |
| `media_report.md` | MediaAgent 独立报告 |
| `query_report.md` | QueryAgent 独立报告 |
| `forum_log.txt` | 完整论坛对话日志 |
| `host_speeches.md` | 主持人 N 次引导发言 |
| **`final_report.md`** | **综合报告 Markdown** |
| **`final_report.html`** | **专业 HTML 报告（含 Chart.js 图表）** |
| `summary.json` | 结构化元数据 |

### 单 Agent 独立运行

```bash
python run_single_agent.py insight "某品牌产品危机舆情"
python run_single_agent.py media   "AI 编程工具市场对比"
python run_single_agent.py query   "某国际事件深度调查"
```

每个 agent 独立产出 markdown 报告，不走 Forum 协作。适合调试单 agent 或验证某个数据源。

---

## 🛠 项目结构

```
agno-mirofish/
├── agno_tools/                  # 工具层（@tool 装饰）
│   ├── db_query_tools.py        # InsightAgent 6 个本地 DB 工具
│   ├── news_search_tools.py     # QueryAgent 6 个 Tavily 工具
│   ├── media_search_tools.py    # MediaAgent 5 个 Bocha 工具
│   ├── hackernews_tools.py      # 3 个 HN 工具（无需 key）
│   ├── github_tools.py          # 3 个 GitHub 工具
│   ├── youtube_tools.py         # 3 个 YouTube 工具
│   ├── reddit_tools.py          # 3 个 Reddit 工具
│   └── sentiment_tools.py       # 多语言情感分析（transformers）
│
├── agno_agents/                 # Agent 层
│   ├── models.py                # 共享 pydantic 模型（AnalysisResult 等）
│   ├── insight_agent.py         # InsightAgent + 完整 prompt
│   ├── media_agent.py           # MediaAgent + 完整 prompt
│   ├── query_agent.py           # QueryAgent + 完整 prompt
│   ├── report_agent.py          # ReportAgent (5 阶段 + 4 个 agno Agent)
│   ├── report_blocks.py         # 自定义可视化标签解析器
│   └── report_styles.py         # 专业 CSS + Chart.js CDN
│
├── agno_team/                   # 编排层
│   ├── _agno_setup.py           # ⭐ 必须最先导入：清代理 + patch agno httpx
│   ├── forum_state.py           # 共享论坛状态（asyncio Lock）
│   ├── forum_host.py            # 主持人 (agno Agent)
│   ├── agent_runner.py          # 单 agent 多步异步流程
│   └── opinion_team.py          # 三 agent asyncio.gather 调度
│
├── scripts/
│   └── init_mock_db.py          # 初始化 SQLite mock 数据库
│
├── run_single_agent.py          # 单 agent 命令行入口
├── run_full_pipeline.py         # 完整流程命令行入口
├── config.py                    # pydantic-settings 配置（从 .env 读取）
├── requirements.txt
└── README.md
```

---

## 🎨 报告可视化组件

ReportAgent 生成的 HTML 报告支持以下专业组件，全部由 LLM 在 prompt 引导下输出，渲染器自动转换：

| 组件 | 标签 | 用途 |
|---|---|---|
| **KPI 数据卡片** | `<kpi-grid>` | 4-6 个核心指标，带 tone（up/down/neutral）和 delta 变化值 |
| **Chart.js 图表** | `<chart-card>` | bar / line / pie / doughnut / radar，自动注入主题色 |
| **Callout 提示框** | `<callout type>` | info / insight / warning / danger / success 五种语义色 |
| **信息源矩阵** | `<info-matrix>` | 三 Agent 覆盖度可视化（★★★ 主力 / ★★ 部分 / ★ 弱 / — 无）|
| **事件时间线** | `<timeline>` | 圆点 + 日期 + 事件，支持 release/crisis/update 不同颜色 |
| **用户原声卡片** | `<quote-card>` | 带装饰引号，显示作者/平台/点赞数 |

一份典型报告会包含 30+ 个可视化组件。

---

## 🔧 常见问题

### Q: 报错 `connection refused` / `proxy error`？

A: 你的系统设置了 SOCKS/HTTP 代理。`agno_team/_agno_setup.py` 已经做了全局 patch，理论上自动处理。如果仍然报错，尝试：

```bash
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
python run_full_pipeline.py "..."
```

### Q: ForumHost 报错 `Model Not Exist`？

A: 你的 `FORUM_HOST_*` 三个字段配置不一致（key/base_url/model 分属不同提供商）。修正 `.env`，确保三个字段同属一家厂商。

### Q: InsightAgent 报错 `database is locked` 或 `no such table`？

A: 没有运行 mock DB 初始化脚本。执行：

```bash
python scripts/init_mock_db.py
```

### Q: Bocha API 返回 403？

A: Bocha 账户余额不足。可以选择充值或临时改用 Tavily（修改 `MediaAgent` 的工具配置）。

### Q: 某个海外平台（YouTube/Reddit）的工具调用失败？

A: 检查 `.env` 中对应的 key 是否配置。**未配置的工具会自动从 InsightAgent 的工具列表中移除，不会出现在 LLM 的 prompt 里**，所以一般不会触发失败。如果还是失败，可能是 API 限速。

---

## 📋 开发笔记

### agno 框架使用情况

| 模块 | 是否使用 agno |
|---|---|
| ForumHost | ✅ agno Agent |
| ReportAgent (5 阶段) | ✅ 4 个专用 agno Agent |
| 三 agent 多步流程的 LLM 调用 | ✅ 通过缓存的 agno Agent |
| 工具函数 | `@tool` 装饰器（保留以备 agent 自主调用模式）|
| 三 agent 协作 | ❌ asyncio.gather（agno Team 会丢失段落级反馈）|
| 工具 dispatch | ❌ 手写（保留以维持精细控制）|

### 关键设计决策

1. **段落级反馈循环**：保留 BettaFish 最核心的特性 —— 每个 agent 产出段落总结后立即被 ForumHost 看到，反向影响下一段。这不能用 agno Team 实现。

2. **代理 patch 全局化**：`agno_team/_agno_setup.py` 必须在所有 agno import 之前导入，否则 agno 会缓存系统代理配置导致无法连接 LLM API。

3. **三档 API 回退**：所有 Agent 的 API key 配置都支持回退（如 ReportAgent: `REPORT_*` → `FORUM_HOST_*` → `QUERY_ENGINE_*`），但**必须三个字段一组回退**，避免出现 DeepSeek 的 key 配 aihubmix base_url 这种荒谬情况。

4. **海外工具动态裁剪**：`_detect_available_overseas()` 在创建 InsightAgent 时检查每个海外平台 key 是否配置，未配置的工具完全不进入 tools 列表也不进入 prompt。

---

## 📜 致谢

- 原项目：[BettaFish (微舆)](https://github.com/666ghj/BettaFish) — 多 Agent 舆情分析系统的完整工程实现
- 框架：[agno](https://github.com/agno-agi/agno) — Python multi-agent framework
- 数据源：Tavily / Bocha / Hacker News / GitHub / YouTube / Reddit / MediaCrawler

---

## 📄 License

MIT
