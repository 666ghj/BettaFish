"""
基于章节IR的HTML/PDF渲染器，实现与示例报告一致的交互与视觉。
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List


class HTMLRenderer:
    """Document IR → HTML 渲染器"""

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self.document: Dict[str, Any] = {}
        self.widget_scripts: List[str] = []
        self.chart_counter = 0
        self.toc_entries: List[Dict[str, Any]] = []
        self.heading_counter = 0
        self.metadata: Dict[str, Any] = {}
        self.chapter_anchor_map: Dict[str, str] = {}
        self.heading_label_map: Dict[str, Dict[str, Any]] = {}
        self.primary_heading_index = 0
        self.secondary_heading_index = 0

    # ====== 公共入口 ======

    def render(self, document_ir: Dict[str, Any]) -> str:
        """接收Document IR，重置内部状态并输出完整HTML"""
        self.document = document_ir or {}
        self.widget_scripts = []
        self.chart_counter = 0
        self.heading_counter = 0
        self.metadata = self.document.get("metadata", {}) or {}
        self.chapter_anchor_map = {
            chapter.get("chapterId"): chapter.get("anchor")
            for chapter in self.document.get("chapters", [])
            if chapter.get("chapterId") and chapter.get("anchor")
        }
        self.heading_label_map = self._compute_heading_labels(self.document.get("chapters", []))
        self.toc_entries = self._collect_toc_entries(
            self.document.get("chapters", [])
        )

        metadata = self.metadata
        theme_tokens = metadata.get("themeTokens") or self.document.get("themeTokens", {})
        title = metadata.get("title") or metadata.get("query") or "智能舆情报告"

        head = self._render_head(title, theme_tokens)
        body = self._render_body()
        return f"<!DOCTYPE html>\n<html lang=\"zh-CN\">\n{head}\n{body}\n</html>"

    # ====== Head / Body ======

    def _render_head(self, title: str, theme_tokens: Dict[str, Any]) -> str:
        """渲染<head>部分，加载主题CSS与必要的脚本依赖"""
        css = self._build_css(theme_tokens)
        return f"""
<head>
  <meta charset="utf-8" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{self._escape_html(title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
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
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
{css}
  </style>
</head>""".strip()

    def _render_body(self) -> str:
        """拼装<body>结构，包含头部、导航、章节和脚本"""
        header = self._render_header()
        cover = self._render_cover()
        hero = self._render_hero()
        toc_section = self._render_toc_section()
        chapters = "".join(
            self._render_chapter(chapter)
            for chapter in self.document.get("chapters", [])
        )
        widget_scripts = "\n".join(self.widget_scripts)
        hydration = self._hydration_script()

        return f"""
<body>
{header}
<main>
{cover}
{hero}
{toc_section}
{chapters}
</main>
{widget_scripts}
{hydration}
</body>""".strip()

    # ====== Header / Meta / TOC ======

    def _render_header(self) -> str:
        """渲染吸顶头部，包含标题、副标题与功能按钮"""
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
    <button id="export-btn" class="action-btn" type="button">⬇️ 导出PDF</button>
  </div>
</header>
""".strip()

    def _render_tagline(self) -> str:
        """渲染标题下方的标语，如无标语则返回空字符串"""
        tagline = self.metadata.get("tagline")
        if not tagline:
            return ""
        return f'<p class="tagline">{self._escape_html(tagline)}</p>'

    def _render_cover(self) -> str:
        """文章开头的封面区，居中展示标题与“文章总览”提示"""
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
        """根据layout中的hero字段输出摘要/KPI/亮点区"""
        hero = self.metadata.get("hero") or {}
        if not hero:
            return ""
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
<section class="hero-section">
  <div class="hero-content">
    {summary_html}
    <ul class="hero-highlights">{highlight_html}</ul>
    <div class="hero-actions">{actions_html}</div>
  </div>
  <div class="hero-side">
    {kpi_cards}
  </div>
</section>
""".strip()

    def _render_meta_panel(self) -> str:
        """当前需求不展示元信息，保留方法便于后续扩展"""
        return ""

    def _render_toc_section(self) -> str:
        """生成目录模块，如无目录数据则返回空字符串"""
        if not self.toc_entries:
            return ""
        toc_config = self.metadata.get("toc") or {}
        toc_title = toc_config.get("title") or "📚 目录"
        toc_items = "".join(
            self._format_toc_entry(entry)
            for entry in self.toc_entries
        )
        return f"""
<nav class="toc">
  <div class="toc-title">{self._escape_html(toc_title)}</div>
  <ul>
    {toc_items}
  </ul>
</nav>
""".strip()

    def _collect_toc_entries(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据metadata中的tocPlan或章节heading收集目录项"""
        metadata = self.metadata
        toc_config = metadata.get("toc") or {}
        custom_entries = toc_config.get("customEntries")
        entries: List[Dict[str, Any]] = []
        if custom_entries:
            for entry in custom_entries:
                anchor = entry.get("anchor") or self.chapter_anchor_map.get(entry.get("chapterId"))
                if not anchor:
                    continue
                entries.append(
                    {
                        "level": entry.get("level", 2),
                        "text": entry.get("display") or entry.get("title") or "",
                        "anchor": anchor,
                        "description": entry.get("description"),
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
                    entries.append(
                        {
                            "level": block.get("level", 2),
                            "text": mapped.get("display") or block.get("text", ""),
                            "anchor": anchor,
                            "description": mapped.get("description"),
                        }
                    )
        return entries

    def _format_toc_entry(self, entry: Dict[str, Any]) -> str:
        """将单个目录项转为带描述的HTML行"""
        desc = entry.get("description")
        desc_html = f'<p class="toc-desc">{self._escape_html(desc)}</p>' if desc else ""
        level = entry.get("level", 2)
        css_level = 1 if level <= 2 else min(level, 4)
        return f'<li class="level-{css_level}"><a href="#{self._escape_attr(entry["anchor"])}">{self._escape_html(entry["text"])}</a>{desc_html}</li>'

    def _compute_heading_labels(self, chapters: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """预计算各级标题的编号（章：一、二；节：1.1；小节：1.1.1）"""
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

    # ====== 章节 & Block 渲染 ======

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        """将章节blocks包裹进<section>，便于CSS控制"""
        section_id = self._escape_attr(chapter.get("anchor") or f"chapter-{chapter.get('chapterId', 'x')}")
        blocks_html = self._render_blocks(chapter.get("blocks", []))
        return f'<section id="{section_id}" class="chapter">\n{blocks_html}\n</section>'

    def _render_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """顺序渲染章节内所有block"""
        return "".join(self._render_block(block) for block in blocks or [])

    def _render_block(self, block: Dict[str, Any]) -> str:
        """根据block.type分派到不同的渲染函数"""
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
            return handler(block)
        return f'<pre class="unknown-block">{self._escape_html(json.dumps(block, ensure_ascii=False, indent=2))}</pre>'

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
        inlines = "".join(self._render_inline(run) for run in block.get("inlines", []))
        return f"<p>{inlines}</p>"

    def _render_list(self, block: Dict[str, Any]) -> str:
        """渲染有序/无序/任务列表"""
        list_type = block.get("listType", "bullet")
        tag = "ol" if list_type == "ordered" else "ul"
        extra_class = "task-list" if list_type == "task" else ""
        items_html = ""
        for item in block.get("items", []):
            content = self._render_blocks(item)
            items_html += f"<li>{content}</li>"
        class_attr = f' class="{extra_class}"' if extra_class else ""
        return f'<{tag}{class_attr}>{items_html}</{tag}>'

    def _render_table(self, block: Dict[str, Any]) -> str:
        """渲染表格，同时保留caption与单元格属性"""
        rows_html = ""
        for row in block.get("rows", []):
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
        latex = self._escape_html(block.get("latex", ""))
        return f'<div class="math-block">$$ {latex} $$</div>'

    def _render_figure(self, block: Dict[str, Any]) -> str:
        """根据新规范默认不渲染外部图片，改为友好提示"""
        caption = block.get("caption") or "图像内容已省略（仅允许HTML原生图表与表格）"
        return f'<div class="figure-placeholder">{self._escape_html(caption)}</div>'

    def _render_callout(self, block: Dict[str, Any]) -> str:
        """渲染高亮提示盒，tone决定颜色"""
        tone = block.get("tone", "info")
        title = block.get("title")
        inner = self._render_blocks(block.get("blocks", []))
        title_html = f"<strong>{self._escape_html(title)}</strong>" if title else ""
        return f'<div class="callout tone-{tone}">{title_html}{inner}</div>'

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        """渲染KPI卡片栅格，包含指标值与涨跌幅"""
        cards = ""
        for item in block.get("items", []):
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
        return f'<div class="kpi-grid">{cards}</div>'

    def _render_widget(self, block: Dict[str, Any]) -> str:
        """渲染Chart.js等交互组件的占位容器，并记录配置JSON"""
        self.chart_counter += 1
        canvas_id = f"chart-{self.chart_counter}"
        config_id = f"chart-config-{self.chart_counter}"

        payload = {
            "widgetId": block.get("widgetId"),
            "widgetType": block.get("widgetType"),
            "props": block.get("props", {}),
            "data": block.get("data", {}),
            "dataRef": block.get("dataRef"),
        }
        config_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        self.widget_scripts.append(
            f'<script type="application/json" id="{config_id}">{config_json}</script>'
        )

        title = block.get("props", {}).get("title")
        title_html = f'<div class="chart-title">{self._escape_html(title)}</div>' if title else ""
        fallback_html = self._render_widget_fallback(block)
        return f"""
        <div class="chart-card">
          {title_html}
          <div class="chart-container">
            <canvas id="{canvas_id}" data-config-id="{config_id}"></canvas>
          </div>
          {fallback_html}
        </div>
        """

    def _render_widget_fallback(self, block: Dict[str, Any]) -> str:
        """渲染图表数据的文本兜底视图，避免Chart.js加载失败时出现空白"""
        data = block.get("data") or {}
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return ""
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
        <div class="chart-fallback">
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
        return f"<noscript>{table_html}</noscript>"

    # ====== Inline 渲染 ======

    def _render_inline(self, run: Dict[str, Any]) -> str:
        """渲染单个inline run，支持多种marks叠加"""
        marks = run.get("marks") or []
        math_mark = next((mark for mark in marks if mark.get("type") == "math"), None)
        if math_mark:
            latex = math_mark.get("value")
            if not isinstance(latex, str) or not latex.strip():
                latex = run.get("text", "")
            return f'<span class="math-inline">\\( {self._escape_html(latex)} \\)</span>'
        text = self._escape_html(run.get("text", ""))
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

    # ====== CSS / JS ======

    def _build_css(self, tokens: Dict[str, Any]) -> str:
        """根据主题token拼接整页CSS，包括响应式与打印样式"""
        colors = tokens.get("colors", {})
        fonts = tokens.get("fonts", {})
        spacing = tokens.get("spacing", {})
        bg = colors.get("bg", "#f8f9fa")
        text_color = colors.get("text", "#212529")
        primary = colors.get("primary", "#007bff")
        secondary = colors.get("secondary", "#6c757d")
        card = colors.get("card", "#ffffff")
        border = colors.get("border", "#dee2e6")
        shadow = "rgba(0,0,0,0.08)"

        return f"""
:root {{
  --bg-color: {bg};
  --text-color: {text_color};
  --primary-color: {primary};
  --secondary-color: {secondary};
  --card-bg: {card};
  --border-color: {border};
  --shadow-color: {shadow};
}}
.dark-mode {{
  --bg-color: #121212;
  --text-color: #e0e0e0;
  --primary-color: #0d6efd;
  --secondary-color: #adb5bd;
  --card-bg: #1f1f1f;
  --border-color: #2c2c2c;
  --shadow-color: rgba(0, 0, 0, 0.4);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: {fonts.get("body", "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif")};
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
main {{
  max-width: {spacing.get("container", "1200px")};
  margin: 40px auto;
  padding: {spacing.get("gutter", "24px")};
  background: var(--card-bg);
  border-radius: 16px;
  box-shadow: 0 10px 30px var(--shadow-color);
}}
h1, h2, h3, h4, h5, h6 {{
  font-family: {fonts.get("heading", fonts.get("body", "sans-serif"))};
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
  padding: 16px;
  border-radius: 12px;
  background: rgba(0,0,0,0.02);
  border: 1px solid var(--border-color);
}}
.kpi-value {{
  font-size: 2rem;
  font-weight: 700;
}}
.kpi-label {{
  color: var(--secondary-color);
}}
.delta.up {{ color: #27ae60; }}
.delta.down {{ color: #e74c3c; }}
.delta.neutral {{ color: var(--secondary-color); }}
.chart-card {{
  margin: 30px 0;
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: rgba(0,0,0,0.01);
}}
.chart-container {{
  position: relative;
  min-height: 320px;
}}
.chart-fallback {{
  margin-top: 12px;
  font-size: 0.85rem;
  overflow-x: auto;
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
  }}
}}
"""

    def _hydration_script(self) -> str:
        """返回页面底部的JS，负责Chart.js注水与导出逻辑"""
        return """
<script>
const chartRegistry = [];

function getThemePalette() {
  const styles = getComputedStyle(document.body);
  return {
    text: styles.getPropertyValue('--text-color').trim(),
    grid: styles.getPropertyValue('--border-color').trim()
  };
}

function applyChartTheme(chart) {
  if (!chart) return;
  const palette = getThemePalette();
  const options = chart.options || {};
  options.plugins = options.plugins || {};
  options.plugins.legend = options.plugins.legend || {};
  options.plugins.legend.labels = options.plugins.legend.labels || {};
  options.plugins.legend.labels.color = palette.text;
  if (options.plugins.title) {
    options.plugins.title.color = palette.text;
  }
  const scales = options.scales || {};
  Object.keys(scales).forEach(key => {
    const scale = scales[key] || {};
    if (scale.ticks) {
      scale.ticks.color = palette.text;
    } else {
      scale.ticks = { color: palette.text };
    }
    if (scale.grid) {
      scale.grid.color = palette.grid;
    } else {
      scale.grid = { color: palette.grid };
    }
  });
  options.scales = scales;
  chart.options = options;
  chart.update('none');
}

function hydrateCharts() {
  if (typeof Chart === 'undefined') {
    return;
  }
  document.querySelectorAll('canvas[data-config-id]').forEach(canvas => {
    const configScript = document.getElementById(canvas.dataset.configId);
    if (!configScript) return;
    let payload;
    try {
      payload = JSON.parse(configScript.textContent);
    } catch (err) {
      console.error('Widget JSON 解析失败', err);
      return;
    }
    const chartType = (payload.widgetType || 'chart.js/bar').split('/').pop();
    const ctx = canvas.getContext('2d');
    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: payload.props && payload.props.legend !== 'hidden',
          position: (payload.props && payload.props.legend) || 'top'
        },
        title: payload.props && payload.props.title ? {
          display: true,
          text: payload.props.title
        } : undefined
      }
    };
    const mergedOptions = Object.assign({}, baseOptions, payload.props && payload.props.options ? payload.props.options : {});
    const config = {
      type: chartType,
      data: payload.data || {},
      options: mergedOptions
    };
    const chart = new Chart(ctx, config);
    chartRegistry.push(chart);
    applyChartTheme(chart);
  });
}

function exportPdf() {
  const target = document.querySelector('main');
  if (!target || typeof html2canvas === 'undefined' || typeof jspdf === 'undefined') {
    alert('PDF导出依赖未就绪');
    return;
  }
  html2canvas(target, {scale: 2}).then(canvas => {
    const imgData = canvas.toDataURL('image/png');
    const pdf = new jspdf.jsPDF('p', 'mm', 'a4');
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const imgHeight = canvas.height * pageWidth / canvas.width;
    let heightLeft = imgHeight;
    let position = 0;

    pdf.addImage(imgData, 'PNG', 0, position, pageWidth, imgHeight);
    heightLeft -= pageHeight;

    while (heightLeft > 0) {
      position = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, 'PNG', 0, position, pageWidth, imgHeight);
      heightLeft -= pageHeight;
    }
    pdf.save('report.pdf');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      chartRegistry.forEach(applyChartTheme);
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
  hydrateCharts();
});
</script>
""".strip()

    # ====== Utils ======

    @staticmethod
    def _escape_html(value: Any) -> str:
        """HTML内容转义工具，避免XSS"""
        return html.escape(str(value)) if value is not None else ""

    @staticmethod
    def _escape_attr(value: Any) -> str:
        """HTML属性值转义工具"""
        return html.escape(str(value), quote=True) if value is not None else ""


__all__ = ["HTMLRenderer"]
