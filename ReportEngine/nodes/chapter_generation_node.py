"""
章节级JSON生成节点。

每个章节依据Markdown模板切片独立调用LLM，流式写入Raw文件，
完成后校验并落盘标准化JSON。该节点只负责“拿到合规章节”。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple, Callable, Optional, Set

from loguru import logger

from ..core import TemplateSection, ChapterStorage
from ..ir import ALLOWED_BLOCK_TYPES, ALLOWED_INLINE_MARKS, IRValidator
from ..prompts import (
    SYSTEM_PROMPT_CHAPTER_JSON,
    SYSTEM_PROMPT_CHAPTER_JSON_REPAIR,
    SYSTEM_PROMPT_CHAPTER_JSON_RECOVERY,
    build_chapter_repair_prompt,
    build_chapter_recovery_payload,
    build_chapter_user_prompt,
)
from ..utils.json_parser import RobustJSONParser, JSONParseError
from .base_node import BaseNode

try:
    from json_repair import repair_json as _json_repair_fn
except ImportError:  # pragma: no cover - 可选依赖
    _json_repair_fn = None


class ChapterJsonParseError(ValueError):
    """章节LLM输出无法解析为合法JSON时抛出的异常，附带原始文本方便排查。"""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        """
        构造异常并附加原始输出，便于日志中定位。

        Args:
            message: 人类可读的错误描述。
            raw_text: 触发异常的完整LLM输出。
        """
        super().__init__(message)
        self.raw_text = raw_text


class ChapterContentError(ValueError):
    """
    章节内容稀疏异常。

    当LLM仅输出标题或正文不足以支撑一章时触发，驱动重试以保证报告质量。
    """

    def __init__(
        self,
        message: str,
        chapter: Optional[Dict[str, Any]] = None,
        body_characters: int = 0,
        narrative_characters: int = 0,
        non_heading_blocks: int = 0,
    ):
        """保存本次异常的正文特征，供重试与兜底策略参考。"""
        super().__init__(message)
        self.chapter_payload: Optional[Dict[str, Any]] = chapter
        self.body_characters: int = int(body_characters or 0)
        self.narrative_characters: int = int(narrative_characters or 0)
        self.non_heading_blocks: int = int(non_heading_blocks or 0)


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
    # 章节若仅包含标题或字符过少则视为失败，强制LLM重新生成
    _MIN_NON_HEADING_BLOCKS = 2
    _MIN_BODY_CHARACTERS = 600
    _MIN_NARRATIVE_CHARACTERS = 300
    _PARAGRAPH_FRAGMENT_MAX_CHARS = 80
    _PARAGRAPH_FRAGMENT_NO_TERMINATOR_MAX_CHARS = 240
    _TERMINATION_PUNCTUATION = set("。！？!?；;……")

    def __init__(
        self,
        llm_client,
        validator: IRValidator,
        storage: ChapterStorage,
        fallback_llm_clients: Optional[List[Tuple[str, Any]]] = None,
        error_log_dir: Optional[str | Path] = None,
    ):
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
        self.fallback_llm_clients: List[Tuple[str, Any]] = fallback_llm_clients or [
            ("report_engine", llm_client)
        ]
        error_dir = Path(error_log_dir or "logs/json_repair_failures")
        error_dir.mkdir(parents=True, exist_ok=True)
        self.error_log_dir = error_dir
        self._failed_block_counter = 0
        self._active_run_id: Optional[str] = None
        self._rescue_attempted_labels: Dict[str, Set[str]] = {}
        self._skipped_placeholder_chapters: Set[str] = set()
        self._archived_failed_json: Dict[str, str] = {}
        # 兜底使用更鲁棒的JSON解析器，尽可能拆出合法块
        self._robust_parser = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,
        )

    def run(
        self,
        section: TemplateSection,
        context: Dict[str, Any],
        run_dir: Path,
        stream_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        针对单个章节调用LLM，校验/落盘章节JSON并返回结构化结果。

        参数:
            section: 模板切片生成的章节对象，包含标题/顺序/slug。
            context: Agent构造的共享上下文（主题、篇幅、布局等）。
            run_dir: 章节存盘目录，由 `ChapterStorage.start_session` 返回。
            stream_callback: 可选流式回调，将LLM delta 推送给前端。
            **kwargs: 透传温度、top_p等采样参数。

        返回:
            dict: 通过IR校验的章节JSON。

        异常:
            ChapterJsonParseError: 多次尝试后仍无法解析合法JSON。
            ChapterContentError: 正文密度不足或只有标题，需要触发重试。
        """
        chapter_meta = {
            "chapterId": section.chapter_id,
            "slug": section.slug,
            "title": section.title,
            "order": section.order,
        }
        chapter_dir = self.storage.begin_chapter(run_dir, chapter_meta)
        run_id = run_dir.name
        self._ensure_run_state(run_id)
        llm_payload = self._build_payload(section, context)
        user_message = build_chapter_user_prompt(llm_payload)

        raw_text = self._stream_llm(
            user_message,
            chapter_dir,
            stream_callback=stream_callback,
            section_meta=chapter_meta,
            **kwargs,
        )
        parse_context: List[str] = []
        placeholder_created = False
        try:
            chapter_json = self._parse_chapter(raw_text)
        except ChapterJsonParseError as parse_error:
            logger.warning(f"{section.title} 章节JSON解析失败，尝试跨引擎修复: {parse_error}")
            parse_context.append(str(parse_error))
            self._archive_failed_output(section, raw_text)
            recovered = self._attempt_cross_engine_json_rescue(
                section,
                llm_payload,
                raw_text,
                run_id,
            )
            if recovered:
                chapter_json = recovered
                logger.info(f"{section.title} 章节JSON已通过跨引擎修复")
            else:
                placeholder = self._build_placeholder_chapter(section, raw_text, parse_error)
                if not placeholder:
                    raise
                chapter_json, placeholder_notes = placeholder
                parse_context.extend(placeholder_notes)
                placeholder_created = True

        # 自动补全关键字段后再校验
        chapter_json.setdefault("chapterId", section.chapter_id)
        chapter_json.setdefault("anchor", section.slug)
        chapter_json.setdefault("title", section.title)
        chapter_json.setdefault("order", section.order)
        self._sanitize_chapter_blocks(chapter_json)

        valid, errors = self.validator.validate_chapter(chapter_json)
        if not valid and errors:
            repaired = self._attempt_llm_structural_repair(
                chapter_json,
                errors,
                raw_text=raw_text,
            )
            if repaired:
                chapter_json = repaired
                chapter_json.setdefault("chapterId", section.chapter_id)
                chapter_json.setdefault("anchor", section.slug)
                chapter_json.setdefault("title", section.title)
                chapter_json.setdefault("order", section.order)
                self._sanitize_chapter_blocks(chapter_json)
                valid, errors = self.validator.validate_chapter(chapter_json)
        content_error: ChapterContentError | None = None
        if valid and not placeholder_created:
            try:
                self._ensure_content_density(chapter_json)
            except ChapterContentError as exc:
                content_error = exc

        error_messages: List[str] = parse_context.copy()
        if not valid and errors:
            error_messages.extend(errors)
        if content_error:
            error_messages.append(str(content_error))

        self.storage.persist_chapter(
            run_dir,
            chapter_meta,
            chapter_json,
            errors=None if not error_messages else error_messages,
        )

        if not valid:
            raise ValueError(
                f"{section.title} 章节JSON校验失败: {'; '.join(errors[:5])}"
            )
        if content_error:
            raise content_error

        return chapter_json

    # ====== 内部方法 ======

    def _build_payload(self, section: TemplateSection, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        构造LLM输入payload。

        参数:
            section: 当前要生成的章节，提供标题/编号/提纲。
            context: 全局上下文字典，包含主题、三引擎报告、篇幅规划等。

        返回:
            dict: 可以直接序列化进提示词的payload，兼顾章节信息与全局约束。
        """
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
        """
        流式调用LLM并实时写入raw文件，同时通过回调将delta抛出。

        参数:
            user_message: 拼装好的用户提示词。
            chapter_dir: 章节的本地缓存目录，用于存放 stream.raw。
            stream_callback: SSE流式推送的回调函数。
            section_meta: 附带的章节ID/标题，用于回调payload。
            **kwargs: 透传温度、top_p等参数。

        返回:
            str: 将所有delta拼接后的原始文本。
        """
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

    def _attempt_cross_engine_json_rescue(
        self,
        section: TemplateSection,
        generation_payload: Dict[str, Any],
        raw_text: str,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        依次调用Report/Forum/Insight/Media四套API尝试修复无法解析的JSON。

        Returns:
            dict | None: 成功修复时返回章节JSON，否则为None。
        """
        if not self.fallback_llm_clients:
            return None
        if self._chapter_already_skipped(section):
            logger.info(f"[{run_id}] {section.title} 已标记为占位，不再触发跨引擎修复")
            return None
        section_payload = {
            "chapterId": section.chapter_id,
            "title": section.title,
            "slug": section.slug,
            "order": section.order,
            "number": section.number,
            "outline": section.outline,
        }
        repair_prompt = build_chapter_recovery_payload(
            section_payload,
            generation_payload,
            raw_text,
        )
        attempted_labels = self._rescue_attempted_labels.setdefault(section.chapter_id, set())
        for label, client in self.fallback_llm_clients:
            if label in attempted_labels:
                continue
            attempt_index = len(attempted_labels) + 1
            attempted_labels.add(label)
            logger.info(
                f"[{run_id}] 章节 {section.title} 触发 {label} API JSON抢修（第{attempt_index}次尝试）"
            )
            try:
                response = client.invoke(
                    SYSTEM_PROMPT_CHAPTER_JSON_RECOVERY,
                    repair_prompt,
                    temperature=0.0,
                    top_p=0.05,
                )
            except Exception as exc:
                logger.warning(f"{label} JSON修复调用失败: {exc}")
                continue
            if not response:
                continue
            try:
                repaired = self._parse_chapter(response)
            except Exception as exc:
                logger.warning(f"{label} JSON修复输出仍无法解析: {exc}")
                continue
            logger.warning(f"[{run_id}] {label} API已修复章节JSON")
            self._archived_failed_json.pop(section.chapter_id, None)
            return repaired
        return None

    def _ensure_run_state(self, run_id: str):
        """确保每次报告运行时的修复状态隔离，防止上一份任务的记录影响新任务。"""
        if self._active_run_id == run_id:
            return
        self._active_run_id = run_id
        self._rescue_attempted_labels = {}
        self._skipped_placeholder_chapters = set()
        self._archived_failed_json = {}

    def _archive_failed_output(self, section: TemplateSection, raw_text: str):
        """缓存当前章节的原始错误JSON，以便后续占位或人工使用。"""
        if not raw_text:
            return
        self._archived_failed_json[section.chapter_id] = raw_text

    def _get_archived_failed_output(self, section: TemplateSection) -> Optional[str]:
        """获取章节最近一次失败的原始输出。"""
        return self._archived_failed_json.get(section.chapter_id)

    def _mark_chapter_skipped(self, section: TemplateSection):
        """记录该章节已经降级为占位，避免重复触发跨引擎修复。"""
        self._skipped_placeholder_chapters.add(section.chapter_id)

    def _chapter_already_skipped(self, section: TemplateSection) -> bool:
        """判断章节是否已经被标记为占位。"""
        return section.chapter_id in self._skipped_placeholder_chapters

    def _build_placeholder_chapter(
        self,
        section: TemplateSection,
        raw_text: str,
        parse_error: Exception,
    ) -> Optional[Tuple[Dict[str, Any], List[str]]]:
        """
        在所有修复失败时构造可渲染的占位章节，并记录日志文件供后续排查。
        """
        snapshot = self._get_archived_failed_output(section) or raw_text
        log_ref = self._persist_error_payload(section, snapshot, parse_error)
        if not log_ref:
            logger.error(f"{section.title} 章节JSON完全损坏且无法写入日志")
            return None
        importance = "critical" if self._is_section_critical(section) else "standard"
        message = (
            f"LLM返回块解析错误，详情请见 {log_ref['relativeFile']} 的 {log_ref['entryId']} 记录。"
        )
        heading_block = {
            "type": "heading",
            "level": 2 if importance == "critical" else 3,
            "text": section.title,
            "anchor": section.slug,
        }
        callout_block = {
            "type": "callout",
            "tone": "danger" if importance == "critical" else "warning",
            "title": "LLM返回块解析错误",
            "blocks": [
                {
                    "type": "paragraph",
                    "inlines": [
                        {
                            "text": message,
                        }
                    ],
                }
            ],
            "meta": {
                "errorLogRef": log_ref,
                "rawJsonPreview": (snapshot or "")[:2000],
                "errorMessage": message,
                "importance": importance,
            },
        }
        placeholder = {
            "chapterId": section.chapter_id,
            "title": section.title,
            "anchor": section.slug,
            "order": section.order,
            "blocks": [heading_block, callout_block],
            "errorPlaceholder": True,
        }
        errors = [
            f"{section.title} 章节JSON解析失败，已降级为占位。参考 {log_ref['relativeFile']}#{log_ref['entryId']}"
        ]
        self._mark_chapter_skipped(section)
        return placeholder, errors

    def _parse_chapter(self, raw_text: str) -> Dict[str, Any]:
        """
        清洗LLM输出并解析JSON。

        参数:
            raw_text: LLM原始输出（可能包含```包裹或额外说明）。

        返回:
            dict: 章节JSON对象，至少包含 chapterId/title/blocks。

        异常:
            ChapterJsonParseError: 多种修复策略仍无法解析合法JSON。
        """
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

        data: Dict[str, Any] | None = None
        try:
            data = self._parse_with_candidates(candidate_payloads)
        except json.JSONDecodeError as exc:
            repaired_payload = self._attempt_json_repair(cleaned)
            if repaired_payload:
                candidate_payloads.append(repaired_payload)
                try:
                    data = self._parse_with_candidates(candidate_payloads[-1:])
                except json.JSONDecodeError:
                    data = None
            if data is None:
                try:
                    data = self._robust_parser.parse(
                        cleaned,
                        context_name="ChapterJSON",
                        expected_keys=["chapter", "blocks", "chapterId", "title"],
                    )
                except JSONParseError as robust_exc:
                    raise ChapterJsonParseError(
                        f"章节JSON解析失败: {robust_exc}", raw_text=cleaned
                    ) from robust_exc

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

    def _persist_error_payload(
        self,
        section: TemplateSection,
        raw_text: str,
        parse_error: Exception,
    ) -> Optional[Dict[str, str]]:
        """将无法解析的JSON文本落盘，便于在HTML中指向具体文件。"""
        try:
            self._failed_block_counter += 1
            entry_id = f"E{self._failed_block_counter:04d}"
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            slug = section.slug or "section"
            filename = f"{timestamp}-{slug}-{entry_id}.json"
            file_path = self.error_log_dir / filename
            payload = {
                "chapterId": section.chapter_id,
                "title": section.title,
                "slug": section.slug,
                "order": section.order,
                "rawOutput": raw_text,
                "error": str(parse_error),
                "loggedAt": timestamp,
            }
            file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            try:
                relative_path = str(file_path.relative_to(Path.cwd()))
            except ValueError:
                relative_path = str(file_path)
            return {
                "file": str(file_path),
                "relativeFile": relative_path,
                "entryId": entry_id,
                "timestamp": timestamp,
            }
        except Exception as exc:
            logger.error(f"记录章节JSON错误日志失败: {exc}")
            return None

    def _is_section_critical(self, section: TemplateSection) -> bool:
        """基于章节深度/编号判断是否会影响目录，从而决定提示强度。"""
        if not section:
            return False
        if section.depth <= 2:
            return True
        number = section.number or ""
        if number and number.count(".") <= 1:
            return True
        return False

    def _repair_llm_json(self, text: str) -> str:
        """
        处理常见的LLM错误（如":=导致的非法JSON）。

        参数:
            text: 原始章节JSON文本。

        返回:
            str: 修复后的文本；若未做改动则返回原内容。
        """
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
        except Exception as exc:  # pragma: no cover - 库级故障
            logger.warning(f"json_repair 修复章节JSON失败: {exc}")
            return None
        if fixed == text:
            return None
        logger.warning("已使用json_repair自动修复章节JSON语法")
        return fixed

    def _attempt_llm_structural_repair(
        self,
        chapter: Dict[str, Any],
        validation_errors: List[str],
        raw_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """将结构性错误的章节交给LLM兜底修复，保持Report Engine相同的API设置。"""
        if not validation_errors:
            return None
        payload = build_chapter_repair_prompt(chapter, validation_errors, raw_text)
        try:
            response = self.llm_client.invoke(
                SYSTEM_PROMPT_CHAPTER_JSON_REPAIR,
                payload,
                temperature=0.0,
                top_p=0.05,
            )
        except Exception as exc:  # pragma: no cover - 网络或API异常仅记录
            logger.error(f"章节JSON LLM修复调用失败: {exc}")
            return None
        if not response:
            return None
        try:
            repaired = self._parse_chapter(response)
        except Exception as exc:
            logger.error(f"LLM修复后的章节JSON解析失败: {exc}")
            return None
        logger.warning("章节JSON经多次本地修复仍不合规，已成功启用LLM兜底修复")
        return repaired

    def _sanitize_chapter_blocks(self, chapter: Dict[str, Any]):
        """
        修正常见的结构性错误（例如list.items嵌套过深）。

        参数:
            chapter: 章节JSON对象，会在原地被清理和规整。
        """

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

        blocks = chapter.get("blocks")
        if isinstance(blocks, list):
            chapter["blocks"] = self._merge_fragment_sequences(blocks)

    def _ensure_content_density(self, chapter: Dict[str, Any]):
        """
        校验章节正文密度。

        若blocks缺失、除标题外无有效区块，或正文字符数低于阈值，
        则视为章节内容异常，触发ChapterContentError以便上游重试。

        参数:
            chapter: 当前章节JSON。

        异常:
            ChapterContentError: 当正文区块数量或字符数达不到下限时抛出。
        """
        blocks = chapter.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise ChapterContentError(
                "章节缺少正文区块，无法输出内容",
                chapter=chapter,
                body_characters=0,
                narrative_characters=0,
                non_heading_blocks=0,
            )

        non_heading_blocks = [
            block
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") not in {"heading", "divider", "toc"}
        ]
        valid_block_count = len(non_heading_blocks)
        body_characters = self._count_body_characters(blocks)
        narrative_characters = self._count_narrative_characters(blocks)

        if (
            valid_block_count < self._MIN_NON_HEADING_BLOCKS
            or body_characters < self._MIN_BODY_CHARACTERS
            or narrative_characters < self._MIN_NARRATIVE_CHARACTERS
        ):
            raise ChapterContentError(
                f"{chapter.get('title') or '该章节'} 正文不足：有效区块 {valid_block_count} 个，估算字符数 {body_characters}，叙述性字符数 {narrative_characters}",
                chapter=chapter,
                body_characters=body_characters,
                narrative_characters=narrative_characters,
                non_heading_blocks=valid_block_count,
            )

    def _count_body_characters(self, blocks: Any) -> int:
        """
        递归统计正文字符数。

        - 忽略heading/divider/widget等非正文类型；
        - 对paragraph/list/table/callout等结构抽取嵌套文本；
        - 仅用于粗粒度判断篇幅是否合理。

        参数:
            blocks: 章节的 blocks 列表或子树。

        返回:
            int: 估算的正文字符数量。
        """

        def walk(node: Any) -> int:
            """递归下钻block树并返回字符估算，跳过非正文类型"""
            if node is None:
                return 0
            if isinstance(node, list):
                return sum(walk(item) for item in node)
            if isinstance(node, str):
                return len(node.strip())
            if not isinstance(node, dict):
                return 0

            block_type = node.get("type")
            if block_type in {"heading", "divider", "toc", "widget"}:
                return 0

            if block_type == "paragraph":
                return self._estimate_paragraph_characters(node)

            if block_type == "list":
                total = 0
                for item in node.get("items", []):
                    total += walk(item)
                return total

            if block_type in {"blockquote", "callout"}:
                return walk(node.get("blocks"))

            if block_type == "table":
                total = 0
                for row in node.get("rows", []):
                    cells = row.get("cells") or []
                    for cell in cells:
                        total += walk(cell.get("blocks"))
                return total

            nested = node.get("blocks")
            if isinstance(nested, list):
                return walk(nested)

            return len(self._extract_block_text(node).strip())

        return walk(blocks)

    def _count_narrative_characters(self, blocks: Any) -> int:
        """
        统计paragraph/callout/list/blockquote等叙述性结构的字符数，避免被表格/图表“刷长”。
        """

        def walk(node: Any) -> int:
            """递归遍历叙述性节点，忽略图表/目录等非正文结构"""
            if node is None:
                return 0
            if isinstance(node, list):
                return sum(walk(item) for item in node)
            if isinstance(node, str):
                return len(node.strip())
            if not isinstance(node, dict):
                return 0

            block_type = node.get("type")
            if block_type == "paragraph":
                return self._estimate_paragraph_characters(node)
            if block_type == "list":
                total = 0
                for item in node.get("items", []):
                    total += walk(item)
                return total
            if block_type in {"callout", "blockquote"}:
                return walk(node.get("blocks"))

            # list项可能是匿名dict，兼容性遍历
            if block_type is None:
                nested = node.get("blocks")
                if isinstance(nested, list):
                    return walk(nested)
            return 0

        return walk(blocks)

    def _estimate_paragraph_characters(self, block: Dict[str, Any]) -> int:
        """提取paragraph文本长度，复用在多种统计中。"""
        inlines = block.get("inlines")
        if isinstance(inlines, list):
            total = 0
            for run in inlines:
                if isinstance(run, dict):
                    text = run.get("text")
                    if isinstance(text, str):
                        total += len(text.strip())
            return total
        text_value = block.get("text")
        if isinstance(text_value, str):
            return len(text_value.strip())
        return len(self._extract_block_text(block).strip())

    def _sanitize_block_content(self, block: Dict[str, Any]):
        """根据类型做精细化修复，例如清理paragraph内的非法inline mark"""
        block_type = block.get("type")
        if block_type == "paragraph":
            self._normalize_paragraph_block(block)
        elif block_type == "table":
            self._sanitize_table_block(block)

    def _sanitize_table_block(self, block: Dict[str, Any]):
        """保证表格的rows/cells结构合法且每个单元格包含至少一个block"""
        rows = self._normalize_table_rows(block.get("rows"))
        block["rows"] = rows

    def _normalize_table_rows(self, rows: Any) -> List[Dict[str, Any]]:
        """确保rows始终是由row对象组成的列表"""
        if rows is None:
            rows_iterable: List[Any] = []
        elif isinstance(rows, list):
            rows_iterable = rows
        else:
            rows_iterable = [rows]

        normalized_rows: List[Dict[str, Any]] = []
        for row in rows_iterable:
            sanitized_row = self._normalize_table_row(row)
            if sanitized_row:
                normalized_rows.append(sanitized_row)

        if not normalized_rows:
            normalized_rows.append({"cells": [self._build_default_table_cell()]})
        return normalized_rows

    def _normalize_table_row(self, row: Any) -> Dict[str, Any] | None:
        """将各种行表达统一成{'cells': [...]}结构"""
        if row is None:
            return None
        if isinstance(row, dict):
            result = dict(row)
            cells_value = result.get("cells")
        else:
            result = {}
            cells_value = row

        cells = self._normalize_table_cells(cells_value)
        if not cells:
            cells = [self._build_default_table_cell()]
        result["cells"] = cells
        return result

    def _normalize_table_cells(self, cells: Any) -> List[Dict[str, Any]]:
        """清洗单元格，保证每个cell下都有非空blocks"""
        if cells is None:
            cell_entries: List[Any] = []
        elif isinstance(cells, list):
            cell_entries = cells
        else:
            cell_entries = [cells]

        normalized_cells: List[Dict[str, Any]] = []
        for cell in cell_entries:
            sanitized = self._normalize_table_cell(cell)
            if sanitized:
                normalized_cells.append(sanitized)

        return normalized_cells

    def _normalize_table_cell(self, cell: Any) -> Dict[str, Any] | None:
        """把各种单元格写法规整为schema认可的形式"""
        if cell is None:
            return {"blocks": [self._as_paragraph_block("")]}

        if isinstance(cell, dict):
            normalized = dict(cell)
            blocks = self._coerce_cell_blocks(normalized.get("blocks"), normalized)
        elif isinstance(cell, list):
            normalized = {}
            blocks = self._coerce_cell_blocks(cell, None)
        elif isinstance(cell, (str, int, float)):
            normalized = {}
            blocks = [self._as_paragraph_block(str(cell))]
        else:
            normalized = {}
            blocks = [self._as_paragraph_block(str(cell))]

        normalized["blocks"] = blocks or [self._as_paragraph_block("")]
        return normalized

    def _coerce_cell_blocks(
        self, blocks: Any, source: Dict[str, Any] | None
    ) -> List[Dict[str, Any]]:
        """将cell.blocks字段强制转换为合法的block数组"""
        if isinstance(blocks, list):
            entries = blocks
        elif blocks is None:
            entries = []
        else:
            entries = [blocks]

        normalized_blocks: List[Dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, dict):
                normalized_blocks.append(entry)
            elif isinstance(entry, list):
                normalized_blocks.extend(self._coerce_cell_blocks(entry, None))
            elif isinstance(entry, (str, int, float)):
                normalized_blocks.append(self._as_paragraph_block(str(entry)))
            elif entry is None:
                continue
            else:
                normalized_blocks.append(self._as_paragraph_block(str(entry)))

        if normalized_blocks:
            return normalized_blocks

        text_hint = ""
        if isinstance(source, dict):
            text_hint = self._extract_block_text(source).strip()
        return [self._as_paragraph_block(text_hint or "--")]

    def _build_default_table_cell(self) -> Dict[str, Any]:
        """生成一个最小可渲染的空白单元格"""
        return {"blocks": [self._as_paragraph_block("--")]}

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
        block["inlines"] = self._strip_inline_artifacts(normalized_runs)

    def _strip_inline_artifacts(self, inlines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """移除被LLM误写入的JSON哨兵文本，防止渲染出`{\"type\": \"\"}`等垃圾字符"""
        cleaned: List[Dict[str, Any]] = []
        for run in inlines or []:
            if not isinstance(run, dict):
                continue
            text = run.get("text")
            if isinstance(text, str):
                stripped = text.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError:
                        payload = None
                    if isinstance(payload, dict) and set(payload.keys()).issubset({"type", "value"}):
                        continue
            cleaned.append(run)
        return cleaned or [self._as_inline_run("")]

    def _merge_fragment_sequences(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并被LLM拆成多段的句子片段，避免HTML出现大量孤立<p>"""
        if not isinstance(blocks, list):
            return blocks

        merged: List[Dict[str, Any]] = []
        fragment_buffer: List[Dict[str, Any]] = []

        def flush_buffer():
            """将当前片段缓冲写入merged列表，必要时合并为单段paragraph"""
            nonlocal fragment_buffer
            if not fragment_buffer:
                return
            if len(fragment_buffer) == 1:
                merged.append(fragment_buffer[0])
            else:
                merged.append(self._combine_paragraph_fragments(fragment_buffer))
            fragment_buffer = []

        for block in blocks:
            if self._is_paragraph_fragment(block):
                fragment_buffer.append(block)
                continue
            flush_buffer()
            merged.append(self._merge_nested_fragments(block))

        flush_buffer()
        return merged

    def _merge_nested_fragments(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """对嵌套结构（callout/list/table）递归处理片段合并"""
        block_type = block.get("type")
        if block_type in {"callout", "blockquote"}:
            nested = block.get("blocks")
            if isinstance(nested, list):
                block["blocks"] = self._merge_fragment_sequences(nested)
        elif block_type == "list":
            items = block.get("items")
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, list):
                        merged_entry = self._merge_fragment_sequences(entry)
                        entry[:] = merged_entry
        elif block_type == "table":
            for row in block.get("rows", []):
                cells = row.get("cells") or []
                for cell in cells:
                    nested_blocks = cell.get("blocks")
                    if isinstance(nested_blocks, list):
                        cell["blocks"] = self._merge_fragment_sequences(nested_blocks)
        return block

    def _combine_paragraph_fragments(self, fragments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将多个句子片段合并为单个paragraph block"""
        template = dict(fragments[0])
        combined_inlines: List[Dict[str, Any]] = []
        for fragment in fragments:
            runs = fragment.get("inlines")
            if isinstance(runs, list) and runs:
                combined_inlines.extend(runs)
            else:
                fallback_text = self._extract_block_text(fragment)
                combined_inlines.append(self._as_inline_run(fallback_text))
        if not combined_inlines:
            combined_inlines.append(self._as_inline_run(""))
        template["inlines"] = combined_inlines
        return template

    def _is_paragraph_fragment(self, block: Dict[str, Any]) -> bool:
        """判断paragraph是否为被错误拆分的短片段"""
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            return False
        inlines = block.get("inlines")
        text = ""
        has_marks = False
        if isinstance(inlines, list) and inlines:
            parts: List[str] = []
            for run in inlines:
                if not isinstance(run, dict):
                    continue
                parts.append(str(run.get("text") or ""))
                marks = run.get("marks")
                if isinstance(marks, list) and any(marks):
                    has_marks = True
            text = "".join(parts)
        else:
            text = self._extract_block_text(block)
        stripped = (text or "").strip()
        if not stripped:
            return True
        if has_marks:
            return False
        if "\n" in stripped:
            return False

        short_limit = self._PARAGRAPH_FRAGMENT_MAX_CHARS
        long_limit = getattr(
            self,
            "_PARAGRAPH_FRAGMENT_NO_TERMINATOR_MAX_CHARS",
            short_limit * 3,
        )

        if stripped[-1] in self._TERMINATION_PUNCTUATION:
            return len(stripped) <= short_limit

        if len(stripped) > long_limit:
            return False
        return True

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
