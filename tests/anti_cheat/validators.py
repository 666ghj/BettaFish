"""
Anti-cheat validators for verifying genuine implementations.

These validators detect:
- Hardcoded/mocked responses
- Test environment detection
- Timing anomalies suggesting fake network calls
"""

import asyncio
import hashlib
import random
import time
from typing import Any, Callable, Dict, List


class NetworkCallValidator:
    """Validates that implementations make real network calls."""

    @staticmethod
    async def validate_async_network_call(
        func: Callable,
        *args,
        iterations: int = 3,
        min_variance_ms: float = 50.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate that an async function makes real network calls.

        Real network calls have timing variance >50ms between iterations.
        Mocked/cached responses have near-zero variance.

        Args:
            func: Async function to test
            *args: Positional arguments for func
            iterations: Number of test iterations
            min_variance_ms: Minimum timing variance to pass
            **kwargs: Keyword arguments for func

        Returns:
            Dictionary with validation results
        """
        results = []

        for i in range(iterations):
            start = time.time()
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000

            results.append({
                "iteration": i,
                "elapsed_ms": elapsed,
                "result_hash": hashlib.md5(str(result).encode()).hexdigest()[:16],
                "result_length": len(str(result)) if result else 0
            })

            # Random delay between iterations
            await asyncio.sleep(random.uniform(0.3, 0.8))

        # Analyze results
        elapsed_times = [r["elapsed_ms"] for r in results]
        result_hashes = [r["result_hash"] for r in results]

        timing_variance = max(elapsed_times) - min(elapsed_times)
        unique_hashes = len(set(result_hashes))

        return {
            "results": results,
            "timing_variance_ms": timing_variance,
            "unique_responses": unique_hashes,
            "is_likely_real": timing_variance >= min_variance_ms,
            "pass": timing_variance >= min_variance_ms
        }

    @staticmethod
    def validate_sync_network_call(
        func: Callable,
        *args,
        iterations: int = 3,
        min_variance_ms: float = 50.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate that a sync function makes real network calls.

        Same as async version but for synchronous functions.
        """
        results = []

        for i in range(iterations):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000

            results.append({
                "iteration": i,
                "elapsed_ms": elapsed,
                "result_hash": hashlib.md5(str(result).encode()).hexdigest()[:16],
                "result_length": len(str(result)) if result else 0
            })

            time.sleep(random.uniform(0.3, 0.8))

        elapsed_times = [r["elapsed_ms"] for r in results]
        timing_variance = max(elapsed_times) - min(elapsed_times)

        return {
            "results": results,
            "timing_variance_ms": timing_variance,
            "is_likely_real": timing_variance >= min_variance_ms,
            "pass": timing_variance >= min_variance_ms
        }


class DynamicQueryValidator:
    """Validates that implementations handle different queries correctly."""

    @staticmethod
    async def validate_dynamic_queries(
        search_func: Callable,
        queries: List[str],
        query_setter: Callable = None
    ) -> Dict[str, Any]:
        """
        Test implementation with multiple unique queries.

        Real implementations return different results for different queries.
        Fake implementations may return the same hardcoded data.

        Args:
            search_func: Async search function to test
            queries: List of different queries to test
            query_setter: Optional function to set query on crawler

        Returns:
            Validation results dictionary
        """
        results = {}

        for query in queries:
            if query_setter:
                query_setter(query)

            search_results = await search_func()

            # Hash first few results for comparison
            sample = str(search_results[:3]) if search_results else ""
            results[query] = {
                "count": len(search_results) if search_results else 0,
                "sample_hash": hashlib.md5(sample.encode()).hexdigest()[:16] if sample else None
            }

        # Analyze uniqueness
        hashes = [r["sample_hash"] for r in results.values() if r["sample_hash"]]
        unique_count = len(set(hashes))

        return {
            "query_results": results,
            "unique_result_sets": unique_count,
            "total_queries": len(queries),
            "is_likely_real": unique_count >= len(queries) - 1,  # Allow 1 duplicate
            "pass": unique_count >= len(queries) - 1
        }


class ResponseStructureValidator:
    """Validates that response data structures are correct."""

    @staticmethod
    def validate_structure(
        data: Dict[str, Any],
        required_fields: List[str],
        platform: str = None
    ) -> Dict[str, Any]:
        """
        Validate that a data structure has required fields.

        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            platform: Expected platform value (optional)

        Returns:
            Validation results
        """
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)

        platform_match = True
        if platform and "platform" in data:
            platform_match = data["platform"] == platform

        return {
            "missing_fields": missing_fields,
            "platform_match": platform_match,
            "pass": len(missing_fields) == 0 and platform_match
        }

    @staticmethod
    def validate_batch(
        items: List[Dict[str, Any]],
        required_fields: List[str],
        platform: str = None
    ) -> Dict[str, Any]:
        """
        Validate a batch of items.

        Args:
            items: List of data dictionaries
            required_fields: Required fields for each item
            platform: Expected platform value

        Returns:
            Batch validation results
        """
        if not items:
            return {
                "total_items": 0,
                "valid_items": 0,
                "pass": False,
                "errors": ["No items to validate"]
            }

        errors = []
        valid_count = 0

        for i, item in enumerate(items):
            result = ResponseStructureValidator.validate_structure(
                item, required_fields, platform
            )
            if result["pass"]:
                valid_count += 1
            else:
                errors.append(f"Item {i}: {result['missing_fields']}")

        return {
            "total_items": len(items),
            "valid_items": valid_count,
            "pass": valid_count == len(items),
            "errors": errors[:5]  # Limit error output
        }
