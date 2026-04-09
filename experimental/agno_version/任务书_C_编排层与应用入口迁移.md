# 任务书 C：编排层、报告生成与应用入口迁移

**项目**：BettaFish (微舆) → agno 框架重构
**负责人**：C
**前置依赖**：
- A 组完成工具层接口定义后可开始 ReportAgent 开发
- B 组完成三个核心 Agent 后，开始 Team 编排

---

## 背景与目标

你负责整个系统的"顶层"部分：

1. **ReportEngine 迁移**：将报告生成引擎重写为 agno Agent
2. **ForumEngine 迁移**：将日志监控+主持人发言机制重写为 agno Agent
3. **编排层（最重要）**：用 agno `Team` 把 A/B 组的所有 Agent 组装成一个协作整体
4. **应用入口**：替换 `app.py`，保留 Flask + SocketIO 的实时流式接口

---

## 需要阅读的原始代码

**先通读以下文件：**

| 文件路径 | 说明 |
|---|---|
| `app.py` | Flask 主入口，含 SocketIO 实时推送、多引擎调度逻辑（重点）|
| `ReportEngine/agent.py` | ReportAgent 主类，串联模板选择→布局→章节生成→渲染 |
| `ReportEngine/nodes/template_selection_node.py` | 根据内容选择报告模板 |
| `ReportEngine/nodes/document_layout_node.py` | 生成报告布局/大纲 |
| `ReportEngine/nodes/chapter_generation_node.py` | 逐章生成报告内容 |
| `ReportEngine/nodes/word_budget_node.py` | 控制各章节字数预算 |
| `ReportEngine/renderers/` | HTML 渲染器 |
| `ReportEngine/report_template/` | 报告模板文件 |
| `ForumEngine/monitor.py` | 日志监控器（监控三个引擎的 log 输出）|
| `ForumEngine/llm_host.py` | 论坛主持人（LLM 生成串联发言）|

**重点理解 `app.py` 的调度逻辑**：
- 用户通过 Web 界面提交分析任务
- `app.py` 同时启动 InsightEngine、MediaEngine、QueryEngine
- ForumEngine 监控三个引擎的日志，生成主持人串联发言，推送到前端
- 三个引擎完成后，ReportEngine 读取它们的输出，生成综合报告
- 全程通过 SocketIO 向前端推送实时进度

---

## 交付物结构

```
agno_agents/
└── report_agent.py        # ReportEngine → agno Agent

agno_team/
├── __init__.py
├── forum_agent.py         # ForumEngine → agno Agent
└── opinion_team.py        # agno Team：编排所有 Agent

main.py                    # 新应用入口，替换 app.py（保留 Flask + SocketIO）
```

---

## 详细工作说明

### 1. ReportEngine → `agno_agents/report_agent.py`

ReportEngine 接收三个引擎的 Markdown 分析报告，生成一份完整的综合 HTML 报告。

原始流程：模板选择 → 布局规划 → 字数预算 → 逐章生成 → HTML 渲染

**迁移思路**：将这个流程用 agno Agent 的多步骤 `instructions` 驱动，HTML 渲染逻辑保留原代码。

```python
# agno_agents/report_agent.py
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from pathlib import Path
from config import settings

# 把 ReportEngine 的渲染能力封装为 tool
@tool(description="将报告 Markdown 内容渲染为 HTML 文件，返回文件路径")
def render_report_to_html(
    report_markdown: str,
    template_name: str,
    output_filename: str
) -> str:
    """
    保留原 ReportEngine/renderers/ 的 HTML 渲染逻辑
    返回生成的 HTML 文件路径
    """
    from ReportEngine.renderers import HTMLRenderer  # 直接复用原渲染器
    renderer = HTMLRenderer(template_name)
    output_path = renderer.render(report_markdown, output_filename)
    return str(output_path)

@tool(description="列出可用的报告模板")
def list_report_templates() -> list:
    """返回 ReportEngine/report_template/ 下的所有模板名称"""
    from ReportEngine.report_template import get_available_templates
    return get_available_templates()

REPORT_SYSTEM_PROMPT = """
你是一个专业的报告生成专家。你会收到来自三个分析引擎的原始分析内容：
- InsightEngine 的深度搜索报告
- MediaEngine 的媒体分析报告
- QueryEngine 的数据查询结果

你的任务：
1. 先调用 list_report_templates 了解可用模板
2. 根据内容特点选择最合适的模板
3. 规划报告结构（章节标题和字数分配）
4. 逐章撰写高质量报告内容
5. 调用 render_report_to_html 生成最终 HTML 报告
6. 返回 HTML 文件路径

报告要求：结构清晰、语言专业、数据支撑充分、有预测走向和决策建议。
"""
# 继续从 ReportEngine/nodes/ 的各 prompt 补充完整指令

def create_report_agent(config=settings) -> Agent:
    return Agent(
        name="ReportAgent",
        model=OpenAIChat(
            id=config.REPORT_ENGINE_MODEL_NAME,
            api_key=config.REPORT_ENGINE_API_KEY,
            base_url=config.REPORT_ENGINE_BASE_URL,
        ),
        tools=[render_report_to_html, list_report_templates],
        instructions=REPORT_SYSTEM_PROMPT,
        markdown=True,
        stream=True,
    )

def run_report_generation(
    insight_report: str,
    media_report: str,
    query_report: str,
    config=settings
) -> str:
    """
    对外接口：接收三个引擎的报告，生成综合 HTML 报告路径。
    """
    agent = create_report_agent(config)
    combined_input = f"""
## InsightEngine 分析报告
{insight_report}

## MediaEngine 媒体分析报告
{media_report}

## QueryEngine 查询结果
{query_report}
"""
    response = agent.run(combined_input)
    return response.content
```

---

### 2. ForumEngine → `agno_team/forum_agent.py`

原 ForumEngine 有两个功能：
- `LogMonitor`：监控三个引擎的日志文件，提取关键输出
- `LLMHost`：用 LLM 生成论坛主持人的串联发言，推送到前端

迁移思路：ForumEngine 本质是一个"旁观者"，不做核心分析，只负责汇总其他 Agent 的进度并生成活跃的"主持人"发言。

```python
# agno_team/forum_agent.py
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from config import settings

# 日志监控功能：保留原 LogMonitor 逻辑，封装为 tool
@tool(description="获取当前各分析引擎的最新进度摘要")
def get_engine_progress() -> dict:
    """
    读取各引擎日志，返回当前进度：
    {
        "insight": {"status": "running", "latest_output": "...", "progress": 60},
        "media": {"status": "done", "latest_output": "...", "progress": 100},
        "query": {"status": "running", "latest_output": "...", "progress": 40},
    }
    """
    from ForumEngine.monitor import LogMonitor  # 复用原监控逻辑
    monitor = LogMonitor()
    return monitor.get_current_status()

FORUM_HOST_PROMPT = """
你是一个舆情分析论坛的主持人，风格活跃、专业。
你需要根据当前各分析引擎的进展，生成简短的串联发言（1-2句话），
让用户感受到分析正在有条不紊地进行。

规则：
- 发言要体现你对各引擎输出内容的理解
- 语气像真正的分析会议主持人
- 每次发言不超过50字
- 当某个引擎有新进展时，及时点评
"""

def create_forum_agent(config=settings) -> Agent:
    return Agent(
        name="ForumHost",
        model=OpenAIChat(
            id=config.FORUM_ENGINE_MODEL_NAME,
            api_key=config.FORUM_ENGINE_API_KEY,
            base_url=config.FORUM_ENGINE_BASE_URL,
        ),
        tools=[get_engine_progress],
        instructions=FORUM_HOST_PROMPT,
        stream=True,
    )
```

---

### 3. 编排层（核心任务）→ `agno_team/opinion_team.py`

这是整个迁移中**架构最重要的部分**，用 agno `Team` 把所有 Agent 组装起来。

原 `app.py` 的调度模式是：并行启动三个分析引擎 → 等待完成 → 启动报告引擎。
对应 agno 的 `Team` 模式应该是 **`coordinate`（协调模式）**，由一个协调者 Agent 决定调用顺序。

```python
# agno_team/opinion_team.py
from agno.agent import Agent
from agno.team import Team
from agno.models.openai import OpenAIChat
from agno_agents import create_insight_agent, create_media_agent, create_query_agent
from agno_agents.report_agent import create_report_agent
from agno_team.forum_agent import create_forum_agent
from config import settings

def create_opinion_team(config=settings) -> Team:
    """
    创建舆情分析 Team。

    工作流程：
    1. 协调者收到用户的分析主题
    2. 并行触发 InsightAgent、MediaAgent、QueryAgent
    3. 三个分析完成后，触发 ReportAgent 生成综合报告
    4. ForumHost 在整个过程中持续生成主持人发言
    """

    insight_agent = create_insight_agent(config)
    media_agent = create_media_agent(config)
    query_agent = create_query_agent(config)
    report_agent = create_report_agent(config)

    # 协调者：决定调用哪个 Agent、何时调用
    team = Team(
        name="微舆舆情分析团队",
        mode="coordinate",   # 协调模式：由 team leader 决定任务分配
        model=OpenAIChat(    # Team leader 使用的模型
            id=config.INSIGHT_ENGINE_MODEL_NAME,
            api_key=config.INSIGHT_ENGINE_API_KEY,
            base_url=config.INSIGHT_ENGINE_BASE_URL,
        ),
        members=[insight_agent, media_agent, query_agent, report_agent],
        instructions="""
你是舆情分析团队的协调者。收到分析主题后：
1. 同时向 InsightAgent、MediaAgent、QueryAgent 发布分析任务
2. 等待三个 Agent 完成分析
3. 将三份报告汇总后，交给 ReportAgent 生成综合报告
4. 返回最终报告路径给用户
""",
        markdown=True,
        stream=True,
        show_tool_calls=True,
    )
    return team

def run_opinion_analysis(topic: str, config=settings) -> str:
    """
    对外接口：接收分析主题，返回综合报告路径。
    替代原 app.py 中的任务调度逻辑。
    """
    team = create_opinion_team(config)
    response = team.run(f"请对以下主题进行全面的舆情分析：{topic}")
    return response.content
```

---

### 4. 应用入口 → `main.py`

替换原 `app.py`，保留 Flask + SocketIO，但把引擎调度部分替换为 agno Team 调用。

```python
# main.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from agno_team.opinion_team import create_opinion_team, run_opinion_analysis
from agno_team.forum_agent import create_forum_agent
from config import settings
from loguru import logger

app = Flask(__name__)
app.config['SECRET_KEY'] = settings.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('start_analysis')
def handle_start_analysis(data):
    topic = data.get('topic', '')
    if not topic:
        emit('error', {'message': '请输入分析主题'})
        return

    emit('analysis_started', {'topic': topic})

    team = create_opinion_team()

    # agno 流式输出，每收到 token 就推送到前端
    for chunk in team.run(f"请对以下主题进行全面的舆情分析：{topic}", stream=True):
        socketio.emit('analysis_progress', {
            'agent': chunk.agent_name if hasattr(chunk, 'agent_name') else 'system',
            'content': chunk.content,
        })

    emit('analysis_complete', {'message': '分析完成'})

# 保留原 app.py 中的其他路由（配置管理、健康检查等）
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host=settings.HOST, port=settings.PORT, debug=False)
```

**注意**：原 `app.py` 中有大量配置管理路由（读写 `config.py`、管理 Streamlit 子进程等），这些逻辑可以先直接从原文件复制过来，不需要重写，只替换引擎调度的部分。

---

## 接口约定（与 B 组对齐）

C 组调用 B 组交付物的方式：

```python
from agno_agents import run_insight_analysis, run_media_analysis, run_query
from agno_agents.report_agent import run_report_generation
```

如果 B 组还没完成，可以先用 mock 函数替代：
```python
def run_insight_analysis(query: str) -> str:
    return f"[Mock] InsightAgent 对 '{query}' 的分析结果"
```

---

## 与前端的兼容性

原项目前端（`templates/` 和 `static/`）通过 SocketIO 事件与后端通信，事件名称包括：
- `start_analysis` → 触发分析
- `analysis_progress` → 实时进度推送
- `forum_message` → 主持人发言
- `analysis_complete` → 分析完成

迁移后，这些事件名称**保持不变**，确保前端无需修改。

---

## 验收标准

- [ ] `create_opinion_team()` 可以无报错实例化
- [ ] `run_opinion_analysis("某热点事件")` 可以完整运行（使用真实 API Key）
- [ ] SocketIO 流式推送正常：前端能实时收到每个 Agent 的输出
- [ ] 原前端页面功能正常：提交主题 → 实时显示进度 → 最终展示报告
- [ ] `main.py` 启动后，访问 `http://localhost:5000` 正常显示
- [ ] ForumHost 主持人发言在前端正常展示
- [ ] 原 `app.py` 的配置管理路由在 `main.py` 中保留完整
