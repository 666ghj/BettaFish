# agno_team/forum_agent.py
# TODO(C组): 迁移自 ForumEngine/monitor.py + ForumEngine/llm_host.py
# 负责监控各引擎进度并生成论坛主持人发言

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from typing import Dict


@tool(description="获取当前各分析引擎的最新运行状态和进度摘要")
def get_engine_progress() -> Dict:
    """
    读取各引擎日志，返回实时进度。
    迁移自 ForumEngine/monitor.py LogMonitor 类

    Returns:
        {
            "insight": {"status": "running|done|idle", "progress": 0~100, "latest_output": str},
            "media":   {"status": ..., "progress": ..., "latest_output": ...},
            "query":   {"status": ..., "progress": ..., "latest_output": ...},
        }
    """
    # TODO(C组): 复用 ForumEngine/monitor.py 中的 LogMonitor 日志读取逻辑
    raise NotImplementedError("TODO(C组)")


FORUM_HOST_PROMPT = """
# TODO(C组): 从 ForumEngine/llm_host.py 迁移主持人 prompt
# 主持人风格：专业、活跃，每次发言不超过50字，根据引擎进展实时点评
"""


def create_forum_agent(config=None):
    """
    创建论坛主持人 Agent。

    Args:
        config: Settings 对象，为 None 时从全局 settings 读取
    """
    if config is None:
        from config import settings
        config = settings

    return Agent(
        name="ForumHost",
        model=OpenAIChat(
            id=config.FORUM_HOST_MODEL_NAME,
            api_key=config.FORUM_HOST_API_KEY,
            base_url=config.FORUM_HOST_BASE_URL,
        ),
        tools=[get_engine_progress],
        instructions=FORUM_HOST_PROMPT,
        stream=True,
    )
