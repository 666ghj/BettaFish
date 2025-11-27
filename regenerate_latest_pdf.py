"""
使用新的SVG矢量图表功能重新生成最新报告的PDF
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from ReportEngine.renderers import PDFRenderer

def find_latest_report():
    """
    在 `final_reports/ir` 中查找最新的报告 IR JSON。

    按修改时间倒序选择第一条，若目录或文件缺失则记录错误并返回 None。

    返回:
        Path | None: 最新 IR 文件路径；未找到则为 None。
    """
    ir_dir = Path("final_reports/ir")

    if not ir_dir.exists():
        logger.error(f"报告目录不存在: {ir_dir}")
        return None

    # 获取所有JSON文件并按修改时间排序
    json_files = sorted(ir_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not json_files:
        logger.error("未找到报告文件")
        return None

    latest_file = json_files[0]
    logger.info(f"找到最新报告: {latest_file.name}")

    return latest_file

def load_document_ir(file_path):
    """
    读取指定路径的 Document IR JSON，并统计章节/图表数量。

    解析失败时返回 None；成功时会打印章节数与图表数，便于确认
    输入报告的规模。

    参数:
        file_path: IR 文件路径

    返回:
        dict | None: 解析后的 Document IR；失败返回 None。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        logger.info(f"成功加载报告: {file_path.name}")

        # 统计图表数量
        chart_count = 0
        chapters = document_ir.get('chapters', [])

        def count_charts(blocks):
            """递归统计 block 列表中的 Chart.js 图表数量"""
            count = 0
            for block in blocks:
                if isinstance(block, dict):
                    if block.get('type') == 'widget' and block.get('widgetType', '').startswith('chart.js'):
                        count += 1
                    # 递归处理嵌套blocks
                    nested = block.get('blocks')
                    if isinstance(nested, list):
                        count += count_charts(nested)
            return count

        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            chart_count += count_charts(blocks)

        logger.info(f"报告包含 {len(chapters)} 个章节，{chart_count} 个图表")

        return document_ir

    except Exception as e:
        logger.error(f"加载报告失败: {e}")
        return None

def generate_pdf_with_vector_charts(document_ir, output_path):
    """
    使用 PDFRenderer 将 Document IR 渲染为包含 SVG 矢量图表的 PDF。

    启用布局优化，生成后输出文件大小与成功提示；异常时返回 None。

    参数:
        document_ir: 完整的 Document IR
        output_path: 目标 PDF 路径

    返回:
        Path | None: 成功时返回生成的 PDF 路径，失败返回 None。
    """
    try:
        logger.info("=" * 60)
        logger.info("开始生成PDF（带矢量图表）")
        logger.info("=" * 60)

        # 创建PDF渲染器
        renderer = PDFRenderer()

        # 渲染PDF
        result_path = renderer.render_to_pdf(
            document_ir,
            output_path,
            optimize_layout=True
        )

        logger.info("=" * 60)
        logger.info(f"✓ PDF生成成功: {result_path}")
        logger.info("=" * 60)

        # 显示文件大小
        file_size = result_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        logger.info(f"文件大小: {size_mb:.2f} MB")

        return result_path

    except Exception as e:
        logger.error(f"生成PDF失败: {e}", exc_info=True)
        return None

def main():
    """
    主入口：重新生成最新报告的矢量 PDF。

    步骤：
        1) 查找最新 IR 文件；
        2) 读取并统计报告结构；
        3) 构造输出文件名并确保目录存在；
        4) 调用渲染函数生成 PDF，输出路径与特性说明。

    返回:
        int: 0 表示成功，非 0 表示失败。
    """
    logger.info("🚀 使用SVG矢量图表重新生成最新报告的PDF")
    logger.info("")

    # 1. 找到最新报告
    latest_report = find_latest_report()
    if not latest_report:
        logger.error("未找到报告文件")
        return 1

    # 2. 加载报告数据
    document_ir = load_document_ir(latest_report)
    if not document_ir:
        logger.error("加载报告失败")
        return 1

    # 3. 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_name = latest_report.stem.replace("report_ir_", "")
    output_filename = f"report_vector_{report_name}_{timestamp}.pdf"
    output_path = Path("final_reports/pdf") / output_filename

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"输出路径: {output_path}")
    logger.info("")

    # 4. 生成PDF
    result = generate_pdf_with_vector_charts(document_ir, output_path)

    if result:
        logger.info("")
        logger.info("🎉 PDF生成完成！")
        logger.info("")
        logger.info("特性说明:")
        logger.info("  ✓ 图表以SVG矢量格式渲染")
        logger.info("  ✓ 支持无限缩放不失真")
        logger.info("  ✓ 保留完整的图表视觉效果")
        logger.info("  ✓ 折线图、柱状图、饼图等均为矢量曲线")
        logger.info("")
        logger.info(f"PDF文件位置: {result.absolute()}")
        return 0
    else:
        logger.error("❌ PDF生成失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
