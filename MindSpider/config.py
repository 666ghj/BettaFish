# -*- coding: utf-8 -*-
"""
存储数据库连接信息和API密钥
"""

from pydantic_settings import BaseSettings
from typing import Optional, Literal
from pydantic import Field
from pathlib import Path

# 计算 .env 优先级：优先当前工作目录，其次项目根目录（MindSpider 的上级目录）
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
CWD_ENV: Path = Path.cwd() / ".env"
ENV_FILE: str = str(CWD_ENV if CWD_ENV.exists() else (PROJECT_ROOT / ".env"))

class Settings(BaseSettings):
    """全局配置管理，优先从环境变量和.env加载。支持MySQL/PostgreSQL统一数据库参数命名。"""
    DB_DIALECT: str = Field("mysql", description="数据库类型，支持'mysql'或'postgresql'")
    DB_HOST: str = Field("your_host", description="数据库主机名或IP地址")
    DB_PORT: int = Field(3306, description="数据库端口号")
    DB_USER: str = Field("your_username", description="数据库用户名")
    DB_PASSWORD: str = Field("your_password", description="数据库密码")
    DB_NAME: str = Field("mindspider", description="数据库名称")
    DB_CHARSET: str = Field("utf8mb4", description="数据库字符集")
    MINDSPIDER_API_KEY: Optional[str] = Field(None, description="MINDSPIDER API密钥")
    MINDSPIDER_BASE_URL: Optional[str] = Field("https://api.deepseek.com", description="MINDSPIDER API基础URL，推荐deepseek-chat模型使用https://api.deepseek.com")
    MINDSPIDER_MODEL_NAME: Optional[str] = Field("deepseek-chat", description="MINDSPIDER API模型名称, 推荐deepseek-chat")

    # Localized source collection. Default path avoids China-locked sources.
    MINDSPIDER_SOURCE_MODE: Literal["localized", "legacy_china"] = Field("localized", description="localized uses SearXNG/Naver/Brave/RSS; legacy_china enables original China platform crawlers explicitly")
    MINDSPIDER_SOURCE_PROVIDER: Literal["searxng", "naver", "brave", "tavily", "serper", "jina"] = Field("searxng", description="Localized source provider")
    MINDSPIDER_SOURCE_QUERIES: str = Field("AI, technology, market, public opinion", description="Comma-separated source discovery queries")
    MINDSPIDER_RSS_FEEDS: Optional[str] = Field(None, description="Comma-separated RSS feed URLs")
    MINDSPIDER_REDDIT_SUBREDDITS: Optional[str] = Field(None, description="Comma-separated subreddit names for optional public Reddit source search")
    MINDSPIDER_YOUTUBE_CHANNEL_IDS: Optional[str] = Field(None, description="Comma-separated YouTube channel IDs for youtube-rss source")
    REDDIT_CLIENT_ID: Optional[str] = Field(None, description="Reddit API client id for reddit-api source")
    REDDIT_CLIENT_SECRET: Optional[str] = Field(None, description="Reddit API client secret for reddit-api source")
    YOUTUBE_DATA_API_KEY: Optional[str] = Field(None, description="YouTube Data API key for youtube-data source")
    BLUESKY_IDENTIFIER: Optional[str] = Field(None, description="Optional Bluesky handle/email for API-backed Bluesky search")
    BLUESKY_APP_PASSWORD: Optional[str] = Field(None, description="Optional Bluesky app password for API-backed Bluesky search")
    MASTODON_INSTANCE: str = Field("mastodon.social", description="Mastodon instance hostname for mastodon source")
    MASTODON_ACCESS_TOKEN: Optional[str] = Field(None, description="Optional Mastodon access token for instance search")
    X_BEARER_TOKEN: Optional[str] = Field(None, description="X/Twitter API v2 bearer token for x-api source")
    SEARCH_FAIL_CLOSED: bool = Field(True, description="Fail closed on source provider errors")
    SEARCH_TIMEOUT: int = Field(30, description="Source provider timeout seconds")
    SEARXNG_BASE_URL: Optional[str] = Field("http://searxng:8080", description="SearXNG URL in Compose; use localhost for host/dev")
    BRAVE_SEARCH_API_KEY: Optional[str] = Field(None, description="Brave Search API key")
    NAVER_CLIENT_ID: Optional[str] = Field(None, description="Naver Search client id")
    NAVER_CLIENT_SECRET: Optional[str] = Field(None, description="Naver Search client secret")
    TAVILY_API_KEY: Optional[str] = Field(None, description="Tavily API key")
    SERPER_API_KEY: Optional[str] = Field(None, description="Serper API key")
    JINA_API_KEY: Optional[str] = Field(None, description="Jina API key")

    class Config:
        env_file = ENV_FILE
        env_prefix = ""
        case_sensitive = False
        extra = "allow"

settings = Settings()
