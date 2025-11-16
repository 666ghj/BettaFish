# Western Media Setup Guide

This guide explains how to set up BettaFish to monitor Western media sources, especially USA political news from both left and right perspectives, plus social media platforms and tech news.

## Table of Contents

1. [Overview](#overview)
2. [Supported Platforms](#supported-platforms)
3. [Installation](#installation)
4. [API Setup](#api-setup)
5. [Database Setup](#database-setup)
6. [Configuration](#configuration)
7. [IP Protection & Rate Limiting](#ip-protection--rate-limiting)
8. [Usage Examples](#usage-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Western media monitoring system includes:

- **News Sources**: RSS feeds from left/right/center news outlets (CNN, Fox News, Reuters, etc.)
- **Social Media**: Reddit, Twitter/X, YouTube, HackerNews
- **Categories**: Politics (left/right/center), Technology, General News

**IMPORTANT**: Since you're running from home, the system includes aggressive rate limiting and IP protection to prevent bans.

---

## Supported Platforms

### News Sources (RSS-based)

#### Left-leaning
- CNN, CNN Politics
- MSNBC
- New York Times
- Washington Post
- NPR

#### Right-leaning
- Fox News, Fox News Politics
- Breitbart
- Daily Wire
- New York Post

#### Center/Balanced
- Reuters
- Associated Press (AP)
- BBC News
- Wall Street Journal

#### Tech News
- TechCrunch
- The Verge
- Wired
- HackerNews

#### Google News
- USA General News
- Politics
- Technology

### Social Media Platforms

1. **Reddit** - Requires free API credentials
2. **Twitter/X** - Uses scraper (no API needed, but risky)
3. **YouTube** - Requires free API key (quota-limited)
4. **HackerNews** - No API key needed (fully free)
5. **TikTok** - Note: US TikTok scraping is complex and not fully implemented yet

---

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

The following new packages will be installed:
- `praw` - Reddit API
- `feedparser` - RSS feeds
- `google-api-python-client` - YouTube API
- `tweepy` - Twitter API (optional)
- `ntscraper` - Twitter scraper (no API needed)
- `ratelimit` - Rate limiting
- `fake-useragent` - User agent rotation

### 2. Install Playwright (if not already installed)

```bash
playwright install
```

---

## API Setup

### Reddit API (Required for Reddit)

**Free tier**: 60 requests per minute

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select **"script"** type
4. Fill in:
   - **name**: BettaFish (or any name)
   - **description**: Public opinion analysis
   - **redirect uri**: http://localhost:8080 (won't be used)
5. Click "Create app"
6. Copy your **client_id** (under the app name) and **client_secret**

### YouTube API (Required for YouTube)

**Free tier**: 10,000 quota units per day
- Search: 100 units per request
- Video details: 1 unit per request

1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**:
   - Go to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API key"
   - Copy the API key
5. (Optional) Restrict the key to YouTube Data API v3 for security

### Twitter API (Optional)

**Note**: Twitter API is now paid ($100+/month). We provide a free scraper alternative, but it's risky for IP bans.

If you have Twitter API access:
1. Go to https://developer.twitter.com/
2. Apply for developer access
3. Create an app and get your Bearer Token

**Recommended**: Use the ntscraper (no API needed) with VERY conservative rate limiting.

### HackerNews (No API Key Needed)

HackerNews provides a free public API with no authentication. Ready to use!

---

## Database Setup

### 1. Create Western Media Tables

Run the SQL schema to create tables for Western platforms:

```bash
# For MySQL
mysql -u your_user -p your_database < MindSpider/schema/western_media_tables.sql

# For PostgreSQL
psql -U your_user -d your_database -f MindSpider/schema/western_media_tables.sql
```

This creates tables for:
- `reddit_post`, `reddit_comment`
- `twitter_tweet`
- `youtube_video`, `youtube_comment`
- `hackernews_post`, `hackernews_comment`
- `western_news_article`

### 2. Verify Tables

```sql
-- Check if tables were created
SHOW TABLES LIKE '%reddit%';
SHOW TABLES LIKE '%twitter%';
SHOW TABLES LIKE '%youtube%';
SHOW TABLES LIKE '%hackernews%';
SHOW TABLES LIKE '%western_news%';
```

---

## Configuration

### 1. Update .env File

Copy the example and fill in your credentials:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

Add the following to your `.env`:

```bash
# ================== Western Media Platform APIs ====================

# Reddit API (https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=BettaFish/1.0

# YouTube Data API v3 (https://console.cloud.google.com/)
YOUTUBE_API_KEY=your_youtube_api_key_here

# Twitter/X API (optional - scraper works without it)
TWITTER_BEARER_TOKEN=your_bearer_token_here  # Optional

# ================== Rate Limiting (IP Protection) ====================
# IMPORTANT: Adjust these to protect your home IP from bans!

# Global delay between requests (seconds) - MINIMUM 3 recommended
RATE_LIMIT_DELAY=3

# Maximum requests per hour (conservative limit)
MAX_REQUESTS_PER_HOUR=100

# Platform-specific rate limits (requests per hour)
REDDIT_RATE_LIMIT=60
TWITTER_RATE_LIMIT=20      # Very conservative - Twitter is risky!
YOUTUBE_RATE_LIMIT=100
HACKERNEWS_RATE_LIMIT=120
GOOGLE_NEWS_RATE_LIMIT=100
WESTERN_NEWS_RATE_LIMIT=200

# Minimum delays between requests (seconds)
REDDIT_MIN_DELAY=2.0
TWITTER_MIN_DELAY=10.0     # Very high - Twitter aggressively blocks scrapers
YOUTUBE_MIN_DELAY=1.0
HACKERNEWS_MIN_DELAY=1.0
GOOGLE_NEWS_MIN_DELAY=2.0
WESTERN_NEWS_MIN_DELAY=2.0
```

### 2. Verify Configuration

```bash
cd MindSpider/DeepSentimentCrawling/western_platforms
python config.py
```

This will show which APIs are configured and current rate limits.

---

## IP Protection & Rate Limiting

### Why IP Protection Matters

When crawling from home, you risk:
- **IP bans** from websites/platforms
- **Account bans** (for Reddit, Twitter, YouTube)
- **ISP throttling** or warnings

### Built-in Protections

The system includes multiple layers of protection:

#### 1. **Rate Limiting**
- Per-platform request limits (e.g., max 20 Twitter requests/hour)
- Minimum delays between requests (e.g., 10 seconds for Twitter)
- Automatic request counting and blocking when limits are reached

#### 2. **User Agent Rotation**
- Random user agents for each request
- Mimics different browsers to avoid detection

#### 3. **Conservative Defaults**
- Twitter: 20 requests/hour, 10-second delays (very conservative)
- Reddit: 60 requests/hour, 2-second delays
- YouTube: 100 requests/hour (quota-based)
- News RSS: 200 requests/hour, 2-second delays

### Best Practices

1. **Start Conservative**: Use the default rate limits first
2. **Monitor for Errors**: Watch for 429 (rate limit) or 403 (banned) errors
3. **Reduce Frequency**: Don't crawl 24/7 from home
4. **Use Official APIs**: Prefer Reddit/YouTube APIs over scraping
5. **Avoid Twitter Scraping**: Twitter is the most aggressive - consider skipping or using very sparingly

### Advanced: Proxy Setup (Optional)

If you need higher volume, consider using proxy services:

1. Sign up for a proxy provider (e.g., Bright Data, ScraperAPI)
2. Update `.env`:
   ```bash
   ENABLE_IP_PROXY=true
   IP_PROXY_PROVIDER_NAME=your_provider
   ```
3. Configure proxy settings in `MindSpider/DeepSentimentCrawling/MediaCrawler/config/base_config.py`

---

## Usage Examples

### 1. Collect Western News (RSS Feeds)

```python
import asyncio
from MindSpider.BroadTopicExtraction.western_news_collector import WesternNewsCollector

async def collect_news():
    async with WesternNewsCollector(rate_limit_delay=3.0) as collector:
        # Collect from all political perspectives
        result = await collector.collect_by_political_spectrum()

        print(f"Total articles: {sum(r['total_articles'] for r in result.values())}")

asyncio.run(collect_news())
```

### 2. Crawl Reddit Political Subreddits

```python
from MindSpider.DeepSentimentCrawling.western_platforms import RedditCrawler

crawler = RedditCrawler(rate_limit_delay=2.0)

# Crawl across political spectrum
result = crawler.crawl_politics(
    political_lean='all',  # 'left', 'right', 'center', or 'all'
    posts_per_sub=10
)

print(f"Posts: {result['total_posts']}, Comments: {result['total_comments']}")
```

### 3. Search Reddit for Specific Topics

```python
from MindSpider.DeepSentimentCrawling.western_platforms import RedditCrawler

crawler = RedditCrawler()

# Search all of Reddit
result = crawler.search_reddit(
    query='artificial intelligence',
    time_filter='week',
    limit=50
)

print(f"Found {result['total_posts']} posts")
```

### 4. Crawl HackerNews

```python
import asyncio
from MindSpider.DeepSentimentCrawling.western_platforms import HackerNewsCrawler

async def crawl_hn():
    async with HackerNewsCrawler(rate_limit_delay=1.0) as crawler:
        # Get top stories
        result = await crawler.crawl_stories(
            story_type='top',
            limit=30,
            fetch_comments=True,
            max_comments_per_story=50
        )

        print(f"Stories: {result['total_posts']}, Comments: {result['total_comments']}")

asyncio.run(crawl_hn())
```

### 5. Search YouTube Videos

```python
from MindSpider.DeepSentimentCrawling.western_platforms import YouTubeCrawler

crawler = YouTubeCrawler(rate_limit_delay=1.0)

result = crawler.search_videos(
    query='artificial intelligence news',
    max_results=10,
    order='date'  # 'relevance', 'date', 'viewCount', 'rating'
)

print(f"Found {result['total_videos']} videos")
print(f"API quota used: {crawler.quota_used}/10000")
```

### 6. Monitor Political YouTube Channels

```python
from MindSpider.DeepSentimentCrawling.western_platforms import YouTubeCrawler

crawler = YouTubeCrawler()

result = crawler.monitor_political_channels(videos_per_channel=5)

print(f"Videos: {result['total_videos']}, Comments: {result['total_comments']}")
print(f"Quota used: {result['quota_used']}/10000")
```

### 7. Twitter/X Search (Use Sparingly!)

```python
from MindSpider.DeepSentimentCrawling.western_platforms import TwitterCrawler

# IMPORTANT: Very high rate limit delay for Twitter!
crawler = TwitterCrawler(rate_limit_delay=10.0)

result = crawler.search_tweets(
    query='artificial intelligence',
    mode='term',
    limit=10  # Keep very low!
)

print(f"Found {result['total_tweets']} tweets")
```

### 8. Combined Political Monitoring

```python
import asyncio
from MindSpider.DeepSentimentCrawling.western_platforms import (
    RedditCrawler, YouTubeCrawler, HackerNewsCrawler
)

async def monitor_politics():
    # Reddit
    reddit = RedditCrawler(rate_limit_delay=2.0)
    reddit_result = reddit.crawl_politics(political_lean='all', posts_per_sub=5)

    # YouTube
    youtube = YouTubeCrawler(rate_limit_delay=1.0)
    youtube_result = youtube.monitor_political_channels(videos_per_channel=3)

    # HackerNews (for tech perspective on news)
    async with HackerNewsCrawler(rate_limit_delay=1.0) as hn:
        hn_result = await hn.crawl_stories(story_type='top', limit=20)

    print(f"Reddit: {reddit_result['total_posts']} posts, {reddit_result['total_comments']} comments")
    print(f"YouTube: {youtube_result['total_videos']} videos, {youtube_result['total_comments']} comments")
    print(f"HackerNews: {hn_result['total_posts']} posts, {hn_result['total_comments']} comments")

asyncio.run(monitor_politics())
```

### 9. Check Rate Limiter Status

```python
from MindSpider.DeepSentimentCrawling.western_platforms import get_rate_limiter

rate_limiter = get_rate_limiter()
rate_limiter.print_status()
```

---

## Troubleshooting

### Reddit Issues

**Error: "Reddit API credentials not found"**
- Ensure `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are set in `.env`
- Verify credentials at https://www.reddit.com/prefs/apps

**Error: 429 Too Many Requests**
- Reddit's rate limit is 60 requests per minute
- Increase `REDDIT_MIN_DELAY` in `.env`
- Reduce crawling frequency

### YouTube Issues

**Error: "YouTube API key not found"**
- Set `YOUTUBE_API_KEY` in `.env`
- Get key from https://console.cloud.google.com/

**Error: Quota exceeded**
- YouTube free tier: 10,000 units/day
- Each search costs 100 units
- Wait until next day or upgrade to paid tier
- Reduce `max_results` in searches

### Twitter Issues

**Error: Scraping failed**
- Twitter aggressively blocks scrapers
- Increase `TWITTER_MIN_DELAY` to 15+ seconds
- Reduce request frequency
- Consider using official API (paid) instead

**Error: IP banned**
- Wait 24-48 hours
- Use VPN or proxy for future requests
- Reduce crawling frequency significantly

### HackerNews Issues

**Error: Timeout**
- HackerNews API is usually very reliable
- Check your internet connection
- Increase timeout in crawler

### General IP Protection

**How to avoid IP bans:**
1. **Use Conservative Rate Limits**: Start with defaults, increase slowly
2. **Monitor Errors**: Stop immediately if you see 403/429 errors
3. **Crawl During Off-Peak**: Night/early morning in USA
4. **Limit Daily Requests**: Set a maximum per day
5. **Use Official APIs**: Prefer APIs over scraping
6. **Consider VPN/Proxy**: For higher volume needs

**Signs of being banned:**
- 403 Forbidden errors
- Connection timeouts
- Empty results when data should exist
- CAPTCHA challenges

**If you get banned:**
1. Stop all requests immediately
2. Wait 24-48 hours
3. Use VPN/proxy for future requests
4. Significantly reduce rate limits

---

## Daily Monitoring Schedule Example

Here's a safe daily monitoring schedule for home use:

```python
# Morning (7-9 AM): News Collection
- Western News RSS: 30 minutes, all sources
- Reddit: 15 minutes, politics + tech
- HackerNews: 10 minutes, top stories

# Afternoon (2-4 PM): Social Media Update
- YouTube: 20 minutes, political channels
- Reddit: 15 minutes, news subreddits
- HackerNews: 10 minutes, new stories

# Evening (8-10 PM): Final Update
- Western News RSS: 20 minutes, breaking news
- Reddit: 10 minutes, trending topics
- Twitter: 5 minutes ONLY (very risky, optional)

Total daily requests: ~500-800 (well within safe limits)
```

---

## Support

For issues or questions:
1. Check this documentation
2. Review error logs in `logs/` directory
3. Test individual crawlers (see examples above)
4. Open an issue on GitHub

---

## License

This Western media monitoring system is part of the BettaFish project.

---

**Remember**: When crawling from home, always prioritize IP safety over data volume. It's better to collect less data safely than to get banned and collect nothing!
