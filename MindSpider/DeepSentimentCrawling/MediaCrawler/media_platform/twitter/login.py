# -*- coding: utf-8 -*-
"""
Twitter/X login and session management.

Handles cookie-based authentication, session persistence, and credential management.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from twikit import Client
    from twikit.errors import Unauthorized
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False
    Client = None
    Unauthorized = Exception

try:
    from config import settings
except ImportError:
    settings = None


class TwitterLoginManager:
    """
    Manages Twitter login sessions and cookie persistence.

    Supports:
    - Cookie-based authentication (bypasses most anti-bot)
    - Credential-based login with automatic cookie saving
    - Session validation and refresh
    """

    DEFAULT_COOKIES_PATH = "twitter_cookies.json"

    def __init__(self, cookies_path: Optional[str] = None):
        if not TWIKIT_AVAILABLE:
            raise ImportError(
                "twikit not installed. Install with: pip install twikit>=2.0.0"
            )

        self.client = Client('en-US')
        self.cookies_path = cookies_path or self.DEFAULT_COOKIES_PATH
        self.is_logged_in = False

        # Load from config if available
        if settings and not cookies_path:
            if settings.TWITTER_COOKIES_PATH:
                self.cookies_path = settings.TWITTER_COOKIES_PATH

    async def login_with_cookies(self, cookies_path: Optional[str] = None) -> bool:
        """
        Login using saved cookies.

        Args:
            cookies_path: Path to cookies file. Uses default if not provided.

        Returns:
            True if login successful
        """
        path = cookies_path or self.cookies_path
        if not Path(path).exists():
            logger.warning(f"Twitter: Cookies file not found: {path}")
            return False

        try:
            self.client.load_cookies(path)
            self.is_logged_in = True
            logger.info(f"Twitter: Loaded cookies from {path}")
            return True
        except Exception as e:
            logger.error(f"Twitter: Failed to load cookies: {e}")
            return False

    async def login_with_credentials(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        save_cookies: bool = True,
    ) -> bool:
        """
        Login with username/email/password.

        Args:
            username: Twitter username (without @)
            email: Account email
            password: Account password
            save_cookies: Whether to save cookies after successful login

        Returns:
            True if login successful
        """
        # Get credentials from params or config
        auth_username = username
        auth_email = email
        auth_password = password

        if settings:
            auth_username = auth_username or settings.TWITTER_USERNAME
            auth_email = auth_email or settings.TWITTER_EMAIL
            auth_password = auth_password or settings.TWITTER_PASSWORD

        if not all([auth_username, auth_email, auth_password]):
            logger.error(
                "Twitter: Missing credentials. "
                "Provide username, email, and password or set in config."
            )
            return False

        try:
            await self.client.login(
                auth_info_1=auth_username,
                auth_info_2=auth_email,
                password=auth_password
            )
            self.is_logged_in = True
            logger.info("Twitter: Login successful")

            if save_cookies:
                self.save_cookies()

            return True
        except Unauthorized as e:
            logger.error(f"Twitter: Invalid credentials: {e}")
            return False
        except Exception as e:
            logger.error(f"Twitter: Login failed: {e}")
            return False

    async def auto_login(self) -> bool:
        """
        Automatically login using best available method.

        Tries in order:
        1. Load cookies from file
        2. Login with config credentials

        Returns:
            True if login successful
        """
        # Try cookies first
        if await self.login_with_cookies():
            return True

        # Fall back to credentials
        return await self.login_with_credentials()

    def save_cookies(self, path: Optional[str] = None):
        """Save current session cookies to file."""
        save_path = path or self.cookies_path
        try:
            self.client.save_cookies(save_path)
            logger.info(f"Twitter: Saved cookies to {save_path}")
        except Exception as e:
            logger.error(f"Twitter: Failed to save cookies: {e}")

    def clear_cookies(self, path: Optional[str] = None):
        """Delete saved cookies file."""
        clear_path = path or self.cookies_path
        if Path(clear_path).exists():
            try:
                os.remove(clear_path)
                logger.info(f"Twitter: Deleted cookies file: {clear_path}")
            except Exception as e:
                logger.error(f"Twitter: Failed to delete cookies: {e}")

    async def validate_session(self) -> bool:
        """
        Check if current session is still valid.

        Returns:
            True if session is valid
        """
        if not self.is_logged_in:
            return False

        try:
            # Try a simple API call to validate session
            await self.client.get_user_by_screen_name("twitter")
            return True
        except Unauthorized:
            logger.warning("Twitter: Session expired or invalid")
            self.is_logged_in = False
            return False
        except Exception as e:
            logger.warning(f"Twitter: Session validation failed: {e}")
            return False

    async def refresh_session(self) -> bool:
        """
        Refresh an expired session.

        Returns:
            True if refresh successful
        """
        logger.info("Twitter: Attempting session refresh...")
        self.is_logged_in = False
        return await self.auto_login()

    def get_client(self) -> Optional[Client]:
        """Get the underlying twikit client."""
        return self.client if self.is_logged_in else None


async def create_authenticated_client(
    cookies_path: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[Client]:
    """
    Create and authenticate a Twitter client.

    Convenience function for quick client creation.

    Args:
        cookies_path: Path to cookies file
        username: Twitter username
        email: Account email
        password: Account password

    Returns:
        Authenticated twikit Client or None
    """
    manager = TwitterLoginManager(cookies_path)

    if await manager.login_with_cookies():
        return manager.get_client()

    if await manager.login_with_credentials(username, email, password):
        return manager.get_client()

    return None
