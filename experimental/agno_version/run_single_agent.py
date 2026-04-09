#!/usr/bin/env python3
"""
单独运行三个 Agent 中的任意一个，生成独立报告。
还原原项目的多步 Node 流程：规划结构 → 逐段搜索+总结+反思 → 格式化报告。

用法：
    python run_single_agent.py insight "某品牌产品质量危机"
    python run_single_agent.py media   "人工智能发展趋势"
    python run_single_agent.py query   "某新闻事件深度分析"
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json as json_module


def create_client(config_prefix: str):
    """创建 OpenAI 客户端"""
    from openai import OpenAI
    from config import settings

    api_key = getattr(settings, f"{config_prefix}_API_KEY")
    base_url = getattr(settings, f"{config_prefix}_BASE_URL")
    model_name = getattr(settings, f"{config_prefix}_MODEL_NAME")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=600)
    return client, model_name


def _parse_json(text: str):
    """容错解析 LLM 返回的 JSON（兼容 ```json 代码块、混杂文本等）"""
    import re
    text = text.strip()
    # 去掉 markdown 代码块标记
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json_module.loads(text)
    except json_module.JSONDecodeError:
        # 提取第一个 JSON 对象
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            try:
                return json_module.loads(match.group())
            except json_module.JSONDecodeError:
                pass
        return None


def call_llm(client, model_name: str, system_prompt: str, user_content: str, stream_output: bool = False) -> str:
    """调用 LLM，支持流式输出"""
    stream = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
        stream=True,
    )

    chunks = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
            if stream_output:
                print(delta, end="", flush=True)
    if stream_output:
        print()
    return "".join(chunks)


def run_pipeline(agent_type: str, query: str):
    """
    还原原项目的多步 Node 调用流程：
    1. ReportStructureNode: 规划报告结构 → JSON
    2. 对每个段落:
       a. FirstSearchNode: 生成搜索决策 → JSON（当前无工具，跳过实际搜索）
       b. FirstSummaryNode: 根据段落主题撰写初稿 → JSON
       c. ReflectionNode: 反思并决定补充搜索 → JSON
       d. ReflectionSummaryNode: 深化段落内容 → JSON
    3. ReportFormattingNode: 汇总所有段落，生成最终 Markdown 报告
    """
    agent_config = {
        "insight": "INSIGHT_ENGINE",
        "media":   "MEDIA_ENGINE",
        "query":   "QUERY_ENGINE",
    }
    config_prefix = agent_config[agent_type]
    client, model_name = create_client(config_prefix)

    # 动态导入各阶段 prompt
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

    # ===== 阶段一：规划报告结构 =====
    print("\n📋 阶段一：规划报告结构...")
    structure_raw = call_llm(client, model_name, SYSTEM_PROMPT_REPORT_STRUCTURE, query)
    try:
        paragraphs = json_module.loads(structure_raw)
    except json_module.JSONDecodeError:
        # 尝试提取 JSON 部分
        import re
        match = re.search(r'\[[\s\S]*\]', structure_raw)
        paragraphs = json_module.loads(match.group()) if match else []

    print(f"   规划了 {len(paragraphs)} 个段落：")
    for i, p in enumerate(paragraphs, 1):
        print(f"   {i}. {p['title']}")

    # ===== 阶段二：逐段搜索+总结+反思 =====
    paragraph_results = []
    for idx, para in enumerate(paragraphs, 1):
        title = para["title"]
        content = para.get("content", "")
        para_input = json_module.dumps({"title": title, "content": content}, ensure_ascii=False)

        print(f"\n🔍 段落 {idx}/{len(paragraphs)}：{title}")

        # 2a. 首次搜索决策
        print("   → 搜索决策...", end="", flush=True)
        search_decision_raw = call_llm(client, model_name, SYSTEM_PROMPT_FIRST_SEARCH, para_input)
        print(" 完成")

        # 解析搜索决策并真正调用工具（query=Tavily, media=Bocha, insight=本地DB）
        search_results_text = f"（暂无真实搜索结果，请基于已有知识分析：{title}）"
        decision = _parse_json(search_decision_raw)
        if decision and agent_type in ("query", "media", "insight"):
            tool_name = decision.get("search_tool", "")
            search_query = decision.get("search_query", title)
            tool_kwargs = {"query": search_query}

            if agent_type == "query":
                from agno_tools import call_news_tool as _call_tool
                if tool_name == "search_news_by_date":
                    tool_kwargs["start_date"] = decision.get("start_date", "")
                    tool_kwargs["end_date"] = decision.get("end_date", "")
                if not tool_name:
                    tool_name = "basic_search_news"
            elif agent_type == "media":
                from agno_tools import call_media_tool as _call_tool
                if not tool_name:
                    tool_name = "comprehensive_search"
            else:  # insight
                from agno_tools import call_insight_tool as _call_tool
                # InsightAgent 的工具用 topic 而不是 query
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
                if not tool_name:
                    tool_name = "search_topic_globally"

            print(f"   → 调用工具 {tool_name}({list(tool_kwargs.values())[0]})...", end="", flush=True)
            search_results_text = _call_tool(tool_name, **tool_kwargs)
            print(f" 完成（{len(search_results_text)} 字符）")

        # 2b. 首次总结
        summary_input = json_module.dumps({
            "title": title,
            "content": content,
            "search_query": query,
            "search_results": [search_results_text]
        }, ensure_ascii=False)

        print("   → 撰写初稿...", end="", flush=True)
        summary_raw = call_llm(client, model_name, SYSTEM_PROMPT_FIRST_SUMMARY, summary_input)
        print(" 完成")

        try:
            summary_data = json_module.loads(summary_raw)
            paragraph_state = summary_data.get("paragraph_latest_state", summary_raw)
        except json_module.JSONDecodeError:
            paragraph_state = summary_raw

        # 2c. 反思
        reflection_input = json_module.dumps({
            "title": title,
            "content": content,
            "paragraph_latest_state": paragraph_state
        }, ensure_ascii=False)

        print("   → 反思分析...", end="", flush=True)
        reflection_raw = call_llm(client, model_name, SYSTEM_PROMPT_REFLECTION, reflection_input)
        print(" 完成")

        # 反思阶段也调用真实工具补充搜索
        reflection_results_text = f"（补充搜索结果模拟：{title} 的深度数据）"
        ref_decision = _parse_json(reflection_raw)
        if ref_decision and agent_type in ("query", "media", "insight"):
            tool_name = ref_decision.get("search_tool", "")
            search_query = ref_decision.get("search_query", title)
            tool_kwargs = {"query": search_query}

            if agent_type == "query":
                from agno_tools import call_news_tool as _call_tool
                if tool_name == "search_news_by_date":
                    tool_kwargs["start_date"] = ref_decision.get("start_date", "")
                    tool_kwargs["end_date"] = ref_decision.get("end_date", "")
                if not tool_name:
                    tool_name = "deep_search_news"
            elif agent_type == "media":
                from agno_tools import call_media_tool as _call_tool
                if not tool_name:
                    tool_name = "comprehensive_search"
            else:  # insight
                from agno_tools import call_insight_tool as _call_tool
                tool_kwargs = {"topic": search_query}
                if tool_name == "search_topic_by_date":
                    tool_kwargs["start_date"] = ref_decision.get("start_date", "")
                    tool_kwargs["end_date"] = ref_decision.get("end_date", "")
                elif tool_name == "search_topic_on_platform":
                    tool_kwargs["platform"] = ref_decision.get("platform", "weibo")
                elif tool_name == "search_hot_content":
                    tool_kwargs = {"time_period": ref_decision.get("time_period", "week")}
                elif tool_name == "analyze_sentiment":
                    tool_kwargs = {"texts": ref_decision.get("texts") or [search_query]}
                if not tool_name:
                    tool_name = "get_comments_for_topic"

            print(f"   → 反思补充搜索 {tool_name}({list(tool_kwargs.values())[0]})...", end="", flush=True)
            reflection_results_text = _call_tool(tool_name, **tool_kwargs)
            print(f" 完成（{len(reflection_results_text)} 字符）")

        # 2d. 反思总结（深化内容）
        reflection_summary_input = json_module.dumps({
            "title": title,
            "content": content,
            "search_query": query,
            "search_results": [reflection_results_text],
            "paragraph_latest_state": paragraph_state
        }, ensure_ascii=False)

        print("   → 深化内容...", end="", flush=True)
        ref_summary_raw = call_llm(client, model_name, SYSTEM_PROMPT_REFLECTION_SUMMARY, reflection_summary_input)
        print(" 完成")

        try:
            ref_data = json_module.loads(ref_summary_raw)
            final_state = ref_data.get("updated_paragraph_latest_state", paragraph_state)
        except json_module.JSONDecodeError:
            final_state = paragraph_state

        paragraph_results.append({"title": title, "paragraph_latest_state": final_state})

    # ===== 阶段三：最终报告格式化 =====
    print("\n📝 阶段三：生成最终报告...")
    formatting_input = json_module.dumps(paragraph_results, ensure_ascii=False)
    final_report = call_llm(client, model_name, SYSTEM_PROMPT_REPORT_FORMATTING, formatting_input, stream_output=True)

    return paragraph_results, final_report


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    agent_type = sys.argv[1].lower()
    query = sys.argv[2]

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    valid_types = ["insight", "media", "query"]
    if agent_type not in valid_types:
        print(f"未知的 agent 类型: {agent_type}")
        print(f"可选: {', '.join(valid_types)}")
        sys.exit(1)

    agent_names = {"insight": "InsightAgent", "media": "MediaAgent", "query": "QueryAgent"}
    print(f"启动 {agent_names[agent_type]}，分析主题：{query}")
    print("=" * 60)

    paragraph_results, final_report = run_pipeline(agent_type, query)

    # 保存报告
    output_dir = Path("reports") / f"{agent_type}_reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query[:20].replace(" ", "_").replace("/", "_")

    md_path = output_dir / f"{safe_query}_{timestamp}.md"
    md_path.write_text(final_report, encoding="utf-8")
    print(f"\n报告已保存: {md_path}")

    # 保存结构化数据
    from agno_agents.models import AnalysisResult, ParagraphResult
    result = AnalysisResult(
        query=query,
        paragraphs=[ParagraphResult(**p) for p in paragraph_results],
        final_report=final_report,
    )
    json_path = output_dir / f"{safe_query}_{timestamp}.json"
    json_path.write_text(json_module.dumps(result.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"结构化数据: {json_path}")

    print(f"\n段落数: {len(paragraph_results)}")
    for i, p in enumerate(paragraph_results, 1):
        print(f"  {i}. {p['title']}")
    print(f"\n报告字数: {len(final_report)}")


if __name__ == "__main__":
    main()
