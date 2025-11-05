"""
Report Engine
一个智能报告生成AI代理实现
基于三个子agent的输出和论坛日志生成综合HTML报告
"""

from .agent import ReportAgent, create_agent

__version__ = "1.0.0"
__author__ = "Report Engine Team"

__all__ = ["ReportAgent", "create_agent"]
