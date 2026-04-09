# agno_team/agent_runner.py
# 单个 Agent 的多步流程编排（async 版本）
# 提取自 run_single_agent.py，加入 ForumState 集成
#
# Stage 3 改造：所有 LLM 调用改用 agno Agent（之前是裸 OpenAI SDK）
# - 每个 (engine_type, stage) 组合用一个独立的 agno Agent 实例
# - Agent 的 instructions 在每次调用前动态设置，避免预创建 30+ 个 Agent
# - 工具调用仍然走我们手写的 dispatch（保持段落级流程的精细控制）

from __future__ import annotations

# 必须最先导入：清代理 + patch agno httpx client
from . import _agno_setup  # noqa: F401

import asyncio
import json
import re
from typing import List, Dict, Any, Optional

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from .forum_state import ForumState, format_host_speech_for_prompt


_ROLE_MAP = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
    "tool": "tool",
    "model": "assistant",
}


# ===== agno Agent 缓存 =====
# 按 engine_type 缓存一个"通用"的 agno Agent，每次调用时通过 message 传 system/user

_agents_cache: Dict[str, Agent] = {}


def _get_agno_agent(config_prefix: str) -> Agent:
    """
    获取或创建一个 engine 对应的 agno Agent。

    设计取舍：
    - 不为每个 stage 单独创建 agent（避免 30+ 个 agent 实例）
    - 让 agent 的 instructions 保持空，每次调用都把 system_prompt 拼到 user message 前面
    - 这相当于把 agno 当成一个"带代理 patch 的 OpenAI SDK 包装器"使用
    """
    if config_prefix in _agents_cache:
        return _agents_cache[config_prefix]

    from config import settings
    api_key = getattr(settings, f"{config_prefix}_API_KEY")
    base_url = getattr(settings, f"{config_prefix}_BASE_URL")
    model_name = getattr(settings, f"{config_prefix}_MODEL_NAME")

    if not api_key:
        raise ValueError(f"{config_prefix}_API_KEY 未配置")

    agent = Agent(
        name=f"{config_prefix}_Worker",
        model=OpenAIChat(
            id=model_name,
            api_key=api_key,
            base_url=base_url,
            role_map=_ROLE_MAP,
        ),
        # 不设 instructions，每次调用通过 user prompt 携带 system_prompt
        # 这样可以让一个 agent 实例服务于 6 个不同 stage 的 prompt
        system_message_role="system",
        markdown=True,
    )
    _agents_cache[config_prefix] = agent
    return agent


async def _call_llm(client_or_agent, model_name_or_unused, system_prompt: str, user_content: str) -> str:
    """
    调用 LLM 的统一入口（agno 模式）。

    保持与旧版相同的签名，便于其他代码不改动。
    第一/二个参数实际上不再使用（保留是为了兼容性），真正的 agent 通过
    config_prefix → _get_agno_agent 动态获取。

    Stage 3 改造：传入的 client/model 参数被忽略，改用全局 agno Agent 缓存。
    """
    # 如果第一个参数已经是 agno Agent（兼容直接传入的情况）
    if isinstance(client_or_agent, Agent):
        agent = client_or_agent
    else:
        # 兼容老调用方式：第一个参数曾经是 OpenAI client，现在用全局 fallback
        # （实际上 Stage 3 之后会通过 config_prefix 直接拿）
        raise ValueError("agent_runner Stage 3 改造后，请通过 _call_llm_via_engine 调用")

    # agno Agent 的 instructions 是在 init 时设置的；这里我们用 prepend 方式
    # 把 system_prompt 拼到 user message 前面，让 agent 临时拥有这个角色
    full_message = f"<system>\n{system_prompt}\n</system>\n\n{user_content}"
    response = await agent.arun(full_message)
    return response.content if response else ""


async def _call_llm_via_engine(config_prefix: str, system_prompt: str, user_content: str) -> str:
    """
    Stage 3 推荐入口：根据 engine_type 拿对应的 agno Agent，调用一次。
    """
    agent = _get_agno_agent(config_prefix)
    full_message = f"<system>\n{system_prompt}\n</system>\n\n{user_content}"
    try:
        response = await agent.arun(full_message)
        return response.content if response else ""
    except Exception as e:
        print(f"⚠️  agno agent 调用失败 ({config_prefix}): {e}")
        return ""


# 兼容旧的 _get_client / _call_llm_sync API（其他文件可能还在用）

def _get_client(config_prefix: str):
    """兼容旧 API：返回 (agent, model_name) 元组"""
    agent = _get_agno_agent(config_prefix)
    from config import settings
    return agent, getattr(settings, f"{config_prefix}_MODEL_NAME")


def _parse_json(text: str) -> Optional[Any]:
    """容错解析 LLM 返回的 JSON"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*?\}", text) or re.search(r"\[[\s\S]*?\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


# ===== 工具调用调度 =====

async def _call_tool_async(agent_type: str, decision: Dict[str, Any], default_topic: str) -> str:
    """根据 decision 字典调用对应的工具（异步包装同步工具）"""
    tool_name = decision.get("search_tool", "")
    search_query = decision.get("search_query", default_topic)

    if agent_type == "query":
        from agno_tools import call_news_tool
        tool_kwargs = {"query": search_query}
        if tool_name == "search_news_by_date":
            tool_kwargs["start_date"] = decision.get("start_date", "")
            tool_kwargs["end_date"] = decision.get("end_date", "")
        if not tool_name:
            tool_name = "basic_search_news"
        return await asyncio.to_thread(call_news_tool, tool_name, **tool_kwargs)

    elif agent_type == "media":
        from agno_tools import call_media_tool
        tool_kwargs = {"query": search_query}
        if not tool_name:
            tool_name = "comprehensive_search"
        return await asyncio.to_thread(call_media_tool, tool_name, **tool_kwargs)

    elif agent_type == "insight":
        # 国内本地数据库工具
        domestic_tools = {
            "search_hot_content", "search_topic_globally", "search_topic_by_date",
            "get_comments_for_topic", "search_topic_on_platform", "analyze_sentiment",
        }
        # 海外工具
        overseas_tools = {
            "search_hackernews", "search_hackernews_recent", "search_hackernews_comments",
            "search_github_repos", "search_github_issues", "search_github_code",
            "search_youtube_videos", "get_youtube_comments", "search_youtube_with_comments",
            "search_reddit", "get_subreddit_hot", "get_reddit_post_comments",
        }

        if tool_name in overseas_tools:
            from agno_tools import call_overseas_tool
            # 海外工具的参数命名是 query 而不是 topic
            tool_kwargs = {"query": search_query}
            if tool_name == "search_reddit":
                if decision.get("subreddit"):
                    tool_kwargs["subreddit"] = decision["subreddit"]
                tool_kwargs["sort"] = decision.get("sort", "relevance")
            elif tool_name == "get_subreddit_hot":
                tool_kwargs = {
                    "subreddit": decision.get("subreddit", "programming"),
                    "time_filter": decision.get("time_filter", "week"),
                }
            elif tool_name == "get_youtube_comments":
                tool_kwargs = {"video_id": decision.get("video_id", "")}
            elif tool_name == "get_reddit_post_comments":
                tool_kwargs = {
                    "post_id": decision.get("post_id", ""),
                    "subreddit": decision.get("subreddit", ""),
                }
            return await asyncio.to_thread(call_overseas_tool, tool_name, **tool_kwargs)

        # 国内工具（默认路径）
        from agno_tools import call_insight_tool
        tool_kwargs = {"topic": search_query}
        if tool_name == "search_topic_by_date":
            tool_kwargs["start_date"] = decision.get("start_date", "")
            tool_kwargs["end_date"] = decision.get("end_date", "")
        elif tool_name == "search_topic_on_platform":
            tool_kwargs["platform"] = decision.get("platform", "weibo")
            if decision.get("start_date"):
                tool_kwargs["start_date"] = decision.get("start_date")
                tool_kwargs["end_date"] = decision.get("end_date", "")
        elif tool_name == "search_hot_content":
            tool_kwargs = {"time_period": decision.get("time_period", "week")}
        elif tool_name == "analyze_sentiment":
            tool_kwargs = {"texts": decision.get("texts") or [search_query]}
        if not tool_name or tool_name not in domestic_tools:
            tool_name = "search_topic_globally"
        return await asyncio.to_thread(call_insight_tool, tool_name, **tool_kwargs)

    return f"未知 agent_type: {agent_type}"


# ===== 单 Agent 完整流程（异步版）=====

AGENT_CONFIG = {
    "insight": ("InsightAgent", "INSIGHT_ENGINE", "INSIGHT"),
    "media":   ("MediaAgent",   "MEDIA_ENGINE",   "MEDIA"),
    "query":   ("QueryAgent",   "QUERY_ENGINE",   "QUERY"),
}


async def run_agent_pipeline(
    agent_type: str,
    query: str,
    forum_state: Optional[ForumState] = None,
) -> Dict[str, Any]:
    """
    异步运行单个 Agent 的完整三阶段流程：
    1. 规划报告结构
    2. 逐段：搜索决策 → 工具调用 → 撰写初稿 → 反思 → 补充搜索 → 深化
    3. 最终格式化报告

    在每个段落的 SummaryNode 之前会读取 forum_state 的最新 HOST 发言，
    塞进 prompt 前缀作为引导；段落产出后写入 forum_state。

    Returns:
        dict: {
            "agent_type": str,
            "agent_name": str,
            "query": str,
            "paragraphs": List[{"title": str, "paragraph_latest_state": str}],
            "final_report": str,
        }
    """
    if agent_type not in AGENT_CONFIG:
        raise ValueError(f"未知 agent_type: {agent_type}")

    agent_name, config_prefix, forum_role = AGENT_CONFIG[agent_type]
    # Stage 3 改造：不再创建 OpenAI client，所有 LLM 调用通过 _call_llm_via_engine 走 agno
    # 仍然预热一次 agent 实例（缓存命中后续都很快）
    _get_agno_agent(config_prefix)

    # 检测可用的海外工具（仅 insight 需要）
    overseas_extra = ""
    if agent_type == "insight":
        from config import settings
        from agno_agents.insight_agent import _detect_available_overseas, _build_overseas_section
        available = _detect_available_overseas(settings)
        overseas_extra = _build_overseas_section(available)

    # 动态导入对应 agent 的 prompt
    if agent_type == "insight":
        from agno_agents.insight_agent import (
            SYSTEM_PROMPT_REPORT_STRUCTURE,
            SYSTEM_PROMPT_FIRST_SEARCH,
            SYSTEM_PROMPT_FIRST_SUMMARY,
            SYSTEM_PROMPT_REFLECTION,
            SYSTEM_PROMPT_REFLECTION_SUMMARY,
            SYSTEM_PROMPT_REPORT_FORMATTING,
        )
    elif agent_type == "media":
        from agno_agents.media_agent import (
            SYSTEM_PROMPT_REPORT_STRUCTURE,
            SYSTEM_PROMPT_FIRST_SEARCH,
            SYSTEM_PROMPT_FIRST_SUMMARY,
            SYSTEM_PROMPT_REFLECTION,
            SYSTEM_PROMPT_REFLECTION_SUMMARY,
            SYSTEM_PROMPT_REPORT_FORMATTING,
        )
    else:
        from agno_agents.query_agent import (
            SYSTEM_PROMPT_REPORT_STRUCTURE,
            SYSTEM_PROMPT_FIRST_SEARCH,
            SYSTEM_PROMPT_FIRST_SUMMARY,
            SYSTEM_PROMPT_REFLECTION,
            SYSTEM_PROMPT_REFLECTION_SUMMARY,
            SYSTEM_PROMPT_REPORT_FORMATTING,
        )

    print(f"\n🚀 [{agent_name}] 启动，主题: {query}")

    # ===== 阶段一：规划报告结构 =====
    structure_raw = await _call_llm_via_engine(config_prefix, SYSTEM_PROMPT_REPORT_STRUCTURE, query)
    paragraphs_outline = _parse_json(structure_raw)
    if not isinstance(paragraphs_outline, list):
        paragraphs_outline = []

    print(f"📋 [{agent_name}] 规划了 {len(paragraphs_outline)} 个段落")

    # ===== 阶段二：逐段搜索 + 总结 + 反思 =====
    paragraph_results: List[Dict[str, str]] = []

    for idx, para in enumerate(paragraphs_outline, 1):
        if not isinstance(para, dict):
            continue
        title = para.get("title", "")
        content = para.get("content", "")
        para_input = json.dumps({"title": title, "content": content}, ensure_ascii=False)

        print(f"🔍 [{agent_name}] 段落 {idx}/{len(paragraphs_outline)}: {title}")

        # 2a. 首次搜索决策（insight 类型在 system prompt 末尾追加海外平台说明）
        search_system = SYSTEM_PROMPT_FIRST_SEARCH + (overseas_extra if overseas_extra else "")
        search_decision_raw = await _call_llm_via_engine(config_prefix, search_system, para_input)
        decision = _parse_json(search_decision_raw)

        # 2b. 调用真实工具
        search_results = f"（无搜索结果：{title}）"
        if isinstance(decision, dict):
            try:
                search_results = await _call_tool_async(agent_type, decision, title)
            except Exception as e:
                search_results = f"工具调用失败: {e}"

        # 2c. 读取 HOST 引导发言并撰写初稿
        host_hint = forum_state.get_latest_host_speech() if forum_state else None
        host_prefix = format_host_speech_for_prompt(host_hint) if host_hint else ""

        summary_input = host_prefix + json.dumps({
            "title": title,
            "content": content,
            "search_query": query,
            "search_results": [search_results],
        }, ensure_ascii=False)

        summary_raw = await _call_llm_via_engine(config_prefix, SYSTEM_PROMPT_FIRST_SUMMARY, summary_input)
        summary_data = _parse_json(summary_raw)
        paragraph_state = (
            summary_data.get("paragraph_latest_state", summary_raw)
            if isinstance(summary_data, dict)
            else summary_raw
        )

        # ⭐ 写入 forum_state（可能触发 Host）
        if forum_state is not None:
            await forum_state.write(forum_role, paragraph_state)

        # 2d. 反思：基于当前段落生成补充搜索
        reflection_input = json.dumps({
            "title": title,
            "content": content,
            "paragraph_latest_state": paragraph_state,
        }, ensure_ascii=False)

        reflection_system = SYSTEM_PROMPT_REFLECTION + (overseas_extra if overseas_extra else "")
        reflection_raw = await _call_llm_via_engine(config_prefix, reflection_system, reflection_input)
        ref_decision = _parse_json(reflection_raw)

        ref_search_results = f"（无补充搜索结果：{title}）"
        if isinstance(ref_decision, dict):
            try:
                ref_search_results = await _call_tool_async(agent_type, ref_decision, title)
            except Exception as e:
                ref_search_results = f"补充搜索失败: {e}"

        # 2e. 反思总结：再次读取 HOST 引导，深化段落
        host_hint2 = forum_state.get_latest_host_speech() if forum_state else None
        host_prefix2 = format_host_speech_for_prompt(host_hint2) if host_hint2 else ""

        ref_summary_input = host_prefix2 + json.dumps({
            "title": title,
            "content": content,
            "search_query": query,
            "search_results": [ref_search_results],
            "paragraph_latest_state": paragraph_state,
        }, ensure_ascii=False)

        ref_summary_raw = await _call_llm_via_engine(config_prefix, SYSTEM_PROMPT_REFLECTION_SUMMARY, ref_summary_input)
        ref_summary_data = _parse_json(ref_summary_raw)
        final_state = (
            ref_summary_data.get("updated_paragraph_latest_state", paragraph_state)
            if isinstance(ref_summary_data, dict)
            else paragraph_state
        )

        # ⭐ 深化后的段落再次写入 forum_state
        if forum_state is not None:
            await forum_state.write(forum_role, final_state)

        paragraph_results.append({
            "title": title,
            "paragraph_latest_state": final_state,
        })

    # ===== 阶段三：最终报告格式化 =====
    print(f"📝 [{agent_name}] 生成最终报告...")
    formatting_input = json.dumps(paragraph_results, ensure_ascii=False)
    final_report = await _call_llm_via_engine(config_prefix, SYSTEM_PROMPT_REPORT_FORMATTING, formatting_input)

    print(f"✅ [{agent_name}] 完成（{len(final_report)} 字）")

    return {
        "agent_type": agent_type,
        "agent_name": agent_name,
        "query": query,
        "paragraphs": paragraph_results,
        "final_report": final_report,
    }
