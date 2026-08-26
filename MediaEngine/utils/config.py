"""
Configuration management module for the Media Engine (pydantic_settings style).
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Literal


# 计算 .env 优先级：优先当前工作目录，其次项目根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CWD_ENV: Path = Path.cwd() / ".env"
ENV_FILE: str = str(CWD_ENV if CWD_ENV.exists() else (PROJECT_ROOT / ".env"))

class Settings(BaseSettings):
    """
    全局配置；支持 .env 和环境变量自动加载。
    变量名与原 config.py 大写一致，便于平滑过渡。
    """
    # ====================== 数据库配置 ======================
    DB_HOST: str = Field("your_db_host", description="数据库主机，例如localhost 或 127.0.0.1。我们也提供云数据库资源便捷配置，日均10w+数据，可免费申请，联系我们：670939375@qq.com NOTE：为进行数据合规性审查与服务升级，云数据库自2025年10月1日起暂停接收新的使用申请")
    DB_PORT: int = Field(3306, description="数据库端口号，默认为3306")
    DB_USER: str = Field("your_db_user", description="数据库用户名")
    DB_PASSWORD: str = Field("your_db_password", description="数据库密码")
    DB_NAME: str = Field("your_db_name", description="数据库名称")
    DB_CHARSET: str = Field("utf8mb4", description="数据库字符集，推荐utf8mb4，兼容emoji")
    DB_DIALECT: str = Field("mysql", description="数据库类型，例如 'mysql' 或 'postgresql'。用于支持多种数据库后端（如 SQLAlchemy，请与连接信息共同配置）")

    # ======================= LLM 相关 =======================
    INSIGHT_ENGINE_API_KEY: Optional[str] = Field(None, description="Insight Agent（推荐Kimi，https://platform.moonshot.cn/）API密钥，用于主LLM。您可以更改每个部分LLM使用的API，🚩只要兼容OpenAI请求格式都可以，定义好KEY、BASE_URL与MODEL_NAME即可正常使用。重要提醒：我们强烈推荐您先使用推荐的配置申请API，先跑通再进行您的更改！")
    INSIGHT_ENGINE_BASE_URL: Optional[str] = Field("https://api.moonshot.cn/v1", description="Insight Agent LLM接口BaseUrl，可自定义厂商API")
    INSIGHT_ENGINE_MODEL_NAME: str = Field("kimi-k2-0711-preview", description="Insight Agent LLM模型名称，如kimi-k2-0711-preview")
    
    MEDIA_ENGINE_API_KEY: Optional[str] = Field(None, description="Media Agent（推荐Gemini，这里我用了一个中转厂商，你也可以换成你自己的，申请地址：https://www.chataiapi.com/）API密钥")
    MEDIA_ENGINE_BASE_URL: Optional[str] = Field("https://www.chataiapi.com/v1", description="Media Agent LLM接口BaseUrl")
    MEDIA_ENGINE_MODEL_NAME: str = Field("gemini-2.5-pro", description="Media Agent LLM模型名称，如gemini-2.5-pro")
    
    BOCHA_WEB_SEARCH_API_KEY: Optional[str] = Field(None, description="Bocha Web Search API Key")
    BOCHA_API_KEY: Optional[str] = Field(None, description="Bocha 兼容键（别名）")
    
    SEARCH_TIMEOUT: int = Field(240, description="搜索超时（秒）")
    SEARCH_CONTENT_MAX_LENGTH: int = Field(20000, description="用于提示的最长内容长度")
    MAX_REFLECTIONS: int = Field(2, description="最大反思轮数")
    MAX_PARAGRAPHS: int = Field(5, description="最大段落数")
    
    MINDSPIDER_API_KEY: Optional[str] = Field(None, description="MindSpider API密钥")
    MINDSPIDER_BASE_URL: Optional[str] = Field("https://api.deepseek.com", description="MindSpider LLM接口BaseUrl")
    MINDSPIDER_MODEL_NAME: str = Field("deepseek-reasoner", description="MindSpider LLM模型名称，如deepseek-reasoner")
    
    OUTPUT_DIR: str = Field("reports", description="输出目录")
    SAVE_INTERMEDIATE_STATES: bool = Field(True, description="是否保存中间状态")

    
    QUERY_ENGINE_API_KEY: Optional[str] = Field(None, description="Query Agent（推荐DeepSeek，https://www.deepseek.com/）API密钥")
    QUERY_ENGINE_BASE_URL: Optional[str] = Field("https://api.deepseek.com", description="Query Agent LLM接口BaseUrl")
    QUERY_ENGINE_MODEL_NAME: str = Field("deepseek-reasoner", description="Query Agent LLM模型，如deepseek-reasoner")
    
    REPORT_ENGINE_API_KEY: Optional[str] = Field(None, description="Report Agent（推荐Gemini，这里我用了一个中转厂商，你也可以换成你自己的，申请地址：https://www.chataiapi.com/）API密钥")
    REPORT_ENGINE_BASE_URL: Optional[str] = Field("https://www.chataiapi.com/v1", description="Report Agent LLM接口BaseUrl")
    REPORT_ENGINE_MODEL_NAME: str = Field("gemini-2.5-pro", description="Report Agent LLM模型，如gemini-2.5-pro")
    
    FORUM_HOST_API_KEY: Optional[str] = Field(None, description="Forum Host（Qwen3最新模型，这里我使用了硅基流动这个平台，申请地址：https://cloud.siliconflow.cn/）API密钥")
    FORUM_HOST_BASE_URL: Optional[str] = Field("https://api.siliconflow.cn/v1", description="Forum Host LLM BaseUrl")
    FORUM_HOST_MODEL_NAME: str = Field("Qwen/Qwen3-235B-A22B-Instruct-2507", description="Forum Host LLM模型名，如Qwen/Qwen3-235B-A22B-Instruct-2507")
    
    KEYWORD_OPTIMIZER_API_KEY: Optional[str] = Field(None, description="SQL keyword Optimizer（小参数Qwen3模型，这里我使用了硅基流动这个平台，申请地址：https://cloud.siliconflow.cn/）API密钥")
    KEYWORD_OPTIMIZER_BASE_URL: Optional[str] = Field("https://api.siliconflow.cn/v1", description="Keyword Optimizer BaseUrl")
    KEYWORD_OPTIMIZER_MODEL_NAME: str = Field("Qwen/Qwen3-30B-A3B-Instruct-2507", description="Keyword Optimizer LLM模型名称，如Qwen/Qwen3-30B-A3B-Instruct-2507")

    # ================== 网络工具配置 ====================
    TAVILY_API_KEY: Optional[str] = Field(None, description="Tavily API（申请地址：https://www.tavily.com/）API密钥，用于Tavily网络搜索")
    
    SEARCH_TOOL_TYPE: Literal["AnspireAPI", "BochaAPI", "XquikAPI"] = Field("AnspireAPI", description="网络搜索工具类型，支持AnspireAPI、BochaAPI或XquikAPI，默认为AnspireAPI")
    BOCHA_BASE_URL: Optional[str] = Field("https://api.bochaai.com/v1/ai-search", description="Bocha AI 搜索BaseUrl或博查网页搜索BaseUrl")
    BOCHA_WEB_SEARCH_API_KEY: Optional[str] = Field(None, description="Bocha API（申请地址：https://open.bochaai.com/）API密钥，用于Bocha搜索")
    # Anspire AI Search API（申请地址：https://open.anspire.cn/）
    ANSPIRE_BASE_URL: Optional[str] = Field("https://plugin.anspire.cn/api/ntsearch/search", description="Anspire AI 搜索BaseUrl")
    ANSPIRE_API_KEY: Optional[str] = Field(None, description="Anspire AI Search API（申请地址：https://open.anspire.cn/）API密钥，用于Anspire搜索")
    # Xquik Tweet Search API（申请地址：https://xquik.com）
    XQUIK_BASE_URL: Optional[str] = Field("https://xquik.com/api/v1/x/tweets/search", description="Xquik Tweet 搜索BaseUrl")
    XQUIK_API_KEY: Optional[str] = Field(None, description="Xquik API密钥，用于X/Twitter帖子搜索")

    class Config:
        env_file = ENV_FILE
        env_prefix = ""
        case_sensitive = False
        extra = "allow"


settings = Settings()
