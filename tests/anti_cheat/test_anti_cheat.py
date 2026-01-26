"""
Anti-Cheat Test Suite

This test suite validates that implementations are genuine and not faked.
It uses multiple techniques to detect cheating:

1. Timing Variance Analysis - Real network calls have variable latency
2. Dynamic Query Testing - Different queries must return different results
3. Implementation Verification - Source code must contain real logic
4. AST Analysis - Functions must have real implementations, not stubs

Pass Criteria:
- All platform implementations must pass checksum verification
- Network calls must show >30ms timing variance
- Different queries must produce at least 2 unique result sets
- No forbidden patterns (MOCK_DATA, NotImplementedError) in production code
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List

import pytest

from tests.anti_cheat import (
    NetworkCallValidator,
    DynamicQueryValidator,
    ResponseStructureValidator,
    ImplementationChecker,
    ASTChecker,
)


# ===== Pass Criteria Definition =====

ANTI_CHEAT_PASS_CRITERIA = {
    # Timing analysis
    "min_timing_variance_ms": 30,      # Real network calls vary by at least 30ms
    "max_consistent_variance_ms": 5,    # Mocked calls have <5ms variance

    # Query uniqueness
    "min_unique_result_sets": 2,        # At least 2/3 queries return unique results
    "min_query_count": 3,               # Test with at least 3 queries

    # Implementation verification
    "min_implementation_lines": 50,     # Real implementations have >50 lines
    "max_stub_methods": 0,              # No stub methods allowed

    # Structure validation
    "required_platform_fields": ["id", "platform", "title"],
}


class TestNetworkCallAntiCheat:
    """Tests that verify real network calls are being made."""

    @pytest.mark.anti_cheat
    @pytest.mark.asyncio
    async def test_hackernews_timing_variance(self):
        """
        HackerNews API must show timing variance indicating real calls.

        Real API calls have network latency that varies between requests.
        Mocked/cached responses return instantly with no variance.
        """
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsClient

        client = HackerNewsClient()

        async def search():
            return await client.search_stories("python", hits_per_page=3)

        result = await NetworkCallValidator.validate_async_network_call(
            search,
            iterations=3,
            min_variance_ms=ANTI_CHEAT_PASS_CRITERIA["min_timing_variance_ms"]
        )

        await client.close()

        assert result["pass"], (
            f"ANTI-CHEAT FAILURE: Timing variance is {result['timing_variance_ms']:.1f}ms. "
            f"Expected >= {ANTI_CHEAT_PASS_CRITERIA['min_timing_variance_ms']}ms. "
            "This suggests mocked or cached responses."
        )

        print(f"[PASS] Timing variance: {result['timing_variance_ms']:.1f}ms")

    @pytest.mark.anti_cheat
    @pytest.mark.asyncio
    async def test_reddit_timing_variance(self):
        """Reddit API must show timing variance indicating real calls."""
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditClient

        client = RedditClient()
        if not client.authenticate():
            pytest.skip("Reddit authentication failed")

        def search():
            return client.search_posts("python", limit=3)

        result = NetworkCallValidator.validate_sync_network_call(
            search,
            iterations=3,
            min_variance_ms=ANTI_CHEAT_PASS_CRITERIA["min_timing_variance_ms"]
        )

        assert result["pass"], (
            f"ANTI-CHEAT FAILURE: Reddit timing variance is {result['timing_variance_ms']:.1f}ms. "
            "This suggests mocked responses."
        )

        print(f"[PASS] Reddit timing variance: {result['timing_variance_ms']:.1f}ms")


class TestDynamicQueryAntiCheat:
    """Tests that verify different queries return different results."""

    @pytest.mark.anti_cheat
    @pytest.mark.asyncio
    async def test_hackernews_dynamic_queries(self):
        """
        Different search queries must return different results.

        Hardcoded implementations return the same data regardless of query.
        Real implementations return query-specific results.
        """
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        crawler = HackerNewsCrawler()
        crawler.max_results = 5
        await crawler.start()

        queries = ["machine learning", "blockchain", "rust programming"]

        async def search():
            return await crawler.search()

        def set_query(q):
            crawler.keyword = q

        result = await DynamicQueryValidator.validate_dynamic_queries(
            search, queries, query_setter=set_query
        )

        await crawler.close()

        assert result["pass"], (
            f"ANTI-CHEAT FAILURE: Only {result['unique_result_sets']}/{len(queries)} unique result sets. "
            "Different queries should return different results."
        )

        print(f"[PASS] {result['unique_result_sets']}/{len(queries)} unique result sets")

    @pytest.mark.anti_cheat
    @pytest.mark.asyncio
    async def test_reddit_dynamic_queries(self):
        """Reddit must return different results for different queries."""
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditCrawler

        crawler = RedditCrawler()
        crawler.max_results = 5

        try:
            await crawler.start()
        except Exception as e:
            pytest.skip(f"Reddit initialization failed: {e}")

        queries = ["artificial intelligence", "cryptocurrency", "game development"]

        async def search():
            return await crawler.search()

        def set_query(q):
            crawler.keyword = q

        result = await DynamicQueryValidator.validate_dynamic_queries(
            search, queries, query_setter=set_query
        )

        await crawler.close()

        assert result["pass"], (
            f"ANTI-CHEAT FAILURE: Only {result['unique_result_sets']}/{len(queries)} unique result sets for Reddit."
        )


class TestImplementationAntiCheat:
    """Tests that verify implementation files contain real code."""

    @pytest.mark.anti_cheat
    def test_western_crawler_implementations(self):
        """
        Western platform crawler files must contain real implementations.

        Checks for:
        - No forbidden patterns (MOCK_DATA, NotImplementedError)
        - Required patterns for each platform (API libraries, async methods)
        - Minimum file size (real implementations have substance)
        """
        project_root = Path(__file__).parent.parent.parent

        files_to_check = [
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/hackernews/core.py",
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/reddit/core.py",
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/twitter/core.py",
        ]

        failures = []

        for file_rel in files_to_check:
            file_path = project_root / file_rel
            if not file_path.exists():
                continue  # Skip non-existent files

            result = ImplementationChecker.verify_implementation(file_path)

            if not result["pass"]:
                reasons = []
                if result.get("forbidden_patterns_found"):
                    reasons.append(f"forbidden patterns: {result['forbidden_patterns_found']}")
                if result.get("required_patterns_missing"):
                    reasons.append(f"missing patterns: {result['required_patterns_missing']}")
                if not result.get("min_lines_check"):
                    reasons.append(f"only {result.get('line_count', 0)} lines")

                failures.append(f"{file_rel}: {', '.join(reasons)}")

        if failures:
            failure_msg = "\n".join(failures)
            pytest.fail(f"ANTI-CHEAT FAILURE: Implementation verification failed:\n{failure_msg}")

        print(f"[PASS] {len(files_to_check)} implementation files verified")

    @pytest.mark.anti_cheat
    def test_llm_adapter_implementations(self):
        """LLM adapter files must contain real implementations."""
        project_root = Path(__file__).parent.parent.parent

        files_to_check = [
            "utils/llm/adapters/openai_adapter.py",
            "utils/llm/adapters/azure_adapter.py",
            "utils/llm/adapters/anthropic_adapter.py",
        ]

        failures = []

        for file_rel in files_to_check:
            file_path = project_root / file_rel
            if not file_path.exists():
                continue

            result = ImplementationChecker.verify_implementation(file_path)

            if not result["pass"]:
                reasons = []
                if result.get("forbidden_patterns_found"):
                    reasons.append(f"forbidden patterns: {result['forbidden_patterns_found']}")
                if not result.get("min_lines_check"):
                    reasons.append(f"only {result.get('line_count', 0)} lines")
                failures.append(f"{file_rel}: {', '.join(reasons)}")

        if failures:
            failure_msg = "\n".join(failures)
            pytest.fail(f"ANTI-CHEAT FAILURE: LLM adapter verification failed:\n{failure_msg}")

        print(f"[PASS] LLM adapters verified")


class TestASTAntiCheat:
    """Tests using AST analysis to detect stub implementations."""

    @pytest.mark.anti_cheat
    def test_no_stub_async_methods(self):
        """
        Async methods must have real implementations, not just 'pass' or 'raise'.

        Stub implementations that pass tests but do nothing in production
        are detected via AST analysis.
        """
        project_root = Path(__file__).parent.parent.parent

        crawler_files = [
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/hackernews/core.py",
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/reddit/core.py",
            "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/twitter/core.py",
        ]

        failures = []

        for file_rel in crawler_files:
            file_path = project_root / file_rel
            if not file_path.exists():
                continue

            result = ASTChecker.has_real_async_methods(file_path)

            if result.get("stub_methods"):
                failures.append(f"{file_rel}: stub methods: {result['stub_methods']}")

            if not result.get("has_real_implementations"):
                failures.append(f"{file_rel}: no real async implementations")

        if failures:
            failure_msg = "\n".join(failures)
            pytest.fail(f"ANTI-CHEAT FAILURE: Stub implementations detected:\n{failure_msg}")

        print("[PASS] No stub async methods detected")


class TestResponseStructureAntiCheat:
    """Tests that verify response data structures are correct."""

    @pytest.mark.anti_cheat
    @pytest.mark.asyncio
    async def test_hackernews_response_structure(self):
        """HackerNews responses must have correct structure."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsClient

        client = HackerNewsClient()
        results = await client.search_stories("python", hits_per_page=5)
        await client.close()

        assert len(results) > 0, "No results to validate"

        required_fields = ["id", "title", "platform"]
        validation = ResponseStructureValidator.validate_batch(
            results, required_fields, platform="hackernews"
        )

        assert validation["pass"], (
            f"ANTI-CHEAT FAILURE: Response structure validation failed. "
            f"Errors: {validation.get('errors', [])}"
        )

        print(f"[PASS] {validation['valid_items']}/{validation['total_items']} items valid")


class TestPassCriteriaDefinition:
    """Tests that validate pass criteria are well-defined."""

    @pytest.mark.anti_cheat
    def test_all_criteria_defined(self):
        """All required pass criteria must be defined with sensible values."""
        required = [
            "min_timing_variance_ms",
            "min_unique_result_sets",
            "min_implementation_lines",
        ]

        for criterion in required:
            assert criterion in ANTI_CHEAT_PASS_CRITERIA, \
                f"Missing pass criterion: {criterion}"
            assert ANTI_CHEAT_PASS_CRITERIA[criterion] > 0, \
                f"Pass criterion {criterion} must be positive"

        print("\n=== Anti-Cheat Pass Criteria ===")
        for name, value in ANTI_CHEAT_PASS_CRITERIA.items():
            print(f"  {name}: {value}")

    @pytest.mark.anti_cheat
    def test_criteria_are_reasonable(self):
        """Pass criteria must be reasonable (not too strict, not too lenient)."""
        # Timing variance should be realistic for network calls
        timing = ANTI_CHEAT_PASS_CRITERIA["min_timing_variance_ms"]
        assert 20 <= timing <= 200, f"Timing variance {timing}ms seems unreasonable"

        # Line count should catch real implementations
        lines = ANTI_CHEAT_PASS_CRITERIA["min_implementation_lines"]
        assert 30 <= lines <= 200, f"Min lines {lines} seems unreasonable"

        print("[PASS] Pass criteria are reasonable")


def run_all_anti_cheat_tests():
    """Run all anti-cheat tests and generate summary report."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "-m", "anti_cheat", "--tb=short"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    print("=== Anti-Cheat Test Suite ===\n")
    success = run_all_anti_cheat_tests()
    print("\n" + ("=" * 50))
    print("RESULT:", "PASS" if success else "FAIL")
