"""
Report Engine核心工具集合。

该包封装了模板切片、章节存储与章节装订三大基础能力，
所有上层节点都会复用这些工具保证结构一致。
"""

from .template_parser import TemplateSection, parse_template_sections
from .chapter_storage import ChapterStorage
from .stitcher import DocumentComposer

__all__ = [
    "TemplateSection",
    "parse_template_sections",
    "ChapterStorage",
    "DocumentComposer",
]
