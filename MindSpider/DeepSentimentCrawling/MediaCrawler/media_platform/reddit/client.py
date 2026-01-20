# -*- coding: utf-8 -*-
"""
Reddit API client wrapper using PRAW.

Provides a unified interface for Reddit operations with OAuth authentication
and built-in rate limiting.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import praw
    from praw.models import Submission, Comment, Redditor
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    praw = None
    Submission = None
    Comment = None
    Redditor = None

try:
    from config import settings
except ImportError:
    settings = None


class RedditClient:
    """
    Reddit API client wrapper with PRAW.

    PRAW handles OAuth authentication and rate limiting automatically.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        if not PRAW_AVAILABLE:
            raise ImportError(
                "praw not installed. Install with: pip install praw>=7.7.0"
            )

        # Get credentials
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent or "BettaFish/1.0"

        if settings:
            self.client_id = self.client_id or settings.REDDIT_CLIENT_ID
            self.client_secret = self.client_secret or settings.REDDIT_CLIENT_SECRET
            self.user_agent = settings.REDDIT_USER_AGENT or self.user_agent

        self.reddit = None
        self.is_authenticated = False

    def authenticate(self) -> bool:
        """
        Initialize Reddit client with OAuth credentials.

        Uses read-only mode (no user login required).

        Returns:
            True if authentication successful
        """
        if not self.client_id or not self.client_secret:
            logger.error(
                "Reddit: Missing credentials. "
                "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET"
            )
            return False

        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            # PRAW uses read-only mode by default when no user credentials
            self.is_authenticated = True
            logger.info("Reddit: Authenticated successfully (read-only mode)")
            return True
        except Exception as e:
            logger.error(f"Reddit: Authentication failed: {e}")
            return False

    def _ensure_authenticated(self) -> bool:
        """Ensure client is authenticated."""
        if not self.is_authenticated:
            return self.authenticate()
        return True

    def search_posts(
        self,
        query: str,
        subreddit: Optional[str] = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search for posts matching query.

        Args:
            query: Search query string
            subreddit: Limit to specific subreddit (None for all)
            sort: Sort by: relevance, hot, top, new, comments
            time_filter: Time filter: all, day, hour, month, week, year
            limit: Maximum posts to return

        Returns:
            List of post dictionaries
        """
        if not self._ensure_authenticated():
            return []

        results = []
        try:
            if subreddit:
                sub = self.reddit.subreddit(subreddit)
                submissions = sub.search(
                    query,
                    sort=sort,
                    time_filter=time_filter,
                    limit=limit
                )
            else:
                submissions = self.reddit.subreddit("all").search(
                    query,
                    sort=sort,
                    time_filter=time_filter,
                    limit=limit
                )

            for submission in submissions:
                parsed = self._parse_submission(submission)
                if parsed:
                    results.append(parsed)

            logger.info(f"Reddit: Found {len(results)} posts for '{query}'")

        except Exception as e:
            logger.error(f"Reddit: Search error: {e}")

        return results

    def get_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "hot",
        time_filter: str = "day",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            sort: Sort by: hot, new, top, rising, controversial
            time_filter: For top/controversial: all, day, hour, month, week, year
            limit: Maximum posts to return

        Returns:
            List of post dictionaries
        """
        if not self._ensure_authenticated():
            return []

        results = []
        try:
            sub = self.reddit.subreddit(subreddit)

            if sort == "hot":
                submissions = sub.hot(limit=limit)
            elif sort == "new":
                submissions = sub.new(limit=limit)
            elif sort == "top":
                submissions = sub.top(time_filter=time_filter, limit=limit)
            elif sort == "rising":
                submissions = sub.rising(limit=limit)
            elif sort == "controversial":
                submissions = sub.controversial(time_filter=time_filter, limit=limit)
            else:
                submissions = sub.hot(limit=limit)

            for submission in submissions:
                parsed = self._parse_submission(submission)
                if parsed:
                    results.append(parsed)

            logger.info(f"Reddit: Got {len(results)} posts from r/{subreddit}")

        except Exception as e:
            logger.error(f"Reddit: Failed to get subreddit posts: {e}")

        return results

    def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        """Get a single post by ID."""
        if not self._ensure_authenticated():
            return None

        try:
            submission = self.reddit.submission(id=post_id)
            return self._parse_submission(submission)
        except Exception as e:
            logger.error(f"Reddit: Failed to get post {post_id}: {e}")
            return None

    def get_post_comments(
        self,
        post_id: str,
        sort: str = "best",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get comments for a post.

        Args:
            post_id: Post ID
            sort: Sort by: best, top, new, controversial, old, qa
            limit: Maximum comments to return

        Returns:
            List of comment dictionaries
        """
        if not self._ensure_authenticated():
            return []

        results = []
        try:
            submission = self.reddit.submission(id=post_id)
            submission.comment_sort = sort
            submission.comments.replace_more(limit=0)  # Don't expand "more comments"

            count = 0
            for comment in submission.comments.list():
                if count >= limit:
                    break
                parsed = self._parse_comment(comment, post_id)
                if parsed:
                    results.append(parsed)
                    count += 1

            logger.info(f"Reddit: Got {len(results)} comments for post {post_id}")

        except Exception as e:
            logger.error(f"Reddit: Failed to get comments for {post_id}: {e}")

        return results

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user profile by username."""
        if not self._ensure_authenticated():
            return None

        try:
            redditor = self.reddit.redditor(username)
            return self._parse_redditor(redditor)
        except Exception as e:
            logger.error(f"Reddit: Failed to get user {username}: {e}")
            return None

    def _parse_submission(self, submission: Submission) -> Optional[Dict[str, Any]]:
        """Parse PRAW submission object to dictionary."""
        try:
            author_name = str(submission.author) if submission.author else "[deleted]"
            author_id = submission.author.id if submission.author else None

            return {
                "id": submission.id,
                "post_id": submission.id,
                "platform": "reddit",
                "subreddit": submission.subreddit.display_name,
                "author": author_name,
                "author_id": author_id,
                "title": submission.title,
                "content": submission.selftext,
                "selftext": submission.selftext,
                "content_html": submission.selftext_html,
                "url": f"https://reddit.com{submission.permalink}",
                "post_url": f"https://reddit.com{submission.permalink}",
                "created_at": int(submission.created_utc),
                "created_utc": int(submission.created_utc),
                "score": submission.score,
                "upvote_ratio": submission.upvote_ratio,
                "num_comments": submission.num_comments,
                "is_self": submission.is_self,
                "is_video": submission.is_video,
                "media_url": submission.url if not submission.is_self else None,
                "thumbnail": submission.thumbnail if submission.thumbnail != "self" else None,
                "flair": submission.link_flair_text,
                "link_flair_text": submission.link_flair_text,
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Reddit: Failed to parse submission: {e}")
            return None

    def _parse_comment(self, comment: Comment, post_id: str) -> Optional[Dict[str, Any]]:
        """Parse PRAW comment object to dictionary."""
        try:
            author_name = str(comment.author) if comment.author else "[deleted]"
            author_id = comment.author.id if comment.author else None

            # Get parent ID (strip prefix)
            parent_id = comment.parent_id
            if parent_id.startswith("t1_"):
                parent_id = parent_id[3:]  # Comment parent
            elif parent_id.startswith("t3_"):
                parent_id = None  # Post is parent (top-level comment)

            return {
                "id": comment.id,
                "comment_id": comment.id,
                "post_id": post_id,
                "subreddit": comment.subreddit.display_name,
                "author": author_name,
                "author_id": author_id,
                "content": comment.body,
                "body": comment.body,
                "content_html": comment.body_html,
                "body_html": comment.body_html,
                "created_at": int(comment.created_utc),
                "created_utc": int(comment.created_utc),
                "score": comment.score,
                "parent_comment_id": parent_id,
                "parent_id": parent_id,
                "depth": comment.depth,
                "is_submitter": comment.is_submitter,
            }
        except Exception as e:
            logger.warning(f"Reddit: Failed to parse comment: {e}")
            return None

    def _parse_redditor(self, redditor: Redditor) -> Optional[Dict[str, Any]]:
        """Parse PRAW redditor object to dictionary."""
        try:
            return {
                "id": redditor.id,
                "user_id": redditor.id,
                "username": redditor.name,
                "name": redditor.name,
                "created_at": int(redditor.created_utc),
                "created_utc": int(redditor.created_utc),
                "link_karma": redditor.link_karma,
                "comment_karma": redditor.comment_karma,
                "is_gold": redditor.is_gold,
                "is_mod": redditor.is_mod,
                "has_verified_email": redditor.has_verified_email,
            }
        except Exception as e:
            logger.warning(f"Reddit: Failed to parse redditor: {e}")
            return None
