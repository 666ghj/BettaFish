# agno_team/opinion_team.py
# 舆情分析主调度器（路径3：asyncio + 内存共享 forum_state）
#
# 工作流程：
# 1. 创建 ForumState（共享论坛状态 + Host 触发回调）
# 2. asyncio.gather 三个 agent 并发执行
# 3. 每个 agent 在生成段落总结时：
#    - 读取 ForumState 中最新的 HOST 发言并塞进 prompt
#    - 写入段落产出，自动触发 Host 阈值检查
# 4. 三 agent 全部完成后，调用 ReportAgent 综合三份报告 + 论坛日志

from __future__ import annotations
import asyncio
from typing import Dict, Any, List, Optional

from .forum_state import ForumState
from .forum_host import ForumHost
from .agent_runner import run_agent_pipeline


async def run_opinion_pipeline(
    query: str,
    host_threshold: int = 5,
    config=None,
) -> Dict[str, Any]:
    """
    异步运行完整的舆情分析流程：三 agent 并发 + ForumHost 引导 + 最终汇总。

    Args:
        query: 分析主题
        host_threshold: 累计多少条 agent 段落总结触发一次 Host 引导，默认 5
        config: Settings 对象

    Returns:
        dict: {
            "query": str,
            "agent_results": {
                "insight": {agent_results dict},
                "media":   {agent_results dict},
                "query":   {agent_results dict},
            },
            "forum_log": str (完整论坛日志的人类可读格式),
            "host_speeches": List[str] (所有 HOST 引导发言),
        }
    """
    # 初始化 ForumHost
    host = ForumHost(config=config)

    # 创建 ForumState，绑定 host 回调
    forum_state = ForumState(
        host_threshold=host_threshold,
        host_callback=host.generate,
    )

    print(f"\n{'=' * 60}")
    print(f"  舆情分析任务启动")
    print(f"  主题: {query}")
    print(f"  Host 引导阈值: {host_threshold} 条")
    print(f"{'=' * 60}\n")

    # ⭐ 三 agent 并发执行
    insight_task = asyncio.create_task(
        run_agent_pipeline("insight", query, forum_state),
        name="InsightAgent",
    )
    media_task = asyncio.create_task(
        run_agent_pipeline("media", query, forum_state),
        name="MediaAgent",
    )
    query_task = asyncio.create_task(
        run_agent_pipeline("query", query, forum_state),
        name="QueryAgent",
    )

    # gather 等待全部完成
    results = await asyncio.gather(
        insight_task, media_task, query_task,
        return_exceptions=True,
    )

    # 处理可能的异常
    agent_results = {}
    for r in results:
        if isinstance(r, Exception):
            print(f"⚠️  Agent 执行失败: {type(r).__name__}: {r}")
            continue
        agent_results[r["agent_type"]] = r

    print(f"\n{'=' * 60}")
    print(f"  全部 Agent 执行完毕")
    print(f"  论坛总条数: {len(forum_state.entries)}")
    print(f"  Host 引导次数: {len(forum_state.get_all_host_speeches())}")
    print(f"{'=' * 60}\n")

    return {
        "query": query,
        "agent_results": agent_results,
        "forum_log": forum_state.format_full_log(),
        "host_speeches": [e.content for e in forum_state.get_all_host_speeches()],
        "_forum_state": forum_state,  # 供 ReportAgent 进一步使用
    }


def run_opinion_analysis(query: str, host_threshold: int = 5, config=None) -> Dict[str, Any]:
    """
    同步入口：包装 run_opinion_pipeline，便于命令行/Flask 调用。
    """
    return asyncio.run(run_opinion_pipeline(query, host_threshold=host_threshold, config=config))
