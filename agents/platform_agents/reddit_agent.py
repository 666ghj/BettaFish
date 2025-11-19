#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reddit Platform Agent
Specialized agent for monitoring Reddit subreddits

Agent Persona:
- Name: Reddit Agent
- Role: Reddit platform monitoring specialist
- Expertise: Reddit API, subreddit dynamics, political discussions
- Personality: Thorough, community-aware, balanced, cautious
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.shared.base_agent import BaseAgent
from MindSpider.DeepSentimentCrawling.western_platforms import RedditCrawler


class RedditAgent(BaseAgent):
    """
    Reddit monitoring agent

    Responsibilities:
    - Monitor political subreddits (left/right/center)
    - Monitor technology subreddits
    - Collect posts and comments
    - Track subreddit trends
    - Respect Reddit API rate limits

    Configuration:
    - subreddits: Dict of subreddit categories
    - posts_per_subreddit: Number of posts to collect
    - fetch_comments: Whether to collect comments
    - max_comments_per_post: Maximum comments per post
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__("reddit_agent", config)

        # Agent personality
        self.personality = {
            'thorough': 'Collects comprehensive data from subreddits',
            'community_aware': 'Understands Reddit culture and norms',
            'balanced': 'Monitors across political spectrum equally',
            'cautious': 'Respects API limits and community guidelines'
        }

        # Reddit crawler
        self.crawler = None

        # Default configuration
        self.subreddits = config.get('subreddits', {
            'political_left': ['politics', 'democrats', 'liberal'],
            'political_right': ['conservative', 'republican'],
            'political_center': ['neutralpolitics', 'moderatepolitics'],
            'tech': ['technology', 'programming', 'artificial']
        })

        self.posts_per_subreddit = config.get('posts_per_subreddit', 25)
        self.fetch_comments = config.get('fetch_comments', True)
        self.max_comments_per_post = config.get('max_comments_per_post', 50)

    async def _initialize(self):
        """Initialize Reddit crawler"""
        self.log_info("Initializing Reddit crawler...")

        try:
            self.crawler = RedditCrawler(
                rate_limit_delay=self.get_config('rate_limit_delay', 2.0)
            )
            self.log_info("Reddit crawler initialized successfully")

        except ValueError as e:
            self.log_error(f"Failed to initialize Reddit crawler: {e}")
            self.log_error(
                "Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env"
            )
            raise

    async def _shutdown(self):
        """Cleanup Reddit crawler"""
        self.log_info("Shutting down Reddit crawler...")
        # Crawler cleanup if needed
        self.crawler = None

    async def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Reddit monitoring task

        Task parameters:
        - task_type: 'monitor_all' | 'monitor_category' | 'search'
        - category: 'political_left' | 'political_right' | 'political_center' | 'tech'
        - subreddits: List of specific subreddits (optional)
        - query: Search query (for search tasks)
        """
        task_type = task.get('task_type', 'monitor_all')

        if task_type == 'monitor_all':
            return await self._monitor_all_subreddits()

        elif task_type == 'monitor_category':
            category = task.get('category')
            return await self._monitor_category(category)

        elif task_type == 'monitor_specific':
            subreddits = task.get('subreddits', [])
            return await self._monitor_specific_subreddits(subreddits)

        elif task_type == 'search':
            query = task.get('query')
            subreddit = task.get('subreddit')
            return await self._search_reddit(query, subreddit)

        else:
            raise ValueError(f"Unknown task type: {task_type}")

    async def _monitor_all_subreddits(self) -> Dict[str, Any]:
        """Monitor all configured subreddits"""
        self.log_info("Monitoring all subreddits...")

        all_posts = []
        all_comments = []
        stats = {
            'subreddits_monitored': 0,
            'posts_collected': 0,
            'comments_collected': 0,
            'categories': {}
        }

        # Monitor each category
        for category, subreddit_list in self.subreddits.items():
            self.log_info(f"Monitoring category: {category}")

            for subreddit in subreddit_list:
                try:
                    # Check rate limit before crawling
                    await self._check_rate_limit()

                    # Crawl subreddit
                    result = self.crawler.crawl_subreddit(
                        subreddit_name=subreddit,
                        sort='hot',
                        limit=self.posts_per_subreddit,
                        fetch_comments=self.fetch_comments,
                        max_comments_per_post=self.max_comments_per_post
                    )

                    # Collect results
                    all_posts.extend(result['posts'])
                    all_comments.extend(result['comments'])

                    # Update stats
                    stats['subreddits_monitored'] += 1
                    stats['posts_collected'] += result['total_posts']
                    stats['comments_collected'] += result['total_comments']

                    if category not in stats['categories']:
                        stats['categories'][category] = {
                            'subreddits': 0,
                            'posts': 0,
                            'comments': 0
                        }

                    stats['categories'][category]['subreddits'] += 1
                    stats['categories'][category]['posts'] += result['total_posts']
                    stats['categories'][category]['comments'] += result['total_comments']

                    self.log_info(
                        f"r/{subreddit}: {result['total_posts']} posts, "
                        f"{result['total_comments']} comments"
                    )

                except Exception as e:
                    self.log_error(f"Failed to crawl r/{subreddit}: {e}")
                    continue

        # Send data to pipeline
        if all_posts:
            await self._send_data_to_pipeline(all_posts, all_comments)

        # Report to project manager
        await self._report_completion(stats)

        return {
            'stats': stats,
            'posts': len(all_posts),
            'comments': len(all_comments)
        }

    async def _monitor_category(self, category: str) -> Dict[str, Any]:
        """Monitor a specific category of subreddits"""
        if category not in self.subreddits:
            raise ValueError(f"Unknown category: {category}")

        self.log_info(f"Monitoring category: {category}")

        subreddits = self.subreddits[category]
        all_posts = []
        all_comments = []

        for subreddit in subreddits:
            try:
                await self._check_rate_limit()

                result = self.crawler.crawl_subreddit(
                    subreddit_name=subreddit,
                    sort='hot',
                    limit=self.posts_per_subreddit,
                    fetch_comments=self.fetch_comments,
                    max_comments_per_post=self.max_comments_per_post
                )

                all_posts.extend(result['posts'])
                all_comments.extend(result['comments'])

            except Exception as e:
                self.log_error(f"Failed to crawl r/{subreddit}: {e}")
                continue

        if all_posts:
            await self._send_data_to_pipeline(all_posts, all_comments)

        return {
            'category': category,
            'posts': len(all_posts),
            'comments': len(all_comments)
        }

    async def _monitor_specific_subreddits(
        self,
        subreddits: List[str]
    ) -> Dict[str, Any]:
        """Monitor specific subreddits"""
        self.log_info(f"Monitoring {len(subreddits)} specific subreddits")

        all_posts = []
        all_comments = []

        for subreddit in subreddits:
            try:
                await self._check_rate_limit()

                result = self.crawler.crawl_subreddit(
                    subreddit_name=subreddit,
                    sort='hot',
                    limit=self.posts_per_subreddit,
                    fetch_comments=self.fetch_comments,
                    max_comments_per_post=self.max_comments_per_post
                )

                all_posts.extend(result['posts'])
                all_comments.extend(result['comments'])

            except Exception as e:
                self.log_error(f"Failed to crawl r/{subreddit}: {e}")
                continue

        if all_posts:
            await self._send_data_to_pipeline(all_posts, all_comments)

        return {
            'subreddits': subreddits,
            'posts': len(all_posts),
            'comments': len(all_comments)
        }

    async def _search_reddit(
        self,
        query: str,
        subreddit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search Reddit for posts matching query"""
        self.log_info(f"Searching Reddit for: {query}")

        await self._check_rate_limit()

        result = self.crawler.search_reddit(
            query=query,
            subreddit_name=subreddit,
            limit=self.posts_per_subreddit
        )

        if result['posts']:
            await self._send_data_to_pipeline(result['posts'], [])

        return {
            'query': query,
            'subreddit': subreddit,
            'posts': result['total_posts']
        }

    async def _check_rate_limit(self):
        """Check with rate limiter before making request"""
        # Send rate limit check message
        await self.send_message(
            to='rate_limiter_agent',
            message_type='rate_limit_check',
            payload={
                'platform': 'reddit',
                'requested_operations': 1
            },
            priority=4
        )

        # TODO: Wait for approval from rate limiter
        # For now, just add a delay
        await asyncio.sleep(0.5)

    async def _send_data_to_pipeline(
        self,
        posts: List[Dict],
        comments: List[Dict]
    ):
        """Send collected data to data pipeline"""
        self.log_info(f"Sending data: {len(posts)} posts, {len(comments)} comments")

        await self.send_message(
            to='data_pipeline_agent',
            message_type='data_delivery',
            payload={
                'platform': 'reddit',
                'data_type': 'reddit_posts_comments',
                'posts': posts,
                'comments': comments,
                'collection_time': datetime.now().isoformat()
            },
            priority=3
        )

    async def _report_completion(self, stats: Dict[str, Any]):
        """Report task completion to project manager"""
        await self.send_message(
            to='project_manager_agent',
            message_type='task_status',
            payload={
                'status': 'completed',
                'summary': stats,
                'timestamp': datetime.now().isoformat()
            },
            priority=3
        )

    async def _custom_health_check(self) -> Dict[str, Any]:
        """Reddit-specific health checks"""
        return {
            'crawler_initialized': self.crawler is not None,
            'subreddits_configured': len(self.subreddits),
            'total_subreddits': sum(
                len(subs) for subs in self.subreddits.values()
            )
        }


async def main():
    """Test Reddit agent"""
    from loguru import logger

    logger.info("Testing Reddit Agent...")

    # Configuration
    config = {
        'rate_limit_delay': 2.0,
        'posts_per_subreddit': 5,
        'fetch_comments': True,
        'max_comments_per_post': 10,
        'subreddits': {
            'tech': ['technology', 'programming']
        }
    }

    # Create agent
    agent = RedditAgent(config)

    try:
        # Initialize
        await agent.initialize()

        # Check health
        health = await agent.health_check()
        logger.info(f"Health: {health}")

        # Execute task
        task = {
            'task_id': 'TEST-001',
            'task_type': 'monitor_category',
            'category': 'tech'
        }

        result = await agent.execute_task(task)
        logger.info(f"Result: {result}")

        # Shutdown
        await agent.shutdown()

    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
