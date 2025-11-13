"""
章节级JSON生成节点。

每个章节依据Markdown模板切片独立调用LLM，流式写入Raw文件，
完成后校验并落盘标准化JSON。该节点只负责“拿到合规章节”。
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple, Callable, Optional

from loguru import logger

from ..core import TemplateSection, ChapterStorage
from ..ir import ALLOWED_BLOCK_TYPES, ALLOWED_INLINE_MARKS, IRValidator
from ..prompts import (
    SYSTEM_PROMPT_CHAPTER_JSON,
    build_chapter_user_prompt,
)
from .base_node import BaseNode

try:
    from json_repair import repair_json as _json_repair_fn
except ImportError:  # pragma: no cover - optional dependency
    _json_repair_fn = None


class ChapterJsonParseError(ValueError):
    """章节LLM输出无法解析为合法JSON时抛出的异常，附带原始文本方便排查。"""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        super().__init__(message)
        self.raw_text = raw_text


class ChapterGenerationNode(BaseNode):
    """
    负责按章节调用LLM并校验JSON结构。

    核心能力：
        - 构造章节级 payload 与提示词；
        - 以流式形式写入 raw 文件并透传 delta；
        - 尝试修复/解析LLM输出，并使用 IRValidator 校验；
        - 对block结构做容错修复，确保最终JSON可渲染。
    """

    _COLON_EQUALS_PATTERN = re.compile(r'(":\s*)=')
    _LINE_BREAK_SENTINEL = "__LINE_BREAK__"
    _INLINE_MARK_ALIASES = {
        "strong": "bold",
        "b": "bold",
        "em": "italic",
        "emphasis": "italic",
        "i": "italic",
        "u": "underline",
        "strike-through": "strike",
        "strikethrough": "strike",
        "s": "strike",
        "codeblock": "code",
        "monospace": "code",
        "hyperlink": "link",
        "url": "link",
        "colour": "color",
        "textcolor": "color",
        "bgcolor": "highlight",
        "background": "highlight",
        "highlightcolor": "highlight",
        "sub": "subscript",
        "sup": "superscript",
    }

    def __init__(self, llm_client, validator: IRValidator, storage: ChapterStorage):
        """
        记录LLM客户端/校验器/章节存储器，便于run方法调度。

        Args:
            llm_client: 实际调用大模型的客户端
            validator: IR结构校验器
            storage: 负责章节流式落盘的存储器
        """
        super().__init__(llm_client, "ChapterGenerationNode")
        self.validator = validator
        self.storage = storage

    def run(
        self,
        section: TemplateSection,
        context: Dict[str, Any],
        run_dir: Path,
        stream_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """针对单个章节调用LLM，校验/落盘章节JSON并返回结构化结果"""
        chapter_meta = {
            "chapterId": section.chapter_id,
            "slug": section.slug,
            "title": section.title,
            "order": section.order,
        }
        chapter_dir = self.storage.begin_chapter(run_dir, chapter_meta)
        llm_payload = self._build_payload(section, context)
        user_message = build_chapter_user_prompt(llm_payload)

        raw_text = self._stream_llm(
            user_message,
            chapter_dir,
            stream_callback=stream_callback,
            section_meta=chapter_meta,
            **kwargs,
        )
        chapter_json = self._parse_chapter(raw_text)

        # 自动补全关键字段后再校验
        chapter_json.setdefault("chapterId", section.chapter_id)
        chapter_json.setdefault("anchor", section.slug)
        chapter_json.setdefault("title", section.title)
        chapter_json.setdefault("order", section.order)
        self._sanitize_chapter_blocks(chapter_json)

        valid, errors = self.validator.validate_chapter(chapter_json)
        self.storage.persist_chapter(
            run_dir,
            chapter_meta,
            chapter_json,
            errors=None if valid else errors,
        )

        if not valid:
            raise ValueError(
                f"{section.title} 章节JSON校验失败: {'; '.join(errors[:5])}"
            )

        return chapter_json

    # ====== 内部方法 ======

    def _build_payload(self, section: TemplateSection, context: Dict[str, Any]) -> Dict[str, Any]:
        """构造LLM输入payload"""
        reports = context.get("reports", {})
        # 章节篇幅规划（来自WordBudgetNode），用于指导字数与强调点
        chapter_plan_map = context.get("chapter_directives", {})
        chapter_plan = chapter_plan_map.get(section.chapter_id) if chapter_plan_map else {}
        payload = {
            "section": {
                "chapterId": section.chapter_id,
                "title": section.title,
                "slug": section.slug,
                "order": section.order,
                "number": section.number,
                "outline": section.outline,
            },
            "globalContext": {
                "query": context.get("query"),
                "templateName": context.get("template_name"),
                "themeTokens": context.get("theme_tokens", {}),
                "styleDirectives": context.get("style_directives", {}),
                # layout里包含标题/目录/hero等信息，方便章节保持统一视觉调性
                "layout": context.get("layout"),
                "templateOverview": context.get("template_overview", {}),
            },
            "reports": {
                "query_engine": reports.get("query_engine", ""),
                "media_engine": reports.get("media_engine", ""),
                "insight_engine": reports.get("insight_engine", ""),
            },
            "forumLogs": context.get("forum_logs", ""),
            "dataBundles": context.get("data_bundles", []),
            "constraints": {
                "language": "zh-CN",
                "maxTokens": context.get("max_tokens", 4096),
                "allowedBlocks": ALLOWED_BLOCK_TYPES,
                "styleHints": {
                    "expectWidgets": True,
                    "forceHeadingAnchors": True,
                    "allowInlineMix": True,
                },
            },
            "chapterPlan": chapter_plan,
            "wordPlan": context.get("word_plan"),
        }
        if chapter_plan:
            constraints = payload["constraints"]
            if chapter_plan.get("targetWords"):
                constraints["wordTarget"] = chapter_plan["targetWords"]
            if chapter_plan.get("minWords"):
                constraints["minWords"] = chapter_plan["minWords"]
            if chapter_plan.get("maxWords"):
                constraints["maxWords"] = chapter_plan["maxWords"]
            if chapter_plan.get("emphasis"):
                constraints["emphasis"] = chapter_plan["emphasis"]
            if chapter_plan.get("sections"):
                constraints["sectionBudgets"] = chapter_plan["sections"]
                payload["globalContext"]["sectionBudgets"] = chapter_plan["sections"]
        return payload

    def _stream_llm(
        self,
        user_message: str,
        chapter_dir: Path,
        stream_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        section_meta: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """流式调用LLM并实时写入raw文件，同时通过回调将delta抛出。"""
        chunks: List[str] = []
        with self.storage.capture_stream(chapter_dir) as stream_fp:
            stream = self.llm_client.stream_invoke(
                SYSTEM_PROMPT_CHAPTER_JSON,
                user_message,
                temperature=kwargs.get("temperature", 0.2),
                top_p=kwargs.get("top_p", 0.95),
            )
            for delta in stream:
                stream_fp.write(delta)
                chunks.append(delta)
                if stream_callback:
                    meta = section_meta or {}
                    try:
                        stream_callback(delta, meta)
                    except Exception as callback_error:  # pragma: no cover - 仅记录，不阻断主流程
                        logger.warning(f"章节流式回调失败: {callback_error}")
        return "".join(chunks)

    def _parse_chapter(self, raw_text: str) -> Dict[str, Any]:
        """清洗LLM输出并解析JSON"""
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("LLM返回空内容")

        candidate_payloads = [cleaned]
        repaired = self._repair_llm_json(cleaned)
        if repaired != cleaned:
            candidate_payloads.append(repaired)

        try:
            data = self._parse_with_candidates(candidate_payloads)
        except json.JSONDecodeError as exc:
            repaired_payload = self._attempt_json_repair(cleaned)
            if repaired_payload:
                candidate_payloads.append(repaired_payload)
                try:
                    data = self._parse_with_candidates(candidate_payloads[-1:])
                except json.JSONDecodeError as inner_exc:
                    raise ChapterJsonParseError(
                        f"章节JSON解析失败: {inner_exc}", raw_text=cleaned
                    ) from inner_exc
            else:
                raise ChapterJsonParseError(
                    f"章节JSON解析失败: {exc}", raw_text=cleaned
                ) from exc

        if "chapter" in data and isinstance(data["chapter"], dict):
            return data["chapter"]
        if isinstance(data, dict) and all(
            key in data for key in ("chapterId", "title", "blocks")
        ):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "chapter" in item and isinstance(item["chapter"], dict):
                        return item["chapter"]
                    if all(key in item for key in ("chapterId", "title", "blocks")):
                        return item
        raise ValueError("章节JSON缺少chapter字段")

    def _repair_llm_json(self, text: str) -> str:
        """处理常见的LLM错误（如\":=导致的非法JSON）"""
        repaired = text
        mutated = False

        new_text = self._COLON_EQUALS_PATTERN.sub(r"\1", repaired)
        if new_text != repaired:
            logger.warning("检测到章节JSON中的\":=\"字符，已自动移除多余的'='号")
            repaired = new_text
            mutated = True

        repaired, escaped = self._escape_in_string_controls(repaired)
        if escaped:
            logger.warning("检测到章节JSON字符串中存在未转义的控制字符，已自动转换为转义序列")
            mutated = True

        repaired, balanced = self._balance_brackets(repaired)
        if balanced:
            logger.warning("检测到章节JSON括号不平衡，已自动补齐/剔除异常括号")
            mutated = True

        repaired, commas_fixed = self._fix_missing_commas(repaired)
        if commas_fixed:
            logger.warning("检测到章节JSON对象/数组之间缺少逗号，已自动补齐")
            mutated = True

        return repaired if mutated else text

    def _escape_in_string_controls(self, text: str) -> Tuple[str, bool]:
        """
        将字符串字面量中的裸换行/制表符/控制字符替换为JSON合法的转义序列。
        """
        if not text:
            return text, False

        result: List[str] = []
        in_string = False
        escaped = False
        mutated = False
        control_map = {"\n": "\\n", "\r": "\\n", "\t": "\\t"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string and ch in control_map:
                result.append(control_map[ch])
                mutated = True
                continue

            if in_string and ord(ch) < 0x20:
                result.append(f"\\u{ord(ch):04x}")
                mutated = True
                continue

            result.append(ch)

        return "".join(result), mutated

    def _fix_missing_commas(self, text: str) -> Tuple[str, bool]:
        """在对象/数组连续出现时自动补逗号"""
        if not text:
            return text, False

        chars: List[str] = []
        mutated = False
        in_string = False
        escaped = False
        length = len(text)
        i = 0
        while i < length:
            ch = text[i]
            chars.append(ch)
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
                i += 1
                continue
            if not in_string and ch in "}]":
                j = i + 1
                while j < length and text[j] in " \t\r\n":
                    j += 1
                if j < length:
                    next_ch = text[j]
                    if next_ch in "{[":
                        chars.append(",")
                        mutated = True
            i += 1
        return "".join(chars), mutated

    def _balance_brackets(self, text: str) -> Tuple[str, bool]:
        """尝试修复因LLM多写/少写括号导致的不平衡结构"""
        if not text:
            return text, False

        result: List[str] = []
        stack: List[str] = []
        mutated = False
        in_string = False
        escaped = False

        opener_map = {"{": "}", "[": "]"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string:
                result.append(ch)
                continue

            if ch in "{[":
                stack.append(ch)
                result.append(ch)
                continue

            if ch in "}]":
                if stack and ((ch == "}" and stack[-1] == "{") or (ch == "]" and stack[-1] == "[")):
                    stack.pop()
                    result.append(ch)
                else:
                    mutated = True
                continue

            result.append(ch)

        while stack:
            opener = stack.pop()
            result.append(opener_map[opener])
            mutated = True

        return "".join(result), mutated

    def _attempt_json_repair(self, text: str) -> str | None:
        """使用可选的json_repair库进一步修复复杂语法错误"""
        if not _json_repair_fn:
            return None
        try:
            fixed = _json_repair_fn(text)
        except Exception as exc:  # pragma: no cover - library failure
            logger.warning(f"json_repair 修复章节JSON失败: {exc}")
            return None
        if fixed == text:
            return None
        logger.warning("已使用json_repair自动修复章节JSON语法")
        return fixed

    def _sanitize_chapter_blocks(self, chapter: Dict[str, Any]):
        """修正常见的结构性错误（例如list.items嵌套过深）"""

        def walk(blocks: List[Dict[str, Any]] | None):
            """递归检查并修复嵌套结构，保证每个block合法"""
            if not isinstance(blocks, list):
                return
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                self._ensure_block_type(block)
                self._sanitize_block_content(block)
                block_type = block.get("type")
                if block_type == "list":
                    items = block.get("items")
                    normalized = self._normalize_list_items(items)
                    if normalized:
                        block["items"] = normalized
                    for entry in block.get("items", []):
                        walk(entry)
                elif block_type in {"callout", "blockquote"}:
                    walk(block.get("blocks"))
                elif block_type == "table":
                    for row in block.get("rows", []):
                        cells = row.get("cells") or []
                        for cell in cells:
                            walk(cell.get("blocks"))
                elif block_type == "widget":
                    self._normalize_widget_block(block)
                else:
                    nested = block.get("blocks")
                    if isinstance(nested, list):
                        walk(nested)

        walk(chapter.get("blocks"))

    def _sanitize_block_content(self, block: Dict[str, Any]):
        """根据类型做精细化修复，例如清理paragraph内的非法inline mark"""
        block_type = block.get("type")
        if block_type == "paragraph":
            self._normalize_paragraph_block(block)

    def _normalize_paragraph_block(self, block: Dict[str, Any]):
        """将paragraph的inlines统一规整，剔除非法marks"""
        inlines = block.get("inlines")
        normalized_runs: List[Dict[str, Any]] = []
        if isinstance(inlines, list) and inlines:
            for run in inlines:
                normalized_runs.extend(self._coerce_inline_run(run))
        else:
            normalized_runs = [self._as_inline_run(self._extract_block_text(block))]
        if not normalized_runs:
            normalized_runs = [self._as_inline_run("")]
        block["inlines"] = normalized_runs

    def _coerce_inline_run(self, run: Any) -> List[Dict[str, Any]]:
        """将任意inline写法规整为合法run"""
        if isinstance(run, dict):
            normalized_run = dict(run)
            text = normalized_run.get("text")
            if not isinstance(text, str):
                text = "" if text is None else str(text)
            marks = normalized_run.get("marks")
            sanitized_marks, extra_text = self._sanitize_inline_marks(marks)
            normalized_run["marks"] = sanitized_marks
            normalized_run["text"] = (text or "") + extra_text
            return [normalized_run]
        if isinstance(run, str):
            return [self._as_inline_run(run)]
        if isinstance(run, (int, float)):
            return [self._as_inline_run(str(run))]
        if isinstance(run, list):
            normalized: List[Dict[str, Any]] = []
            for item in run:
                normalized.extend(self._coerce_inline_run(item))
            return normalized
        return [self._as_inline_run("" if run is None else str(run))]

    def _sanitize_inline_marks(self, marks: Any) -> Tuple[List[Dict[str, Any]], str]:
        """过滤非法marks并将break类控制符转成文本"""
        text_suffix = ""
        if marks is None:
            return [], text_suffix
        mark_list = marks if isinstance(marks, list) else [marks]
        sanitized: List[Dict[str, Any]] = []
        for mark in mark_list:
            normalized_mark, extra_text = self._normalize_inline_mark(mark)
            if normalized_mark:
                sanitized.append(normalized_mark)
            if extra_text:
                text_suffix += extra_text
        return sanitized, text_suffix

    def _normalize_inline_mark(self, mark: Any) -> Tuple[Dict[str, Any] | None, str]:
        """对单个mark做兼容映射，或者在必要时转换为文本"""
        if not isinstance(mark, dict):
            return None, ""
        canonical_type = self._canonical_inline_mark_type(mark.get("type"))
        if canonical_type == self._LINE_BREAK_SENTINEL:
            return None, "\n"
        if canonical_type in ALLOWED_INLINE_MARKS:
            normalized = dict(mark)
            normalized["type"] = canonical_type
            return normalized, ""
        return None, ""

    def _canonical_inline_mark_type(self, mark_type: Any) -> str | None:
        """将mark type映射为Schema所支持的取值"""
        if not isinstance(mark_type, str):
            return None
        normalized = mark_type.strip()
        if not normalized:
            return None
        lowered = normalized.lower()
        if lowered in {"break", "linebreak", "br"}:
            return self._LINE_BREAK_SENTINEL
        return self._INLINE_MARK_ALIASES.get(lowered, lowered)

    def _extract_block_text(self, block: Dict[str, Any]) -> str:
        """优先从text/content等字段提取fallback文本"""
        for key in ("text", "content", "value", "title"):
            value = block.get(key)
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
        return ""

    def _normalize_list_items(self, items: Any) -> List[List[Dict[str, Any]]]:
        """确保list block的items为[[block, block], ...]结构"""
        if not isinstance(items, list):
            return []
        normalized: List[List[Dict[str, Any]]] = []
        for item in items:
            normalized.extend(self._coerce_list_item(item))
        return [entry for entry in normalized if entry]

    def _coerce_list_item(self, item: Any) -> List[List[Dict[str, Any]]]:
        """将各种嵌套写法统一折算为区块数组"""
        result: List[List[Dict[str, Any]]] = []
        if isinstance(item, dict):
            self._ensure_block_type(item)
            result.append([item])
            return result
        if isinstance(item, list):
            dicts = [elem for elem in item if isinstance(elem, dict)]
            if dicts:
                for elem in dicts:
                    self._ensure_block_type(elem)
                result.append(dicts)
            for elem in item:
                if isinstance(elem, list):
                    result.extend(self._coerce_list_item(elem))
                elif isinstance(elem, dict):
                    continue
                elif isinstance(elem, str):
                    result.append([self._as_paragraph_block(elem)])
                elif isinstance(elem, (int, float)):
                    result.append([self._as_paragraph_block(str(elem))])
        elif isinstance(item, str):
            result.append([self._as_paragraph_block(item)])
        elif isinstance(item, (int, float)):
            result.append([self._as_paragraph_block(str(item))])
        return result

    def _normalize_widget_block(self, block: Dict[str, Any]):
        """确保widget具备顶层data或dataRef"""
        has_data = block.get("data") is not None or block.get("dataRef") is not None
        if has_data:
            return
        props = block.get("props")
        if isinstance(props, dict) and "data" in props:
            block["data"] = props.pop("data")
            return
        block["data"] = {"labels": [], "datasets": []}

    def _ensure_block_type(self, block: Dict[str, Any]):
        """若block缺少合法type，则降级为paragraph"""
        block_type = block.get("type")
        if isinstance(block_type, str) and block_type in ALLOWED_BLOCK_TYPES:
            return
        text = ""
        for key in ("text", "content", "title"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        if not text:
            try:
                text = json.dumps(block, ensure_ascii=False)
            except Exception:
                text = str(block)
        block.clear()
        block["type"] = "paragraph"
        block["inlines"] = [self._as_inline_run(text)]

    @staticmethod
    def _as_paragraph_block(text: str) -> Dict[str, Any]:
        """将字符串快速包装成paragraph block，方便统一处理"""
        return {
            "type": "paragraph",
            "inlines": [ChapterGenerationNode._as_inline_run(text)],
        }

    @staticmethod
    def _as_inline_run(text: str) -> Dict[str, Any]:
        """构造基础inline run，保证marks字段存在"""
        return {"text": text or "", "marks": []}

    @staticmethod
    def _parse_with_candidates(payloads: List[str]) -> Dict[str, Any]:
        """按顺序尝试多个payload，直到解析成功"""
        last_exc: json.JSONDecodeError | None = None
        for payload in payloads:
            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc


__all__ = ["ChapterGenerationNode", "ChapterJsonParseError"]
