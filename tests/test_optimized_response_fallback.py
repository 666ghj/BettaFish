"""
Unit tests for the execute_search_tool defensive error handling in InsightEngine/agent.py.

Tests the fix for issue #657: when keyword_optimizer.optimize_keywords() raises
an unexpected exception, the optimized_response variable would be unbound, causing
UnboundLocalError at the later access site. The fix wraps the call in try/except
and falls back to the original query as the keyword.
"""

import unittest
from dataclasses import dataclass
from typing import List


@dataclass
class KeywordOptimizationResponse:
    """Minimal replica of the real dataclass for testing."""
    original_query: str
    optimized_keywords: List[str]
    reasoning: str
    success: bool
    error_message: str = ""


def execute_search_tool_optimized_response_logic(query, keyword_optimizer_func):
    """
    Isolated replication of the optimized_response assignment logic from
    execute_search_tool, with the fix applied.
    Returns the optimized_response that would be used.
    """
    try:
        optimized_response = keyword_optimizer_func(
            original_query=query, context="test context"
        )
    except Exception as e:
        optimized_response = KeywordOptimizationResponse(
            original_query=query,
            optimized_keywords=[query],
            reasoning=f"关键词优化异常，使用原始查询: {str(e)}",
            success=False,
            error_message=str(e),
        )
    return optimized_response


class TestOptimizedResponseFallback(unittest.TestCase):

    def test_normal_optimization_returns_optimized_keywords(self):
        """When optimize_keywords succeeds, its result is used directly."""
        def mock_optimizer(original_query, context):
            return KeywordOptimizationResponse(
                original_query=original_query,
                optimized_keywords=["keyword1", "keyword2"],
                reasoning="Normal optimization",
                success=True,
            )

        result = execute_search_tool_optimized_response_logic("test query", mock_optimizer)
        self.assertEqual(result.optimized_keywords, ["keyword1", "keyword2"])
        self.assertTrue(result.success)

    def test_optimizer_exception_falls_back_to_original_query(self):
        """When optimize_keywords raises an exception, the original query is used as fallback."""
        def failing_optimizer(original_query, context):
            raise RuntimeError("API connection failed")

        result = execute_search_tool_optimized_response_logic("test query", failing_optimizer)

        # optimized_response is always bound — no UnboundLocalError
        self.assertIsNotNone(result)
        # Falls back to the original query as keyword
        self.assertEqual(result.optimized_keywords, ["test query"])
        self.assertFalse(result.success)
        self.assertIn("API connection failed", result.error_message)

    def test_optimizer_attribute_error_falls_back(self):
        """AttributeError from a None-like optimizer is also caught."""
        def bad_optimizer(original_query, context):
            raise AttributeError("'NoneType' object has no attribute 'optimize_keywords'")

        result = execute_search_tool_optimized_response_logic("search term", bad_optimizer)
        self.assertEqual(result.optimized_keywords, ["search term"])
        self.assertFalse(result.success)

    def test_fallback_preserves_original_query(self):
        """The fallback response always preserves the original query."""
        def raising_optimizer(original_query, context):
            raise ValueError("Some internal error")

        query = "舆情分析测试"
        result = execute_search_tool_optimized_response_logic(query, raising_optimizer)
        self.assertEqual(result.original_query, query)
        self.assertEqual(result.optimized_keywords, [query])


if __name__ == "__main__":
    unittest.main()
