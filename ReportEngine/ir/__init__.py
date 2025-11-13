"""
Report Engine的可执行JSON契约(IR)定义与校验工具。

该模块暴露统一的Schema文本与校验器，供提示词、章节生成、
以及最终装订流程共同复用，确保从LLM到渲染的产物结构一致。
"""

from .schema import (
    IR_VERSION,
    CHAPTER_JSON_SCHEMA,
    CHAPTER_JSON_SCHEMA_TEXT,
    ALLOWED_BLOCK_TYPES,
    ALLOWED_INLINE_MARKS,
)
from .validator import IRValidator

__all__ = [
    "IR_VERSION",
    "CHAPTER_JSON_SCHEMA",
    "CHAPTER_JSON_SCHEMA_TEXT",
    "ALLOWED_BLOCK_TYPES",
    "ALLOWED_INLINE_MARKS",
    "IRValidator",
]
