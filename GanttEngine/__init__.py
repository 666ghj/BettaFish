"""
GanttEngine - 甘特图生成引擎

从Excel文件读取项目任务数据，自动生成交互式甘特图
"""

from .excel_parser import ExcelParser
from .gantt_generator import GanttGenerator
from .flask_interface import create_gantt_routes

__version__ = "1.0.0"
__all__ = ["ExcelParser", "GanttGenerator", "create_gantt_routes"]
