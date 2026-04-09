# 任务书 A：数据层与工具层迁移

**项目**：BettaFish (微舆) → agno 框架重构
**负责人**：A
**依赖关系**：本任务是 B、C 两组的前置依赖，工具接口定义需优先完成

---

## 背景与目标

BettaFish 是一个多 Agent 舆情分析系统，原项目完全自研，不依赖任何 Agent 框架。本次重构目标是将其迁移至 [agno](https://github.com/agno-agi/agno) 框架。

你负责**数据层和工具层**：将所有数据采集、数据库查询、情感分析能力，统一封装为 agno 标准的 `@tool` 函数，供 B 组的 Agent 直接调用。

---

## 需要阅读的原始代码

在开始前，请先通读以下文件：

| 文件路径 | 说明 |
|---|---|
| `InsightEngine/tools/search.py` | 数据库查询工具（MediaCrawlerDB，5种查询方法）|
| `InsightEngine/tools/keyword_optimizer.py` | 关键词优化工具 |
| `InsightEngine/tools/sentiment_analyzer.py` | 情感分析工具（支持22种语言）|
| `MediaEngine/tools/search.py` | 媒体数据查询工具 |
| `QueryEngine/tools/search.py` | 通用查询工具 |
| `MindSpider/main.py` | 爬虫主入口（MindSpider类）|
| `MindSpider/config.py` | 爬虫配置 |
| `SentimentAnalysisModel/` | 情感分析模型（transformers）|
| `InsightEngine/utils/` | 文本处理工具函数 |
| `MediaEngine/utils/` | 媒体引擎工具函数 |
| `config.py` | 全局配置（数据库连接、API Key 等）|

---

## 交付物结构

在项目根目录新建 `agno_tools/` 目录，按以下结构交付：

```
agno_tools/
├── __init__.py              # 统一导出所有 tool
├── db_query_tools.py        # 数据库查询工具（来自各 Engine/tools/search.py）
├── crawler_tools.py         # 爬虫工具（来自 MindSpider）
├── sentiment_tools.py       # 情感分析工具（来自 SentimentAnalysisModel + InsightEngine/tools/sentiment_analyzer.py）
├── keyword_tools.py         # 关键词工具（来自 InsightEngine/tools/keyword_optimizer.py）
└── shared_utils.py          # 公共工具函数（来自各 Engine/utils/）
```

---

## 详细工作说明

### 1. 数据库查询工具（`db_query_tools.py`）

原始代码中，`InsightEngine/tools/search.py` 里有一个 `MediaCrawlerDB` 类，包含 5 种查询方法（微博、论坛、新闻等）。

**迁移方式**：将每个查询方法独立为一个 agno `@tool` 函数。

```python
# agno_tools/db_query_tools.py
from agno.tools import tool
from typing import List, Dict, Any

@tool(description="查询微博数据库，按关键词搜索微博内容")
def search_weibo(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Args:
        keyword: 搜索关键词
        limit: 返回结果数量上限
    Returns:
        微博数据列表，每条包含 content, author, publish_time, likes 等字段
    """
    # 保留原 MediaCrawlerDB 的数据库连接和查询逻辑
    ...

@tool(description="查询论坛数据库，按关键词搜索帖子")
def search_forum(keyword: str, platform: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
    ...

# 按照原 MediaCrawlerDB 中有多少查询方法，就拆出多少个 @tool 函数
```

**注意**：
- 数据库连接配置从 `config.py` 的 `Settings` 对象读取，不要硬编码
- 原代码使用 SQLAlchemy + asyncpg，迁移时可保持同步版本（agno tool 不强制异步）

---

### 2. 爬虫工具（`crawler_tools.py`）

原始代码 `MindSpider/main.py` 中的 `MindSpider` 类负责触发爬虫任务（调用 playwright 爬取各平台数据）。

**迁移方式**：将 MindSpider 的启动和状态查询封装为 tool。

```python
# agno_tools/crawler_tools.py
from agno.tools import tool

@tool(description="启动MindSpider爬虫，采集指定平台的舆情数据")
def start_crawler(
    keyword: str,
    platforms: List[str],   # 如 ["weibo", "forum", "news"]
    max_count: int = 100
) -> Dict[str, Any]:
    """触发爬取任务，返回任务ID和预估完成时间"""
    ...

@tool(description="查询爬虫任务状态")
def get_crawler_status(task_id: str) -> Dict[str, Any]:
    """返回任务进度、已采集数量、是否完成"""
    ...
```

---

### 3. 情感分析工具（`sentiment_tools.py`）

原始代码 `InsightEngine/tools/sentiment_analyzer.py` 中有 `multilingual_sentiment_analyzer`，基于 transformers 模型，支持 22 种语言。

**迁移方式**：直接封装为 tool，模型懒加载（首次调用时初始化）。

```python
# agno_tools/sentiment_tools.py
from agno.tools import tool

# 模块级懒加载，避免 import 时就加载大模型
_analyzer = None

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        # 保留原始 SentimentAnalysisModel 的加载逻辑
        from SentimentAnalysisModel import load_model
        _analyzer = load_model()
    return _analyzer

@tool(description="对文本列表进行多语言情感分析，返回正/负/中性及置信度")
def analyze_sentiment(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Args:
        texts: 待分析文本列表
    Returns:
        每条文本的分析结果，含 sentiment (positive/negative/neutral), confidence, language
    """
    analyzer = _get_analyzer()
    return analyzer.batch_analyze(texts)
```

---

### 4. 关键词工具（`keyword_tools.py`）

原始代码 `InsightEngine/tools/keyword_optimizer.py` 中的 `keyword_optimizer`，用 LLM 将用户查询扩展为多个搜索关键词。

**注意**：这个工具本身调用 LLM，迁移时需要从 `config.py` 读取 LLM 配置，使用 openai 兼容接口即可，**不要引入 agno 的 Agent**，保持它只是一个普通的工具函数。

```python
@tool(description="将用户查询优化为多个数据库搜索关键词组合")
def optimize_keywords(query: str, num_keywords: int = 5) -> List[str]:
    """返回针对该查询优化后的关键词列表"""
    ...
```

---

### 5. `__init__.py` 统一导出

```python
# agno_tools/__init__.py
from .db_query_tools import search_weibo, search_forum, search_news  # 按实际方法名导出
from .crawler_tools import start_crawler, get_crawler_status
from .sentiment_tools import analyze_sentiment
from .keyword_tools import optimize_keywords
from .shared_utils import format_search_results  # 来自原 InsightEngine/utils/

__all__ = [
    "search_weibo", "search_forum", "search_news",
    "start_crawler", "get_crawler_status",
    "analyze_sentiment",
    "optimize_keywords",
    "format_search_results",
]
```

---

## 接口约定（必须遵守，B 组依赖此）

1. **所有 `@tool` 函数必须有完整的 docstring**，说明参数和返回值格式
2. **返回值统一为 `List[Dict]` 或 `Dict`**，不要返回自定义类对象
3. **不要在 tool 函数中 `print`**，统一用 `loguru.logger`
4. **tool 函数签名中不要有默认为 `None` 的必填参数**，agno 会将 tool 签名暴露给 LLM
5. 完成接口定义（可以是空实现）后，**尽快通知 B 组**，让他们可以开始开发

---

## 环境准备

```bash
pip install agno
# agno 安装文档：https://docs.agno.com/introduction
```

agno tool 的写法参考：
```python
from agno.tools import tool

@tool
def my_tool(param: str) -> str:
    """工具描述，LLM 会读取这段文字来决定何时调用此工具"""
    return f"result: {param}"
```

---

## 验收标准

- [ ] 所有 tool 函数可以被独立 `import` 并调用（不依赖 agno Agent 运行时）
- [ ] `agno_tools/__init__.py` 可以无报错 `from agno_tools import *`
- [ ] 情感分析 tool 通过单元测试：输入 ["今天天气真好", "这件事太糟糕了"]，返回正确的 positive/negative 结果
- [ ] 数据库查询 tool 通过集成测试：能查询到真实数据（需要配置 `.env`）
- [ ] 不破坏原有 `InsightEngine`、`MediaEngine`、`QueryEngine` 的正常运行（可以两套代码并存）
