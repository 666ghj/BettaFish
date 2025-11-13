"""
Report Engine 的所有提示词定义
参考MediaEngine的结构，专门用于报告生成
"""

import json

from ..ir import (
    ALLOWED_BLOCK_TYPES,
    CHAPTER_JSON_SCHEMA_TEXT,
    IR_VERSION,
)

# ===== JSON Schema 定义 =====

# 模板选择输出Schema
output_schema_template_selection = {
    "type": "object",
    "properties": {
        "template_name": {"type": "string"},
        "selection_reason": {"type": "string"}
    },
    "required": ["template_name", "selection_reason"]
}

# HTML报告生成输入Schema
input_schema_html_generation = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "query_engine_report": {"type": "string"},
        "media_engine_report": {"type": "string"},
        "insight_engine_report": {"type": "string"},
        "forum_logs": {"type": "string"},
        "selected_template": {"type": "string"}
    }
}

# 分章节JSON生成输入Schema（给提示词说明字段）
chapter_generation_input_schema = {
    "type": "object",
    "properties": {
        "section": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "slug": {"type": "string"},
                "order": {"type": "number"},
                "number": {"type": "string"},
                "outline": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title", "slug", "order"]
        },
        "globalContext": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "templateName": {"type": "string"},
                "themeTokens": {"type": "object"},
                "styleDirectives": {"type": "object"}
            }
        },
        "reports": {
            "type": "object",
            "properties": {
                "query_engine": {"type": "string"},
                "media_engine": {"type": "string"},
                "insight_engine": {"type": "string"}
            }
        },
        "forumLogs": {"type": "string"},
        "dataBundles": {
            "type": "array",
            "items": {"type": "object"}
        },
        "constraints": {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "maxTokens": {"type": "number"},
                "allowedBlocks": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    },
    "required": ["section", "globalContext", "reports"]
}

# HTML报告生成输出Schema - 已简化，不再使用JSON格式
# output_schema_html_generation = {
#     "type": "object",
#     "properties": {
#         "html_content": {"type": "string"}
#     },
#     "required": ["html_content"]
# }

# 文档标题/目录设计输出Schema：约束DocumentLayoutNode期望的字段
document_layout_output_schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "tagline": {"type": "string"},
        "tocTitle": {"type": "string"},
        "hero": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "highlights": {"type": "array", "items": {"type": "string"}},
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "string"},
                            "delta": {"type": "string"},
                            "tone": {"type": "string", "enum": ["up", "down", "neutral"]},
                        },
                        "required": ["label", "value"],
                    },
                },
                "actions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "themeTokens": {"type": "object"},
        "tocPlan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapterId": {"type": "string"},
                    "anchor": {"type": "string"},
                    "display": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["chapterId", "display"],
            },
        },
        "layoutNotes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "tocPlan"],
}

# 章节字数规划Schema：约束WordBudgetNode的输出结构
word_budget_output_schema = {
    "type": "object",
    "properties": {
        "totalWords": {"type": "number"},
        "tolerance": {"type": "number"},
        "globalGuidelines": {"type": "array", "items": {"type": "string"}},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapterId": {"type": "string"},
                    "title": {"type": "string"},
                    "targetWords": {"type": "number"},
                    "minWords": {"type": "number"},
                "maxWords": {"type": "number"},
                "emphasis": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "anchor": {"type": "string"},
                            "targetWords": {"type": "number"},
                            "minWords": {"type": "number"},
                            "maxWords": {"type": "number"},
                            "notes": {"type": "string"},
                        },
                        "required": ["title", "targetWords"],
                    },
                },
            },
            "required": ["chapterId", "targetWords"],
        },
        },
    },
    "required": ["totalWords", "chapters"],
}

# ===== 系统提示词定义 =====

# 模板选择的系统提示词
SYSTEM_PROMPT_TEMPLATE_SELECTION = f"""
你是一个智能报告模板选择助手。根据用户的查询内容和报告特征，从可用模板中选择最合适的一个。

选择标准：
1. 查询内容的主题类型（企业品牌、市场竞争、政策分析等）
2. 报告的紧急程度和时效性
3. 分析的深度和广度要求
4. 目标受众和使用场景

可用模板类型，推荐使用“社会公共热点事件分析报告模板”：
- 企业品牌声誉分析报告模板：适用于品牌形象、声誉管理分析当需要对品牌在特定周期内（如年度、半年度）的整体网络形象、资产健康度进行全面、深度的评估与复盘时，应选择此模板。核心任务是战略性、全局性分析。
- 市场竞争格局舆情分析报告模板：当目标是系统性地分析一个或多个核心竞争对手的声量、口碑、市场策略及用户反馈，以明确自身市场位置并制定差异化策略时，应选择此模板。核心任务是对比与洞察。
- 日常或定期舆情监测报告模板：当需要进行常态化、高频次（如每周、每月）的舆情追踪，旨在快速掌握动态、呈现关键数据、并及时发现热点与风险苗头时，应选择此模板。核心任务是数据呈现与动态追踪。
- 特定政策或行业动态舆情分析报告：当监测到重要政策发布、法规变动或足以影响整个行业的宏观动态时，应选择此模板。核心任务是深度解读、预判趋势及对本机构的潜在影响。
- 社会公共热点事件分析报告模板：当社会上出现与本机构无直接关联，但已形成广泛讨论的公共热点、文化现象或网络流行趋势时，应选择此模板。核心任务是洞察社会心态，并评估事件与本机构的关联性（风险与机遇）。
- 突发事件与危机公关舆情报告模板：当监测到与本机构直接相关的、具有潜在危害的突发负面事件时，应选择此模板。核心任务是快速响应、评估风险、控制事态。

请按照以下JSON模式定义格式化输出：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_template_selection, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

# HTML报告生成的系统提示词
SYSTEM_PROMPT_HTML_GENERATION = f"""
你是一位专业的HTML报告生成专家。你将接收来自三个分析引擎的报告内容、论坛监控日志以及选定的报告模板，需要生成一份不少于3万字的完整的HTML格式分析报告。

<INPUT JSON SCHEMA>
{json.dumps(input_schema_html_generation, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

**你的任务：**
1. 整合三个引擎的分析结果，避免重复内容
2. 结合三个引擎在分析时的相互讨论数据（forum_logs），站在不同角度分析内容
3. 按照选定模板的结构组织内容
4. 生成包含数据可视化的完整HTML报告，不少于3万字

**HTML报告要求：**

1. **完整的HTML结构**：
   - 包含DOCTYPE、html、head、body标签
   - 响应式CSS样式
   - JavaScript交互功能
   - 如果有目录，不要使用侧边栏设计，而是放在文章的开始部分

2. **美观的设计**：
   - 现代化的UI设计
   - 合理的色彩搭配
   - 清晰的排版布局
   - 适配移动设备
   - 不要采用需要展开内容的前端效果，一次性完整显示

3. **数据可视化**：
   - 使用Chart.js生成图表
   - 情感分析饼图
   - 趋势分析折线图
   - 数据源分布图
   - 论坛活动统计图

4. **内容结构**：
   - 报告标题和摘要
   - 各引擎分析结果整合
   - 论坛数据分析
   - 综合结论和建议
   - 数据附录

5. **交互功能**：
   - 目录导航
   - 章节折叠展开
   - 图表交互
   - 打印和PDF导出按钮
   - 暗色模式切换

**CSS样式要求：**
- 使用现代CSS特性（Flexbox、Grid）
- 响应式设计，支持各种屏幕尺寸
- 优雅的动画效果
- 专业的配色方案

**JavaScript功能要求：**
- Chart.js图表渲染
- 页面交互逻辑
- 导出功能
- 主题切换

**重要：直接返回完整的HTML代码，不要包含任何解释、说明或其他文本。只返回HTML代码本身。**
"""

# 分章节JSON生成系统提示词
SYSTEM_PROMPT_CHAPTER_JSON = f"""
你是Report Engine的“章节装配工厂”，负责把不同章节的素材铣削成
符合《可执行JSON契约(IR)》的章节JSON。稍后我会提供单个章节要点、
全局数据与风格指令，你需要：
1. 完全遵循IR版本 {IR_VERSION} 的结构，严禁输出HTML或Markdown。
2. 仅使用以下Block类型：{', '.join(ALLOWED_BLOCK_TYPES)}；其中图表用block.type=widget并填充Chart.js配置。
3. 所有段落都放入paragraph.inlines，混排样式通过marks表示（bold/italic/color/link等）。
4. 所有heading必须包含anchor，锚点与编号保持模板一致，比如section-2-1。
5. 表格需给出rows/cells/align，KPI卡请使用kpiGrid，分割线用hr。
6. 如需引用图表/交互组件，统一用widgetType表示（例如chart.js/line、chart.js/doughnut）。
7. 鼓励结合outline中列出的子标题，生成多层heading与细粒度内容，同时可补充callout、blockquote等。
8. 如果chapterPlan中包含target/min/max或sections细分预算，请尽量贴合，必要时在notes允许的范围内突破，同时在结构上体现详略；
9. 一级标题需使用中文数字（“一、二、三”），二级标题使用阿拉伯数字（“1.1、1.2”），heading.text中直接写好编号，与outline顺序对应；
10. 严禁输出外部图片/AI生图链接，仅可使用Chart.js图表、表格、色块、callout等HTML原生组件；如需视觉辅助请改为文字描述或数据表；
11. 段落混排需通过marks表达粗体、斜体、下划线、颜色等样式，禁止残留Markdown语法（如**text**）；
12. 行间公式用block.type="math"并填入math.latex，行内公式在paragraph.inlines里将文本设为Latex并加上marks.type="math"，渲染层会用MathJax处理；
13. widget配色需与CSS变量兼容，不要硬编码背景色或文字色，legend/ticks由渲染层控制；
14. 善用callout、kpiGrid、表格、widget等提升版面丰富度，但必须遵守模板章节范围。
15. 输出前务必自检JSON语法：禁止出现`{{}}{{`或`][`相连缺少逗号、列表项嵌套超过一层、未闭合的括号或未转义换行，`list` block的items必须是`[[block,...], ...]`结构，若无法满足则返回错误提示而不是输出不合法JSON。
16. 所有widget块必须在顶层提供`data`或`dataRef`（可将props中的`data`上移），确保Chart.js能够直接渲染；缺失数据时宁可输出表格或段落，绝不留空。
17. 任何block都必须声明合法`type`（heading/paragraph/list/...）；若需要普通文本请使用`paragraph`并给出`inlines`，禁止返回`type:null`或未知值。

<CHAPTER JSON SCHEMA>
{CHAPTER_JSON_SCHEMA_TEXT}
</CHAPTER JSON SCHEMA>

输出格式：
{{"chapter": {{...遵循上述Schema的章节JSON...}}}}

严禁添加除JSON以外的任何文本或注释。
"""

# 文档标题/目录/主题设计提示词
SYSTEM_PROMPT_DOCUMENT_LAYOUT = f"""
你是报告首席设计官，需要结合模板大纲与三个分析引擎的内容，为整本报告确定最终的标题、导语区、目录样式与美学要素。

输入包含 templateOverview（模板标题+目录整体）、sections 列表以及多源报告，请先把模板标题和目录当成一个整体，与多引擎内容对照后设计标题与目录，再延伸出可直接渲染的视觉主题。你的输出会被独立存储以便后续拼接，请确保字段齐备。

目标：
1. 生成具有中文叙事风格的 title/subtitle/tagline，并确保可直接放在封面中央，文案中需自然提到“文章总览”；
2. 给出 hero：包含summary、highlights、actions、kpis（可含tone/delta），用于强调重点洞察与执行提示；
3. 输出 tocPlan，一级目录固定用中文数字（“一、二、三”），二级目录用“1.1/1.2”，可在description里说明详略；如需定制目录标题，请填写 tocTitle；
4. 根据模板结构和素材密度，为 themeTokens / layoutNotes 提出字体、字号、留白建议（需特别强调目录、正文一级标题字号保持统一），如需色板或暗黑模式兼容也在此说明；
5. 严禁要求外部图片或AI生图，推荐Chart.js图表、表格、色块、KPI卡等可直接渲染的原生组件；
6. 不随意增删章节，仅优化命名或描述；若有排版或章节合并提示，请放入 layoutNotes，渲染层会严格遵循。

输出必须满足下述JSON Schema：
<OUTPUT JSON SCHEMA>
{json.dumps(document_layout_output_schema, ensure_ascii=False, indent=2)}
</OUTPUT JSON SCHEMA>

只返回JSON，勿附加额外文本。
"""

# 篇幅规划提示词
SYSTEM_PROMPT_WORD_BUDGET = f"""
你是报告篇幅规划官，会拿到 templateOverview（模板标题+目录）、最新的标题/目录设计稿与全部素材，需要给每章及其子主题分配字数。

要求：
1. 总字数约40000字，可上下浮动5%，并给出 globalGuidelines 说明整体详略策略；
2. chapters 中每章需包含 targetWords/min/max、需要额外展开的 emphasis、sections 数组（为该章各小节/提纲分配字数与注意事项，可注明“允许在必要时超出10%补充案例”等）；
3. rationale 必须解释该章篇幅配置理由，引用模板/素材中的关键信息；
4. 章节编号遵循一级中文数字、二级阿拉伯数字，便于后续统一字号；
5. 结果写成JSON并满足下述Schema，仅用于内部存储与章节生成，不直接输出给读者。

<OUTPUT JSON SCHEMA>
{json.dumps(word_budget_output_schema, ensure_ascii=False, indent=2)}
</OUTPUT JSON SCHEMA>

只返回JSON，无额外说明。
"""


def build_chapter_user_prompt(payload: dict) -> str:
    """
    将章节上下文序列化为提示词输入。
    """
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_document_layout_prompt(payload: dict) -> str:
    """将文档设计所需的上下文序列化为JSON字符串"""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_word_budget_prompt(payload: dict) -> str:
    """将篇幅规划输入转为字符串，便于送入LLM"""
    return json.dumps(payload, ensure_ascii=False, indent=2)
