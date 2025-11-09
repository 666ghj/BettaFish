# BettaFish USA Adaptation - Quick Technical Reference

## Chinese Platforms (7 Total)
| Platform | Type | DB Tables | Key Features |
|----------|------|-----------|--------------|
| 微博 (Weibo) | Microblog | weibo_* | Trending, retweets, hashtags |
| 抖音 (Douyin) | Short video | douyin_aweme_* | Video trending, creators |
| 小红书 (XHS) | Shopping + lifestyle | xiaohongshu_* | Product reviews, lifestyle |
| B站 (Bilibili) | Video platform | bilibili_* | Danmaku (bullet comments) |
| 快手 (Kuaishou) | Live + short video | kuaishou_* | Grassroots content |
| 知乎 (Zhihu) | Q&A | zhihu_* | Expert discussions |
| 贴吧 (Tieba) | Forum | tieba_* | Community threads |

## USA Platforms (Need to Add)
1. **Twitter/X** - API v2 based
2. **Reddit** - API based
3. **Facebook** - Graph API based
4. **Instagram** - API based
5. **TikTok US** - Different from Douyin (separate crawler)
6. **YouTube** - Data API based
7. **LinkedIn** - API based

## Critical Files to Change

### 1. Crawlers (`/MindSpider/DeepSentimentCrawling/MediaCrawler/`)
```
main.py:
  Line 32-40: CrawlerFactory.CRAWLERS dict
  FROM: {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}
  TO:   {"twitter", "reddit", "facebook", "instagram", "tiktok_us", "youtube", "linkedin"}
  
  Line 20-26: Import statements
  FROM: from media_platform.weibo import WeiboCrawler, etc.
  TO:   Add imports for 7 new crawlers
```

### 2. Prompts - Translate COMPLETELY
```
/InsightEngine/prompts/prompts.py       (630 lines)
/MediaEngine/prompts/prompts.py         (450 lines) 
/QueryEngine/prompts/prompts.py         (450 lines)
/ReportEngine/prompts/prompts.py        (136 lines)

Priority sections:
- Line 40 (InsightEngine): Platform list hardcoded as Chinese
- Line 247-253 (InsightEngine): Platform-specific language examples
- ALL system prompts mentioning "舆情" (public opinion)
- ALL examples using Weibo/Chinese culture
```

### 3. Database Models (`/MindSpider/.../MediaCrawler/database/models.py`)
```
Add new table classes:
- TwitterTweet, TwitterReply, TwitterRetweet
- RedditPost, RedditComment, RedditSubreddit
- FacebookPost, FacebookComment, FacebookReaction
- InstagramPost, InstagramComment
- YouTubeVideo, YouTubeComment
- LinkedInPost, LinkedInComment
- TikTokUSVideo, TikTokUSComment

Keep common fields:
- platform, content_id, author_username, author_id
- content_text, engagement metrics, post_timestamp
- source_keyword
```

### 4. Search Tools (`/InsightEngine/tools/search.py`)
```
Line 18-23: Tool descriptions (translated to English, not Chinese)
Line 150-250: Platform table mappings
  CURRENT: bilibili_video, weibo_content, douyin_aweme, etc.
  NEEDED:  twitter_tweet, reddit_post, facebook_post, etc.

Methods to expand:
- search_hot_content() - Add platform weights
- search_topic_on_platform() - Update platform list validation
- _extract_engagement() - Handle Twitter retweets, Reddit upvotes, etc.
```

### 5. Configuration (`/config.py`)
```
Add API keys:
TWITTER_API_KEY
TWITTER_API_SECRET
REDDIT_CLIENT_ID
REDDIT_SECRET
FACEBOOK_ACCESS_TOKEN
INSTAGRAM_ACCESS_TOKEN
YOUTUBE_API_KEY
LINKEDIN_ACCESS_TOKEN

Switch LLM models from Chinese-optimized:
INSIGHT_ENGINE_MODEL_NAME: Remove "kimi" → Add "gpt-4o" or "claude-opus"
FORUM_HOST_MODEL_NAME: Remove "Qwen3" → Add GPT-4 Turbo
KEYWORD_OPTIMIZER_MODEL_NAME: Remove Qwen → Add Claude/GPT-4
```

### 6. Report Templates (`/ReportEngine/report_template/`)
```
All 6 templates in Chinese:
1. 企业品牌声誉分析报告模板.md → Brand Reputation Analysis Report
2. 市场竞争格局舆情分析报告.md → Market Competition Analysis Report
3. 日常或定期舆情监测报告.md → Daily Social Media Monitoring Report
4. 特定政策或行业动态舆情分析报告.md → Policy/Industry Dynamics Report
5. 社会公共热点事件分析报告.md → Public Event Analysis Report
6. 突发事件与危机公关舆情报告.md → Crisis Management Report

Keep structure, update examples and context
```

## Language Barriers Summary

| Severity | Category | Files Affected | Impact |
|----------|----------|-----------------|--------|
| CRITICAL | Prompts (system instructions) | 4 main files | LLM won't understand USA context |
| CRITICAL | Hardcoded platform names | 5+ files | Code logic depends on Chinese platform names |
| HIGH | Comments & documentation | ~50 Python files | Developer understanding, maintenance |
| HIGH | LLM model recommendations | config.py | Models optimized for Chinese, not English |
| MEDIUM | Error/log messages | 15+ files | User-facing messages in Chinese |
| MEDIUM | Database schema | models.py | Platform-specific fields for Chinese platforms |
| LOW | Variable naming | Throughout | Code clarity (wb_client, dy, etc.) |

## Platform Adaptation Strategy

### Recommended Approach:
1. **Use official APIs** (Twitter v2, Reddit, YouTube Data, LinkedIn, Facebook Graph)
   - Avoids Playwright complexity for USA platforms
   - Better rate limiting
   - Official support for authentication

2. **Keep existing Chinese crawlers** (browser-based works better for them)
   - Bilibili, Weibo, Xiaohongshu still use Playwright
   - Chinese crawlers don't have good official APIs

3. **Abstract platform differences** in search tools
   - Create table mapping system
   - Handle different engagement metrics per platform
   - Support different date/timestamp formats

## Sentiment Analysis

**Current:** WeiboSentiment (Chinese-specific models)
**Models available:**
- WeiboSentiment_MachineLearning (SVM, XGBoost, LSTM, BERT)
- WeiboSentiment_Finetuned (GPT2-LoRA, BertChinese-LoRA)
- WeiboMultilingualSentiment (22 languages, can use for English)

**Recommendation:**
1. Use `tabularisai/multilingual-sentiment-analysis` (already in codebase)
2. Fine-tune on Reddit/Twitter sentiment corpus
3. Add sarcasm detection (critical for Reddit/Twitter)
4. Platform-specific emotion dictionaries:
   - Reddit: "Actually...", "username checks out" patterns
   - Twitter: Emoji usage, hashtag sentiment
   - YouTube: Long-form discussion patterns

## Database Structure

```sql
Common schema across all platforms:
- platform_*_post/tweet/video
  - id (primary key)
  - platform_id (VARCHAR, unique per platform)
  - content_id (internal ID)
  - author_id (user ID)
  - author_username (user handle)
  - content_text (TEXT, UTF-8mb4)
  - created_at (timestamp)
  - engagement_likes (INT)
  - engagement_comments (INT)
  - engagement_shares (INT)
  - engagement_views (INT, if applicable)
  - source_keyword (VARCHAR, for tracking)
  - media_urls (JSON array if multiple images/videos)
  - post_url (VARCHAR)
  - created_at (timestamp)
  - updated_at (timestamp)

- platform_*_comment
  - Similar structure, with parent_post_id reference
```

## Files Saved for Reference

Complete analysis saved to: **ADAPTATION_GUIDE_USA_PLATFORMS.md**
- Full detailed analysis (7 sections)
- Effort estimates
- Code examples for each change
- Configuration structure documentation

This quick reference: **QUICK_REFERENCE_USA_ADAPTATION.md**
- Compressed format for quick lookup
- File locations and line numbers
- Tables summarizing key information
