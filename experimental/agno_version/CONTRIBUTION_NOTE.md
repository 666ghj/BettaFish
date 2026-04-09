# 基于 agno 框架的重构实验

本目录是 BettaFish 项目的一个实验性重构版本，基于 [agno](https://github.com/agno-agi/agno) 多智能体框架。

---

## 🔗 与原项目的关系

- **完全独立**：本目录代码不影响原 BettaFish 任何文件（只新增，不修改）
- **架构差异**：

| 维度 | 原 BettaFish | 本 agno 版本 |
|---|---|---|
| 进程模型 | Flask + 3 个 Streamlit 子进程 | 单进程 asyncio |
| Agent 间通信 | `logs/*.log` 文件 + LogMonitor 轮询 | 内存共享 `ForumState` + `asyncio.Lock` |
| LLM 编排 | 自定义 Node 系统（`nodes/`, `state/`, `llms/`） | agno `Agent` |
| 工具定义 | Python 类方法 | `@agno.tools.tool` 装饰器 |
| 报告生成 | ReportEngine（1700 行，IR Schema + Chart.js） | 5 阶段 ReportAgent + 6 章节并发 |
| 可视化 | IR JSON → Chart.js | 自定义 HTML 标签（`<kpi-grid>`, `<chart-card>` 等）→ Chart.js |

---

## ✅ 保留的核心特性

- **段落级 Forum 反馈循环**：每个 agent 产出段落总结后写入 `ForumState`，达到阈值（默认 5 条）自动触发 `ForumHost` 主持人发言，**反向影响下一段写作方向**。这是 BettaFish 最核心的特性。
- **ForumHost 的 4 段式发言结构**：事件梳理 / 观点整合 / 趋势预测 / 问题引导，与原项目 prompt 完全一致。
- **三 Agent 并发执行**：`asyncio.gather` 实现，与原项目的 Streamlit 子进程并发等价。
- **原项目所有 prompt**：`SYSTEM_PROMPT_REPORT_STRUCTURE` / `FIRST_SEARCH` / `FIRST_SUMMARY` / `REFLECTION` / `REFLECTION_SUMMARY` / `REPORT_FORMATTING` 完整保留，包含 JSON Schema。

---

## ✨ 新增能力

### 1. 海外数据源扩展（4 个新平台）

InsightAgent 在原有 6 个中文社交媒体工具基础上，新增：

| 平台 | 工具数 | 认证 |
|---|---|---|
| Hacker News | 3 | 无需 |
| GitHub | 3 | 可选 PAT |
| YouTube | 3 | Data API Key |
| Reddit | 3 | OAuth |

**动态裁剪**：未配置 key 的平台自动从 prompt 和 tool list 中移除，不会被 LLM 调用。

### 2. 专业可视化组件（6 种）

ReportAgent 生成的 HTML 报告支持：

- `<kpi-grid>` — 数据卡片网格（带 tone 和 delta）
- `<chart-card>` — Chart.js 图表（bar/line/pie/doughnut/radar）
- `<callout>` — 语义化提示框（info/insight/warning/danger/success）
- `<info-matrix>` — 信息源覆盖矩阵（★星级可视化）
- `<timeline>` — 事件时间线（含 crisis/release/update 分类）
- `<quote-card>` — 用户原声卡片

一份典型报告会包含 30+ 个可视化组件。

### 3. ReportAgent 多阶段流程

- **Stage 1**: 大纲规划（综合三 agent 报告 + Host 发言，LLM 生成 5-7 章结构）
- **Stage 2**: 6 章节**并发**写作（`asyncio.gather`）
- **Stage 3**: 跨源对比验证（三方共识 / 分歧 / 可信度评级）
- **Stage 4**: 执行摘要（一句话结论 + 关键发现 + 风险预警）
- **Stage 5**: HTML 渲染（含 Chart.js CDN + 响应式 CSS）

---

## 📦 当前状态

| 模块 | 状态 |
|---|---|
| InsightAgent / MediaAgent / QueryAgent | ✅ 完整迁移 |
| ForumHost + ForumState 段落级反馈 | ✅ 完整保留 |
| ReportAgent 5 阶段综合报告 | ✅ 实现 |
| Chart.js + 6 种可视化组件 | ✅ 实现 |
| 海外数据源（HN/GitHub/YouTube/Reddit）| ✅ 实现 |
| MindSpider 爬虫集成 | ❌ 用 SQLite mock 数据库（`scripts/init_mock_db.py`）|
| Web UI（Flask + Streamlit）| ❌ 仅命令行 |
| PDF 导出 | ❌ 仅 HTML |

---

## 🚀 快速验证

```bash
cd experimental/agno_version

# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（参考 README 的 .env 示例）
cp .env.example .env
vim .env  # 填入各 Agent 的 API key

# 3. 初始化 mock 数据库
python scripts/init_mock_db.py

# 4. 运行完整流程
python run_full_pipeline.py "Claude Code 在中文程序员社区的舆情分析"
```

输出见 `reports/full_pipeline/{主题}_{时间戳}/final_report.html`。

完整文档见本目录的 `README.md`。

---

## 💡 设计取舍说明

### 为什么用 asyncio 而不是 agno Team？

agno 的 `Team` 是 **回合制**（agent 轮流说话）或 **路由式**（协调者选一个 agent），**不支持「三 agent 真并发 + 共享公告板 + 外部观察者反馈」**这种模式。

BettaFish 原版用 Streamlit 子进程+文件监控实现了这个模式。agno 版用 `asyncio.gather + ForumState + ForumHost 回调` 实现了等价功能。

### 为什么工具调用没用 agno 自主 dispatch？

agno 原生支持 `agent.run()` 自主选择并调用工具，但这样会**失去段落级反馈循环的插入点**：我们需要在「工具调用」和「段落总结」之间插入 HOST 引导读取。

所以保留了手写的 6 步流程（搜索决策 → 工具调用 → 读 HOST → 总结 → 反思 → 深化），但每一步的 LLM 调用都走 agno Agent。

---

## 🤝 期望

希望这个实验版本能给原项目作者提供一个新的架构参考：

1. 如果觉得 agno 版本有合并价值，可以讨论后续合作方向
2. 如果想从这里摘取某些部分（比如可视化组件或海外数据源工具），欢迎
3. 即便只是作为实验保留给社区参考也很好

---

## 🔗 源仓库

本目录代码的完整 git 历史见：https://github.com/NextE-Moffatt/agno-mirofish

（由于是大规模重构，本 PR 采用 rsync 复制的方式合并，没有保留 commit 历史。完整历史请查看源仓库。）
