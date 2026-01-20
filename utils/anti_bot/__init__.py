"""
Anti-bot and Cloudflare protection utilities.

Provides mechanisms to bypass bot detection and rate limiting:
- User agent rotation
- Request rate limiting
- Cookie persistence
- Proxy support
- Browser fingerprint randomization
"""

from .protection import (
    AntiBotProtection,
    RateLimiter,
    UserAgentRotator,
    CookieManager,
    ProxyManager,
)

__all__ = [
    "AntiBotProtection",
    "RateLimiter",
    "UserAgentRotator",
    "CookieManager",
    "ProxyManager",
]
