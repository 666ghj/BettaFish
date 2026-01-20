"""
Anti-bot protection utilities for web crawling.

Provides robust mechanisms to avoid detection and blocking:
- User agent rotation with realistic browser profiles
- Intelligent rate limiting per domain
- Cookie persistence and management
- Proxy rotation support
- Request header randomization
"""

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from loguru import logger

try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False
    UserAgent = None


# Realistic browser user agents as fallback
DEFAULT_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Common accept headers
ACCEPT_HEADERS = {
    "html": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "json": "application/json, text/plain, */*",
    "xml": "application/xml, text/xml, */*",
    "any": "*/*",
}

# Accept-Language variations
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en,zh-CN;q=0.9,zh;q=0.8",
]


class UserAgentRotator:
    """Rotates user agents to avoid fingerprinting."""

    def __init__(self, custom_agents: Optional[List[str]] = None):
        """
        Initialize with optional custom user agent list.

        Args:
            custom_agents: Optional list of custom user agents
        """
        self._custom_agents = custom_agents
        self._fake_ua = None
        self._index = 0

        if FAKE_UA_AVAILABLE:
            try:
                self._fake_ua = UserAgent()
            except Exception as e:
                logger.warning(f"Failed to initialize fake_useragent: {e}")

    def get_random(self) -> str:
        """Get a random user agent string."""
        # Priority: custom > fake_useragent > default list
        if self._custom_agents:
            return random.choice(self._custom_agents)

        if self._fake_ua:
            try:
                return self._fake_ua.random
            except Exception:
                pass

        return random.choice(DEFAULT_USER_AGENTS)

    def get_next(self) -> str:
        """Get user agent in rotation (round-robin)."""
        agents = self._custom_agents or DEFAULT_USER_AGENTS
        ua = agents[self._index % len(agents)]
        self._index += 1
        return ua


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 10
    requests_per_hour: int = 100
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 5.0
    burst_limit: int = 5  # Max requests in quick succession
    burst_cooldown: float = 30.0  # Cooldown after burst


class RateLimiter:
    """
    Intelligent rate limiter with per-domain tracking.

    Features:
    - Per-domain rate limiting
    - Burst detection and cooldown
    - Adaptive delays based on response patterns
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._domain_stats: Dict[str, Dict[str, Any]] = {}
        self._global_last_request = 0.0

    def _get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """Get or create domain statistics."""
        if domain not in self._domain_stats:
            self._domain_stats[domain] = {
                "request_times": [],
                "last_request": 0.0,
                "burst_count": 0,
                "in_cooldown": False,
                "cooldown_until": 0.0,
                "error_count": 0,
            }
        return self._domain_stats[domain]

    def _cleanup_old_requests(self, stats: Dict[str, Any], window_seconds: int = 3600):
        """Remove request times older than window."""
        cutoff = time.time() - window_seconds
        stats["request_times"] = [t for t in stats["request_times"] if t > cutoff]

    async def wait_if_needed(self, domain: str) -> float:
        """
        Wait if rate limit would be exceeded.

        Args:
            domain: Target domain

        Returns:
            Actual wait time in seconds
        """
        stats = self._get_domain_stats(domain)
        self._cleanup_old_requests(stats)
        now = time.time()

        # Check if in cooldown
        if stats["in_cooldown"] and now < stats["cooldown_until"]:
            wait_time = stats["cooldown_until"] - now
            logger.debug(f"Domain {domain} in cooldown, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            stats["in_cooldown"] = False
            stats["burst_count"] = 0
            return wait_time

        # Check requests per minute
        minute_ago = now - 60
        recent_requests = [t for t in stats["request_times"] if t > minute_ago]
        if len(recent_requests) >= self.config.requests_per_minute:
            wait_time = 60 - (now - min(recent_requests))
            logger.debug(f"Rate limit (per-minute) for {domain}, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            return wait_time

        # Check requests per hour
        if len(stats["request_times"]) >= self.config.requests_per_hour:
            wait_time = 3600 - (now - min(stats["request_times"]))
            logger.warning(f"Rate limit (per-hour) for {domain}, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            return wait_time

        # Check burst limit
        burst_window = now - 5  # 5 second window for burst detection
        burst_requests = [t for t in stats["request_times"] if t > burst_window]
        if len(burst_requests) >= self.config.burst_limit:
            stats["in_cooldown"] = True
            stats["cooldown_until"] = now + self.config.burst_cooldown
            logger.debug(f"Burst detected for {domain}, entering cooldown")
            await asyncio.sleep(self.config.burst_cooldown)
            return self.config.burst_cooldown

        # Normal delay with jitter
        time_since_last = now - stats["last_request"]
        if time_since_last < self.config.min_delay_seconds:
            delay = self.config.min_delay_seconds - time_since_last
            # Add random jitter
            delay += random.uniform(0, self.config.max_delay_seconds - self.config.min_delay_seconds)
            await asyncio.sleep(delay)
            return delay

        return 0.0

    def record_request(self, domain: str, success: bool = True):
        """
        Record a completed request.

        Args:
            domain: Target domain
            success: Whether request was successful
        """
        stats = self._get_domain_stats(domain)
        now = time.time()
        stats["request_times"].append(now)
        stats["last_request"] = now

        if not success:
            stats["error_count"] += 1
            # Increase cooldown on errors
            if stats["error_count"] >= 3:
                stats["in_cooldown"] = True
                stats["cooldown_until"] = now + self.config.burst_cooldown * 2
                logger.warning(f"Multiple errors for {domain}, extending cooldown")
        else:
            stats["error_count"] = 0

    def get_stats(self, domain: str) -> Dict[str, Any]:
        """Get current stats for a domain."""
        stats = self._get_domain_stats(domain)
        self._cleanup_old_requests(stats)
        return {
            "requests_last_minute": len([t for t in stats["request_times"] if t > time.time() - 60]),
            "requests_last_hour": len(stats["request_times"]),
            "in_cooldown": stats["in_cooldown"],
            "error_count": stats["error_count"],
        }


class CookieManager:
    """
    Manages cookie persistence for maintaining sessions.

    Features:
    - Save/load cookies to/from file
    - Per-domain cookie storage
    - Cookie expiration handling
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize cookie manager.

        Args:
            storage_dir: Directory for cookie storage
        """
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".bettafish" / "cookies"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cookies: Dict[str, Dict[str, str]] = {}

    def _get_cookie_file(self, domain: str) -> Path:
        """Get cookie file path for domain."""
        safe_domain = domain.replace(".", "_").replace(":", "_")
        return self.storage_dir / f"{safe_domain}.json"

    def save_cookies(self, domain: str, cookies: Dict[str, str]):
        """
        Save cookies for a domain.

        Args:
            domain: Target domain
            cookies: Cookie dictionary
        """
        self._cookies[domain] = cookies
        cookie_file = self._get_cookie_file(domain)
        try:
            with open(cookie_file, "w") as f:
                json.dump({
                    "domain": domain,
                    "cookies": cookies,
                    "saved_at": datetime.now().isoformat(),
                }, f, indent=2)
            logger.debug(f"Saved cookies for {domain}")
        except Exception as e:
            logger.warning(f"Failed to save cookies for {domain}: {e}")

    def load_cookies(self, domain: str) -> Optional[Dict[str, str]]:
        """
        Load cookies for a domain.

        Args:
            domain: Target domain

        Returns:
            Cookie dictionary or None
        """
        # Check memory cache first
        if domain in self._cookies:
            return self._cookies[domain]

        # Try loading from file
        cookie_file = self._get_cookie_file(domain)
        if cookie_file.exists():
            try:
                with open(cookie_file, "r") as f:
                    data = json.load(f)
                    cookies = data.get("cookies", {})
                    self._cookies[domain] = cookies
                    logger.debug(f"Loaded cookies for {domain}")
                    return cookies
            except Exception as e:
                logger.warning(f"Failed to load cookies for {domain}: {e}")

        return None

    def clear_cookies(self, domain: str):
        """Clear cookies for a domain."""
        self._cookies.pop(domain, None)
        cookie_file = self._get_cookie_file(domain)
        if cookie_file.exists():
            cookie_file.unlink()


class ProxyManager:
    """
    Manages proxy rotation for distributed requests.

    Features:
    - Proxy pool management
    - Health checking
    - Automatic rotation on failure
    """

    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize proxy manager.

        Args:
            proxies: List of proxy URLs (http://host:port or socks5://host:port)
        """
        self._proxies = proxies or []
        self._healthy_proxies: Set[str] = set(self._proxies)
        self._failed_proxies: Dict[str, float] = {}  # proxy -> failure time
        self._index = 0

    def add_proxy(self, proxy: str):
        """Add a proxy to the pool."""
        if proxy not in self._proxies:
            self._proxies.append(proxy)
            self._healthy_proxies.add(proxy)

    def remove_proxy(self, proxy: str):
        """Remove a proxy from the pool."""
        if proxy in self._proxies:
            self._proxies.remove(proxy)
        self._healthy_proxies.discard(proxy)

    def get_proxy(self) -> Optional[str]:
        """
        Get next healthy proxy (round-robin).

        Returns:
            Proxy URL or None if no healthy proxies
        """
        if not self._healthy_proxies:
            # Try recovering failed proxies after cooldown
            now = time.time()
            recovered = [
                p for p, t in self._failed_proxies.items()
                if now - t > 300  # 5 minute cooldown
            ]
            for proxy in recovered:
                self._healthy_proxies.add(proxy)
                del self._failed_proxies[proxy]

        if not self._healthy_proxies:
            return None

        healthy_list = list(self._healthy_proxies)
        proxy = healthy_list[self._index % len(healthy_list)]
        self._index += 1
        return proxy

    def mark_failed(self, proxy: str):
        """Mark a proxy as failed."""
        self._healthy_proxies.discard(proxy)
        self._failed_proxies[proxy] = time.time()
        logger.warning(f"Proxy marked as failed: {proxy}")

    def mark_healthy(self, proxy: str):
        """Mark a proxy as healthy."""
        if proxy in self._proxies:
            self._healthy_proxies.add(proxy)
            self._failed_proxies.pop(proxy, None)

    @property
    def healthy_count(self) -> int:
        """Get count of healthy proxies."""
        return len(self._healthy_proxies)


class AntiBotProtection:
    """
    Unified anti-bot protection combining all strategies.

    Usage:
        protection = AntiBotProtection()

        async with protection.protected_request("example.com") as ctx:
            headers = ctx.get_headers()
            # Make request with headers
            ctx.record_success()  # or ctx.record_failure()
    """

    def __init__(
        self,
        rate_limit_config: Optional[RateLimitConfig] = None,
        proxies: Optional[List[str]] = None,
        cookie_storage_dir: Optional[str] = None,
    ):
        """
        Initialize anti-bot protection.

        Args:
            rate_limit_config: Rate limiting configuration
            proxies: List of proxy URLs
            cookie_storage_dir: Directory for cookie storage
        """
        self.user_agent_rotator = UserAgentRotator()
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.cookie_manager = CookieManager(cookie_storage_dir)
        self.proxy_manager = ProxyManager(proxies)

    def get_headers(
        self,
        accept_type: str = "html",
        referer: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Get randomized request headers.

        Args:
            accept_type: Accept header type (html, json, xml, any)
            referer: Optional referer URL
            extra_headers: Additional headers to include

        Returns:
            Headers dictionary
        """
        headers = {
            "User-Agent": self.user_agent_rotator.get_random(),
            "Accept": ACCEPT_HEADERS.get(accept_type, ACCEPT_HEADERS["any"]),
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "cross-site",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        if referer:
            headers["Referer"] = referer

        if extra_headers:
            headers.update(extra_headers)

        return headers

    async def wait_for_rate_limit(self, domain: str) -> float:
        """Wait if rate limit would be exceeded."""
        return await self.rate_limiter.wait_if_needed(domain)

    def record_request(self, domain: str, success: bool = True):
        """Record a completed request."""
        self.rate_limiter.record_request(domain, success)

    def get_proxy(self) -> Optional[str]:
        """Get a proxy for the request."""
        return self.proxy_manager.get_proxy()

    def save_cookies(self, domain: str, cookies: Dict[str, str]):
        """Save cookies for a domain."""
        self.cookie_manager.save_cookies(domain, cookies)

    def load_cookies(self, domain: str) -> Optional[Dict[str, str]]:
        """Load cookies for a domain."""
        return self.cookie_manager.load_cookies(domain)
