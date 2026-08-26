"""
Deep Search Agent
一个无框架的深度搜索AI代理实现
"""

from .agent import (
    AnspireSearchAgent,
    DeepSearchAgent,
    XquikSearchAgent,
    create_agent,
)
from .utils.config import Settings

__version__ = "1.0.0"
__author__ = "Deep Search Agent Team"

__all__ = [
    "DeepSearchAgent",
    "AnspireSearchAgent",
    "XquikSearchAgent",
    "create_agent",
    "Settings",
]
