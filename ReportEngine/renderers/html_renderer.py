"""
基于章节IR的HTML/PDF渲染器，实现与示例报告一致的交互与视觉。
"""

from __future__ import annotations

import ast
import copy
import html
import json
from typing import Any, Dict, List


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

        metadata = self.metadata
        theme_tokens = metadata.get("themeTokens") or self.document.get("themeTokens", {})
        title = metadata.get("title") or metadata.get("query") or "智能舆情报告"
        hero_kpis = (metadata.get("hero") or {}).get("kpis")
        self.hero_kpi_signature = self._kpi_signature_from_items(hero_kpis)

        head = self._render_head(title, theme_tokens)
        body = self._render_body()
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
        return f"""
<head>
  <meta charset="utf-8" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{self._escape_html(title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-sankey@4"></script>
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
  <script>
    document.documentElement.classList.remove('no-js');
    document.documentElement.classList.add('js-ready');
  </script>
</head>""".strip()

    def _render_body(self) -> str:
        """
        拼装<body>结构，包含头部、导航、章节和脚本。

        返回:
            str: body片段HTML。
        """
        header = self._render_header()
        cover = self._render_cover()
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
{cover}
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
    <!-- <button id="export-btn" class="action-btn" type="button">⬇️ 导出PDF</button> -->
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

        返回:
            str: hero区HTML，若无数据则为空字符串。
        """
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
            list[dict]: 规范化后的目录条目，包含level/text/anchor。
        """
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
        blocks_html = self._render_blocks(chapter.get("blocks", []))
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
        latex = self._escape_html(block.get("latex", ""))
        return f'<div class="math-block">$$ {latex} $$</div>'

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

    def _render_widget(self, block: Dict[str, Any]) -> str:
        """
        渲染Chart.js等交互组件的占位容器，并记录配置JSON。

        参数:
            block: widget类型的block，包含widgetId/props/data。

        返回:
            str: 含canvas与配置脚本的HTML。
        """
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
        fallback_html = self._render_widget_fallback(normalized_data)
        return f"""
        <div class="chart-card">
          {title_html}
          <div class="chart-container">
            <canvas id="{canvas_id}" data-config-id="{config_id}"></canvas>
          </div>
          {fallback_html}
        </div>
        """

    def _render_widget_fallback(self, data: Dict[str, Any]) -> str:
        """渲染图表数据的文本兜底视图，避免Chart.js加载失败时出现空白"""
        if not isinstance(data, dict):
            return ""
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
        <div class="chart-fallback" data-prebuilt="true">
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
            latex = math_mark.get("value")
            if not isinstance(latex, str) or not latex.strip():
                latex = text_value
            return f'<span class="math-inline">\\( {self._escape_html(latex)} \\)</span>'
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
        colors = tokens.get("colors") or {}
        typography = tokens.get("typography") or {}
        fonts = tokens.get("fonts") or typography.get("fontFamily") or {}
        spacing = tokens.get("spacing") or {}
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
  }}
  .chapter h2,
  .chapter h3,
  .chapter h4 {{
    break-after: avoid;
    page-break-after: avoid;
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
const STABLE_CHART_TYPES = ['line', 'bar'];
const CHART_TYPE_LABELS = {
  line: '折线图',
  bar: '柱状图',
  doughnut: '圆环图',
  pie: '饼图',
  radar: '雷达图',
  polarArea: '极地区域图'
};

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
    const card = canvas.closest('.chart-card') || canvas.parentElement;
    const optionsTemplate = buildChartOptions(payload);
    const desiredType = chartTypes[0];
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
  const pdf = new jspdf.jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pxWidth = Math.max(target.scrollWidth, document.documentElement.scrollWidth);
  const restoreButton = () => {
    if (exportBtn) {
      exportBtn.disabled = false;
    }
  };
  let renderTask;
  try {
    renderTask = pdf.html(target, {
      x: 8,
      y: 12,
      width: pageWidth - 16,
      margin: [12, 12, 20, 12],
      autoPaging: 'text',
      windowWidth: pxWidth,
      pagebreak: {
        mode: ['css', 'legacy'],
        avoid: ['.chapter > *', '.callout', '.chart-card', '.table-wrap', '.kpi-grid', '.hero-section']
      },
      html2canvas: {
        scale: 0.72,
        useCORS: true,
        logging: false
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


__all__ = ["HTMLRenderer"]
