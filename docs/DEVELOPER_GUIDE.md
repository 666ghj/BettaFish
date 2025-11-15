# BettaFish 开发者指南

**文档版本**: 1.0.0
**最后更新**: 2025-11-15
**适用人群**: Python开发者、系统架构师、贡献者

---

## 快速开始

### 环境搭建 (5分钟)

```bash
# 1. 克隆仓库
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish

# 2. 创建虚拟环境
conda create -n bettafish python=3.11
conda activate bettafish

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 配置环境变量
cp .env.example .env
nano .env  # 填写必要的API密钥

# 5. 启动开发服务器
python app.py
```

访问 http://localhost:5000

---

## 项目结构详解

```
BettaFish/
├── app.py                    # Flask主应用 (1060行)
│   ├── 进程管理
│   ├── WebSocket通信
│   ├── 配置API
│   └── 系统启动协调
│
├── config.py                 # 全局配置 (Pydantic Settings)
│
├── QueryEngine/              # 搜索引擎Agent
│   ├── agent.py              # Agent主类
│   ├── llms/base.py          # LLM客户端
│   ├── nodes/                # 处理节点
│   ├── tools/                # 搜索工具
│   └── utils/config.py       # Agent配置
│
├── MediaEngine/              # 多模态分析Agent
│   └── (结构同QueryEngine)
│
├── InsightEngine/            # 数据挖掘Agent
│   ├── agent.py              # Agent主类 (关键!)
│   ├── tools/
│   │   ├── search.py         # 数据库查询工具
│   │   ├── sentiment_analyzer.py  # 情感分析
│   │   └── keyword_optimizer.py   # 关键词优化
│   └── ...
│
├── ReportEngine/             # 报告生成Agent
│   ├── agent.py
│   ├── report_template/      # 报告模板库
│   └── flask_interface.py    # API接口
│
├── ForumEngine/              # Agent协作引擎
│   ├── monitor.py            # 日志监控
│   └── llm_host.py           # LLM主持人
│
├── MindSpider/               # 爬虫系统
│   ├── main.py               # 爬虫主程序
│   ├── BroadTopicExtraction/ # 话题提取
│   ├── DeepSentimentCrawling/  # 深度爬取
│   └── schema/               # 数据库schema
│
├── SentimentAnalysisModel/   # 情感分析模型
│   ├── WeiboMultilingualSentiment/  # 多语言 (推荐)
│   ├── WeiboSentiment_SmallQwen/    # Qwen3微调
│   └── ... (其他模型)
│
└── docs/                     # 技术文档
    ├── README_COMPREHENSIVE.md  # 项目完整说明
    ├── ARCHITECTURE.md          # 架构设计
    ├── DEVELOPER_GUIDE.md       # 开发者指南
    └── DEPLOYMENT_GUIDE.md      # 部署手册
```

---

## 核心概念

### 1. Agent架构

每个Agent是独立的Python进程,通过以下组件协作:

- **LLM Client**: 与大语言模型通信
- **Tools**: 专业工具集 (搜索、数据库、分析等)
- **Nodes**: 处理节点 (责任链模式)
- **State**: 状态管理对象

**示例: InsightEngine Agent**:

```python
# InsightEngine/agent.py
class DeepSearchAgent:
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.llm_client = self._initialize_llm()
        self.search_agency = MediaCrawlerDB()  # 数据库工具
        self.sentiment_analyzer = multilingual_sentiment_analyzer
        self._initialize_nodes()

    def run(self, query: str) -> str:
        """执行完整分析流程"""
        state = State(query=query)

        # 节点处理链
        state = self.first_search_node.process(state)
        state = self.reflection_node.process(state)
        state = self.first_summary_node.process(state)
        state = self.reflection_summary_node.process(state)
        state = self.report_formatting_node.process(state)

        return state.final_report
```

### 2. ForumEngine协作机制

**工作原理**:

1. Agent写日志到 `logs/forum.log`
2. ForumEngine监控文件变化
3. 解析Agent发言
4. LLM主持人生成总结
5. 总结写回日志
6. Agent读取总结并调整策略

**日志格式**:

```
[14:30:25] [QUERY] 开始搜索"华为手机"相关新闻...
[14:30:26] [INSIGHT] 发现数据库中有1250条相关评论
[14:30:30] [HOST] 【主持人总结】当前进展良好...
```

### 3. 配置管理 (Pydantic Settings)

**设计优势**:
- 类型安全
- 自动验证
- 环境变量支持
- 配置热重载

**示例**:

```python
# config.py
class Settings(BaseSettings):
    DB_HOST: str = Field("localhost", description="数据库主机")
    DB_PORT: int = Field(3306, description="数据库端口")

    INSIGHT_ENGINE_API_KEY: Optional[str] = Field(None, description="...")

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False
    )

# 使用
from config import settings

db_url = f"postgresql://{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
```

---

## 开发工作流

### 添加新功能

**示例: 为InsightEngine添加新的数据库查询工具**

1. **在tools/search.py添加方法**:

```python
# InsightEngine/tools/search.py
class MediaCrawlerDB:
    def search_by_author(self, author_name: str, limit: int = 100) -> DBResponse:
        """按作者搜索"""
        query = """
        SELECT * FROM weibo_posts
        WHERE author = %s
        ORDER BY post_time DESC
        LIMIT %s
        """

        results = self.db.execute(query, (author_name, limit))

        return DBResponse(
            tool_name="search_by_author",
            parameters={"author_name": author_name, "limit": limit},
            results=[dict(row) for row in results],
            results_count=len(results)
        )
```

2. **注册到Agent**:

```python
# InsightEngine/agent.py
def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> DBResponse:
    if tool_name == "search_by_author":
        author_name = kwargs.get("author_name", query)
        limit = kwargs.get("limit", 100)
        return self.search_agency.search_by_author(author_name, limit)
    # ... 其他工具
```

3. **更新提示词** (让LLM知道新工具):

```python
# InsightEngine/prompts/prompts.py
TOOL_DESCRIPTIONS = """
可用工具:
1. search_by_author - 按作者搜索内容
   参数: author_name (作者名), limit (最大结果数)
   示例: search_by_author(author_name="张三", limit=50)

2. ... (其他工具)
"""
```

4. **编写测试**:

```python
# tests/test_insight_engine.py
def test_search_by_author():
    agent = DeepSearchAgent()
    result = agent.execute_search_tool(
        tool_name="search_by_author",
        query="测试作者",
        limit=10
    )

    assert result.tool_name == "search_by_author"
    assert len(result.results) <= 10
```

### 调试技巧

**1. 启用详细日志**:

```python
# 在Agent初始化时
import logging
logging.basicConfig(level=logging.DEBUG)

from loguru import logger
logger.add("debug.log", level="DEBUG")
```

**2. 单独测试Agent**:

```bash
# 启动单个Agent的Streamlit界面
streamlit run SingleEngineApp/insight_engine_streamlit_app.py --server.port 8501
```

**3. 查看Forum日志**:

```bash
tail -f logs/forum.log
```

**4. 检查数据库**:

```bash
# PostgreSQL
psql -U bettafish -d bettafish

# 查看表
\dt

# 查询示例
SELECT * FROM topics LIMIT 10;
```

---

## 代码规范

### Python代码风格

**使用Black格式化**:

```bash
pip install black
black . --line-length 100
```

**类型提示**:

```python
from typing import List, Dict, Optional, Union

def search_topics(
    keywords: List[str],
    limit: int = 100
) -> Dict[str, Any]:
    """
    搜索话题

    Args:
        keywords: 关键词列表
        limit: 最大结果数

    Returns:
        搜索结果字典
    """
    pass
```

### 命名规范

- **类名**: PascalCase (e.g. `DeepSearchAgent`)
- **函数名**: snake_case (e.g. `execute_search_tool`)
- **常量**: UPPER_SNAKE_CASE (e.g. `MAX_RETRIES`)
- **私有方法**: 前缀`_` (e.g. `_validate_input`)

### 文档字符串

```python
def complex_function(param1: str, param2: int) -> Dict:
    """
    函数简要说明 (一句话)

    更详细的功能描述,可以多行...

    Args:
        param1: 参数1说明
        param2: 参数2说明

    Returns:
        返回值说明

    Raises:
        ValueError: 什么情况下抛出
        TypeError: 什么情况下抛出

    Examples:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'key': 'value'}
    """
    pass
```

---

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_insight_engine.py

# 显示详细输出
pytest -v

# 覆盖率报告
pytest --cov=InsightEngine --cov-report=html
```

### 编写测试

```python
# tests/test_insight_engine.py
import pytest
from InsightEngine.agent import DeepSearchAgent

class TestDeepSearchAgent:
    @pytest.fixture
    def agent(self):
        """创建测试Agent实例"""
        return DeepSearchAgent()

    def test_execute_search_tool(self, agent):
        """测试搜索工具执行"""
        result = agent.execute_search_tool(
            tool_name="search_hot_content",
            query="",
            time_period="week"
        )

        assert result.tool_name == "search_hot_content"
        assert isinstance(result.results, list)
        assert result.results_count >= 0

    def test_sentiment_analysis(self, agent):
        """测试情感分析"""
        texts = ["这个产品很好", "服务太差了"]
        result = agent.analyze_sentiment_only(texts)

        assert "positive_count" in result
        assert "negative_count" in result
```

---

## 性能优化建议

### 1. 数据库查询优化

```python
# ❌ 错误: N+1查询
for topic_id in topic_ids:
    comments = db.query(f"SELECT * FROM comments WHERE topic_id={topic_id}")

# ✅ 正确: 批量查询
topic_ids_str = ','.join([str(id) for id in topic_ids])
comments = db.query(f"SELECT * FROM comments WHERE topic_id IN ({topic_ids_str})")
```

### 2. LLM调用优化

```python
# 使用缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_llm_response(prompt: str) -> str:
    return llm.generate(prompt)
```

### 3. 异步处理

```python
import asyncio

async def parallel_tasks():
    results = await asyncio.gather(
        task1(),
        task2(),
        task3()
    )
    return results
```

---

## 故障排查

### 常见问题

**1. Streamlit应用启动失败**

```bash
# 检查端口占用
lsof -i :8501  # Linux/Mac
netstat -ano | findstr :8501  # Windows

# 杀掉占用进程
kill -9 <PID>
```

**2. 数据库连接错误**

```python
# 检查配置
from config import settings
print(f"DB: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

# 测试连接
import psycopg2
conn = psycopg2.connect(
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
    database=settings.DB_NAME
)
```

**3. LLM API调用失败**

```python
# 检查API密钥
print(f"API Key: {settings.INSIGHT_ENGINE_API_KEY[:10]}...")

# 测试连接
from openai import OpenAI
client = OpenAI(
    api_key=settings.INSIGHT_ENGINE_API_KEY,
    base_url=settings.INSIGHT_ENGINE_BASE_URL
)
response = client.chat.completions.create(
    model=settings.INSIGHT_ENGINE_MODEL_NAME,
    messages=[{"role": "user", "content": "test"}]
)
print(response.choices[0].message.content)
```

---

## 贡献指南

### 提交代码流程

```bash
# 1. Fork仓库并克隆
git clone https://github.com/YOUR_USERNAME/BettaFish.git
cd BettaFish

# 2. 创建功能分支
git checkout -b feature/your-feature-name

# 3. 开发并测试
# ... 编写代码 ...
pytest

# 4. 提交代码
git add .
git commit -m "feat: add new feature description"

# 5. 推送到Fork仓库
git push origin feature/your-feature-name

# 6. 创建Pull Request
# 在GitHub上创建PR
```

### Commit消息规范

```
<type>(<scope>): <subject>

type:
- feat: 新功能
- fix: Bug修复
- docs: 文档更新
- style: 代码格式
- refactor: 重构
- test: 测试
- chore: 构建/工具

示例:
feat(InsightEngine): add search_by_author tool
fix(ForumEngine): resolve log parsing error
docs(README): update installation guide
```

---

## 更多资源

- **官方文档**: https://github.com/666ghj/BettaFish
- **问题反馈**: https://github.com/666ghj/BettaFish/issues
- **讨论区**: https://github.com/666ghj/BettaFish/discussions
- **技术架构**: docs/ARCHITECTURE.md
- **部署指南**: docs/DEPLOYMENT_GUIDE.md

---

**文档更新**: 2025-11-15
**维护者**: BettaFish开发团队
