"""
论坛日志测试数据

包含各种日志格式的最小示例，用于测试ForumEngine/monitor.py中的日志解析函数。
涵盖旧格式（[HH:MM:SS]）和新格式（loguru默认格式）的日志记录示例。
"""

# ===== 旧格式（支持 [HH:MM:SS]）=====

# 单行JSON，旧格式
OLD_FORMAT_SINGLE_LINE_JSON = """[17:42:31] 2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {"paragraph_latest_state": "这是首次总结内容"}"""

# 多行JSON，旧格式
OLD_FORMAT_MULTILINE_JSON = [
    "[17:42:31] 2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "[17:42:31] \"paragraph_latest_state\": \"这是多行\\nJSON内容\"",
    "[17:42:31] }"
]

# 包含FirstSummaryNode的旧格式日志
OLD_FORMAT_FIRST_SUMMARY = """[17:42:31] 2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - FirstSummaryNode 清理后的输出: {"paragraph_latest_state": "首次总结"}"""

# 包含ReflectionSummaryNode的旧格式日志
OLD_FORMAT_REFLECTION_SUMMARY = """[17:43:00] 2025-11-05 17:43:00.272 | INFO | InsightEngine.nodes.summary_node:process_output:296 - ReflectionSummaryNode 清理后的输出: {"updated_paragraph_latest_state": "反思总结"}"""

# 旧格式，非目标节点（应该被忽略）
OLD_FORMAT_NON_TARGET = """[17:41:16] 2025-11-05 17:41:16.742 | INFO | InsightEngine.nodes.report_structure_node:run:52 - 正在为查询生成报告结构"""


# ===== 新格式（loguru默认格式）=====

# 单行JSON，新格式
NEW_FORMAT_SINGLE_LINE_JSON = """2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {"paragraph_latest_state": "这是首次总结内容"}"""

# 多行JSON，新格式
NEW_FORMAT_MULTILINE_JSON = [
    "2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "2025-11-05 17:42:31.288 | INFO     | InsightEngine.nodes.summary_node:process_output:132 - \"paragraph_latest_state\": \"这是多行\\nJSON内容\"",
    "2025-11-05 17:42:31.289 | INFO     | InsightEngine.nodes.summary_node:process_output:133 - }"
]

# 包含FirstSummaryNode的新格式日志
NEW_FORMAT_FIRST_SUMMARY = """2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - FirstSummaryNode 清理后的输出: {"paragraph_latest_state": "首次总结"}"""

# 包含ReflectionSummaryNode的新格式日志
NEW_FORMAT_REFLECTION_SUMMARY = """2025-11-05 17:43:00.272 | INFO     | InsightEngine.nodes.summary_node:process_output:296 - ReflectionSummaryNode 清理后的输出: {"updated_paragraph_latest_state": "反思总结"}"""

# 新格式，非目标节点（应该被忽略）
NEW_FORMAT_NON_TARGET = """2025-11-05 17:41:16.742 | INFO     | InsightEngine.nodes.report_structure_node:run:52 - 正在为查询生成报告结构: 洛阳钼业预期股价变化"""

# 新格式，ForumEngine的日志
NEW_FORMAT_FORUM_ENGINE = """2025-11-05 22:31:09.964 | INFO     | ForumEngine.monitor:monitor_logs:457 - ForumEngine: 论坛创建中..."""


# ===== 复杂JSON示例 =====

# 包含updated_paragraph_latest_state的JSON（应该优先提取这个）
COMPLEX_JSON_WITH_UPDATED = [
    "2025-11-05 17:43:00.272 | INFO     | InsightEngine.nodes.summary_node:process_output:296 - 清理后的输出: {",
    "2025-11-05 17:43:00.273 | INFO     | InsightEngine.nodes.summary_node:process_output:297 - \"updated_paragraph_latest_state\": \"## 核心发现（更新版）\\n1. 这是更新后的内容\"",
    "2025-11-05 17:43:00.274 | INFO     | InsightEngine.nodes.summary_node:process_output:298 - }"
]

# 只有paragraph_latest_state的JSON
COMPLEX_JSON_WITH_PARAGRAPH = [
    "2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "2025-11-05 17:42:31.288 | INFO     | InsightEngine.nodes.summary_node:process_output:132 - \"paragraph_latest_state\": \"## 核心发现概述\\n1. 这是首次总结内容\"",
    "2025-11-05 17:42:31.289 | INFO     | InsightEngine.nodes.summary_node:process_output:133 - }"
]

# 包含换行符的JSON内容
COMPLEX_JSON_WITH_NEWLINES = [
    "[17:42:31] 2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "[17:42:31] \"paragraph_latest_state\": \"第一行内容\\n第二行内容\\n第三行内容\"",
    "[17:42:31] }"
]

# ===== 边界情况 =====

# 不包含"清理后的输出"的行（应该被忽略）
LINE_WITHOUT_CLEAN_OUTPUT = """2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - JSON解析成功"""

# 包含"清理后的输出"但不是JSON格式
LINE_WITH_CLEAN_OUTPUT_NOT_JSON = """2025-11-05 17:42:31.287 | INFO     | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: 这不是JSON格式的内容"""

# 空行
EMPTY_LINE = ""

# 只有时间戳的行
LINE_WITH_ONLY_TIMESTAMP_OLD = "[17:42:31]"
LINE_WITH_ONLY_TIMESTAMP_NEW = "2025-11-05 17:42:31.287 | INFO | module:function:1 -"

# 无效的JSON格式
INVALID_JSON = [
    "2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "2025-11-05 17:42:31.288 | INFO | InsightEngine.nodes.summary_node:process_output:132 - \"paragraph_latest_state\": \"缺少结束引号",
    "2025-11-05 17:42:31.289 | INFO | InsightEngine.nodes.summary_node:process_output:133 - }"
]

# ===== 混合格式（同一批日志中既有旧格式也有新格式）=====
MIXED_FORMAT_LINES = [
    "[17:42:31] 2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
    "2025-11-05 17:42:31.288 | INFO     | InsightEngine.nodes.summary_node:process_output:132 - \"paragraph_latest_state\": \"混合格式内容\"",
    "[17:42:31] }"
]

