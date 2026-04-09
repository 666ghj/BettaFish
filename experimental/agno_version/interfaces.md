# 接口契约文档

> **重要**：此文档由总负责人维护，接口签名一旦确认不得单方面修改。
> 如需变更，需三组对齐后更新此文档。

---

## A → B 接口（tool 函数签名）

A 组必须严格按照此签名实现，B 组按此签名调用。

```python
# 数据库查询
search_weibo(keyword: str, limit: int = 20) -> List[Dict[str, Any]]
# 返回字段：content, author, publish_time, likes

search_forum(keyword: str, platform: str = "all", limit: int = 20) -> List[Dict[str, Any]]
# 返回字段：content, author, publish_time, replies

search_news(keyword: str, limit: int = 20) -> List[Dict[str, Any]]
# 返回字段：title, content, source, publish_time

# 情感分析
analyze_sentiment(texts: List[str]) -> List[Dict[str, Any]]
# 返回字段：sentiment("positive"|"negative"|"neutral"), confidence(float), language(str)

# 关键词优化
optimize_keywords(query: str, num_keywords: int = 5) -> List[str]

# 爬虫
start_crawler(keyword: str, platforms: List[str], max_count: int = 100) -> Dict[str, Any]
# 返回字段：task_id(str), status("started"), estimated_seconds(int)

get_crawler_status(task_id: str) -> Dict[str, Any]
# 返回字段：task_id, status("running"|"done"|"failed"), progress(0~100), collected(int)
```

---

## B → C 接口（agent 运行函数签名）

B 组必须严格按照此签名实现，C 组按此签名调用。

```python
# 工厂函数
create_insight_agent(config: Settings = None) -> Agent
create_media_agent(config: Settings = None) -> Agent
create_query_agent(config: Settings = None) -> Agent

# 运行函数
run_insight_analysis(query: str, config: Settings = None) -> str  # 返回 Markdown 报告
run_media_analysis(query: str, config: Settings = None) -> str    # 返回 Markdown 报告
run_query(query: str, config: Settings = None) -> str             # 返回 Markdown 结果
```

---

## C 对外接口（Team 运行函数）

```python
create_opinion_team(config: Settings = None) -> Team
run_opinion_analysis(topic: str, config: Settings = None) -> str  # 返回报告路径或内容
run_report_generation(insight_report: str, media_report: str, query_report: str, config: Settings = None) -> str
```

---

## SocketIO 事件（前端不变）

| 方向 | 事件名 | 数据格式 |
|---|---|---|
| 前端→后端 | `start_analysis` | `{"topic": str}` |
| 后端→前端 | `analysis_started` | `{"topic": str}` |
| 后端→前端 | `analysis_progress` | `{"agent": str, "content": str}` |
| 后端→前端 | `forum_message` | `{"speaker": "host", "content": str}` |
| 后端→前端 | `analysis_complete` | `{"message": str}` |
| 后端→前端 | `error` | `{"message": str}` |

---

## 变更记录

| 日期 | 变更内容 | 影响方 |
|---|---|---|
| 2026-04-02 | 初始版本 | 全体 |
