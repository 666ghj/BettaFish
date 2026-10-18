"""
图表审查服务 - 统一管理图表验证和修复。

提供单例服务，确保所有渲染器共享修复状态，避免重复修复。
修复成功后可自动持久化到 IR 文件。

线程安全说明：
- 验证器和修复器实例是无状态的，可安全共享
- 每次 review_document 调用会创建独立的 ReviewSession
- 统计信息通过 ReviewSession 返回，避免并发竞争
"""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ReportEngine.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    ValidationResult,
    create_chart_validator,
    create_chart_repairer
)
from ReportEngine.utils.chart_repair_api import create_llm_repair_functions
from common.provenance.validators import gate_chart_revision


@dataclass
class ReviewStats:
    """
    图表审查统计信息 - 每次审查会话独立的统计数据。

    通过为每次 review_document 调用创建独立的 ReviewStats 实例，
    避免多线程并发时的统计数据竞争问题。
    """
    total: int = 0
    valid: int = 0
    repaired_locally: int = 0
    repaired_api: int = 0
    failed: int = 0

    def to_dict(self) -> Dict[str, int]:
        """转换为字典格式"""
        return {
            'total': self.total,
            'valid': self.valid,
            'repaired_locally': self.repaired_locally,
            'repaired_api': self.repaired_api,
            'failed': self.failed
        }

    @property
    def repaired_total(self) -> int:
        """修复总数"""
        return self.repaired_locally + self.repaired_api


class ChartReviewService:
    """
    图表审查服务 - 单例模式。

    职责：
    1. 统一管理图表验证和修复
    2. 维护修复缓存，避免重复修复
    3. 支持修复后自动持久化到 IR 文件
    4. 提供统计信息（通过 ReviewStats 返回，线程安全）

    线程安全说明：
    - validator 和 repairer 是无状态的，可安全共享
    - 每次 review_document 调用创建独立的 ReviewStats
    - 不再使用全局 _stats，避免并发竞争
    """

    _instance: Optional["ChartReviewService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ChartReviewService":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化服务（仅首次调用时执行）"""
        if self._initialized:
            return

        self._initialized = True

        # 初始化验证器和修复器（无状态，可安全共享）
        self.validator = create_chart_validator()
        self.llm_repair_fns = create_llm_repair_functions()
        self.repairer = create_chart_repairer(
            validator=self.validator,
            llm_repair_fns=self.llm_repair_fns
        )

        # 打印 LLM 修复函数状态
        if not self.llm_repair_fns:
            logger.warning("ChartReviewService: 未配置任何 LLM API，图表 API 修复功能不可用")
        else:
            logger.info(f"ChartReviewService: 已配置 {len(self.llm_repair_fns)} 个 LLM 修复函数")

        # 最后一次审查的统计信息（仅用于向后兼容，不推荐在并发场景使用）
        # 新代码应使用 review_document 返回的 ReviewStats
        self._last_stats: Optional[ReviewStats] = None
        self._last_stats_lock = threading.Lock()

        logger.info("ChartReviewService 初始化完成")

    def reset_stats(self) -> None:
        """
        重置统计信息（向后兼容，不推荐使用）。

        注意：此方法仅用于向后兼容。在并发场景下，
        应使用 review_document 返回的 ReviewStats 对象。
        """
        with self._last_stats_lock:
            self._last_stats = None

    @property
    def stats(self) -> Dict[str, int]:
        """
        获取最后一次审查的统计信息副本（向后兼容）。

        警告：在并发场景下，此属性可能返回其他线程的统计结果。
        推荐使用 review_document 返回的 ReviewStats 对象。

        返回:
            Dict[str, int]: 统计信息字典副本
        """
        with self._last_stats_lock:
            if self._last_stats is None:
                return {
                    'total': 0,
                    'valid': 0,
                    'repaired_locally': 0,
                    'repaired_api': 0,
                    'failed': 0
                }
            return self._last_stats.to_dict()

    def review_document(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: Optional[str | Path] = None,
        *,
        reset_stats: bool = True,
        save_on_repair: bool = True
    ) -> ReviewStats:
        """
        审查并修复文档中的所有图表。

        遍历所有章节的 blocks，检测图表类型的 widget，
        对未审查过的图表进行验证和修复。

        线程安全：每次调用创建独立的 ReviewStats，避免并发竞争。

        参数:
            document_ir: Document IR 数据
            ir_file_path: IR 文件路径，如果提供且有修复，会自动保存
            reset_stats: 保留参数以保持向后兼容，不再有实际作用
            save_on_repair: 修复后是否自动保存到文件

        返回:
            ReviewStats: 本次审查的统计信息（线程安全）
        """
        # 每次调用创建独立的统计对象，避免并发竞争
        session_stats = ReviewStats()

        if not document_ir:
            logger.warning("ChartReviewService: document_ir 为空，跳过审查")
            # 更新 _last_stats 以保持向后兼容
            with self._last_stats_lock:
                self._last_stats = session_stats
            return session_stats

        has_repairs = False

        # 遍历所有章节
        for chapter in document_ir.get("chapters", []) or []:
            if not isinstance(chapter, dict):
                continue
            blocks = chapter.get("blocks", [])
            if isinstance(blocks, list):
                chapter_repairs = self._walk_and_review_blocks(blocks, chapter, session_stats)
                if chapter_repairs:
                    has_repairs = True

        # 输出统计信息
        self._log_stats(session_stats)

        # 更新 _last_stats 以保持向后兼容
        with self._last_stats_lock:
            self._last_stats = session_stats

        # 如果有修复且提供了文件路径，保存到文件
        if has_repairs and ir_file_path and save_on_repair:
            self._save_ir_to_file(document_ir, ir_file_path)

        return session_stats

    def _walk_and_review_blocks(
        self,
        blocks: List[Any],
        chapter_context: Dict[str, Any] | None,
        session_stats: ReviewStats
    ) -> bool:
        """
        递归遍历 blocks 并审查图表。

        参数:
            blocks: 要遍历的 block 列表
            chapter_context: 章节上下文
            session_stats: 本次审查会话的统计对象

        返回:
            bool: 是否有修复发生
        """
        has_repairs = False

        for block in blocks or []:
            if not isinstance(block, dict):
                continue

            # 检查是否是图表 widget
            if block.get("type") == "widget":
                repaired = self._review_chart_block(block, chapter_context, session_stats)
                if repaired:
                    has_repairs = True

            # 递归处理嵌套的 blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                if self._walk_and_review_blocks(nested_blocks, chapter_context, session_stats):
                    has_repairs = True

            # 处理 list 类型的 items
            if block.get("type") == "list":
                for item in block.get("items", []):
                    if isinstance(item, list):
                        if self._walk_and_review_blocks(item, chapter_context, session_stats):
                            has_repairs = True

            # 处理 table 类型的 cells
            if block.get("type") == "table":
                for row in block.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    for cell in row.get("cells", []):
                        if isinstance(cell, dict):
                            cell_blocks = cell.get("blocks", [])
                            if isinstance(cell_blocks, list):
                                if self._walk_and_review_blocks(cell_blocks, chapter_context, session_stats):
                                    has_repairs = True

        return has_repairs

    def _review_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None,
        session_stats: ReviewStats
    ) -> bool:
        """
        审查单个图表 block。

        参数:
            block: 要审查的 block
            chapter_context: 章节上下文
            session_stats: 本次审查会话的统计对象

        返回:
            bool: 是否进行了修复
        """
        widget_type = block.get("widgetType", "")
        if not isinstance(widget_type, str):
            return False

        # 只处理 chart.js 类型（词云单独处理，不需要修复）
        is_chart = widget_type.startswith("chart.js")
        is_wordcloud = "wordcloud" in widget_type.lower()

        if not is_chart:
            return False

        widget_id = block.get("widgetId", "unknown")

        # 检查是否已审查过
        if block.get("_chart_reviewed"):
            logger.debug(f"图表 {widget_id} 已审查过，跳过")
            return False

        session_stats.total += 1

        # 词云直接标记为有效
        if is_wordcloud:
            session_stats.valid += 1
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "valid"
            block["_chart_review_method"] = "none"
            return False

        # 先进行数据规范化（从章节上下文补充数据）
        self._normalize_chart_block(block, chapter_context)

        # 验证图表
        validation_result = self.validator.validate(block)

        if validation_result.is_valid:
            # 验证通过
            session_stats.valid += 1
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "valid"
            block["_chart_review_method"] = "none"
            if validation_result.warnings:
                logger.debug(f"图表 {widget_id} 验证通过，但有警告: {validation_result.warnings}")
            return False

        # 验证失败，尝试修复
        logger.warning(f"图表 {widget_id} 验证失败: {validation_result.errors}")

        original = copy.deepcopy(block)
        repair_result = self.repairer.repair(copy.deepcopy(original), validation_result)

        repaired_block = (
            gate_chart_revision(original, repair_result.repaired_block)
            if repair_result.success and repair_result.repaired_block else None
        )
        if repaired_block is not None:
            # 修复成功，覆盖原始 block 数据
            # 保留原始的一些元信息
            original_widget_id = block.get("widgetId")
            block.clear()
            block.update(repaired_block)
            # 确保 widgetId 不丢失
            if original_widget_id and not block.get("widgetId"):
                block["widgetId"] = original_widget_id

            method = repair_result.method or "local"
            if method == "local":
                session_stats.repaired_locally += 1
            elif method == "api":
                session_stats.repaired_api += 1

            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "repaired"
            block["_chart_review_method"] = method

            logger.info(f"图表 {widget_id} 修复成功 (方法: {method}): {repair_result.changes}")
            return True

        # 修复失败
        session_stats.failed += 1
        block["_chart_reviewed"] = True
        block["_chart_renderable"] = False
        block["_chart_review_status"] = "failed"
        block["_chart_review_method"] = "none"
        block["_chart_error_reason"] = self._format_error_reason(validation_result)

        logger.warning(f"图表 {widget_id} 修复失败，已标记为不可渲染")
        return False

    def _normalize_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None = None
    ) -> None:
        """
        规范化图表数据，补全缺失字段（如props、scales、datasets），提升容错性。

        与 HTMLRenderer._normalize_chart_block() 保持一致：
        - 确保 props 存在
        - 将顶层 scales 合并进 props.options
        - 确保 data 存在
        - 尝试使用章节级 data 作为兜底
        - 自动生成 labels
        """
        if not isinstance(block, dict):
            return

        if block.get("type") != "widget":
            return

        widget_type = block.get("widgetType", "")
        if not (isinstance(widget_type, str) and widget_type.startswith("chart.js")):
            return

        original = copy.deepcopy(block)

        # 确保 props 存在
        props = block.get("props")
        if not isinstance(props, dict):
            block["props"] = {}
            props = block["props"]

        # 将顶层 scales 合并进 options，避免配置丢失
        scales = block.get("scales")
        if isinstance(scales, dict):
            options = props.get("options") if isinstance(props.get("options"), dict) else {}
            props["options"] = self._merge_dicts(options, {"scales": scales})

        # 确保 data 存在
        data = block.get("data")
        if not isinstance(data, dict):
            data = {}
            block["data"] = data

        # 如果 datasets 为空，尝试使用章节级 data 填充
        if chapter_context and self._is_chart_data_empty(data):
            chapter_data = chapter_context.get("data") if isinstance(chapter_context, dict) else None
            if isinstance(chapter_data, dict):
                fallback_ds = chapter_data.get("datasets")
                if isinstance(fallback_ds, list) and len(fallback_ds) > 0:
                    merged_data = copy.deepcopy(data)
                    merged_data["datasets"] = copy.deepcopy(fallback_ds)

                    if not merged_data.get("labels") and isinstance(chapter_data.get("labels"), list):
                        merged_data["labels"] = copy.deepcopy(chapter_data["labels"])

                    block["data"] = merged_data

        # 若仍缺少 labels 且数据点包含 x 值，自动生成便于 fallback 和坐标刻度
        data_ref = block.get("data")
        if isinstance(data_ref, dict) and not data_ref.get("labels"):
            datasets_ref = data_ref.get("datasets")
            if isinstance(datasets_ref, list) and datasets_ref:
                first_ds = datasets_ref[0]
                ds_data = first_ds.get("data") if isinstance(first_ds, dict) else None
                if isinstance(ds_data, list):
                    labels_from_data = []
                    for idx, point in enumerate(ds_data):
                        if isinstance(point, dict):
                            label_text = point.get("x") or point.get("label") or f"点{idx + 1}"
                        else:
                            label_text = f"点{idx + 1}"
                        labels_from_data.append(str(label_text))

                    if labels_from_data:
                        data_ref["labels"] = labels_from_data

        if gate_chart_revision(original, block) is None:
            block.clear()
            block.update(original)

    @staticmethod
    def _is_chart_data_empty(data: Dict[str, Any] | None) -> bool:
        """检查图表数据是否为空或缺少有效 datasets"""
        if not isinstance(data, dict):
            return True

        datasets = data.get("datasets")
        if not isinstance(datasets, list) or len(datasets) == 0:
            return True

        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            series = ds.get("data")
            if isinstance(series, list) and len(series) > 0:
                return False

        return True

    @staticmethod
    def _merge_dicts(
        base: Dict[str, Any] | None, override: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        递归合并两个字典，override 覆盖 base，均为新副本，避免副作用。
        """
        result = copy.deepcopy(base) if isinstance(base, dict) else {}
        if not isinstance(override, dict):
            return result
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ChartReviewService._merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _format_error_reason(self, validation_result: ValidationResult | None) -> str:
        """格式化错误原因"""
        if not validation_result:
            return "未知错误"
        errors = validation_result.errors or []
        if not errors:
            return "验证失败但无具体错误信息"
        return "; ".join(errors[:3])

    def _log_stats(self, stats: ReviewStats) -> None:
        """输出统计信息"""
        if stats.total == 0:
            logger.debug("ChartReviewService: 没有图表需要审查")
            return

        logger.info(
            f"ChartReviewService 图表审查完成: "
            f"总计 {stats.total} 个, "
            f"有效 {stats.valid} 个, "
            f"修复 {stats.repaired_total} 个 (本地 {stats.repaired_locally}, API {stats.repaired_api}), "
            f"失败 {stats.failed} 个"
        )

    # 内部元数据键，不应保存到 IR 文件
    _INTERNAL_METADATA_KEYS = frozenset([
        "_chart_reviewed",
        "_chart_renderable",
        "_chart_review_status",
        "_chart_review_method",
        "_chart_error_reason",
    ])

    def _strip_internal_metadata(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        移除文档中所有内部元数据键，返回干净的副本用于持久化。

        这些内部标记仅用于渲染过程的状态跟踪，不应保存到 IR 文件中，
        以避免污染文档结构和导致重复使用时的不一致行为。
        """
        cleaned = copy.deepcopy(document_ir)

        def strip_from_block(block: Dict[str, Any]) -> None:
            """递归移除 block 及其嵌套结构中的内部元数据"""
            if not isinstance(block, dict):
                return

            # 移除当前 block 的内部键
            for key in self._INTERNAL_METADATA_KEYS:
                block.pop(key, None)

            # 递归处理嵌套的 blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                for nested in nested_blocks:
                    strip_from_block(nested)

            # 处理 list 类型的 items
            if block.get("type") == "list":
                for item in block.get("items", []):
                    if isinstance(item, list):
                        for sub_block in item:
                            strip_from_block(sub_block)

            # 处理 table 类型的 cells
            if block.get("type") == "table":
                for row in block.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    for cell in row.get("cells", []):
                        if isinstance(cell, dict):
                            cell_blocks = cell.get("blocks", [])
                            if isinstance(cell_blocks, list):
                                for cell_block in cell_blocks:
                                    strip_from_block(cell_block)

        # 处理所有章节
        for chapter in cleaned.get("chapters", []) or []:
            if not isinstance(chapter, dict):
                continue
            blocks = chapter.get("blocks", [])
            if isinstance(blocks, list):
                for block in blocks:
                    strip_from_block(block)

        return cleaned

    def _save_ir_to_file(self, document_ir: Dict[str, Any], file_path: str | Path) -> None:
        """保存 IR 到文件（移除内部元数据后）"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # 移除内部元数据键，保持 IR 文件干净
            cleaned_ir = self._strip_internal_metadata(document_ir)

            path.write_text(
                json.dumps(cleaned_ir, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"ChartReviewService: 修复后的 IR 已保存到 {path}")
        except Exception as e:
            logger.exception(f"ChartReviewService: 保存 IR 文件失败: {e}")


# 全局单例实例
_chart_review_service: Optional[ChartReviewService] = None


def get_chart_review_service() -> ChartReviewService:
    """获取 ChartReviewService 单例实例"""
    global _chart_review_service
    if _chart_review_service is None:
        _chart_review_service = ChartReviewService()
    return _chart_review_service


def review_document_charts(
    document_ir: Dict[str, Any],
    ir_file_path: Optional[str | Path] = None,
    *,
    reset_stats: bool = True,
    save_on_repair: bool = True
) -> ReviewStats:
    """
    便捷函数：审查并修复文档中的所有图表。

    参数:
        document_ir: Document IR 数据
        ir_file_path: IR 文件路径，如果提供且有修复，会自动保存
        reset_stats: 保留参数以保持向后兼容，不再有实际作用
        save_on_repair: 修复后是否自动保存到文件

    返回:
        ReviewStats: 本次审查的统计信息
    """
    service = get_chart_review_service()
    return service.review_document(
        document_ir,
        ir_file_path,
        reset_stats=reset_stats,
        save_on_repair=save_on_repair
    )


__all__ = [
    "ChartReviewService",
    "ReviewStats",
    "get_chart_review_service",
    "review_document_charts",
]

