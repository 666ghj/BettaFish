"""
Implementation checksum verification.

Verifies that implementation files contain real logic, not test stubs
or hardcoded responses.
"""

import ast
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any


class ImplementationChecker:
    """Verify implementations contain real logic, not test stubs."""

    # Patterns that suggest fake/stub implementations
    FORBIDDEN_PATTERNS = [
        r"if\s+['\"]test['\"]",           # if 'test' in ...
        r"if\s+pytest",                    # if pytest ...
        r"if\s+__name__\s*==\s*['\"]__test__['\"]",
        r"return\s+\[\]\s*#\s*TODO",       # return [] # TODO
        r"pass\s*#\s*TODO",                # pass # TODO
        r"raise\s+NotImplementedError\(\)",
        r"HARDCODED_RESPONSE\s*=",         # Explicit hardcoded responses
        r"MOCK_DATA\s*=",                  # Mock data declarations
    ]

    # Patterns that should be present for specific implementations
    REQUIRED_PATTERNS = {
        "twitter/core.py": [
            r"twikit",
            r"Client",
            r"search_tweet|search",
            r"async\s+def\s+search",
        ],
        "reddit/core.py": [
            r"praw",
            r"Reddit",
            r"subreddit",
            r"async\s+def\s+search",
        ],
        "hackernews/core.py": [
            r"httpx|aiohttp|requests",
            r"algolia|firebase",
            r"async\s+def\s+search",
        ],
        "openai_adapter.py": [
            r"openai",
            r"OpenAI",
            r"chat\.completions\.create",
        ],
        "azure_adapter.py": [
            r"AzureOpenAI",
            r"api_version",
        ],
        "anthropic_adapter.py": [
            r"anthropic",
            r"Anthropic",
            r"messages\.create",
            r"content\[0\]\.text",  # Anthropic-specific response format
        ],
    }

    @classmethod
    def verify_implementation(cls, file_path: Path) -> Dict[str, Any]:
        """
        Verify a file contains genuine implementation.

        Args:
            file_path: Path to file to verify

        Returns:
            Verification results dictionary
        """
        if not file_path.exists():
            return {
                "file": str(file_path),
                "exists": False,
                "pass": False,
                "error": "File not found"
            }

        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Check for forbidden patterns
        forbidden_found = []
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                forbidden_found.append(pattern)

        # Check for required patterns based on filename
        file_key = None
        for key in cls.REQUIRED_PATTERNS:
            if key in str(file_path):
                file_key = key
                break

        required_missing = []
        if file_key:
            for pattern in cls.REQUIRED_PATTERNS[file_key]:
                if not re.search(pattern, content, re.IGNORECASE):
                    required_missing.append(pattern)

        # Calculate implementation hash
        impl_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Check for minimum implementation size
        min_lines = 50  # Real implementations should have at least 50 lines
        line_count = len(content.splitlines())

        return {
            "file": str(file_path),
            "exists": True,
            "forbidden_patterns_found": forbidden_found,
            "required_patterns_missing": required_missing,
            "implementation_hash": impl_hash,
            "line_count": line_count,
            "min_lines_check": line_count >= min_lines,
            "pass": (
                len(forbidden_found) == 0 and
                len(required_missing) == 0 and
                line_count >= min_lines
            )
        }

    @classmethod
    def verify_all_implementations(cls, project_root: Path) -> Dict[str, Any]:
        """
        Verify all implementation files in the project.

        Args:
            project_root: Path to project root

        Returns:
            Verification results for all files
        """
        files_to_check = [
            project_root / "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/twitter/core.py",
            project_root / "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/reddit/core.py",
            project_root / "MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/hackernews/core.py",
            project_root / "utils/llm/adapters/openai_adapter.py",
            project_root / "utils/llm/adapters/azure_adapter.py",
            project_root / "utils/llm/adapters/anthropic_adapter.py",
        ]

        results = {}
        all_pass = True

        for file_path in files_to_check:
            result = cls.verify_implementation(file_path)
            results[str(file_path.relative_to(project_root))] = result
            if not result["pass"]:
                all_pass = False

        return {
            "files": results,
            "all_pass": all_pass,
            "total_files": len(files_to_check),
            "passed_files": sum(1 for r in results.values() if r.get("pass", False))
        }


class ASTChecker:
    """
    Check implementation via AST analysis.

    More reliable than regex for detecting actual function implementations.
    """

    @staticmethod
    def has_real_async_methods(file_path: Path) -> Dict[str, Any]:
        """
        Check if file has real async method implementations.

        Args:
            file_path: Path to Python file

        Returns:
            Analysis results
        """
        if not file_path.exists():
            return {"exists": False, "pass": False}

        content = file_path.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {"exists": True, "syntax_error": str(e), "pass": False}

        async_methods = []
        stub_methods = []

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check if it's a real implementation or just pass/NotImplementedError
                is_stub = False

                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Pass):
                        is_stub = True
                    elif isinstance(stmt, ast.Raise):
                        is_stub = True
                    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                        # Just a docstring
                        is_stub = True

                if is_stub:
                    stub_methods.append(node.name)
                else:
                    async_methods.append(node.name)

        return {
            "exists": True,
            "async_methods": async_methods,
            "stub_methods": stub_methods,
            "has_real_implementations": len(async_methods) > 0,
            "pass": len(async_methods) > 0 and len(stub_methods) == 0
        }
