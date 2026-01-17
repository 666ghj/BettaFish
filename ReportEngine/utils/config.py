"""
Report Engine 配置模块，统一读取环境变量并提供类型安全的访问方式。
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

from loguru import logger

class Settings(BaseSettings):
    """Report Engine 配置，环境变量与字段均为REPORT_ENGINE_前缀一致大写。"""
    REPORT_ENGINE_API_KEY: Optional[str] = Field(None, description="Report Engine LLM API密钥")
    REPORT_ENGINE_BASE_URL: Optional[str] = Field(None, description="Report Engine LLM基础URL")
    REPORT_ENGINE_MODEL_NAME: Optional[str] = Field(None, description="Report Engine LLM模型名称")
    REPORT_ENGINE_PROVIDER: Optional[str] = Field(None, description="模型服务商，仅兼容保留")
    # 其他引擎API（用于跨引擎修复）
    FORUM_HOST_API_KEY: Optional[str] = Field(
        None, description="Forum Engine / Forum Host 的LLM API密钥（用于章节修复兜底）"
    )
    FORUM_HOST_BASE_URL: Optional[str] = Field(
        None, description="Forum Engine API Base URL（为空则使用LLM默认配置）"
    )
    FORUM_HOST_MODEL_NAME: Optional[str] = Field(
        None, description="Forum Engine LLM模型名称"
    )
    INSIGHT_ENGINE_API_KEY: Optional[str] = Field(
        None, description="Insight Engine LLM API密钥，用于跨引擎章节修复"
    )
    INSIGHT_ENGINE_BASE_URL: Optional[str] = Field(
        None, description="Insight Engine API Base URL"
    )
    INSIGHT_ENGINE_MODEL_NAME: Optional[str] = Field(
        None, description="Insight Engine LLM模型名称"
    )
    MEDIA_ENGINE_API_KEY: Optional[str] = Field(
        None, description="Media Engine LLM API密钥，用于跨引擎章节修复"
    )
    MEDIA_ENGINE_BASE_URL: Optional[str] = Field(
        None, description="Media Engine API Base URL"
    )
    MEDIA_ENGINE_MODEL_NAME: Optional[str] = Field(
        None, description="Media Engine LLM模型名称"
    )
    MAX_CONTENT_LENGTH: int = Field(200000, description="最大内容长度")
    OUTPUT_DIR: str = Field("final_reports", description="主输出目录")
    # 章节分块JSON会存储在该目录，便于溯源与断点续传
    CHAPTER_OUTPUT_DIR: str = Field(
        "final_reports/chapters", description="章节JSON缓存目录"
    )
    # 装订后的整本IR/manifest也会持久化，方便调试与审计
    DOCUMENT_IR_OUTPUT_DIR: str = Field(
        "final_reports/ir", description="整本IR/Manifest输出目录"
    )
    CHAPTER_JSON_MAX_ATTEMPTS: int = Field(
        2, description="章节JSON解析失败时的最大尝试次数"
    )
    TEMPLATE_DIR: str = Field("ReportEngine/report_template", description="多模板目录")
    API_TIMEOUT: float = Field(900.0, description="单API超时时间（秒）")
    MAX_RETRY_DELAY: float = Field(180.0, description="最大重试间隔（秒）")
    MAX_RETRIES: int = Field(8, description="最大重试次数")
    LOG_FILE: str = Field("logs/report.log", description="日志输出文件")
    ENABLE_PDF_EXPORT: bool = Field(True, description="是否允许导出PDF")
    CHART_STYLE: str = Field("modern", description="图表样式：modern/classic/")
    JSON_ERROR_LOG_DIR: str = Field(
        "logs/json_repair_failures", description="无法修复的JSON块落盘目录"
    )
    
    # GraphRAG 配置
    GRAPHRAG_ENABLED: bool = Field(
        default=False, description="是否启用GraphRAG知识图谱功能"
    )
    GRAPHRAG_MAX_QUERIES: int = Field(
        default=3, description="GraphRAG每章节查询次数上限"
    )

    # 报告压缩配置
    ENABLE_REPORT_COMPRESSION: bool = Field(
        default=True, description="是否启用报告压缩以避免上下文超限"
    )
    SUMMARY_STRATEGY: str = Field(
        default="rule", description="摘要策略：rule=规则提取, llm=LLM摘要, hybrid=混合"
    )
    SUMMARY_COMPRESSION_RATIO: float = Field(
        default=0.35, description="摘要目标压缩率（0.3-0.4推荐）"
    )
    EXTRACTION_STRATEGY: str = Field(
        default="keyword", description="提取策略：keyword=关键词匹配, embedding=语义相似度"
    )
    EXTRACTION_MAX_RATIO: float = Field(
        default=0.5, description="章节提取内容最大比例（相对原文）"
    )
    KEYWORD_MATCH_THRESHOLD: int = Field(
        default=2, description="段落至少匹配的关键词数量"
    )
    KEEP_CONTEXT_PARAGRAPHS: bool = Field(
        default=True, description="提取时是否保留匹配段落的上下文"
    )
    CONTEXT_PARAGRAPHS_COUNT: int = Field(
        default=1, description="保留的上下文段落数量（前后各N段）"
    )

    class Config:
        """Pydantic配置：允许从.env读取并兼容大小写"""
        env_file = ".env"
        env_prefix = ""
        case_sensitive = False
        extra = "allow"

settings = Settings()


def print_config(config: Settings):
    """
    将当前配置项按人类可读格式输出到日志，方便排障。

    参数:
        config: Settings实例，通常为全局settings。
    """
    message = ""
    message += "\n=== Report Engine 配置 ===\n"
    message += f"LLM 模型: {config.REPORT_ENGINE_MODEL_NAME}\n"
    message += f"LLM Base URL: {config.REPORT_ENGINE_BASE_URL or '(默认)'}\n"
    message += f"最大内容长度: {config.MAX_CONTENT_LENGTH}\n"
    message += f"输出目录: {config.OUTPUT_DIR}\n"
    message += f"章节JSON目录: {config.CHAPTER_OUTPUT_DIR}\n"
    message += f"章节JSON最大尝试次数: {config.CHAPTER_JSON_MAX_ATTEMPTS}\n"
    message += f"整本IR目录: {config.DOCUMENT_IR_OUTPUT_DIR}\n"
    message += f"模板目录: {config.TEMPLATE_DIR}\n"
    message += f"API 超时时间: {config.API_TIMEOUT} 秒\n"
    message += f"最大重试间隔: {config.MAX_RETRY_DELAY} 秒\n"
    message += f"最大重试次数: {config.MAX_RETRIES}\n"
    message += f"日志文件: {config.LOG_FILE}\n"
    message += f"PDF 导出: {config.ENABLE_PDF_EXPORT}\n"
    message += f"图表样式: {config.CHART_STYLE}\n"
    message += f"LLM API Key: {'已配置' if config.REPORT_ENGINE_API_KEY else '未配置'}\n"
    message += f"报告压缩: {config.ENABLE_REPORT_COMPRESSION}\n"
    if config.ENABLE_REPORT_COMPRESSION:
        message += f"  摘要策略: {config.SUMMARY_STRATEGY}\n"
        message += f"  压缩率: {config.SUMMARY_COMPRESSION_RATIO:.0%}\n"
        message += f"  提取策略: {config.EXTRACTION_STRATEGY}\n"
    message += "=========================\n"
    logger.info(message)
