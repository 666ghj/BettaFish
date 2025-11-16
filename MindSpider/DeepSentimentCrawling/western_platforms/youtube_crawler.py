#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Crawler Module
Fetches videos and comments using YouTube Data API v3
Requires YouTube API key (free tier available with quotas)

API Quotas (Free Tier):
- 10,000 units per day
- Search: 100 units per request
- Video details: 1 unit per request
- Comments: 1 unit per request
"""

import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import time
import json
from datetime import datetime as dt
import isodate

# Load environment variables
load_dotenv()


class YouTubeCrawler:
    """
    YouTube crawler using official YouTube Data API v3
    Requires API key (free tier available at https://console.cloud.google.com/)

    To get an API key:
    1. Go to https://console.cloud.google.com/
    2. Create a new project
    3. Enable YouTube Data API v3
    4. Create credentials (API key)
    5. Add to .env: YOUTUBE_API_KEY=your_key
    """

    # Popular YouTube channels for different categories
    CHANNELS = {
        'news_left': [
            'CNN',  # CNN
            'msnbc',  # MSNBC
            'UCupvZG-5ko_eiXAupbDfxWw'  # CNN (by ID)
        ],
        'news_right': [
            'FoxNewsChannel',  # Fox News
            'UCXIJgqnII2ZOINSWNOGFThA'  # Fox News (by ID)
        ],
        'news_center': [
            'Reuters',  # Reuters
            'AssociatedPress'  # AP
        ],
        'tech': [
            'TechCrunch',  # TechCrunch
            'TheVerge',  # The Verge
            'MKBHD'  # Marques Brownlee
        ]
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_delay: float = 1.0
    ):
        """
        Initialize YouTube crawler

        Args:
            api_key: YouTube API key (from env if not provided)
            rate_limit_delay: Delay between API requests
        """
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')

        if not self.api_key:
            raise ValueError(
                "YouTube API key not found. Please set YOUTUBE_API_KEY "
                "in .env file or pass it as an argument."
            )

        self.rate_limit_delay = rate_limit_delay
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.quota_used = 0  # Track quota usage

        logger.info("YouTube crawler initialized")

    def _parse_video(self, video_data: Dict) -> Optional[Dict]:
        """
        Parse YouTube video data to database format

        Args:
            video_data: Raw video data from API

        Returns:
            Formatted video dictionary
        """
        try:
            snippet = video_data.get('snippet', {})
            statistics = video_data.get('contentDetails', {})
            stats = video_data.get('statistics', {})

            # Parse ISO 8601 duration
            duration = statistics.get('duration', 'PT0S')

            # Parse published date
            published_at = snippet.get('publishedAt', '')
            published_ts = int(dt.fromisoformat(published_at.replace('Z', '+00:00')).timestamp()) if published_at else 0

            # Extract tags
            tags = snippet.get('tags', [])

            return {
                'video_id': video_data['id'],
                'title': snippet.get('title', '')[:500],
                'channel_id': snippet.get('channelId', ''),
                'channel_title': snippet.get('channelTitle', '')[:200],
                'description': snippet.get('description', '')[:1000],
                'published_at': published_ts,
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0)),
                'duration': duration,
                'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'tags': json.dumps(tags),
                'category_id': snippet.get('categoryId', ''),
                'language': snippet.get('defaultLanguage', 'en'),
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse video: {e}")
            return None

    def _parse_comment(self, comment_data: Dict, video_id: str) -> Optional[Dict]:
        """Parse YouTube comment to database format"""
        try:
            snippet = comment_data.get('snippet', {})
            top_level = snippet.get('topLevelComment', {}).get('snippet', {})

            published_at = top_level.get('publishedAt', '')
            published_ts = int(dt.fromisoformat(published_at.replace('Z', '+00:00')).timestamp()) if published_at else 0

            return {
                'comment_id': comment_data['id'],
                'video_id': video_id,
                'parent_id': snippet.get('parentId', ''),
                'author': top_level.get('authorDisplayName', '')[:100],
                'content': top_level.get('textDisplay', '')[:2000],
                'like_count': int(top_level.get('likeCount', 0)),
                'published_at': published_ts,
                'is_reply': 1 if snippet.get('parentId') else 0,
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse comment: {e}")
            return None

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        order: str = 'relevance',
        published_after: Optional[str] = None
    ) -> Dict:
        """
        Search for videos by keyword

        Args:
            query: Search query
            max_results: Maximum number of results (max 50 per request)
            order: Sort order ('relevance', 'date', 'rating', 'viewCount')
            published_after: RFC 3339 formatted date-time (e.g., '2024-01-01T00:00:00Z')

        Returns:
            Dictionary with videos
        """
        logger.info(f"Searching YouTube for '{query}' (max_results={max_results})...")

        try:
            # Build search request
            request = self.youtube.search().list(
                q=query,
                part='id,snippet',
                type='video',
                maxResults=min(max_results, 50),
                order=order,
                publishedAfter=published_after,
                regionCode='US'
            )

            response = request.execute()
            self.quota_used += 100  # Search costs 100 units

            # Extract video IDs
            video_ids = [item['id']['videoId'] for item in response.get('items', [])]

            if not video_ids:
                logger.info("No videos found")
                return {'videos': [], 'total_videos': 0}

            # Get detailed video info (includes statistics)
            videos = self.get_videos_by_ids(video_ids)

            time.sleep(self.rate_limit_delay)

            logger.info(f"✓ Found {len(videos)} videos for '{query}'")

            return {
                'videos': videos,
                'total_videos': len(videos),
                'query': query
            }

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return {'videos': [], 'total_videos': 0, 'error': str(e)}

    def get_videos_by_ids(self, video_ids: List[str]) -> List[Dict]:
        """
        Get detailed information for multiple videos

        Args:
            video_ids: List of video IDs

        Returns:
            List of parsed video dictionaries
        """
        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(video_ids)
            )

            response = request.execute()
            self.quota_used += 1  # Costs 1 unit

            videos = []
            for item in response.get('items', []):
                video = self._parse_video(item)
                if video:
                    videos.append(video)

            return videos

        except HttpError as e:
            logger.error(f"Failed to get video details: {e}")
            return []

    def get_video_comments(
        self,
        video_id: str,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Get comments for a specific video

        Args:
            video_id: YouTube video ID
            max_results: Maximum number of comments to retrieve

        Returns:
            List of parsed comments
        """
        logger.info(f"Fetching comments for video {video_id}...")

        try:
            request = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(max_results, 100),
                order='relevance'
            )

            response = request.execute()
            self.quota_used += 1  # Costs 1 unit

            comments = []
            for item in response.get('items', []):
                comment = self._parse_comment(item, video_id)
                if comment:
                    comments.append(comment)

            time.sleep(self.rate_limit_delay)

            logger.info(f"✓ Fetched {len(comments)} comments")

            return comments

        except HttpError as e:
            # Comments might be disabled
            logger.warning(f"Failed to get comments for {video_id}: {e}")
            return []

    def crawl_channel(
        self,
        channel_id: str,
        max_videos: int = 10,
        fetch_comments: bool = True,
        max_comments_per_video: int = 20
    ) -> Dict:
        """
        Crawl videos from a specific channel

        Args:
            channel_id: YouTube channel ID or username
            max_videos: Maximum number of videos to fetch
            fetch_comments: Whether to fetch comments
            max_comments_per_video: Max comments per video

        Returns:
            Dictionary with videos and comments
        """
        logger.info(f"Crawling channel {channel_id}...")

        try:
            # Search for videos from this channel
            request = self.youtube.search().list(
                part='id,snippet',
                channelId=channel_id,
                maxResults=min(max_videos, 50),
                order='date',
                type='video'
            )

            response = request.execute()
            self.quota_used += 100

            video_ids = [item['id']['videoId'] for item in response.get('items', [])]

            if not video_ids:
                logger.info("No videos found for channel")
                return {'videos': [], 'comments': [], 'total_videos': 0, 'total_comments': 0}

            # Get video details
            videos = self.get_videos_by_ids(video_ids)

            # Get comments if requested
            comments = []
            if fetch_comments:
                for video in videos:
                    video_comments = self.get_video_comments(
                        video['video_id'],
                        max_results=max_comments_per_video
                    )
                    comments.extend(video_comments)

            logger.info(f"✓ Channel crawl complete: {len(videos)} videos, {len(comments)} comments")

            return {
                'videos': videos,
                'comments': comments,
                'total_videos': len(videos),
                'total_comments': len(comments)
            }

        except HttpError as e:
            logger.error(f"Failed to crawl channel: {e}")
            return {'videos': [], 'comments': [], 'total_videos': 0, 'total_comments': 0, 'error': str(e)}

    def monitor_political_channels(
        self,
        videos_per_channel: int = 5
    ) -> Dict:
        """
        Monitor videos from political news channels

        Args:
            videos_per_channel: Number of latest videos per channel

        Returns:
            Combined videos from all political channels
        """
        logger.info("Monitoring political YouTube channels...")

        all_videos = []
        all_comments = []

        for category, channels in [('left', self.CHANNELS['news_left']),
                                    ('right', self.CHANNELS['news_right']),
                                    ('center', self.CHANNELS['news_center'])]:

            logger.info(f"Fetching {category}-leaning channels...")

            for channel in channels[:2]:  # Limit to avoid quota exhaustion
                try:
                    result = self.crawl_channel(
                        channel_id=channel,
                        max_videos=videos_per_channel,
                        fetch_comments=True,
                        max_comments_per_video=10
                    )

                    all_videos.extend(result['videos'])
                    all_comments.extend(result['comments'])

                    time.sleep(self.rate_limit_delay * 2)

                except Exception as e:
                    logger.error(f"Failed to crawl channel {channel}: {e}")
                    continue

        logger.info(f"Political monitoring complete: {len(all_videos)} videos, {len(all_comments)} comments")
        logger.info(f"Total API quota used: {self.quota_used} units")

        return {
            'videos': all_videos,
            'comments': all_comments,
            'total_videos': len(all_videos),
            'total_comments': len(all_comments),
            'quota_used': self.quota_used
        }


def main():
    """Test YouTube crawler"""
    logger.info("Testing YouTube Crawler...")

    try:
        crawler = YouTubeCrawler(rate_limit_delay=1.0)

        # Test 1: Search for videos
        logger.info("\nTest 1: Searching for videos...")
        result = crawler.search_videos(
            query='artificial intelligence news',
            max_results=5,
            order='date'
        )

        logger.info(f"Search results: {result['total_videos']} videos")

        # Show sample videos
        if result['videos']:
            logger.info("\nSample videos:")
            for video in result['videos'][:3]:
                logger.info(f"  - {video['title']} ({video['channel_title']}, views: {video['view_count']})")

        # Test 2: Get comments for first video
        if result['videos']:
            logger.info("\nTest 2: Fetching comments...")
            first_video_id = result['videos'][0]['video_id']
            comments = crawler.get_video_comments(first_video_id, max_results=5)
            logger.info(f"Comments fetched: {len(comments)}")

        logger.info(f"\n✓ Tests complete! API quota used: {crawler.quota_used}/10000 units")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("\nTo use YouTube crawler:")
        logger.info("1. Go to https://console.cloud.google.com/")
        logger.info("2. Create a new project")
        logger.info("3. Enable YouTube Data API v3")
        logger.info("4. Create an API key")
        logger.info("5. Add to .env: YOUTUBE_API_KEY=your_key")


if __name__ == "__main__":
    main()
