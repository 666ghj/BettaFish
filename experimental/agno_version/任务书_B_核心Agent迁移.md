# 任务书 B：核心 Agent 迁移（InsightEngine / MediaEngine / QueryEngine）

**项目**：BettaFish (微舆) → agno 框架重构
**负责人**：B
**前置依赖**：需等 A 组完成 `agno_tools/__init__.py` 的接口定义（空实现即可）后开始

---

## 背景与目标

BettaFish 有三个核心分析引擎，每个引擎手写了一套 `nodes/` + `state/` + `llms/` 的 Agent 框架。

你的目标是用 **agno `Agent`** 重写这三个引擎：

| 原引擎 | 功能 | 对应 LLM |
|---|---|---|
| `InsightEngine` | 社交媒体舆情分析（本地数据库，含反思循环）| kimi-k2 |
| `MediaEngine` | 多模态网页内容分析（综合搜索/图片/结构化数据）| gemini-2.5-pro |
| `QueryEngine` | 新闻深度分析（多源核实/事实核查）| deepseek-chat |

---

## 需要阅读的原始代码

**先通读以下文件，理解每个引擎的工作流程，再开始写代码：**

| 文件路径 | 说明 |
|---|---|
| `InsightEngine/agent.py` | DeepSearchAgent 主类，含聚类采样和反思循环逻辑 |
| `InsightEngine/nodes/search_node.py` | 生成搜索查询（FirstSearchNode + ReflectionNode）|
| `InsightEngine/nodes/summary_node.py` | 总结搜索结果（FirstSummaryNode + ReflectionSummaryNode）|
| `InsightEngine/nodes/report_structure_node.py` | 规划报告结构 |
| `InsightEngine/nodes/formatting_node.py` | 最终报告格式化 |
| `InsightEngine/state/state.py` | State / Paragraph / Research 数据结构 |
| `InsightEngine/prompts/` | 所有 system prompt |
| `MediaEngine/agent.py` | 媒体分析 Agent（结构类似 InsightEngine）|
| `QueryEngine/agent.py` | 查询 Agent |
| `config.py` | 各 Engine 的 API Key / Base URL / Model Name 配置 |

**重点理解 InsightEngine 的反思循环**（最复杂的部分）：
1. `ReportStructureNode`：根据用户查询，规划报告的段落标题和大纲
2. `FirstSearchNode`：为每个段落生成搜索关键词
3. 调用工具查询数据库，得到原始数据
4. `FirstSummaryNode`：对搜索结果做初步总结
5. `ReflectionNode`：判断总结是否充分，若不足则生成追加查询
6. 重复步骤 3-5，直到满足条件或达到最大迭代次数
7. `ReportFormattingNode`：将所有段落汇总为完整报告

---

## 交付物结构

在项目根目录新建 `agno_agents/` 目录，按以下结构交付：

```
agno_agents/
├── __init__.py
├── insight_agent.py      # InsightEngine → agno Agent
├── media_agent.py        # MediaEngine → agno Agent
└── query_agent.py        # QueryEngine → agno Agent
```

---

## 详细工作说明

### 1. agno Agent 的核心写法

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat  # openai 兼容接口
from agno_tools import search_weibo, search_forum, analyze_sentiment

agent = Agent(
    name="InsightAgent",
    model=OpenAIChat(
        id="kimi-k2-0711-preview",
        api_key=settings.INSIGHT_ENGINE_API_KEY,
        base_url=settings.INSIGHT_ENGINE_BASE_URL,
    ),
    tools=[search_weibo, search_forum, analyze_sentiment, optimize_keywords],
    instructions="""你是一个舆情深度分析专家...（从 InsightEngine/prompts/ 迁移）""",
    markdown=True,
)
```

---

### 2. InsightEngine → `insight_agent.py`（重点任务）

InsightEngine 的核心是**反思循环**，迁移思路如下：

**方案A（推荐）：用 agno 的多轮 `run()` 模拟反思循环**

agno Agent 天然支持多轮对话，可以利用这一点实现反思：

```python
# agno_agents/insight_agent.py
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.run.response import RunResponse
from config import Settings, settings
from agno_tools import (
    search_weibo, search_forum, search_news,
    analyze_sentiment, optimize_keywords, format_search_results
)

INSIGHT_SYSTEM_PROMPT = """
你是一个专业的舆情深度分析专家。你的工作流程：
1. 收到分析主题后，先规划报告结构（3-5个段落，每个段落有明确主题）
2. 针对每个段落，调用搜索工具获取相关数据
3. 分析数据充分性：如果数据不足，换用不同关键词再次搜索
4. 对每个段落的数据进行情感分析和观点总结
5. 将所有段落汇总，输出完整的结构化分析报告

注意：
- 每个段落至少搜索2次，确保数据充分
- 情感分析必须覆盖所有关键数据
- 报告需包含：事件概述、舆论倾向、关键观点、预测走向
"""
# （继续从 InsightEngine/prompts/ 中迁移完整 prompt）

def create_insight_agent(config: Settings = settings) -> Agent:
    return Agent(
        name="InsightAgent",
        model=OpenAIChat(
            id=config.INSIGHT_ENGINE_MODEL_NAME,
            api_key=config.INSIGHT_ENGINE_API_KEY,
            base_url=config.INSIGHT_ENGINE_BASE_URL,
        ),
        tools=[search_weibo, search_forum, search_news, analyze_sentiment, optimize_keywords],
        instructions=INSIGHT_SYSTEM_PROMPT,
        markdown=True,
        show_tool_calls=True,
        # agno 支持流式输出
        stream=True,
    )

def run_insight_analysis(query: str, config: Settings = settings) -> str:
    """
    对外接口：接收用户查询，返回完整分析报告。
    替代原 DeepSearchAgent.run(query) 方法。
    """
    agent = create_insight_agent(config)
    response: RunResponse = agent.run(query)
    return response.content
```

**关于聚类采样逻辑**（`InsightEngine/agent.py` 中的 `ENABLE_CLUSTERING`）：

原代码用 `sentence-transformers` + KMeans 对大量搜索结果做聚类，只取代表性样本。
迁移时有两个选择：
- **选择1（简单）**：在 tool 函数层面（A 组负责）处理聚类，tool 返回时就已经是精简后的结果。和 A 组对齐这个接口。
- **选择2（保留）**：在 `run_insight_analysis` 中，先调用 tool 获取原始数据，做聚类后再喂给 agent。

建议选择1，更符合 agno 的设计理念。

---

### 3. MediaEngine → `media_agent.py`

MediaEngine 结构与 InsightEngine 相似，但 prompt 和工具不同，分析对象侧重媒体报道（非社交媒体）。

```python
# agno_agents/media_agent.py
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config import settings
from agno_tools import search_news  # 媒体引擎主要使用新闻查询工具

MEDIA_SYSTEM_PROMPT = """..."""  # 从 MediaEngine/prompts/ 迁移

def create_media_agent(config=settings) -> Agent:
    return Agent(
        name="MediaAgent",
        model=OpenAIChat(
            id=config.MEDIA_ENGINE_MODEL_NAME,
            api_key=config.MEDIA_ENGINE_API_KEY,
            base_url=config.MEDIA_ENGINE_BASE_URL,
        ),
        tools=[search_news, analyze_sentiment],
        instructions=MEDIA_SYSTEM_PROMPT,
        markdown=True,
        stream=True,
    )

def run_media_analysis(query: str, config=settings) -> str:
    agent = create_media_agent(config)
    return agent.run(query).content
```

---

### 4. QueryEngine → `query_agent.py`

QueryEngine 是相对简单的查询 Agent，负责根据用户问题从数据库中检索数据并给出简洁答复。

```python
# agno_agents/query_agent.py
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config import settings
from agno_tools import search_weibo, search_forum, search_news

QUERY_SYSTEM_PROMPT = """..."""  # 从 QueryEngine/prompts/ 迁移

def create_query_agent(config=settings) -> Agent:
    return Agent(
        name="QueryAgent",
        model=OpenAIChat(
            id=config.QUERY_ENGINE_MODEL_NAME,
            api_key=config.QUERY_ENGINE_API_KEY,
            base_url=config.QUERY_ENGINE_BASE_URL,
        ),
        tools=[search_weibo, search_forum, search_news],
        instructions=QUERY_SYSTEM_PROMPT,
        markdown=True,
        stream=True,
    )

def run_query(query: str, config=settings) -> str:
    agent = create_query_agent(config)
    return agent.run(query).content
```

---

### 5. `agno_agents/__init__.py`

```python
from .insight_agent import create_insight_agent, run_insight_analysis
from .media_agent import create_media_agent, run_media_analysis
from .query_agent import create_query_agent, run_query

__all__ = [
    "create_insight_agent", "run_insight_analysis",
    "create_media_agent", "run_media_analysis",
    "create_query_agent", "run_query",
]
```

---

## Prompt 迁移说明

原项目的 prompt 分散在各 Engine 的 `prompts/` 目录下（`SYSTEM_PROMPT_FIRST_SEARCH`、`SYSTEM_PROMPT_REFLECTION` 等）。

迁移时，将这些 prompt **合并为一个 `instructions` 字符串**传给 agno Agent。合并策略：
- 将"首次搜索"和"反思"两个 system prompt 整合为一段完整指令
- 指令中说明工作流程（先搜索，评估充分性，不足则继续搜索）
- 删除原 prompt 中关于"JSON 格式输出"的硬性要求（agno 有自己的结构化输出机制）

---

## 与 State 对象的对应关系

原 `InsightEngine/state/state.py` 中的 `State` 对象（含 `Paragraph`、`Research`、`Search`）用于在节点间传递数据。

迁移到 agno 后，**这些状态由 agno Agent 的对话历史自动维护**，不需要手动管理 State 对象。

如果 C 组的编排层需要查询分析进度，通过 agno 的 `AgentSession` 接口获取即可。

---

## 验收标准

- [ ] 三个 `create_*_agent()` 函数可以无报错实例化（即使没有真实 API Key，也应能创建对象）
- [ ] `run_insight_analysis("2024年某热点事件舆情分析")` 能完整运行并返回报告字符串
- [ ] `run_media_analysis()` 和 `run_query()` 同上
- [ ] 支持流式输出（`stream=True`），C 组编排层可以实时获取 token
- [ ] 对外接口签名（`run_*` 函数）与原引擎的 `agent.run(query)` 保持兼容
- [ ] 三个 agent 的 prompt 内容与原 `prompts/` 目录保持一致，不遗漏关键指令
