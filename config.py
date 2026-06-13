# -*- coding: utf-8 -*-
"""
微舆配置文件

此模块使用 pydantic-settings 管理全局配置，支持从环境变量和 .env 文件自动加载。
数据模型定义位置：
- 本文件 - 配置模型定义
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional, Literal
from loguru import logger


# 计算 .env 优先级：优先当前工作目录，其次项目根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parent
CWD_ENV: Path = Path.cwd() / ".env"
ENV_FILE: str = str(CWD_ENV if CWD_ENV.exists() else (PROJECT_ROOT / ".env"))


class Settings(BaseSettings):
    """
    全局配置；支持 .env 和环境变量自动加载。
    变量名与原 config.py 大写一致，便于平滑过渡。
    """
    # ================== Flask 服务器配置 ====================
    HOST: str = Field("0.0.0.0", description="BETTAFISH 主机地址，例如 0.0.0.0 或 127.0.0.1")
    PORT: int = Field(5000, description="Flask服务器端口号，默认5000")

    # ====================== 数据库配置 ======================
    DB_DIALECT: str = Field("postgresql", description="数据库类型，可选 mysql 或 postgresql；请与其他连接信息同时配置")
    DB_HOST: str = Field("your_db_host", description="数据库主机，例如localhost 或 127.0.0.1")
    DB_PORT: int = Field(5432, description="数据库端口号，postgresql默认为5432，mysql默认为3306")
    DB_USER: str = Field("your_db_user", description="数据库用户名")
    DB_PASSWORD: str = Field("your_db_password", description="数据库密码")
    DB_NAME: str = Field("your_db_name", description="数据库名称")
    DB_CHARSET: str = Field("utf8mb4", description="数据库字符集，推荐utf8mb4，兼容emoji")
    
    # ======================= LLM 相关 =======================
    # 我们的LLM模型API赞助商有：https://aihubmix.com/?aff=8Ds9，提供了非常全面的模型api
    
    # Insight Agent（推荐Kimi，申请地址：https://platform.moonshot.cn/）
    INSIGHT_ENGINE_API_KEY: Optional[str] = Field(None, description="Insight Agent（推荐 kimi-k2，官方申请地址：https://platform.moonshot.cn/）API 密钥，用于主 LLM。🚩请先按推荐配置申请并跑通，再根据需要调整 KEY、BASE_URL 与 MODEL_NAME。")
    INSIGHT_ENGINE_BASE_URL: Optional[str] = Field("https://api.moonshot.cn/v1", description="Insight Agent LLM BaseUrl，可根据厂商自定义")
    INSIGHT_ENGINE_MODEL_NAME: str = Field("kimi-k2-0711-preview", description="Insight Agent LLM 模型名称，例如 kimi-k2-0711-preview")
    
    # Media Agent（推荐Gemini，推荐中转厂商：https://aihubmix.com/?aff=8Ds9）
    MEDIA_ENGINE_API_KEY: Optional[str] = Field(None, description="Media Agent（推荐 gemini-2.5-pro，中转厂商申请地址：https://aihubmix.com/?aff=8Ds9）API 密钥")
    MEDIA_ENGINE_BASE_URL: Optional[str] = Field("https://aihubmix.com/v1", description="Media Agent LLM BaseUrl，可根据中转服务调整")
    MEDIA_ENGINE_MODEL_NAME: str = Field("gemini-2.5-pro", description="Media Agent LLM 模型名称，如 gemini-2.5-pro")
    
    # Query Agent（推荐DeepSeek，申请地址：https://www.deepseek.com/）
    QUERY_ENGINE_API_KEY: Optional[str] = Field(None, description="Query Agent（推荐 deepseek，官方申请地址：https://platform.deepseek.com/）API 密钥")
    QUERY_ENGINE_BASE_URL: Optional[str] = Field("https://api.deepseek.com", description="Query Agent LLM BaseUrl")
    QUERY_ENGINE_MODEL_NAME: str = Field("deepseek-chat", description="Query Agent LLM 模型名称，如 deepseek-reasoner")
    
    # Report Agent（推荐Gemini，推荐中转厂商：https://aihubmix.com/?aff=8Ds9）
    REPORT_ENGINE_API_KEY: Optional[str] = Field(None, description="Report Agent（推荐 gemini-2.5-pro，中转厂商申请地址：https://aihubmix.com/?aff=8Ds9）API 密钥")
    REPORT_ENGINE_BASE_URL: Optional[str] = Field("https://aihubmix.com/v1", description="Report Agent LLM BaseUrl，可根据中转服务调整")
    REPORT_ENGINE_MODEL_NAME: str = Field("gemini-2.5-pro", description="Report Agent LLM 模型名称，如 gemini-2.5-pro")

    # MindSpider Agent（推荐Deepseek，官方申请地址：https://platform.deepseek.com/）
    MINDSPIDER_API_KEY: Optional[str] = Field(None, description="MindSpider Agent（推荐 deepseek，官方申请地址：https://platform.deepseek.com/）API 密钥")
    MINDSPIDER_BASE_URL: Optional[str] = Field(None, description="MindSpider Agent BaseUrl，可按所选服务配置")
    MINDSPIDER_MODEL_NAME: Optional[str] = Field(None, description="MindSpider Agent 模型名称，例如 deepseek-reasoner")
    
    # Forum Host（Qwen3最新模型，这里我使用了硅基流动这个平台，申请地址：https://cloud.siliconflow.cn/）
    FORUM_HOST_API_KEY: Optional[str] = Field(None, description="Forum Host（推荐 qwen-plus，官方申请地址：https://www.aliyun.com/product/bailian）API 密钥")
    FORUM_HOST_BASE_URL: Optional[str] = Field(None, description="Forum Host LLM BaseUrl，可按所选服务配置")
    FORUM_HOST_MODEL_NAME: Optional[str] = Field(None, description="Forum Host LLM 模型名称，例如 qwen-plus")
    
    # SQL keyword Optimizer（小参数Qwen3模型，这里我使用了硅基流动这个平台，申请地址：https://cloud.siliconflow.cn/）
    KEYWORD_OPTIMIZER_API_KEY: Optional[str] = Field(None, description="SQL Keyword Optimizer（推荐 qwen-plus，官方申请地址：https://www.aliyun.com/product/bailian）API 密钥")
    KEYWORD_OPTIMIZER_BASE_URL: Optional[str] = Field(None, description="Keyword Optimizer BaseUrl，可按所选服务配置")
    KEYWORD_OPTIMIZER_MODEL_NAME: Optional[str] = Field(None, description="Keyword Optimizer LLM 模型名称，例如 qwen-plus")
    
    # ================== 网络工具配置 ====================
    # Tavily API（申请地址：https://www.tavily.com/）
    TAVILY_API_KEY: Optional[str] = Field(None, description="Tavily API（申请地址：https://www.tavily.com/）API密钥，用于Tavily网络搜索")

    SEARCH_TOOL_TYPE: Literal["LocalizedAPI", "TavilyAPI", "BraveAPI", "NaverAPI", "SerperAPI", "JinaAPI", "SearxngAPI", "AnspireAPI", "BochaAPI"] = Field("LocalizedAPI", description="搜索工具类型。localized 默认使用 SEARCH_PROVIDER，并保留 Anspire/Bocha 作为 legacy/upstream 选项。")
    SEARCH_PROVIDER: Literal["tavily", "brave", "naver", "serper", "jina", "searxng", "anspire", "bocha"] = Field("searxng", description="Localized search provider. Compose/local default is searxng; opt into brave/naver/tavily/serper/jina with keys.")
    SEARCH_MARKET: Literal["global", "korea", "china", "japan", "developer"] = Field("global", description="검색 시장/언어 힌트. Provider별 query/source routing에 사용.")
    SEARCH_FAIL_CLOSED: bool = Field(True, description="검색 provider 실패를 빈 성공으로 숨기지 않고 명시적으로 실패 처리한다.")
    SEARCH_MAX_RESULTS: int = Field(10, description="기본 검색 결과 수")

    # ================== MindSpider source collection ====================
    MINDSPIDER_SOURCE_MODE: Literal["localized", "legacy_china"] = Field("localized", description="MindSpider source mode. localized uses provider/RSS sources; legacy_china enables original China platform crawlers explicitly.")
    MINDSPIDER_SOURCE_PROVIDER: Literal["searxng", "naver", "brave", "tavily", "serper", "jina"] = Field("searxng", description="Default localized MindSpider source provider.")
    MINDSPIDER_SOURCE_QUERIES: str = Field("AI, technology, market, public opinion", description="Comma-separated default queries for localized source discovery.")
    MINDSPIDER_RSS_FEEDS: Optional[str] = Field(None, description="Comma-separated RSS feed URLs for localized MindSpider source collection.")
    MINDSPIDER_REDDIT_SUBREDDITS: Optional[str] = Field(None, description="Comma-separated subreddit names for optional public Reddit search.")
    MINDSPIDER_YOUTUBE_CHANNEL_IDS: Optional[str] = Field(None, description="Comma-separated channel IDs for YouTube channel RSS collection.")
    REDDIT_CLIENT_ID: Optional[str] = Field(None, description="Reddit API client id for reddit-api source.")
    REDDIT_CLIENT_SECRET: Optional[str] = Field(None, description="Reddit API client secret for reddit-api source.")
    YOUTUBE_DATA_API_KEY: Optional[str] = Field(None, description="YouTube Data API key for youtube-data source.")
    BLUESKY_IDENTIFIER: Optional[str] = Field(None, description="Optional Bluesky handle/email for API-backed Bluesky search.")
    BLUESKY_APP_PASSWORD: Optional[str] = Field(None, description="Optional Bluesky app password for API-backed Bluesky search.")
    MASTODON_INSTANCE: str = Field("mastodon.social", description="Mastodon instance hostname for mastodon source.")
    MASTODON_ACCESS_TOKEN: Optional[str] = Field(None, description="Optional Mastodon token for instances requiring authenticated search.")
    X_BEARER_TOKEN: Optional[str] = Field(None, description="X/Twitter API v2 bearer token for x-api source.")

    # Global/Korean-friendly search providers
    BRAVE_SEARCH_API_KEY: Optional[str] = Field(None, description="Brave Search API key. Good global default with independent web index.")
    BRAVE_SEARCH_BASE_URL: str = Field("https://api.search.brave.com/res/v1/web/search", description="Brave Search API endpoint")
    NAVER_CLIENT_ID: Optional[str] = Field(None, description="Naver Search API client id. Strong Korean web/blog/news/local coverage.")
    NAVER_CLIENT_SECRET: Optional[str] = Field(None, description="Naver Search API client secret")
    NAVER_SEARCH_BASE_URL: str = Field("https://openapi.naver.com/v1/search/news.json", description="Naver Search API endpoint; can be switched to webkr/blog/news endpoints.")
    SERPER_API_KEY: Optional[str] = Field(None, description="Serper.dev API key. Google-result proxy style provider for broad global coverage.")
    SERPER_BASE_URL: str = Field("https://google.serper.dev/search", description="Serper search endpoint")
    JINA_API_KEY: Optional[str] = Field(None, description="Optional Jina API key for Search/Reader style retrieval if quota requires it.")
    JINA_SEARCH_BASE_URL: str = Field("https://s.jina.ai/", description="Jina Search endpoint prefix")
    SEARXNG_BASE_URL: Optional[str] = Field("http://searxng:8080", description="Self-hosted/public SearXNG base URL. In Docker Compose use http://searxng:8080; host/dev may use http://localhost:8080")

    # Legacy / upstream China-focused providers
    # Bocha API（申请地址：https://open.bochaai.com/）
    BOCHA_BASE_URL: Optional[str] = Field("https://api.bocha.cn/v1/ai-search", description="Bocha AI 搜索BaseUrl或博查网页搜索BaseUrl")
    BOCHA_WEB_SEARCH_API_KEY: Optional[str] = Field(None, description="Bocha API（申请地址：https://open.bochaai.com/）API密钥，用于Bocha搜索")

    # Anspire AI Search API（申请地址：https://open.anspire.cn/?share_code=3E1FUOUH）
    ANSPIRE_BASE_URL: Optional[str] = Field("https://plugin.anspire.cn/api/ntsearch/search", description="Anspire AI 搜索BaseUrl")
    ANSPIRE_API_KEY: Optional[str] = Field(None, description="Anspire AI Search API（申请地址：https://open.anspire.cn/?share_code=3E1FUOUH）API密钥，用于Anspire搜索")

    
    # ================== Insight Engine 搜索配置 ====================
    DEFAULT_SEARCH_HOT_CONTENT_LIMIT: int = Field(100, description="热榜内容默认最大数")
    DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE: int = Field(50, description="按表全局话题最大数")
    DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE: int = Field(100, description="按日期话题最大数")
    DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT: int = Field(500, description="单话题评论最大数")
    DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT: int = Field(200, description="平台搜索话题最大数")
    MAX_SEARCH_RESULTS_FOR_LLM: int = Field(0, description="供LLM用搜索结果最大数")
    MAX_HIGH_CONFIDENCE_SENTIMENT_RESULTS: int = Field(0, description="高置信度情感分析最大数")
    MAX_REFLECTIONS: int = Field(3, description="最大反思次数")
    MAX_PARAGRAPHS: int = Field(6, description="最大段落数")
    SEARCH_TIMEOUT: int = Field(240, description="单次搜索请求超时")
    MAX_CONTENT_LENGTH: int = Field(500000, description="搜索最大内容长度")
    
    model_config = ConfigDict(
        env_file=ENV_FILE,
        env_prefix="",
        case_sensitive=False,
        extra="allow"
    )


# 创建全局配置实例
settings = Settings()


def reload_settings() -> Settings:
    """
    重新加载配置
    
    从 .env 文件和环境变量重新加载配置，更新全局 settings 实例。
    用于在运行时动态更新配置。
    
    Returns:
        Settings: 新创建的配置实例
    """
    
    global settings
    settings = Settings()
    return settings
