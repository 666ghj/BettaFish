#!/usr/bin/env python3
"""
完整的舆情分析流程：三 Agent 并发 + ForumHost 引导

用法：
    python run_full_pipeline.py "Claude Code 在中文程序员社区的舆情分析"
    python run_full_pipeline.py "Claude Code" --threshold 3

工作机制：
    1. InsightAgent / MediaAgent / QueryAgent 三个 agent 通过 asyncio 并发执行
    2. 每个 agent 内部仍然是「规划 → 段落（搜索→总结→反思→深化）→ 最终格式化」流程
    3. 段落总结产出后立即写入共享 ForumState
    4. ForumState 累计 N 条 agent 发言后自动触发 ForumHost LLM 调用
    5. Host 发言写回 ForumState，下一段段落总结时被 agent 读取并塞入 prompt
    6. 形成「Agent 段落产出 → Host 引导 → Agent 下段调整方向」的真实反馈循环
    7. 三 agent 全部完成后，输出三份独立报告 + 完整论坛日志
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json
import argparse

# 清理代理（避免 agno/httpx 走 SOCKS 代理）
for _k in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(_k, None)

# 让脚本能找到项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description="舆情分析全流程")
    parser.add_argument("query", help="分析主题")
    parser.add_argument("--threshold", type=int, default=5, help="Host 触发阈值（默认 5 条 agent 发言）")
    parser.add_argument("--output", type=str, default="reports/full_pipeline", help="输出目录")
    parser.add_argument("--no-report", action="store_true", help="跳过 ReportAgent 综合报告生成")
    args = parser.parse_args()

    from agno_team import run_opinion_analysis

    result = run_opinion_analysis(
        query=args.query,
        host_threshold=args.threshold,
    )

    # ===== 落盘 =====
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = args.query[:30].replace(" ", "_").replace("/", "_")
    out_dir = Path(args.output) / f"{safe_query}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 三份 agent 报告
    for agent_type, agent_result in result["agent_results"].items():
        md_path = out_dir / f"{agent_type}_report.md"
        md_path.write_text(agent_result["final_report"], encoding="utf-8")
        print(f"  📄 {agent_type:8} → {md_path}")

    # 完整论坛日志
    forum_path = out_dir / "forum_log.txt"
    forum_path.write_text(result["forum_log"], encoding="utf-8")
    print(f"  📋 forum    → {forum_path}")

    # Host 发言单独保存
    host_path = out_dir / "host_speeches.md"
    host_md = "\n\n---\n\n".join(
        f"## Host 发言 #{i + 1}\n\n{s}" for i, s in enumerate(result["host_speeches"])
    )
    host_path.write_text(host_md, encoding="utf-8")
    print(f"  🎤 host     → {host_path}")

    # 结构化数据（供后续 ReportAgent 消费）
    summary_path = out_dir / "summary.json"
    summary_data = {
        "query": result["query"],
        "agent_results": {
            k: {
                "agent_name": v["agent_name"],
                "paragraphs": v["paragraphs"],
                "final_report_chars": len(v["final_report"]),
            }
            for k, v in result["agent_results"].items()
        },
        "host_speeches_count": len(result["host_speeches"]),
        "forum_entries_count": len(result["forum_log"].split("\n")),
    }
    summary_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  📊 summary  → {summary_path}")

    # ===== 调用 ReportAgent 生成最终综合报告 =====
    if not args.no_report and result["agent_results"]:
        from agno_agents import run_report_generation

        report = run_report_generation(
            query=args.query,
            agent_results=result["agent_results"],
            forum_log=result["forum_log"],
            host_speeches=result["host_speeches"],
        )

        final_md_path = out_dir / "final_report.md"
        final_md_path.write_text(report["markdown"], encoding="utf-8")
        print(f"  📕 final.md → {final_md_path}")

        final_html_path = out_dir / "final_report.html"
        final_html_path.write_text(report["html"], encoding="utf-8")
        print(f"  🌐 final.html → {final_html_path}")

        print(f"\n📕 综合报告标题：{report['title']}")
        print(f"   章节数：{report['stats']['chapter_count']}")
        print(f"   Markdown：{report['stats']['markdown_chars']} 字符")

    print(f"\n✅ 全部输出已保存至: {out_dir}")


if __name__ == "__main__":
    main()
