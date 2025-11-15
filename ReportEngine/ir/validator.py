"""
章节级JSON结构校验器。

LLM按章节生成IR后，需要在落盘与装订前经过严格校验，以避免
渲染期的结构性崩溃。本模块实现轻量级的Python校验逻辑，
无需依赖jsonschema库即可快速定位错误。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .schema import ALLOWED_BLOCK_TYPES, ALLOWED_INLINE_MARKS, IR_VERSION


class IRValidator:
    """
    章节IR结构校验器。

    说明：
        - validate_chapter返回(是否通过, 错误列表)
        - 错误定位采用path语法，便于快速追踪
        - 内置对heading/paragraph/list/table等所有区块的细粒度校验
    """

    def __init__(self, schema_version: str = IR_VERSION):
        """记录当前Schema版本，便于未来多版本并存"""
        self.schema_version = schema_version

    # ======== 对外接口 ========

    def validate_chapter(self, chapter: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """校验单个章节对象的必填字段与block结构"""
        errors: List[str] = []
        if not isinstance(chapter, dict):
            return False, ["chapter必须是对象"]

        for field in ("chapterId", "title", "anchor", "order", "blocks"):
            if field not in chapter:
                errors.append(f"missing chapter.{field}")

        if not isinstance(chapter.get("blocks"), list) or not chapter.get("blocks"):
            errors.append("chapter.blocks必须是非空数组")
            return False, errors

        blocks = chapter.get("blocks", [])
        for idx, block in enumerate(blocks):
            self._validate_block(block, f"blocks[{idx}]", errors)

        return len(errors) == 0, errors

    # ======== 内部工具 ========

    def _validate_block(self, block: Any, path: str, errors: List[str]):
        """根据block类型调用不同的校验器"""
        if not isinstance(block, dict):
            errors.append(f"{path} 必须是对象")
            return

        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            errors.append(f"{path}.type 不被支持: {block_type}")
            return

        validator = getattr(self, f"_validate_{block_type}_block", None)
        if validator:
            validator(block, path, errors)

    def _validate_heading_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """heading必须有level/text/anchor"""
        if "level" not in block or not isinstance(block["level"], int):
            errors.append(f"{path}.level 必须是整数")
        if "text" not in block:
            errors.append(f"{path}.text 缺失")
        if "anchor" not in block:
            errors.append(f"{path}.anchor 缺失")

    def _validate_paragraph_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """paragraph需要非空inlines，并逐条校验"""
        inlines = block.get("inlines")
        if not isinstance(inlines, list) or not inlines:
            errors.append(f"{path}.inlines 必须是非空数组")
            return
        for idx, run in enumerate(inlines):
            self._validate_inline_run(run, f"{path}.inlines[{idx}]", errors)

    def _validate_list_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """列表需要声明listType且每个item都是block数组"""
        if block.get("listType") not in {"ordered", "bullet", "task"}:
            errors.append(f"{path}.listType 取值非法")
        items = block.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.items 必须是非空列表")
            return
        for i, item in enumerate(items):
            if not isinstance(item, list):
                errors.append(f"{path}.items[{i}] 必须是区块数组")
                continue
            for j, sub_block in enumerate(item):
                self._validate_block(sub_block, f"{path}.items[{i}][{j}]", errors)

    def _validate_table_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """表格需提供rows/cells/blocks，递归校验单元格内容"""
        rows = block.get("rows")
        if not isinstance(rows, list) or not rows:
            errors.append(f"{path}.rows 必须是非空数组")
            return
        for r_idx, row in enumerate(rows):
            cells = row.get("cells") if isinstance(row, dict) else None
            if not isinstance(cells, list) or not cells:
                errors.append(f"{path}.rows[{r_idx}].cells 必须是非空数组")
                continue
            for c_idx, cell in enumerate(cells):
                if not isinstance(cell, dict):
                    errors.append(f"{path}.rows[{r_idx}].cells[{c_idx}] 必须是对象")
                    continue
                blocks = cell.get("blocks")
                if not isinstance(blocks, list) or not blocks:
                    errors.append(
                        f"{path}.rows[{r_idx}].cells[{c_idx}].blocks 必须是非空数组"
                    )
                    continue
                for b_idx, sub_block in enumerate(blocks):
                    self._validate_block(
                        sub_block,
                        f"{path}.rows[{r_idx}].cells[{c_idx}].blocks[{b_idx}]",
                        errors,
                    )

    def _validate_blockquote_block(
        self, block: Dict[str, Any], path: str, errors: List[str]
    ):
        """引用块内部需要至少一个子block"""
        inner = block.get("blocks")
        if not isinstance(inner, list) or not inner:
            errors.append(f"{path}.blocks 必须是非空数组")
            return
        for idx, sub_block in enumerate(inner):
            self._validate_block(sub_block, f"{path}.blocks[{idx}]", errors)

    def _validate_callout_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """callout需声明tone，并至少有一个子block"""
        tone = block.get("tone")
        if tone not in {"info", "warning", "success", "danger"}:
            errors.append(f"{path}.tone 取值非法: {tone}")
        blocks = block.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{path}.blocks 必须是非空数组")
            return
        for idx, sub_block in enumerate(blocks):
            self._validate_block(sub_block, f"{path}.blocks[{idx}]", errors)

    def _validate_kpiGrid_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """KPI卡需要非空items，每项包含label/value"""
        items = block.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.items 必须是非空数组")
            return
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{path}.items[{idx}] 必须是对象")
                continue
            if "label" not in item or "value" not in item:
                errors.append(f"{path}.items[{idx}] 需要label与value")

    def _validate_widget_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """widget必须声明widgetId/type，并提供数据或数据引用"""
        if "widgetId" not in block:
            errors.append(f"{path}.widgetId 缺失")
        if "widgetType" not in block:
            errors.append(f"{path}.widgetType 缺失")
        if "data" not in block and "dataRef" not in block:
            errors.append(f"{path} 需要 data 或 dataRef 其一")

    def _validate_code_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """code block至少要有content"""
        if "content" not in block:
            errors.append(f"{path}.content 缺失")

    def _validate_math_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """数学块要求latex字段"""
        if "latex" not in block:
            errors.append(f"{path}.latex 缺失")

    def _validate_figure_block(
        self, block: Dict[str, Any], path: str, errors: List[str]
    ):
        """figure需要img对象且至少带src"""
        img = block.get("img")
        if not isinstance(img, dict):
            errors.append(f"{path}.img 必须是对象")
            return
        if "src" not in img:
            errors.append(f"{path}.img.src 缺失")

    def _validate_inline_run(
        self, run: Any, path: str, errors: List[str]
    ):
        """校验paragraph中的inline run与marks合法性"""
        if not isinstance(run, dict):
            errors.append(f"{path} 必须是对象")
            return
        if "text" not in run:
            errors.append(f"{path}.text 缺失")
        marks = run.get("marks", [])
        if marks is None:
            return
        if not isinstance(marks, list):
            errors.append(f"{path}.marks 必须是数组")
            return
        for m_idx, mark in enumerate(marks):
            if not isinstance(mark, dict):
                errors.append(f"{path}.marks[{m_idx}] 必须是对象")
                continue
            m_type = mark.get("type")
            if m_type not in ALLOWED_INLINE_MARKS:
                errors.append(f"{path}.marks[{m_idx}].type 不被支持: {m_type}")


__all__ = ["IRValidator"]
