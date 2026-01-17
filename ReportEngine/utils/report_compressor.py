"""
报告压缩器：提供摘要和主题提取功能以避免上下文超限。

该模块实现两种压缩策略：
1. 规则提取摘要：用于阶段1-2（文档布局、篇幅规划）
2. 关键词匹配提取：用于阶段3（章节生成）
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple
from loguru import logger

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba 未安装，将使用简单分词策略")


class ReportCompressor:
    """报告压缩器：提供摘要和主题提取功能"""

    # 结论性关键词
    CONCLUSION_KEYWORDS = {
        "总结", "结论", "发现", "核心", "关键", "重点", "要点",
        "综上", "总之", "总体", "整体", "主要", "建议", "启示"
    }

    # 停用词
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这"
    }

    def __init__(self, config, llm_client=None):
        """
        初始化压缩器。

        Args:
            config: Settings 配置对象
            llm_client: 可选的 LLM 客户端，用于 LLM 摘要策略
        """
        self.config = config
        self.llm_client = llm_client

        # 初始化 jieba（如果可用）
        if JIEBA_AVAILABLE:
            jieba.setLogLevel(logger.level("WARNING").no)

    def summarize_reports(self, reports: Dict[str, str]) -> Dict[str, str]:
        """
        为阶段1-2生成摘要版本。

        Args:
            reports: 原始报告字典 {engine_name: content}

        Returns:
            摘要后的报告字典
        """
        strategy = getattr(self.config, 'SUMMARY_STRATEGY', 'rule')
        target_ratio = getattr(self.config, 'SUMMARY_COMPRESSION_RATIO', 0.35)

        summarized = {}
        for engine_name, content in reports.items():
            if not content or not content.strip():
                summarized[engine_name] = content
                continue

            original_len = len(content)

            if strategy == "rule":
                summary = self._summarize_by_rules(content, target_ratio)
            elif strategy == "llm" and self.llm_client:
                summary = self._summarize_by_llm(content, engine_name, target_ratio)
            else:
                # 降级到规则提取
                summary = self._summarize_by_rules(content, target_ratio)

            summarized[engine_name] = summary

            # 记录压缩率
            compressed_len = len(summary)
            ratio = compressed_len / original_len if original_len > 0 else 1.0
            logger.info(
                f"[摘要] {engine_name}: {original_len} → {compressed_len} 字符 "
                f"(压缩率: {ratio:.1%})"
            )

        return summarized

    def extract_relevant_content(
        self,
        reports: Dict[str, str],
        chapter_title: str,
        chapter_outline: str
    ) -> Dict[str, str]:
        """
        为阶段3提取相关内容。

        Args:
            reports: 原始报告字典
            chapter_title: 章节标题
            chapter_outline: 章节大纲

        Returns:
            提取后的报告字典
        """
        strategy = getattr(self.config, 'EXTRACTION_STRATEGY', 'keyword')

        # 提取关键词
        keywords = self._extract_keywords(chapter_title, chapter_outline)

        if not keywords:
            logger.warning(f"章节 '{chapter_title}' 未提取到关键词，返回原始报告")
            return reports

        logger.info(f"[提取] 章节 '{chapter_title}' 关键词: {', '.join(keywords[:10])}")

        if strategy == "keyword":
            extracted = self._extract_by_keyword(reports, keywords)
        else:
            # 降级到关键词匹配
            extracted = self._extract_by_keyword(reports, keywords)

        # 记录提取结果
        for engine_name, content in extracted.items():
            original_len = len(reports.get(engine_name, ""))
            extracted_len = len(content)
            ratio = extracted_len / original_len if original_len > 0 else 1.0
            logger.info(
                f"[提取] {engine_name}: {original_len} → {extracted_len} 字符 "
                f"(提取率: {ratio:.1%})"
            )

        return extracted

    def _summarize_by_rules(self, report: str, target_ratio: float = 0.35) -> str:
        """
        规则提取摘要。

        保留：
        - 所有标题
        - 结论性段落
        - 数据段落
        - 列表项

        Args:
            report: 原始报告文本
            target_ratio: 目标压缩率

        Returns:
            摘要文本
        """
        lines = report.split('\n')
        kept_lines = []

        for line in lines:
            stripped = line.strip()

            # 保留空行（用于段落分隔）
            if not stripped:
                if kept_lines and kept_lines[-1].strip():  # 避免连续空行
                    kept_lines.append(line)
                continue

            # 保留标题
            if stripped.startswith('#'):
                kept_lines.append(line)
                continue

            # 保留列表项
            if re.match(r'^[\-\*\+]\s', stripped) or re.match(r'^\d+\.\s', stripped):
                kept_lines.append(line)
                continue

            # 保留结论性段落
            if any(keyword in stripped for keyword in self.CONCLUSION_KEYWORDS):
                kept_lines.append(line)
                continue

            # 保留数据段落（包含数字、百分比）
            if re.search(r'\d+[%％]|\d+\.\d+|\d{4}年|\d+月', stripped):
                kept_lines.append(line)
                continue

            # 保留表格行（包含 | 分隔符）
            if '|' in stripped and stripped.count('|') >= 2:
                kept_lines.append(line)
                continue

        summary = '\n'.join(kept_lines)

        # 如果压缩率不够，进一步过滤
        current_ratio = len(summary) / len(report) if len(report) > 0 else 1.0
        if current_ratio > target_ratio * 1.2:  # 允许20%误差
            # 进一步过滤：只保留标题和关键段落
            summary = self._aggressive_filter(kept_lines, target_ratio, len(report))

        return summary

    def _aggressive_filter(
        self,
        lines: List[str],
        target_ratio: float,
        original_len: int
    ) -> str:
        """更激进的过滤策略"""
        kept = []
        for line in lines:
            stripped = line.strip()
            # 只保留标题、列表项和包含多个关键词的段落
            if (stripped.startswith('#') or
                re.match(r'^[\-\*\+\d]+[\.\)]\s', stripped) or
                sum(1 for kw in self.CONCLUSION_KEYWORDS if kw in stripped) >= 2):
                kept.append(line)

        return '\n'.join(kept)

    def _summarize_by_llm(
        self,
        report: str,
        engine_name: str,
        target_ratio: float = 0.35
    ) -> str:
        """
        使用 LLM 进行智能摘要。

        Args:
            report: 原始报告文本
            engine_name: 引擎名称
            target_ratio: 目标压缩率

        Returns:
            摘要文本
        """
        if not self.llm_client:
            logger.warning("LLM 客户端未配置，降级到规则提取")
            return self._summarize_by_rules(report, target_ratio)

        target_length = int(len(report) * target_ratio)

        system_prompt = """你是一个专业的报告摘要助手。请提取报告中的关键信息，包括：
1. 所有标题和章节结构
2. 核心发现和结论
3. 重要数据和统计
4. 关键建议和要点

保持原有的 Markdown 格式，删除冗余的描述性文本。"""

        user_prompt = f"""请将以下报告压缩到约 {target_length} 字符，保留关键信息：

{report}"""

        try:
            response = self.llm_client.invoke(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                top_p=0.9
            )
            return response.strip()
        except Exception as e:
            logger.error(f"LLM 摘要失败: {e}，降级到规则提取")
            return self._summarize_by_rules(report, target_ratio)

    def _extract_by_keyword(
        self,
        reports: Dict[str, str],
        keywords: List[str]
    ) -> Dict[str, str]:
        """
        基于关键词匹配提取相关段落。

        Args:
            reports: 原始报告字典
            keywords: 关键词列表

        Returns:
            提取后的报告字典
        """
        threshold = getattr(self.config, 'KEYWORD_MATCH_THRESHOLD', 2)
        keep_context = getattr(self.config, 'KEEP_CONTEXT_PARAGRAPHS', True)
        context_count = getattr(self.config, 'CONTEXT_PARAGRAPHS_COUNT', 1)
        max_ratio = getattr(self.config, 'EXTRACTION_MAX_RATIO', 0.5)

        extracted = {}

        for engine_name, content in reports.items():
            if not content or not content.strip():
                extracted[engine_name] = content
                continue

            # 分段
            paragraphs = self._split_paragraphs(content)

            # 计算每个段落的匹配度
            matches = []
            for idx, para in enumerate(paragraphs):
                score = self._calculate_match_score(para, keywords)
                if score >= threshold:
                    matches.append((idx, score, para))

            # 按匹配度排序
            matches.sort(key=lambda x: x[1], reverse=True)

            # 提取段落（包含上下文）
            selected_indices = set()
            for idx, score, para in matches:
                selected_indices.add(idx)
                if keep_context:
                    # 添加上下文段落
                    for offset in range(1, context_count + 1):
                        if idx - offset >= 0:
                            selected_indices.add(idx - offset)
                        if idx + offset < len(paragraphs):
                            selected_indices.add(idx + offset)

            # 按原始顺序重组
            selected_paragraphs = [
                paragraphs[i] for i in sorted(selected_indices)
            ]

            extracted_text = '\n\n'.join(selected_paragraphs)

            # 检查提取率
            current_ratio = len(extracted_text) / len(content) if len(content) > 0 else 1.0
            if current_ratio > max_ratio:
                # 只保留最相关的段落
                top_matches = matches[:int(len(matches) * max_ratio)]
                selected_indices = {idx for idx, _, _ in top_matches}
                selected_paragraphs = [
                    paragraphs[i] for i in sorted(selected_indices)
                ]
                extracted_text = '\n\n'.join(selected_paragraphs)

            extracted[engine_name] = extracted_text

        return extracted

    def _extract_keywords(self, title: str, outline: str) -> List[str]:
        """
        从标题和大纲提取关键词。

        Args:
            title: 章节标题
            outline: 章节大纲

        Returns:
            关键词列表
        """
        text = f"{title} {outline}"

        if JIEBA_AVAILABLE:
            # 使用 jieba 分词
            words = jieba.cut(text)
            keywords = [
                w.strip() for w in words
                if len(w.strip()) >= 2 and w.strip() not in self.STOP_WORDS
            ]
        else:
            # 简单分词：按空格和标点分割
            words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
            keywords = [
                w for w in words
                if len(w) >= 2 and w not in self.STOP_WORDS
            ]

        # 去重并保持顺序
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    def _split_paragraphs(self, text: str) -> List[str]:
        """
        将文本分割为段落。

        Args:
            text: 原始文本

        Returns:
            段落列表
        """
        # 按双换行符分割
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _calculate_match_score(self, paragraph: str, keywords: List[str]) -> int:
        """
        计算段落与关键词的匹配度。

        Args:
            paragraph: 段落文本
            keywords: 关键词列表

        Returns:
            匹配分数（匹配的关键词数量）
        """
        para_lower = paragraph.lower()
        score = sum(1 for kw in keywords if kw.lower() in para_lower)
        return score


__all__ = ["ReportCompressor"]
