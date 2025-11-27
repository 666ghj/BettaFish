"""
基于章节IR的HTML/PDF渲染器，实现与示例报告一致的交互与视觉。

新增要点：
1. 内置Chart.js数据验证/修复（ChartValidator+LLM兜底），杜绝非法配置导致的注入或崩溃；
2. 将MathJax/Chart.js/html2canvas/jspdf等依赖内联并带CDN fallback，适配离线或被墙环境；
3. 预置思源宋体子集的Base64字体，用于PDF/HTML一体化导出，避免缺字或额外系统依赖。
"""

from __future__ import annotations

import ast
import copy
import html
import json
import os
import re
import base64
from pathlib import Path
from typing import Any, Dict, List
from loguru import logger

from ReportEngine.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    create_chart_validator,
    create_chart_repairer
)
from ReportEngine.utils.chart_repair_api import create_llm_repair_functions


class HTMLRenderer:
    """
    Document IR → HTML 渲染器。

    - 读取 IR metadata/chapters，将结构映射为响应式HTML；
    - 动态构造目录、锚点、Chart.js脚本及互动逻辑；
    - 提供主题变量、编号映射等辅助功能。
    """

    CALLOUT_ALLOWED_TYPES = {
        "paragraph",
        "list",
        "table",
        "blockquote",
        "code",
        "math",
        "figure",
        "kpiGrid",
    }
    INLINE_ARTIFACT_KEYS = {
        "props",
        "widgetId",
        "widgetType",
        "data",
        "dataRef",
        "datasets",
        "labels",
        "config",
        "options",
    }
    TABLE_COMPLEX_CHARS = set(
        "@％%（）()，,。；;：:、？?！!·…-—_+<>[]{}|\\/\"'`~$^&*#"
    )

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化渲染器缓存并允许注入额外配置（如主题覆盖）"""
        self.config = config or {}
        self.document: Dict[str, Any] = {}
        self.widget_scripts: List[str] = []
        self.chart_counter = 0
        self.toc_entries: List[Dict[str, Any]] = []
        self.heading_counter = 0
        self.metadata: Dict[str, Any] = {}
        self.chapters: List[Dict[str, Any]] = []
        self.chapter_anchor_map: Dict[str, str] = {}
        self.heading_label_map: Dict[str, Dict[str, Any]] = {}
        self.primary_heading_index = 0
        self.secondary_heading_index = 0
        self.toc_rendered = False
        self.hero_kpi_signature: tuple | None = None
        self._current_chapter: Dict[str, Any] | None = None
        self._lib_cache: Dict[str, str] = {}
        self._pdf_font_base64: str | None = None

        # 初始化图表验证和修复器
        self.chart_validator = create_chart_validator()
        llm_repair_fns = create_llm_repair_functions()
        self.chart_repairer = create_chart_repairer(
            validator=self.chart_validator,
            llm_repair_fns=llm_repair_fns
        )
        # 记录修复失败的图表，避免多次触发LLM循环修复
        self._chart_failure_notes: Dict[str, str] = {}
        self._chart_failure_recorded: set[str] = set()

        # 统计信息
        self.chart_validation_stats = {
            'total': 0,
            'valid': 0,
            'repaired_locally': 0,
            'repaired_api': 0,
            'failed': 0
        }

    @staticmethod
    def _get_lib_path() -> Path:
        """获取第三方库文件的目录路径"""
        return Path(__file__).parent / "libs"

    @staticmethod
    def _get_font_path() -> Path:
        """返回PDF导出所需字体的路径（使用优化后的子集字体）"""
        return Path(__file__).parent / "assets" / "fonts" / "SourceHanSerifSC-Medium-Subset.ttf"

    def _load_lib(self, filename: str) -> str:
        """
        加载指定的第三方库文件内容

        参数:
            filename: 库文件名

        返回:
            str: 库文件的JavaScript代码内容
        """
        if filename in self._lib_cache:
            return self._lib_cache[filename]

        lib_path = self._get_lib_path() / filename
        try:
            with open(lib_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._lib_cache[filename] = content
                return content
        except FileNotFoundError:
            print(f"警告: 库文件 {filename} 未找到，将使用CDN备用链接")
            return ""
        except Exception as e:
            print(f"警告: 读取库文件 {filename} 时出错: {e}")
            return ""

    def _load_pdf_font_data(self) -> str:
        """加载PDF字体的Base64数据，避免重复读取大型文件"""
        if self._pdf_font_base64 is not None:
            return self._pdf_font_base64
        font_path = self._get_font_path()
        try:
            data = font_path.read_bytes()
            self._pdf_font_base64 = base64.b64encode(data).decode("ascii")
            return self._pdf_font_base64
        except FileNotFoundError:
            logger.warning("PDF字体文件缺失：%s", font_path)
        except Exception as exc:
            logger.warning("读取PDF字体文件失败：%s (%s)", font_path, exc)
        self._pdf_font_base64 = ""
        return self._pdf_font_base64

    def _build_script_with_fallback(
        self,
        inline_code: str,
        cdn_url: str,
        check_expression: str,
        lib_name: str,
        is_defer: bool = False
    ) -> str:
        """
        构建带有CDN fallback机制的script标签

        策略：
        1. 优先嵌入本地库代码
        2. 添加检测脚本，验证库是否成功加载
        3. 如果检测失败，动态加载CDN版本作为备用

        参数:
            inline_code: 本地库的JavaScript代码内容
            cdn_url: CDN备用链接
            check_expression: JavaScript表达式，用于检测库是否加载成功
            lib_name: 库名称（用于日志输出）
            is_defer: 是否使用defer属性

        返回:
            str: 完整的script标签HTML
        """
        defer_attr = ' defer' if is_defer else ''

        if inline_code:
            # 嵌入本地库代码，并添加fallback检测
            return f"""
  <script{defer_attr}>
    // {lib_name} - 嵌入式版本
    try {{
      {inline_code}
    }} catch (e) {{
      console.error('{lib_name}嵌入式加载失败:', e);
    }}
  </script>
  <script{defer_attr}>
    // {lib_name} - CDN Fallback检测
    (function() {{
      var checkLib = function() {{
        if (!({check_expression})) {{
          console.warn('{lib_name}本地版本加载失败，正在从CDN加载备用版本...');
          var script = document.createElement('script');
          script.src = '{cdn_url}';
          script.onerror = function() {{
            console.error('{lib_name} CDN备用加载也失败了');
          }};
          script.onload = function() {{
            console.log('{lib_name} CDN备用版本加载成功');
          }};
          document.head.appendChild(script);
        }}
      }};

      // 延迟检测，确保嵌入代码有时间执行
      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', function() {{
          setTimeout(checkLib, 100);
        }});
      }} else {{
        setTimeout(checkLib, 100);
      }}
    }})();
  </script>""".strip()
        else:
            # 本地文件读取失败，直接使用CDN
            logger.warning(f"{lib_name}本地文件未找到或读取失败，将直接使用CDN")
            return f'  <script{defer_attr} src="{cdn_url}"></script>'

    # ====== 公共入口 ======

    def render(self, document_ir: Dict[str, Any]) -> str:
        """
        接收Document IR，重置内部状态并输出完整HTML。

        参数:
            document_ir: 由 DocumentComposer 生成的整本报告数据。

        返回:
            str: 可直接写入磁盘的完整HTML文档。
        """
        self.document = document_ir or {}
        self.widget_scripts = []
        self.chart_counter = 0
        self.heading_counter = 0
        self.metadata = self.document.get("metadata", {}) or {}
        raw_chapters = self.document.get("chapters", []) or []
        self.toc_rendered = False
        self.chapters = self._prepare_chapters(raw_chapters)
        self.chapter_anchor_map = {
            chapter.get("chapterId"): chapter.get("anchor")
            for chapter in self.chapters
            if chapter.get("chapterId") and chapter.get("anchor")
        }
        self.heading_label_map = self._compute_heading_labels(self.chapters)
        self.toc_entries = self._collect_toc_entries(self.chapters)

        # 重置图表验证统计
        self.chart_validation_stats = {
            'total': 0,
            'valid': 0,
            'repaired_locally': 0,
            'repaired_api': 0,
            'failed': 0
        }
        # 每次渲染重新统计失败计数，但保留失败原因，避免重复LLM调用
        self._chart_failure_recorded = set()

        metadata = self.metadata
        theme_tokens = metadata.get("themeTokens") or self.document.get("themeTokens", {})
        title = metadata.get("title") or metadata.get("query") or "智能舆情报告"
        hero_kpis = (metadata.get("hero") or {}).get("kpis")
        self.hero_kpi_signature = self._kpi_signature_from_items(hero_kpis)

        head = self._render_head(title, theme_tokens)
        body = self._render_body()

        # 输出图表验证统计
        self._log_chart_validation_stats()

        return f"<!DOCTYPE html>\n<html lang=\"zh-CN\" class=\"no-js\">\n{head}\n{body}\n</html>"

    # ====== 头部 / 正文 ======

    def _resolve_color_value(self, value: Any, fallback: str) -> str:
        """从颜色token中提取字符串值"""
        if isinstance(value, str):
            value = value.strip()
            return value or fallback
        if isinstance(value, dict):
            for key in ("main", "value", "color", "base", "default"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            for candidate in value.values():
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return fallback

    def _resolve_color_family(self, value: Any, fallback: Dict[str, str]) -> Dict[str, str]:
        """解析主/亮/暗三色，缺失时回落到默认值"""
        result = {
            "main": fallback.get("main", "#007bff"),
            "light": fallback.get("light", fallback.get("main", "#007bff")),
            "dark": fallback.get("dark", fallback.get("main", "#007bff")),
        }
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                result["main"] = stripped
            return result
        if isinstance(value, dict):
            result["main"] = self._resolve_color_value(value.get("main") or value, result["main"])
            result["light"] = self._resolve_color_value(value.get("light") or value.get("lighter"), result["light"])
            result["dark"] = self._resolve_color_value(value.get("dark") or value.get("darker"), result["dark"])
        return result

    def _render_head(self, title: str, theme_tokens: Dict[str, Any]) -> str:
        """
        渲染<head>部分，加载主题CSS与必要的脚本依赖。

        参数:
            title: 页面title标签内容。
            theme_tokens: 主题变量，用于注入CSS。

        返回:
            str: head片段HTML。
        """
        css = self._build_css(theme_tokens)

        # 加载第三方库
        chartjs = self._load_lib("chart.js")
        chartjs_sankey = self._load_lib("chartjs-chart-sankey.js")
        html2canvas = self._load_lib("html2canvas.min.js")
        jspdf = self._load_lib("jspdf.umd.min.js")
        mathjax = self._load_lib("mathjax.js")
        wordcloud2 = self._load_lib("wordcloud2.min.js")

        # 生成嵌入式script标签，并为每个库添加CDN fallback机制
        # Chart.js - 主要图表库
        chartjs_tag = self._build_script_with_fallback(
            inline_code=chartjs,
            cdn_url="https://cdn.jsdelivr.net/npm/chart.js",
            check_expression="typeof Chart !== 'undefined'",
            lib_name="Chart.js"
        )

        # Chart.js Sankey插件
        sankey_tag = self._build_script_with_fallback(
            inline_code=chartjs_sankey,
            cdn_url="https://cdn.jsdelivr.net/npm/chartjs-chart-sankey@4",
            check_expression="typeof Chart !== 'undefined' && Chart.controllers && Chart.controllers.sankey",
            lib_name="chartjs-chart-sankey"
        )

        # wordcloud2 - 词云渲染
        wordcloud_tag = self._build_script_with_fallback(
            inline_code=wordcloud2,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/wordcloud2.js/1.2.2/wordcloud2.min.js",
            check_expression="typeof WordCloud !== 'undefined'",
            lib_name="wordcloud2"
        )

        # html2canvas - 用于截图
        html2canvas_tag = self._build_script_with_fallback(
            inline_code=html2canvas,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
            check_expression="typeof html2canvas !== 'undefined'",
            lib_name="html2canvas"
        )

        # jsPDF - 用于PDF导出
        jspdf_tag = self._build_script_with_fallback(
            inline_code=jspdf,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
            check_expression="typeof jspdf !== 'undefined'",
            lib_name="jsPDF"
        )

        # MathJax - 数学公式渲染
        mathjax_tag = self._build_script_with_fallback(
            inline_code=mathjax,
            cdn_url="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
            check_expression="typeof MathJax !== 'undefined'",
            lib_name="MathJax",
            is_defer=True
        )

        # PDF字体数据不再嵌入HTML，减小文件体积
        pdf_font_script = ""

        return f"""
<head>
  <meta charset="utf-8" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{self._escape_html(title)}</title>
  {chartjs_tag}
  {sankey_tag}
  {wordcloud_tag}
  {html2canvas_tag}
  {jspdf_tag}
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$','$$'], ['\\\\[','\\\\]']]
      }},
      options: {{
        skipHtmlTags: ['script','noscript','style','textarea','pre','code'],
        processEscapes: true
      }}
    }};
  </script>
  {mathjax_tag}
  {pdf_font_script}
  <style>
{css}
  </style>
  <script>
    document.documentElement.classList.remove('no-js');
    document.documentElement.classList.add('js-ready');
  </script>
</head>""".strip()

    def _render_body(self) -> str:
        """
        拼装<body>结构，包含头部、导航、章节和脚本。
        新版本：移除独立的cover section，标题合并到hero section中。

        返回:
            str: body片段HTML。
        """
        header = self._render_header()
        # cover = self._render_cover()  # 不再单独渲染cover
        hero = self._render_hero()
        toc_section = self._render_toc_section()
        chapters = "".join(self._render_chapter(chapter) for chapter in self.chapters)
        widget_scripts = "\n".join(self.widget_scripts)
        hydration = self._hydration_script()
        overlay = """
<div id="export-overlay" class="export-overlay no-print" aria-hidden="true">
  <div class="export-dialog" role="status" aria-live="assertive">
    <div class="export-spinner" aria-hidden="true"></div>
    <p class="export-status">正在导出PDF，请稍候...</p>
    <div class="export-progress" role="progressbar" aria-valuetext="正在导出">
      <div class="export-progress-bar"></div>
    </div>
  </div>
</div>
""".strip()

        return f"""
<body>
{header}
{overlay}
<main>
{hero}
{toc_section}
{chapters}
</main>
{widget_scripts}
{hydration}
</body>""".strip()

    # ====== 页眉 / 元信息 / 目录 ======

    def _render_header(self) -> str:
        """
        渲染吸顶头部，包含标题、副标题与功能按钮。

        返回:
            str: header HTML。
        """
        metadata = self.metadata
        title = metadata.get("title") or "智能舆情分析报告"
        subtitle = metadata.get("subtitle") or metadata.get("templateName") or "自动生成"
        return f"""
<header class="report-header no-print">
  <div>
    <h1>{self._escape_html(title)}</h1>
    <p class="subtitle">{self._escape_html(subtitle)}</p>
    {self._render_tagline()}
  </div>
  <div class="header-actions">
    <button id="theme-toggle" class="action-btn" type="button">🌗 主题切换</button>
    <button id="print-btn" class="action-btn" type="button">🖨️ 打印</button>
    <button id="export-btn" class="action-btn" type="button" style="display: none;">⬇️ 导出PDF</button>
  </div>
</header>
""".strip()

    def _render_tagline(self) -> str:
        """
        渲染标题下方的标语，如无标语则返回空字符串。

        返回:
            str: tagline HTML或空串。
        """
        tagline = self.metadata.get("tagline")
        if not tagline:
            return ""
        return f'<p class="tagline">{self._escape_html(tagline)}</p>'

    def _render_cover(self) -> str:
        """
        文章开头的封面区，居中展示标题与“文章总览”提示。

        返回:
            str: cover section HTML。
        """
        title = self.metadata.get("title") or "智能舆情报告"
        subtitle = self.metadata.get("subtitle") or self.metadata.get("templateName") or ""
        overview_hint = "文章总览"
        return f"""
<section class="cover">
  <p class="cover-hint">{overview_hint}</p>
  <h1>{self._escape_html(title)}</h1>
  <p class="cover-subtitle">{self._escape_html(subtitle)}</p>
</section>
""".strip()

    def _render_hero(self) -> str:
        """
        根据layout中的hero字段输出摘要/KPI/亮点区。
        新版本：将标题和总览合并在一起，去掉椭圆背景。

        返回:
            str: hero区HTML，若无数据则为空字符串。
        """
        hero = self.metadata.get("hero") or {}
        if not hero:
            return ""

        # 获取标题和副标题
        title = self.metadata.get("title") or "智能舆情报告"
        subtitle = self.metadata.get("subtitle") or self.metadata.get("templateName") or ""

        summary = hero.get("summary")
        summary_html = f'<p class="hero-summary">{self._escape_html(summary)}</p>' if summary else ""
        highlights = hero.get("highlights") or []
        highlight_html = "".join(
            f'<li><span class="badge">{self._escape_html(text)}</span></li>'
            for text in highlights
        )
        actions = hero.get("actions") or []
        actions_html = "".join(
            f'<button class="ghost-btn" type="button">{self._escape_html(text)}</button>'
            for text in actions
        )
        kpi_cards = ""
        for item in hero.get("kpis", []):
            delta = item.get("delta")
            tone = item.get("tone") or "neutral"
            delta_html = f'<span class="delta {tone}">{self._escape_html(delta)}</span>' if delta else ""
            kpi_cards += f"""
            <div class="hero-kpi">
                <div class="label">{self._escape_html(item.get("label"))}</div>
                <div class="value">{self._escape_html(item.get("value"))}</div>
                {delta_html}
            </div>
            """

        return f"""
<section class="hero-section-combined">
  <div class="hero-header">
    <p class="hero-hint">文章总览</p>
    <h1 class="hero-title">{self._escape_html(title)}</h1>
    <p class="hero-subtitle">{self._escape_html(subtitle)}</p>
  </div>
  <div class="hero-body">
    <div class="hero-content">
      {summary_html}
      <ul class="hero-highlights">{highlight_html}</ul>
      <div class="hero-actions">{actions_html}</div>
    </div>
    <div class="hero-side">
      {kpi_cards}
    </div>
  </div>
</section>
""".strip()

    def _render_meta_panel(self) -> str:
        """当前需求不展示元信息，保留方法便于后续扩展"""
        return ""

    def _render_toc_section(self) -> str:
        """
        生成目录模块，如无目录数据则返回空字符串。

        返回:
            str: toc HTML结构。
        """
        if not self.toc_entries:
            return ""
        if self.toc_rendered:
            return ""
        toc_config = self.metadata.get("toc") or {}
        toc_title = toc_config.get("title") or "📚 目录"
        toc_items = "".join(
            self._format_toc_entry(entry)
            for entry in self.toc_entries
        )
        self.toc_rendered = True
        return f"""
<nav class="toc">
  <div class="toc-title">{self._escape_html(toc_title)}</div>
  <ul>
    {toc_items}
  </ul>
</nav>
""".strip()

    def _collect_toc_entries(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        根据metadata中的tocPlan或章节heading收集目录项。

        参数:
            chapters: Document IR中的章节数组。

        返回:
            list[dict]: 规范化后的目录条目，包含level/text/anchor/description。
        """
        metadata = self.metadata
        toc_config = metadata.get("toc") or {}
        custom_entries = toc_config.get("customEntries")
        entries: List[Dict[str, Any]] = []

        if custom_entries:
            for entry in custom_entries:
                anchor = entry.get("anchor") or self.chapter_anchor_map.get(entry.get("chapterId"))

                # 验证anchor是否有效
                if not anchor:
                    logger.warning(
                        f"目录项 '{entry.get('display') or entry.get('title')}' "
                        f"缺少有效的anchor，已跳过"
                    )
                    continue

                # 验证anchor是否在chapter_anchor_map中或在chapters的blocks中
                anchor_valid = self._validate_toc_anchor(anchor, chapters)
                if not anchor_valid:
                    logger.warning(
                        f"目录项 '{entry.get('display') or entry.get('title')}' "
                        f"的anchor '{anchor}' 在文档中未找到对应的章节"
                    )

                # 清理描述文本
                description = entry.get("description")
                if description:
                    description = self._clean_text_from_json_artifacts(description)

                entries.append(
                    {
                        "level": entry.get("level", 2),
                        "text": entry.get("display") or entry.get("title") or "",
                        "anchor": anchor,
                        "description": description,
                    }
                )
            return entries

        for chapter in chapters or []:
            for block in chapter.get("blocks", []):
                if block.get("type") == "heading":
                    anchor = block.get("anchor") or chapter.get("anchor") or ""
                    if not anchor:
                        continue
                    mapped = self.heading_label_map.get(anchor, {})
                    # 清理描述文本
                    description = mapped.get("description")
                    if description:
                        description = self._clean_text_from_json_artifacts(description)
                    entries.append(
                        {
                            "level": block.get("level", 2),
                            "text": mapped.get("display") or block.get("text", ""),
                            "anchor": anchor,
                            "description": description,
                        }
                    )
        return entries

    def _validate_toc_anchor(self, anchor: str, chapters: List[Dict[str, Any]]) -> bool:
        """
        验证目录anchor是否在文档中存在对应的章节或heading。

        参数:
            anchor: 需要验证的anchor
            chapters: Document IR中的章节数组

        返回:
            bool: anchor是否有效
        """
        # 检查是否是章节anchor
        if anchor in self.chapter_anchor_map.values():
            return True

        # 检查是否在heading_label_map中
        if anchor in self.heading_label_map:
            return True

        # 检查章节的blocks中是否有这个anchor
        for chapter in chapters or []:
            chapter_anchor = chapter.get("anchor")
            if chapter_anchor == anchor:
                return True

            for block in chapter.get("blocks", []):
                block_anchor = block.get("anchor")
                if block_anchor == anchor:
                    return True

        return False

    def _prepare_chapters(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """复制章节并展开其中序列化的block，避免渲染缺失"""
        prepared: List[Dict[str, Any]] = []
        for chapter in chapters or []:
            chapter_copy = copy.deepcopy(chapter)
            chapter_copy["blocks"] = self._expand_blocks_in_place(chapter_copy.get("blocks", []))
            prepared.append(chapter_copy)
        return prepared

    def _expand_blocks_in_place(self, blocks: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        """遍历block列表，将内嵌JSON串拆解为独立block"""
        expanded: List[Dict[str, Any]] = []
        for block in blocks or []:
            extras = self._extract_embedded_blocks(block)
            expanded.append(block)
            if extras:
                expanded.extend(self._expand_blocks_in_place(extras))
        return expanded

    def _extract_embedded_blocks(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        在block内部查找被误写成字符串的block列表，并返回补充的block
        """
        extracted: List[Dict[str, Any]] = []

        def traverse(node: Any) -> None:
            """递归遍历block树，识别text字段内潜在的嵌套block JSON"""
            if isinstance(node, dict):
                for key, value in list(node.items()):
                    if key == "text" and isinstance(value, str):
                        decoded = self._decode_embedded_block_payload(value)
                        if decoded:
                            node[key] = ""
                            extracted.extend(decoded)
                        continue
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(block)
        return extracted

    def _decode_embedded_block_payload(self, raw: str) -> List[Dict[str, Any]] | None:
        """
        将字符串形式的block描述恢复为结构化列表。
        """
        if not isinstance(raw, str):
            return None
        stripped = raw.strip()
        if not stripped or stripped[0] not in "{[":
            return None
        payload: Any | None = None
        decode_targets = [stripped]
        if stripped and stripped[0] != "[":
            decode_targets.append(f"[{stripped}]")
        for candidate in decode_targets:
            try:
                payload = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if payload is None:
            for candidate in decode_targets:
                try:
                    payload = ast.literal_eval(candidate)
                    break
                except (ValueError, SyntaxError):
                    continue
        if payload is None:
            return None

        blocks = self._collect_blocks_from_payload(payload)
        return blocks or None

    @staticmethod
    def _looks_like_block(payload: Dict[str, Any]) -> bool:
        """粗略判断dict是否符合block结构"""
        if not isinstance(payload, dict):
            return False
        if "type" in payload and isinstance(payload["type"], str):
            return True
        structural_keys = {"blocks", "rows", "items", "widgetId", "widgetType", "data"}
        return any(key in payload for key in structural_keys)

    def _collect_blocks_from_payload(self, payload: Any) -> List[Dict[str, Any]]:
        """递归收集payload中的block节点"""
        collected: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            block_list = payload.get("blocks")
            block_type = payload.get("type")
            if isinstance(block_list, list) and not block_type:
                for candidate in block_list:
                    collected.extend(self._collect_blocks_from_payload(candidate))
                return collected
            if payload.get("cells") and not block_type:
                for cell in payload["cells"]:
                    collected.extend(self._collect_blocks_from_payload(cell.get("blocks")))
                return collected
            if payload.get("items") and not block_type:
                for item in payload["items"]:
                    collected.extend(self._collect_blocks_from_payload(item))
                return collected
            appended = False
            if block_type or payload.get("widgetId") or payload.get("rows"):
                coerced = self._coerce_block_dict(payload)
                if coerced:
                    collected.append(coerced)
                    appended = True
            items = payload.get("items")
            if isinstance(items, list) and not block_type:
                for item in items:
                    collected.extend(self._collect_blocks_from_payload(item))
                return collected
            if appended:
                return collected
        elif isinstance(payload, list):
            for item in payload:
                collected.extend(self._collect_blocks_from_payload(item))
        elif payload is None:
            return collected
        return collected

    def _coerce_block_dict(self, payload: Any) -> Dict[str, Any] | None:
        """尝试将dict补充为合法block结构"""
        if not isinstance(payload, dict):
            return None
        block = copy.deepcopy(payload)
        block_type = block.get("type")
        if not block_type:
            if "widgetId" in block:
                block_type = block["type"] = "widget"
            elif "rows" in block or "cells" in block:
                block_type = block["type"] = "table"
                if "rows" not in block and isinstance(block.get("cells"), list):
                    block["rows"] = [{"cells": block.pop("cells")}]
            elif "items" in block:
                block_type = block["type"] = "list"
        return block if block.get("type") else None

    def _format_toc_entry(self, entry: Dict[str, Any]) -> str:
        """
        将单个目录项转为带描述的HTML行。

        参数:
            entry: 目录条目，需包含 `text` 与 `anchor`。

        返回:
            str: `<li>` 形式的HTML。
        """
        desc = entry.get("description")
        # 清理描述文本中的JSON片段
        if desc:
            desc = self._clean_text_from_json_artifacts(desc)
        desc_html = f'<p class="toc-desc">{self._escape_html(desc)}</p>' if desc else ""
        level = entry.get("level", 2)
        css_level = 1 if level <= 2 else min(level, 4)
        return f'<li class="level-{css_level}"><a href="#{self._escape_attr(entry["anchor"])}">{self._escape_html(entry["text"])}</a>{desc_html}</li>'

    def _compute_heading_labels(self, chapters: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        预计算各级标题的编号（章：一、二；节：1.1；小节：1.1.1）。

        参数:
            chapters: Document IR中的章节数组。

        返回:
            dict: 锚点到编号/描述的映射，方便TOC与正文引用。
        """
        label_map: Dict[str, Dict[str, Any]] = {}

        for chap_idx, chapter in enumerate(chapters or [], start=1):
            chapter_heading_seen = False
            section_idx = 0
            subsection_idx = 0
            deep_counters: Dict[int, int] = {}

            for block in chapter.get("blocks", []):
                if block.get("type") != "heading":
                    continue
                level = block.get("level", 2)
                anchor = block.get("anchor") or chapter.get("anchor")
                if not anchor:
                    continue

                raw_text = block.get("text", "")
                clean_title = self._strip_order_prefix(raw_text)
                label = None
                display_text = raw_text

                if not chapter_heading_seen:
                    label = f"{self._to_chinese_numeral(chap_idx)}、"
                    display_text = f"{label} {clean_title}".strip()
                    chapter_heading_seen = True
                    section_idx = 0
                    subsection_idx = 0
                    deep_counters.clear()
                elif level <= 2:
                    section_idx += 1
                    subsection_idx = 0
                    deep_counters.clear()
                    label = f"{chap_idx}.{section_idx}"
                    display_text = f"{label} {clean_title}".strip()
                else:
                    if section_idx == 0:
                        section_idx = 1
                    if level == 3:
                        subsection_idx += 1
                        deep_counters.clear()
                        label = f"{chap_idx}.{section_idx}.{subsection_idx}"
                    else:
                        deep_counters[level] = deep_counters.get(level, 0) + 1
                        parts = [str(chap_idx), str(section_idx or 1), str(subsection_idx or 1)]
                        for lvl in sorted(deep_counters.keys()):
                            parts.append(str(deep_counters[lvl]))
                        label = ".".join(parts)
                    display_text = f"{label} {clean_title}".strip()

                label_map[anchor] = {
                    "level": level,
                    "display": display_text,
                    "label": label,
                    "title": clean_title,
                }
        return label_map

    @staticmethod
    def _strip_order_prefix(text: str) -> str:
        """移除形如“1.0 ”或“一、”的前缀，得到纯标题"""
        if not text:
            return ""
        separators = [" ", "、", ".", "．"]
        stripped = text.lstrip()
        for sep in separators:
            parts = stripped.split(sep, 1)
            if len(parts) == 2 and parts[0]:
                return parts[1].strip()
        return stripped.strip()

    @staticmethod
    def _to_chinese_numeral(number: int) -> str:
        """将1/2/3映射为中文序号（十内）"""
        numerals = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        if number <= 10:
            return numerals[number]
        tens, ones = divmod(number, 10)
        if number < 20:
            return "十" + (numerals[ones] if ones else "")
        words = ""
        if tens > 0:
            words += numerals[tens] + "十"
        if ones:
            words += numerals[ones]
        return words

    # ====== 章节与块级渲染 ======

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        """
        将章节blocks包裹进<section>，便于CSS控制。

        参数:
            chapter: 单个章节JSON。

        返回:
            str: section包裹的HTML。
        """
        section_id = self._escape_attr(chapter.get("anchor") or f"chapter-{chapter.get('chapterId', 'x')}")
        prev_chapter = self._current_chapter
        self._current_chapter = chapter
        try:
            blocks_html = self._render_blocks(chapter.get("blocks", []))
        finally:
            self._current_chapter = prev_chapter
        return f'<section id="{section_id}" class="chapter">\n{blocks_html}\n</section>'

    def _render_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """
        顺序渲染章节内所有block。

        参数:
            blocks: 章节内部的block数组。

        返回:
            str: 拼接后的HTML。
        """
        return "".join(self._render_block(block) for block in blocks or [])

    def _render_block(self, block: Dict[str, Any]) -> str:
        """
        根据block.type分派到不同的渲染函数。

        参数:
            block: 单个block对象。

        返回:
            str: 渲染后的HTML，未知类型会输出JSON调试信息。
        """
        block_type = block.get("type")
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "list": self._render_list,
            "table": self._render_table,
            "blockquote": self._render_blockquote,
            "hr": lambda b: "<hr />",
            "code": self._render_code,
            "math": self._render_math,
            "figure": self._render_figure,
            "callout": self._render_callout,
            "kpiGrid": self._render_kpi_grid,
            "widget": self._render_widget,
            "toc": lambda b: self._render_toc_section(),
        }
        handler = handlers.get(block_type)
        if handler:
            html_fragment = handler(block)
            return self._wrap_error_block(html_fragment, block)
        # 兼容旧格式：缺少type但包含inlines时按paragraph处理
        if isinstance(block, dict) and block.get("inlines"):
            html_fragment = self._render_paragraph({"inlines": block.get("inlines")})
            return self._wrap_error_block(html_fragment, block)
        # 兼容直接传入字符串的场景
        if isinstance(block, str):
            html_fragment = self._render_paragraph({"inlines": [{"text": block}]})
            return self._wrap_error_block(html_fragment, {"meta": {}, "type": "paragraph"})
        if isinstance(block.get("blocks"), list):
            html_fragment = self._render_blocks(block["blocks"])
            return self._wrap_error_block(html_fragment, block)
        fallback = f'<pre class="unknown-block">{self._escape_html(json.dumps(block, ensure_ascii=False, indent=2))}</pre>'
        return self._wrap_error_block(fallback, block)

    def _wrap_error_block(self, html_fragment: str, block: Dict[str, Any]) -> str:
        """若block标记了error元数据，则包裹提示容器并注入tooltip。"""
        if not html_fragment:
            return html_fragment
        meta = block.get("meta") or {}
        log_ref = meta.get("errorLogRef")
        if not isinstance(log_ref, dict):
            return html_fragment
        raw_preview = (meta.get("rawJsonPreview") or "")[:1200]
        error_message = meta.get("errorMessage") or "LLM返回块解析错误"
        importance = meta.get("importance") or "standard"
        ref_label = ""
        if log_ref.get("relativeFile") and log_ref.get("entryId"):
            ref_label = f"{log_ref['relativeFile']}#{log_ref['entryId']}"
        tooltip = f"{error_message} | {ref_label}".strip()
        attr_raw = self._escape_attr(raw_preview or tooltip)
        attr_title = self._escape_attr(tooltip)
        class_suffix = self._escape_attr(importance)
        return (
            f'<div class="llm-error-block importance-{class_suffix}" '
            f'data-raw="{attr_raw}" title="{attr_title}">{html_fragment}</div>'
        )

    def _render_heading(self, block: Dict[str, Any]) -> str:
        """渲染heading block，确保锚点存在"""
        original_level = max(1, min(6, block.get("level", 2)))
        if original_level <= 2:
            level = 2
        elif original_level == 3:
            level = 3
        else:
            level = min(original_level, 6)
        anchor = block.get("anchor")
        if anchor:
            anchor_attr = self._escape_attr(anchor)
        else:
            self.heading_counter += 1
            anchor = f"heading-{self.heading_counter}"
            anchor_attr = self._escape_attr(anchor)
        mapping = self.heading_label_map.get(anchor, {})
        display_text = mapping.get("display") or block.get("text", "")
        subtitle = block.get("subtitle")
        subtitle_html = f'<small>{self._escape_html(subtitle)}</small>' if subtitle else ""
        return f'<h{level} id="{anchor_attr}">{self._escape_html(display_text)}{subtitle_html}</h{level}>'

    def _render_paragraph(self, block: Dict[str, Any]) -> str:
        """渲染段落，内部通过inline run保持混排样式"""
        inlines_data = block.get("inlines", [])
        # 仅包含单个display公式时直接渲染为块，避免<p>内嵌<div>
        if len(inlines_data) == 1:
            standalone = self._render_standalone_math_inline(inlines_data[0])
            if standalone:
                return standalone

        inlines = "".join(self._render_inline(run) for run in inlines_data)
        return f"<p>{inlines}</p>"

    def _render_standalone_math_inline(self, run: Dict[str, Any] | str) -> str | None:
        """当段落只包含单个display公式时，转为math-block避免破坏行内布局"""
        if isinstance(run, dict):
            text_value, marks = self._normalize_inline_payload(run)
            if marks:
                return None
            math_id_hint = run.get("mathIds") or run.get("mathId")
        else:
            text_value = "" if run is None else str(run)
            math_id_hint = None
            marks = []

        rendered = self._render_text_with_inline_math(
            text_value,
            math_id_hint,
            allow_display_block=True
        )
        if rendered and rendered.strip().startswith('<div class="math-block"'):
            return rendered
        return None

    def _render_list(self, block: Dict[str, Any]) -> str:
        """渲染有序/无序/任务列表"""
        list_type = block.get("listType", "bullet")
        tag = "ol" if list_type == "ordered" else "ul"
        extra_class = "task-list" if list_type == "task" else ""
        items_html = ""
        for item in block.get("items", []):
            content = self._render_blocks(item)
            if not content.strip():
                continue
            items_html += f"<li>{content}</li>"
        class_attr = f' class="{extra_class}"' if extra_class else ""
        return f'<{tag}{class_attr}>{items_html}</{tag}>'

    def _render_table(self, block: Dict[str, Any]) -> str:
        """
        渲染表格，同时保留caption与单元格属性。

        参数:
            block: table类型的block。

        返回:
            str: 包含<table>结构的HTML。
        """
        rows = self._normalize_table_rows(block.get("rows") or [])
        rows_html = ""
        for row in rows:
            row_cells = ""
            for cell in row.get("cells", []):
                cell_tag = "th" if cell.get("header") or cell.get("isHeader") else "td"
                attr = []
                if cell.get("rowspan"):
                    attr.append(f'rowspan="{int(cell["rowspan"])}"')
                if cell.get("colspan"):
                    attr.append(f'colspan="{int(cell["colspan"])}"')
                if cell.get("align"):
                    attr.append(f'class="align-{cell["align"]}"')
                attr_str = (" " + " ".join(attr)) if attr else ""
                content = self._render_blocks(cell.get("blocks", []))
                row_cells += f"<{cell_tag}{attr_str}>{content}</{cell_tag}>"
            rows_html += f"<tr>{row_cells}</tr>"
        caption = block.get("caption")
        caption_html = f"<caption>{self._escape_html(caption)}</caption>" if caption else ""
        return f'<div class="table-wrap"><table>{caption_html}<tbody>{rows_html}</tbody></table></div>'

    def _normalize_table_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        检测并修正仅有单列的竖排表，转换为标准网格。

        参数:
            rows: 原始表格行。

        返回:
            list[dict]: 若检测到竖排表则返回转置后的行，否则原样返回。
        """
        if not rows:
            return []
        if not all(len((row.get("cells") or [])) == 1 for row in rows):
            return rows
        texts = [self._extract_row_text(row) for row in rows]
        header_span = self._detect_transposed_header_span(rows, texts)
        if not header_span:
            return rows
        normalized = self._transpose_single_cell_table(rows, header_span)
        return normalized or rows

    def _detect_transposed_header_span(self, rows: List[Dict[str, Any]], texts: List[str]) -> int:
        """推断竖排表头的行数，用于后续转置"""
        max_fields = min(8, len(rows) // 2)
        header_span = 0
        for idx, text in enumerate(texts):
            if idx >= max_fields:
                break
            if self._is_potential_table_header(text):
                header_span += 1
            else:
                break
        if header_span < 2:
            return 0
        remainder = texts[header_span:]
        if not remainder or (len(rows) - header_span) % header_span != 0:
            return 0
        if not any(self._looks_like_table_value(txt) for txt in remainder):
            return 0
        return header_span

    def _is_potential_table_header(self, text: str) -> bool:
        """根据长度与字符特征判断是否像表头字段"""
        if not text:
            return False
        stripped = text.strip()
        if not stripped or len(stripped) > 12:
            return False
        return not any(ch.isdigit() or ch in self.TABLE_COMPLEX_CHARS for ch in stripped)

    def _looks_like_table_value(self, text: str) -> bool:
        """判断该文本是否更像数据值，用于辅助判断转置"""
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) >= 12:
            return True
        return any(ch.isdigit() or ch in self.TABLE_COMPLEX_CHARS for ch in stripped)

    def _transpose_single_cell_table(self, rows: List[Dict[str, Any]], span: int) -> List[Dict[str, Any]]:
        """将单列多行的表格转换为标准表头 + 若干数据行"""
        total = len(rows)
        if total <= span or (total - span) % span != 0:
            return []
        header_rows = rows[:span]
        data_rows = rows[span:]
        normalized: List[Dict[str, Any]] = []
        header_cells = []
        for row in header_rows:
            cell = copy.deepcopy((row.get("cells") or [{}])[0])
            cell["header"] = True
            header_cells.append(cell)
        normalized.append({"cells": header_cells})
        for start in range(0, len(data_rows), span):
            group = data_rows[start : start + span]
            if len(group) < span:
                break
            normalized.append(
                {
                    "cells": [
                        copy.deepcopy((item.get("cells") or [{}])[0])
                        for item in group
                    ]
                }
            )
        return normalized

    def _extract_row_text(self, row: Dict[str, Any]) -> str:
        """提取表格行中的纯文本，方便启发式分析"""
        cells = row.get("cells") or []
        if not cells:
            return ""
        cell = cells[0]
        texts: List[str] = []
        for block in cell.get("blocks", []):
            if isinstance(block, dict):
                if block.get("type") == "paragraph":
                    for inline in block.get("inlines") or []:
                        if isinstance(inline, dict):
                            value = inline.get("text")
                        else:
                            value = inline
                        if value is None:
                            continue
                        texts.append(str(value))
        return "".join(texts)

    def _render_blockquote(self, block: Dict[str, Any]) -> str:
        """渲染引用块，可嵌套其他block"""
        inner = self._render_blocks(block.get("blocks", []))
        return f"<blockquote>{inner}</blockquote>"

    def _render_code(self, block: Dict[str, Any]) -> str:
        """渲染代码块，附带语言信息"""
        lang = block.get("lang") or ""
        content = self._escape_html(block.get("content", ""))
        return f'<pre class="code-block" data-lang="{self._escape_attr(lang)}"><code>{content}</code></pre>'

    def _render_math(self, block: Dict[str, Any]) -> str:
        """渲染数学公式，占位符交给外部MathJax或后处理"""
        latex_raw = block.get("latex", "")
        latex = self._escape_html(self._normalize_latex_string(latex_raw))
        math_id = self._escape_attr(block.get("mathId", "")) if block.get("mathId") else ""
        id_attr = f' data-math-id="{math_id}"' if math_id else ""
        return f'<div class="math-block"{id_attr}>$$ {latex} $$</div>'

    def _render_figure(self, block: Dict[str, Any]) -> str:
        """根据新规范默认不渲染外部图片，改为友好提示"""
        caption = block.get("caption") or "图像内容已省略（仅允许HTML原生图表与表格）"
        return f'<div class="figure-placeholder">{self._escape_html(caption)}</div>'

    def _render_callout(self, block: Dict[str, Any]) -> str:
        """
        渲染高亮提示盒，tone决定颜色。

        参数:
            block: callout类型的block。

        返回:
            str: callout HTML，若内部包含不允许的块会被拆分。
        """
        tone = block.get("tone", "info")
        title = block.get("title")
        safe_blocks, trailing_blocks = self._split_callout_content(block.get("blocks"))
        inner = self._render_blocks(safe_blocks)
        title_html = f"<strong>{self._escape_html(title)}</strong>" if title else ""
        callout_html = f'<div class="callout tone-{tone}">{title_html}{inner}</div>'
        trailing_html = self._render_blocks(trailing_blocks) if trailing_blocks else ""
        return callout_html + trailing_html

    def _split_callout_content(
        self, blocks: List[Dict[str, Any]] | None
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """限定callout内部仅包含轻量内容，其余块剥离到外层"""
        if not blocks:
            return [], []
        safe: List[Dict[str, Any]] = []
        trailing: List[Dict[str, Any]] = []
        for idx, child in enumerate(blocks):
            child_type = child.get("type")
            if child_type == "list":
                sanitized, overflow = self._sanitize_callout_list(child)
                if sanitized:
                    safe.append(sanitized)
                if overflow:
                    trailing.extend(overflow)
                    trailing.extend(copy.deepcopy(blocks[idx + 1 :]))
                    break
            elif child_type in self.CALLOUT_ALLOWED_TYPES:
                safe.append(child)
            else:
                trailing.extend(copy.deepcopy(blocks[idx:]))
                break
        else:
            return safe, []
        return safe, trailing

    def _sanitize_callout_list(
        self, block: Dict[str, Any]
    ) -> tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
        """当列表项包含结构型block时，将其截断移出callout"""
        items = block.get("items") or []
        if not items:
            return block, []
        sanitized_items: List[List[Dict[str, Any]]] = []
        trailing: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            safe, overflow = self._split_callout_content(item)
            if safe:
                sanitized_items.append(safe)
            if overflow:
                trailing.extend(overflow)
                for rest in items[idx + 1 :]:
                    trailing.extend(copy.deepcopy(rest))
                break
        if not sanitized_items:
            return None, trailing
        new_block = copy.deepcopy(block)
        new_block["items"] = sanitized_items
        return new_block, trailing

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        """渲染KPI卡片栅格，包含指标值与涨跌幅"""
        if self._should_skip_overview_kpi(block):
            return ""
        cards = ""
        items = block.get("items", [])
        for item in items:
            delta = item.get("delta")
            delta_tone = item.get("deltaTone") or "neutral"
            delta_html = f'<span class="delta {delta_tone}">{self._escape_html(delta)}</span>' if delta else ""
            cards += f"""
            <div class="kpi-card">
              <div class="kpi-value">{self._escape_html(item.get("value", ""))}<small>{self._escape_html(item.get("unit", ""))}</small></div>
              <div class="kpi-label">{self._escape_html(item.get("label", ""))}</div>
              {delta_html}
            </div>
            """
        count_attr = f' data-kpi-count="{len(items)}"' if items else ""
        return f'<div class="kpi-grid"{count_attr}>{cards}</div>'

    def _merge_dicts(
        self, base: Dict[str, Any] | None, override: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        递归合并两个字典，override覆盖base，均为新副本，避免副作用。
        """
        result = copy.deepcopy(base) if isinstance(base, dict) else {}
        if not isinstance(override, dict):
            return result
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _looks_like_chart_dataset(self, candidate: Any) -> bool:
        """启发式判断对象是否包含Chart.js常见的labels/datasets结构"""
        if not isinstance(candidate, dict):
            return False
        labels = candidate.get("labels")
        datasets = candidate.get("datasets")
        return isinstance(labels, list) or isinstance(datasets, list)

    def _coerce_chart_data_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        兼容LLM输出的Chart.js完整配置（含type/data/options）。
        若data中嵌套一个真正的labels/datasets结构，则提取并返回该结构。
        """
        if not isinstance(data, dict):
            return {}
        if self._looks_like_chart_dataset(data):
            return data
        for key in ("data", "chartData", "payload"):
            nested = data.get(key)
            if self._looks_like_chart_dataset(nested):
                return copy.deepcopy(nested)
        return data

    def _prepare_widget_payload(
        self, block: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        预处理widget数据，兼容部分block将Chart.js配置写入data字段的情况。

        返回:
            tuple(props, data): 归一化后的props与chart数据
        """
        props = copy.deepcopy(block.get("props") or {})
        raw_data = block.get("data")
        data_copy = copy.deepcopy(raw_data) if isinstance(raw_data, dict) else raw_data
        widget_type = block.get("widgetType") or ""
        chart_like = isinstance(widget_type, str) and widget_type.startswith("chart.js")

        if chart_like and isinstance(data_copy, dict):
            inline_options = data_copy.pop("options", None)
            inline_type = data_copy.pop("type", None)
            normalized_data = self._coerce_chart_data_structure(data_copy)
            if isinstance(inline_options, dict):
                props["options"] = self._merge_dicts(props.get("options"), inline_options)
            if isinstance(inline_type, str) and inline_type and not props.get("type"):
                props["type"] = inline_type
        elif isinstance(data_copy, dict):
            normalized_data = data_copy
        else:
            normalized_data = {}

        return props, normalized_data

    @staticmethod
    def _is_chart_data_empty(data: Dict[str, Any] | None) -> bool:
        """检查图表数据是否为空或缺少有效datasets"""
        if not isinstance(data, dict):
            return True

        datasets = data.get("datasets")
        if not isinstance(datasets, list) or len(datasets) == 0:
            return True

        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            series = ds.get("data")
            if isinstance(series, list) and len(series) > 0:
                return False

        return True

    def _chart_cache_key(self, block: Dict[str, Any]) -> str:
        """使用修复器的缓存算法生成稳定的key，便于跨阶段共享结果"""
        if hasattr(self, "chart_repairer") and block:
            try:
                return self.chart_repairer.build_cache_key(block)
            except Exception:
                pass
        return str(id(block))

    def _note_chart_failure(self, cache_key: str, reason: str) -> None:
        """记录修复失败原因，后续渲染直接使用占位提示"""
        if not cache_key:
            return
        if not reason:
            reason = "LLM返回的图表信息格式有误，无法正常显示"
        self._chart_failure_notes[cache_key] = reason

    def _record_chart_failure_stat(self, cache_key: str | None = None) -> None:
        """确保失败计数只统计一次"""
        if cache_key and cache_key in self._chart_failure_recorded:
            return
        self.chart_validation_stats['failed'] += 1
        if cache_key:
            self._chart_failure_recorded.add(cache_key)

    def _format_chart_error_reason(
        self,
        validation_result: ValidationResult | None = None,
        fallback_reason: str | None = None
    ) -> str:
        """拼接友好的失败提示"""
        base = "LLM返回的图表信息格式有误，已尝试本地与多模型修复但仍无法正常显示。"
        detail = None
        if validation_result:
            if validation_result.errors:
                detail = validation_result.errors[0]
            elif validation_result.warnings:
                detail = validation_result.warnings[0]
        if not detail and fallback_reason:
            detail = fallback_reason
        if detail:
            text = f"{base} 提示：{detail}"
            return text[:180] + ("..." if len(text) > 180 else "")
        return base

    def _render_chart_error_placeholder(
        self,
        title: str | None,
        reason: str,
        widget_id: str | None = None
    ) -> str:
        """输出图表失败时的简洁占位提示，避免破坏HTML/PDF布局"""
        safe_title = self._escape_html(title or "图表未能展示")
        safe_reason = self._escape_html(reason)
        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        return f"""
        <div class="chart-card chart-card--error"{widget_attr}>
          <div class="chart-error">
            <div class="chart-error__icon">!</div>
            <div class="chart-error__body">
              <div class="chart-error__title">{safe_title}</div>
              <p class="chart-error__desc">{safe_reason}</p>
            </div>
          </div>
        </div>
        """

    def _has_chart_failure(self, block: Dict[str, Any]) -> tuple[bool, str | None]:
        """检查是否已有修复失败记录"""
        cache_key = self._chart_cache_key(block)
        if block.get("_chart_renderable") is False:
            return True, block.get("_chart_error_reason")
        if cache_key in self._chart_failure_notes:
            return True, self._chart_failure_notes.get(cache_key)
        return False, None

    def _normalize_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None = None,
    ) -> None:
        """
        补全图表block中的缺失字段（如scales、datasets），提升容错性。

        - 将错误挂在block顶层的scales合并进props.options。
        - 当data缺失或datasets为空时，尝试使用章节级的data作为兜底。
        """

        if not isinstance(block, dict):
            return

        if block.get("type") != "widget":
            return

        widget_type = block.get("widgetType", "")
        if not (isinstance(widget_type, str) and widget_type.startswith("chart.js")):
            return

        # 确保props存在
        props = block.get("props")
        if not isinstance(props, dict):
            block["props"] = {}
            props = block["props"]

        # 将顶层scales合并进options，避免配置丢失
        scales = block.get("scales")
        if isinstance(scales, dict):
            options = props.get("options") if isinstance(props.get("options"), dict) else {}
            props["options"] = self._merge_dicts(options, {"scales": scales})

        # 确保data存在
        data = block.get("data")
        if not isinstance(data, dict):
            data = {}
            block["data"] = data

        # 如果datasets为空，尝试使用章节级data填充
        if chapter_context and self._is_chart_data_empty(data):
            chapter_data = chapter_context.get("data") if isinstance(chapter_context, dict) else None
            if isinstance(chapter_data, dict):
                fallback_ds = chapter_data.get("datasets")
                if isinstance(fallback_ds, list) and len(fallback_ds) > 0:
                    merged_data = copy.deepcopy(data)
                    merged_data["datasets"] = copy.deepcopy(fallback_ds)

                    if not merged_data.get("labels") and isinstance(chapter_data.get("labels"), list):
                        merged_data["labels"] = copy.deepcopy(chapter_data["labels"])

                    block["data"] = merged_data

        # 若仍缺少labels且数据点包含x值，自动生成便于fallback和坐标刻度
        data_ref = block.get("data")
        if isinstance(data_ref, dict) and not data_ref.get("labels"):
            datasets_ref = data_ref.get("datasets")
            if isinstance(datasets_ref, list) and datasets_ref:
                first_ds = datasets_ref[0]
                ds_data = first_ds.get("data") if isinstance(first_ds, dict) else None
                if isinstance(ds_data, list):
                    labels_from_data = []
                    for idx, point in enumerate(ds_data):
                        if isinstance(point, dict):
                            label_text = point.get("x") or point.get("label") or f"点{idx + 1}"
                        else:
                            label_text = f"点{idx + 1}"
                        labels_from_data.append(str(label_text))

                    if labels_from_data:
                        data_ref["labels"] = labels_from_data

    def _render_widget(self, block: Dict[str, Any]) -> str:
        """
        渲染Chart.js等交互组件的占位容器，并记录配置JSON。

        在渲染前进行图表验证和修复：
        1. 验证图表数据格式
        2. 如果无效，尝试本地修复
        3. 如果本地修复失败，尝试API修复
        4. 如果所有修复都失败，输出提示占位并跳过再次修复

        参数:
            block: widget类型的block，包含widgetId/props/data。

        返回:
            str: 含canvas与配置脚本的HTML。
        """
        # 先在block层面做一次容错补全（scales、章节级数据等）
        self._normalize_chart_block(block, getattr(self, "_current_chapter", None))

        # 统计
        widget_type = block.get('widgetType', '')
        is_chart = isinstance(widget_type, str) and widget_type.startswith('chart.js')
        is_wordcloud = isinstance(widget_type, str) and 'wordcloud' in widget_type.lower()
        widget_id = block.get('widgetId')
        cache_key = self._chart_cache_key(block) if is_chart else ""
        props_snapshot = block.get("props") if isinstance(block.get("props"), dict) else {}
        display_title = props_snapshot.get("title") or block.get("title") or widget_id or "图表"

        if is_chart:
            self.chart_validation_stats['total'] += 1

            # 词云使用专用渲染逻辑，不按Chart.js规则验证，直接跳过防止误判
            if is_wordcloud:
                self.chart_validation_stats['valid'] += 1
            else:
                # 如果此前已记录失败，直接使用占位提示，避免重复修复
                has_failed, cached_reason = self._has_chart_failure(block)
                if has_failed:
                    self._record_chart_failure_stat(cache_key)
                    reason = cached_reason or "LLM返回的图表信息格式有误，无法正常显示"
                    return self._render_chart_error_placeholder(display_title, reason, widget_id)

                # 验证图表数据
                validation_result = self.chart_validator.validate(block)

                if not validation_result.is_valid:
                    logger.warning(
                        f"图表 {block.get('widgetId', 'unknown')} 验证失败: {validation_result.errors}"
                    )

                    # 尝试修复
                    repair_result = self.chart_repairer.repair(block, validation_result)

                    if repair_result.success and repair_result.repaired_block:
                        # 修复成功，使用修复后的数据
                        block = repair_result.repaired_block
                        logger.info(
                            f"图表 {block.get('widgetId', 'unknown')} 修复成功 "
                            f"(方法: {repair_result.method}): {repair_result.changes}"
                        )

                        # 更新统计
                        if repair_result.method == 'local':
                            self.chart_validation_stats['repaired_locally'] += 1
                        elif repair_result.method == 'api':
                            self.chart_validation_stats['repaired_api'] += 1
                    else:
                        # 修复失败，记录失败并输出占位提示
                        fail_reason = self._format_chart_error_reason(validation_result)
                        block["_chart_renderable"] = False
                        block["_chart_error_reason"] = fail_reason
                        self._note_chart_failure(cache_key, fail_reason)
                        self._record_chart_failure_stat(cache_key)
                        logger.warning(
                            f"图表 {block.get('widgetId', 'unknown')} 修复失败，已跳过渲染: {fail_reason}"
                        )
                        return self._render_chart_error_placeholder(display_title, fail_reason, widget_id)
                else:
                    # 验证通过
                    self.chart_validation_stats['valid'] += 1
                    if validation_result.warnings:
                        logger.info(
                            f"图表 {block.get('widgetId', 'unknown')} 验证通过，"
                            f"但有警告: {validation_result.warnings}"
                        )

        # 渲染图表HTML
        self.chart_counter += 1
        canvas_id = f"chart-{self.chart_counter}"
        config_id = f"chart-config-{self.chart_counter}"

        props, normalized_data = self._prepare_widget_payload(block)
        payload = {
            "widgetId": block.get("widgetId"),
            "widgetType": block.get("widgetType"),
            "props": props,
            "data": normalized_data,
            "dataRef": block.get("dataRef"),
        }
        config_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        self.widget_scripts.append(
            f'<script type="application/json" id="{config_id}">{config_json}</script>'
        )

        title = props.get("title")
        title_html = f'<div class="chart-title">{self._escape_html(title)}</div>' if title else ""
        fallback_html = (
            self._render_wordcloud_fallback(props, block.get("widgetId"), block.get("data"))
            if is_wordcloud
            else self._render_widget_fallback(normalized_data, block.get("widgetId"))
        )
        return f"""
        <div class="chart-card{' wordcloud-card' if is_wordcloud else ''}">
          {title_html}
          <div class="chart-container">
            <canvas id="{canvas_id}" data-config-id="{config_id}"></canvas>
          </div>
          {fallback_html}
        </div>
        """

    def _render_widget_fallback(self, data: Dict[str, Any], widget_id: str | None = None) -> str:
        """渲染图表数据的文本兜底视图，避免Chart.js加载失败时出现空白"""
        if not isinstance(data, dict):
            return ""
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return ""

        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        header_cells = "".join(
            f"<th>{self._escape_html(ds.get('label') or f'系列{idx + 1}')}</th>"
            for idx, ds in enumerate(datasets)
        )
        body_rows = ""
        for idx, label in enumerate(labels):
            row_cells = [f"<td>{self._escape_html(label)}</td>"]
            for ds in datasets:
                series = ds.get("data") or []
                value = series[idx] if idx < len(series) else ""
                row_cells.append(f"<td>{self._escape_html(value)}</td>")
            body_rows += f"<tr>{''.join(row_cells)}</tr>"
        table_html = f"""
        <div class="chart-fallback" data-prebuilt="true"{widget_attr}>
          <table>
            <thead>
              <tr><th>类别</th>{header_cells}</tr>
            </thead>
            <tbody>
              {body_rows}
            </tbody>
          </table>
        </div>
        """
        return table_html

    def _render_wordcloud_fallback(
        self,
        props: Dict[str, Any] | None,
        widget_id: str | None = None,
        block_data: Any | None = None,
    ) -> str:
        """为词云提供表格兜底，避免WordCloud渲染失败后页面空白"""
        def _collect_items(raw: Any) -> list[dict]:
            """将多种词云输入格式（数组/对象/元组/纯文本）规整为统一的词条列表"""
            collected: list[dict] = []
            skip_keys = {"items", "data", "words", "labels", "datasets", "sourceData"}
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        text = item.get("word") or item.get("text") or item.get("label")
                        weight = item.get("weight")
                        category = item.get("category") or ""
                        if text:
                            collected.append({"word": str(text), "weight": weight, "category": str(category)})
                        # 若嵌套了 items/words/data 列表，递归提取
                        for nested_key in ("items", "words", "data"):
                            nested = item.get(nested_key)
                            if isinstance(nested, list):
                                collected.extend(_collect_items(nested))
                    elif isinstance(item, (list, tuple)) and item:
                        text = item[0]
                        weight = item[1] if len(item) > 1 else None
                        category = item[2] if len(item) > 2 else ""
                        if text:
                            collected.append({"word": str(text), "weight": weight, "category": str(category)})
                    elif isinstance(item, str):
                        collected.append({"word": item, "weight": 1.0, "category": ""})
            elif isinstance(raw, dict):
                # 若包含 items/words/data 列表，优先递归提取，不把键名当词
                handled = False
                for nested_key in ("items", "words", "data"):
                    nested = raw.get(nested_key)
                    if isinstance(nested, list):
                        collected.extend(_collect_items(nested))
                        handled = True
                if handled:
                    return collected

                # 非Chart结构且不包含skip_keys时，把key/value当作词云条目
                if not {"labels", "datasets"}.intersection(raw.keys()):
                    for text, weight in raw.items():
                        if text in skip_keys:
                            continue
                        collected.append({"word": str(text), "weight": weight, "category": ""})
            return collected

        words: list[dict] = []
        seen: set[str] = set()
        candidates = []
        if isinstance(props, dict):
            # 仅接受明确的词条数组字段，避免将嵌套items误当作词条
            if "data" in props and isinstance(props.get("data"), list):
                candidates.append(props["data"])
            if "words" in props and isinstance(props.get("words"), list):
                candidates.append(props["words"])
            if "items" in props and isinstance(props.get("items"), list):
                candidates.append(props["items"])
        candidates.append((props or {}).get("sourceData"))

        # 允许使用block.data兜底，避免缺失props时出现空白
        if block_data is not None:
            if isinstance(block_data, dict) and "items" in block_data and isinstance(block_data.get("items"), list):
                candidates.append(block_data["items"])
            else:
                candidates.append(block_data)

        for raw in candidates:
            for item in _collect_items(raw):
                key = f"{item['word']}::{item.get('category','')}"
                if key in seen:
                    continue
                seen.add(key)
                words.append(item)

        if not words:
            return ""

        def _format_weight(value: Any) -> str:
            """统一格式化权重，支持百分比/数值与字符串回退"""
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if 0 <= value <= 1.5:
                    return f"{value * 100:.1f}%"
                return f"{value:.2f}".rstrip("0").rstrip(".")
            return str(value)

        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        rows = "".join(
            f"<tr><td>{self._escape_html(item['word'])}</td>"
            f"<td>{self._escape_html(_format_weight(item['weight']))}</td>"
            f"<td>{self._escape_html(item['category'] or '-')}</td></tr>"
            for item in words
        )
        return f"""
        <div class="chart-fallback" data-prebuilt="true"{widget_attr}>
          <table>
            <thead>
              <tr><th>关键词</th><th>权重</th><th>类别</th></tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
        """

    def _log_chart_validation_stats(self):
        """输出图表验证统计信息"""
        stats = self.chart_validation_stats
        if stats['total'] == 0:
            return

        logger.info("=" * 60)
        logger.info("图表验证统计")
        logger.info("=" * 60)
        logger.info(f"总图表数量: {stats['total']}")
        logger.info(f"  ✓ 验证通过: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")

        if stats['repaired_locally'] > 0:
            logger.info(
                f"  ⚠ 本地修复: {stats['repaired_locally']} "
                f"({stats['repaired_locally']/stats['total']*100:.1f}%)"
            )

        if stats['repaired_api'] > 0:
            logger.info(
                f"  ⚠ API修复: {stats['repaired_api']} "
                f"({stats['repaired_api']/stats['total']*100:.1f}%)"
            )

        if stats['failed'] > 0:
            logger.warning(
                f"  ✗ 修复失败: {stats['failed']} "
                f"({stats['failed']/stats['total']*100:.1f}%) - "
                f"这些图表将展示简洁占位提示"
            )

        logger.info("=" * 60)

    # ====== 前置信息防护 ======

    def _kpi_signature_from_items(self, items: Any) -> tuple | None:
        """将KPI数组转换为可比较的签名"""
        if not isinstance(items, list):
            return None
        normalized = []
        for raw in items:
            normalized_item = self._normalize_kpi_item(raw)
            if normalized_item:
                normalized.append(normalized_item)
        return tuple(normalized) if normalized else None

    def _normalize_kpi_item(self, item: Any) -> tuple[str, str, str, str, str] | None:
        """
        将单条KPI记录规整为可对比的签名。

        参数:
            item: KPI数组中的原始字典，可能缺失字段或类型混杂。

        返回:
            tuple | None: (label, value, unit, delta, tone) 的五元组；若输入非法则为None。
        """
        if not isinstance(item, dict):
            return None

        def normalize(value: Any) -> str:
            """统一各类值的表现形式，便于生成稳定签名"""
            if value is None:
                return ""
            if isinstance(value, (int, float)):
                return str(value)
            return str(value).strip()

        label = normalize(item.get("label"))
        value = normalize(item.get("value"))
        unit = normalize(item.get("unit"))
        delta = normalize(item.get("delta"))
        tone = normalize(item.get("deltaTone") or item.get("tone"))
        return label, value, unit, delta, tone

    def _should_skip_overview_kpi(self, block: Dict[str, Any]) -> bool:
        """若KPI内容与封面一致，则判定为重复总览"""
        if not self.hero_kpi_signature:
            return False
        block_signature = self._kpi_signature_from_items(block.get("items"))
        if not block_signature:
            return False
        return block_signature == self.hero_kpi_signature

    # ====== 行内渲染 ======

    def _normalize_inline_payload(self, run: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
        """将嵌套inline node展平成基础文本与marks"""
        if not isinstance(run, dict):
            return ("" if run is None else str(run)), []

        marks = list(run.get("marks") or [])
        text_value: Any = run.get("text", "")
        seen: set[int] = set()

        while isinstance(text_value, dict):
            obj_id = id(text_value)
            if obj_id in seen:
                text_value = ""
                break
            seen.add(obj_id)
            nested_marks = text_value.get("marks")
            if nested_marks:
                marks.extend(nested_marks)
            if "text" in text_value:
                text_value = text_value.get("text")
            else:
                text_value = json.dumps(text_value, ensure_ascii=False)
                break

        if text_value is None:
            text_value = ""
        elif isinstance(text_value, (int, float)):
            text_value = str(text_value)
        elif not isinstance(text_value, str):
            try:
                text_value = json.dumps(text_value, ensure_ascii=False)
            except TypeError:
                text_value = str(text_value)

        if isinstance(text_value, str):
            stripped = text_value.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                payload = None
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    try:
                        payload = ast.literal_eval(stripped)
                    except (ValueError, SyntaxError):
                        payload = None
                if isinstance(payload, dict):
                    sentinel_keys = {"xrefs", "widgets", "footnotes", "errors", "metadata"}
                    if set(payload.keys()).issubset(sentinel_keys):
                        text_value = ""
                    else:
                        inline_payload = self._coerce_inline_payload(payload)
                        if inline_payload:
                            nested_text = inline_payload.get("text")
                            if nested_text is not None:
                                text_value = nested_text
                            nested_marks = inline_payload.get("marks")
                            if isinstance(nested_marks, list):
                                marks.extend(nested_marks)
                        elif any(key in payload for key in self.INLINE_ARTIFACT_KEYS):
                            text_value = ""

        return text_value, marks

    @staticmethod
    def _normalize_latex_string(raw: Any) -> str:
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
        return latex

    def _render_text_with_inline_math(
        self,
        text: Any,
        math_id: str | list | None = None,
        allow_display_block: bool = False
    ) -> str | None:
        """
        识别纯文本中的数学定界符并渲染为math-inline/math-block，提升兼容性。

        - 支持 $...$、$$...$$、\\(\\)、\\[\\]。
        - 若未检测到公式，返回None。
        """
        if not isinstance(text, str) or not text:
            return None

        pattern = re.compile(r'(\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\])', re.S)
        matches = list(pattern.finditer(text))
        if not matches:
            return None

        cursor = 0
        parts: List[str] = []
        id_iter = iter(math_id) if isinstance(math_id, list) else None

        for idx, m in enumerate(matches, start=1):
            start, end = m.span()
            prefix = text[cursor:start]
            raw = next(g for g in m.groups()[1:] if g is not None)
            latex = self._normalize_latex_string(raw)
            # 若已有math_id，直接使用，避免与SVG注入ID不一致；否则按局部序号生成
            if id_iter:
                mid = next(id_iter, f"auto-math-{idx}")
            else:
                mid = math_id or f"auto-math-{idx}"
            id_attr = f' data-math-id="{self._escape_attr(mid)}"'
            is_display = m.group(1).startswith('$$') or m.group(1).startswith('\\[')
            is_standalone = (
                len(matches) == 1 and
                not text[:start].strip() and
                not text[end:].strip()
            )
            use_block = allow_display_block and is_display and is_standalone
            if use_block:
                # 独立display公式，跳过两侧空白，直接渲染块级
                parts.append(f'<div class="math-block"{id_attr}>$$ {self._escape_html(latex)} $$</div>')
                cursor = len(text)
                break
            else:
                if prefix:
                    parts.append(self._escape_html(prefix))
                parts.append(f'<span class="math-inline"{id_attr}>\\( {self._escape_html(latex)} \\)</span>')
            cursor = end

        if cursor < len(text):
            parts.append(self._escape_html(text[cursor:]))
        return "".join(parts)

    @staticmethod
    def _coerce_inline_payload(payload: Dict[str, Any]) -> Dict[str, Any] | None:
        """尽力将字符串里的内联节点恢复为dict，修复渲染遗漏"""
        if not isinstance(payload, dict):
            return None
        inline_type = payload.get("type")
        if inline_type and inline_type not in {"inline", "text"}:
            return None
        if "text" not in payload and "marks" not in payload:
            return None
        return payload

    def _render_inline(self, run: Dict[str, Any]) -> str:
        """
        渲染单个inline run，支持多种marks叠加。

        参数:
            run: 含 text 与 marks 的内联节点。

        返回:
            str: 已包裹标签/样式的HTML片段。
        """
        text_value, marks = self._normalize_inline_payload(run)
        math_mark = next((mark for mark in marks if mark.get("type") == "math"), None)
        if math_mark:
            latex = self._normalize_latex_string(math_mark.get("value"))
            if not isinstance(latex, str) or not latex.strip():
                latex = self._normalize_latex_string(text_value)
            math_id = self._escape_attr(run.get("mathId", "")) if run.get("mathId") else ""
            id_attr = f' data-math-id="{math_id}"' if math_id else ""
            return f'<span class="math-inline"{id_attr}>\\( {self._escape_html(latex)} \\)</span>'

        # 尝试从纯文本中提取数学公式（即便没有math mark）
        math_id_hint = run.get("mathIds") or run.get("mathId")
        mathified = self._render_text_with_inline_math(text_value, math_id_hint)
        if mathified is not None:
            return mathified

        text = self._escape_html(text_value)
        styles: List[str] = []
        prefix: List[str] = []
        suffix: List[str] = []
        for mark in marks:
            mark_type = mark.get("type")
            if mark_type == "bold":
                prefix.append("<strong>")
                suffix.insert(0, "</strong>")
            elif mark_type == "italic":
                prefix.append("<em>")
                suffix.insert(0, "</em>")
            elif mark_type == "code":
                prefix.append("<code>")
                suffix.insert(0, "</code>")
            elif mark_type == "highlight":
                prefix.append("<mark>")
                suffix.insert(0, "</mark>")
            elif mark_type == "link":
                href_raw = mark.get("href")
                if href_raw and href_raw != "#":
                    href = self._escape_attr(href_raw)
                    title = self._escape_attr(mark.get("title") or "")
                    prefix.append(f'<a href="{href}" title="{title}" target="_blank" rel="noopener">')
                    suffix.insert(0, "</a>")
                else:
                    prefix.append('<span class="broken-link">')
                    suffix.insert(0, "</span>")
            elif mark_type == "color":
                value = mark.get("value")
                if value:
                    styles.append(f"color: {value}")
            elif mark_type == "font":
                family = mark.get("family")
                size = mark.get("size")
                weight = mark.get("weight")
                if family:
                    styles.append(f"font-family: {family}")
                if size:
                    styles.append(f"font-size: {size}")
                if weight:
                    styles.append(f"font-weight: {weight}")
            elif mark_type == "underline":
                styles.append("text-decoration: underline")
            elif mark_type == "strike":
                styles.append("text-decoration: line-through")
            elif mark_type == "subscript":
                prefix.append("<sub>")
                suffix.insert(0, "</sub>")
            elif mark_type == "superscript":
                prefix.append("<sup>")
                suffix.insert(0, "</sup>")

        if styles:
            style_attr = "; ".join(styles)
            prefix.insert(0, f'<span style="{style_attr}">')
            suffix.append("</span>")

        if not marks and "**" in (run.get("text") or ""):
            return self._render_markdown_bold_fallback(run.get("text", ""))

        return "".join(prefix) + text + "".join(suffix)

    def _render_markdown_bold_fallback(self, text: str) -> str:
        """在LLM未使用marks时兜底转换**粗体**"""
        if not text:
            return ""
        result: List[str] = []
        cursor = 0
        while True:
            start = text.find("**", cursor)
            if start == -1:
                result.append(html.escape(text[cursor:]))
                break
            end = text.find("**", start + 2)
            if end == -1:
                result.append(html.escape(text[cursor:]))
                break
            result.append(html.escape(text[cursor:start]))
            bold_content = html.escape(text[start + 2:end])
            result.append(f"<strong>{bold_content}</strong>")
            cursor = end + 2
        return "".join(result)

    # ====== 文本 / 安全工具 ======

    def _clean_text_from_json_artifacts(self, text: Any) -> str:
        """
        清理文本中的JSON片段和伪造的结构标记。

        LLM有时会在文本字段中混入未完成的JSON片段，如：
        "描述文本，{ \"chapterId\": \"S3" 或 "描述文本，{ \"level\": 2"

        此方法会：
        1. 移除不完整的JSON对象（以 { 开头但未正确闭合的）
        2. 移除不完整的JSON数组（以 [ 开头但未正确闭合的）
        3. 移除孤立的JSON键值对片段

        参数:
            text: 可能包含JSON片段的文本

        返回:
            str: 清理后的纯文本
        """
        if not text:
            return ""

        text_str = self._safe_text(text)

        # 模式1: 移除以逗号+空白+{开头的不完整JSON对象
        # 例如: "文本，{ \"key\": \"value\"" 或 "文本，{\\n  \"key\""
        text_str = re.sub(r',\s*\{[^}]*$', '', text_str)

        # 模式2: 移除以逗号+空白+[开头的不完整JSON数组
        text_str = re.sub(r',\s*\[[^\]]*$', '', text_str)

        # 模式3: 移除孤立的 { 加上后续内容（如果没有匹配的 }）
        # 检查是否有未闭合的 {
        open_brace_pos = text_str.rfind('{')
        if open_brace_pos != -1:
            close_brace_pos = text_str.rfind('}')
            if close_brace_pos < open_brace_pos:
                # { 在 } 后面或没有 }，说明是未闭合的
                # 截断到 { 之前
                text_str = text_str[:open_brace_pos].rstrip(',，、 \t\n')

        # 模式4: 类似处理 [
        open_bracket_pos = text_str.rfind('[')
        if open_bracket_pos != -1:
            close_bracket_pos = text_str.rfind(']')
            if close_bracket_pos < open_bracket_pos:
                # [ 在 ] 后面或没有 ]，说明是未闭合的
                text_str = text_str[:open_bracket_pos].rstrip(',，、 \t\n')

        # 模式5: 移除看起来像JSON键值对的片段，如 "chapterId": "S3
        # 这种情况通常出现在上面的模式之后
        text_str = re.sub(r',?\s*"[^"]+"\s*:\s*"[^"]*$', '', text_str)
        text_str = re.sub(r',?\s*"[^"]+"\s*:\s*[^,}\]]*$', '', text_str)

        # 清理末尾的逗号和空白
        text_str = text_str.rstrip(',，、 \t\n')

        return text_str.strip()

    def _safe_text(self, value: Any) -> str:
        """将任意值安全转换为字符串，None与复杂对象容错"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    def _escape_html(self, value: Any) -> str:
        """HTML文本上下文的转义"""
        return html.escape(self._safe_text(value), quote=False)

    def _escape_attr(self, value: Any) -> str:
        """HTML属性上下文转义并去掉危险换行"""
        escaped = html.escape(self._safe_text(value), quote=True)
        return escaped.replace("\n", " ").replace("\r", " ")

    # ====== CSS / JS（样式与脚本） ======

    def _build_css(self, tokens: Dict[str, Any]) -> str:
        """根据主题token拼接整页CSS，包括响应式与打印样式"""
        # 安全获取各个配置项，确保都是字典类型
        colors_raw = tokens.get("colors")
        colors = colors_raw if isinstance(colors_raw, dict) else {}

        typography_raw = tokens.get("typography")
        typography = typography_raw if isinstance(typography_raw, dict) else {}

        # 安全获取fonts，确保是字典类型
        fonts_raw = tokens.get("fonts") or typography.get("fonts")
        if isinstance(fonts_raw, dict):
            fonts = fonts_raw
        else:
            # 如果fonts是字符串或None，构造一个字典
            font_family = typography.get("fontFamily")
            if isinstance(font_family, str):
                fonts = {"body": font_family, "heading": font_family}
            else:
                fonts = {}

        spacing_raw = tokens.get("spacing")
        spacing = spacing_raw if isinstance(spacing_raw, dict) else {}

        primary_palette = self._resolve_color_family(
            colors.get("primary"),
            {"main": "#1a365d", "light": "#2d3748", "dark": "#0f1a2d"},
        )
        secondary_palette = self._resolve_color_family(
            colors.get("secondary"),
            {"main": "#e53e3e", "light": "#fc8181", "dark": "#c53030"},
        )
        bg = self._resolve_color_value(
            colors.get("bg") or colors.get("background") or colors.get("surface"),
            "#f8f9fa",
        )
        text_color = self._resolve_color_value(
            colors.get("text") or colors.get("onBackground"),
            "#212529",
        )
        card = self._resolve_color_value(
            colors.get("card") or colors.get("surfaceCard"),
            "#ffffff",
        )
        border = self._resolve_color_value(
            colors.get("border") or colors.get("divider"),
            "#dee2e6",
        )
        shadow = "rgba(0,0,0,0.08)"
        container_width = spacing.get("container") or spacing.get("containerWidth") or "1200px"
        gutter = spacing.get("gutter") or spacing.get("pagePadding") or "24px"
        body_font = fonts.get("body") or fonts.get("primary") or "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        heading_font = fonts.get("heading") or fonts.get("primary") or fonts.get("secondary") or body_font

        return f"""
:root {{
  --bg-color: {bg};
  --text-color: {text_color};
  --primary-color: {primary_palette["main"]};
  --primary-color-light: {primary_palette["light"]};
  --primary-color-dark: {primary_palette["dark"]};
  --secondary-color: {secondary_palette["main"]};
  --secondary-color-light: {secondary_palette["light"]};
  --secondary-color-dark: {secondary_palette["dark"]};
  --card-bg: {card};
  --border-color: {border};
  --shadow-color: {shadow};
}}
.dark-mode {{
  --bg-color: #121212;
  --text-color: #e0e0e0;
  --primary-color: #6ea8fe;
  --primary-color-light: #91caff;
  --primary-color-dark: #1f6feb;
  --secondary-color: #f28b82;
  --secondary-color-light: #f9b4ae;
  --secondary-color-dark: #d9655c;
  --card-bg: #1f1f1f;
  --border-color: #2c2c2c;
  --shadow-color: rgba(0, 0, 0, 0.4);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: {body_font};
  background: linear-gradient(180deg, rgba(0,0,0,0.04), rgba(0,0,0,0)) fixed, var(--bg-color);
  color: var(--text-color);
  line-height: 1.7;
  min-height: 100vh;
  transition: background-color 0.45s ease, color 0.45s ease;
}}
.report-header, main, .hero-section, .chapter, .chart-card, .callout, .kpi-card, .toc, .table-wrap {{
  transition: background-color 0.45s ease, color 0.45s ease, border-color 0.45s ease, box-shadow 0.45s ease;
}}
.report-header {{
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--card-bg);
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  box-shadow: 0 2px 6px var(--shadow-color);
}}
.tagline {{
  margin: 4px 0 0;
  color: var(--secondary-color);
  font-size: 0.95rem;
}}
.hero-section {{
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 24px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(0,123,255,0.1), rgba(23,162,184,0.1));
  border: 1px solid rgba(0,0,0,0.08);
  margin-bottom: 32px;
}}
.hero-content {{
  flex: 2;
  min-width: 260px;
}}
.hero-side {{
  flex: 1;
  min-width: 220px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}}
.hero-kpi {{
  background: var(--card-bg);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 6px 16px var(--shadow-color);
}}
.hero-kpi .label {{
  font-size: 0.9rem;
  color: var(--secondary-color);
}}
.hero-kpi .value {{
  font-size: 1.8rem;
  font-weight: 700;
}}
.hero-highlights {{
  list-style: none;
  padding: 0;
  margin: 16px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}}
.hero-highlights li {{
  margin: 0;
}}
.badge {{
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(0,0,0,0.05);
  font-size: 0.9rem;
}}
.broken-link {{
  text-decoration: underline dotted;
  color: var(--primary-color);
}}
.hero-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}}
.ghost-btn {{
  border: 1px solid var(--primary-color);
  background: transparent;
  color: var(--primary-color);
  border-radius: 999px;
  padding: 8px 16px;
  cursor: pointer;
}}
.hero-summary {{
  font-size: 1.05rem;
  font-weight: 500;
  margin-top: 0;
}}
.llm-error-block {{
  border: 1px dashed var(--secondary-color);
  border-radius: 12px;
  padding: 12px;
  margin: 12px 0;
  background: rgba(229,62,62,0.06);
  position: relative;
}}
.llm-error-block.importance-critical {{
  border-color: var(--secondary-color-dark);
  background: rgba(229,62,62,0.12);
}}
.llm-error-block::after {{
  content: attr(data-raw);
  white-space: pre-wrap;
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  max-height: 240px;
  overflow: auto;
  background: rgba(0,0,0,0.85);
  color: #fff;
  font-size: 0.85rem;
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 8px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
  z-index: 20;
}}
.llm-error-block:hover::after {{
  opacity: 1;
}}
.report-header h1 {{
  margin: 0;
  font-size: 1.6rem;
  color: var(--primary-color);
}}
.report-header .subtitle {{
  margin: 4px 0 0;
  color: var(--secondary-color);
}}
.header-actions {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}}
.cover {{
  text-align: center;
  margin: 20px 0 40px;
}}
.cover h1 {{
  font-size: 2.4rem;
  margin: 0.4em 0;
}}
.cover-hint {{
  letter-spacing: 0.4em;
  color: var(--secondary-color);
  font-size: 0.95rem;
}}
.cover-subtitle {{
  color: var(--secondary-color);
  margin: 0;
}}
.action-btn {{
  border: none;
  border-radius: 6px;
  background: var(--primary-color);
  color: #fff;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 0.95rem;
  transition: transform 0.2s ease;
  min-width: 160px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}}
.action-btn:hover {{
  transform: translateY(-1px);
}}
body.exporting {{
  cursor: progress;
}}
.export-overlay {{
  position: fixed;
  inset: 0;
  background: rgba(3, 9, 26, 0.55);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
  z-index: 999;
}}
.export-overlay.active {{
  opacity: 1;
  pointer-events: all;
}}
.export-dialog {{
  background: rgba(12, 19, 38, 0.92);
  padding: 24px 32px;
  border-radius: 18px;
  color: #fff;
  text-align: center;
  min-width: 280px;
  box-shadow: 0 16px 40px rgba(0,0,0,0.45);
}}
.export-spinner {{
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 3px solid rgba(255,255,255,0.2);
  border-top-color: var(--secondary-color);
  margin: 0 auto 16px;
  animation: export-spin 1s linear infinite;
}}
.export-status {{
  margin: 0;
  font-size: 1rem;
}}
.exporting *,
.exporting *::before,
.exporting *::after {{
  animation: none !important;
  transition: none !important;
}}
.export-progress {{
  width: 220px;
  height: 6px;
  background: rgba(255,255,255,0.25);
  border-radius: 999px;
  overflow: hidden;
  margin: 20px auto 0;
  position: relative;
}}
.export-progress-bar {{
  position: absolute;
  top: 0;
  bottom: 0;
  width: 45%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  animation: export-progress 1.4s ease-in-out infinite;
}}
@keyframes export-spin {{
  from {{ transform: rotate(0deg); }}
  to {{ transform: rotate(360deg); }}
}}
@keyframes export-progress {{
  0% {{ left: -45%; }}
  50% {{ left: 20%; }}
  100% {{ left: 110%; }}
}}
main {{
  max-width: {container_width};
  margin: 40px auto;
  padding: {gutter};
  background: var(--card-bg);
  border-radius: 16px;
  box-shadow: 0 10px 30px var(--shadow-color);
}}
h1, h2, h3, h4, h5, h6 {{
  font-family: {heading_font};
  color: var(--text-color);
  margin-top: 2em;
  margin-bottom: 0.6em;
  line-height: 1.35;
}}
h2 {{
  font-size: 1.9rem;
}}
h3 {{
  font-size: 1.4rem;
}}
h4 {{
  font-size: 1.2rem;
}}
p {{
  margin: 1em 0;
  text-align: justify;
}}
ul, ol {{
  margin-left: 1.5em;
  padding-left: 0;
}}
img, canvas, svg {{
  max-width: 100%;
  height: auto;
}}
.meta-card {{
  background: rgba(0,0,0,0.02);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--border-color);
}}
.meta-card ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.meta-card li {{
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dashed var(--border-color);
  padding: 8px 0;
}}
.toc {{
  margin-top: 30px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  background: rgba(0,0,0,0.01);
}}
.toc-title {{
  font-weight: 600;
  margin-bottom: 10px;
}}
.toc ul {{
  list-style: none;
  margin: 0;
  padding: 0;
}}
.toc li {{
  margin: 4px 0;
}}
.toc li.level-1 {{
  font-size: 1.05rem;
  font-weight: 600;
  margin-top: 12px;
}}
.toc li.level-2 {{
  margin-left: 12px;
}}
.toc li a {{
  color: var(--primary-color);
  text-decoration: none;
}}
.toc li.level-3 {{
  margin-left: 16px;
  font-size: 0.95em;
}}
.toc-desc {{
  margin: 2px 0 0;
  color: var(--secondary-color);
  font-size: 0.9rem;
}}
.toc-desc {{
  margin: 2px 0 0;
  color: var(--secondary-color);
  font-size: 0.9rem;
}}
.chapter {{
  margin-top: 40px;
  padding-top: 32px;
  border-top: 1px solid rgba(0,0,0,0.05);
}}
.chapter:first-of-type {{
  border-top: none;
  padding-top: 0;
}}
blockquote {{
  border-left: 4px solid var(--primary-color);
  padding: 12px 16px;
  background: rgba(0,0,0,0.04);
  border-radius: 0 8px 8px 0;
}}
.table-wrap {{
  overflow-x: auto;
  margin: 20px 0;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
table th, table td {{
  padding: 12px;
  border: 1px solid var(--border-color);
}}
table th {{
  background: rgba(0,0,0,0.03);
}}
.align-center {{ text-align: center; }}
.align-right {{ text-align: right; }}
.callout {{
  border-left: 4px solid var(--primary-color);
  padding: 16px;
  border-radius: 8px;
  margin: 20px 0;
  background: rgba(0,0,0,0.02);
}}
.callout.tone-warning {{ border-color: #ff9800; }}
.callout.tone-success {{ border-color: #2ecc71; }}
.callout.tone-danger {{ border-color: #e74c3c; }}
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin: 20px 0;
}}
.kpi-card {{
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(0,0,0,0.02);
  border: 1px solid var(--border-color);
  align-items: flex-start;
}}
.kpi-value {{
  font-size: 2rem;
  font-weight: 700;
  display: flex;
  flex-wrap: nowrap;
  gap: 4px 6px;
  line-height: 1.25;
  word-break: break-word;
  overflow-wrap: break-word;
}}
.kpi-value small {{
  font-size: 0.65em;
  align-self: baseline;
  white-space: nowrap;
}}
.kpi-label {{
  color: var(--secondary-color);
  line-height: 1.35;
  word-break: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
}}
.delta.up {{ color: #27ae60; }}
.delta.down {{ color: #e74c3c; }}
.delta.neutral {{ color: var(--secondary-color); }}
.delta {{
  display: block;
  line-height: 1.3;
  word-break: break-word;
  overflow-wrap: break-word;
}}
.chart-card {{
  margin: 30px 0;
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: rgba(0,0,0,0.01);
}}
.chart-card.chart-card--error {{
  border-style: dashed;
  background: linear-gradient(135deg, rgba(0,0,0,0.015), rgba(0,0,0,0.04));
}}
.chart-error {{
  display: flex;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 10px;
  align-items: flex-start;
  background: rgba(0,0,0,0.03);
  color: var(--secondary-color);
}}
.chart-error__icon {{
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: var(--secondary-color-dark);
  background: rgba(0,0,0,0.06);
  font-size: 0.9rem;
}}
.chart-error__title {{
  font-weight: 600;
  color: var(--text-color);
}}
.chart-error__desc {{
  margin: 4px 0 0;
  color: var(--secondary-color);
  line-height: 1.6;
}}
.chart-card.wordcloud-card .chart-container {{
  min-height: 180px;
}}
.chart-container {{
  position: relative;
  min-height: 220px;
}}
.chart-fallback {{
  display: none;
  margin-top: 12px;
  font-size: 0.85rem;
  overflow-x: auto;
}}
.no-js .chart-fallback {{
  display: block;
}}
.no-js .chart-container {{
  display: none;
}}
.chart-fallback table {{
  width: 100%;
  border-collapse: collapse;
}}
.chart-fallback th,
.chart-fallback td {{
  border: 1px solid var(--border-color);
  padding: 6px 8px;
  text-align: left;
}}
.chart-fallback th {{
  background: rgba(0,0,0,0.04);
}}
.wordcloud-fallback .wordcloud-badges {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}}
.wordcloud-badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(74, 144, 226, 0.35);
  color: var(--text-color);
  background: linear-gradient(135deg, rgba(74, 144, 226, 0.14) 0%, rgba(74, 144, 226, 0.24) 100%);
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06);
}}
.dark-mode .wordcloud-badge {{
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
}}
.wordcloud-badge small {{
  color: var(--secondary-color);
  font-weight: 600;
  font-size: 0.75rem;
}}
.chart-note {{
  margin-top: 8px;
  font-size: 0.85rem;
  color: var(--secondary-color);
}}
figure {{
  margin: 20px 0;
  text-align: center;
}}
figure img {{
  max-width: 100%;
  border-radius: 12px;
}}
.figure-placeholder {{
  padding: 16px;
  border: 1px dashed var(--border-color);
  border-radius: 12px;
  color: var(--secondary-color);
  text-align: center;
  font-size: 0.95rem;
  margin: 20px 0;
}}
.math-block {{
  text-align: center;
  font-size: 1.1rem;
  margin: 24px 0;
}}
.math-inline {{
  font-family: {fonts.get("heading", fonts.get("body", "sans-serif"))};
  font-style: italic;
  white-space: nowrap;
  padding: 0 0.15em;
}}
pre.code-block {{
  background: #1e1e1e;
  color: #fff;
  padding: 16px;
  border-radius: 12px;
  overflow-x: auto;
}}
@media (max-width: 768px) {{
  .report-header {{
    flex-direction: column;
    align-items: flex-start;
  }}
  main {{
    margin: 0;
    border-radius: 0;
  }}
}}
@media print {{
  .no-print {{ display: none !important; }}
  body {{
    background: #fff;
  }}
  main {{
    box-shadow: none;
    margin: 0;
    max-width: 100%;
  }}
  .chapter > *,
  .hero-section,
.callout,
.chart-card,
.kpi-grid,
.table-wrap,
figure,
blockquote {{
  break-inside: avoid;
  page-break-inside: avoid;
  max-width: 100%;
}}
.chapter h2,
.chapter h3,
.chapter h4 {{
  break-after: avoid;
  page-break-after: avoid;
  break-inside: avoid;
}}
.chart-card,
.table-wrap {{
  overflow: visible !important;
  max-width: 100% !important;
  box-sizing: border-box;
}}
.chart-card canvas {{
  width: 100% !important;
  height: auto !important;
  max-width: 100% !important;
}}
.table-wrap {{
  overflow-x: auto;
  max-width: 100%;
}}
.table-wrap table {{
  table-layout: fixed;
  width: 100%;
  max-width: 100%;
}}
.table-wrap table th,
.table-wrap table td {{
  word-break: break-word;
  overflow-wrap: break-word;
}}
/* 防止图片和图表溢出 */
img, canvas, svg {{
  max-width: 100% !important;
  height: auto !important;
}}
/* 确保所有容器不超出页面宽度 */
* {{
  box-sizing: border-box;
  max-width: 100%;
}}
}}
"""

    def _hydration_script(self) -> str:
        """返回页面底部的JS，负责Chart.js注水与导出逻辑"""
        return """
<script>
document.documentElement.classList.remove('no-js');
document.documentElement.classList.add('js-ready');

const chartRegistry = [];
const wordCloudRegistry = new Map();
const STABLE_CHART_TYPES = ['line', 'bar'];
const CHART_TYPE_LABELS = {
  line: '折线图',
  bar: '柱状图',
  doughnut: '圆环图',
  pie: '饼图',
  radar: '雷达图',
  polarArea: '极地区域图'
};

// 与PDF矢量渲染保持一致的颜色替换/提亮规则
const DEFAULT_CHART_COLORS = [
  '#4A90E2', '#E85D75', '#50C878', '#FFB347',
  '#9B59B6', '#3498DB', '#E67E22', '#16A085',
  '#F39C12', '#D35400', '#27AE60', '#8E44AD'
];
const CSS_VAR_COLOR_MAP = {
  'var(--chart-color-green)': '#4BC0C0',
  'var(--chart-color-red)': '#FF6384',
  'var(--chart-color-blue)': '#36A2EB',
  'var(--color-accent)': '#4A90E2',
  'var(--re-accent-color)': '#4A90E2',
  'var(--re-accent-color-translucent)': 'rgba(74, 144, 226, 0.08)',
  'var(--color-kpi-down)': '#E85D75',
  'var(--re-danger-color)': '#E85D75',
  'var(--re-danger-color-translucent)': 'rgba(232, 93, 117, 0.08)',
  'var(--color-warning)': '#FFB347',
  'var(--re-warning-color)': '#FFB347',
  'var(--re-warning-color-translucent)': 'rgba(255, 179, 71, 0.08)',
  'var(--color-success)': '#50C878',
  'var(--re-success-color)': '#50C878',
  'var(--re-success-color-translucent)': 'rgba(80, 200, 120, 0.08)',
  'var(--color-accent-positive)': '#50C878',
  'var(--color-accent-negative)': '#E85D75',
  'var(--color-text-secondary)': '#6B7280',
  'var(--accentPositive)': '#50C878',
  'var(--accentNegative)': '#E85D75',
  'var(--sentiment-positive, #28A745)': '#28A745',
  'var(--sentiment-negative, #E53E3E)': '#E53E3E',
  'var(--sentiment-neutral, #FFC107)': '#FFC107',
  'var(--sentiment-positive)': '#28A745',
  'var(--sentiment-negative)': '#E53E3E',
  'var(--sentiment-neutral)': '#FFC107',
  'var(--color-primary)': '#3498DB',
  'var(--color-secondary)': '#95A5A6'
};
const WORDCLOUD_CATEGORY_COLORS = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#6b7280',
  controversial: '#f59e0b'
};

function normalizeColorToken(color) {
  if (typeof color !== 'string') return color;
  const trimmed = color.trim();
  if (!trimmed) return null;
  // 支持 var(--token, fallback) 形式，优先解析fallback
  const varWithFallback = trimmed.match(/^var\(\s*--[^,)+]+,\s*([^)]+)\)/i);
  if (varWithFallback && varWithFallback[1]) {
    const fallback = varWithFallback[1].trim();
    const normalizedFallback = normalizeColorToken(fallback);
    if (normalizedFallback) return normalizedFallback;
  }
  if (CSS_VAR_COLOR_MAP[trimmed]) {
    return CSS_VAR_COLOR_MAP[trimmed];
  }
  if (trimmed.startsWith('var(')) {
    if (/accent|primary/i.test(trimmed)) return '#4A90E2';
    if (/danger|down|error/i.test(trimmed)) return '#E85D75';
    if (/warning/i.test(trimmed)) return '#FFB347';
    if (/success|up/i.test(trimmed)) return '#50C878';
    return '#3498DB';
  }
  return trimmed;
}

function hexToRgb(color) {
  if (typeof color !== 'string') return null;
  const normalized = color.replace('#', '');
  if (!(normalized.length === 3 || normalized.length === 6)) return null;
  const hex = normalized.length === 3 ? normalized.split('').map(c => c + c).join('') : normalized;
  const intVal = parseInt(hex, 16);
  if (Number.isNaN(intVal)) return null;
  return [(intVal >> 16) & 255, (intVal >> 8) & 255, intVal & 255];
}

function parseRgbString(color) {
  if (typeof color !== 'string') return null;
  const match = color.match(/rgba?\s*\(([^)]+)\)/i);
  if (!match) return null;
  const parts = match[1].split(',').map(p => parseFloat(p.trim())).filter(v => !Number.isNaN(v));
  if (parts.length < 3) return null;
  return [parts[0], parts[1], parts[2]].map(v => Math.max(0, Math.min(255, v)));
}

function alphaFromColor(color) {
  if (typeof color !== 'string') return null;
  const raw = color.trim();
  if (!raw) return null;
  if (raw.toLowerCase() === 'transparent') return 0;

  const extractAlpha = (source) => {
    const match = source.match(/rgba?\s*\(([^)]+)\)/i);
    if (!match) return null;
    const parts = match[1].split(',').map(p => p.trim());
    if (source.toLowerCase().startsWith('rgba') && parts.length >= 2) {
      const alphaToken = parts[parts.length - 1];
      const isPercent = /%$/.test(alphaToken);
      const alphaVal = parseFloat(alphaToken.replace('%', ''));
      if (!Number.isNaN(alphaVal)) {
        const normalizedAlpha = isPercent ? alphaVal / 100 : alphaVal;
        return Math.max(0, Math.min(1, normalizedAlpha));
      }
    }
    if (parts.length >= 3) return 1;
    return null;
  };

  const rawAlpha = extractAlpha(raw);
  if (rawAlpha !== null) return rawAlpha;

  const normalized = normalizeColorToken(raw);
  if (typeof normalized === 'string' && normalized !== raw) {
    const normalizedAlpha = extractAlpha(normalized);
    if (normalizedAlpha !== null) return normalizedAlpha;
  }

  return null;
}

function rgbFromColor(color) {
  const normalized = normalizeColorToken(color);
  return hexToRgb(normalized) || parseRgbString(normalized);
}

function colorLuminance(color) {
  const rgb = rgbFromColor(color);
  if (!rgb) return null;
  const [r, g, b] = rgb.map(v => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function lightenColor(color, ratio) {
  const rgb = rgbFromColor(color);
  if (!rgb) return color;
  const factor = Math.min(1, Math.max(0, ratio || 0.25));
  const mixed = rgb.map(v => Math.round(v + (255 - v) * factor));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function ensureAlpha(color, alpha) {
  const rgb = rgbFromColor(color);
  if (!rgb) return color;
  const clamped = Math.min(1, Math.max(0, alpha));
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${clamped})`;
}

function liftDarkColor(color) {
  const normalized = normalizeColorToken(color);
  const lum = colorLuminance(normalized);
  if (lum !== null && lum < 0.12) {
    return lightenColor(normalized, 0.35);
  }
  return normalized;
}

function mixColors(colorA, colorB, amount) {
  const rgbA = rgbFromColor(colorA);
  const rgbB = rgbFromColor(colorB);
  if (!rgbA && !rgbB) return colorA || colorB;
  if (!rgbA) return colorB;
  if (!rgbB) return colorA;
  const t = Math.min(1, Math.max(0, amount || 0));
  const mixed = rgbA.map((v, idx) => Math.round(v * (1 - t) + rgbB[idx] * t));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function pickComputedColor(keys, fallback, styles) {
  const styleRef = styles || getComputedStyle(document.body);
  for (const key of keys) {
    const val = styleRef.getPropertyValue(key);
    if (val && val.trim()) {
      const normalized = normalizeColorToken(val.trim());
      if (normalized) return normalized;
    }
  }
  return fallback;
}

function resolveWordcloudTheme() {
  const styles = getComputedStyle(document.body);
  const isDark = document.body.classList.contains('dark-mode');
  const text = pickComputedColor(['--text-color'], isDark ? '#e5e7eb' : '#111827', styles);
  const secondary = pickComputedColor(['--secondary-color', '--color-text-secondary'], isDark ? '#cbd5e1' : '#475569', styles);
  const accent = liftDarkColor(
    pickComputedColor(['--primary-color', '--color-accent', '--re-accent-color'], '#4A90E2', styles)
  );
  const cardBg = pickComputedColor(
    ['--card-bg', '--paper-bg', '--bg', '--bg-color', '--background', '--page-bg'],
    isDark ? '#0f172a' : '#ffffff',
    styles
  );
  return { text, secondary, accent, cardBg, isDark };
}

function normalizeDatasetColors(payload, chartType) {
  const changes = [];
  const data = payload && payload.data;
  if (!data || !Array.isArray(data.datasets)) {
    return changes;
  }
  const type = chartType || 'bar';
  const needsArrayColors = type === 'pie' || type === 'doughnut' || type === 'polarArea';
  const MIN_PIE_ALPHA = 0.6;
  const pickColor = (value, fallback) => {
    if (Array.isArray(value) && value.length) return value[0];
    return value || fallback;
  };

  data.datasets.forEach((dataset, idx) => {
    if (!isPlainObject(dataset)) return;
    if (type === 'line') {
      dataset.fill = true;  // 对折线图强制开启填充，便于区域对比
    }
    const paletteColor = normalizeColorToken(DEFAULT_CHART_COLORS[idx % DEFAULT_CHART_COLORS.length]);
    const borderInput = dataset.borderColor;
    const backgroundInput = dataset.backgroundColor;
    const borderIsArray = Array.isArray(borderInput);
    const bgIsArray = Array.isArray(backgroundInput);
    const baseCandidate = pickColor(borderInput, pickColor(backgroundInput, dataset.color || paletteColor));
    const liftedBase = liftDarkColor(baseCandidate || paletteColor);

    if (needsArrayColors) {
      const labelCount = Array.isArray(data.labels) ? data.labels.length : 0;
      const rawColors = bgIsArray ? backgroundInput : [];
      const dataLength = Array.isArray(dataset.data) ? dataset.data.length : 0;
      const total = Math.max(labelCount, rawColors.length, dataLength, 1);
      const normalizedColors = [];
      let fixedTransparentCount = 0;
      for (let i = 0; i < total; i++) {
        const fallbackColor = DEFAULT_CHART_COLORS[(idx + i) % DEFAULT_CHART_COLORS.length];
        const normalizedRaw = normalizeColorToken(rawColors[i]);
        const alpha = alphaFromColor(normalizedRaw);
        const isInvisible = typeof normalizedRaw === 'string' && normalizedRaw.toLowerCase() === 'transparent';
        if (alpha === 0 || isInvisible) {
          fixedTransparentCount += 1;
        }
        const baseColor = (!normalizedRaw || isInvisible) ? fallbackColor : normalizedRaw;
        const targetAlpha = alpha === null ? 1 : alpha;
        const normalizedColor = ensureAlpha(
          liftDarkColor(baseColor),
          Math.max(MIN_PIE_ALPHA, targetAlpha)
        );
        normalizedColors.push(normalizedColor);
      }
      dataset.backgroundColor = normalizedColors;
      dataset.borderColor = normalizedColors.map(col => ensureAlpha(liftDarkColor(col), 1));
      const changeLabel = fixedTransparentCount
        ? `dataset${idx}: 修正${fixedTransparentCount}个透明扇区`
        : `dataset${idx}: 标准化扇区颜色(${normalizedColors.length})`;
      changes.push(changeLabel);
      return;
    }

    if (!borderInput) {
      dataset.borderColor = liftedBase;
      changes.push(`dataset${idx}: 补全边框色`);
    } else if (borderIsArray) {
      dataset.borderColor = borderInput.map(col => liftDarkColor(col));
    } else {
      dataset.borderColor = liftDarkColor(borderInput);
    }

    const typeAlpha = type === 'line'
      ? (dataset.fill ? 0.25 : 0.18)
      : type === 'radar'
        ? 0.25
        : type === 'scatter' || type === 'bubble'
          ? 0.6
          : type === 'bar'
            ? 0.85
            : null;

    if (typeAlpha !== null) {
      if (bgIsArray && dataset.backgroundColor.length) {
        dataset.backgroundColor = backgroundInput.map(col => ensureAlpha(liftDarkColor(col), typeAlpha));
      } else {
        const bgSeed = pickColor(backgroundInput, pickColor(dataset.borderColor, paletteColor));
        dataset.backgroundColor = ensureAlpha(liftDarkColor(bgSeed), typeAlpha);
      }
      if (dataset.fill || type !== 'line') {
        changes.push(`dataset${idx}: 应用淡化填充以避免遮挡`);
      }
    } else if (!dataset.backgroundColor) {
      dataset.backgroundColor = ensureAlpha(liftedBase, 0.85);
    } else if (bgIsArray) {
      dataset.backgroundColor = backgroundInput.map(col => liftDarkColor(col));
    } else if (!bgIsArray) {
      dataset.backgroundColor = liftDarkColor(dataset.backgroundColor);
    }

    if (type === 'line' && !dataset.pointBackgroundColor) {
      dataset.pointBackgroundColor = Array.isArray(dataset.borderColor)
        ? dataset.borderColor[0]
        : dataset.borderColor;
    }
  });

  if (changes.length) {
    payload._colorAudit = changes;
  }
  return changes;
}

function getThemePalette() {
  const styles = getComputedStyle(document.body);
  return {
    text: styles.getPropertyValue('--text-color').trim(),
    grid: styles.getPropertyValue('--border-color').trim()
  };
}

function applyChartTheme(chart) {
  if (!chart) return;
  try {
    chart.update('none');
  } catch (err) {
    console.error('Chart refresh failed', err);
  }
}

function isPlainObject(value) {
  return Object.prototype.toString.call(value) === '[object Object]';
}

function cloneDeep(value) {
  if (Array.isArray(value)) {
    return value.map(cloneDeep);
  }
  if (isPlainObject(value)) {
    const obj = {};
    Object.keys(value).forEach(key => {
      obj[key] = cloneDeep(value[key]);
    });
    return obj;
  }
  return value;
}

function mergeOptions(base, override) {
  const result = isPlainObject(base) ? cloneDeep(base) : {};
  if (!isPlainObject(override)) {
    return result;
  }
  Object.keys(override).forEach(key => {
    const overrideValue = override[key];
    if (Array.isArray(overrideValue)) {
      result[key] = cloneDeep(overrideValue);
    } else if (isPlainObject(overrideValue)) {
      result[key] = mergeOptions(result[key], overrideValue);
    } else {
      result[key] = overrideValue;
    }
  });
  return result;
}

function resolveChartTypes(payload) {
  const explicit = payload && payload.props && payload.props.type;
  const widgetType = payload && payload.widgetType ? payload.widgetType : 'chart.js/bar';
  const derived = widgetType && widgetType.includes('/') ? widgetType.split('/').pop() : widgetType;
  const extra = Array.isArray(payload && payload.preferredTypes) ? payload.preferredTypes : [];
  const pipeline = [explicit, derived, ...extra, ...STABLE_CHART_TYPES].filter(Boolean);
  const result = [];
  pipeline.forEach(type => {
    if (type && !result.includes(type)) {
      result.push(type);
    }
  });
  return result.length ? result : ['bar'];
}

function describeChartType(type) {
  return CHART_TYPE_LABELS[type] || type || '图表';
}

function setChartDegradeNote(card, fromType, toType) {
  if (!card) return;
  card.setAttribute('data-chart-state', 'degraded');
  let note = card.querySelector('.chart-note');
  if (!note) {
    note = document.createElement('p');
    note.className = 'chart-note';
    card.appendChild(note);
  }
  note.textContent = `${describeChartType(fromType)}渲染失败，已自动切换为${describeChartType(toType)}以确保兼容。`;
}

function clearChartDegradeNote(card) {
  if (!card) return;
  card.removeAttribute('data-chart-state');
  const note = card.querySelector('.chart-note');
  if (note) {
    note.remove();
  }
}

function isWordCloudWidget(payload) {
  const type = payload && payload.widgetType;
  return typeof type === 'string' && type.toLowerCase().includes('wordcloud');
}

function hashString(str) {
  let h = 0;
  if (!str) return h;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return h;
}

function normalizeWordcloudItems(payload) {
  const sources = [];
  const props = payload && payload.props;
  const dataField = payload && payload.data;
  if (props) {
    ['data', 'items', 'words', 'sourceData'].forEach(key => {
      if (props[key]) sources.push(props[key]);
    });
  }
  if (dataField) {
    sources.push(dataField);
  }

  const seen = new Map();
  const pushItem = (word, weight, category) => {
    if (!word) return;
    let numeric = 1;
    if (typeof weight === 'number' && Number.isFinite(weight)) {
      numeric = weight;
    } else if (typeof weight === 'string') {
      const parsed = parseFloat(weight);
      numeric = Number.isFinite(parsed) ? parsed : 1;
    }
    if (!(numeric > 0)) numeric = 1;
    const cat = (category || '').toString().toLowerCase();
    const key = `${word}__${cat}`;
    const existing = seen.get(key);
    const payloadItem = { word: String(word), weight: numeric, category: cat };
    if (!existing || numeric > existing.weight) {
      seen.set(key, payloadItem);
    }
  };

  const consume = (raw) => {
    if (!raw) return;
    if (Array.isArray(raw)) {
      raw.forEach(item => {
        if (!item) return;
        if (Array.isArray(item)) {
          pushItem(item[0], item[1], item[2]);
        } else if (typeof item === 'object') {
          pushItem(item.word || item.text || item.label, item.weight, item.category);
        } else if (typeof item === 'string') {
          pushItem(item, 1, '');
        }
      });
    } else if (typeof raw === 'object') {
      Object.entries(raw).forEach(([word, weight]) => pushItem(word, weight, ''));
    }
  };

  sources.forEach(consume);

  const items = Array.from(seen.values());
  items.sort((a, b) => (b.weight || 0) - (a.weight || 0));
  return items.slice(0, 150);
}

function wordcloudColor(category) {
  const key = typeof category === 'string' ? category.toLowerCase() : '';
  const palette = resolveWordcloudTheme();
  const base = WORDCLOUD_CATEGORY_COLORS[key] || palette.accent || palette.secondary || '#334155';
  return liftDarkColor(base);
}

function renderWordCloudFallback(canvas, items, reason) {
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  if (!card) return;
  const wrapper = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (wrapper) {
    wrapper.style.display = 'none';
  } else {
    canvas.style.display = 'none';
  }
  let fallback = card.querySelector('.chart-fallback[data-dynamic="true"]');
  if (!fallback) {
    fallback = card.querySelector('.chart-fallback');
  }
  if (!fallback) {
    fallback = document.createElement('div');
    card.appendChild(fallback);
  }
  fallback.className = 'chart-fallback wordcloud-fallback';
  fallback.setAttribute('data-dynamic', 'true');
  fallback.style.display = 'block';
  fallback.innerHTML = '';
  card.setAttribute('data-chart-state', 'fallback');
  const buildBadge = (item, maxWeight) => {
    const badge = document.createElement('span');
    badge.className = 'wordcloud-badge';
    const clampedWeight = Math.max(0.5, (item.weight || 1));
    const normalized = Math.min(1, clampedWeight / (maxWeight || 1));
    const fontSize = 0.85 + normalized * 0.9;
    badge.style.fontSize = `${fontSize}rem`;
    badge.style.background = `linear-gradient(135deg, ${lightenColor(wordcloudColor(item.category), 0.05)} 0%, ${lightenColor(wordcloudColor(item.category), 0.15)} 100%)`;
    badge.style.borderColor = lightenColor(wordcloudColor(item.category), 0.25);
    badge.textContent = item.word;
    if (item.weight !== undefined && item.weight !== null) {
      const meta = document.createElement('small');
      meta.textContent = item.weight >= 0 && item.weight <= 1.5
        ? `${(item.weight * 100).toFixed(0)}%`
        : item.weight.toFixed(1).replace(/\.0+$/, '').replace(/0+$/, '').replace(/\.$/, '');
      badge.appendChild(meta);
    }
    return badge;
  };

  if (reason) {
    const notice = document.createElement('p');
    notice.className = 'chart-fallback__notice';
    notice.textContent = `词云未能渲染${reason ? `（${reason}）` : ''}，已展示关键词列表。`;
    fallback.appendChild(notice);
  }
  if (!items || !items.length) {
    const empty = document.createElement('p');
    empty.textContent = '暂无可用数据。';
    fallback.appendChild(empty);
    return;
  }
  const badges = document.createElement('div');
  badges.className = 'wordcloud-badges';
  const maxWeight = items.reduce((max, item) => Math.max(max, item.weight || 0), 1);
  items.forEach(item => {
    badges.appendChild(buildBadge(item, maxWeight));
  });
  fallback.appendChild(badges);
}

function renderWordCloud(canvas, payload, skipRegistry) {
  const items = normalizeWordcloudItems(payload);
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  const container = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (!items.length) {
    renderWordCloudFallback(canvas, items, '无有效数据');
    return;
  }
  if (typeof WordCloud === 'undefined') {
    renderWordCloudFallback(canvas, items, '词云依赖未加载');
    return;
  }
  const theme = resolveWordcloudTheme();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const width = Math.max(260, (container ? container.clientWidth : canvas.clientWidth || canvas.width || 320));
  const height = Math.max(120, Math.round(width / 5)); // 5:1 宽高比
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  canvas.style.backgroundColor = 'transparent';

  const resolveBgColor = () => {
    const cardEl = card || container || document.body;
    const style = getComputedStyle(cardEl);
    const tokens = ['--card-bg', '--panel-bg', '--paper-bg', '--bg', '--background', '--page-bg'];
    for (const key of tokens) {
      const val = style.getPropertyValue(key);
      if (val && val.trim() && val.trim() !== 'transparent') return val.trim();
    }
    if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') return style.backgroundColor;
    const bodyStyle = getComputedStyle(document.body);
    for (const key of tokens) {
      const val = bodyStyle.getPropertyValue(key);
      if (val && val.trim() && val.trim() !== 'transparent') return val.trim();
    }
    if (bodyStyle.backgroundColor && bodyStyle.backgroundColor !== 'rgba(0, 0, 0, 0)') {
      return bodyStyle.backgroundColor;
    }
    return 'transparent';
  };
  const bgColor = resolveBgColor() || theme.cardBg || 'transparent';

  const maxWeight = items.reduce((max, item) => Math.max(max, item.weight || 0), 0) || 1;
  const weightLookup = new Map();
  const categoryLookup = new Map();
  items.forEach(it => {
    weightLookup.set(it.word, it.weight || 1);
    categoryLookup.set(it.word, it.category || '');
  });
  const list = items.map(item => [item.word, item.weight && item.weight > 0 ? item.weight : 1]);
  try {
    WordCloud(canvas, {
      list,
      gridSize: Math.max(3, Math.floor(Math.sqrt(canvas.width * canvas.height) / 170)),
      weightFactor: (val) => {
        const normalized = Math.max(0, val) / maxWeight;
        const cap = Math.min(width, height);
        const base = Math.max(9, cap / 5.5);
        const size = base * (0.8 + normalized * 1.3);
        return size * dpr;
      },
      color: (word) => {
        const w = weightLookup.get(word) || 1;
        const ratio = Math.max(0, Math.min(1, w / (maxWeight || 1)));
        const category = categoryLookup.get(word) || '';
        const base = wordcloudColor(category);
        const target = theme.isDark ? '#ffffff' : (theme.text || '#111827');
        const mixAmount = theme.isDark
          ? 0.28 + (1 - ratio) * 0.22
          : 0.12 + (1 - ratio) * 0.35;
        const mixed = mixColors(base, target, mixAmount);
        return ensureAlpha(mixed || base, theme.isDark ? 0.95 : 1);
      },
      rotateRatio: 0,
      rotationSteps: 0,
      shuffle: false,
      shrinkToFit: true,
      drawOutOfBound: false,
      shape: 'square',
      ellipticity: 0.45,
      clearCanvas: true,
      backgroundColor: bgColor
    });
    if (container) {
      container.style.display = '';
      container.style.minHeight = `${height}px`;
      container.style.background = 'transparent';
    }
    const fallback = card && card.querySelector('.chart-fallback');
    if (fallback) {
      fallback.style.display = 'none';
    }
    card && card.removeAttribute('data-chart-state');
    if (!skipRegistry) {
      wordCloudRegistry.set(canvas, () => renderWordCloud(canvas, payload, true));
    }
  } catch (err) {
    console.error('WordCloud 渲染失败', err);
    renderWordCloudFallback(canvas, items, err && err.message ? err.message : '');
  }
}

function createFallbackTable(labels, datasets) {
  if (!Array.isArray(datasets) || !datasets.length) {
    return null;
  }
  const primaryDataset = datasets.find(ds => Array.isArray(ds && ds.data));
  const resolvedLabels = Array.isArray(labels) && labels.length
    ? labels
    : (primaryDataset && primaryDataset.data ? primaryDataset.data.map((_, idx) => `数据点 ${idx + 1}`) : []);
  if (!resolvedLabels.length) {
    return null;
  }
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  const categoryHeader = document.createElement('th');
  categoryHeader.textContent = '类别';
  headRow.appendChild(categoryHeader);
  datasets.forEach((dataset, index) => {
    const th = document.createElement('th');
    th.textContent = dataset && dataset.label ? dataset.label : `系列${index + 1}`;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  resolvedLabels.forEach((label, rowIdx) => {
    const row = document.createElement('tr');
    const labelCell = document.createElement('td');
    labelCell.textContent = label;
    row.appendChild(labelCell);
    datasets.forEach(dataset => {
      const cell = document.createElement('td');
      const series = dataset && Array.isArray(dataset.data) ? dataset.data[rowIdx] : undefined;
      if (typeof series === 'number') {
        cell.textContent = series.toLocaleString();
      } else if (series !== undefined && series !== null && series !== '') {
        cell.textContent = series;
      } else {
        cell.textContent = '—';
      }
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  return table;
}

function renderChartFallback(canvas, payload, reason) {
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  if (!card) return;
  clearChartDegradeNote(card);
  const wrapper = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (wrapper) {
    wrapper.style.display = 'none';
  } else {
    canvas.style.display = 'none';
  }
  let fallback = card.querySelector('.chart-fallback[data-dynamic="true"]');
  let prebuilt = false;
  if (!fallback) {
    fallback = card.querySelector('.chart-fallback');
    if (fallback) {
      prebuilt = fallback.hasAttribute('data-prebuilt');
    }
  }
  if (!fallback) {
    fallback = document.createElement('div');
    fallback.className = 'chart-fallback';
    fallback.setAttribute('data-dynamic', 'true');
    card.appendChild(fallback);
  } else if (!prebuilt) {
    fallback.innerHTML = '';
  }
  const titleFromOptions = payload && payload.props && payload.props.options &&
    payload.props.options.plugins && payload.props.options.plugins.title &&
    payload.props.options.plugins.title.text;
  const fallbackTitle = titleFromOptions ||
    (payload && payload.props && payload.props.title) ||
    (payload && payload.widgetId) ||
    canvas.getAttribute('id') ||
    '图表';
  const existingNotice = fallback.querySelector('.chart-fallback__notice');
  if (existingNotice) {
    existingNotice.remove();
  }
  const notice = document.createElement('p');
  notice.className = 'chart-fallback__notice';
  notice.textContent = `${fallbackTitle}：图表未能渲染，已展示表格数据${reason ? `（${reason}）` : ''}`;
  fallback.insertBefore(notice, fallback.firstChild || null);
  if (!prebuilt) {
    const table = createFallbackTable(
      payload && payload.data && payload.data.labels,
      payload && payload.data && payload.data.datasets
    );
    if (table) {
      fallback.appendChild(table);
    }
  }
  fallback.style.display = 'block';
  card.setAttribute('data-chart-state', 'fallback');
}

function buildChartOptions(payload) {
  const rawLegend = payload && payload.props ? payload.props.legend : undefined;
  let legendConfig;
  if (isPlainObject(rawLegend)) {
    legendConfig = mergeOptions({
      display: rawLegend.display !== false,
      position: rawLegend.position || 'top'
    }, rawLegend);
  } else {
    legendConfig = {
      display: rawLegend === 'hidden' ? false : true,
      position: typeof rawLegend === 'string' ? rawLegend : 'top'
    };
  }
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: legendConfig
    }
  };
  if (payload && payload.props && payload.props.title) {
    baseOptions.plugins.title = {
      display: true,
      text: payload.props.title
    };
  }
  const overrideOptions = payload && payload.props && payload.props.options;
  return mergeOptions(baseOptions, overrideOptions);
}

function validateChartData(payload, type) {
  /**
   * 前端验证图表数据
   * 返回: { valid: boolean, errors: string[] }
   */
  const errors = [];

  if (!payload || typeof payload !== 'object') {
    errors.push('无效的payload');
    return { valid: false, errors };
  }

  const data = payload.data;
  if (!data || typeof data !== 'object') {
    errors.push('缺少data字段');
    return { valid: false, errors };
  }

  // 特殊图表类型（scatter, bubble）
  const specialTypes = { 'scatter': true, 'bubble': true };
  if (specialTypes[type]) {
    // 这些类型需要特殊的数据格式 {x, y} 或 {x, y, r}
    // 跳过标准验证
    return { valid: true, errors };
  }

  // 标准图表类型验证
  const datasets = data.datasets;
  if (!Array.isArray(datasets)) {
    errors.push('datasets必须是数组');
    return { valid: false, errors };
  }

  if (datasets.length === 0) {
    errors.push('datasets数组为空');
    return { valid: false, errors };
  }

  // 验证每个dataset
  for (let i = 0; i < datasets.length; i++) {
    const dataset = datasets[i];
    if (!dataset || typeof dataset !== 'object') {
      errors.push(`datasets[${i}]不是对象`);
      continue;
    }

    if (!Array.isArray(dataset.data)) {
      errors.push(`datasets[${i}].data不是数组`);
    } else if (dataset.data.length === 0) {
      errors.push(`datasets[${i}].data为空`);
    }
  }

  // 需要labels的图表类型
  const labelRequiredTypes = {
    'line': true, 'bar': true, 'radar': true,
    'polarArea': true, 'pie': true, 'doughnut': true
  };

  if (labelRequiredTypes[type]) {
    const labels = data.labels;
    if (!Array.isArray(labels)) {
      errors.push('缺少labels数组');
    } else if (labels.length === 0) {
      errors.push('labels数组为空');
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function instantiateChart(ctx, payload, optionsTemplate, type) {
  if (!ctx) {
    return null;
  }
  if (ctx.canvas && typeof Chart !== 'undefined' && typeof Chart.getChart === 'function') {
    const existing = Chart.getChart(ctx.canvas);
    if (existing) {
      existing.destroy();
    }
  }
  const data = cloneDeep(payload && payload.data ? payload.data : {});
  const config = {
    type,
    data,
    options: cloneDeep(optionsTemplate)
  };
  return new Chart(ctx, config);
}

function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(null, args), wait || 200);
  };
}

function hydrateCharts() {
  document.querySelectorAll('canvas[data-config-id]').forEach(canvas => {
    const configScript = document.getElementById(canvas.dataset.configId);
    if (!configScript) return;
    let payload;
    try {
      payload = JSON.parse(configScript.textContent);
    } catch (err) {
      console.error('Widget JSON 解析失败', err);
      renderChartFallback(canvas, { widgetId: canvas.dataset.configId }, '配置解析失败');
      return;
    }
    if (isWordCloudWidget(payload)) {
      renderWordCloud(canvas, payload);
      return;
    }
    if (typeof Chart === 'undefined') {
      renderChartFallback(canvas, payload, 'Chart.js 未加载');
      return;
    }
    const chartTypes = resolveChartTypes(payload);
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      renderChartFallback(canvas, payload, 'Canvas 初始化失败');
      return;
    }

    // 前端数据验证
    const desiredType = chartTypes[0];
    const card = canvas.closest('.chart-card') || canvas.parentElement;
    const colorAdjustments = normalizeDatasetColors(payload, desiredType);
    if (colorAdjustments.length && card) {
      card.setAttribute('data-chart-color-fixes', colorAdjustments.join(' | '));
    }
    const validation = validateChartData(payload, desiredType);
    if (!validation.valid) {
      console.warn('图表数据验证失败:', validation.errors);
      // 验证失败但仍然尝试渲染，因为可能会降级成功
    }

    const optionsTemplate = buildChartOptions(payload);
    let chartInstance = null;
    let selectedType = null;
    let lastError;
    for (const type of chartTypes) {
      try {
        chartInstance = instantiateChart(ctx, payload, optionsTemplate, type);
        selectedType = type;
        break;
      } catch (err) {
        lastError = err;
        console.error('图表渲染失败', type, err);
      }
    }
    if (chartInstance) {
      chartRegistry.push(chartInstance);
      try {
        applyChartTheme(chartInstance);
      } catch (err) {
        console.error('主题同步失败', selectedType || desiredType || payload && payload.widgetType || 'chart', err);
      }
      if (selectedType && selectedType !== desiredType) {
        setChartDegradeNote(card, desiredType, selectedType);
      } else {
        clearChartDegradeNote(card);
      }
    } else {
      const reason = lastError && lastError.message ? lastError.message : '';
      renderChartFallback(canvas, payload, reason);
    }
  });
}

function getExportOverlayParts() {
  const overlay = document.getElementById('export-overlay');
  if (!overlay) {
    return null;
  }
  return {
    overlay,
    status: overlay.querySelector('.export-status')
  };
}

function showExportOverlay(message) {
  const parts = getExportOverlayParts();
  if (!parts) return;
  if (message && parts.status) {
    parts.status.textContent = message;
  }
  parts.overlay.classList.add('active');
  document.body.classList.add('exporting');
}

function updateExportOverlay(message) {
  if (!message) return;
  const parts = getExportOverlayParts();
  if (parts && parts.status) {
    parts.status.textContent = message;
  }
}

function hideExportOverlay(delay) {
  const parts = getExportOverlayParts();
  if (!parts) return;
  const close = () => {
    parts.overlay.classList.remove('active');
    document.body.classList.remove('exporting');
  };
  if (delay && delay > 0) {
    setTimeout(close, delay);
  } else {
    close();
  }
}

// exportPdf已移除
function exportPdf() {
  const target = document.querySelector('main');
  if (!target || typeof jspdf === 'undefined' || typeof jspdf.jsPDF !== 'function') {
    alert('PDF导出依赖未就绪');
    return;
  }
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    exportBtn.disabled = true;
  }
  showExportOverlay('正在导出PDF，请稍候...');
  document.body.classList.add('exporting');
  const pdf = new jspdf.jsPDF('p', 'mm', 'a4');
  try {
    if (window.pdfFontData) {
      pdf.addFileToVFS('SourceHanSerifSC-Medium.ttf', window.pdfFontData);
      pdf.addFont('SourceHanSerifSC-Medium.ttf', 'SourceHanSerif', 'normal');
      pdf.setFont('SourceHanSerif');
      console.log('PDF字体已成功加载');
    } else {
      console.warn('PDF字体数据未找到，将使用默认字体');
    }
  } catch (err) {
    console.warn('Custom PDF font setup failed, fallback to default', err);
  }
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pxWidth = Math.max(
    target.scrollWidth,
    document.documentElement.scrollWidth,
    Math.round(pageWidth * 3.78)
  );
  const restoreButton = () => {
    if (exportBtn) {
      exportBtn.disabled = false;
    }
    document.body.classList.remove('exporting');
  };
  let renderTask;
  try {
    // force charts to rerender at full width before capture
    chartRegistry.forEach(chart => {
      if (chart && typeof chart.resize === 'function') {
        chart.resize();
      }
    });
    wordCloudRegistry.forEach(fn => {
      if (typeof fn === 'function') {
        try {
          fn();
        } catch (err) {
          console.error('词云重新渲染失败', err);
        }
      }
    });
    renderTask = pdf.html(target, {
      x: 8,
      y: 12,
      width: pageWidth - 16,
      margin: [12, 12, 20, 12],
      autoPaging: 'text',
      windowWidth: pxWidth,
      html2canvas: {
        scale: Math.min(1.5, Math.max(1.0, pageWidth / (target.clientWidth || pageWidth))),
        useCORS: true,
        scrollX: 0,
        scrollY: -window.scrollY,
        logging: false,
        allowTaint: true,
        backgroundColor: '#ffffff'
      },
      pagebreak: {
        mode: ['css', 'legacy'],
        avoid: [
          '.chapter > *',
          '.callout',
          '.chart-card',
          '.table-wrap',
          '.kpi-grid',
          '.hero-section'
        ],
        before: '.chapter-divider'
      },
      callback: (doc) => doc.save('report.pdf')
    });
  } catch (err) {
    console.error('PDF 导出失败', err);
    updateExportOverlay('导出失败，请稍后重试');
    hideExportOverlay(1200);
    restoreButton();
    alert('PDF导出失败，请稍后重试');
    return;
  }
  if (renderTask && typeof renderTask.then === 'function') {
    renderTask.then(() => {
      updateExportOverlay('导出完成，正在保存...');
      hideExportOverlay(800);
      restoreButton();
    }).catch(err => {
      console.error('PDF 导出失败', err);
      updateExportOverlay('导出失败，请稍后重试');
      hideExportOverlay(1200);
      restoreButton();
      alert('PDF导出失败，请稍后重试');
    });
  } else {
    hideExportOverlay();
    restoreButton();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const rerenderWordclouds = debounce(() => {
    wordCloudRegistry.forEach(fn => {
      if (typeof fn === 'function') {
        fn();
      }
    });
  }, 260);
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      chartRegistry.forEach(applyChartTheme);
      rerenderWordclouds();
    });
  }
  const printBtn = document.getElementById('print-btn');
  if (printBtn) {
    printBtn.addEventListener('click', () => window.print());
  }
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', exportPdf);
  }
  window.addEventListener('resize', rerenderWordclouds);
  hydrateCharts();
});
</script>
""".strip()


__all__ = ["HTMLRenderer"]
