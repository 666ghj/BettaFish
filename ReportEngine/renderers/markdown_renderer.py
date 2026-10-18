from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ReportEngine.utils.chart_review_service import get_chart_review_service
from common.provenance.citation_service import CitationService


class MarkdownRenderer:
    """
    将 Document IR 转为 Markdown。

    - 图表与词云统一降级为数据表格，避免丢失关键信息；
    - 尽量保留通用特性（标题、列表、代码、表格、引用等）；
    - 对不常见特性（callout/kpiGrid/engineQuote等）使用近似替换。
    """

    def __init__(self) -> None:
        self.document: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.citation_service = CitationService()

    def render(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: str | None = None
    ) -> str:
        """
        入口：将IR转换为Markdown字符串。

        参数:
            document_ir: Document IR 数据
            ir_file_path: 可选，IR 文件路径，提供时修复后会自动保存

        返回:
            str: Markdown 字符串
        """
        self.document = document_ir or {}

        # 使用统一的 ChartReviewService 进行图表审查与修复
        # 虽然 Markdown 渲染时图表会降级为表格，但仍需确保数据有效
        # review_document 返回本次会话的统计信息（线程安全，此处不使用）
        chart_service = get_chart_review_service()
        _ = chart_service.review_document(
            self.document,
            ir_file_path=ir_file_path,
            reset_stats=True,
            save_on_repair=bool(ir_file_path)
        )

        self.metadata = self.document.get("metadata", {}) or {}
        self.citation_service = CitationService(self.document.get("provenanceBundle"))

        parts: List[str] = []
        title = self.metadata.get("title") or self.metadata.get("query") or "报告"
        if title:
            parts.append(f"# {self._escape_text(title)}")
            parts.append("")

        for chapter in self.document.get("chapters", []) or []:
            chapter_md = self._render_chapter(chapter)
            if chapter_md:
                parts.append(chapter_md)

        return "\n".join(part for part in parts if part is not None).strip()

    # ===== 章节与块级渲染 =====

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        lines: List[str] = []
        title = chapter.get("title") or chapter.get("chapterId")
        blocks = chapter.get("blocks", []) if isinstance(chapter.get("blocks"), list) else []

        # 章节标题使用一级标题格式，并避免与首个heading重复
        if title:
            lines.append(f"# {self._escape_text(title)}")
            lines.append("")

        if blocks and self._is_heading_duplicate(blocks[0], title):
            blocks = blocks[1:]

        body = self._render_blocks(blocks)
        if body:
            lines.append(body)
        return "\n".join(lines).strip()

    def _render_blocks(self, blocks: List[Dict[str, Any]] | None, join_with_blank: bool = True) -> str:
        rendered: List[str] = []
        for block in blocks or []:
            md = self._render_block(block)
            if md is None:
                continue
            md = md.strip()
            if md:
                rendered.append(md)
        if not rendered:
            return ""
        separator = "\n\n" if join_with_blank else "\n"
        return separator.join(rendered)

    def _render_block(self, block: Any) -> str:
        if block is None:
            return ""
        if isinstance(block, str):
            return self._escape_text(block)
        if not isinstance(block, dict):
            return ""

        block_type = block.get("type") or ("paragraph" if block.get("inlines") else None)
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "list": self._render_list,
            "table": self._render_table,
            "swotTable": self._render_swot_table,
            "pestTable": self._render_pest_table,
            "blockquote": self._render_blockquote,
            "engineQuote": self._render_engine_quote,
            "hr": lambda b: "---",
            "code": self._render_code,
            "math": self._render_math,
            "figure": self._render_figure,
            "callout": self._render_callout,
            "kpiGrid": self._render_kpi_grid,
            "widget": self._render_widget,
            "toc": lambda b: "",
        }
        if block_type in handlers:
            rendered = handlers[block_type](block)
            return self._append_block_provenance(rendered, block)

        if isinstance(block.get("blocks"), list):
            return self._render_blocks(block["blocks"])

        return self._append_block_provenance(self._fallback_unknown(block), block)

    def _append_block_provenance(self, rendered: str, block: Dict[str, Any]) -> str:
        """Append citations attached to a rich block instead of a child paragraph."""
        if not rendered or block.get("type") == "paragraph":
            return rendered
        provenance = f"{self._render_claim_label(block)}{self._render_citations(block).strip()}".strip()
        if not provenance:
            return rendered
        return f"{rendered}\n\n{provenance}"

    def _render_heading(self, block: Dict[str, Any]) -> str:
        level = block.get("level", 2)
        level = max(1, min(6, level))
        hashes = "#" * level
        text = block.get("text") or ""
        subtitle = block.get("subtitle")
        subtitle_text = f" _{self._escape_text(subtitle)}_" if subtitle else ""
        heading_line = f"{hashes} {self._escape_text(text)}{subtitle_text}"
        # 章节内的一级标题前额外插入一个空行（不影响文档题目）
        if level == 1:
            return f"\n\n\n\n\n{heading_line}"
        return heading_line

    def _render_paragraph(self, block: Dict[str, Any], for_table: bool = False) -> str:
        inlines = block.get("inlines", [])
        # 与 HTML/PDF 输出一致，隐藏旧 IR 中无主张、无引用的证据占位段落。
        if (
            block.get("support_status") == "unsupported"
            and not block.get("claims")
            and not block.get("citation_refs")
        ):
            return ""
        # 检测并跳过包含文档元数据 JSON 的段落
        if self._is_metadata_paragraph(inlines):
            return ""
        text = self._render_inlines(inlines, for_table=for_table)
        return f"{self._render_claim_label(block)}{text}{self._render_citations(block, for_table=for_table)}"

    @staticmethod
    def _render_claim_label(block: Dict[str, Any]) -> str:
        claim_types = {
            str(item.get("claim_type") or "")
            for item in block.get("claims", []) or []
            if isinstance(item, dict)
        }
        if "prediction" in claim_types:
            return "**[预测]** "
        if "recommendation" in claim_types:
            return "**[建议]** "
        if block.get("support_status") == "weak":
            return "**[弱支持]** "
        return ""

    def _render_citations(self, block: Dict[str, Any], for_table: bool = False) -> str:
        fragments: List[str] = []
        for detail in self.citation_service.details_for_block(block):
            number = int(detail["number"])
            url = str(detail.get("url") or "")
            title = str(detail.get("title") or "未命名来源").replace('"', "'")
            if for_table:
                url = url.replace("|", "%7C")
                title = self._escape_text(title, for_table=True)
            if url.lower().startswith(("http://", "https://")):
                fragments.append(f' [[{number}]]({url} "{title}")')
                continue
            lineage = self.citation_service.internal_lineage_text(detail)
            if for_table:
                lineage = self._escape_text(lineage, for_table=True)
            fragments.append(f" [{number}]（内部数据：{lineage}）")
        return "".join(fragments)

    def _is_metadata_paragraph(self, inlines: List[Any]) -> bool:
        """
        检测段落是否只包含文档元数据 JSON。
        
        某些 LLM 生成的内容会将元数据（如 xrefs、widgets、footnotes、metadata）
        错误地作为段落内容输出，本方法识别并标记这种情况以便跳过渲染。
        """
        if not inlines or len(inlines) != 1:
            return False
        first = inlines[0]
        if not isinstance(first, dict):
            return False
        text = first.get("text", "")
        if not isinstance(text, str):
            return False
        text = text.strip()
        if not text.startswith("{") or not text.endswith("}"):
            return False
        # 检测典型的元数据键
        metadata_indicators = ['"xrefs"', '"widgets"', '"footnotes"', '"metadata"', '"sectionBudgets"']
        return any(indicator in text for indicator in metadata_indicators)

    def _render_list(self, block: Dict[str, Any]) -> str:
        list_type = block.get("listType", "bullet")
        items = block.get("items") or []
        lines: List[str] = []
        for idx, item_blocks in enumerate(items):
            prefix = "-"
            if list_type == "ordered":
                prefix = f"{idx + 1}."
            elif list_type == "task":
                prefix = "- [ ]"
            content = self._render_blocks(item_blocks, join_with_blank=False)
            if not content:
                continue
            content_lines = content.splitlines() or [""]
            first = content_lines[0]
            lines.append(f"{prefix} {first}")
            for cont in content_lines[1:]:
                lines.append(f"  {cont}")
        return "\n".join(lines)

    def _flatten_nested_cells(self, cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        展平错误嵌套的单元格结构。

        某些 LLM 生成的表格数据中，单元格被错误地递归嵌套：
        cells[0] 正常, cells[1].cells[0] 正常, cells[1].cells[1].cells[0] 正常...
        本方法将这种嵌套结构展平为标准的平行单元格数组。

        参数:
            cells: 可能包含嵌套结构的单元格数组。

        返回:
            List[Dict]: 展平后的单元格数组。
        """
        if not cells:
            return []

        flattened: List[Dict[str, Any]] = []

        def _extract_cells(cell_or_list: Any) -> None:
            """递归提取所有单元格"""
            if not isinstance(cell_or_list, dict):
                return

            # 如果当前对象有 blocks，说明它是一个有效的单元格
            if "blocks" in cell_or_list:
                # 创建单元格副本，移除嵌套的 cells
                clean_cell = {
                    k: v for k, v in cell_or_list.items()
                    if k != "cells"
                }
                flattened.append(clean_cell)

            # 如果当前对象有嵌套的 cells，递归处理
            nested_cells = cell_or_list.get("cells")
            if isinstance(nested_cells, list):
                for nested_cell in nested_cells:
                    _extract_cells(nested_cell)

        for cell in cells:
            _extract_cells(cell)

        return flattened

    def _fix_nested_table_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        修复嵌套错误的表格行结构。

        某些 LLM 生成的表格数据中，所有行的单元格都被嵌套在第一行中，
        导致表格只有1行但包含所有数据。本方法检测并修复这种情况。

        参数:
            rows: 原始的表格行数组。

        返回:
            List[Dict]: 修复后的表格行数组。
        """
        if not rows or len(rows) != 1:
            # 只处理只有1行的异常情况
            return rows

        first_row = rows[0]
        original_cells = first_row.get("cells", [])

        # 检查是否存在嵌套结构
        has_nested = any(
            isinstance(cell.get("cells"), list)
            for cell in original_cells
            if isinstance(cell, dict)
        )

        if not has_nested:
            return rows

        # 展平所有单元格
        all_cells = self._flatten_nested_cells(original_cells)

        if len(all_cells) <= 2:
            # 单元格太少，不需要重组
            return rows

        # 辅助函数：获取单元格文本
        def _get_cell_text(cell: Dict[str, Any]) -> str:
            """获取单元格的文本内容"""
            blocks = cell.get("blocks", [])
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        if isinstance(inline, dict):
                            text = inline.get("text", "")
                            if text:
                                return str(text).strip()
            return ""

        def _is_placeholder_cell(cell: Dict[str, Any]) -> bool:
            """判断单元格是否是占位符（如 '--', '-', '—' 等）"""
            text = _get_cell_text(cell)
            return text in ("--", "-", "—", "——", "", "N/A", "n/a")

        # 先过滤掉占位符单元格
        all_cells = [c for c in all_cells if not _is_placeholder_cell(c)]

        if len(all_cells) <= 2:
            return rows

        # 检测表头列数：查找带有 bold 标记或典型表头词的单元格
        def _is_header_cell(cell: Dict[str, Any]) -> bool:
            """判断单元格是否像表头（有加粗标记或是典型表头词）"""
            blocks = cell.get("blocks", [])
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        if isinstance(inline, dict):
                            marks = inline.get("marks", [])
                            if any(isinstance(m, dict) and m.get("type") == "bold" for m in marks):
                                return True
            # 也检查典型的表头词
            text = _get_cell_text(cell)
            header_keywords = {
                "时间", "日期", "名称", "类型", "状态", "数量", "金额", "比例", "指标",
                "平台", "渠道", "来源", "描述", "说明", "备注", "序号", "编号",
                "事件", "关键", "数据", "支撑", "反应", "市场", "情感", "节点",
                "维度", "要点", "详情", "标签", "影响", "趋势", "权重", "类别",
                "信息", "内容", "风格", "偏好", "主要", "用户", "核心", "特征",
                "分类", "范围", "对象", "项目", "阶段", "周期", "频率", "等级",
            }
            return any(kw in text for kw in header_keywords) and len(text) <= 20

        # 计算表头列数：统计连续的表头单元格数量
        header_count = 0
        for cell in all_cells:
            if _is_header_cell(cell):
                header_count += 1
            else:
                # 遇到第一个非表头单元格，说明数据区开始
                break

        # 如果没有检测到表头，尝试使用启发式方法
        if header_count == 0:
            # 假设列数为 4 或 5（常见的表格列数）
            total = len(all_cells)
            for possible_cols in [4, 5, 3, 6, 2]:
                if total % possible_cols == 0:
                    header_count = possible_cols
                    break
            else:
                # 尝试找到最接近的能整除的列数
                for possible_cols in [4, 5, 3, 6, 2]:
                    remainder = total % possible_cols
                    # 允许最多3个多余的单元格（可能是尾部的总结或注释）
                    if remainder <= 3:
                        header_count = possible_cols
                        break
                else:
                    # 无法确定列数，返回原始数据
                    return rows

        # 计算有效的单元格数量（可能需要截断尾部多余的单元格）
        total = len(all_cells)
        remainder = total % header_count
        if remainder > 0 and remainder <= 3:
            # 截断尾部多余的单元格（可能是总结或注释）
            all_cells = all_cells[:total - remainder]
        elif remainder > 3:
            # 余数太大，可能列数检测错误，返回原始数据
            return rows

        # 重新组织成多行
        fixed_rows: List[Dict[str, Any]] = []
        for i in range(0, len(all_cells), header_count):
            row_cells = all_cells[i:i + header_count]
            # 标记第一行为表头
            if i == 0:
                for cell in row_cells:
                    cell["header"] = True
            fixed_rows.append({"cells": row_cells})

        return fixed_rows

    def _render_table(self, block: Dict[str, Any]) -> str:
        raw_rows = block.get("rows") or []
        if not raw_rows:
            return ""

        # 先修复可能存在的嵌套行结构问题
        rows = self._fix_nested_table_rows(raw_rows)

        header_cells: List[str] = []
        body_rows: List[List[str]] = []

        # 展平可能存在的嵌套单元格结构（作为额外保护）
        first_row_cells_raw = rows[0].get("cells") if isinstance(rows[0], dict) else None
        first_row_cells = self._flatten_nested_cells(first_row_cells_raw) if first_row_cells_raw else None

        # 检测首行是否声明为表头
        has_header = bool(first_row_cells and any(cell.get("header") or cell.get("isHeader") for cell in first_row_cells))

        # 计算最大列数，忽略rowspan
        col_count = 0
        for row in rows:
            cells_raw = row.get("cells") if isinstance(row, dict) else None
            cells = self._flatten_nested_cells(cells_raw) if cells_raw else []
            span = 0
            for cell in cells:
                span += int(cell.get("colspan") or 1)
            col_count = max(col_count, span)

        if has_header and first_row_cells:
            header_cells = [self._render_cell_content(cell) for cell in first_row_cells]
            rows = rows[1:]
        else:
            header_cells = [f"列{idx + 1}" for idx in range(col_count or (len(first_row_cells or []) or 1))]

        for row in rows:
            if not isinstance(row, dict):
                continue
            cells_raw = row.get("cells") or []
            # 展平可能存在的嵌套单元格结构
            cells = self._flatten_nested_cells(cells_raw)
            row_cells: List[str] = []
            for cell in cells:
                text = self._render_cell_content(cell)
                span = int(cell.get("colspan") or 1)
                row_cells.append(text)
                if span > 1:
                    row_cells.extend([""] * (span - 1))
            while len(row_cells) < len(header_cells):
                row_cells.append("")
            body_rows.append(row_cells[: len(header_cells)])

        lines = [
            self._markdown_row(header_cells),
            self._markdown_separator(len(header_cells)),
        ]
        for row in body_rows:
            lines.append(self._markdown_row(row))
        return "\n".join(lines)

    def _render_swot_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "SWOT 分析"
        summary = block.get("summary")
        quadrants = [
            ("strengths", "S 优势"),
            ("weaknesses", "W 劣势"),
            ("opportunities", "O 机会"),
            ("threats", "T 威胁"),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in quadrants:
            items = self._normalize_swot_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> 暂无数据")
                continue
            table_lines = [
                self._markdown_row(["序号", "要点", "详情", "标签"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or item.get("evidence") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "未命名要点", for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_pest_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "PEST 分析"
        summary = block.get("summary")
        dimensions = [
            ("political", "P 政治"),
            ("economic", "E 经济"),
            ("social", "S 社会"),
            ("technological", "T 技术"),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in dimensions:
            items = self._normalize_pest_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> 暂无数据")
                continue
            table_lines = [
                self._markdown_row(["序号", "要点", "详情", "标签"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("weight"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "未命名要点", for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_blockquote(self, block: Dict[str, Any]) -> str:
        inner = self._render_blocks(block.get("blocks", []))
        return self._quote_lines(inner)

    def _render_engine_quote(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or block.get("engine") or "引用"
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}**"
        return self._quote_lines(f"{header}\n{inner}" if inner else header)

    def _render_code(self, block: Dict[str, Any]) -> str:
        lang = block.get("lang") or ""
        content = block.get("content") or ""
        return f"```{lang}\n{content}\n```"

    def _render_math(self, block: Dict[str, Any]) -> str:
        latex = self._normalize_math(block.get("latex", ""))
        if not latex:
            return ""
        return f"$$\n{latex}\n$$"

    def _render_figure(self, block: Dict[str, Any]) -> str:
        caption = block.get("caption") or "图像内容占位"
        return f"> ![图示占位]({''}) {self._escape_text(caption)}"

    def _render_callout(self, block: Dict[str, Any]) -> str:
        tone = block.get("tone") or "info"
        title = block.get("title")
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}** [{tone}]" if title else f"[{tone}]"
        content = header if not inner else f"{header}\n{inner}"
        return self._quote_lines(content)

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        items = block.get("items") or []
        if not items:
            return ""
        header = ["指标", "数值", "变化"]
        lines = [self._markdown_row(header), self._markdown_separator(len(header))]
        for item in items:
            label = item.get("label") or ""
            value = f"{item.get('value', '')}{item.get('unit') or ''}"
            delta = self._format_delta(item.get("delta"), item.get("deltaTone"))
            lines.append(self._markdown_row([
                self._escape_text(label, for_table=True),
                self._escape_text(value, for_table=True),
                self._escape_text(delta, for_table=True),
            ]))
        return "\n".join(lines)

    def _render_widget(self, block: Dict[str, Any]) -> str:
        widget_type = (block.get("widgetType") or "").lower()
        title = block.get("title") or (block.get("props", {}) or {}).get("title")
        title_prefix = f"**{self._escape_text(title)}**\n\n" if title else ""

        if widget_type.startswith("chart.js"):
            chart_table = self._render_chart_as_table(block)
            return f"{title_prefix}{chart_table}".strip()
        if "wordcloud" in widget_type:
            cloud_table = self._render_wordcloud_as_table(block)
            return f"{title_prefix}{cloud_table}".strip()

        data_preview = ""
        try:
            data_preview = json.dumps(block.get("data") or {}, ensure_ascii=False)[:200]
        except Exception:
            data_preview = ""
        note = "> 数据组件暂不支持Markdown渲染"
        return f"{title_prefix}{note}" + (f"\n\n```\n{data_preview}\n```" if data_preview else "")

    # ===== 工具方法 =====

    def _render_chart_as_table(self, block: Dict[str, Any]) -> str:
        data = self._coerce_chart_data(block.get("data") or {})
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return "> 图表数据缺失，无法转为表格"

        headers = ["类别"] + [
            ds.get("label") or f"系列{idx + 1}"
            for idx, ds in enumerate(datasets)
        ]
        lines = [self._markdown_row(headers), self._markdown_separator(len(headers))]
        for idx, label in enumerate(labels):
            row_cells = [self._escape_text(self._stringify_value(label), for_table=True)]
            for ds in datasets:
                series = ds.get("data") or []
                value = series[idx] if idx < len(series) else ""
                row_cells.append(self._escape_text(self._stringify_value(value), for_table=True))
            lines.append(self._markdown_row(row_cells))
        return "\n".join(lines)

    def _render_wordcloud_as_table(self, block: Dict[str, Any]) -> str:
        items = self._collect_wordcloud_items(block)
        if not items:
            return "> 词云数据缺失，无法转为表格"

        lines = [
            self._markdown_row(["关键词", "权重", "类别"]),
            self._markdown_separator(3),
        ]
        for item in items:
            lines.append(
                self._markdown_row([
                    self._escape_text(item.get("word", ""), for_table=True),
                    self._escape_text(self._stringify_value(item.get("weight")), for_table=True),
                    self._escape_text(item.get("category", "") or "-", for_table=True),
                ])
            )
        return "\n".join(lines)

    def _render_cell_content(self, cell: Dict[str, Any]) -> str:
        blocks = cell.get("blocks") if isinstance(cell, dict) else None
        return self._render_blocks_as_text(blocks)

    def _render_blocks_as_text(self, blocks: List[Dict[str, Any]] | None) -> str:
        texts: List[str] = []
        for block in blocks or []:
            texts.append(self._render_block_as_text(block))
        return " ".join(filter(None, texts))

    def _render_block_as_text(self, block: Any) -> str:
        if isinstance(block, str):
            return self._escape_text(block, for_table=True)
        if not isinstance(block, dict):
            return ""
        block_type = block.get("type")
        if block_type == "paragraph":
            return self._render_paragraph(block, for_table=True)
        if block_type == "heading":
            text = self._escape_text(block.get("text") or "", for_table=True)
        elif block_type == "list":
            items = []
            for sub in block.get("items") or []:
                items.append(self._render_blocks_as_text(sub))
            text = "; ".join(filter(None, items))
        elif block_type == "math":
            text = f"${self._normalize_math(block.get('latex', ''))}$"
        elif block_type == "code":
            text = block.get("content", "") or ""
        elif block_type == "widget":
            text = self._escape_text(block.get("title") or "图表", for_table=True)
        elif isinstance(block.get("blocks"), list):
            text = self._render_blocks_as_text(block.get("blocks"))
        else:
            text = self._escape_text(str(block), for_table=True)
        if not text:
            return ""
        return f"{self._render_claim_label(block)}{text}{self._render_citations(block, for_table=True)}"

    def _markdown_row(self, cells: List[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    def _markdown_separator(self, count: int) -> str:
        return "| " + " | ".join(["---"] * max(1, count)) + " |"

    def _render_inlines(self, inlines: List[Any], for_table: bool = False) -> str:
        parts: List[str] = []
        for run in inlines or []:
            parts.append(self._render_inline_run(run, for_table=for_table))
        return "".join(parts)

    def _render_inline_run(self, run: Any, for_table: bool = False) -> str:
        if isinstance(run, dict):
            # 处理 inlineRun 类型：嵌套的 inlines 数组
            if run.get("type") == "inlineRun":
                inner_inlines = run.get("inlines") or []
                outer_marks = run.get("marks") or []
                # 递归渲染内部的 inlines
                inner_text = self._render_inlines(inner_inlines, for_table=for_table)
                # 应用外层的 marks
                result = inner_text
                for mark in outer_marks:
                    result = self._apply_mark(result, mark)
                return result
            text = run.get("text", "")
            marks = run.get("marks") or []
        else:
            text = run if isinstance(run, str) else ""
            marks = []
        
        # 尝试检测并解析被错误序列化为字符串的 inlineRun JSON
        if isinstance(text, str) and text.startswith('{"type": "inlineRun"'):
            parsed = self._try_parse_inline_run_string(text)
            if parsed:
                return self._render_inline_run(parsed, for_table=for_table)
        
        result = self._escape_text(text, for_table=for_table)
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            mtype = mark.get("type")
            if mtype == "bold":
                result = f"**{result}**"
            elif mtype == "italic":
                result = f"*{result}*"
            elif mtype == "underline":
                result = f"__{result}__"
            elif mtype == "strike":
                result = f"~~{result}~~"
            elif mtype == "code":
                result = f"`{result}`"
            elif mtype == "link":
                href = mark.get("href") or mark.get("value")
                href = str(href) if href else ""
                result = f"[{result}]({href})" if href else result
            elif mtype == "highlight":
                result = f"=={result}=="
            elif mtype == "subscript":
                result = f"~{result}~"
            elif mtype == "superscript":
                result = f"^{result}^"
            elif mtype == "math":
                latex = self._normalize_math(mark.get("value") or text)
                result = f"${latex}$" if latex else result
            # 颜色/字体等非通用标记直接降级为纯文本
        return result

    def _apply_mark(self, text: str, mark: Any) -> str:
        """
        对文本应用单个 mark 格式。
        
        用于处理 inlineRun 类型的外层 marks。
        """
        if not isinstance(mark, dict):
            return text
        mtype = mark.get("type")
        if mtype == "bold":
            return f"**{text}**"
        elif mtype == "italic":
            return f"*{text}*"
        elif mtype == "underline":
            return f"__{text}__"
        elif mtype == "strike":
            return f"~~{text}~~"
        elif mtype == "code":
            return f"`{text}`"
        elif mtype == "link":
            href = mark.get("href") or mark.get("value")
            href = str(href) if href else ""
            return f"[{text}]({href})" if href else text
        elif mtype == "highlight":
            return f"=={text}=="
        elif mtype == "subscript":
            return f"~{text}~"
        elif mtype == "superscript":
            return f"^{text}^"
        elif mtype == "math":
            latex = self._normalize_math(mark.get("value") or text)
            return f"${latex}$" if latex else text
        return text

    def _try_parse_inline_run_string(self, text: str) -> dict | None:
        """
        尝试解析被错误序列化为字符串的 inlineRun JSON。
        
        某些 LLM 生成的内容会将 inlineRun 结构意外地作为字符串
        存入 text 字段，本方法尝试识别并解析这种情况。
        
        参数:
            text: 可能包含 JSON 的字符串
            
        返回:
            dict | None: 解析成功返回 inlineRun 字典，否则返回 None
        """
        if not text or not isinstance(text, str):
            return None
        text = text.strip()
        if not text.startswith('{"type": "inlineRun"'):
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "inlineRun":
                return parsed
        except json.JSONDecodeError:
            pass
        return None

    def _is_heading_duplicate(self, block: Dict[str, Any], chapter_title: str | None) -> bool:
        """判断首个heading是否与章节标题重复"""
        if not isinstance(block, dict) or block.get("type") != "heading":
            return False
        if not chapter_title:
            return False
        heading_text = block.get("text") or ""
        return self._normalize_heading_text(heading_text) == self._normalize_heading_text(chapter_title)

    def _normalize_heading_text(self, text: Any) -> str:
        """去除序号前缀并统一空白"""
        if not isinstance(text, str):
            return ""
        stripped = text.strip()
        # 去掉类似“1.”、“1.1”、“一、”
        for sep in (" ", "、"):
            if sep in stripped:
                maybe_prefix, rest = stripped.split(sep, 1)
                if self._looks_like_prefix(maybe_prefix):
                    stripped = rest.strip()
                    break
        else:
            parts = stripped.split(".", 1)
            if len(parts) == 2 and self._looks_like_prefix(parts[0]):
                stripped = parts[1].strip()
        return stripped

    @staticmethod
    def _looks_like_prefix(token: str) -> bool:
        """判断token是否像序号前缀"""
        if not token:
            return False
        if token.isdigit():
            return True
        chinese_numerals = set("一二三四五六七八九十零〇壹贰叁肆伍陆柒捌玖拾")
        return all(ch in chinese_numerals or ch == "." for ch in token)

    def _quote_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            prefix = "> " if line else ">"
            lines.append(f"{prefix}{line}")
        return "\n".join(lines)

    def _normalize_swot_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                impact = entry.get("impact")
                priority = entry.get("priority")
                evidence = entry.get("evidence")
                items.append({
                    "title": title or "未命名要点",
                    "detail": detail,
                    "impact": impact,
                    "priority": priority,
                    "evidence": evidence,
                })
        return items

    def _normalize_pest_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                items.append({
                    "title": title or "未命名要点",
                    "detail": detail,
                    "impact": entry.get("impact"),
                    "priority": entry.get("priority"),
                    "weight": entry.get("weight"),
                })
        return items

    def _coerce_chart_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if "labels" in data or "datasets" in data:
            return data
        for key in ("data", "chartData", "payload"):
            nested = data.get(key)
            if isinstance(nested, dict) and ("labels" in nested or "datasets" in nested):
                return nested
        return data

    def _collect_wordcloud_items(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        props = block.get("props") or {}
        candidates: List[Any] = []
        for key in ("data", "words", "items"):
            value = props.get(key)
            if isinstance(value, list):
                candidates.append(value)
        data_field = block.get("data")
        if isinstance(data_field, list):
            candidates.append(data_field)
        elif isinstance(data_field, dict):
            if isinstance(data_field.get("items"), list):
                candidates.append(data_field.get("items"))
            if isinstance(data_field.get("words"), list):
                candidates.append(data_field.get("words"))

        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def push(word: str, weight: Any, category: str) -> None:
            key = f"{word}::{category}"
            if key in seen:
                return
            seen.add(key)
            items.append({"word": word, "weight": weight, "category": category})

        for candidate in candidates:
            for entry in candidate or []:
                if isinstance(entry, dict):
                    word = entry.get("word") or entry.get("text") or entry.get("label")
                    if not word:
                        continue
                    weight = entry.get("weight") or entry.get("value")
                    category = entry.get("category") or ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, (list, tuple)) and entry:
                    word = entry[0]
                    weight = entry[1] if len(entry) > 1 else ""
                    category = entry[2] if len(entry) > 2 else ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, str):
                    push(entry, "", "")
        return items

    def _escape_text(self, text: Any, for_table: bool = False) -> str:
        if text is None:
            return ""
        value = str(text)
        if for_table:
            value = value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")
        return value.strip()

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, dict):
            # 优先取常见数值字段
            for key in ("y", "value"):
                if key in value:
                    return str(value[key])
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        if isinstance(value, list):
            return ", ".join(self._stringify_value(v) for v in value)
        return str(value)

    def _normalize_math(self, raw: Any) -> str:
        if not isinstance(raw, str):
            return ""
        text = raw.strip()
        patterns = [
            ("$$", "$$"),
            ("\\[", "\\]"),
            ("\\(", "\\)"),
        ]
        for start, end in patterns:
            if text.startswith(start) and text.endswith(end):
                return text[len(start) : -len(end)].strip()
        return text

    def _format_delta(self, delta: Any, tone: Any) -> str:
        if delta is None:
            return ""
        prefix = ""
        tone_val = (tone or "").lower()
        if tone_val in ("up", "increase", "positive"):
            prefix = "▲ "
        elif tone_val in ("down", "decrease", "negative"):
            prefix = "▼ "
        return f"{prefix}{delta}"

    def _fallback_unknown(self, block: Dict[str, Any]) -> str:
        try:
            payload = json.dumps(block, ensure_ascii=False, indent=2)
        except Exception:
            payload = str(block)
        logger.debug(f"未识别的区块类型，使用JSON兜底: {block}")
        return f"```json\n{payload}\n```"


__all__ = ["MarkdownRenderer"]
