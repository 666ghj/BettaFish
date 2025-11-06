# ForumEngine日志解析测试

本测试套件用于测试 `ForumEngine/monitor.py` 中的日志解析功能，验证其在不同日志格式下的正确性。

## 测试数据

`forum_log_test_data.py` 包含各种日志格式的最小示例（论坛日志测试数据）：

### 旧格式（[HH:MM:SS]）
- `OLD_FORMAT_SINGLE_LINE_JSON`: 单行JSON
- `OLD_FORMAT_MULTILINE_JSON`: 多行JSON
- `OLD_FORMAT_FIRST_SUMMARY`: 包含FirstSummaryNode的日志
- `OLD_FORMAT_REFLECTION_SUMMARY`: 包含ReflectionSummaryNode的日志

### 新格式（loguru默认格式）
- `NEW_FORMAT_SINGLE_LINE_JSON`: 单行JSON
- `NEW_FORMAT_MULTILINE_JSON`: 多行JSON
- `NEW_FORMAT_FIRST_SUMMARY`: 包含FirstSummaryNode的日志
- `NEW_FORMAT_REFLECTION_SUMMARY`: 包含ReflectionSummaryNode的日志

### 复杂示例
- `COMPLEX_JSON_WITH_UPDATED`: 包含updated_paragraph_latest_state的JSON
- `COMPLEX_JSON_WITH_PARAGRAPH`: 只有paragraph_latest_state的JSON
- `MIXED_FORMAT_LINES`: 混合格式的日志行

## 运行测试

### 使用pytest（推荐）

```bash
# 安装pytest（如果还没有安装）
pip install pytest

# 运行所有测试
pytest tests/test_monitor.py -v

# 运行特定测试
pytest tests/test_monitor.py::TestLogMonitor::test_extract_json_content_new_format_multiline -v
```

### 直接运行

```bash
python tests/test_monitor.py
```

## 测试覆盖

测试覆盖以下函数：

1. **is_target_log_line**: 识别目标节点日志行
2. **is_json_start_line**: 识别JSON开始行
3. **is_json_end_line**: 识别JSON结束行
4. **extract_json_content**: 提取JSON内容（单行和多行）
5. **format_json_content**: 格式化JSON内容（优先提取updated_paragraph_latest_state）
6. **extract_node_content**: 提取节点内容
7. **process_lines_for_json**: 完整处理流程
8. **is_valuable_content**: 判断内容是否有价值

## 预期问题

当前代码可能无法正确处理loguru新格式，主要问题在于：

1. **时间戳移除**：`extract_json_content()` 中的正则 `r'^\[\d{2}:\d{2}:\d{2}\]\s*'` 只能匹配 `[HH:MM:SS]` 格式，无法匹配loguru的 `YYYY-MM-DD HH:mm:ss.SSS` 格式

2. **时间戳匹配**：`extract_node_content()` 中的正则 `r'\[\d{2}:\d{2}:\d{2}\]\s*(.+)'` 同样只能匹配旧格式

这些测试会帮助识别这些问题，并指导后续的代码修复。

