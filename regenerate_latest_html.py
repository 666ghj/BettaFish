"""
使用最新的章节JSON重新装订并渲染HTML报告。
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from loguru import logger

# 确保可以找到项目内模块
sys.path.insert(0, str(Path(__file__).parent))

from ReportEngine.core import ChapterStorage, DocumentComposer
from ReportEngine.ir import IRValidator
from ReportEngine.renderers import HTMLRenderer
from ReportEngine.utils.config import settings


def find_latest_run_dir(chapter_root: Path):
    """
    定位章节根目录下最新一次运行的输出目录。

    扫描 `chapter_root` 下所有子目录，筛选出包含 `manifest.json`
    的候选，按修改时间倒序取最新一条。若目录不存在或没有有效
    manifest，会记录错误并返回 None。

    参数:
        chapter_root: 章节输出的根目录（通常是 settings.CHAPTER_OUTPUT_DIR）

    返回:
        Path | None: 最新的 run 目录路径；若未找到则为 None。
    """
    if not chapter_root.exists():
        logger.error(f"章节目录不存在: {chapter_root}")
        return None

    run_dirs = []
    for candidate in chapter_root.iterdir():
        if not candidate.is_dir():
            continue
        manifest_path = candidate / "manifest.json"
        if manifest_path.exists():
            run_dirs.append((candidate, manifest_path.stat().st_mtime))

    if not run_dirs:
        logger.error("未找到带 manifest.json 的章节目录")
        return None

    latest_dir = sorted(run_dirs, key=lambda item: item[1], reverse=True)[0][0]
    logger.info(f"找到最新run目录: {latest_dir.name}")
    return latest_dir


def load_manifest(run_dir: Path):
    """
    读取单次运行目录内的 manifest.json。

    成功时返回 reportId 以及元数据字典；读取或解析失败会记录错误
    并返回 (None, None)，以便上层提前终止流程。

    参数:
        run_dir: 包含 manifest.json 的章节输出目录

    返回:
        tuple[str | None, dict | None]: (report_id, metadata)
    """
    manifest_path = run_dir / "manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        report_id = manifest.get("reportId") or run_dir.name
        metadata = manifest.get("metadata") or {}
        logger.info(f"报告ID: {report_id}")
        if manifest.get("createdAt"):
            logger.info(f"创建时间: {manifest['createdAt']}")
        return report_id, metadata
    except Exception as exc:
        logger.error(f"读取manifest失败: {exc}")
        return None, None


def load_chapters(run_dir: Path):
    """
    读取指定 run 目录下的所有章节 JSON。

    会复用 ChapterStorage 的 load_chapters 能力，自动按 order 排序。
    读取后打印章节数量，便于确认完整性。

    参数:
        run_dir: 单次报告的章节目录

    返回:
        list[dict]: 章节 JSON 列表（若目录为空则为空列表）
    """
    storage = ChapterStorage(settings.CHAPTER_OUTPUT_DIR)
    chapters = storage.load_chapters(run_dir)
    logger.info(f"加载章节数: {len(chapters)}")
    return chapters


def validate_chapters(chapters):
    """
    使用 IRValidator 对章节结构做快速校验。

    仅记录未通过的章节及前三条错误，不会中断流程；目的是在
    重装订前发现潜在结构问题。

    参数:
        chapters: 章节 JSON 列表
    """
    validator = IRValidator()
    invalid = []
    for chapter in chapters:
        ok, errors = validator.validate_chapter(chapter)
        if not ok:
            invalid.append((chapter.get("chapterId") or "unknown", errors))

    if invalid:
        logger.warning(f"有 {len(invalid)} 个章节未通过结构校验，将继续装订：")
        for chapter_id, errors in invalid:
            preview = "; ".join(errors[:3])
            logger.warning(f"  - {chapter_id}: {preview}")
    else:
        logger.info("章节结构校验通过")


def stitch_document(report_id, metadata, chapters):
    """
    将各章节与元数据装订为完整的 Document IR。

    使用 DocumentComposer 统一处理章节顺序、全局元数据等，并打印
    装订完成的章节与图表数量。

    参数:
        report_id: 报告 ID（来自 manifest 或目录名）
        metadata: manifest 中的全局元数据
        chapters: 已加载的章节列表

    返回:
        dict: 完整的 Document IR 对象
    """
    composer = DocumentComposer()
    document_ir = composer.build_document(report_id, metadata, chapters)
    logger.info(
        f"装订完成: {len(document_ir.get('chapters', []))} 个章节，"
        f"{count_charts(document_ir)} 个图表"
    )
    return document_ir


def count_charts(document_ir):
    """
    统计整本 Document IR 中的 Chart.js 图表数量。

    会遍历每章的 blocks，递归查找 widget 类型中以 `chart.js`
    开头的组件，便于快速感知图表规模。

    参数:
        document_ir: 完整的 Document IR

    返回:
        int: 图表总数
    """
    chart_count = 0
    for chapter in document_ir.get("chapters", []):
        blocks = chapter.get("blocks", [])
        chart_count += _count_chart_blocks(blocks)
    return chart_count


def _count_chart_blocks(blocks):
    """
    递归统计 block 列表中的 Chart.js 组件数量。

    兼容嵌套的 blocks/list/table 结构，确保所有层级的图表都被计入。

    参数:
        blocks: 任意层级的 block 列表

    返回:
        int: 统计到的 chart.js 图表数量
    """
    count = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "widget" and str(block.get("widgetType", "")).startswith("chart.js"):
            count += 1
        nested = block.get("blocks")
        if isinstance(nested, list):
            count += _count_chart_blocks(nested)
        if block.get("type") == "list":
            for item in block.get("items", []):
                if isinstance(item, list):
                    count += _count_chart_blocks(item)
        if block.get("type") == "table":
            for row in block.get("rows", []):
                for cell in row.get("cells", []):
                    if isinstance(cell, dict):
                        cell_blocks = cell.get("blocks", [])
                        if isinstance(cell_blocks, list):
                            count += _count_chart_blocks(cell_blocks)
    return count


def save_document_ir(document_ir, base_name, timestamp):
    """
    将重新装订好的整本 Document IR 落盘。

    按 `report_ir_{slug}_{timestamp}_regen.json` 命名写入
    `settings.DOCUMENT_IR_OUTPUT_DIR`，确保目录存在并返回保存路径。

    参数:
        document_ir: 已装订完成的整本 IR
        base_name: 由主题/标题生成的安全文件名片段
        timestamp: 时间戳字符串，用于区分多次重生成

    返回:
        Path: 保存的 IR 文件路径
    """
    output_dir = Path(settings.DOCUMENT_IR_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    ir_filename = f"report_ir_{base_name}_{timestamp}_regen.json"
    ir_path = output_dir / ir_filename
    ir_path.write_text(json.dumps(document_ir, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"IR已保存: {ir_path}")
    return ir_path


def render_html(document_ir, base_name, timestamp):
    """
    使用 HTMLRenderer 将 Document IR 渲染为 HTML 并保存。

    渲染后落盘到 `final_reports/html`，打印图表验证统计信息，方便
    观察 Chart.js 数据的修复/失败情况。

    参数:
        document_ir: 装订完成的整本 IR
        base_name: 文件名片段（来源于报告主题/标题）
        timestamp: 时间戳字符串

    返回:
        Path: 生成的 HTML 文件路径
    """
    renderer = HTMLRenderer()
    html_content = renderer.render(document_ir)

    output_dir = Path(settings.OUTPUT_DIR) / "html"
    output_dir.mkdir(parents=True, exist_ok=True)
    html_filename = f"report_html_{base_name}_{timestamp}.html"
    html_path = output_dir / html_filename
    html_path.write_text(html_content, encoding="utf-8")

    file_size_mb = html_path.stat().st_size / (1024 * 1024)
    logger.info(f"HTML生成成功: {html_path} ({file_size_mb:.2f} MB)")
    logger.info(
        "图表验证统计: "
        f"total={renderer.chart_validation_stats.get('total', 0)}, "
        f"valid={renderer.chart_validation_stats.get('valid', 0)}, "
        f"repaired={renderer.chart_validation_stats.get('repaired_locally', 0) + renderer.chart_validation_stats.get('repaired_api', 0)}, "
        f"failed={renderer.chart_validation_stats.get('failed', 0)}"
    )
    return html_path


def build_slug(text):
    """
    将主题/标题转换为文件系统安全的片段。

    仅保留字母/数字/空格/下划线/连字符，空格统一为下划线，并限制
    最长 60 字符，避免过长文件名。

    参数:
        text: 原始主题或标题

    返回:
        str: 清洗后的安全字符串
    """
    text = str(text or "report")
    sanitized = "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).strip()
    sanitized = sanitized.replace(" ", "_")
    return sanitized[:60] or "report"


def main():
    """
    主入口：读取最新章节、装订 IR 并渲染 HTML。

    流程：
        1) 找到最新的章节 run 目录并读取 manifest；
        2) 加载章节并执行结构校验（仅警告）；
        3) 装订整本 IR，保存 IR 副本；
        4) 渲染 HTML 并输出路径与统计信息。

    返回:
        int: 0 表示成功，其余表示失败。
    """
    logger.info("🚀 使用最新的LLM章节重新装订并渲染HTML")

    chapter_root = Path(settings.CHAPTER_OUTPUT_DIR)
    latest_run = find_latest_run_dir(chapter_root)
    if not latest_run:
        return 1

    report_id, metadata = load_manifest(latest_run)
    if not report_id or metadata is None:
        return 1

    chapters = load_chapters(latest_run)
    if not chapters:
        logger.error("未找到章节JSON，无法装订")
        return 1

    validate_chapters(chapters)

    document_ir = stitch_document(report_id, metadata, chapters)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = build_slug(
        metadata.get("query") or metadata.get("title") or metadata.get("reportId") or report_id
    )

    ir_path = save_document_ir(document_ir, base_name, timestamp)
    html_path = render_html(document_ir, base_name, timestamp)

    logger.info("")
    logger.info("🎉 HTML装订与渲染完成")
    logger.info(f"IR文件: {ir_path.resolve()}")
    logger.info(f"HTML文件: {html_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
