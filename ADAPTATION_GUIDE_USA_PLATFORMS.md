# BettaFish - Chinese Social Media Analysis System to USA Adaptation Guide

## Executive Summary

BettaFish is a comprehensive Chinese public opinion analysis system designed specifically for Chinese social media platforms. It includes data crawling, sentiment analysis, multi-engine analysis (Insight, Media, Query), forum discussion hosting, and report generation. Adapting it for USA sources requires significant architectural changes across all components.

---

## 1. CHINESE PLATFORMS CURRENTLY SUPPORTED

### Active Crawlers (7 platforms):

1. **微博 (Weibo)** - "Chinese Twitter"
   - Path: `/media_platform/weibo/`
   - Focus: Posts, comments, hashtags, retweets, likes
   - Key features: Trending topics, celebrity discussions

2. **抖音 (Douyin)** - "Chinese TikTok"
   - Path: `/media_platform/douyin/`
   - Focus: Short videos, comments, shares, likes
   - Key features: Video trending, creator engagement

3. **小红书 (Xiaohongshu/XHS)** - "Little Red Book" - Social shopping + lifestyle
   - Path: `/media_platform/xhs/`
   - Focus: Product reviews, lifestyle posts, shopping discussions
   - Key features: User-generated product reviews, lifestyle trends

4. **B站 (Bilibili)** - Video platform (anime/gaming/vlogging)
   - Path: `/media_platform/bilibili/`
   - Focus: Videos, danmaku (bullet comments), replies
   - Key features: Unique danmaku culture, creator comments

5. **快手 (Kuaishou)** - Live streaming + short videos
   - Path: `/media_platform/kuaishou/`
   - Focus: Short videos, live streams, comments
   - Key features: Live engagement, grassroots content

6. **知乎 (Zhihu)** - "Chinese Quora"
   - Path: `/media_platform/zhihu/`
   - Focus: Q&A format, expert answers, discussions
   - Key features: In-depth discussions, expert opinions

7. **百度贴吧 (Baidu Tieba)** - "Baidu Post Bar"
   - Path: `/media_platform/tieba/`
   - Focus: Forum discussions, threads, replies
   - Key features: Community forums, niche discussions

**Database Models** (all in `/database/models.py`):
- BilibiliVideo, BilibiliVideoComment, BilibiliUpInfo
- DouyinAweme, DouyinAwemeComment
- WeiboContent, WeiboComment
- KuaishouContent, KuaishouComment
- XiaoHongShuNote, XiaoHongShuComment
- ZhihuQuestion, ZhihuAnswer, ZhihuComment
- TiebaThread, TiebaPost

---

## 2. HARDCODED CHINESE-SPECIFIC ELEMENTS

### In Configuration Files:

**File: `/config.py` & `/.env.example`**
```
DB_CHARSET: utf8mb4  # ✓ Already supports emoji, suitable for all platforms
Recommended LLM models:
- Insight: Kimi (中国制造) - "has best understanding of Chinese internet culture"
- Media: Gemini (but through Chinese-friendly API)
- Query: DeepSeek (中文优化)
- Forum Host: Qwen3 (完全中文化)
```

### In Prompts (Massive Chinese References):

**File: `/InsightEngine/prompts/prompts.py`** (Lines 170-267)
```python
Platform-specific language guidance:
- 微博：热搜词汇、话题标签 ("武大又上热搜", "心疼武大学子")
- 知乎：问答式表达 ("如何看待武汉大学", "武大是什么体验")
- B站：弹幕文化 ("武大yyds", "武大人路过", "我武最强")
- 贴吧：直接称呼 ("武大吧", "武大的兄弟们")
- 抖音/快手：短视频描述 ("武大日常", "武大vlog")
- 小红书：分享式 ("武大真的很美", "武大攻略")

Emotion word library (中文化):
- Positive: "太棒了"、"牛逼"、"绝了"、"爱了"、"yyds"、"666"
- Negative: "无语"、"离谱"、"绝了"、"服了"、"麻了"、"破防"
- Neutral: "围观"、"吃瓜"、"路过"、"有一说一"、"实名"
```

**File: `/MediaEngine/prompts/prompts.py`**
```python
Platform names hardcoded:
Line 40: "可选值：bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"
Language-specific search emphasis on:
- "网民真实表达" (netizen authentic expression)
- "口语化词汇" (colloquial vocabulary)
- "网络流行语" (internet slang)
- "褒贬词、情绪词" (sentiment-loaded vocabulary)
```

**File: `/QueryEngine/prompts/prompts.py`**
```python
Platform-specific search tools:
- search_topic_on_platform requires: "platform参数，可选值：bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"
- Uses Chinese date format expectations
```

**File: `/InsightEngine/tools/search.py`** (Lines 1-50)
```python
Database schema for 7 Chinese platforms only
Table names hardcoded:
- bilibili_video, bilibili_video_comment
- douyin_aweme, douyin_aweme_comment
- weibo_content, weibo_comment
- kuaishou_content, kuaishou_comment
- xiaohongshu_note, xiaohongshu_comment
- zhihu_question, zhihu_answer, zhihu_comment
- tieba_thread, tieba_post

Comment extraction logic tied to Chinese platform conventions:
- 弹幕 (danmaku) counting for Bilibili
- 转发 (retweets) counting for Weibo
- 收藏 (favorites) for Xiaohongshu
```

### In Report Templates:

**File: `/ReportEngine/report_template/`** (6 templates, ALL in Chinese):
```
1. 企业品牌声誉分析报告模板.md - Brand reputation (企业品牌)
2. 市场竞争格局舆情分析报告模板.md - Market competition (竞争格局)
3. 日常或定期舆情监测报告模板.md - Daily monitoring (日常监测)
4. 特定政策或行业动态舆情分析报告.md - Policy analysis (政策分析)
5. 社会公共热点事件分析报告模板.md - Public events (热点事件)
6. 突发事件与危机公关舆情报告模板.md - Crisis management (危机公关)
```

**Template Structure Example (社会公共热点事件分析报告):**
```
- 1.0 报告摘要 (Executive Summary)
- 2.0 事件全景与演变脉络 (Event narrative & timeline)
- 3.0 传播路径与引爆点分析 (Propagation & virality)
- 4.0 舆论场多方观点与情绪光谱 (Sentiment spectrum)
- 5.0 深层动因与价值观探讨 (Root causes & values)
- 6.0 关联性评估与行动建议 (Relevance & recommendations)
```

### In Sentiment Analysis:

**File: `/SentimentAnalysisModel/WeiboMultilingualSentiment/predict.py`**
```python
Model: tabularisai/multilingual-sentiment-analysis
Supports: 22 languages (including Chinese)
Sentiment Categories: 5-level classification
- 非常负面 (Very Negative)
- 负面 (Negative)
- 中性 (Neutral)
- 正面 (Positive)
- 非常正面 (Very Positive)

Chinese-Specific Models also available:
- WeiboSentiment_MachineLearning/ (SVM, XGBoost, LSTM, BERT)
- WeiboSentiment_Finetuned/ (GPT2-Lora, BertChinese-Lora)
- WeiboSentiment_SmallQwen/ (Qwen3 fine-tuned models)
- BertTopicDetection_Finetuned/ (Topic detection)
```

### In Database Schema:

**File: `/MindSpider/DeepSentimentCrawling/MediaCrawler/database/models.py`**
```python
All 7 Chinese platforms with platform-specific fields:
- Bilibili: video_danmaku, video_coin_count (unique to Bilibili)
- Douyin: sec_uid, short_user_id (TikTok-like structure)
- Weibo: Compatible with Weibo API structure
- Kuaishou: GraphQL-based queries (lines show graphql.py)
- XiaoHongShu: Product review focus
- Zhihu: Answer voting system
- Tieba: Thread-based forum structure
```

---

## 3. WHAT NEEDS TO CHANGE FOR USA SOCIAL MEDIA

### New Platforms to Add:

1. **Twitter/X** - Tweets, retweets, likes, replies
2. **Reddit** - Subreddits, posts, comments, upvotes
3. **Facebook** - Posts, comments, shares, reactions
4. **Instagram** - Posts, captions, comments, likes
5. **TikTok (US)** - Short videos (separate from Chinese Douyin)
6. **YouTube** - Videos, comments, likes, trending
7. **LinkedIn** - Professional posts, comments, reactions
8. **Bluesky/Threads** - Emerging platforms
9. **Nextdoor** - Community posts
10. **Discord** - Community discussions (optional)

### Major Architectural Changes Required:

#### A. CRAWLER MODULE (`/MediaCrawler/media_platform/`)
```
Changes needed:
1. Create new crawler classes:
   - twitter/client.py, core.py, field.py, login.py
   - reddit/client.py, core.py (API-based)
   - facebook/client.py, core.py
   - instagram/client.py, core.py
   - youtube/client.py, core.py
   - linkedin/client.py, core.py

2. Update CrawlerFactory in main.py:
   CRAWLERS = {
       "twitter": TwitterCrawler,
       "reddit": RedditCrawler,
       "facebook": FacebookCrawler,
       "instagram": InstagramCrawler,
       "tiktok_us": TikTokUSCrawler,
       "youtube": YouTubeCrawler,
       "linkedin": LinkedInCrawler,
   }

3. API-Based approach (more suitable for USA):
   - Use official APIs where available (Reddit, YouTube, Twitter API v2)
   - Reduces need for browser automation (Playwright)
   - Better rate limiting and authentication
```

#### B. DATABASE MODELS
```python
New table schemas for each platform:
- twitter_tweet, twitter_retweet, twitter_reply, twitter_like
- reddit_post, reddit_comment, reddit_subreddit
- facebook_post, facebook_comment, facebook_reaction
- instagram_post, instagram_comment, instagram_like
- youtube_video, youtube_comment, youtube_like
- linkedin_post, linkedin_comment, linkedin_reaction
- tiktok_us_video, tiktok_us_comment

Common fields across all:
- platform (VARCHAR)
- content_id (unique identifier)
- content_text (TEXT - UTF-8 sufficient)
- author_username, author_id
- engagement metrics (likes, comments, shares)
- post_timestamp, created_at
- source_keyword
- media_urls (for images/videos)
```

#### C. CONFIGURATION FILES
**File to modify: `/config.py`**
```python
Changes:
1. Remove Weibo-specific settings
2. Add API keys for:
   - TWITTER_API_KEY, TWITTER_API_SECRET
   - REDDIT_CLIENT_ID, REDDIT_SECRET
   - FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID
   - INSTAGRAM_ACCESS_TOKEN
   - YOUTUBE_API_KEY
   - LINKEDIN_ACCESS_TOKEN

2. Change DB charset validation (UTF-8 works for English)
3. Update platform list validation
4. Consider rate limiting configs per platform

Example changes:
```

#### D. PROMPTS - MAJOR REWRITES REQUIRED
**File: `/InsightEngine/prompts/prompts.py`**
```python
Current structure hardcoded for 7 platforms:
"可选值：bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"

Must become:
"可选值：twitter, reddit, facebook, instagram, youtube, linkedin, tiktok_us"

Search keyword guidance (currently Chinese-focused):
NEEDS COMPLETE REWRITE with USA platform culture:

Twitter-specific:
- Use hashtags: #topic, #Breaking
- Handle @ mentions
- Retweet culture: "RT @user"
- Quote tweets for criticism
- Thread discussions

Reddit-specific:
- Subreddit names: r/subreddit
- Redditor culture (anonymous, discussion-focused)
- Upvote/downvote etiquette
- Cross-post references
- Silver/Gold award system

Facebook-specific:
- Group dynamics
- Reactions (like, love, wow, haha, sad, angry)
- Sharing between friends/public
- Event discussions

Instagram-specific:
- Hashtag culture (different from Twitter)
- Influencer engagement
- Story vs. Post dynamics
- Engagement baiting patterns

YouTube-specific:
- Video comments (different context)
- Community posts
- Pinned comments
- Reply chains

Search strategy examples:
Before: "武大" (school name) + platform-specific slang
After: "#ElonMusk" or "r/news" or keyword + platform
```

**File: `/MediaEngine/prompts/prompts.py`**
```python
Remove platform-specific language instruction:
"微博：热搜词汇、话题标签"
"B站：弹幕文化"
"贴吧：直接称呼"

Replace with USA platform culture:
"Twitter: Hashtag culture, @mentions, quote tweeting, threads"
"Reddit: Subreddit context, upvote/downvote, community norms"
"Facebook: Group discussions, reactions, event-based discussions"
"Instagram: Visual-first, hashtags, influencer engagement"
```

**File: `/QueryEngine/prompts/prompts.py`**
```python
Update platform parameter:
"可选值：twitter, reddit, facebook, instagram, youtube, linkedin, tiktok_us"

Remove search_topic_on_platform tool complexity built around 7 specific platforms
Must handle different API capabilities:
- Twitter API v2: Different search syntax
- Reddit API: Subreddit-specific
- YouTube Data API: Video-specific search
```

#### E. SENTIMENT ANALYSIS RETRAINING
```
Current: WeiboSentiment models (trained on Chinese Weibo data)
Problem: Models tuned for Chinese slang, emoji usage, cultural references

Changes needed:
1. Use multi-lingual model (already available: tabularisai/multilingual-sentiment-analysis)
2. Consider English-specific fine-tuning on:
   - Twitter sentiment corpus
   - Reddit discussion tone
   - YouTube comment sentiment
3. New sentiment word library for English:
   - Positive: "amazing", "love", "incredible", "brilliant"
   - Negative: "terrible", "hate", "awful", "pathetic"
   - Sarcasm detection (heavy in Reddit/Twitter)
   - Emoji interpretation (same as Chinese but different usage)

3. Platform-specific sentiment considerations:
   - Twitter: Sarcasm, irony, hashtag sentiment
   - Reddit: Nuanced debate, downvote = disagreement
   - Facebook: More polite disagreement
   - YouTube: Mixed sentiment in replies
```

#### F. REPORT TEMPLATES
**File: `/ReportEngine/report_template/`**
```
Current templates (China-specific language/context):
- 企业品牌声誉分析报告模板 (Brand reputation)
- 市场竞争格局舆情分析报告 (Market competition)
- 日常或定期舆情监测报告 (Daily monitoring)
- 特定政策或行业动态舆情分析报告 (Policy analysis)
- 社会公共热点事件分析报告 (Public events/hot topics)
- 突发事件与危机公关舆情报告 (Crisis management)

Sections need USA context updates:
- Remove references to "舆情" (Chinese netizen opinion)
- Update metric names (followers vs fans, upvotes vs likes)
- Change geographic context (US states vs Chinese provinces)
- Update cultural references (social events in USA)

Could keep structure but update content examples
```

#### G. DATABASE QUERIES IN SEARCH TOOLS
**File: `/InsightEngine/tools/search.py`**
```python
Current hardcoded table names:
- `bilibili_video`, `weibo_content`, `douyin_aweme`, etc.

Must add support for:
- `twitter_tweet`, `twitter_reply`, `twitter_retweet`
- `reddit_post`, `reddit_comment`
- `facebook_post`, `facebook_comment`
- `instagram_post`, `instagram_comment`
- `youtube_video`, `youtube_comment`
- `linkedin_post`, `linkedin_comment`

Methods to update:
1. search_hot_content() - works on all platforms
2. search_topic_globally() - modify table mapping
3. search_topic_by_date() - update date field names
4. get_comments_for_topic() - handle different comment table structures
5. search_topic_on_platform() - expand platform list

Hot content algorithm (currently):
W_LIKE = 1.0, W_COMMENT = 5.0, W_SHARE = 10.0, W_VIEW = 0.1
May need platform-specific weights:
- Twitter: Retweets (shares) = higher weight than likes
- Reddit: Upvotes + gold = different calculation
- YouTube: Views = very important
- Instagram: Engagement rate = likes + comments / followers
```

---

## 4. LANGUAGE BARRIERS IN CODE/PROMPTS

### Critical Chinese Language Issues:

#### A. Comments and Documentation
**Severity: HIGH**
- 95% of codebase is in Chinese comments
- File: Nearly all Python files start with `# -*- coding: utf-8 -*-` and Chinese comments
- Example: `/MindSpider/DeepSentimentCrawling/MediaCrawler/main.py` line 14:
  ```python
  # 微博爬虫主流程代码
  ```

**Fix required:**
- Translate all comments to English
- Update variable names from Chinese to English:
  - `wb_client` (Weibo client) → `social_media_client`
  - `DY` (Douyin) → `TIKTOK_US`
  - Platform names in config

#### B. String Messages and Prompts
**Severity: CRITICAL**
- All error messages in Chinese
- All log messages in Chinese
- All prompt instructions in Chinese
- User-facing strings in Chinese

**Files affected:**
- `/InsightEngine/prompts/prompts.py` - 630 lines
- `/MediaEngine/prompts/prompts.py` - 450 lines
- `/QueryEngine/prompts/prompts.py` - 450 lines
- `/ReportEngine/prompts/prompts.py` - 136 lines
- `/InsightEngine/tools/search.py` - 800+ lines
- `/InsightEngine/tools/sentiment_analyzer.py`

**Example (line 136-167 of InsightEngine/prompts.py):**
```python
SYSTEM_PROMPT_REPORT_STRUCTURE = f"""
你是一位专业的舆情分析师和报告架构师。给定一个查询，你需要规划一个全面、深入的舆情分析报告结构。
```

All must be translated to English for LLM to understand USA context.

#### C. LLM Model Recommendations
**Severity: HIGH**
`/config.py` recommends Chinese-optimized models:
```python
INSIGHT_ENGINE_MODEL_NAME: str = "kimi-k2-0711-preview"  # Kimi (Chinese model)
FORUM_HOST_MODEL_NAME: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"  # Qwen (Chinese)
KEYWORD_OPTIMIZER_MODEL_NAME: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"  # Qwen (Chinese)
```

**Changes needed:**
- Switch to English-optimized or multilingual models
- Recommendation: ChatGPT 4/4.5 Turbo, Claude, Gemini 2.5 Pro
- Ensure models understand USA social media context

#### D. Platform-Specific Cultural Knowledge
**Severity: MEDIUM**
LLM prompts expect agents to understand:
- Chinese platform conventions (handled by prompt design)
- Chinese slang and emoji usage
- Chinese social dynamics

**Required additions:**
- USA platform conventions (hashtag usage, thread culture, etc.)
- English slang and meme culture
- USA social/political dynamics
- Platform-specific etiquette

---

## 5. CONFIGURATION STRUCTURE SUMMARY

### Main Config Files:

**1. `/config.py` (104 lines)**
- Flask server (HOST, PORT)
- Database connection (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_CHARSET, DB_DIALECT)
- LLM API keys (4 different LLM services)
- Network tools (Tavily, Bocha)
- Search limits and timeouts
- 100% pydantic-settings based (env variable support)

**2. `/.env.example` (81 lines)**
- Template for all config values
- Shows all required API keys
- Platform recommendations (Chinese models)

**3. `/MindSpider/config.py` (36 lines)**
- Database config (mirrors main config)
- MindSpider-specific API key

### LLM Service Configuration:
```
4 Different LLM services (likely for load balancing):

1. InsightEngine (Main analysis)
   - Default: Kimi (moonshot.cn)
   - Customizable: Any OpenAI-compatible API

2. MediaEngine (Media content analysis)
   - Default: Gemini (via aihubmix.com)
   - Focus: Image/visual analysis

3. QueryEngine (Query processing)
   - Default: DeepSeek (deepseek.com)
   - Focus: Complex reasoning

4. ReportEngine (Report generation)
   - Default: Gemini (via aihubmix.com)

5. ForumHost (Discussion hosting)
   - Default: Qwen3 (siliconflow.cn)
   - Focus: Chinese language optimization

6. KeywordOptimizer (SQL optimization)
   - Default: Qwen3 (siliconflow.cn)
   - Focus: Search query optimization
```

### Configuration Changes for USA:
```
1. Database: No changes needed (UTF-8 supports all languages)
2. LLM Models: Switch to English-optimized models
3. API Keys: Remove Chinese-specific services
4. Search configs: May need adjustments for larger US datasets
```

---

## 6. COMPONENT BREAKDOWN FOR USA ADAPTATION

### By Priority:

#### PRIORITY 1 (Critical - Breaks functionality):
1. **MediaCrawler platform modules** - Add 7 new crawlers
2. **Database models** - Add tables for new platforms
3. **Prompts (all engines)** - Translate & rewrite for USA context
4. **CrawlerFactory** - Support new platforms
5. **Sentiment analyzer** - Retrain or use English models

#### PRIORITY 2 (High - Affects features):
1. **Search tools** - Update table references
2. **Configuration** - Add API keys for new platforms
3. **Report templates** - Update context/language
4. **Comments in all Python files** - Translate
5. **Error messages and logs** - Translate

#### PRIORITY 3 (Medium - Code quality):
1. **Variable names** - English naming conventions
2. **Database field names** - Standardize across platforms
3. **Configuration organization** - Platform-agnostic structure
4. **Type hints** - Ensure consistency

---

## 7. ESTIMATED EFFORT BREAKDOWN

| Component | Files | Effort | Notes |
|-----------|-------|--------|-------|
| New Crawlers (7 platforms) | 40+ | 8-12 weeks | API-based reduces complexity |
| Database Models | 1 | 2 days | Add new table definitions |
| Main Prompts | 4 | 1-2 weeks | Full translation + context rewrite |
| Search Tools | 2 | 3-5 days | Add platform support |
| Configuration | 2 | 1 day | Add new API keys |
| Sentiment Analysis | 5 | 2-3 days | Use multilingual model |
| Code Translation | ~50 | 1-2 weeks | Comments, messages, logs |
| Testing | - | 2-3 weeks | Each platform crawler + integration |
| Report Templates | 6 | 3-5 days | Update content examples |
| **Total** | **~100** | **12-16 weeks** | ~3-4 months |

---

## CONCLUSION

BettaFish is a well-architected system specifically optimized for Chinese social media analysis. While the core architecture is sound and extensible, adapting it for USA platforms requires:

1. **7 new crawler implementations** (Twitter, Reddit, Facebook, Instagram, YouTube, LinkedIn, TikTok US)
2. **Complete prompt rewrite** for USA social media culture and conventions
3. **Full translation** of Chinese comments, messages, and documentation
4. **New sentiment analysis models** trained on English/USA data
5. **Database expansion** with 7 new platform tables and adapted schemas
6. **LLM model switching** from Chinese-optimized to English-optimized services

The good news: The core architecture (agent-based research, multi-engine analysis, database abstraction) is platform-agnostic and can support any social media platform with these changes.

