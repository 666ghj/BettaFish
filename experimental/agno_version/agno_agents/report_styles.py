# agno_agents/report_styles.py
# 专业报告 HTML 渲染样式

# Chart.js 库：用于渲染 <chart-card> 组件
# 通过 CDN 加载，离线时有 fallback 提示
CHART_JS_LIBS = """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
// Chart.js 默认配置 - 统一主题
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif';
    Chart.defaults.font.size = 13;
    Chart.defaults.color = '#4b5563';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.padding = 15;
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(30, 58, 138, 0.95)';
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: '600' };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
}
</script>
"""

REPORT_CSS = """
<style>
:root {
    --primary: #1e3a8a;
    --primary-light: #3b82f6;
    --accent: #f59e0b;
    --text: #1f2937;
    --text-secondary: #6b7280;
    --bg: #ffffff;
    --bg-alt: #f9fafb;
    --border: #e5e7eb;
    --code-bg: #f3f4f6;
    --table-stripe: #f9fafb;
    --quote-bg: #eff6ff;
    --quote-border: #3b82f6;
}

* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
    font-size: 16px;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue",
                 Helvetica, Arial, sans-serif;
    line-height: 1.75;
    color: var(--text);
    background: var(--bg);
    max-width: 900px;
    margin: 0 auto;
    padding: 60px 40px;
    counter-reset: chapter;
}

/* === 封面 === */
.cover {
    text-align: center;
    padding: 120px 0 100px;
    border-bottom: 3px double var(--primary);
    margin-bottom: 80px;
}

.cover .badge {
    display: inline-block;
    padding: 6px 18px;
    background: var(--primary);
    color: white;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
    border-radius: 20px;
    margin-bottom: 30px;
    text-transform: uppercase;
}

.cover h1 {
    font-size: 42px;
    margin: 20px 0;
    color: var(--primary);
    font-weight: 700;
    line-height: 1.3;
    border: none;
}

.cover .subtitle {
    font-size: 18px;
    color: var(--text-secondary);
    margin-top: 30px;
    font-weight: 400;
}

.cover .meta {
    margin-top: 60px;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 2;
}

.cover .meta strong {
    color: var(--text);
}

/* === 标题 === */
h1 {
    font-size: 32px;
    color: var(--primary);
    margin-top: 80px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 3px solid var(--primary);
    font-weight: 700;
    counter-increment: chapter;
}

h1::before {
    content: "第 " counter(chapter, cjk-decimal) " 章  ";
    color: var(--accent);
    font-weight: 800;
}

h1.no-counter::before {
    content: none;
}

h2 {
    font-size: 24px;
    color: var(--primary);
    margin-top: 48px;
    margin-bottom: 18px;
    padding-left: 14px;
    border-left: 5px solid var(--primary-light);
    font-weight: 600;
}

h3 {
    font-size: 19px;
    color: var(--text);
    margin-top: 36px;
    margin-bottom: 14px;
    font-weight: 600;
}

h4 {
    font-size: 16px;
    color: var(--text);
    margin-top: 28px;
    margin-bottom: 10px;
    font-weight: 600;
}

p {
    margin: 16px 0;
    text-align: justify;
    text-indent: 2em;
}

/* === 列表 === */
ul, ol {
    margin: 16px 0;
    padding-left: 30px;
}

li {
    margin: 8px 0;
    line-height: 1.8;
}

li > p {
    text-indent: 0;
    margin: 4px 0;
}

/* === 表格 === */
table {
    width: 100%;
    margin: 24px 0;
    border-collapse: collapse;
    font-size: 14px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    border-radius: 6px;
    overflow: hidden;
}

thead {
    background: var(--primary);
    color: white;
}

th {
    padding: 14px 16px;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.5px;
}

td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
}

tbody tr:nth-child(even) {
    background: var(--table-stripe);
}

tbody tr:hover {
    background: #fef3c7;
    transition: background 0.2s;
}

/* === 引用 === */
blockquote {
    margin: 24px 0;
    padding: 18px 24px;
    background: var(--quote-bg);
    border-left: 4px solid var(--quote-border);
    color: #1e40af;
    font-style: normal;
    border-radius: 0 6px 6px 0;
}

blockquote p {
    margin: 8px 0;
    text-indent: 0;
}

blockquote p:first-child::before {
    content: "❝ ";
    color: var(--primary-light);
    font-size: 20px;
    font-weight: bold;
}

/* === 代码 === */
code {
    background: var(--code-bg);
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "SF Mono", Monaco, Consolas, "Liberation Mono", monospace;
    font-size: 0.9em;
    color: #c7254e;
}

pre {
    background: #1e293b;
    color: #e2e8f0;
    padding: 18px 24px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 20px 0;
}

pre code {
    background: none;
    color: inherit;
    padding: 0;
}

/* === 强调 === */
strong {
    color: var(--primary);
    font-weight: 600;
}

em {
    color: var(--accent);
    font-style: normal;
    font-weight: 500;
}

/* === 链接 === */
a {
    color: var(--primary-light);
    text-decoration: none;
    border-bottom: 1px dashed var(--primary-light);
    transition: all 0.2s;
}

a:hover {
    color: var(--accent);
    border-bottom-color: var(--accent);
}

/* === 分隔符 === */
hr {
    border: none;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 60px 0;
}

/* === 目录 === */
.toc {
    background: var(--bg-alt);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 28px 36px;
    margin: 40px 0 60px;
}

.toc h2 {
    margin-top: 0;
    border: none;
    padding: 0;
    text-align: center;
    color: var(--primary);
}

.toc ul {
    list-style: none;
    padding-left: 0;
}

.toc li {
    margin: 10px 0;
    padding: 6px 0;
    border-bottom: 1px dotted var(--border);
}

.toc a {
    border: none;
    color: var(--text);
    font-weight: 500;
}

.toc a:hover {
    color: var(--primary);
}

.toc .toc-page {
    float: right;
    color: var(--text-secondary);
    font-size: 13px;
}

/* === 关键发现卡片 === */
.key-finding {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border-left: 5px solid var(--accent);
    padding: 20px 28px;
    margin: 24px 0;
    border-radius: 0 8px 8px 0;
}

.key-finding-title {
    font-weight: 700;
    color: #92400e;
    margin-bottom: 8px;
    font-size: 14px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* === 数据卡片 === */
.data-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 20px;
    margin: 30px 0;
}

.data-card {
    background: var(--bg-alt);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
}

.data-card .number {
    font-size: 32px;
    font-weight: 700;
    color: var(--primary);
    display: block;
}

.data-card .label {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 8px;
}

/* === 附录 === */
.appendix {
    margin-top: 100px;
    padding-top: 40px;
    border-top: 2px dashed var(--border);
    font-size: 14px;
    color: var(--text-secondary);
}

.appendix h2 {
    color: var(--text-secondary);
}

.forum-entry {
    margin: 12px 0;
    padding: 10px 16px;
    background: var(--bg-alt);
    border-left: 3px solid var(--border);
    border-radius: 0 4px 4px 0;
    font-size: 13px;
    line-height: 1.6;
}

.forum-entry.host {
    border-left-color: var(--accent);
    background: #fef9c3;
}

.forum-entry .speaker {
    font-weight: 600;
    color: var(--primary);
}

/* === 页脚 === */
.footer {
    margin-top: 80px;
    padding-top: 30px;
    border-top: 1px solid var(--border);
    text-align: center;
    font-size: 13px;
    color: var(--text-secondary);
}

/* === 打印优化 === */
@media print {
    body {
        max-width: none;
        padding: 0;
    }
    h1 {
        page-break-before: always;
    }
    h1, h2 {
        page-break-after: avoid;
    }
    table, blockquote, pre {
        page-break-inside: avoid;
    }
}

/* ======================================================= */
/* ============ 可视化组件（Chart/KPI/Callout等）============= */
/* ======================================================= */

/* === Chart 卡片 === */
.chart-card {
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px 28px;
    margin: 32px 0;
    box-shadow: 0 2px 8px rgba(30, 58, 138, 0.06);
}

.chart-card--error {
    background: #fef2f2;
    border-color: #fca5a5;
}

.chart-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--primary-light);
    text-align: center;
}

.chart-canvas-wrap {
    position: relative;
    height: 320px;
    width: 100%;
}

.chart-error {
    color: #dc2626;
    font-size: 13px;
    margin: 10px 0;
}

/* === KPI 网格 === */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin: 28px 0;
}

.kpi-card {
    background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 22px 20px;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
    position: relative;
    overflow: hidden;
}

.kpi-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 4px;
    background: var(--primary);
}

.kpi-card--up::before { background: #10b981; }
.kpi-card--down::before { background: #ef4444; }
.kpi-card--neutral::before { background: var(--primary-light); }

.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(30, 58, 138, 0.1);
}

.kpi-label {
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 500;
    margin-bottom: 10px;
    letter-spacing: 0.5px;
}

.kpi-value {
    font-size: 30px;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}

.kpi-unit {
    font-size: 16px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-left: 2px;
}

.kpi-delta {
    margin-top: 8px;
    font-size: 13px;
    font-weight: 600;
}

.kpi-delta--up { color: #059669; }
.kpi-delta--down { color: #dc2626; }
.kpi-delta--neutral { color: var(--text-secondary); }

/* === Callout 提示框 === */
.callout {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 18px 22px;
    margin: 24px 0;
    border-radius: 10px;
    border-left: 5px solid;
}

.callout--info {
    background: #eff6ff;
    border-color: #3b82f6;
    color: #1e3a8a;
}

.callout--insight {
    background: #f0f9ff;
    border-color: #0ea5e9;
    color: #075985;
}

.callout--warning {
    background: #fffbeb;
    border-color: #f59e0b;
    color: #78350f;
}

.callout--danger {
    background: #fef2f2;
    border-color: #ef4444;
    color: #7f1d1d;
}

.callout--success {
    background: #f0fdf4;
    border-color: #10b981;
    color: #064e3b;
}

.callout-icon {
    font-size: 24px;
    flex-shrink: 0;
    line-height: 1;
    padding-top: 2px;
}

.callout-body {
    flex: 1;
    line-height: 1.7;
}

.callout-title {
    font-weight: 700;
    margin-bottom: 6px;
    font-size: 15px;
}

.callout-body p {
    text-indent: 0;
    margin: 6px 0;
}

.callout-body p:first-child { margin-top: 0; }
.callout-body p:last-child { margin-bottom: 0; }

/* === 信息源矩阵 === */
.info-matrix-wrap {
    margin: 32px 0;
    background: var(--bg-alt);
    border-radius: 10px;
    padding: 24px 28px;
    border: 1px solid var(--border);
}

.matrix-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 16px;
    text-align: center;
}

.info-matrix {
    width: 100%;
    margin: 0 0 12px 0;
}

.info-matrix .matrix-td {
    text-align: center;
}

.matrix-cell {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 14px;
    min-width: 56px;
}

.matrix-primary { background: #dcfce7; color: #15803d; }
.matrix-strong { background: #dcfce7; color: #15803d; }
.matrix-secondary { background: #fef3c7; color: #92400e; }
.matrix-weak { background: #fee2e2; color: #b91c1c; }
.matrix-none { background: #f3f4f6; color: #9ca3af; }

.matrix-legend {
    display: flex;
    gap: 16px;
    justify-content: center;
    font-size: 12px;
    padding-top: 12px;
    border-top: 1px dashed var(--border);
}

.matrix-legend span {
    padding: 3px 8px;
    border-radius: 3px;
    font-weight: 600;
}

/* === 时间线 === */
.timeline-wrap {
    margin: 32px 0;
    padding: 24px;
    background: var(--bg-alt);
    border-radius: 10px;
}

.timeline-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 20px;
    text-align: center;
}

.timeline {
    position: relative;
    padding-left: 30px;
}

.timeline::before {
    content: "";
    position: absolute;
    left: 10px;
    top: 10px;
    bottom: 10px;
    width: 2px;
    background: linear-gradient(to bottom, var(--primary-light), var(--border));
}

.timeline-event {
    position: relative;
    padding-bottom: 24px;
}

.timeline-marker {
    position: absolute;
    left: -25px;
    top: 4px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--primary);
    border: 3px solid white;
    box-shadow: 0 0 0 2px var(--primary);
    z-index: 1;
}

.timeline-event--crisis .timeline-marker { background: #ef4444; box-shadow: 0 0 0 2px #ef4444; }
.timeline-event--release .timeline-marker { background: #10b981; box-shadow: 0 0 0 2px #10b981; }
.timeline-event--update .timeline-marker { background: #f59e0b; box-shadow: 0 0 0 2px #f59e0b; }

.timeline-date {
    font-size: 13px;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 4px;
    font-variant-numeric: tabular-nums;
}

.timeline-text {
    font-size: 15px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.6;
}

.timeline-detail {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 6px;
    line-height: 1.6;
}

/* === 用户原声卡片 === */
.quote-card {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border-left: 4px solid var(--primary-light);
    border-radius: 0 10px 10px 0;
    padding: 22px 26px;
    margin: 24px 0;
    position: relative;
}

.quote-mark {
    position: absolute;
    top: 8px;
    left: 12px;
    font-size: 48px;
    color: var(--primary-light);
    opacity: 0.25;
    line-height: 1;
    font-family: Georgia, serif;
}

.quote-text {
    padding-left: 40px;
    font-size: 16px;
    line-height: 1.75;
    color: #1e3a8a;
    font-style: italic;
}

.quote-meta {
    padding-left: 40px;
    margin-top: 12px;
    font-size: 13px;
    color: var(--text-secondary);
    font-style: normal;
}

.quote-author { color: var(--primary); font-weight: 600; }
.quote-source { color: var(--text-secondary); }
.quote-likes { color: #dc2626; font-weight: 600; }

/* === 响应式 === */
@media (max-width: 768px) {
    body {
        padding: 30px 20px;
    }
    .cover {
        padding: 60px 0;
    }
    .cover h1 {
        font-size: 28px;
    }
    h1 {
        font-size: 24px;
    }
    h2 {
        font-size: 20px;
    }
    table {
        font-size: 12px;
    }
    th, td {
        padding: 8px 10px;
    }
    .kpi-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .kpi-value {
        font-size: 24px;
    }
    .chart-canvas-wrap {
        height: 260px;
    }
}
</style>
"""
