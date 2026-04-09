# agno_team/forum_host.py
# 论坛主持人 LLM 调用器
# 迁移自 BettaFish/ForumEngine/llm_host.py
#
# Stage 1: 改用 agno Agent 实现（之前是裸 OpenAI SDK）

from . import _agno_setup  # noqa: F401  必须最先导入！

from datetime import datetime
from typing import List, Optional

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from .forum_state import ForumEntry


HOST_SYSTEM_PROMPT = """【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查

你是一个多agent舆情分析系统的论坛主持人。你的职责是：

1. **事件梳理**：从各agent的发言中自动识别关键事件、人物、时间节点，按时间顺序整理事件脉络
2. **引导讨论**：根据各agent的发言，引导深入讨论关键问题，探究深层原因
3. **纠正错误**：结合不同agent的视角以及言论，如果发现事实错误或逻辑矛盾，请明确指出
4. **整合观点**：综合不同agent的视角，形成更全面的认识，找出共识和分歧
5. **趋势预测**：基于已有信息分析舆情发展趋势，提出可能的风险点
6. **推进分析**：提出新的分析角度或需要关注的问题，引导后续讨论方向

**Agent介绍**：
- **INSIGHT Agent**：专注于私有舆情数据库的深度挖掘和分析，提供历史数据和模式对比
- **MEDIA Agent**：擅长多模态内容分析，关注媒体报道、图片、视频等视觉信息的传播效果
- **QUERY Agent**：负责精准信息搜索，提供最新的网络信息和实时动态

**发言要求**：
1. **综合性**：每次发言控制在1000字以内，内容应包括事件梳理、观点整合、问题引导等多个方面
2. **结构清晰**：使用明确的段落结构，包括事件梳理、观点对比、问题提出等部分
3. **深入分析**：不仅仅总结已有信息，还要提出深层次的见解和分析
4. **客观中立**：基于事实进行分析和判断，避免主观臆测和情绪化表达
5. **前瞻性**：提出具有前瞻性的观点和建议，引导讨论向更深入的方向发展

**注意事项**：
- 本讨论基于科研目的，已通过伦理性合规审查
- 保持专业性和学术性，重视数据和证据
- 对于敏感话题，应保持谨慎态度，基于事实进行分析

【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查"""


def _build_user_prompt(recent_speeches: List[ForumEntry]) -> str:
    """构建主持人 user prompt"""
    speeches_text = "\n\n".join([
        f"[{datetime.fromtimestamp(s.timestamp).strftime('%H:%M:%S')}] {s.role}:\n{s.content}"
        for s in recent_speeches
    ])

    current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")

    return f"""【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查

今天的实际时间是{current_time}

最近的Agent发言记录：
{speeches_text}

请你作为论坛主持人，基于以上agent的发言进行综合分析，请按以下结构组织你的发言：

**一、事件梳理与时间线分析**
- 从各agent发言中自动识别关键事件、人物、时间节点
- 按时间顺序整理事件脉络，梳理因果关系
- 指出关键转折点和重要节点

**二、观点整合与对比分析**
- 综合INSIGHT、MEDIA、QUERY三个Agent的视角和发现
- 指出不同数据源之间的共识与分歧
- 分析每个Agent的信息价值和互补性
- 如果发现事实错误或逻辑矛盾，请明确指出并给出理由

**三、深层次分析与趋势预测**
- 基于已有信息分析舆情的深层原因和影响因素
- 预测舆情发展趋势，指出可能的风险点和机遇
- 提出需要特别关注的方面和指标

**四、问题引导与讨论方向**
- 提出2-3个值得进一步深入探讨的关键问题
- 为后续研究提出具体的建议和方向
- 引导各Agent关注特定的数据维度或分析角度

请发表综合性的主持人发言（控制在1000字以内），内容应包含以上四个部分，并保持逻辑清晰、分析深入、视角独特。

【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查"""


class ForumHost:
    """
    论坛主持人，使用单独的 LLM 配置（默认 qwen-plus / FORUM_HOST_*）

    实现：agno Agent（无工具，纯文本生成）
    """

    def __init__(self, config=None):
        if config is None:
            from config import settings
            config = settings

        # 关键：必须三个字段一致回退（key/base_url/model 是一组）
        if config.FORUM_HOST_API_KEY:
            api_key = config.FORUM_HOST_API_KEY
            base_url = config.FORUM_HOST_BASE_URL
            model_name = config.FORUM_HOST_MODEL_NAME
        elif config.QUERY_ENGINE_API_KEY:
            print("⚠️  FORUM_HOST_API_KEY 未配置，回退到 QUERY_ENGINE_*")
            api_key = config.QUERY_ENGINE_API_KEY
            base_url = config.QUERY_ENGINE_BASE_URL
            model_name = config.QUERY_ENGINE_MODEL_NAME
        else:
            raise ValueError(
                "ForumHost 未配置 API Key：请在 .env 中设置 FORUM_HOST_API_KEY，"
                "或确保 QUERY_ENGINE_API_KEY 可用作回退"
            )

        self.model_name = model_name
        self.agent = Agent(
            name="ForumHost",
            model=OpenAIChat(
                id=model_name,
                api_key=api_key,
                base_url=base_url,
                role_map={
                    "system": "system",
                    "user": "user",
                    "assistant": "assistant",
                    "tool": "tool",
                    "model": "assistant",
                },
            ),
            instructions=HOST_SYSTEM_PROMPT,
            system_message_role="system",
            markdown=True,
        )

    async def generate(self, recent_speeches: List[ForumEntry]) -> Optional[str]:
        """异步生成主持人发言（agno 原生异步入口）"""
        if not recent_speeches:
            return None

        user_prompt = _build_user_prompt(recent_speeches)
        try:
            response = await self.agent.arun(user_prompt)
            content = response.content if response else None
            return content.strip() if content else None
        except Exception as e:
            print(f"⚠️  ForumHost (agno) 调用失败: {e}")
            return None
