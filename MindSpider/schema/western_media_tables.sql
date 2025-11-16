-- Western Media Platforms Database Schema
-- Tables for USA and Western media monitoring
-- Platform support: Reddit, Twitter/X, YouTube, TikTok, HackerNews, Google News

-- ===============================
-- Reddit Platform Tables
-- ===============================

-- Reddit posts table
DROP TABLE IF EXISTS `reddit_post`;
CREATE TABLE `reddit_post` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `post_id` varchar(32) NOT NULL COMMENT 'Reddit post ID',
    `subreddit` varchar(100) NOT NULL COMMENT 'Subreddit name',
    `title` varchar(500) NOT NULL COMMENT 'Post title',
    `author` varchar(100) COMMENT 'Post author username',
    `content` text COMMENT 'Post content/selftext',
    `url` varchar(512) COMMENT 'Post URL',
    `score` int DEFAULT 0 COMMENT 'Upvote score',
    `upvote_ratio` float DEFAULT 0 COMMENT 'Upvote ratio (0-1)',
    `num_comments` int DEFAULT 0 COMMENT 'Number of comments',
    `created_utc` bigint NOT NULL COMMENT 'Post creation timestamp',
    `flair_text` varchar(100) COMMENT 'Post flair',
    `is_self` tinyint(1) DEFAULT 0 COMMENT 'Is self post (text only)',
    `permalink` varchar(512) COMMENT 'Reddit permalink',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_reddit_post_unique` (`post_id`),
    KEY `idx_reddit_subreddit` (`subreddit`),
    KEY `idx_reddit_score` (`score`),
    KEY `idx_reddit_created` (`created_utc`),
    KEY `idx_reddit_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Reddit posts table';

-- Reddit comments table
DROP TABLE IF EXISTS `reddit_comment`;
CREATE TABLE `reddit_comment` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `comment_id` varchar(32) NOT NULL COMMENT 'Reddit comment ID',
    `post_id` varchar(32) NOT NULL COMMENT 'Parent post ID',
    `parent_id` varchar(32) COMMENT 'Parent comment ID (for replies)',
    `author` varchar(100) COMMENT 'Comment author username',
    `content` text NOT NULL COMMENT 'Comment content',
    `score` int DEFAULT 0 COMMENT 'Comment score',
    `created_utc` bigint NOT NULL COMMENT 'Comment creation timestamp',
    `depth` int DEFAULT 0 COMMENT 'Comment depth/level',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_reddit_comment_unique` (`comment_id`),
    KEY `idx_reddit_comment_post` (`post_id`),
    KEY `idx_reddit_comment_score` (`score`),
    KEY `idx_reddit_comment_created` (`created_utc`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Reddit comments table';

-- ===============================
-- Twitter/X Platform Tables
-- ===============================

-- Twitter tweets table
DROP TABLE IF EXISTS `twitter_tweet`;
CREATE TABLE `twitter_tweet` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `tweet_id` varchar(32) NOT NULL COMMENT 'Twitter tweet ID',
    `author_username` varchar(100) NOT NULL COMMENT 'Tweet author username',
    `author_name` varchar(200) COMMENT 'Tweet author display name',
    `content` text NOT NULL COMMENT 'Tweet text content',
    `created_at` bigint NOT NULL COMMENT 'Tweet creation timestamp',
    `retweet_count` int DEFAULT 0 COMMENT 'Number of retweets',
    `like_count` int DEFAULT 0 COMMENT 'Number of likes',
    `reply_count` int DEFAULT 0 COMMENT 'Number of replies',
    `quote_count` int DEFAULT 0 COMMENT 'Number of quotes',
    `impression_count` int DEFAULT 0 COMMENT 'Number of impressions',
    `hashtags` text COMMENT 'Hashtags (JSON array)',
    `urls` text COMMENT 'URLs in tweet (JSON array)',
    `media_urls` text COMMENT 'Media URLs (JSON array)',
    `language` varchar(10) DEFAULT 'en' COMMENT 'Tweet language',
    `is_retweet` tinyint(1) DEFAULT 0 COMMENT 'Is this a retweet',
    `is_reply` tinyint(1) DEFAULT 0 COMMENT 'Is this a reply',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_twitter_tweet_unique` (`tweet_id`),
    KEY `idx_twitter_author` (`author_username`),
    KEY `idx_twitter_created` (`created_at`),
    KEY `idx_twitter_likes` (`like_count`),
    KEY `idx_twitter_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Twitter/X tweets table';

-- ===============================
-- YouTube Platform Tables
-- ===============================

-- YouTube videos table
DROP TABLE IF EXISTS `youtube_video`;
CREATE TABLE `youtube_video` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `video_id` varchar(32) NOT NULL COMMENT 'YouTube video ID',
    `title` varchar(500) NOT NULL COMMENT 'Video title',
    `channel_id` varchar(50) NOT NULL COMMENT 'Channel ID',
    `channel_title` varchar(200) COMMENT 'Channel name',
    `description` text COMMENT 'Video description',
    `published_at` bigint NOT NULL COMMENT 'Publish timestamp',
    `view_count` bigint DEFAULT 0 COMMENT 'View count',
    `like_count` int DEFAULT 0 COMMENT 'Like count',
    `comment_count` int DEFAULT 0 COMMENT 'Comment count',
    `duration` varchar(20) COMMENT 'Video duration (ISO 8601)',
    `thumbnail_url` varchar(512) COMMENT 'Thumbnail URL',
    `tags` text COMMENT 'Video tags (JSON array)',
    `category_id` varchar(10) COMMENT 'YouTube category ID',
    `language` varchar(10) DEFAULT 'en' COMMENT 'Video language',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_youtube_video_unique` (`video_id`),
    KEY `idx_youtube_channel` (`channel_id`),
    KEY `idx_youtube_published` (`published_at`),
    KEY `idx_youtube_views` (`view_count`),
    KEY `idx_youtube_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='YouTube videos table';

-- YouTube comments table
DROP TABLE IF EXISTS `youtube_comment`;
CREATE TABLE `youtube_comment` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `comment_id` varchar(64) NOT NULL COMMENT 'YouTube comment ID',
    `video_id` varchar(32) NOT NULL COMMENT 'Parent video ID',
    `parent_id` varchar(64) COMMENT 'Parent comment ID (for replies)',
    `author` varchar(100) COMMENT 'Comment author name',
    `content` text NOT NULL COMMENT 'Comment text',
    `like_count` int DEFAULT 0 COMMENT 'Like count',
    `published_at` bigint NOT NULL COMMENT 'Comment publish timestamp',
    `is_reply` tinyint(1) DEFAULT 0 COMMENT 'Is this a reply to another comment',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_youtube_comment_unique` (`comment_id`),
    KEY `idx_youtube_comment_video` (`video_id`),
    KEY `idx_youtube_comment_published` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='YouTube comments table';

-- ===============================
-- TikTok Platform Tables
-- ===============================

-- TikTok videos table (US TikTok)
DROP TABLE IF EXISTS `tiktok_video`;
CREATE TABLE `tiktok_video` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `video_id` varchar(32) NOT NULL COMMENT 'TikTok video ID',
    `author_username` varchar(100) NOT NULL COMMENT 'Author username',
    `author_name` varchar(200) COMMENT 'Author display name',
    `title` varchar(500) COMMENT 'Video title/caption',
    `description` text COMMENT 'Video description',
    `created_at` bigint NOT NULL COMMENT 'Video creation timestamp',
    `view_count` bigint DEFAULT 0 COMMENT 'View count',
    `like_count` int DEFAULT 0 COMMENT 'Like count',
    `comment_count` int DEFAULT 0 COMMENT 'Comment count',
    `share_count` int DEFAULT 0 COMMENT 'Share count',
    `hashtags` text COMMENT 'Hashtags (JSON array)',
    `video_url` varchar(512) COMMENT 'Video URL',
    `music_title` varchar(200) COMMENT 'Background music title',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_tiktok_video_unique` (`video_id`),
    KEY `idx_tiktok_author` (`author_username`),
    KEY `idx_tiktok_created` (`created_at`),
    KEY `idx_tiktok_views` (`view_count`),
    KEY `idx_tiktok_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='TikTok videos table (US)';

-- ===============================
-- HackerNews Platform Tables
-- ===============================

-- HackerNews posts table
DROP TABLE IF EXISTS `hackernews_post`;
CREATE TABLE `hackernews_post` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `post_id` varchar(32) NOT NULL COMMENT 'HackerNews post ID',
    `post_type` varchar(20) NOT NULL COMMENT 'Post type (story|ask|show|job|poll)',
    `title` varchar(500) NOT NULL COMMENT 'Post title',
    `author` varchar(100) COMMENT 'Post author username',
    `url` varchar(512) COMMENT 'External URL (for stories)',
    `text` text COMMENT 'Post text content (for ask/show)',
    `score` int DEFAULT 0 COMMENT 'Post score/points',
    `num_comments` int DEFAULT 0 COMMENT 'Number of comments',
    `created_at` bigint NOT NULL COMMENT 'Post creation timestamp',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_hn_post_unique` (`post_id`),
    KEY `idx_hn_type` (`post_type`),
    KEY `idx_hn_score` (`score`),
    KEY `idx_hn_created` (`created_at`),
    KEY `idx_hn_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='HackerNews posts table';

-- HackerNews comments table
DROP TABLE IF EXISTS `hackernews_comment`;
CREATE TABLE `hackernews_comment` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `comment_id` varchar(32) NOT NULL COMMENT 'HackerNews comment ID',
    `post_id` varchar(32) NOT NULL COMMENT 'Parent post ID',
    `parent_id` varchar(32) COMMENT 'Parent comment ID (for replies)',
    `author` varchar(100) COMMENT 'Comment author username',
    `text` text NOT NULL COMMENT 'Comment text',
    `created_at` bigint NOT NULL COMMENT 'Comment creation timestamp',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_hn_comment_unique` (`comment_id`),
    KEY `idx_hn_comment_post` (`post_id`),
    KEY `idx_hn_comment_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='HackerNews comments table';

-- ===============================
-- Western News Sources Table
-- ===============================
-- For RSS feeds from Google News, news websites, etc.

DROP TABLE IF EXISTS `western_news_article`;
CREATE TABLE `western_news_article` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto-increment ID',
    `article_id` varchar(128) NOT NULL COMMENT 'Article unique ID (hash of URL)',
    `source` varchar(100) NOT NULL COMMENT 'News source (cnn|fox|nyt|wsj|bbc|reuters|google_news)',
    `political_lean` varchar(20) COMMENT 'Political leaning (left|right|center)',
    `title` varchar(500) NOT NULL COMMENT 'Article title',
    `url` varchar(512) NOT NULL COMMENT 'Article URL',
    `author` varchar(200) COMMENT 'Article author',
    `description` text COMMENT 'Article description/summary',
    `content` text COMMENT 'Full article content (if scraped)',
    `published_at` bigint COMMENT 'Article publish timestamp',
    `category` varchar(50) COMMENT 'News category (politics|tech|business|world)',
    `topic_id` varchar(64) DEFAULT NULL COMMENT 'Associated topic ID',
    `crawling_task_id` varchar(64) DEFAULT NULL COMMENT 'Associated crawling task ID',
    `add_ts` bigint NOT NULL COMMENT 'Record add timestamp',
    `last_modify_ts` bigint NOT NULL COMMENT 'Record last modify timestamp',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_western_news_unique` (`article_id`),
    KEY `idx_western_news_source` (`source`),
    KEY `idx_western_news_lean` (`political_lean`),
    KEY `idx_western_news_published` (`published_at`),
    KEY `idx_western_news_topic` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Western news articles table';

-- ===============================
-- Platform Statistics View
-- ===============================

CREATE OR REPLACE VIEW `v_western_platform_stats` AS
SELECT
    'Reddit' as platform,
    COUNT(*) as total_posts,
    SUM(num_comments) as total_comments,
    DATE(FROM_UNIXTIME(MAX(created_utc))) as last_crawl_date
FROM reddit_post
UNION ALL
SELECT
    'Twitter' as platform,
    COUNT(*) as total_posts,
    SUM(reply_count) as total_comments,
    DATE(FROM_UNIXTIME(MAX(created_at))) as last_crawl_date
FROM twitter_tweet
UNION ALL
SELECT
    'YouTube' as platform,
    COUNT(*) as total_posts,
    SUM(comment_count) as total_comments,
    DATE(FROM_UNIXTIME(MAX(published_at))) as last_crawl_date
FROM youtube_video
UNION ALL
SELECT
    'TikTok' as platform,
    COUNT(*) as total_posts,
    SUM(comment_count) as total_comments,
    DATE(FROM_UNIXTIME(MAX(created_at))) as last_crawl_date
FROM tiktok_video
UNION ALL
SELECT
    'HackerNews' as platform,
    COUNT(*) as total_posts,
    SUM(num_comments) as total_comments,
    DATE(FROM_UNIXTIME(MAX(created_at))) as last_crawl_date
FROM hackernews_post;
