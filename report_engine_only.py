#!/usr/bin/env python
"""
Report Engine 命令行版本

这是一个不需要前端的命令行报告生成程序。
主要流程：
1. 检查PDF依赖
2. 获取最新的log、md文件
3. 直接调用Report Engine生成报告（跳过文件增加审核）
4. 自动保存HTML、PDF（如果有依赖）和Markdown到final_reports/（Markdown 会在 PDF 之后生成）

使用方法：
    python report_engine_only.py [选项]

选项：
    --query QUERY     指定报告主题（可选，默认从文件名提取）
    --skip-pdf        跳过PDF生成（即使有依赖）
    --skip-markdown   跳过Markdown生成
    --verbose         显示详细日志
    --help            显示帮助信息
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from loguru import logger

from common.provenance.identity import validate_engine_bundles
from common.provenance.io import load_sidecar
from common.provenance.models import ProvenanceBundle
from common.provenance.normalizer import merge_bundles

# 全局配置
VERBOSE = False

# 配置日志
def setup_logger(verbose: bool = False):
    """设置日志配置"""
    global VERBOSE
    VERBOSE = verbose

    logger.remove()  # 移除默认处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="DEBUG" if verbose else "INFO"
    )


def check_dependencies() -> tuple[bool, Optional[str]]:
    """
    检查PDF生成所需的系统依赖

    Returns:
        tuple: (is_available: bool, message: str)
            - is_available: PDF功能是否可用
            - message: 依赖检查结果消息
    """
    logger.info("=" * 70)
    logger.info("步骤 1/4: 检查系统依赖")
    logger.info("=" * 70)

    try:
        from ReportEngine.utils.dependency_check import check_pango_available
        is_available, message = check_pango_available()

        if is_available:
            logger.success("✓ PDF 依赖检测通过，将同时生成 HTML 和 PDF 文件")
        else:
            logger.warning("⚠ PDF 依赖缺失，仅生成 HTML 文件")
            logger.info("\n" + message)

        return is_available, message
    except Exception as e:
        logger.error(f"依赖检查失败: {e}")
        return False, str(e)


def get_latest_engine_reports() -> Dict[str, str]:
    """
    获取三个引擎目录中的最新报告文件

    Returns:
        Dict[str, str]: 引擎名称到文件路径的映射
    """
    logger.info("\n" + "=" * 70)
    logger.info("步骤 2/4: 获取最新的分析引擎报告")
    logger.info("=" * 70)

    # 定义三个引擎的目录
    directories = {
        'insight': 'insight_engine_streamlit_reports',
        'media': 'media_engine_streamlit_reports',
        'query': 'query_engine_streamlit_reports'
    }

    latest_files = {}

    for engine, directory in directories.items():
        if not os.path.exists(directory):
            logger.warning(f"⚠ {engine.capitalize()} Engine 目录不存在: {directory}")
            continue

        # 获取所有 .md 文件
        md_files = [f for f in os.listdir(directory) if f.endswith('.md')]

        if not md_files:
            logger.warning(f"⚠ {engine.capitalize()} Engine 目录中没有找到 .md 文件")
            continue

        # 获取最新文件
        latest_file = max(
            md_files,
            key=lambda x: os.path.getmtime(os.path.join(directory, x))
        )
        latest_path = os.path.join(directory, latest_file)
        latest_files[engine] = latest_path

        logger.info(f"✓ 找到 {engine.capitalize()} Engine 最新报告")

    if not latest_files:
        logger.error("❌ 未找到任何引擎报告文件，请先运行分析引擎生成报告")
        sys.exit(1)

    logger.info(f"\n共找到 {len(latest_files)} 个引擎的最新报告")

    return latest_files


def confirm_file_selection(latest_files: Dict[str, str]) -> bool:
    """
    向用户确认选择的文件是否正确

    Args:
        latest_files: 引擎名称到文件路径的映射

    Returns:
        bool: 用户确认则返回True，否则返回False
    """
    logger.info("\n" + "=" * 70)
    logger.info("请确认以下选择的文件：")
    logger.info("=" * 70)

    for engine, file_path in latest_files.items():
        filename = os.path.basename(file_path)
        # 获取文件修改时间
        mtime = os.path.getmtime(file_path)
        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"  {engine.capitalize()} Engine:")
        logger.info(f"    文件名: {filename}")
        logger.info(f"    路径: {file_path}")
        logger.info(f"    修改时间: {mtime_str}")
        logger.info("")

    logger.info("=" * 70)

    # 提示用户确认
    try:
        response = input("是否使用以上文件生成报告? [Y/n]: ").strip().lower()

        # 默认是y，所以空输入或y都表示确认
        if response == '' or response == 'y' or response == 'yes':
            logger.success("✓ 用户确认，继续生成报告")
            return True
        else:
            logger.warning("✗ 用户取消操作")
            return False
    except (KeyboardInterrupt, EOFError):
        logger.warning("\n✗ 用户取消操作")
        return False


def load_engine_reports(latest_files: Dict[str, str]) -> list[str]:
    """
    加载引擎报告内容

    Args:
        latest_files: 引擎名称到文件路径的映射

    Returns:
        list[str]: 报告内容列表
    """
    reports = []

    for engine in ('query', 'media', 'insight'):
        file_path = latest_files.get(engine)
        if not file_path:
            reports.append("")
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                reports.append(content)
                logger.debug(f"已加载 {engine} 报告，长度: {len(content)} 字符")
        except Exception as e:
            logger.error(f"加载 {engine} 报告失败: {e}")

    return reports


def load_provenance_bundle(
    latest_files: Dict[str, str],
    *,
    expected_query: Optional[str] = None,
) -> ProvenanceBundle:
    """Load one query-consistent set of audit sidecars for CLI replay.

    A filename is not a reliable query identity.  Every selected report must
    therefore have a sidecar with ``meta.query`` and all sidecars must agree
    before their evidence is merged.
    """
    bundles: Dict[str, ProvenanceBundle] = {}
    for engine in ('query', 'media', 'insight'):
        file_path = latest_files.get(engine)
        if not file_path:
            continue
        bundle = load_sidecar(file_path)
        bundles[engine] = bundle

    identity = validate_engine_bundles(
        bundles,
        expected_query=expected_query or "",
        require_query=True,
        require_consistent_run=True,
    )
    merged = merge_bundles(bundles.values())
    if identity["query"]:
        merged.meta["query"] = identity["query"]
        merged.meta["queries"] = [identity["query"]]
    if identity["run_id"]:
        merged.meta["run_id"] = identity["run_id"]
        merged.meta["run_ids"] = [identity["run_id"]]
    return merged


def extract_query_from_reports(latest_files: Dict[str, str]) -> str:
    """
    从报告文件名中提取查询主题

    Args:
        latest_files: 引擎名称到文件路径的映射

    Returns:
        str: 提取的查询主题
    """
    # 尝试从文件名中提取主题
    for engine, file_path in latest_files.items():
        filename = os.path.basename(file_path)
        # 假设文件名格式为: report_主题_时间戳.md
        if '_' in filename:
            parts = filename.replace('.md', '').split('_')
            if len(parts) >= 2:
                # 提取中间部分作为主题
                topic = '_'.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                if topic:
                    return topic

    # 如果无法提取，返回默认值
    return "综合分析报告"


def generate_report(
    reports: list[str],
    query: str,
    pdf_available: bool,
    provenance_bundle: Optional[ProvenanceBundle] = None,
) -> Dict[str, Any]:
    """
    调用Report Engine生成报告

    Args:
        reports: 报告内容列表
        query: 报告主题
        pdf_available: PDF功能是否可用

    Returns:
        Dict[str, Any]: 包含生成结果的字典
    """
    logger.info("\n" + "=" * 70)
    logger.info("步骤 3/4: 生成综合报告")
    logger.info("=" * 70)
    logger.info(f"报告主题: {query}")
    logger.info(f"输入报告数量: {len(reports)}")

    try:
        from ReportEngine.agent import ReportAgent

        # 初始化Report Agent
        logger.info("正在初始化 Report Engine...")
        agent = ReportAgent()

        # 定义流式事件处理器
        def stream_handler(event_type: str, payload: Dict[str, Any]):
            """处理Report Engine的流式事件"""
            if event_type == 'stage':
                stage = payload.get('stage', '')
                if stage == 'agent_start':
                    logger.info(f"开始生成报告: {payload.get('report_id', '')}")
                elif stage == 'template_selected':
                    logger.info(f"✓ 已选择模板: {payload.get('template', '')}")
                elif stage == 'template_sliced':
                    logger.info(f"✓ 模板解析完成，共 {payload.get('section_count', 0)} 个章节")
                elif stage == 'layout_designed':
                    logger.info(f"✓ 文档布局设计完成")
                    logger.info(f"  标题: {payload.get('title', '')}")
                elif stage == 'word_plan_ready':
                    logger.info(f"✓ 篇幅规划完成，目标章节数: {payload.get('chapter_targets', 0)}")
                elif stage == 'chapters_compiled':
                    logger.info(f"✓ 章节生成完成，共 {payload.get('chapter_count', 0)} 个章节")
                elif stage == 'html_rendered':
                    logger.info(f"✓ HTML 渲染完成")
                elif stage == 'report_saved':
                    logger.info(f"✓ 报告已保存")
            elif event_type == 'chapter_status':
                chapter_id = payload.get('chapterId', '')
                title = payload.get('title', '')
                status = payload.get('status', '')
                if status == 'generating':
                    logger.info(f"  正在生成章节: {title}")
                elif status == 'completed':
                    attempt = payload.get('attempt', 1)
                    warning = payload.get('warning', '')
                    if warning:
                        logger.warning(f"  ✓ 章节完成: {title} (第 {attempt} 次尝试，{payload.get('warningMessage', '')})")
                    else:
                        logger.success(f"  ✓ 章节完成: {title}")
            elif event_type == 'error':
                logger.error(f"错误: {payload.get('message', '')}")

        # 生成报告
        logger.info("开始生成报告，这可能需要几分钟时间...")
        result = agent.generate_report(
            query=query,
            reports=reports,
            forum_logs="",  # 不使用论坛日志
            custom_template="",  # 使用自动模板选择
            save_report=True,  # 自动保存报告
            stream_handler=stream_handler,
            provenance_bundle=provenance_bundle,
        )

        logger.success("✓ 报告生成成功！")
        return result

    except Exception as e:
        logger.exception(f"❌ 报告生成失败: {e}")
        sys.exit(1)


def save_pdf(document_ir_path: str, query: str) -> Optional[str]:
    """
    从IR文件生成并保存PDF

    Args:
        document_ir_path: Document IR文件路径
        query: 报告主题

    Returns:
        Optional[str]: PDF文件路径，如果失败则返回None
    """
    logger.info("\n正在生成 PDF 文件...")

    try:
        # 读取IR数据
        with open(document_ir_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        # 创建PDF渲染器
        from ReportEngine.renderers import PDFRenderer
        renderer = PDFRenderer()

        # 准备输出路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(
            c for c in query if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        query_safe = query_safe.replace(" ", "_")[:30] or "report"

        pdf_dir = Path("final_reports") / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)

        pdf_filename = f"final_report_{query_safe}_{timestamp}.pdf"
        pdf_path = pdf_dir / pdf_filename

        # 使用 render_to_pdf 方法直接生成PDF文件，传入 IR 文件路径用于修复后保存
        logger.info(f"开始渲染PDF: {pdf_path}")
        result_path = renderer.render_to_pdf(
            document_ir,
            pdf_path,
            optimize_layout=True,
            ir_file_path=document_ir_path
        )

        # 显示文件大小
        file_size = result_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        logger.success(f"✓ PDF 已保存: {pdf_path}")
        logger.info(f"  文件大小: {size_mb:.2f} MB")

        return str(result_path)

    except Exception as e:
        logger.exception(f"❌ PDF 生成失败: {e}")
        return None


def save_markdown(document_ir_path: str, query: str) -> Optional[str]:
    """
    从IR文件生成并保存Markdown

    Args:
        document_ir_path: Document IR文件路径
        query: 报告主题

    Returns:
        Optional[str]: Markdown文件路径，如果失败则返回None
    """
    logger.info("\n正在生成 Markdown 文件...")

    try:
        with open(document_ir_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        from ReportEngine.renderers import MarkdownRenderer
        renderer = MarkdownRenderer()
        # 传入 IR 文件路径用于修复后保存
        markdown_content = renderer.render(document_ir, ir_file_path=document_ir_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(
            c for c in query if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        query_safe = query_safe.replace(" ", "_")[:30] or "report"

        md_dir = Path("final_reports") / "md"
        md_dir.mkdir(parents=True, exist_ok=True)

        md_filename = f"final_report_{query_safe}_{timestamp}.md"
        md_path = md_dir / md_filename

        md_path.write_text(markdown_content, encoding='utf-8')

        file_size_kb = md_path.stat().st_size / 1024
        logger.success(f"✓ Markdown 已保存: {md_path}")
        logger.info(f"  文件大小: {file_size_kb:.1f} KB")

        return str(md_path)

    except Exception as e:
        logger.exception(f"❌ Markdown 生成失败: {e}")
        return None


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Report Engine 命令行版本 - 无需前端的报告生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python report_engine_only.py
  python report_engine_only.py --query "土木工程行业分析"
  python report_engine_only.py --skip-pdf --verbose

注意:
  程序会自动获取三个引擎目录中的最新报告文件，
  不进行文件增加审核，直接生成综合报告，并默认在PDF之后生成Markdown。
        """
    )

    parser.add_argument(
        '--query',
        type=str,
        default=None,
        help='指定报告主题（默认从文件名自动提取）'
    )

    parser.add_argument(
        '--skip-pdf',
        action='store_true',
        help='跳过PDF生成（即使系统支持）'
    )

    parser.add_argument(
        '--skip-markdown',
        action='store_true',
        help='跳过Markdown生成'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志信息'
    )

    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 设置日志
    setup_logger(verbose=args.verbose)

    logger.info("\n")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 20 + "Report Engine 命令行版本" + " " * 24 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("\n")

    # 步骤 1: 检查依赖
    pdf_available, _ = check_dependencies()
    markdown_enabled = not args.skip_markdown

    # 如果用户指定跳过PDF，则禁用PDF生成
    if args.skip_pdf:
        logger.info("用户指定 --skip-pdf，将跳过 PDF 生成")
        pdf_available = False

    if not markdown_enabled:
        logger.info("用户指定 --skip-markdown，将跳过 Markdown 生成")

    # 步骤 2: 获取最新文件
    latest_files = get_latest_engine_reports()

    # 确认文件选择
    if not confirm_file_selection(latest_files):
        logger.info("\n程序已退出")
        sys.exit(0)

    # 加载报告内容
    reports = load_engine_reports(latest_files)
    provenance_bundle = load_provenance_bundle(
        latest_files,
        expected_query=args.query,
    )

    if not reports:
        logger.error("❌ 未能加载任何报告内容")
        sys.exit(1)

    # 提取或使用指定的查询主题
    query = (
        str(args.query or "").strip()
        or str(provenance_bundle.meta.get("query") or "").strip()
        or extract_query_from_reports(latest_files)
    )
    logger.info(f"使用报告主题: {query}")

    # 步骤 3: 生成报告
    result = generate_report(reports, query, pdf_available, provenance_bundle)

    # 步骤 4: 保存文件
    logger.info("\n" + "=" * 70)
    logger.info("步骤 4/4: 保存生成的文件")
    logger.info("=" * 70)

    # HTML 已经在 generate_report 中自动保存
    html_path = result.get('report_filepath', '')
    ir_path = result.get('ir_filepath', '')
    pdf_path = None
    markdown_path = None

    if html_path:
        logger.success(f"✓ HTML 已保存: {result.get('report_relative_path', html_path)}")

    # 如果有PDF依赖，生成并保存PDF
    if pdf_available:
        if ir_path and os.path.exists(ir_path):
            pdf_path = save_pdf(ir_path, query)
        else:
            logger.warning("⚠ 未找到 IR 文件，无法生成 PDF")
    else:
        logger.info("⚠ 跳过 PDF 生成（缺少系统依赖或用户指定跳过）")

    # 生成并保存Markdown（在PDF之后）
    if markdown_enabled:
        if ir_path and os.path.exists(ir_path):
            markdown_path = save_markdown(ir_path, query)
        else:
            logger.warning("⚠ 未找到 IR 文件，无法生成 Markdown")
    else:
        logger.info("⚠ 跳过 Markdown 生成（用户指定）")

    # 总结
    logger.info("\n" + "=" * 70)
    logger.success("✓ 报告生成完成！")
    logger.info("=" * 70)
    logger.info(f"报告 ID: {result.get('report_id', 'N/A')}")
    logger.info(f"HTML 文件: {result.get('report_relative_path', 'N/A')}")
    if pdf_available:
        if pdf_path:
            logger.info(f"PDF 文件: {os.path.relpath(pdf_path, os.getcwd())}")
        else:
            logger.info("PDF 文件: 生成失败，请检查日志")
    else:
        logger.info("PDF 文件: 已跳过")
    if markdown_enabled:
        if markdown_path:
            logger.info(f"Markdown 文件: {os.path.relpath(markdown_path, os.getcwd())}")
        else:
            logger.info("Markdown 文件: 生成失败，请检查日志")
    else:
        logger.info("Markdown 文件: 已跳过")
    logger.info("=" * 70)
    logger.info("\n程序结束")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n\n用户中断程序")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"\n程序异常退出: {e}")
        sys.exit(1)
