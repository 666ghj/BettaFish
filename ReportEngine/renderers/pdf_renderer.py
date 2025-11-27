"""
PDF渲染器 - 使用WeasyPrint从HTML生成PDF
支持完整的CSS样式和中文字体
"""

from __future__ import annotations

import base64
import copy
import os
import sys
import io
import re
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from loguru import logger
from ReportEngine.utils.dependency_check import (
    prepare_pango_environment,
    check_pango_available,
)

try:
    from rich.console import Console
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# 在导入WeasyPrint之前，尝试补充常见的macOS Homebrew动态库路径，
# 避免因未设置DYLD_LIBRARY_PATH而找不到pango/cairo等依赖。
if sys.platform == 'darwin':
    mac_libs = [Path('/opt/homebrew/lib'), Path('/usr/local/lib')]
    current = os.environ.get('DYLD_LIBRARY_PATH', '')
    inserts = []
    for lib in mac_libs:
        if lib.exists() and str(lib) not in current.split(':'):
            inserts.append(str(lib))
    if inserts:
        os.environ['DYLD_LIBRARY_PATH'] = ":".join(inserts + ([current] if current else []))

# Windows: 自动补充常见 GTK/Pango 运行时路径，避免 DLL 加载失败
if sys.platform.startswith('win'):
    added = prepare_pango_environment()
    if added:
        logger.debug(f"已自动添加 GTK 运行时路径: {added}")

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
    PDF_DEP_STATUS = "OK"
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    # 判断错误类型以提供更友好的提示，并尝试输出缺失依赖的详细信息
    try:
        _, dep_message = check_pango_available()
    except Exception:
        dep_message = None

    if isinstance(e, OSError):
        msg = dep_message or (
            "PDF 导出依赖缺失（系统库未安装或环境变量未设置），"
            "PDF 导出功能将不可用。其他功能不受影响。"
        )
        # 使用 rich 显示警告（如果可用）
        if RICH_AVAILABLE and dep_message:
            console = Console()
            panel = Panel(
                dep_message,
                title="[bold yellow]PDF 导出依赖缺失[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
            console.print(panel)
        else:
            logger.warning(msg)
        PDF_DEP_STATUS = msg
    else:
        msg = dep_message or "WeasyPrint未安装，PDF导出功能将不可用"
        if RICH_AVAILABLE and dep_message:
            console = Console()
            panel = Panel(
                dep_message,
                title="[bold yellow]WeasyPrint 未安装[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
            console.print(panel)
        else:
            logger.warning(msg)
        PDF_DEP_STATUS = msg
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    PDF_DEP_STATUS = f"WeasyPrint 加载失败: {e}，PDF导出功能将不可用"
    logger.warning(PDF_DEP_STATUS)

from .html_renderer import HTMLRenderer
from .pdf_layout_optimizer import PDFLayoutOptimizer, PDFLayoutConfig
from .chart_to_svg import create_chart_converter
from .math_to_svg import MathToSVG
try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False
    logger = logger  # ensure logger exists even before declaration


class PDFRenderer:
    """
    基于WeasyPrint的PDF渲染器

    - 直接从HTML生成PDF，保留所有CSS样式
    - 完美支持中文字体
    - 自动处理分页和布局
    """

    def __init__(
        self,
        config: Dict[str, Any] | None = None,
        layout_optimizer: PDFLayoutOptimizer | None = None
    ):
        """
        初始化PDF渲染器

        参数:
            config: 渲染器配置
            layout_optimizer: PDF布局优化器（可选）
        """
        self.config = config or {}
        self.html_renderer = HTMLRenderer(config)
        self.layout_optimizer = layout_optimizer or PDFLayoutOptimizer()

        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError(
                PDF_DEP_STATUS
                if 'PDF_DEP_STATUS' in globals() else
                "WeasyPrint未安装，请运行: pip install weasyprint"
            )

        # 初始化图表转换器
        try:
            font_path = self._get_font_path()
            self.chart_converter = create_chart_converter(font_path=str(font_path))
            logger.info("图表SVG转换器初始化成功")
        except Exception as e:
            logger.warning(f"图表SVG转换器初始化失败: {e}，将使用表格降级")

        # 初始化数学公式转换器
        try:
            self.math_converter = MathToSVG(font_size=16, color='black')
            logger.info("数学公式SVG转换器初始化成功")
        except Exception as e:
            logger.warning(f"数学公式SVG转换器初始化失败: {e}，公式将显示为文本")
            self.math_converter = None

    @staticmethod
    def _get_font_path() -> Path:
        """获取字体文件路径"""
        # 优先使用完整字体以确保字符覆盖
        fonts_dir = Path(__file__).parent / "assets" / "fonts"

        # 检查完整字体
        full_font = fonts_dir / "SourceHanSerifSC-Medium.otf"
        if full_font.exists():
            logger.info(f"使用完整字体: {full_font}")
            return full_font

        # 检查TTF子集字体
        subset_ttf = fonts_dir / "SourceHanSerifSC-Medium-Subset.ttf"
        if subset_ttf.exists():
            logger.info(f"使用TTF子集字体: {subset_ttf}")
            return subset_ttf

        # 检查OTF子集字体
        subset_otf = fonts_dir / "SourceHanSerifSC-Medium-Subset.otf"
        if subset_otf.exists():
            logger.info(f"使用OTF子集字体: {subset_otf}")
            return subset_otf

        raise FileNotFoundError(f"未找到字体文件，请检查 {fonts_dir} 目录")

    def _preprocess_charts(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        预处理图表：验证和修复所有图表数据

        这个方法确保在转换为SVG之前，所有图表数据都是有效的。
        使用与HTMLRenderer相同的验证和修复逻辑，保证PDF和HTML的一致性。

        参数:
            document_ir: Document IR数据

        返回:
            Dict[str, Any]: 修复后的Document IR（深拷贝）
        """
        # 深拷贝以避免修改原始IR
        ir_copy = copy.deepcopy(document_ir)

        repair_stats = {
            'total': 0,
            'repaired': 0,
            'failed': 0
        }

        def repair_widgets_in_blocks(blocks: list, chapter_context: Dict[str, Any] | None = None) -> None:
            """递归修复blocks中的所有widget"""
            for block in blocks:
                if not isinstance(block, dict):
                    continue

                # 处理widget类型
                if block.get('type') == 'widget':
                    # 先用HTML渲染器的容错逻辑补全字段
                    try:
                        self.html_renderer._normalize_chart_block(block, chapter_context)
                    except Exception as exc:  # 防御性处理，避免单个图表阻断流程
                        logger.debug(f"预处理图表 {block.get('widgetId')} 时出错: {exc}")

                    widget_type = block.get('widgetType', '')
                    if widget_type.startswith('chart.js'):
                        repair_stats['total'] += 1

                        # 使用HTMLRenderer的验证器和修复器
                        validation = self.html_renderer.chart_validator.validate(block)

                        if not validation.is_valid:
                            logger.debug(f"图表 {block.get('widgetId')} 需要修复: {validation.errors}")

                            # 尝试修复
                            repair_result = self.html_renderer.chart_repairer.repair(block, validation)

                            if repair_result.success and repair_result.repaired_block:
                                # 更新block内容（在副本中）
                                block.update(repair_result.repaired_block)
                                repair_stats['repaired'] += 1
                                logger.debug(
                                    f"图表 {block.get('widgetId')} 已修复 "
                                    f"(方法: {repair_result.method})"
                                )
                            else:
                                repair_stats['failed'] += 1
                                reason = self.html_renderer._format_chart_error_reason(validation)
                                block["_chart_renderable"] = False
                                block["_chart_error_reason"] = reason
                                self.html_renderer._note_chart_failure(
                                    self.html_renderer._chart_cache_key(block),
                                    reason
                                )
                                logger.warning(
                                    f"图表 {block.get('widgetId')} 修复失败，将使用占位提示: {reason}"
                                )

                # 递归处理嵌套的blocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                repair_widgets_in_blocks(nested_blocks, chapter_context)

                # 处理列表项
            if block.get('type') == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        repair_widgets_in_blocks(item, chapter_context)

                # 处理表格单元格
            if block.get('type') == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            repair_widgets_in_blocks(cell_blocks, chapter_context)

        # 处理所有章节
        chapters = ir_copy.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            repair_widgets_in_blocks(blocks, chapter)

        # 输出统计信息
        if repair_stats['total'] > 0:
            logger.info(
                f"PDF图表预处理完成: "
                f"总计 {repair_stats['total']} 个图表, "
                f"修复 {repair_stats['repaired']} 个, "
                f"失败 {repair_stats['failed']} 个"
            )

        return ir_copy

    def _convert_charts_to_svg(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        将document_ir中的所有图表转换为SVG

        参数:
            document_ir: Document IR数据

        返回:
            Dict[str, str]: widgetId到SVG字符串的映射
        """
        svg_map = {}

        if not hasattr(self, 'chart_converter') or not self.chart_converter:
            logger.warning("图表转换器未初始化，跳过图表转换")
            return svg_map

        # 遍历所有章节
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_and_convert_widgets(blocks, svg_map)

        logger.info(f"成功转换 {len(svg_map)} 个图表为SVG")
        return svg_map

    def _convert_wordclouds_to_images(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        将document_ir中的词云widget转换为PNG并返回data URI映射
        """
        img_map: Dict[str, str] = {}

        if not WORDCLOUD_AVAILABLE:
            logger.debug("wordcloud库未安装，词云将使用表格兜底")
            return img_map

        # 遍历所有章节
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_wordcloud_widgets(blocks, img_map)

        if img_map:
            logger.info(f"成功转换 {len(img_map)} 个词云为图片")
        return img_map

    def _extract_and_convert_widgets(
        self,
        blocks: list,
        svg_map: Dict[str, str]
    ) -> None:
        """
        递归遍历blocks，找到所有widget并转换为SVG

        参数:
            blocks: block列表
            svg_map: 用于存储转换结果的字典
        """
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')

            # 处理widget类型
            if block_type == 'widget':
                widget_id = block.get('widgetId')
                widget_type = block.get('widgetType', '')

                # 只处理chart.js类型的widget
                if widget_id and widget_type.startswith('chart.js'):
                    widget_type_lower = widget_type.lower()
                    props = block.get('props')
                    props_type = str(props.get('type') or '').lower() if isinstance(props, dict) else ''
                    if 'wordcloud' in widget_type_lower or 'wordcloud' in props_type:
                        logger.debug(f"检测到词云 {widget_id}，跳过SVG转换并使用图片注入流程")
                        continue

                    failed, fail_reason = self.html_renderer._has_chart_failure(block)
                    if block.get("_chart_renderable") is False or failed:
                        logger.debug(
                            f"跳过转换失败的图表 {widget_id}"
                            f"{f'，原因: {fail_reason}' if fail_reason else ''}"
                        )
                        continue
                    try:
                        svg_content = self.chart_converter.convert_widget_to_svg(
                            block,
                            width=800,
                            height=500,
                            dpi=100
                        )
                        if svg_content:
                            svg_map[widget_id] = svg_content
                            logger.debug(f"图表 {widget_id} 转换为SVG成功")
                        else:
                            logger.warning(f"图表 {widget_id} 转换为SVG失败")
                    except Exception as e:
                        logger.error(f"转换图表 {widget_id} 时出错: {e}")

            # 递归处理嵌套的blocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_and_convert_widgets(nested_blocks, svg_map)

            # 处理列表项
            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_and_convert_widgets(item, svg_map)

            # 处理表格单元格
            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_and_convert_widgets(cell_blocks, svg_map)

    def _extract_wordcloud_widgets(
        self,
        blocks: list,
        img_map: Dict[str, str]
    ) -> None:
        """
        递归遍历blocks，找到词云widget并生成图片
        """
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')
            if block_type == 'widget':
                widget_id = block.get('widgetId')
                widget_type = block.get('widgetType', '')

                props = block.get('props')
                props_type = str(props.get('type') or '') if isinstance(props, dict) else ''
                is_wordcloud = (
                    isinstance(widget_type, str) and 'wordcloud' in widget_type.lower()
                ) or ('wordcloud' in props_type.lower())

                if widget_id and is_wordcloud:
                    try:
                        data_uri = self._generate_wordcloud_image(block)
                        if data_uri:
                            img_map[widget_id] = data_uri
                            logger.debug(f"词云 {widget_id} 转换为图片成功")
                    except Exception as exc:
                        logger.warning(f"生成词云图片失败 {widget_id}: {exc}")

            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_wordcloud_widgets(nested_blocks, img_map)

            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_wordcloud_widgets(item, img_map)

            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_wordcloud_widgets(cell_blocks, img_map)

    def _normalize_wordcloud_items(self, block: Dict[str, Any]) -> list:
        """
        从widget block中提取词云数据
        """
        props = block.get('props') or {}
        raw_items = props.get('data')
        if not isinstance(raw_items, list):
            return []
        normalized = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            word = item.get('word') or item.get('text') or item.get('label')
            if not word:
                continue
            weight = item.get('weight')
            try:
                weight_val = float(weight)
                if weight_val <= 0:
                    weight_val = 1.0
            except (TypeError, ValueError):
                weight_val = 1.0
            category = (item.get('category') or '').lower()
            normalized.append({'word': str(word), 'weight': weight_val, 'category': category})
        return normalized

    def _generate_wordcloud_image(self, block: Dict[str, Any]) -> str | None:
        """
        生成词云PNG并返回data URI
        """
        items = self._normalize_wordcloud_items(block)
        if not items:
            return None

        # 使用频次形式馈入wordcloud库
        frequencies = {}
        for item in items:
            weight = item['weight']
            # 兼容权重为0-1的小数，放大以体现差异
            freq = weight * 100 if 0 < weight <= 1.5 else weight
            frequencies[item['word']] = max(1, freq)

        font_path = str(self._get_font_path())
        wc = WordCloud(
            width=1000,
            height=360,
            background_color="white",
            font_path=font_path,
            prefer_horizontal=0.98,
            random_state=42,
            max_words=180,
            collocations=False,
        )
        wc.generate_from_frequencies(frequencies)

        buffer = io.BytesIO()
        wc.to_image().save(buffer, format='PNG')
        encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    def _convert_math_to_svg(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        将document_ir中的所有数学公式转换为SVG

        参数:
            document_ir: Document IR数据

        返回:
            Dict[str, str]: 公式块ID到SVG字符串的映射
        """
        svg_map = {}

        if not hasattr(self, 'math_converter') or not self.math_converter:
            logger.warning("数学公式转换器未初始化，跳过公式转换")
            return svg_map

        # 遍历所有章节，保持全局计数器避免ID重复
        block_counter = [0]
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_and_convert_math_blocks(blocks, svg_map, block_counter)

        logger.info(f"成功转换 {len(svg_map)} 个数学公式为SVG")
        return svg_map

    def _extract_and_convert_math_blocks(
        self,
        blocks: list,
        svg_map: Dict[str, str],
        block_counter: list = None
    ) -> None:
        """
        递归遍历blocks，找到所有math块并转换为SVG

        参数:
            blocks: block列表
            svg_map: 用于存储转换结果的字典
            block_counter: 用于生成唯一ID的计数器
        """
        if block_counter is None:
            block_counter = [0]

        def _extract_inline_math_from_inlines(inlines: list):
            """从段落内联节点中提取数学公式"""
            if not isinstance(inlines, list):
                return
            for run in inlines:
                if not isinstance(run, dict):
                    continue
                marks = run.get('marks') or []
                math_mark = next((m for m in marks if m.get('type') == 'math'), None)

                if math_mark:
                    # 仅单个math mark
                    raw = math_mark.get('value') or run.get('text') or ''
                    latex = self._normalize_latex(raw)
                    # 行内mark统一按inline处理，避免误将行内公式当成display
                    is_display = False
                    if not latex:
                        continue
                    block_counter[0] += 1
                    math_id = run.get('mathId') or f"math-inline-{block_counter[0]}"
                    run['mathId'] = math_id
                    try:
                        svg_content = (
                            self.math_converter.convert_display_to_svg(latex)
                            if is_display else
                            self.math_converter.convert_inline_to_svg(latex)
                        )
                        if svg_content:
                            svg_map[math_id] = svg_content
                            logger.debug(f"公式 {math_id} 转换为SVG成功")
                        else:
                            logger.warning(f"公式 {math_id} 转换为SVG失败: {latex[:50]}...")
                    except Exception as exc:
                        logger.error(f"转换内联公式 {latex[:50]}... 时出错: {exc}")
                    continue

                # 无math mark，尝试解析文本中的多个公式
                text_val = run.get('text')
                if not isinstance(text_val, str):
                    continue
                segments = self._find_all_math_in_text(text_val)
                if not segments:
                    continue
                ids_for_html: list[str] = []
                for idx, (latex, is_display) in enumerate(segments, start=1):
                    if not latex:
                        continue
                    block_counter[0] += 1
                    math_id = f"auto-math-{block_counter[0]}"
                    ids_for_html.append(math_id)
                    try:
                        svg_content = (
                            self.math_converter.convert_display_to_svg(latex)
                            if is_display else
                            self.math_converter.convert_inline_to_svg(latex)
                        )
                        if svg_content:
                            svg_map[math_id] = svg_content
                            logger.debug(f"公式 {math_id} 转换为SVG成功")
                        else:
                            logger.warning(f"公式 {math_id} 转换为SVG失败: {latex[:50]}...")
                    except Exception as exc:
                        logger.error(f"转换内联公式 {latex[:50]}... 时出错: {exc}")
                if ids_for_html:
                    # 将ID列表写回run，便于HTML渲染时使用相同ID（顺序对应segments）
                    run['mathIds'] = ids_for_html

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')

            # 处理math类型
            if block_type == 'math':
                latex = self._normalize_latex(block.get('latex', ''))
                if latex:
                    block_counter[0] += 1
                    math_id = f"math-block-{block_counter[0]}"
                    try:
                        svg_content = self.math_converter.convert_display_to_svg(latex)
                        if svg_content:
                            svg_map[math_id] = svg_content
                            # 将ID添加到block中，以便后续注入时识别
                            block['mathId'] = math_id
                            logger.debug(f"公式 {math_id} 转换为SVG成功")
                        else:
                            logger.warning(f"公式 {math_id} 转换为SVG失败: {latex[:50]}...")
                    except Exception as e:
                        logger.error(f"转换公式 {latex[:50]}... 时出错: {e}")
            else:
                # 提取段落、表格等内部的内联公式
                inlines = block.get('inlines')
                if inlines:
                    _extract_inline_math_from_inlines(inlines)

            # 递归处理嵌套的blocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_and_convert_math_blocks(nested_blocks, svg_map, block_counter)

            # 处理列表项
            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_and_convert_math_blocks(item, svg_map, block_counter)

            # 处理表格单元格
            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_and_convert_math_blocks(cell_blocks, svg_map, block_counter)

            # 处理callout内部的blocks
            if block_type == 'callout':
                callout_blocks = block.get('blocks', [])
                if isinstance(callout_blocks, list):
                    self._extract_and_convert_math_blocks(callout_blocks, svg_map, block_counter)

    def _inject_svg_into_html(self, html: str, svg_map: Dict[str, str]) -> str:
        """
        将SVG内容直接注入到HTML中（不使用JavaScript）

        参数:
            html: 原始HTML内容
            svg_map: widgetId到SVG内容的映射

        返回:
            str: 注入SVG后的HTML
        """
        if not svg_map:
            return html

        import re

        # 为每个widgetId查找对应的canvas并替换为SVG
        for widget_id, svg_content in svg_map.items():
            # 清理SVG内容（移除XML声明，因为SVG将嵌入HTML）
            svg_content = re.sub(r'<\?xml[^>]+\?>', '', svg_content)
            svg_content = re.sub(r'<!DOCTYPE[^>]+>', '', svg_content)
            svg_content = svg_content.strip()

            # 创建SVG容器HTML
            svg_html = f'<div class="chart-svg-container">{svg_content}</div>'

            # 查找包含此widgetId的配置脚本（限制在同一个</script>内，避免跨标签误配）
            config_pattern = rf'<script[^>]+id="([^"]+)"[^>]*>(?:(?!</script>).)*?"widgetId"\s*:\s*"{re.escape(widget_id)}"(?:(?!</script>).)*?</script>'
            match = re.search(config_pattern, html, re.DOTALL)

            if match:
                config_id = match.group(1)

                # 查找对应的canvas元素
                # 格式: <canvas id="chart-N" data-config-id="chart-config-N"></canvas>
                canvas_pattern = rf'<canvas[^>]+data-config-id="{re.escape(config_id)}"[^>]*></canvas>'

                # 【修复】替换canvas为SVG，使用lambda避免反斜杠转义问题
                html, replaced = re.subn(canvas_pattern, lambda m: svg_html, html, count=1)
                if replaced:
                    logger.debug(f"已替换图表 {widget_id} 的canvas为SVG")
                else:
                    logger.warning(f"未找到图表 {widget_id} 的canvas进行替换")

                # 将对应fallback标记为隐藏，避免PDF中出现重复表格
                fallback_pattern = rf'<div class="chart-fallback"([^>]*data-widget-id="{re.escape(widget_id)}"[^>]*)>'

                def _hide_fallback(m: re.Match) -> str:
                    """为匹配到的图表fallback添加隐藏类，防止PDF中重复渲染"""
                    tag = m.group(0)
                    if 'svg-hidden' in tag:
                        return tag
                    return tag.replace('chart-fallback"', 'chart-fallback svg-hidden"', 1)

                html = re.sub(fallback_pattern, _hide_fallback, html, count=1)
            else:
                logger.warning(f"未找到图表 {widget_id} 对应的配置脚本")

        return html

    @staticmethod
    def _normalize_latex(raw: Any) -> str:
        """去除外层数学定界符，兼容 $...$、$$...$$、\\(\\)、\\[\\] 等格式"""
        if not isinstance(raw, str):
            return ""
        latex = raw.strip()
        patterns = [
            r'^\$\$(.*)\$\$$',
            r'^\$(.*)\$$',
            r'^\\\[(.*)\\\]$',
            r'^\\\((.*)\\\)$',
        ]
        for pat in patterns:
            m = re.match(pat, latex, re.DOTALL)
            if m:
                latex = m.group(1).strip()
                break
        # 清理控制字符、防止mathtext解析失败
        latex = re.sub(r'[\x00-\x1f\x7f]', '', latex)
        # 常见兼容：\tfrac/\dfrac -> \frac
        latex = latex.replace(r'\tfrac', r'\frac').replace(r'\dfrac', r'\frac')
        return latex

    @staticmethod
    def _find_first_math_in_text(text: Any) -> tuple[str, bool] | None:
        """从纯文本中提取首个数学片段，返回(内容, 是否display)"""
        if not isinstance(text, str):
            return None
        pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]', re.S)
        matches = list(pattern.finditer(text))
        if not matches:
            return None
        m = matches[0]
        raw = next(g for g in m.groups() if g is not None)
        latex = raw.strip()
        is_display_raw = bool(m.group(1) or m.group(4))  # $$ or \[ \]
        is_standalone = (
            len(matches) == 1 and
            not text[:m.start()].strip() and
            not text[m.end():].strip()
        )
        return latex, bool(is_display_raw and is_standalone)

    @staticmethod
    def _find_all_math_in_text(text: Any) -> list[tuple[str, bool]]:
        """从纯文本中提取所有数学片段，返回[(内容, 是否display)]"""
        if not isinstance(text, str):
            return []
        pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]', re.S)
        results = []
        matches = list(pattern.finditer(text))
        if not matches:
            return results
        total = len(matches)

        for m in matches:
            raw = next(g for g in m.groups() if g is not None)
            latex = raw.strip()
            is_display_raw = bool(m.group(1) or m.group(4))
            is_standalone = (
                total == 1 and
                not text[:m.start()].strip() and
                not text[m.end():].strip()
            )
            is_display = is_display_raw and is_standalone
            results.append((latex, is_display))
        return results

    def _inject_wordcloud_images(self, html: str, img_map: Dict[str, str]) -> str:
        """
        将词云PNG data URI注入HTML，替换对应canvas
        """
        if not img_map:
            return html

        import re

        for widget_id, data_uri in img_map.items():
            img_html = (
                f'<div class="chart-svg-container wordcloud-img">'
                f'<img src="{data_uri}" alt="词云" />'
                f'</div>'
            )

            config_pattern = rf'<script[^>]+id="([^"]+)"[^>]*>(?:(?!</script>).)*?"widgetId"\s*:\s*"{re.escape(widget_id)}"(?:(?!</script>).)*?</script>'
            match = re.search(config_pattern, html, re.DOTALL)
            if not match:
                logger.debug(f"未找到词云 {widget_id} 的配置脚本，跳过注入")
                continue

            config_id = match.group(1)
            canvas_pattern = rf'<canvas[^>]+data-config-id="{re.escape(config_id)}"[^>]*></canvas>'

            html, replaced = re.subn(canvas_pattern, lambda m: img_html, html, count=1)
            if replaced:
                logger.debug(f"已替换词云 {widget_id} 的canvas为PNG图片")
            else:
                logger.warning(f"未找到词云 {widget_id} 的canvas进行替换")

            fallback_pattern = rf'<div class="chart-fallback"([^>]*data-widget-id="{re.escape(widget_id)}"[^>]*)>'

            def _hide_fallback(m: re.Match) -> str:
                """匹配词云表格兜底并打上隐藏标记，避免SVG/图片重复显示"""
                tag = m.group(0)
                if 'svg-hidden' in tag:
                    return tag
                return tag.replace('chart-fallback"', 'chart-fallback svg-hidden"', 1)

            html = re.sub(fallback_pattern, _hide_fallback, html, count=1)

        return html

    def _inject_math_svg_into_html(self, html: str, svg_map: Dict[str, str]) -> str:
        """
        将数学公式SVG内容注入到HTML中

        参数:
            html: 原始HTML内容
            svg_map: 公式ID到SVG内容的映射

        返回:
            str: 注入SVG后的HTML
        """
        if not svg_map:
            return html

        import re

        # 优先替换内联公式，再替换块级公式，保持顺序一致
        for math_id, svg_content in svg_map.items():
            # 清理SVG内容（移除XML声明，因为SVG将嵌入HTML）
            svg_content = re.sub(r'<\?xml[^>]+\?>', '', svg_content)
            svg_content = re.sub(r'<!DOCTYPE[^>]+>', '', svg_content)
            svg_content = svg_content.strip()

            svg_block_html = f'<div class="math-svg-container">{svg_content}</div>'
            svg_inline_html = f'<span class="math-svg-inline">{svg_content}</span>'

            replaced = False
            # 优先按 data-math-id 精确替换
            inline_pattern = rf'<span class="math-inline"[^>]*data-math-id="{re.escape(math_id)}"[^>]*>.*?</span>'
            if re.search(inline_pattern, html, re.DOTALL):
                html = re.sub(inline_pattern, lambda m: svg_inline_html, html, count=1)
                replaced = True
            else:
                block_pattern = rf'<div class="math-block"[^>]*data-math-id="{re.escape(math_id)}"[^>]*>.*?</div>'
                if re.search(block_pattern, html, re.DOTALL):
                    html = re.sub(block_pattern, lambda m: svg_block_html, html, count=1)
                    replaced = True

            # 如果没有找到特定ID，按出现顺序兜底替换
            if not replaced:
                html, sub_inline = re.subn(r'<span class="math-inline">[^<]*</span>', lambda m: svg_inline_html, html, count=1)
                if sub_inline:
                    replaced = True
                else:
                    html, sub_block = re.subn(r'<div class="math-block">\$\$[^$]*\$\$</div>', lambda m: svg_block_html, html, count=1)
                    if sub_block:
                        replaced = True

            if replaced:
                logger.debug(f"已替换公式 {math_id} 为SVG")

        return html

    def _get_pdf_html(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True
    ) -> str:
        """
        生成适用于PDF的HTML内容

        - 移除交互式元素（按钮、导航等）
        - 添加PDF专用样式
        - 嵌入字体文件
        - 应用布局优化
        - 将图表转换为SVG矢量图形

        参数:
            document_ir: Document IR数据
            optimize_layout: 是否启用布局优化

        返回:
            str: 优化后的HTML内容
        """
        # 如果启用布局优化，先分析文档并生成优化配置
        if optimize_layout:
            logger.info("启用PDF布局优化...")
            layout_config = self.layout_optimizer.optimize_for_document(document_ir)

            # 保存优化日志
            log_dir = Path('logs/pdf_layouts')
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            # 保存配置和优化日志
            optimization_log = self.layout_optimizer._log_optimization(
                self.layout_optimizer._analyze_document(document_ir),
                layout_config
            )
            self.layout_optimizer.config = layout_config
            self.layout_optimizer.save_config(log_file, optimization_log)
        else:
            layout_config = self.layout_optimizer.config

        # 关键修复：先预处理图表，确保数据有效
        logger.info("预处理图表数据...")
        preprocessed_ir = self._preprocess_charts(document_ir)

        # 转换图表为SVG（使用预处理后的IR）
        logger.info("开始转换图表为SVG矢量图形...")
        svg_map = self._convert_charts_to_svg(preprocessed_ir)

        # 转换词云为PNG
        logger.info("开始转换词云为图片...")
        wordcloud_map = self._convert_wordclouds_to_images(preprocessed_ir)

        # 转换数学公式为SVG
        logger.info("开始转换数学公式为SVG矢量图形...")
        math_svg_map = self._convert_math_to_svg(preprocessed_ir)

        # 使用HTML渲染器生成基础HTML（使用预处理后的IR，以便复用mathId等标记）
        html = self.html_renderer.render(preprocessed_ir)

        # 注入图表SVG
        if svg_map:
            html = self._inject_svg_into_html(html, svg_map)
            logger.info(f"已注入 {len(svg_map)} 个SVG图表")

        if wordcloud_map:
            html = self._inject_wordcloud_images(html, wordcloud_map)
            logger.info(f"已注入 {len(wordcloud_map)} 个词云图片")

        # 注入数学公式SVG
        if math_svg_map:
            html = self._inject_math_svg_into_html(html, math_svg_map)
            logger.info(f"已注入 {len(math_svg_map)} 个SVG公式")

        # 获取字体路径并转换为base64（用于嵌入）
        font_path = self._get_font_path()
        font_data = font_path.read_bytes()
        font_base64 = base64.b64encode(font_data).decode('ascii')

        # 判断字体格式
        font_format = 'opentype' if font_path.suffix == '.otf' else 'truetype'

        # 生成优化后的CSS
        optimized_css = self.layout_optimizer.generate_pdf_css()

        # 添加PDF专用CSS
        pdf_css = f"""
<style>
/* PDF专用字体嵌入 */
@font-face {{
    font-family: 'SourceHanSerif';
    src: url(data:font/{font_format};base64,{font_base64}) format('{font_format}');
    font-weight: normal;
    font-style: normal;
}}

/* 强制所有文本使用思源宋体 */
body, h1, h2, h3, h4, h5, h6, p, li, td, th, div, span {{
    font-family: 'SourceHanSerif', serif !important;
}}

/* PDF专用样式调整 */
.report-header {{
    display: none !important;
}}

.no-print {{
    display: none !important;
}}

body {{
    background: white !important;
}}

/* SVG图表容器样式 */
.chart-svg-container {{
    width: 100%;
    height: auto;
    display: flex;
    justify-content: center;
    align-items: center;
}}

.chart-svg-container svg {{
    max-width: 100%;
    height: auto;
}}
.chart-svg-container img {{
    max-width: 100%;
    height: auto;
}}

/* 数学公式SVG容器样式 */
.math-svg-container {{
    width: 100%;
    height: auto;
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 20px 0;
}}

.math-svg-container svg {{
    max-width: 100%;
    height: auto;
}}

/* 隐藏原始的math-block（因为已被SVG替换） */
.math-block {{
    display: none !important;
}}

/* 当对应SVG成功注入时隐藏fallback表格，失败时继续显示兜底数据 */
.chart-fallback.svg-hidden {{
    display: none !important;
}}

/* 确保chart-container显示（用于放置SVG） */
.chart-container {{
    display: block !important;
    min-height: 400px;
}}

{optimized_css}
</style>
"""

        # 在</head>前插入PDF专用CSS
        html = html.replace('</head>', f'{pdf_css}\n</head>')

        return html

    def render_to_pdf(
        self,
        document_ir: Dict[str, Any],
        output_path: str | Path,
        optimize_layout: bool = True
    ) -> Path:
        """
        将Document IR渲染为PDF文件

        参数:
            document_ir: Document IR数据
            output_path: PDF输出路径
            optimize_layout: 是否启用布局优化（默认True）

        返回:
            Path: 生成的PDF文件路径
        """
        output_path = Path(output_path)

        logger.info(f"开始生成PDF: {output_path}")

        # 生成HTML内容
        html_content = self._get_pdf_html(document_ir, optimize_layout)

        # 配置字体
        font_config = FontConfiguration()

        # 从HTML字符串创建WeasyPrint HTML对象
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        # 生成PDF
        try:
            html_doc.write_pdf(
                output_path,
                font_config=font_config,
                presentational_hints=True  # 保留HTML的呈现提示
            )
            logger.info(f"✓ PDF生成成功: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF生成失败: {e}")
            raise

    def render_to_bytes(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True
    ) -> bytes:
        """
        将Document IR渲染为PDF字节流

        参数:
            document_ir: Document IR数据
            optimize_layout: 是否启用布局优化（默认True）

        返回:
            bytes: PDF文件的字节内容
        """
        html_content = self._get_pdf_html(document_ir, optimize_layout)
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        return html_doc.write_pdf(
            font_config=font_config,
            presentational_hints=True
        )


__all__ = ["PDFRenderer"]
