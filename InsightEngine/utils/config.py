"""
Configuration management module for the Insight Engine.
Handles environment variables and config file parameters.
"""

import os
from dataclasses import dataclass
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from loguru import logger

class Settings(BaseSettings):
    INSIGHT_ENGINE_API_KEY: Optional[str] = Field(None, description="Insight Engine LLM API密钥")
    INSIGHT_ENGINE_BASE_URL: Optional[str] = Field(None, description="Insight Engine LLM base url，可选")
    INSIGHT_ENGINE_MODEL_NAME: Optional[str] = Field(None, description="Insight Engine LLM模型名称")
    INSIGHT_ENGINE_PROVIDER: Optional[str] = Field(None, description="Insight Engine模型提供者，不再建议使用")
    DB_HOST: Optional[str] = Field(None, description="数据库主机")
    DB_USER: Optional[str] = Field(None, description="数据库用户名")
    DB_PASSWORD: Optional[str] = Field(None, description="数据库密码")
    DB_NAME: Optional[str] = Field(None, description="数据库名称")
    DB_PORT: int = Field(3306, description="数据库端口")
    DB_CHARSET: str = Field("utf8mb4", description="数据库字符集")
    DB_DIALECT: Optional[str] = Field("mysql", description="数据库方言，如mysql、postgresql等，SQLAlchemy后端选择")
    MAX_REFLECTIONS: int = Field(3, description="最大反思次数")
    MAX_PARAGRAPHS: int = Field(6, description="最大段落数")
    SEARCH_TIMEOUT: int = Field(240, description="单次搜索请求超时")
    MAX_CONTENT_LENGTH: int = Field(500000, description="搜索最大内容长度")
    DEFAULT_SEARCH_HOT_CONTENT_LIMIT: int = Field(100, description="热榜内容默认最大数")
    DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE: int = Field(50, description="按表全局话题最大数")
    DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE: int = Field(100, description="按日期话题最大数")
    DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT: int = Field(500, description="单话题评论最大数")
    DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT: int = Field(200, description="平台搜索话题最大数")
    MAX_SEARCH_RESULTS_FOR_LLM: int = Field(0, description="供LLM用搜索结果最大数")
    MAX_HIGH_CONFIDENCE_SENTIMENT_RESULTS: int = Field(0, description="高置信度情感分析最大数")
    OUTPUT_DIR: str = Field("reports", description="输出路径")
    SAVE_INTERMEDIATE_STATES: bool = Field(True, description="是否保存中间状态")

    class Config:
        env_file = ".env"
        env_prefix = ""
        case_sensitive = False
        extra = "allow"

settings = Settings()