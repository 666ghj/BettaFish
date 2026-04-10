"""
Prompt模块
定义Deep Search Agent各个阶段使用的系统提示词
"""

from .prompts import (
    SYSTEM_PROMPT_REPORT_STRUCTURE,
    SYSTEM_PROMPT_FIRST_SEARCH,
    SYSTEM_PROMPT_FIRST_SUMMARY,
    SYSTEM_PROMPT_REFLECTION,
    SYSTEM_PROMPT_REFLECTION_SUMMARY,
    SYSTEM_PROMPT_REPORT_FORMATTING,
    output_schema_report_structure,
    output_schema_first_search,
    output_schema_first_summary,
    output_schema_reflection,
    output_schema_reflection_summary,
    input_schema_report_formatting,
    build_first_search_prompt,
    build_reflection_prompt,
)

__all__ = [
    "SYSTEM_PROMPT_REPORT_STRUCTURE",
    "SYSTEM_PROMPT_FIRST_SEARCH", 
    "SYSTEM_PROMPT_FIRST_SUMMARY",
    "SYSTEM_PROMPT_REFLECTION",
    "SYSTEM_PROMPT_REFLECTION_SUMMARY",
    "SYSTEM_PROMPT_REPORT_FORMATTING",
    "output_schema_report_structure",
    "output_schema_first_search",
    "output_schema_first_summary", 
    "output_schema_reflection",
    "output_schema_reflection_summary",
    "input_schema_report_formatting",
    "build_first_search_prompt",
    "build_reflection_prompt",
]
