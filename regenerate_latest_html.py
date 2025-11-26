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
    """定位包含 manifest.json 的最新章节输出目录。"""
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
    """读取manifest.json并返回report_id与metadata。"""
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
    """加载章节JSON列表。"""
    storage = ChapterStorage(settings.CHAPTER_OUTPUT_DIR)
    chapters = storage.load_chapters(run_dir)
    logger.info(f"加载章节数: {len(chapters)}")
    return chapters


def validate_chapters(chapters):
    """使用IRValidator做快速校验，仅记录警告不阻断流程。"""
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
    """将章节装订为整本Document IR。"""
    composer = DocumentComposer()
    document_ir = composer.build_document(report_id, metadata, chapters)
    logger.info(
        f"装订完成: {len(document_ir.get('chapters', []))} 个章节，"
        f"{count_charts(document_ir)} 个图表"
    )
    return document_ir


def count_charts(document_ir):
    """统计IR中的图表数量。"""
    chart_count = 0
    for chapter in document_ir.get("chapters", []):
        blocks = chapter.get("blocks", [])
        chart_count += _count_chart_blocks(blocks)
    return chart_count


def _count_chart_blocks(blocks):
    """递归统计chart.js组件。"""
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
    """将装订好的IR重新落盘，便于后续复用。"""
    output_dir = Path(settings.DOCUMENT_IR_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    ir_filename = f"report_ir_{base_name}_{timestamp}_regen.json"
    ir_path = output_dir / ir_filename
    ir_path.write_text(json.dumps(document_ir, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"IR已保存: {ir_path}")
    return ir_path


def render_html(document_ir, base_name, timestamp):
    """使用HTMLRenderer渲染并落盘HTML文件。"""
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
    """将主题/标题转换为安全的文件名片段。"""
    text = str(text or "report")
    sanitized = "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).strip()
    sanitized = sanitized.replace(" ", "_")
    return sanitized[:60] or "report"


def main():
    """主入口：装订最新章节并渲染HTML。"""
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
