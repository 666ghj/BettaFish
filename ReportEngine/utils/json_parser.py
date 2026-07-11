"""
统一的JSON解析和修复工具。

提供鲁棒的JSON解析能力，支持：
1. 自动清理markdown代码块标记和思考内容
2. 本地语法修复（括号平衡、逗号补全、控制字符转义等）
3. 使用json_repair库进行高级修复
4. LLM辅助修复（可选）
5. 详细的错误日志和调试信息
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Callable
from loguru import logger

try:
    from json_repair import repair_json as _json_repair_fn
except ImportError:
    _json_repair_fn = None


class JSONParseError(ValueError):
    """JSON解析失败时抛出的异常，附带原始文本方便排查。"""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        """
        构造异常并附加原始输出，便于日志中定位。

        Args:
            message: 人类可读的错误描述。
            raw_text: 触发异常的完整LLM输出。
        """
        super().__init__(message)
        self.raw_text = raw_text


class RobustJSONParser:
    """
    鲁棒的JSON解析器。

    集成多种修复策略，确保LLM返回的内容能够被正确解析：
    - 清理markdown包裹、思考内容等额外信息
    - 修复常见语法错误（缺少逗号、括号不平衡等）
    - 转义未转义的控制字符
    - 使用第三方库进行高级修复
    - 可选的LLM辅助修复
    """

    # 常见的LLM思考内容模式
    _THINKING_PATTERNS = [
        r"^\s*<thinking>.*?</thinking>\s*",
        r"^\s*<thought>.*?</thought>\s*",
        r"^\s*让我想想.*?(?=\{|\[|$)",
        r"^\s*首先.*?(?=\{|\[|$)",
        r"^\s*分析.*?(?=\{|\[|$)",
        r"^\s*根据.*?(?=\{|\[|$)",
    ]

    # 冒号等号模式（LLM常见错误）
    _COLON_EQUALS_PATTERN = re.compile(r'(":\s*)=')

    def __init__(
        self,
        llm_repair_fn: Optional[Callable[[str, str], Optional[str]]] = None,
        enable_json_repair: bool = True,
        enable_llm_repair: bool = False,
        max_repair_attempts: int = 3,
    ):
        """
        初始化JSON解析器。

        Args:
            llm_repair_fn: 可选的LLM修复函数，接收(原始JSON, 错误信息)返回修复后的JSON
            enable_json_repair: 是否启用json_repair库
            enable_llm_repair: 是否启用LLM辅助修复
            max_repair_attempts: 最大修复尝试次数
        """
        self.llm_repair_fn = llm_repair_fn
        self.enable_json_repair = enable_json_repair and _json_repair_fn is not None
        self.enable_llm_repair = enable_llm_repair
        self.max_repair_attempts = max_repair_attempts

    def parse(
        self,
        raw_text: str,
        context_name: str = "JSON",
        expected_keys: Optional[List[str]] = None,
        extract_wrapper_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        解析LLM返回的JSON文本。

        参数:
            raw_text: LLM原始输出（可能包含```包裹、思考内容等）
            context_name: 上下文名称，用于错误信息
            expected_keys: 期望的键列表，用于验证
            extract_wrapper_key: 如果JSON被包裹在某个键中，指定该键名进行提取

        返回:
            dict: 解析后的JSON对象

        异常:
            JSONParseError: 多种修复策略仍无法解析合法JSON
        """
        if not isinstance(raw_text, str):
            raise JSONParseError(
                f"{context_name}返回的不是文本内容: {type(raw_text).__name__}",
                raw_text=repr(raw_text),
            )
        if not raw_text.strip():
            raise JSONParseError(f"{context_name}返回空内容", raw_text=raw_text)

        # 原始文本用于后续日志
        original_text = raw_text

        # 步骤1: 构造候选集，包含不同清理策略
        candidates = self._build_candidate_payloads(raw_text, context_name)

        # 步骤2: 尝试解析所有候选
        last_error: Optional[json.JSONDecodeError] = None
        for i, candidate in enumerate(candidates):
            try:
                data = json.loads(candidate)
                logger.debug(f"{context_name} JSON解析成功（候选{i + 1}/{len(candidates)}）")
                return self._extract_and_validate(
                    data, expected_keys, extract_wrapper_key, context_name
                )
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.debug(f"{context_name} 候选{i + 1}解析失败: {exc}")

        cleaned = candidates[0] if candidates else original_text

        # 步骤3: 使用json_repair库
        if self.enable_json_repair:
            repaired = self._attempt_json_repair(cleaned, context_name)
            if repaired:
                try:
                    data = json.loads(repaired)
                    logger.info(f"{context_name} JSON通过json_repair库修复成功")
                    return self._extract_and_validate(
                        data, expected_keys, extract_wrapper_key, context_name
                    )
                except json.JSONDecodeError as exc:
                    last_error = exc
                    logger.debug(f"{context_name} json_repair修复后仍无法解析: {exc}")

        # 步骤4: 使用LLM修复（如果启用）
        if self.enable_llm_repair and self.llm_repair_fn:
            llm_repaired = self._attempt_llm_repair(cleaned, str(last_error), context_name)
            if llm_repaired:
                try:
                    data = json.loads(llm_repaired)
                    logger.info(f"{context_name} JSON通过LLM修复成功")
                    return self._extract_and_validate(
                        data, expected_keys, extract_wrapper_key, context_name
                    )
                except json.JSONDecodeError as exc:
                    last_error = exc
                    logger.warning(f"{context_name} LLM修复后仍无法解析: {exc}")

        # 所有策略都失败了
        error_msg = f"{context_name} JSON解析失败: {last_error}"
        logger.error(error_msg)
        logger.debug(f"原始文本前500字符: {original_text[:500]}")
        raise JSONParseError(error_msg, raw_text=original_text) from last_error

    def _build_candidate_payloads(self, raw_text: str, context_name: str) -> List[str]:
        """
        针对原始文本构造多个候选JSON字符串，覆盖不同的清理策略。

        返回:
            List[str]: 候选JSON文本列表
        """
        cleaned = self._clean_response(raw_text)
        candidates = [cleaned]

        local_repaired = self._apply_local_repairs(cleaned)
        if local_repaired != cleaned:
            candidates.append(local_repaired)

        # 对含有三层列表结构的内容强制拉平一次
        flattened = self._flatten_nested_arrays(local_repaired)
        if flattened not in candidates:
            candidates.append(flattened)

        return candidates

    def _clean_response(self, raw: str) -> str:
        """
        清理LLM响应，去除markdown标记和思考内容。

        参数:
            raw: LLM原始输出

        返回:
            str: 清理后的文本
        """
        cleaned = raw.strip()

        # 移除思考内容（多语言支持）
        for pattern in self._THINKING_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # 模型可能先输出其他代码块；显式标记为 JSON 的代码块优先级最高。
        fenced_match = re.search(
            r"```json\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE
        )
        if not fenced_match:
            fenced_match = re.search(r"```\s*([\s\S]*?)\s*```", cleaned)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()
        else:
            # 如果没有找到完整代码块，再尝试移除前后缀
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]

            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            cleaned = cleaned.strip()

        # 尝试提取第一个完整的JSON对象或数组
        cleaned = self._extract_first_json_structure(cleaned)

        return cleaned

    def _extract_first_json_structure(self, text: str) -> str:
        """
        从文本中提取第一个完整的JSON对象或数组。

        这对于处理LLM在JSON前后添加说明文字的情况很有用。

        参数:
            text: 可能包含JSON的文本

        返回:
            str: 提取的JSON文本，如果找不到则返回原文本
        """
        # 查找第一个 { 或 [
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace == -1 and start_bracket == -1:
            return text

        # 确定起始位置
        if start_brace == -1:
            start = start_bracket
            opener = "["
            closer = "]"
        elif start_bracket == -1:
            start = start_brace
            opener = "{"
            closer = "}"
        else:
            start = min(start_brace, start_bracket)
            opener = text[start]
            closer = "}" if opener == "{" else "]"

        # 查找对应的结束位置
        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(text)):
            ch = text[i]

            if escaped:
                escaped = False
                continue

            if ch == "\\":
                escaped = True
                continue

            if ch == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        # 如果没找到完整的结构，返回从起始位置到结尾
        return text[start:] if start < len(text) else text

    def _apply_local_repairs(self, text: str) -> str:
        """
        应用本地修复策略。

        参数:
            text: 原始JSON文本

        返回:
            str: 修复后的文本
        """
        repaired = text
        mutated = False

        # 修复 ":=" 错误
        new_text = self._COLON_EQUALS_PATTERN.sub(r"\1", repaired)
        if new_text != repaired:
            logger.warning("检测到\":=\"字符，已自动移除多余的'='号")
            repaired = new_text
            mutated = True

        # 转义控制字符
        repaired, escaped = self._escape_control_characters(repaired)
        if escaped:
            logger.warning("检测到未转义的控制字符，已自动转换为转义序列")
            mutated = True

        # 修复缺少的逗号
        repaired, commas_fixed = self._fix_missing_commas(repaired)
        if commas_fixed:
            logger.warning("检测到对象/数组之间缺少逗号，已自动补齐")
            mutated = True

        # 合并多余的方括号（LLM常见把二维列表层级写成三层）
        repaired, brackets_collapsed = self._collapse_redundant_brackets(repaired)
        if brackets_collapsed:
            logger.warning("检测到连续的方括号嵌套，已尝试折叠为二维结构")
            mutated = True

        # 平衡括号
        repaired, balanced = self._balance_brackets(repaired)
        if balanced:
            logger.warning("检测到括号不平衡，已自动补齐/剔除异常括号")
            mutated = True

        # 移除尾随逗号
        repaired, trailing_removed = self._remove_trailing_commas(repaired)
        if trailing_removed:
            logger.warning("检测到尾随逗号，已自动移除")
            mutated = True

        return repaired if mutated else text

    def _escape_control_characters(self, text: str) -> Tuple[str, bool]:
        """
        将字符串字面量中的裸换行/制表符/控制字符替换为JSON合法的转义序列。

        参数:
            text: 原始JSON文本

        返回:
            Tuple[str, bool]: (修复后的文本, 是否有修改)
        """
        if not text:
            return text, False

        result: List[str] = []
        in_string = False
        escaped = False
        mutated = False
        control_map = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}

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
        """
        在对象/数组元素之间自动补逗号。

        参数:
            text: 原始JSON文本

        返回:
            Tuple[str, bool]: (修复后的文本, 是否有修改)
        """
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
                # 如果我们正在退出字符串，检查后面是否需要逗号
                if in_string:
                    # 查找下一个非空白字符
                    j = i + 1
                    while j < length and text[j] in " \t\r\n":
                        j += 1
                    # 如果下一个字符是 " { [ 或数字，可能需要逗号
                    if j < length:
                        next_ch = text[j]
                        if next_ch in "\"[{" or next_ch.isdigit():
                            # 检查是否已经在对象或数组中
                            # 通过检查前面是否有未闭合的 { 或 [
                            has_opener = False
                            for k in range(len(chars) - 1, -1, -1):
                                if chars[k] in "{[":
                                    has_opener = True
                                    break
                                elif chars[k] in "]}":
                                    break

                            if has_opener:
                                chars.append(",")
                                mutated = True

                in_string = not in_string
                i += 1
                continue

            # 在 } 或 ] 后面检查是否需要逗号
            if not in_string and ch in "}]":
                j = i + 1
                # 跳过空白
                while j < length and text[j] in " \t\r\n":
                    j += 1
                # 如果下一个非空白字符是 { [ " 或数字，添加逗号
                if j < length:
                    next_ch = text[j]
                    if next_ch in "{[\"" or next_ch.isdigit():
                        chars.append(",")
                        mutated = True

            i += 1

        return "".join(chars), mutated

    def _collapse_redundant_brackets(self, text: str) -> Tuple[str, bool]:
        """
        针对LLM生成的三层或更多层数组（如]]], [[ / [[[）进行折叠，避免表格/列表写出额外维度。

        返回:
            Tuple[str, bool]: (修复后的文本, 是否有修改)
        """
        if not text:
            return text, False

        mutated = False

        patterns = [
            # 典型错误: "]]], [[{...}" -> "]], [{...}"
            (re.compile(r"\]\s*\]\s*\]\s*,\s*\[\s*\["), "]],["),
            # 极端情况: 连续三层开头 "[[[" -> "[["
            (re.compile(r"\[\s*\[\s*\["), "[["),
            # 极端情况: 结尾 "]]]" -> "]]"
            (re.compile(r"\]\s*\]\s*\]"), "]]"),
        ]

        repaired = text
        for pattern, replacement in patterns:
            new_text, count = pattern.subn(replacement, repaired)
            if count > 0:
                mutated = True
                repaired = new_text

        return repaired, mutated

    def _flatten_nested_arrays(self, text: str) -> str:
        """
        对明显多余的一层列表进行折叠，例如 [[[x]]] -> [[x]]。
        """
        if not text:
            return text
        text = re.sub(r"\]\s*\]\s*\]", "]]", text)
        text = re.sub(r"\[\s*\[\s*\[", "[[", text)
        return text

    def _balance_brackets(self, text: str) -> Tuple[str, bool]:
        """
        尝试修复因LLM多写/少写括号导致的不平衡结构。

        参数:
            text: 原始JSON文本

        返回:
            Tuple[str, bool]: (修复后的文本, 是否有修改)
        """
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
                if stack and (
                    (ch == "}" and stack[-1] == "{") or (ch == "]" and stack[-1] == "[")
                ):
                    stack.pop()
                    result.append(ch)
                else:
                    # 不匹配的闭括号，忽略
                    mutated = True
                continue

            result.append(ch)

        # 补齐未闭合的括号
        while stack:
            opener = stack.pop()
            result.append(opener_map[opener])
            mutated = True

        return "".join(result), mutated

    def _remove_trailing_commas(self, text: str) -> Tuple[str, bool]:
        """
        移除JSON对象和数组中的尾随逗号。

        参数:
            text: 原始JSON文本

        返回:
            Tuple[str, bool]: (修复后的文本, 是否有修改)
        """
        if not text:
            return text, False

        # 使用正则表达式移除尾随逗号
        # 匹配 , 后面跟着空白和 } 或 ] 的情况
        pattern = r",(\s*[}\]])"
        new_text = re.sub(pattern, r"\1", text)

        return new_text, new_text != text

    def _attempt_json_repair(self, text: str, context_name: str) -> Optional[str]:
        """
        使用json_repair库进行高级修复。

        参数:
            text: 原始JSON文本
            context_name: 上下文名称

        返回:
            Optional[str]: 修复后的JSON文本，失败返回None
        """
        if not _json_repair_fn:
            return None

        try:
            fixed = _json_repair_fn(text)
            if fixed and fixed != text:
                logger.info(f"{context_name} 使用json_repair库自动修复JSON")
                return fixed
        except Exception as exc:
            logger.debug(f"{context_name} json_repair修复失败: {exc}")

        return None

    def _attempt_llm_repair(
        self, text: str, error_msg: str, context_name: str
    ) -> Optional[str]:
        """
        使用LLM进行JSON修复。

        参数:
            text: 原始JSON文本
            error_msg: 解析错误信息
            context_name: 上下文名称

        返回:
            Optional[str]: 修复后的JSON文本，失败返回None
        """
        if not self.llm_repair_fn:
            return None

        try:
            logger.info(f"{context_name} 尝试使用LLM修复JSON")
            repaired = self.llm_repair_fn(text, error_msg)
            if repaired and repaired != text:
                return repaired
        except Exception as exc:
            logger.warning(f"{context_name} LLM修复失败: {exc}")

        return None

    def _extract_and_validate(
        self,
        data: Any,
        expected_keys: Optional[List[str]],
        extract_wrapper_key: Optional[str],
        context_name: str,
    ) -> Dict[str, Any]:
        """
        提取并验证JSON数据。

        参数:
            data: 解析后的数据
            expected_keys: 期望的键列表
            extract_wrapper_key: 包裹键名
            context_name: 上下文名称

        返回:
            Dict[str, Any]: 提取并验证后的数据

        异常:
            JSONParseError: 如果数据格式不符合预期
        """
        # 提取包裹的数据
        if extract_wrapper_key and isinstance(data, dict):
            if extract_wrapper_key in data:
                data = data[extract_wrapper_key]
            else:
                logger.warning(
                    f"{context_name} 未找到包裹键'{extract_wrapper_key}'，使用原始数据"
                )

        # 验证数据类型
        if not isinstance(data, dict):
            if isinstance(data, list):
                if len(data) > 0:
                    # 尝试找到最符合期望的元素
                    best_match = None
                    max_match_count = 0

                    for item in data:
                        if isinstance(item, dict):
                            if expected_keys:
                                # 计算匹配的键数量
                                match_count = sum(1 for key in expected_keys if key in item)
                                if match_count > max_match_count:
                                    max_match_count = match_count
                                    best_match = item
                            elif best_match is None:
                                best_match = item

                    if best_match:
                        logger.warning(
                            f"{context_name} 返回数组，自动提取最佳匹配元素（匹配{max_match_count}/{len(expected_keys or [])}个键）"
                        )
                        data = best_match
                    else:
                        raise JSONParseError(
                            f"{context_name} 返回的数组中没有有效的对象"
                        )
                else:
                    raise JSONParseError(f"{context_name} 返回空数组")
            else:
                raise JSONParseError(
                    f"{context_name} 返回的不是JSON对象: {type(data).__name__}"
                )

        # 验证必需的键
        if expected_keys:
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.warning(
                    f"{context_name} 缺少预期的键: {', '.join(missing_keys)}"
                )
                # 尝试修复常见的键名变体
                data = self._try_recover_missing_keys(data, missing_keys, context_name)

        return data

    def _try_recover_missing_keys(
        self, data: Dict[str, Any], missing_keys: List[str], context_name: str
    ) -> Dict[str, Any]:
        """
        尝试从数据中恢复缺失的键，通过查找相似的键名。

        参数:
            data: 原始数据
            missing_keys: 缺失的键列表
            context_name: 上下文名称

        返回:
            Dict[str, Any]: 修复后的数据
        """
        # 常见的键名映射
        key_aliases = {
            "template_name": ["templateName", "name", "template"],
            "selection_reason": ["selectionReason", "reason", "explanation"],
            "title": ["reportTitle", "documentTitle"],
            "chapters": ["chapterList", "chapterPlan", "sections"],
            "totalWords": ["total_words", "wordCount", "totalWordCount"],
        }

        for missing_key in missing_keys:
            if missing_key in key_aliases:
                for alias in key_aliases[missing_key]:
                    if alias in data:
                        logger.info(
                            f"{context_name} 找到键'{missing_key}'的别名'{alias}'，自动映射"
                        )
                        data[missing_key] = data[alias]
                        break

        return data


__all__ = ["RobustJSONParser", "JSONParseError"]
