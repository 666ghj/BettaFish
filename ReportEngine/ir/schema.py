"""
Report Engine JSON契约（IR）Schema定义。

这里集中维护所有章节级别的Schema与可用于提示词的文本表示，
确保章节生成、校验与渲染对同一个结构有统一认知。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

IR_VERSION = "1.0"

# ====== 基础常量 ======
ALLOWED_INLINE_MARKS: List[str] = [
    "bold",
    "italic",
    "underline",
    "strike",
    "code",
    "link",
    "color",
    "font",
    "highlight",
    "subscript",
    "superscript",
    "math",
]

ALLOWED_BLOCK_TYPES: List[str] = [
    "heading",
    "paragraph",
    "list",
    "table",
    "blockquote",
    "hr",
    "code",
    "math",
    "figure",
    "callout",
    "kpiGrid",
    "widget",
    "toc",
]

# ====== Schema定义 ======
inline_mark_schema: Dict[str, Any] = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"type": "string", "enum": ALLOWED_INLINE_MARKS},
        "value": {"type": ["string", "number", "object"]},
        "href": {"type": "string", "format": "uri-reference"},
        "title": {"type": "string"},
        "style": {"type": "object"},
    },
    "additionalProperties": True,
}

inline_run_schema: Dict[str, Any] = {
    "type": "object",
    "required": ["text"],
    "properties": {
        "text": {"type": "string"},
        "marks": {
            "type": "array",
            "items": {"$ref": "#/definitions/inlineMark"},
        },
    },
    "additionalProperties": True,
}

heading_block: Dict[str, Any] = {
    "title": "HeadingBlock",
    "type": "object",
    "properties": {
        "type": {"const": "heading"},
        "level": {"type": "integer", "minimum": 1, "maximum": 6},
        "text": {"type": "string"},
        "anchor": {"type": "string"},
        "numbering": {"type": "string"},
        "subtitle": {"type": "string"},
    },
    "required": ["type", "level", "text", "anchor"],
    "additionalProperties": True,
}

paragraph_block: Dict[str, Any] = {
    "title": "ParagraphBlock",
    "type": "object",
    "properties": {
        "type": {"const": "paragraph"},
        "inlines": {
            "type": "array",
            "items": {"$ref": "#/definitions/inlineRun"},
        },
        "align": {"type": "string", "enum": ["left", "center", "right", "justify"]},
    },
    "required": ["type", "inlines"],
    "additionalProperties": True,
}

list_block: Dict[str, Any] = {
    "title": "ListBlock",
    "type": "object",
    "properties": {
        "type": {"const": "list"},
        "listType": {"type": "string", "enum": ["ordered", "bullet", "task"]},
        "items": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"$ref": "#/definitions/block"},
            },
        },
    },
    "required": ["type", "listType", "items"],
    "additionalProperties": True,
}

table_block: Dict[str, Any] = {
    "title": "TableBlock",
    "type": "object",
    "properties": {
        "type": {"const": "table"},
        "colgroup": {"type": "array", "items": {"type": "object"}},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cells": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rowspan": {"type": "integer", "minimum": 1},
                                "colspan": {"type": "integer", "minimum": 1},
                                "align": {
                                    "type": "string",
                                    "enum": ["left", "center", "right"],
                                },
                                "blocks": {
                                    "type": "array",
                                    "items": {"$ref": "#/definitions/block"},
                                },
                            },
                            "required": ["blocks"],
                            "additionalProperties": True,
                        },
                    }
                },
                "required": ["cells"],
                "additionalProperties": True,
            },
        },
        "caption": {"type": "string"},
        "zebra": {"type": "boolean"},
    },
    "required": ["type", "rows"],
    "additionalProperties": True,
}

blockquote_block: Dict[str, Any] = {
    "title": "BlockquoteBlock",
    "type": "object",
    "properties": {
        "type": {"const": "blockquote"},
        "blocks": {
            "type": "array",
            "items": {"$ref": "#/definitions/block"},
        },
        "variant": {"type": "string"},
    },
    "required": ["type", "blocks"],
    "additionalProperties": True,
}

hr_block: Dict[str, Any] = {
    "title": "HorizontalRuleBlock",
    "type": "object",
    "properties": {
        "type": {"const": "hr"},
        "variant": {"type": "string"},
    },
    "required": ["type"],
    "additionalProperties": True,
}

code_block: Dict[str, Any] = {
    "title": "CodeBlock",
    "type": "object",
    "properties": {
        "type": {"const": "code"},
        "lang": {"type": "string"},
        "content": {"type": "string"},
        "caption": {"type": "string"},
    },
    "required": ["type", "content"],
    "additionalProperties": True,
}

math_block: Dict[str, Any] = {
    "title": "MathBlock",
    "type": "object",
    "properties": {
        "type": {"const": "math"},
        "latex": {"type": "string"},
        "displayMode": {"type": "boolean"},
    },
    "required": ["type", "latex"],
    "additionalProperties": True,
}

figure_block: Dict[str, Any] = {
    "title": "FigureBlock",
    "type": "object",
    "properties": {
        "type": {"const": "figure"},
        "img": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "alt": {"type": "string"},
                "width": {"type": "number"},
                "height": {"type": "number"},
                "srcset": {"type": "string"},
            },
            "required": ["src"],
            "additionalProperties": True,
        },
        "caption": {"type": "string"},
        "responsive": {"type": "boolean"},
    },
    "required": ["type", "img"],
    "additionalProperties": True,
}

callout_block: Dict[str, Any] = {
    "title": "CalloutBlock",
    "type": "object",
    "properties": {
        "type": {"const": "callout"},
        "tone": {
            "type": "string",
            "enum": ["info", "warning", "success", "danger"],
        },
        "title": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {"$ref": "#/definitions/block"},
        },
    },
    "required": ["type", "tone", "blocks"],
    "additionalProperties": True,
}

kpi_block: Dict[str, Any] = {
    "title": "KPIGridBlock",
    "type": "object",
    "properties": {
        "type": {"const": "kpiGrid"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "delta": {"type": "string"},
                    "deltaTone": {"type": "string", "enum": ["up", "down", "neutral"]},
                },
                "required": ["label", "value"],
                "additionalProperties": True,
            },
        },
        "cols": {"type": "integer"},
    },
    "required": ["type", "items"],
    "additionalProperties": True,
}

widget_block: Dict[str, Any] = {
    "title": "WidgetBlock",
    "type": "object",
    "properties": {
        "type": {"const": "widget"},
        "widgetId": {"type": "string"},
        "widgetType": {"type": "string"},
        "props": {"type": "object"},
        "data": {"type": "object"},
        "dataRef": {"type": "string"},
    },
    "required": ["type", "widgetId", "widgetType"],
    "additionalProperties": True,
}

toc_block: Dict[str, Any] = {
    "title": "TOCBlock",
    "type": "object",
    "properties": {
        "type": {"const": "toc"},
        "depth": {"type": "integer", "minimum": 1, "maximum": 4},
        "autoNumbering": {"type": "boolean"},
    },
    "required": ["type"],
    "additionalProperties": True,
}

block_variants: List[Dict[str, Any]] = [
    heading_block,
    paragraph_block,
    list_block,
    table_block,
    blockquote_block,
    hr_block,
    code_block,
    math_block,
    figure_block,
    callout_block,
    kpi_block,
    widget_block,
    toc_block,
]

CHAPTER_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ReportEngineChapterIR",
    "type": "object",
    "required": ["chapterId", "title", "anchor", "order", "blocks"],
    "properties": {
        "chapterId": {"type": "string"},
        "anchor": {"type": "string"},
        "title": {"type": "string"},
        "order": {"type": "number"},
        "summary": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {"$ref": "#/definitions/block"},
        },
        "xrefs": {"type": "object"},
        "widgets": {"type": "array", "items": {"type": "string"}},
        "footnotes": {"type": "array", "items": {"type": "object"}},
        "errors": {"type": "array", "items": {"type": "string"}},
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
    "definitions": {
        "inlineMark": inline_mark_schema,
        "inlineRun": inline_run_schema,
        "block": {"oneOf": block_variants},
    },
}

CHAPTER_JSON_SCHEMA_TEXT: str = json.dumps(
    CHAPTER_JSON_SCHEMA,
    ensure_ascii=False,
    indent=2,
)

__all__ = [
    "IR_VERSION",
    "ALLOWED_INLINE_MARKS",
    "ALLOWED_BLOCK_TYPES",
    "CHAPTER_JSON_SCHEMA",
    "CHAPTER_JSON_SCHEMA_TEXT",
]
