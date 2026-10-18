"""Shared Streamlit execution lifecycle for Query/Media/Insight engines."""

from __future__ import annotations

import traceback
from contextlib import nullcontext
from typing import Any, Callable

from loguru import logger

from common.provenance.io import save_engine_report
from common.provenance.normalizer import new_provenance_bundle
from common.provenance.runtime import (
    append_runtime_forum_message,
    publish_runtime_failure,
    publish_runtime_result,
)
from common.provenance.validators import filter_valid_evidence
from utils.forum_reader import suppress_global_forum_context
from utils.github_issues import error_with_issue_link


def read_launch_params(st_module) -> tuple[Any, str, bool, str]:
    """Read modern or legacy Streamlit query parameters consistently."""
    def first_value(value: Any, default: Any = "") -> Any:
        if isinstance(value, (list, tuple)):
            return value[0] if value else default
        return value if value is not None else default

    try:
        params = st_module.query_params
        query = params.get("query", "")
        auto_search = str(params.get("auto_search", "false")).lower() == "true"
    except AttributeError:
        params = st_module.experimental_get_query_params()
        query = first_value(params.get("query", ""))
        auto_search = str(first_value(params.get("auto_search", "false"), "false")).lower() == "true"
    if isinstance(query, (list, tuple)):
        query = first_value(query)
    if not isinstance(auto_search, bool):
        auto_search = str(first_value(auto_search, "false")).lower() == "true"
    run_id = first_value(params.get("run_id", ""))
    return params, str(query or ""), auto_search, str(run_id or "")


def should_start_research(st_module, query: str, auto_search: bool, run_id: str) -> bool:
    execution_key = run_id or query
    if auto_search and query and st_module.session_state.get("auto_search_executed") != execution_key:
        st_module.session_state.auto_search_executed = execution_key
        return True
    if query and not auto_search:
        st_module.warning("等待搜索启动信号...")
    return False


def report_launch_failure(
    st_module, *, run_id: str, engine: str, query: str, message: str
) -> None:
    """Show a preflight error and terminate the matching runtime engine slot."""
    st_module.error(message)
    try:
        publish_runtime_failure(run_id, engine, query, message)
    except Exception:
        logger.exception(f"{engine} 启动失败状态提交失败")


def persist_research_result(agent: Any, final_report: str):
    """Persist a research engine result through the shared public API."""
    return save_engine_report(
        final_report,
        query=agent.state.query,
        output_dir=agent.config.OUTPUT_DIR,
        bundle=agent.state.provenance_bundle,
        state=agent.state,
        save_intermediate_state=agent.config.SAVE_INTERMEDIATE_STATES,
    )


def paragraph_evidence_ids(agent: Any, paragraph_title: str) -> list[str]:
    """Return valid evidence retrieved for one paragraph, including deduped contexts."""
    title = str(paragraph_title or "").strip()
    if not title:
        return []
    bundle = filter_valid_evidence(agent.state.provenance_bundle)
    matched = []
    for evidence in bundle.evidence:
        contexts = [evidence.scope]
        contexts.extend(evidence.meta.get("retrieval_contexts") or [])
        if any(
            isinstance(context, dict)
            and str(context.get("subject") or "").strip() == title
            for context in contexts
        ):
            matched.append(evidence.evidence_id)
    return list(dict.fromkeys(matched))


def publish_paragraph_summary(agent: Any, run_id: str, engine: str, paragraph: Any) -> bool:
    """Write a run-scoped forum message only when it has resolvable evidence."""
    if not run_id:
        return False
    evidence_ids = paragraph_evidence_ids(agent, getattr(paragraph, "title", ""))
    return append_runtime_forum_message(
        run_id,
        engine,
        getattr(getattr(paragraph, "research", None), "latest_summary", ""),
        evidence_ids,
    )


def run_streamlit_research(
    *,
    st_module,
    query: str,
    config: Any,
    run_id: str,
    engine: str,
    agent_factory: Callable[[Any], Any],
    display_results: Callable[[Any, str], None],
    app_name: str,
) -> tuple[Any, str] | None:
    """Execute, persist, publish, and display one engine research result."""
    try:
        progress_bar = st_module.progress(0)
        status_text = st_module.empty()

        status_text.text("正在初始化Agent...")
        agent = agent_factory(config)
        st_module.session_state.agent = agent
        progress_bar.progress(10)

        agent.state.provenance_bundle = new_provenance_bundle(
            f"{engine}_engine",
            query,
            run_id=run_id,
        )

        forum_context = suppress_global_forum_context() if run_id else nullcontext()
        with forum_context:
            status_text.text("正在生成报告结构...")
            agent._generate_report_structure(query)
            progress_bar.progress(20)

            total_paragraphs = len(agent.state.paragraphs)
            progress_denominator = max(total_paragraphs, 1)
            for index, paragraph in enumerate(agent.state.paragraphs):
                status_text.text(
                    f"正在处理段落 {index + 1}/{total_paragraphs}: {paragraph.title}"
                )
                agent._initial_search_and_summary(index)
                progress_bar.progress(
                    int(20 + (index + 0.5) / progress_denominator * 60)
                )
                agent._reflection_loop(index)
                paragraph.research.mark_completed()
                try:
                    publish_paragraph_summary(agent, run_id, engine, paragraph)
                except Exception:
                    logger.exception(f"{engine} 段落来源消息写入失败")
                progress_bar.progress(
                    int(20 + (index + 1) / progress_denominator * 60)
                )

            status_text.text("正在生成最终报告...")
            final_report = agent._generate_final_report()

        # Saving is the primary result.  A transient callback failure must not
        # erase a successful local report or mislabel the research itself.
        status_text.text("正在保存报告...")
        persist_research_result(agent, final_report)
        progress_bar.progress(90)

        try:
            published = publish_runtime_result(
                run_id, engine, query, final_report, agent.state.provenance_bundle
            ) if run_id else False
            if run_id and published is not True:
                raise RuntimeError("运行态证据回调未配置或未确认成功")
        except Exception as publish_error:
            logger.exception(f"{engine} 运行态结果提交失败: {publish_error}")
            st_module.warning(
                f"研究和本地保存已完成，但运行态结果提交失败: {publish_error}"
            )
            try:
                publish_runtime_failure(
                    run_id,
                    engine,
                    query,
                    f"研究已保存，但运行态结果提交失败: {publish_error}",
                )
            except Exception:
                logger.exception(f"{engine} 运行态失败状态提交失败")

        progress_bar.progress(100)
        status_text.text("研究完成！")
    except Exception as error:
        try:
            publish_runtime_failure(run_id, engine, query, str(error))
        except Exception:
            logger.exception(f"{engine} 失败状态提交失败")
        error_display = error_with_issue_link(
            f"研究过程中发生错误: {error}",
            traceback.format_exc(),
            app_name=app_name,
        )
        st_module.error(error_display)
        logger.exception(f"研究过程中发生错误: {error}")
        return None

    try:
        display_results(agent, final_report)
    except Exception as display_error:
        logger.exception(f"{engine} 研究已完成，但结果界面渲染失败: {display_error}")
        st_module.warning(
            f"研究、保存和运行态提交已完成，但结果界面渲染失败: {display_error}"
        )
    return agent, final_report


__all__ = [
    "read_launch_params",
    "paragraph_evidence_ids",
    "persist_research_result",
    "publish_paragraph_summary",
    "report_launch_failure",
    "run_streamlit_research",
    "should_start_research",
]
