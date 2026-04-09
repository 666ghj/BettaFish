# agno_agents/report_blocks.py
# 自定义可视化块解析器与渲染器
#
# LLM 在章节中可以输出以下自定义标签，本模块负责：
# 1. 在 Markdown → HTML 转换前，先把这些标签替换成 HTML 占位符
# 2. 保护占位符不被 markdown 解析器破坏
# 3. 最终替换为完整的 HTML 组件
#
# 支持的自定义标签：
#   <chart-card title="..." type="bar|line|pie|doughnut|radar">...JSON...</chart-card>
#   <kpi-grid>...JSON array...</kpi-grid>
#   <callout type="info|warning|danger|success" title="...">...markdown...</callout>
#   <info-matrix title="...">...JSON...</info-matrix>
#   <timeline title="...">...JSON array...</timeline>
#   <quote-card source="..." author="..." likes="123">...text...</quote-card>

from __future__ import annotations
import json
import re
import html as html_lib
from typing import Dict, Tuple, List


# ===== 占位符机制 =====
# 避免 markdown 库把我们的 HTML 当成普通文本破坏

class BlockCollector:
    """收集所有自定义块，生成占位符，最后一次性替换"""
    def __init__(self):
        self.blocks: Dict[str, str] = {}
        self._counter = 0

    def add(self, html: str) -> str:
        self._counter += 1
        # 用非常独特的字符串作为占位符，markdown 不会处理
        # 前后加换行，保证成为独立段落
        placeholder = f"\n\nXMIROFISH_BLOCK_{self._counter:04d}_XEND\n\n"
        self.blocks[f"XMIROFISH_BLOCK_{self._counter:04d}_XEND"] = html
        return placeholder

    def restore(self, html: str) -> str:
        # markdown 会把占位符包进 <p></p>，需要先剥掉
        for token, block_html in self.blocks.items():
            # 可能的形式：<p>TOKEN</p>，直接 TOKEN
            html = re.sub(rf"<p>\s*{token}\s*</p>", block_html, html)
            html = html.replace(token, block_html)
        return html


# ===== 单个块的渲染函数 =====

_chart_counter = [0]


def render_chart_card(json_config: str, title: str = "") -> str:
    """渲染一个 Chart.js 图表卡片"""
    _chart_counter[0] += 1
    chart_id = f"mchart_{_chart_counter[0]}"
    title_html = f'<div class="chart-title">{html_lib.escape(title)}</div>' if title else ""

    # 清理并校验 JSON
    try:
        config = json.loads(json_config.strip())
    except json.JSONDecodeError:
        # 回退：显示原始 JSON 和错误提示
        return f"""
<div class="chart-card chart-card--error">
    {title_html}
    <div class="chart-error">⚠️ 图表配置解析失败，原始数据：</div>
    <pre>{html_lib.escape(json_config[:500])}</pre>
</div>
"""

    # 注入默认样式
    if "options" not in config:
        config["options"] = {}
    config["options"].setdefault("responsive", True)
    config["options"].setdefault("maintainAspectRatio", False)
    config["options"].setdefault("plugins", {}).setdefault("legend", {}).setdefault("position", "bottom")

    # 颜色美化：如果数据集没有颜色，用我们的主题色
    palette = ["#4A90E2", "#E85D75", "#50C878", "#FFB347", "#9B59B6", "#3498DB", "#E67E22", "#16A085"]
    data = config.get("data", {})
    datasets = data.get("datasets", [])
    chart_type = config.get("type", "bar")

    for i, ds in enumerate(datasets):
        if chart_type in ("pie", "doughnut", "polarArea"):
            if "backgroundColor" not in ds and data.get("labels"):
                ds["backgroundColor"] = palette[: len(data["labels"])]
        else:
            if "backgroundColor" not in ds:
                ds["backgroundColor"] = palette[i % len(palette)]
            if "borderColor" not in ds and chart_type in ("line", "radar"):
                ds["borderColor"] = palette[i % len(palette)]
                ds["fill"] = False
                ds["tension"] = 0.3

    config_json = json.dumps(config, ensure_ascii=False)

    return f"""
<div class="chart-card">
    {title_html}
    <div class="chart-canvas-wrap">
        <canvas id="{chart_id}"></canvas>
    </div>
    <script>
        (function() {{
            function initChart() {{
                if (typeof Chart === 'undefined') {{
                    setTimeout(initChart, 100);
                    return;
                }}
                const ctx = document.getElementById('{chart_id}');
                if (!ctx) return;
                new Chart(ctx, {config_json});
            }}
            initChart();
        }})();
    </script>
</div>
"""


def render_kpi_grid(json_items: str) -> str:
    """渲染 KPI 数据卡片网格"""
    try:
        items = json.loads(json_items.strip())
    except json.JSONDecodeError:
        return f'<div class="kpi-error">⚠️ KPI 数据解析失败</div>'

    if not isinstance(items, list):
        return '<div class="kpi-error">⚠️ KPI 需要数组格式</div>'

    cards = []
    for item in items:
        label = html_lib.escape(str(item.get("label", "")))
        value = html_lib.escape(str(item.get("value", "")))
        unit = html_lib.escape(str(item.get("unit", "")))
        delta = html_lib.escape(str(item.get("delta", "")))
        tone = str(item.get("tone", "neutral")).lower()
        if tone not in ("up", "down", "neutral"):
            tone = "neutral"

        delta_html = ""
        if delta:
            icon = "▲" if tone == "up" else "▼" if tone == "down" else "●"
            delta_html = f'<div class="kpi-delta kpi-delta--{tone}">{icon} {delta}</div>'

        unit_html = f'<span class="kpi-unit">{unit}</span>' if unit else ""

        cards.append(f"""
<div class="kpi-card kpi-card--{tone}">
    <div class="kpi-label">{label}</div>
    <div class="kpi-value">{value}{unit_html}</div>
    {delta_html}
</div>
""")

    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def render_callout(content: str, callout_type: str = "info", title: str = "") -> str:
    """渲染提示框"""
    callout_type = callout_type.lower()
    if callout_type not in ("info", "warning", "danger", "success", "insight"):
        callout_type = "info"

    icons = {
        "info": "💡",
        "warning": "⚠️",
        "danger": "🚨",
        "success": "✅",
        "insight": "🔍",
    }
    icon = icons.get(callout_type, "💡")

    # 把内容里的 markdown 先做简单转换（**bold**, *italic*）
    content = content.strip()
    content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
    content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)
    content = re.sub(r"\n\n", "</p><p>", content)
    content = f"<p>{content}</p>"

    title_html = f'<div class="callout-title">{html_lib.escape(title)}</div>' if title else ""

    return f"""
<div class="callout callout--{callout_type}">
    <div class="callout-icon">{icon}</div>
    <div class="callout-body">
        {title_html}
        {content}
    </div>
</div>
"""


def render_info_matrix(json_data: str, title: str = "") -> str:
    """渲染信息源覆盖矩阵"""
    try:
        data = json.loads(json_data.strip())
    except json.JSONDecodeError:
        return '<div class="matrix-error">⚠️ 矩阵数据解析失败</div>'

    headers = data.get("headers", [])
    rows = data.get("rows", [])
    if not headers or not rows:
        return '<div class="matrix-error">⚠️ 矩阵缺少 headers 或 rows</div>'

    # cell 值的图标映射
    level_map = {
        "primary": ('<span class="matrix-cell matrix-primary">★★★</span>', "主力数据源"),
        "strong": ('<span class="matrix-cell matrix-strong">★★★</span>', "主力数据源"),
        "secondary": ('<span class="matrix-cell matrix-secondary">★★</span>', "部分覆盖"),
        "partial": ('<span class="matrix-cell matrix-secondary">★★</span>', "部分覆盖"),
        "weak": ('<span class="matrix-cell matrix-weak">★</span>', "弱覆盖"),
        "none": ('<span class="matrix-cell matrix-none">—</span>', "未覆盖"),
    }

    title_html = f'<div class="matrix-title">{html_lib.escape(title)}</div>' if title else ""

    head_cells = "".join(f"<th>{html_lib.escape(str(h))}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = [f"<td><strong>{html_lib.escape(str(row.get('dimension', '')))}</strong></td>"]
        for agent in headers[1:]:
            level = str(row.get(agent.lower(), "none")).lower()
            cell_html, _ = level_map.get(level, level_map["none"])
            cells.append(f"<td class='matrix-td'>{cell_html}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
<div class="info-matrix-wrap">
    {title_html}
    <table class="info-matrix">
        <thead><tr>{head_cells}</tr></thead>
        <tbody>{"".join(body_rows)}</tbody>
    </table>
    <div class="matrix-legend">
        <span class="matrix-primary">★★★ 主力</span>
        <span class="matrix-secondary">★★ 部分</span>
        <span class="matrix-weak">★ 弱覆盖</span>
        <span class="matrix-none">— 无</span>
    </div>
</div>
"""


def render_timeline(json_items: str, title: str = "") -> str:
    """渲染事件时间线"""
    try:
        items = json.loads(json_items.strip())
    except json.JSONDecodeError:
        return '<div class="timeline-error">⚠️ 时间线数据解析失败</div>'

    if not isinstance(items, list):
        return '<div class="timeline-error">⚠️ 时间线需要数组格式</div>'

    title_html = f'<div class="timeline-title">{html_lib.escape(title)}</div>' if title else ""

    events = []
    for item in items:
        date = html_lib.escape(str(item.get("date", "")))
        event = html_lib.escape(str(item.get("event", "")))
        detail = item.get("detail", "")
        if detail:
            detail = f'<div class="timeline-detail">{html_lib.escape(str(detail))}</div>'
        event_type = str(item.get("type", "default")).lower()

        events.append(f"""
<div class="timeline-event timeline-event--{event_type}">
    <div class="timeline-marker"></div>
    <div class="timeline-content">
        <div class="timeline-date">{date}</div>
        <div class="timeline-text">{event}</div>
        {detail}
    </div>
</div>
""")

    return f"""
<div class="timeline-wrap">
    {title_html}
    <div class="timeline">{"".join(events)}</div>
</div>
"""


def render_quote_card(content: str, source: str = "", author: str = "", likes: str = "") -> str:
    """渲染用户原声卡片"""
    content = html_lib.escape(content.strip())
    source = html_lib.escape(source)
    author = html_lib.escape(author)

    meta = []
    if author:
        meta.append(f'<span class="quote-author">@{author}</span>')
    if source:
        meta.append(f'<span class="quote-source">{source}</span>')
    if likes:
        meta.append(f'<span class="quote-likes">❤ {html_lib.escape(str(likes))}</span>')
    meta_html = f'<div class="quote-meta">{" · ".join(meta)}</div>' if meta else ""

    return f"""
<div class="quote-card">
    <div class="quote-mark">❝</div>
    <div class="quote-text">{content}</div>
    {meta_html}
</div>
"""


# ===== 总解析器 =====

def preprocess_custom_blocks(markdown_text: str) -> Tuple[str, BlockCollector]:
    """
    扫描 markdown 文本，把所有自定义块替换为占位符，同时记录对应的 HTML。
    返回 (替换后的 markdown, collector)。
    """
    collector = BlockCollector()

    # chart-card
    def replace_chart(m):
        attrs = _parse_attrs(m.group(1))
        title = attrs.get("title", "")
        html = render_chart_card(m.group(2), title=title)
        return collector.add(html)

    markdown_text = re.sub(
        r"<chart-card([^>]*)>([\s\S]*?)</chart-card>",
        replace_chart,
        markdown_text,
    )

    # kpi-grid
    def replace_kpi(m):
        html = render_kpi_grid(m.group(1))
        return collector.add(html)

    markdown_text = re.sub(
        r"<kpi-grid[^>]*>([\s\S]*?)</kpi-grid>",
        replace_kpi,
        markdown_text,
    )

    # callout
    def replace_callout(m):
        attrs = _parse_attrs(m.group(1))
        callout_type = attrs.get("type", "info")
        title = attrs.get("title", "")
        html = render_callout(m.group(2), callout_type=callout_type, title=title)
        return collector.add(html)

    markdown_text = re.sub(
        r"<callout([^>]*)>([\s\S]*?)</callout>",
        replace_callout,
        markdown_text,
    )

    # info-matrix
    def replace_matrix(m):
        attrs = _parse_attrs(m.group(1))
        title = attrs.get("title", "")
        html = render_info_matrix(m.group(2), title=title)
        return collector.add(html)

    markdown_text = re.sub(
        r"<info-matrix([^>]*)>([\s\S]*?)</info-matrix>",
        replace_matrix,
        markdown_text,
    )

    # timeline
    def replace_timeline(m):
        attrs = _parse_attrs(m.group(1))
        title = attrs.get("title", "")
        html = render_timeline(m.group(2), title=title)
        return collector.add(html)

    markdown_text = re.sub(
        r"<timeline([^>]*)>([\s\S]*?)</timeline>",
        replace_timeline,
        markdown_text,
    )

    # quote-card
    def replace_quote(m):
        attrs = _parse_attrs(m.group(1))
        html = render_quote_card(
            content=m.group(2),
            source=attrs.get("source", ""),
            author=attrs.get("author", ""),
            likes=attrs.get("likes", ""),
        )
        return collector.add(html)

    markdown_text = re.sub(
        r"<quote-card([^>]*)>([\s\S]*?)</quote-card>",
        replace_quote,
        markdown_text,
    )

    return markdown_text, collector


def _parse_attrs(attr_str: str) -> Dict[str, str]:
    """解析 HTML 属性，形如 ' type="bar" title="hello"'"""
    attrs = {}
    for m in re.finditer(r'(\w+)=[\'"]([^\'"]*)[\'"]', attr_str):
        attrs[m.group(1)] = m.group(2)
    return attrs
