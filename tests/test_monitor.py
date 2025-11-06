"""
测试ForumEngine/monitor.py中的日志解析函数

测试各种日志格式下的解析能力，包括：
1. 旧格式：[HH:MM:SS]
2. 新格式：loguru默认格式 (YYYY-MM-DD HH:mm:ss.SSS | LEVEL | ...)
3. 只应当接收FirstSummaryNode、ReflectionSummaryNode等SummaryNode的输出，不应当接收SearchNode的输出
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ForumEngine.monitor import LogMonitor
from tests import forum_log_test_data as test_data


class TestLogMonitor:
    """测试LogMonitor的日志解析功能"""
    
    def setup_method(self):
        """每个测试方法前的初始化"""
        self.monitor = LogMonitor(log_dir="tests/test_logs")
    
    def test_is_target_log_line_old_format(self):
        """测试旧格式的目标节点识别"""
        # 应该识别包含FirstSummaryNode的行
        assert self.monitor.is_target_log_line(test_data.OLD_FORMAT_FIRST_SUMMARY) == True
        # 应该识别包含ReflectionSummaryNode的行
        assert self.monitor.is_target_log_line(test_data.OLD_FORMAT_REFLECTION_SUMMARY) == True
        # 不应该识别非目标节点
        assert self.monitor.is_target_log_line(test_data.OLD_FORMAT_NON_TARGET) == False
    
    def test_is_target_log_line_new_format(self):
        """测试新格式的目标节点识别"""
        # 应该识别包含FirstSummaryNode的行
        assert self.monitor.is_target_log_line(test_data.NEW_FORMAT_FIRST_SUMMARY) == True
        # 应该识别包含ReflectionSummaryNode的行
        assert self.monitor.is_target_log_line(test_data.NEW_FORMAT_REFLECTION_SUMMARY) == True
        # 不应该识别非目标节点
        assert self.monitor.is_target_log_line(test_data.NEW_FORMAT_NON_TARGET) == False
    
    def test_is_json_start_line_old_format(self):
        """测试旧格式的JSON开始行识别"""
        assert self.monitor.is_json_start_line(test_data.OLD_FORMAT_SINGLE_LINE_JSON) == True
        assert self.monitor.is_json_start_line(test_data.OLD_FORMAT_MULTILINE_JSON[0]) == True
        assert self.monitor.is_json_start_line(test_data.OLD_FORMAT_NON_TARGET) == False
    
    def test_is_json_start_line_new_format(self):
        """测试新格式的JSON开始行识别"""
        assert self.monitor.is_json_start_line(test_data.NEW_FORMAT_SINGLE_LINE_JSON) == True
        assert self.monitor.is_json_start_line(test_data.NEW_FORMAT_MULTILINE_JSON[0]) == True
        assert self.monitor.is_json_start_line(test_data.NEW_FORMAT_NON_TARGET) == False
    
    def test_is_json_end_line(self):
        """测试JSON结束行识别"""
        assert self.monitor.is_json_end_line("}") == True
        assert self.monitor.is_json_end_line("] }") == True
        assert self.monitor.is_json_end_line("[17:42:31] }") == False  # 需要先清理时间戳
        assert self.monitor.is_json_end_line("2025-11-05 17:42:31.289 | INFO | module:function:133 - }") == False  # 需要先清理时间戳
    
    def test_extract_json_content_old_format_single_line(self):
        """测试旧格式单行JSON提取"""
        lines = [test_data.OLD_FORMAT_SINGLE_LINE_JSON]
        result = self.monitor.extract_json_content(lines)
        assert result is not None
        assert "这是首次总结内容" in result
    
    def test_extract_json_content_new_format_single_line(self):
        """测试新格式单行JSON提取"""
        lines = [test_data.NEW_FORMAT_SINGLE_LINE_JSON]
        result = self.monitor.extract_json_content(lines)
        assert result is not None
        assert "这是首次总结内容" in result
    
    def test_extract_json_content_old_format_multiline(self):
        """测试旧格式多行JSON提取"""
        result = self.monitor.extract_json_content(test_data.OLD_FORMAT_MULTILINE_JSON)
        assert result is not None
        assert "多行" in result
        assert "JSON内容" in result
    
    def test_extract_json_content_new_format_multiline(self):
        """测试新格式多行JSON提取（支持loguru格式的时间戳移除）"""
        result = self.monitor.extract_json_content(test_data.NEW_FORMAT_MULTILINE_JSON)
        assert result is not None
        assert "多行" in result
        assert "JSON内容" in result
    
    def test_extract_json_content_updated_priority(self):
        """测试updated_paragraph_latest_state优先提取"""
        result = self.monitor.extract_json_content(test_data.COMPLEX_JSON_WITH_UPDATED)
        assert result is not None
        assert "更新版" in result
        assert "核心发现" in result
    
    def test_extract_json_content_paragraph_only(self):
        """测试只有paragraph_latest_state的情况"""
        result = self.monitor.extract_json_content(test_data.COMPLEX_JSON_WITH_PARAGRAPH)
        assert result is not None
        assert "首次总结" in result or "核心发现" in result
    
    def test_format_json_content(self):
        """测试JSON内容格式化"""
        # 测试updated_paragraph_latest_state优先
        json_obj = {
            "updated_paragraph_latest_state": "更新后的内容",
            "paragraph_latest_state": "首次内容"
        }
        result = self.monitor.format_json_content(json_obj)
        assert result == "更新后的内容"
        
        # 测试只有paragraph_latest_state
        json_obj = {
            "paragraph_latest_state": "首次内容"
        }
        result = self.monitor.format_json_content(json_obj)
        assert result == "首次内容"
        
        # 测试都没有的情况
        json_obj = {"other_field": "其他内容"}
        result = self.monitor.format_json_content(json_obj)
        assert "清理后的输出" in result
    
    def test_extract_node_content_old_format(self):
        """测试旧格式的节点内容提取"""
        line = "[17:42:31] [INSIGHT] [FirstSummaryNode] 清理后的输出: 这是测试内容"
        result = self.monitor.extract_node_content(line)
        assert result is not None
        assert "测试内容" in result
    
    def test_extract_node_content_new_format(self):
        """测试新格式的节点内容提取"""
        line = "2025-11-05 17:42:31.287 | INFO | InsightEngine.nodes.summary_node:process_output:131 - FirstSummaryNode 清理后的输出: 这是测试内容"
        result = self.monitor.extract_node_content(line)
        assert result is not None
        assert "测试内容" in result
    
    def test_process_lines_for_json_old_format(self):
        """测试旧格式的完整处理流程"""
        lines = [
            test_data.OLD_FORMAT_NON_TARGET,  # 应该被忽略
            test_data.OLD_FORMAT_MULTILINE_JSON[0],
            test_data.OLD_FORMAT_MULTILINE_JSON[1],
            test_data.OLD_FORMAT_MULTILINE_JSON[2],
        ]
        result = self.monitor.process_lines_for_json(lines, "insight")
        assert len(result) > 0
        assert any("多行" in content for content in result)
    
    def test_process_lines_for_json_new_format(self):
        """测试新格式的完整处理流程"""
        lines = [
            test_data.NEW_FORMAT_NON_TARGET,  # 应该被忽略
            test_data.NEW_FORMAT_MULTILINE_JSON[0],
            test_data.NEW_FORMAT_MULTILINE_JSON[1],
            test_data.NEW_FORMAT_MULTILINE_JSON[2],
        ]
        result = self.monitor.process_lines_for_json(lines, "insight")
        assert len(result) > 0
        assert any("多行" in content for content in result)
        assert any("JSON内容" in content for content in result)
    
    def test_process_lines_for_json_mixed_format(self):
        """测试混合格式的处理"""
        result = self.monitor.process_lines_for_json(test_data.MIXED_FORMAT_LINES, "insight")
        assert len(result) > 0
        assert any("混合格式内容" in content for content in result)
    
    def test_is_valuable_content(self):
        """测试有价值内容的判断"""
        # 包含"清理后的输出"应该是有价值的
        assert self.monitor.is_valuable_content(test_data.OLD_FORMAT_SINGLE_LINE_JSON) == True
        
        # 排除短小提示信息
        assert self.monitor.is_valuable_content("JSON解析成功") == False
        assert self.monitor.is_valuable_content("成功生成") == False
        
        # 空行应该被过滤
        assert self.monitor.is_valuable_content("") == False
    
    def test_extract_json_content_real_query_engine(self):
        """测试QueryEngine实际生产环境日志提取"""
        result = self.monitor.extract_json_content(test_data.REAL_QUERY_ENGINE_REFLECTION)
        assert result is not None
        assert "洛阳栾川钼业集团" in result
        assert "CMOC" in result
        assert "updated_paragraph_latest_state" not in result  # 应该已经提取内容，不包含字段名
    
    def test_extract_json_content_real_insight_engine(self):
        """测试InsightEngine实际生产环境日志提取（包含标识行）"""
        # 先测试能否识别标识行
        assert self.monitor.is_target_log_line(test_data.REAL_INSIGHT_ENGINE_REFLECTION[0]) == True  # 包含"正在生成反思总结"
        assert self.monitor.is_target_log_line(test_data.REAL_INSIGHT_ENGINE_REFLECTION[1]) == True  # 包含nodes.summary_node
        
        # 测试JSON提取（从第二行开始，因为第一行是标识行）
        json_lines = test_data.REAL_INSIGHT_ENGINE_REFLECTION[1:]  # 跳过标识行
        result = self.monitor.extract_json_content(json_lines)
        assert result is not None
        assert "核心发现" in result
        assert "更新版" in result
        assert "洛阳钼业2025年第三季度" in result
    
    def test_extract_json_content_real_media_engine(self):
        """测试MediaEngine实际生产环境日志提取（单行JSON）"""
        # MediaEngine是单行JSON格式，需要先分割成行
        lines = test_data.REAL_MEDIA_ENGINE_REFLECTION.split('\n')
        
        # 测试能否识别标识行
        assert self.monitor.is_target_log_line(lines[0]) == True  # 包含"正在生成反思总结"
        assert self.monitor.is_target_log_line(lines[1]) == True  # 包含nodes.summary_node和"清理后的输出"
        
        # 测试JSON提取（从包含JSON的行开始）
        json_line = lines[1]  # 第二行包含完整的单行JSON
        result = self.monitor.extract_json_content([json_line])
        assert result is not None
        assert "综合信息概览" in result
        assert "洛阳钼业" in result
        assert "updated_paragraph_latest_state" not in result  # 应该已经提取内容
    
    def test_process_lines_for_json_real_query_engine(self):
        """测试QueryEngine实际日志的完整处理流程"""
        result = self.monitor.process_lines_for_json(test_data.REAL_QUERY_ENGINE_REFLECTION, "query")
        assert len(result) > 0
        assert any("洛阳栾川钼业集团" in content for content in result)
    
    def test_process_lines_for_json_real_insight_engine(self):
        """测试InsightEngine实际日志的完整处理流程（包含标识行）"""
        result = self.monitor.process_lines_for_json(test_data.REAL_INSIGHT_ENGINE_REFLECTION, "insight")
        assert len(result) > 0
        assert any("核心发现" in content for content in result)
        assert any("更新版" in content for content in result)
    
    def test_process_lines_for_json_real_media_engine(self):
        """测试MediaEngine实际日志的完整处理流程（单行JSON）"""
        # 将单行字符串分割成多行
        lines = test_data.REAL_MEDIA_ENGINE_REFLECTION.split('\n')
        result = self.monitor.process_lines_for_json(lines, "media")
        assert len(result) > 0
        assert any("综合信息概览" in content for content in result)
        assert any("洛阳钼业" in content for content in result)
    
    def test_filter_search_node_output(self):
        """测试过滤SearchNode的输出（重要：SearchNode不应进入论坛）"""
        # SearchNode的输出包含"清理后的输出: {"，但不包含目标节点模式
        search_lines = test_data.SEARCH_NODE_FIRST_SEARCH
        result = self.monitor.process_lines_for_json(search_lines, "insight")
        # SearchNode的输出应该被过滤，不应该被捕获
        assert len(result) == 0
    
    def test_filter_search_node_output_single_line(self):
        """测试过滤SearchNode的单行JSON输出"""
        # SearchNode的单行JSON格式
        search_line = test_data.SEARCH_NODE_REFLECTION_SEARCH
        result = self.monitor.process_lines_for_json([search_line], "insight")
        # SearchNode的输出应该被过滤
        assert len(result) == 0
    
    def test_search_node_vs_summary_node_mixed(self):
        """测试混合场景：SearchNode和SummaryNode同时存在，只捕获SummaryNode"""
        lines = [
            # SearchNode输出（应该被过滤）
            "[11:16:35] 2025-11-06 11:16:35.567 | INFO | InsightEngine.nodes.search_node:process_output:97 - 清理后的输出: {",
            "[11:16:35] \"search_query\": \"测试查询\"",
            "[11:16:35] }",
            # SummaryNode输出（应该被捕获）
            "[11:17:05] 2025-11-06 11:17:05.547 | INFO | InsightEngine.nodes.summary_node:process_output:131 - 清理后的输出: {",
            "[11:17:05] \"paragraph_latest_state\": \"这是总结内容\"",
            "[11:17:05] }",
        ]
        result = self.monitor.process_lines_for_json(lines, "insight")
        # 应该只捕获SummaryNode的输出，不包含SearchNode的输出
        assert len(result) > 0
        assert any("总结内容" in content for content in result)
        # 确保不包含搜索查询内容
        assert not any("search_query" in content for content in result)
        assert not any("测试查询" in content for content in result)
    
    def test_filter_error_logs_from_summary_node(self):
        """测试过滤SummaryNode的错误日志（重要：错误日志不应进入论坛）"""
        # JSON解析失败错误日志
        assert self.monitor.is_target_log_line(test_data.SUMMARY_NODE_JSON_ERROR) == False
        
        # JSON修复失败错误日志
        assert self.monitor.is_target_log_line(test_data.SUMMARY_NODE_JSON_FIX_ERROR) == False
        
        # ERROR级别日志
        assert self.monitor.is_target_log_line(test_data.SUMMARY_NODE_ERROR_LOG) == False
        
        # Traceback错误日志
        for line in test_data.SUMMARY_NODE_TRACEBACK.split('\n'):
            assert self.monitor.is_target_log_line(line) == False
    
    def test_error_logs_not_captured(self):
        """测试错误日志不会被捕获到论坛"""
        error_lines = [
            test_data.SUMMARY_NODE_JSON_ERROR,
            test_data.SUMMARY_NODE_JSON_FIX_ERROR,
            test_data.SUMMARY_NODE_ERROR_LOG,
        ]
        
        for line in error_lines:
            result = self.monitor.process_lines_for_json([line], "media")
            # 错误日志不应该被捕获
            assert len(result) == 0
    
    def test_mixed_valid_and_error_logs(self):
        """测试混合场景：有效日志和错误日志同时存在，只捕获有效日志"""
        lines = [
            # 错误日志（应该被过滤）
            test_data.SUMMARY_NODE_JSON_ERROR,
            test_data.SUMMARY_NODE_JSON_FIX_ERROR,
            # 有效SummaryNode输出（应该被捕获）
            "[11:55:31] 2025-11-06 11:55:31.762 | INFO | MediaEngine.nodes.summary_node:process_output:134 - 清理后的输出: {",
            "[11:55:31] \"paragraph_latest_state\": \"这是有效的总结内容\"",
            "[11:55:31] }",
        ]
        result = self.monitor.process_lines_for_json(lines, "media")
        # 应该只捕获有效日志，不包含错误日志
        assert len(result) > 0
        assert any("有效的总结内容" in content for content in result)
        # 确保不包含错误信息
        assert not any("JSON解析失败" in content for content in result)
        assert not any("JSON修复失败" in content for content in result)


def run_tests():
    """运行所有测试"""
    import pytest
    
    # 运行测试
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()

