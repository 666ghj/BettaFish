"""
Report Engine渲染器集合。

目前仅提供 HTMLRenderer，未来可扩展为PDF/Markdown等输出。
"""

from .html_renderer import HTMLRenderer

__all__ = ["HTMLRenderer"]
