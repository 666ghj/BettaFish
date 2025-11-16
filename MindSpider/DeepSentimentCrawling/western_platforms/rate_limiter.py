#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rate Limiter and IP Protection Module
Protects against IP bans when crawling Western media platforms from home

Features:
- Per-platform rate limiting
- Request counting and quota management
- Configurable delays
- Warning system for excessive usage
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import defaultdict
from loguru import logger
import threading


class RateLimiter:
    """
    Rate limiter to protect against IP bans

    Tracks requests per platform and enforces delays
    """

    # Default rate limits per platform (requests per hour)
    DEFAULT_LIMITS = {
        'reddit': 60,  # Reddit API allows 60 requests per minute, but be conservative
        'twitter': 20,  # Twitter scraping is very risky - very low limit
        'youtube': 100,  # YouTube API has quota system
        'hackernews': 120,  # HackerNews is permissive
        'google_news': 100,  # RSS feeds are generally okay
        'western_news': 200,  # RSS feeds for news sites
    }

    # Minimum delay between requests per platform (seconds)
    MIN_DELAYS = {
        'reddit': 2.0,
        'twitter': 10.0,  # Very high to avoid bans
        'youtube': 1.0,
        'hackernews': 1.0,
        'google_news': 2.0,
        'western_news': 2.0,
    }

    def __init__(self, custom_limits: Optional[Dict] = None):
        """
        Initialize rate limiter

        Args:
            custom_limits: Custom rate limits (requests per hour) per platform
        """
        self.limits = {**self.DEFAULT_LIMITS}
        if custom_limits:
            self.limits.update(custom_limits)

        # Track requests per platform
        self.request_counts: Dict[str, list] = defaultdict(list)

        # Track last request time per platform
        self.last_request: Dict[str, float] = {}

        # Thread lock for thread-safe operations
        self.lock = threading.Lock()

        logger.info("Rate limiter initialized")
        logger.info(f"Rate limits: {self.limits}")

    def _clean_old_requests(self, platform: str):
        """Remove request timestamps older than 1 hour"""
        cutoff = time.time() - 3600  # 1 hour ago
        with self.lock:
            self.request_counts[platform] = [
                ts for ts in self.request_counts[platform]
                if ts > cutoff
            ]

    def can_make_request(self, platform: str) -> tuple[bool, Optional[str]]:
        """
        Check if a request can be made for the platform

        Args:
            platform: Platform name

        Returns:
            Tuple of (can_make_request, reason_if_not)
        """
        with self.lock:
            # Clean old requests
            self._clean_old_requests(platform)

            # Get current count
            current_count = len(self.request_counts[platform])
            limit = self.limits.get(platform, 100)

            # Check if over limit
            if current_count >= limit:
                return False, f"Rate limit exceeded: {current_count}/{limit} requests in past hour"

            # Check minimum delay
            min_delay = self.MIN_DELAYS.get(platform, 2.0)
            if platform in self.last_request:
                time_since_last = time.time() - self.last_request[platform]
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    return False, f"Too soon since last request. Wait {wait_time:.1f}s"

            return True, None

    def wait_if_needed(self, platform: str):
        """
        Wait if necessary to respect rate limits

        Args:
            platform: Platform name
        """
        min_delay = self.MIN_DELAYS.get(platform, 2.0)

        with self.lock:
            if platform in self.last_request:
                time_since_last = time.time() - self.last_request[platform]
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    logger.debug(f"Waiting {wait_time:.1f}s for rate limit ({platform})...")
                    time.sleep(wait_time)

    def record_request(self, platform: str):
        """
        Record that a request was made

        Args:
            platform: Platform name
        """
        with self.lock:
            current_time = time.time()
            self.request_counts[platform].append(current_time)
            self.last_request[platform] = current_time

            # Clean old requests
            self._clean_old_requests(platform)

            # Log warning if approaching limit
            current_count = len(self.request_counts[platform])
            limit = self.limits.get(platform, 100)

            if current_count >= limit * 0.8:
                logger.warning(
                    f"⚠️  Approaching rate limit for {platform}: "
                    f"{current_count}/{limit} requests in past hour"
                )

    def make_request(self, platform: str, request_func, *args, **kwargs):
        """
        Make a request with automatic rate limiting

        Args:
            platform: Platform name
            request_func: Function to call for the request
            *args, **kwargs: Arguments to pass to request_func

        Returns:
            Result of request_func

        Raises:
            Exception: If rate limit is exceeded
        """
        # Check if we can make request
        can_request, reason = self.can_make_request(platform)

        if not can_request:
            raise Exception(f"Rate limit error for {platform}: {reason}")

        # Wait if needed
        self.wait_if_needed(platform)

        # Make request
        try:
            result = request_func(*args, **kwargs)
            self.record_request(platform)
            return result
        except Exception as e:
            logger.error(f"Request failed for {platform}: {e}")
            # Still record the request to maintain rate limiting
            self.record_request(platform)
            raise

    def get_stats(self, platform: Optional[str] = None) -> Dict:
        """
        Get statistics about request usage

        Args:
            platform: Platform name (None for all platforms)

        Returns:
            Dictionary with statistics
        """
        with self.lock:
            if platform:
                self._clean_old_requests(platform)
                current_count = len(self.request_counts[platform])
                limit = self.limits.get(platform, 100)

                return {
                    'platform': platform,
                    'requests_last_hour': current_count,
                    'limit': limit,
                    'remaining': max(0, limit - current_count),
                    'percentage_used': (current_count / limit * 100) if limit > 0 else 0
                }
            else:
                # Get stats for all platforms
                stats = {}
                for plat in self.request_counts.keys():
                    self._clean_old_requests(plat)
                    current_count = len(self.request_counts[plat])
                    limit = self.limits.get(plat, 100)

                    stats[plat] = {
                        'requests_last_hour': current_count,
                        'limit': limit,
                        'remaining': max(0, limit - current_count),
                        'percentage_used': (current_count / limit * 100) if limit > 0 else 0
                    }

                return stats

    def reset_platform(self, platform: str):
        """Reset request count for a platform"""
        with self.lock:
            self.request_counts[platform] = []
            if platform in self.last_request:
                del self.last_request[platform]
            logger.info(f"Reset rate limiter for {platform}")

    def print_status(self):
        """Print current rate limiting status"""
        stats = self.get_stats()

        logger.info("\n" + "=" * 60)
        logger.info("Rate Limiter Status")
        logger.info("=" * 60)

        if not stats:
            logger.info("No requests made yet")
            return

        for platform, data in stats.items():
            logger.info(
                f"{platform:15s} | "
                f"{data['requests_last_hour']:3d}/{data['limit']:3d} requests | "
                f"{data['percentage_used']:5.1f}% used | "
                f"{data['remaining']:3d} remaining"
            )

        logger.info("=" * 60)


# Global rate limiter instance
_global_rate_limiter = None


def get_rate_limiter(custom_limits: Optional[Dict] = None) -> RateLimiter:
    """
    Get or create global rate limiter instance

    Args:
        custom_limits: Custom rate limits (only used on first call)

    Returns:
        RateLimiter instance
    """
    global _global_rate_limiter

    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(custom_limits)

    return _global_rate_limiter


def main():
    """Test rate limiter"""
    logger.info("Testing Rate Limiter...")

    # Create rate limiter with low limits for testing
    limiter = RateLimiter(custom_limits={
        'test_platform': 5,  # 5 requests per hour
    })

    # Test making requests
    platform = 'test_platform'

    logger.info(f"\nMaking test requests to {platform}...")

    for i in range(7):
        can_request, reason = limiter.can_make_request(platform)

        if can_request:
            logger.info(f"Request {i+1}: ✓ Allowed")
            limiter.record_request(platform)
            time.sleep(0.5)
        else:
            logger.warning(f"Request {i+1}: ✗ Denied - {reason}")

    # Print status
    limiter.print_status()

    logger.info("\n✓ Rate limiter test complete!")


if __name__ == "__main__":
    main()
