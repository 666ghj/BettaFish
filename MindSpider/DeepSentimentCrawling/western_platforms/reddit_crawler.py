#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reddit Crawler Module
Fetches posts and comments from Reddit using PRAW (Python Reddit API Wrapper)
Requires Reddit API credentials (free tier available)
"""

import os
import asyncio
import praw
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()


class RedditCrawler:
    """
    Reddit crawler using PRAW library
    Requires Reddit API credentials (free, rate-limited)

    To get credentials:
    1. Go to https://www.reddit.com/prefs/apps
    2. Click "Create App" or "Create Another App"
    3. Select "script" type
    4. Get your client_id and client_secret
    """

    # Popular subreddits for different categories
    POLITICS_SUBS = {
        'left': ['politics', 'Democrats', 'liberal', 'progressive'],
        'right': ['Conservative', 'Republican', 'conservatives'],
        'center': ['PoliticalDiscussion', 'neutralpolitics', 'moderatepolitics']
    }

    TECH_SUBS = ['technology', 'programming', 'artificial', 'MachineLearning',
                 'datascience', 'Python', 'webdev', 'startups']

    NEWS_SUBS = ['news', 'worldnews', 'UpliftingNews', 'nottheonion']

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        rate_limit_delay: float = 2.0
    ):
        """
        Initialize Reddit crawler

        Args:
            client_id: Reddit API client ID (from env if not provided)
            client_secret: Reddit API client secret (from env if not provided)
            user_agent: User agent string (from env if not provided)
            rate_limit_delay: Additional delay between requests in seconds
        """
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'BettaFish/1.0')
        self.rate_limit_delay = rate_limit_delay

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Reddit API credentials not found. Please set REDDIT_CLIENT_ID "
                "and REDDIT_CLIENT_SECRET in .env file or pass them as arguments."
            )

        # Initialize Reddit instance
        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
        )

        # Set to read-only mode (no posting/voting)
        self.reddit.read_only = True

        logger.info(f"Reddit crawler initialized (read-only mode)")

    def _parse_submission_to_post(self, submission) -> Dict:
        """
        Parse Reddit submission to database post format

        Args:
            submission: PRAW Submission object

        Returns:
            Formatted post dictionary
        """
        try:
            return {
                'post_id': submission.id,
                'subreddit': submission.subreddit.display_name,
                'title': submission.title[:500],
                'author': str(submission.author) if submission.author else '[deleted]',
                'content': submission.selftext if submission.is_self else '',
                'url': submission.url[:512],
                'score': submission.score,
                'upvote_ratio': submission.upvote_ratio,
                'num_comments': submission.num_comments,
                'created_utc': int(submission.created_utc),
                'flair_text': submission.link_flair_text or '',
                'is_self': 1 if submission.is_self else 0,
                'permalink': f"https://reddit.com{submission.permalink}",
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse submission {submission.id}: {e}")
            return None

    def _parse_comment(self, comment, post_id: str) -> Optional[Dict]:
        """
        Parse Reddit comment to database format

        Args:
            comment: PRAW Comment object
            post_id: Parent post ID

        Returns:
            Formatted comment dictionary or None
        """
        try:
            # Skip deleted/removed comments
            if comment.author is None or comment.body == '[deleted]':
                return None

            return {
                'comment_id': comment.id,
                'post_id': post_id,
                'parent_id': comment.parent_id.split('_')[1] if '_' in comment.parent_id else '',
                'author': str(comment.author),
                'content': comment.body[:2000],  # Limit content length
                'score': comment.score,
                'created_utc': int(comment.created_utc),
                'depth': comment.depth,
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse comment: {e}")
            return None

    def crawl_subreddit(
        self,
        subreddit_name: str,
        sort: str = 'hot',
        limit: int = 25,
        fetch_comments: bool = True,
        max_comments_per_post: int = 50
    ) -> Dict:
        """
        Crawl posts from a subreddit

        Args:
            subreddit_name: Name of the subreddit (without 'r/')
            sort: Sort method ('hot', 'new', 'top', 'rising')
            limit: Number of posts to fetch
            fetch_comments: Whether to fetch comments
            max_comments_per_post: Maximum comments to fetch per post

        Returns:
            Dictionary with posts and comments
        """
        logger.info(f"Crawling r/{subreddit_name} ({sort}, limit={limit})...")

        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get submissions based on sort method
            if sort == 'hot':
                submissions = subreddit.hot(limit=limit)
            elif sort == 'new':
                submissions = subreddit.new(limit=limit)
            elif sort == 'top':
                submissions = subreddit.top(time_filter='day', limit=limit)
            elif sort == 'rising':
                submissions = subreddit.rising(limit=limit)
            else:
                submissions = subreddit.hot(limit=limit)

            posts = []
            comments = []

            for submission in submissions:
                # Parse post
                post = self._parse_submission_to_post(submission)
                if post:
                    posts.append(post)

                    # Fetch comments if requested
                    if fetch_comments:
                        try:
                            # Load comments (replace MoreComments)
                            submission.comments.replace_more(limit=0)

                            # Get top-level and nested comments
                            comment_count = 0
                            for comment in submission.comments.list():
                                if comment_count >= max_comments_per_post:
                                    break

                                parsed_comment = self._parse_comment(comment, post['post_id'])
                                if parsed_comment:
                                    comments.append(parsed_comment)
                                    comment_count += 1

                        except Exception as e:
                            logger.error(f"Failed to fetch comments for post {post['post_id']}: {e}")

                # Rate limiting
                time.sleep(self.rate_limit_delay)

            logger.info(f"✓ r/{subreddit_name}: {len(posts)} posts, {len(comments)} comments")

            return {
                'posts': posts,
                'comments': comments,
                'total_posts': len(posts),
                'total_comments': len(comments),
                'subreddit': subreddit_name
            }

        except Exception as e:
            logger.error(f"Failed to crawl r/{subreddit_name}: {e}")
            return {
                'posts': [],
                'comments': [],
                'total_posts': 0,
                'total_comments': 0,
                'error': str(e)
            }

    def search_reddit(
        self,
        query: str,
        subreddit_name: Optional[str] = None,
        sort: str = 'relevance',
        time_filter: str = 'week',
        limit: int = 25
    ) -> Dict:
        """
        Search Reddit for posts matching a query

        Args:
            query: Search query
            subreddit_name: Subreddit to search in (None = all of Reddit)
            sort: Sort method ('relevance', 'hot', 'new', 'top', 'comments')
            time_filter: Time filter ('hour', 'day', 'week', 'month', 'year', 'all')
            limit: Maximum number of results

        Returns:
            Dictionary with search results
        """
        logger.info(f"Searching Reddit for '{query}'...")

        try:
            if subreddit_name:
                subreddit = self.reddit.subreddit(subreddit_name)
                logger.info(f"Searching in r/{subreddit_name}")
            else:
                subreddit = self.reddit.subreddit('all')
                logger.info("Searching all of Reddit")

            # Perform search
            search_results = subreddit.search(
                query,
                sort=sort,
                time_filter=time_filter,
                limit=limit
            )

            posts = []
            for submission in search_results:
                post = self._parse_submission_to_post(submission)
                if post:
                    posts.append(post)

                time.sleep(self.rate_limit_delay)

            logger.info(f"Found {len(posts)} posts matching '{query}'")

            return {
                'posts': posts,
                'total_posts': len(posts),
                'query': query
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                'posts': [],
                'total_posts': 0,
                'error': str(e)
            }

    def crawl_politics(
        self,
        political_lean: str = 'all',
        posts_per_sub: int = 10
    ) -> Dict:
        """
        Crawl political subreddits across the spectrum

        Args:
            political_lean: Which side to crawl ('left', 'right', 'center', 'all')
            posts_per_sub: Number of posts per subreddit

        Returns:
            Combined results from political subreddits
        """
        logger.info(f"Crawling political subreddits ({political_lean})...")

        all_posts = []
        all_comments = []

        # Determine which subreddits to crawl
        if political_lean == 'all':
            subs_to_crawl = (
                self.POLITICS_SUBS['left'] +
                self.POLITICS_SUBS['right'] +
                self.POLITICS_SUBS['center']
            )
        elif political_lean in self.POLITICS_SUBS:
            subs_to_crawl = self.POLITICS_SUBS[political_lean]
        else:
            logger.error(f"Invalid political_lean: {political_lean}")
            return {'posts': [], 'comments': [], 'total_posts': 0, 'total_comments': 0}

        # Crawl each subreddit
        for sub in subs_to_crawl:
            result = self.crawl_subreddit(
                subreddit_name=sub,
                sort='hot',
                limit=posts_per_sub,
                fetch_comments=True,
                max_comments_per_post=20
            )

            all_posts.extend(result['posts'])
            all_comments.extend(result['comments'])

        logger.info(f"Political crawl complete: {len(all_posts)} posts, {len(all_comments)} comments")

        return {
            'posts': all_posts,
            'comments': all_comments,
            'total_posts': len(all_posts),
            'total_comments': len(all_comments)
        }

    def crawl_tech_news(self, posts_per_sub: int = 10) -> Dict:
        """Crawl technology-related subreddits"""
        logger.info("Crawling tech subreddits...")

        all_posts = []
        all_comments = []

        for sub in self.TECH_SUBS[:5]:  # Limit to top 5 tech subs
            result = self.crawl_subreddit(
                subreddit_name=sub,
                sort='hot',
                limit=posts_per_sub,
                fetch_comments=True,
                max_comments_per_post=20
            )

            all_posts.extend(result['posts'])
            all_comments.extend(result['comments'])

        logger.info(f"Tech crawl complete: {len(all_posts)} posts, {len(all_comments)} comments")

        return {
            'posts': all_posts,
            'comments': all_comments,
            'total_posts': len(all_posts),
            'total_comments': len(all_comments)
        }


def main():
    """Test Reddit crawler"""
    logger.info("Testing Reddit Crawler...")

    try:
        crawler = RedditCrawler(rate_limit_delay=1.0)

        # Test 1: Crawl a single subreddit
        result = crawler.crawl_subreddit(
            subreddit_name='technology',
            sort='hot',
            limit=5,
            fetch_comments=True,
            max_comments_per_post=10
        )

        logger.info(f"\nSingle subreddit results:")
        logger.info(f"  Posts: {result['total_posts']}")
        logger.info(f"  Comments: {result['total_comments']}")

        # Test 2: Search for keyword
        search_result = crawler.search_reddit(
            query='artificial intelligence',
            subreddit_name='technology',
            limit=5
        )

        logger.info(f"\nSearch results:")
        logger.info(f"  Matching posts: {search_result['total_posts']}")

        # Show sample posts
        if search_result['posts']:
            logger.info("\nSample posts:")
            for post in search_result['posts'][:3]:
                logger.info(f"  - {post['title']} (r/{post['subreddit']}, score: {post['score']})")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("\nTo use Reddit crawler:")
        logger.info("1. Go to https://www.reddit.com/prefs/apps")
        logger.info("2. Create a 'script' type app")
        logger.info("3. Add credentials to .env file:")
        logger.info("   REDDIT_CLIENT_ID=your_client_id")
        logger.info("   REDDIT_CLIENT_SECRET=your_client_secret")


if __name__ == "__main__":
    main()
