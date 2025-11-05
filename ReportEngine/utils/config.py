"""
Configuration management module for the Report Engine.
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
    MAX_CONTENT_LENGTH: int = Field(200000, description="最大内容长度")
    OUTPUT_DIR: str = Field("final_reports", description="主输出目录")
    TEMPLATE_DIR: str = Field("ReportEngine/report_template", description="多模板目录")
    API_TIMEOUT: float = Field(900.0, description="单API超时时间（秒）")
    MAX_RETRY_DELAY: float = Field(180.0, description="最大重试间隔（秒）")
    MAX_RETRIES: int = Field(8, description="最大重试次数")
    LOG_FILE: str = Field("logs/report.log", description="日志输出文件")
    ENABLE_PDF_EXPORT: bool = Field(True, description="是否允许导出PDF")
    CHART_STYLE: str = Field("modern", description="图表样式：modern/classic/")

    class Config:
        env_file = ".env"
        env_prefix = ""
        case_sensitive = False
        extra = "allow"

settings = Settings()


def print_config(config: Settings):
    message = ""
    message += "\n=== Report Engine 配置 ===\n"
    message += f"LLM 模型: {config.REPORT_ENGINE_MODEL_NAME}\n"
    message += f"LLM Base URL: {config.REPORT_ENGINE_BASE_URL or '(默认)'}\n"
    message += f"最大内容长度: {config.MAX_CONTENT_LENGTH}\n"
    message += f"输出目录: {config.OUTPUT_DIR}\n"
    message += f"模板目录: {config.TEMPLATE_DIR}\n"
    message += f"API 超时时间: {config.API_TIMEOUT} 秒\n"
    message += f"最大重试间隔: {config.MAX_RETRY_DELAY} 秒\n"
    message += f"最大重试次数: {config.MAX_RETRIES}\n"
    message += f"日志文件: {config.LOG_FILE}\n"
    message += f"PDF 导出: {config.ENABLE_PDF_EXPORT}\n"
    message += f"图表样式: {config.CHART_STYLE}\n"
    message += f"LLM API Key: {'已配置' if config.REPORT_ENGINE_API_KEY else '未配置'}\n"
    message += "=========================\n"
    logger.info(message)
