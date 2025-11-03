# -*- coding: utf-8 -*-
"""
微舆配置文件
"""

# ============================== 数据库配置 ==============================
# 配置这些值以连接到您的MySQL实例。
DB_HOST = "localhost"  # 例如："localhost" 或 "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "136528"
DB_NAME = "db"
DB_CHARSET = "utf8mb4"
# 我们也提供云数据库资源便捷配置，日均10w+数据，可免费申请，联系我们：670939375@qq.com
# NOTE：为进行数据合规性审查与服务升级，云数据库自2025年10月1日起暂停接收新的使用申请


# ============================== LLM配置 ==============================
# 使用本地Ollama服务，无需API密钥
# Ollama默认地址: http://localhost:11434/v1
# 请确保已安装并运行Ollama服务，可以使用 ollama serve 启动

# Ollama服务地址（如果使用自定义端口，请修改此地址）
OLLAMA_BASE_URL = "http://localhost:11434/v1"

# Insight Agent - 使用Ollama本地模型
INSIGHT_ENGINE_API_KEY = "ollama"  # Ollama不需要真正的key，这里只是占位符
INSIGHT_ENGINE_BASE_URL = OLLAMA_BASE_URL
INSIGHT_ENGINE_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改

# Media Agent - 使用Ollama本地模型
MEDIA_ENGINE_API_KEY = "ollama"
MEDIA_ENGINE_BASE_URL = OLLAMA_BASE_URL
MEDIA_ENGINE_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改

# Query Agent - 使用Ollama本地模型
QUERY_ENGINE_API_KEY = "ollama"
QUERY_ENGINE_BASE_URL = OLLAMA_BASE_URL
QUERY_ENGINE_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改

# Report Agent - 使用Ollama本地模型
REPORT_ENGINE_API_KEY = "ollama"
REPORT_ENGINE_BASE_URL = OLLAMA_BASE_URL
REPORT_ENGINE_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改

# Forum Host - 使用Ollama本地模型
FORUM_HOST_API_KEY = "ollama"
FORUM_HOST_BASE_URL = OLLAMA_BASE_URL
FORUM_HOST_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改

# SQL keyword Optimizer - 使用Ollama本地模型
KEYWORD_OPTIMIZER_API_KEY = "ollama"
KEYWORD_OPTIMIZER_BASE_URL = OLLAMA_BASE_URL
KEYWORD_OPTIMIZER_MODEL_NAME = "qwen3:0.6b"  # 请根据你本地Ollama安装的模型名称修改


# ============================== 网络工具配置 ==============================
# 注意：项目已支持本地搜索服务，以下API密钥为可选配置
# 如果不配置（设为None），系统将自动使用本地爬虫搜索服务

# Tavily API（可选，如果使用本地搜索则设为None）
# 申请地址：https://www.tavily.com/
TAVILY_API_KEY = None  # 使用本地搜索时设为None，使用Tavily API时填入你的密钥

# Bocha API（可选，如果使用本地搜索则设为None）
# 申请地址：https://open.bochaai.com/
BOCHA_WEB_SEARCH_API_KEY = None  # 使用本地搜索时设为None，使用Bocha API时填入你的密钥
