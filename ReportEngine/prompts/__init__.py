"""
Report Engine提示词模块
定义报告生成各个阶段使用的系统提示词
"""

from .prompts import (
    SYSTEM_PROMPT_TEMPLATE_SELECTION,
    SYSTEM_PROMPT_HTML_GENERATION,
    SYSTEM_PROMPT_CHAPTER_JSON,
    SYSTEM_PROMPT_DOCUMENT_LAYOUT,
    SYSTEM_PROMPT_WORD_BUDGET,
    output_schema_template_selection,
    input_schema_html_generation,
    chapter_generation_input_schema,
    build_chapter_user_prompt,
    build_document_layout_prompt,
    build_word_budget_prompt,
)

__all__ = [
    "SYSTEM_PROMPT_TEMPLATE_SELECTION",
    "SYSTEM_PROMPT_HTML_GENERATION",
    "SYSTEM_PROMPT_CHAPTER_JSON",
    "SYSTEM_PROMPT_DOCUMENT_LAYOUT",
    "SYSTEM_PROMPT_WORD_BUDGET",
    "output_schema_template_selection",
    "input_schema_html_generation",
    "chapter_generation_input_schema",
    "build_chapter_user_prompt",
    "build_document_layout_prompt",
    "build_word_budget_prompt",
]
