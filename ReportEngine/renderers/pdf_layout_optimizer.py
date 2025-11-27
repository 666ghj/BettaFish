"""
PDF布局优化器

自动分析和优化PDF布局，确保内容不溢出、排版美观。
支持：
- 自动调整字号
- 优化行间距
- 调整色块大小
- 智能排列信息块
- 保存和加载优化方案
- 文本宽度检测和溢出预防
- 色块边界检测和自动调整
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger


@dataclass
class KPICardLayout:
    """KPI卡片布局配置"""
    font_size_value: int = 32  # 数值字号
    font_size_label: int = 14  # 标签字号
    font_size_change: int = 13  # 变化值字号
    padding: int = 20  # 内边距
    min_height: int = 120  # 最小高度
    value_max_length: int = 10  # 数值最大字符数（超过则缩小字号）


@dataclass
class CalloutLayout:
    """提示框布局配置"""
    font_size_title: int = 16  # 标题字号
    font_size_content: int = 14  # 内容字号
    padding: int = 20  # 内边距
    line_height: float = 1.6  # 行高倍数
    max_width: str = "100%"  # 最大宽度


@dataclass
class TableLayout:
    """表格布局配置"""
    font_size_header: int = 13  # 表头字号
    font_size_body: int = 12  # 表体字号
    cell_padding: int = 12  # 单元格内边距
    max_cell_width: int = 200  # 最大单元格宽度（像素）
    overflow_strategy: str = "wrap"  # 溢出策略：wrap(换行) / ellipsis(省略号)


@dataclass
class ChartLayout:
    """图表布局配置"""
    font_size_title: int = 16  # 图表标题字号
    font_size_label: int = 12  # 标签字号
    min_height: int = 300  # 最小高度
    max_height: int = 600  # 最大高度
    padding: int = 20  # 内边距


@dataclass
class GridLayout:
    """网格布局配置"""
    columns: int = 3  # 每行列数（正文默认三列）
    gap: int = 20  # 间距
    responsive_breakpoint: int = 768  # 响应式断点（宽度）


@dataclass
class DataBlockLayout:
    """数据块（色块、KPI、表格等）的缩放配置"""
    overview_text_scale: float = 0.93  # 文章总览数据块文字缩放（轻微缩小）
    overview_kpi_scale: float = 0.88  # 总览KPI缩放
    body_text_scale: float = 0.8      # 正文数据块文字缩放（大幅缩小）
    body_kpi_scale: float = 0.76      # 正文KPI缩放
    min_overview_font: int = 12       # 总览最小字号
    min_body_font: int = 11           # 正文最小字号


@dataclass
class PageLayout:
    """页面整体布局配置"""
    font_size_base: int = 14  # 基础字号
    font_size_h1: int = 28  # 一级标题
    font_size_h2: int = 24  # 二级标题
    font_size_h3: int = 20  # 三级标题
    font_size_h4: int = 16  # 四级标题
    line_height: float = 1.6  # 行高倍数
    paragraph_spacing: int = 16  # 段落间距
    section_spacing: int = 32  # 章节间距
    page_padding: int = 40  # 页面边距
    max_content_width: int = 800  # 最大内容宽度


@dataclass
class PDFLayoutConfig:
    """完整的PDF布局配置"""
    page: PageLayout
    kpi_card: KPICardLayout
    callout: CalloutLayout
    table: TableLayout
    chart: ChartLayout
    grid: GridLayout
    data_block: DataBlockLayout

    # 优化策略配置
    auto_adjust_font_size: bool = True  # 自动调整字号
    auto_adjust_grid_columns: bool = True  # 自动调整网格列数
    prevent_orphan_headers: bool = True  # 防止标题孤行
    optimize_for_print: bool = True  # 打印优化

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'page': asdict(self.page),
            'kpi_card': asdict(self.kpi_card),
            'callout': asdict(self.callout),
            'table': asdict(self.table),
            'chart': asdict(self.chart),
            'grid': asdict(self.grid),
            'data_block': asdict(self.data_block),
            'auto_adjust_font_size': self.auto_adjust_font_size,
            'auto_adjust_grid_columns': self.auto_adjust_grid_columns,
            'prevent_orphan_headers': self.prevent_orphan_headers,
            'optimize_for_print': self.optimize_for_print,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PDFLayoutConfig:
        """从字典创建配置"""
        return cls(
            page=PageLayout(**data['page']),
            kpi_card=KPICardLayout(**data['kpi_card']),
            callout=CalloutLayout(**data['callout']),
            table=TableLayout(**data['table']),
            chart=ChartLayout(**data['chart']),
            grid=GridLayout(**data['grid']),
            data_block=DataBlockLayout(**data.get('data_block', {})),
            auto_adjust_font_size=data.get('auto_adjust_font_size', True),
            auto_adjust_grid_columns=data.get('auto_adjust_grid_columns', True),
            prevent_orphan_headers=data.get('prevent_orphan_headers', True),
            optimize_for_print=data.get('optimize_for_print', True),
        )


class PDFLayoutOptimizer:
    """
    PDF布局优化器

    根据内容特征自动优化PDF布局，防止溢出和排版问题。
    """

    # 字符宽度估算系数（基于常见中文字体）
    # 中文字符通常是等宽的，约等于字号的像素值
    # 英文和数字约为字号的0.5-0.6倍
    # 更新：使用更精确的系数以更好地预测溢出
    CHAR_WIDTH_FACTOR = {
        'chinese': 1.05,     # 中文字符（略微增加以确保安全边界）
        'english': 0.58,     # 英文字母
        'number': 0.65,      # 数字（数字通常比字母稍宽）
        'symbol': 0.45,      # 符号
        'percent': 0.7,      # 百分号等特殊符号
    }

    def __init__(self, config: Optional[PDFLayoutConfig] = None):
        """
        初始化优化器

        参数:
            config: 布局配置，如果为None则使用默认配置
        """
        self.config = config or self._create_default_config()
        self.optimization_log = []

    @staticmethod
    def _create_default_config() -> PDFLayoutConfig:
        """创建默认配置"""
        return PDFLayoutConfig(
            page=PageLayout(),
            kpi_card=KPICardLayout(),
            callout=CalloutLayout(),
            table=TableLayout(),
            chart=ChartLayout(),
            grid=GridLayout(),
            data_block=DataBlockLayout(),
        )

    def optimize_for_document(self, document_ir: Dict[str, Any]) -> PDFLayoutConfig:
        """
        根据文档IR内容优化布局配置

        参数:
            document_ir: Document IR数据

        返回:
            PDFLayoutConfig: 优化后的布局配置
        """
        logger.info("开始分析文档并优化布局...")

        # 分析文档结构
        stats = self._analyze_document(document_ir)

        # 根据分析结果调整配置
        optimized_config = self._adjust_config_based_on_stats(stats)

        # 记录优化日志
        self._log_optimization(stats, optimized_config)

        return optimized_config

    def _analyze_document(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析文档内容特征

        返回统计信息：
        - kpi_count: KPI卡片数量
        - table_count: 表格数量
        - chart_count: 图表数量
        - max_kpi_value_length: 最长KPI数值长度
        - max_table_columns: 最多表格列数
        - total_content_length: 总内容长度
        - hero_kpi_count: Hero区域的KPI数量
        - max_hero_kpi_value_length: Hero区域最长KPI数值长度
        """
        stats = {
            'kpi_count': 0,
            'table_count': 0,
            'chart_count': 0,
            'callout_count': 0,
            'max_kpi_value_length': 0,
            'max_table_columns': 0,
            'max_table_rows': 0,
            'total_content_length': 0,
            'has_long_text': False,
            'hero_kpi_count': 0,
            'max_hero_kpi_value_length': 0,
        }

        # 分析hero区域的KPI
        metadata = document_ir.get('metadata', {})
        hero = metadata.get('hero', {})
        if hero:
            hero_kpis = hero.get('kpis', [])
            stats['hero_kpi_count'] = len(hero_kpis)
            for kpi in hero_kpis:
                value = str(kpi.get('value', ''))
                stats['max_hero_kpi_value_length'] = max(
                    stats['max_hero_kpi_value_length'],
                    len(value)
                )

        # 优先使用chapters，fallback到sections
        chapters = document_ir.get('chapters', [])
        if not chapters:
            chapters = document_ir.get('sections', [])

        # 遍历章节
        for chapter in chapters:
            self._analyze_chapter(chapter, stats)

        logger.info(f"文档分析完成: {stats}")
        return stats

    def _analyze_chapter(self, chapter: Dict[str, Any], stats: Dict[str, Any]):
        """分析单个章节"""
        # 分析章节中的blocks
        blocks = chapter.get('blocks', [])
        for block in blocks:
            self._analyze_block(block, stats)

        # 递归处理子章节（如果有）
        children = chapter.get('children', [])
        for child in children:
            if isinstance(child, dict):
                self._analyze_chapter(child, stats)

    def _analyze_block(self, block: Dict[str, Any], stats: Dict[str, Any]):
        """分析单个block节点"""
        if not isinstance(block, dict):
            return

        node_type = block.get('type')

        if node_type == 'kpiGrid':
            kpis = block.get('items', [])
            stats['kpi_count'] += len(kpis)

            # 检查KPI数值长度
            for kpi in kpis:
                value = str(kpi.get('value', ''))
                stats['max_kpi_value_length'] = max(
                    stats['max_kpi_value_length'],
                    len(value)
                )

        elif node_type == 'table':
            stats['table_count'] += 1

            # 分析表格结构
            headers = block.get('headers', [])
            rows = block.get('rows', [])
            if rows and isinstance(rows[0], dict):
                # 从第一行的cells计算列数
                cells = rows[0].get('cells', [])
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(cells)
                )
            else:
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(headers)
                )
            stats['max_table_rows'] = max(
                stats['max_table_rows'],
                len(rows)
            )

        elif node_type == 'chart' or node_type == 'widget':
            stats['chart_count'] += 1

        elif node_type == 'callout':
            stats['callout_count'] += 1
            # 检查callout中的blocks
            callout_blocks = block.get('blocks', [])
            for cb in callout_blocks:
                if isinstance(cb, dict) and cb.get('type') == 'paragraph':
                    text = self._extract_text_from_paragraph(cb)
                    if len(text) > 200:
                        stats['has_long_text'] = True

        elif node_type == 'paragraph':
            text = self._extract_text_from_paragraph(block)
            stats['total_content_length'] += len(text)
            if len(text) > 500:
                stats['has_long_text'] = True

        # 递归处理嵌套的blocks
        nested_blocks = block.get('blocks', [])
        if nested_blocks:
            for nested in nested_blocks:
                self._analyze_block(nested, stats)

    def _extract_text_from_paragraph(self, paragraph: Dict[str, Any]) -> str:
        """从paragraph block中提取纯文本"""
        text_parts = []
        inlines = paragraph.get('inlines', [])
        for inline in inlines:
            if isinstance(inline, dict):
                text = inline.get('text', '')
                if text:
                    text_parts.append(str(text))
            elif isinstance(inline, str):
                text_parts.append(inline)
        return ''.join(text_parts)

    def _analyze_section(self, section: Dict[str, Any], stats: Dict[str, Any]):
        """递归分析章节（保留用于向后兼容）"""
        # 这个方法保留用于向后兼容，实际上调用_analyze_chapter
        self._analyze_chapter(section, stats)

    def _estimate_text_width(self, text: str, font_size: int) -> float:
        """
        估算文本的像素宽度

        参数:
            text: 要测量的文本
            font_size: 字号（像素）

        返回:
            float: 估算的宽度（像素）
        """
        if not text:
            return 0.0

        width = 0.0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                width += font_size * self.CHAR_WIDTH_FACTOR['chinese']
            elif char.isalpha():
                width += font_size * self.CHAR_WIDTH_FACTOR['english']
            elif char.isdigit():
                width += font_size * self.CHAR_WIDTH_FACTOR['number']
            elif char in '%％':  # 百分号
                width += font_size * self.CHAR_WIDTH_FACTOR['percent']
            else:
                width += font_size * self.CHAR_WIDTH_FACTOR['symbol']

        return width

    def _check_text_overflow(self, text: str, font_size: int, max_width: int) -> bool:
        """
        检查文本是否会溢出

        参数:
            text: 要检查的文本
            font_size: 字号（像素）
            max_width: 最大宽度（像素）

        返回:
            bool: True表示会溢出
        """
        estimated_width = self._estimate_text_width(text, font_size)
        return estimated_width > max_width

    def _calculate_safe_font_size(
        self,
        text: str,
        max_width: int,
        min_font_size: int = 10,
        max_font_size: int = 32
    ) -> Tuple[int, bool]:
        """
        计算安全的字号以避免溢出

        参数:
            text: 要显示的文本
            max_width: 最大宽度（像素）
            min_font_size: 最小字号
            max_font_size: 最大字号

        返回:
            Tuple[int, bool]: (建议字号, 是否需要调整)
        """
        if not text:
            return max_font_size, False

        # 从最大字号开始尝试
        for font_size in range(max_font_size, min_font_size - 1, -1):
            if not self._check_text_overflow(text, font_size, max_width):
                # 如果需要缩小字号
                needs_adjustment = font_size < max_font_size
                return font_size, needs_adjustment

        # 如果连最小字号都溢出，返回最小字号并标记需要调整
        return min_font_size, True

    def _detect_kpi_overflow_issues(self, stats: Dict[str, Any]) -> List[str]:
        """
        检测KPI卡片可能的溢出问题

        参数:
            stats: 文档统计信息

        返回:
            List[str]: 检测到的问题列表
        """
        issues = []

        # KPI卡片的典型宽度（像素）
        # 基于2列布局，容器宽度800px，间距20px
        kpi_card_width = (800 - 20) // 2 - 40  # 减去padding

        # 检查最长KPI数值
        max_kpi_length = stats.get('max_kpi_value_length', 0)
        if max_kpi_length > 0:
            # 假设一个很长的数值
            sample_text = '1' * max_kpi_length + '亿元'
            current_font_size = self.config.kpi_card.font_size_value

            if self._check_text_overflow(sample_text, current_font_size, kpi_card_width):
                issues.append(
                    f"KPI数值过长({max_kpi_length}字符)，"
                    f"字号{current_font_size}px可能导致溢出"
                )

        return issues

    def _adjust_config_based_on_stats(
        self,
        stats: Dict[str, Any]
    ) -> PDFLayoutConfig:
        """根据统计信息调整配置"""
        config = PDFLayoutConfig(
            page=PageLayout(**asdict(self.config.page)),
            kpi_card=KPICardLayout(**asdict(self.config.kpi_card)),
            callout=CalloutLayout(**asdict(self.config.callout)),
            table=TableLayout(**asdict(self.config.table)),
            chart=ChartLayout(**asdict(self.config.chart)),
            grid=GridLayout(**asdict(self.config.grid)),
            data_block=DataBlockLayout(**asdict(self.config.data_block)),
            auto_adjust_font_size=self.config.auto_adjust_font_size,
            auto_adjust_grid_columns=self.config.auto_adjust_grid_columns,
            prevent_orphan_headers=self.config.prevent_orphan_headers,
            optimize_for_print=self.config.optimize_for_print,
        )

        # 检测KPI溢出问题
        overflow_issues = self._detect_kpi_overflow_issues(stats)
        if overflow_issues:
            for issue in overflow_issues:
                logger.warning(f"检测到布局问题: {issue}")

        # KPI卡片宽度（像素）- 更保守的计算，留出更多安全边界
        kpi_card_width = (800 - 20) // 2 - 60  # 2列布局，增加边距以防溢出

        # 优先处理Hero区域的KPI（如果有的话）
        if stats['hero_kpi_count'] > 0 and stats['max_hero_kpi_value_length'] > 0:
            # Hero区域的KPI卡片宽度通常更窄
            hero_kpi_width = 250  # Hero侧边栏的典型宽度
            sample_text = '9' * stats['max_hero_kpi_value_length'] + '元'
            safe_font_size, needs_adjustment = self._calculate_safe_font_size(
                sample_text,
                hero_kpi_width,
                min_font_size=14,
                max_font_size=24  # Hero KPI字号通常较小
            )

            if needs_adjustment or stats['max_hero_kpi_value_length'] > 6:
                # Hero KPI需要更保守的字号
                config.kpi_card.font_size_value = max(14, safe_font_size - 2)
                self.optimization_log.append(
                    f"Hero KPI数值较长({stats['max_hero_kpi_value_length']}字符)，"
                    f"字号调整为{config.kpi_card.font_size_value}px"
                )

        # 根据KPI数值长度智能调整字号
        if stats['max_kpi_value_length'] > 0:
            # 创建示例文本进行测试 - 使用实际可能的字符组合
            sample_text = '9' * stats['max_kpi_value_length'] + '亿'  # 加上可能的单位
            safe_font_size, needs_adjustment = self._calculate_safe_font_size(
                sample_text,
                kpi_card_width,
                min_font_size=16,  # 降低最小字号以确保不溢出
                max_font_size=28   # 降低最大字号以更保守
            )

            if needs_adjustment:
                config.kpi_card.font_size_value = safe_font_size
                # 进一步降低以留出安全边界
                config.kpi_card.font_size_value = max(16, safe_font_size - 2)
                self.optimization_log.append(
                    f"KPI数值过长({stats['max_kpi_value_length']}字符)，"
                    f"字号自动调整为{config.kpi_card.font_size_value}px以防止溢出"
                )
            elif stats['max_kpi_value_length'] > 8:
                # 对于较长文本，更保守地调整
                config.kpi_card.font_size_value = min(24, safe_font_size)
                self.optimization_log.append(
                    f"KPI数值较长({stats['max_kpi_value_length']}字符)，"
                    f"预防性调整字号为{config.kpi_card.font_size_value}px"
                )

        # 收紧KPI字号上限，为正文数据块缩放留出空间
        base = config.page.font_size_base
        kpi_value_cap = max(base + 6, 20)
        kpi_label_cap = max(base - 1, 12)
        kpi_change_cap = max(base, 12)

        original_value = config.kpi_card.font_size_value
        original_label = config.kpi_card.font_size_label
        original_change = config.kpi_card.font_size_change

        config.kpi_card.font_size_value = min(original_value, kpi_value_cap)
        config.kpi_card.font_size_value = max(config.kpi_card.font_size_value, base + 1)
        config.kpi_card.font_size_label = min(original_label, kpi_label_cap)
        config.kpi_card.font_size_label = max(config.kpi_card.font_size_label, 12)
        config.kpi_card.font_size_change = min(original_change, kpi_change_cap)
        config.kpi_card.font_size_change = max(config.kpi_card.font_size_change, 12)
        self.optimization_log.append(
            f"KPI字号上限收紧：数值{original_value}px→{config.kpi_card.font_size_value}px，"
            f"标签{original_label}px→{config.kpi_card.font_size_label}px，"
            f"变动{original_change}px→{config.kpi_card.font_size_change}px"
        )

        total_blocks = (stats['kpi_count'] + stats['table_count'] +
                        stats['chart_count'] + stats['callout_count'])

        # 分开收紧文章总览与正文数据块的文字
        if stats['hero_kpi_count'] >= 3 or stats['max_hero_kpi_value_length'] > 6:
            prev = config.data_block.overview_kpi_scale
            config.data_block.overview_kpi_scale = min(prev, 0.86)
            if config.data_block.overview_kpi_scale != prev:
                self.optimization_log.append(
                    f"文章总览KPI较密集，缩放系数 {prev:.2f}→{config.data_block.overview_kpi_scale:.2f}"
                )

        if stats['has_long_text'] or stats['max_table_columns'] > 6:
            prev_text = config.data_block.body_text_scale
            prev_kpi = config.data_block.body_kpi_scale
            config.data_block.body_text_scale = min(prev_text, 0.78)
            config.data_block.body_kpi_scale = min(prev_kpi, 0.74)
            self.optimization_log.append(
                f"正文数据块紧缩：长文本/宽表触发，文字缩放至{config.data_block.body_text_scale*100:.0f}%，"
                f"KPI缩放至{config.data_block.body_kpi_scale*100:.0f}%"
            )
        elif total_blocks > 16:
            prev_text = config.data_block.body_text_scale
            prev_kpi = config.data_block.body_kpi_scale
            config.data_block.body_text_scale = min(prev_text, 0.80)
            config.data_block.body_kpi_scale = min(prev_kpi, 0.75)
            self.optimization_log.append(
                f"正文数据块缩放：内容块较多({total_blocks}个)，文字缩放至{config.data_block.body_text_scale*100:.0f}%，"
                f"KPI缩放至{config.data_block.body_kpi_scale*100:.0f}%"
            )
        elif total_blocks > 10:
            prev_text = config.data_block.body_text_scale
            config.data_block.body_text_scale = min(prev_text, 0.82)
            if config.data_block.body_text_scale != prev_text:
                self.optimization_log.append(
                    f"正文数据块轻量缩放({total_blocks}个块)，文字缩放系数 {prev_text:.2f}→{config.data_block.body_text_scale:.2f}"
                )

        # 根据KPI数量调整间距但保持正文默认三列装订
        config.grid.columns = 3
        if stats['kpi_count'] > 6:
            config.kpi_card.min_height = 100
            config.kpi_card.padding = 14  # 缩小padding以节省空间
            config.grid.gap = 16  # 减小间距
            self.optimization_log.append(
                f"KPI卡片较多({stats['kpi_count']}个)，"
                f"保持三列布局并缩小内边距和间距"
            )
        elif stats['kpi_count'] > 4:
            config.kpi_card.padding = 16
            config.grid.gap = 18
            self.optimization_log.append(
                f"KPI卡片适中({stats['kpi_count']}个)，保持三列布局并适度调整间距"
            )
        elif stats['kpi_count'] <= 2:
            config.kpi_card.padding = 22  # 较少卡片时增加padding
            config.grid.gap = 20
            self.optimization_log.append(
                f"KPI卡片较少({stats['kpi_count']}个)，"
                f"保持三列布局并增加内边距"
            )

        # 根据表格列数调整字号和间距
        if stats['max_table_columns'] > 8:
            config.table.font_size_header = 10
            config.table.font_size_body = 9
            config.table.cell_padding = 6
            self.optimization_log.append(
                f"表格列数很多({stats['max_table_columns']}列)，"
                f"大幅缩小字号和内边距"
            )
        elif stats['max_table_columns'] > 6:
            config.table.font_size_header = 11
            config.table.font_size_body = 10
            config.table.cell_padding = 8
            self.optimization_log.append(
                f"表格列数较多({stats['max_table_columns']}列)，"
                f"缩小字号和内边距"
            )
        elif stats['max_table_columns'] > 4:
            config.table.font_size_header = 12
            config.table.font_size_body = 11
            config.table.cell_padding = 10
            self.optimization_log.append(
                f"表格列数适中({stats['max_table_columns']}列)，"
                f"适度调整字号"
            )

        # 如果有长文本，增加行高和段落间距
        if stats['has_long_text']:
            config.page.line_height = 1.75  # 稍微降低以节省空间
            config.callout.line_height = 1.75
            config.page.paragraph_spacing = 16  # 适度间距
            self.optimization_log.append(
                "检测到长文本，增加行高至1.75和段落间距以提高可读性"
            )
        else:
            # 没有长文本时使用更紧凑的间距
            config.page.line_height = 1.5
            config.callout.line_height = 1.6
            config.page.paragraph_spacing = 14
            self.optimization_log.append(
                "文本长度适中，使用标准行高和段落间距"
            )

        # 如果内容较多，减小整体字号
        if total_blocks > 20:
            config.page.font_size_base = 13
            config.page.font_size_h2 = 22
            config.page.font_size_h3 = 18
            self.optimization_log.append(
                f"内容块较多({total_blocks}个)，"
                f"适度缩小整体字号以优化排版"
            )

        return config

    def _log_optimization(
        self,
        stats: Dict[str, Any],
        config: PDFLayoutConfig
    ):
        """记录优化过程"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'document_stats': stats,
            'optimizations': self.optimization_log.copy(),
            'final_config': config.to_dict(),
        }

        logger.info(f"布局优化完成，应用了{len(self.optimization_log)}项优化")
        for opt in self.optimization_log:
            logger.info(f"  - {opt}")

        # 清空日志供下次使用
        self.optimization_log.clear()

        return log_entry

    def save_config(self, path: str | Path, log_entry: Optional[Dict] = None):
        """
        保存配置到文件

        参数:
            path: 保存路径
            log_entry: 优化日志条目（可选）
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'config': self.config.to_dict(),
        }

        if log_entry:
            data['optimization_log'] = log_entry

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"布局配置已保存: {path}")

    @classmethod
    def load_config(cls, path: str | Path) -> PDFLayoutOptimizer:
        """
        从文件加载配置

        参数:
            path: 配置文件路径

        返回:
            PDFLayoutOptimizer: 加载了配置的优化器实例
        """
        path = Path(path)

        if not path.exists():
            logger.warning(f"配置文件不存在: {path}，使用默认配置")
            return cls()

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = PDFLayoutConfig.from_dict(data['config'])
        optimizer = cls(config)

        logger.info(f"布局配置已加载: {path}")
        return optimizer

    def generate_pdf_css(self) -> str:
        """
        根据当前配置生成PDF专用CSS

        返回:
            str: CSS样式字符串
        """
        cfg = self.config
        db = cfg.data_block

        def _scaled(value: float, scale: float, minimum: int) -> int:
            """按比例缩放并下限保护，避免数据块文字过大或过小"""
            try:
                return max(int(round(value * scale)), minimum)
            except Exception:
                return minimum

        # 文章总览数据块字体
        overview_summary_font = _scaled(cfg.page.font_size_base, db.overview_text_scale, db.min_overview_font)
        overview_badge_font = _scaled(max(cfg.page.font_size_base - 2, db.min_overview_font), db.overview_text_scale, db.min_overview_font)
        overview_kpi_value = _scaled(cfg.kpi_card.font_size_value, db.overview_kpi_scale, db.min_overview_font + 1)
        overview_kpi_label = _scaled(cfg.kpi_card.font_size_label, db.overview_kpi_scale, db.min_overview_font)
        overview_kpi_delta = _scaled(cfg.kpi_card.font_size_change, db.overview_kpi_scale, db.min_overview_font)

        # 正文数据块字体
        body_kpi_value = _scaled(cfg.kpi_card.font_size_value, db.body_kpi_scale, db.min_body_font + 1)
        body_kpi_label = _scaled(cfg.kpi_card.font_size_label, db.body_kpi_scale, db.min_body_font)
        body_kpi_delta = _scaled(cfg.kpi_card.font_size_change, db.body_kpi_scale, db.min_body_font)
        body_callout_title = _scaled(cfg.callout.font_size_title, db.body_text_scale, db.min_body_font + 1)
        body_callout_content = _scaled(cfg.callout.font_size_content, db.body_text_scale, db.min_body_font)
        body_table_header = _scaled(cfg.table.font_size_header, db.body_text_scale, db.min_body_font)
        body_table_body = _scaled(cfg.table.font_size_body, db.body_text_scale, db.min_body_font)
        body_chart_title = _scaled(cfg.chart.font_size_title, db.body_text_scale, db.min_body_font + 1)
        body_badge_font = _scaled(max(cfg.page.font_size_base - 2, db.min_body_font), db.body_text_scale, db.min_body_font)

        css = f"""
/* PDF布局优化样式 - 由PDFLayoutOptimizer自动生成 */

/* 隐藏独立的封面section，已合并到hero */
.cover {{
    display: none !important;
}}

/* PDF中隐藏hero actions（深蓝色的三个按钮） */
.hero-actions {{
    display: none !important;
}}

/* 页面基础样式 */
body {{
    font-size: {cfg.page.font_size_base}px;
    line-height: {cfg.page.line_height};
}}

main {{
    padding: {cfg.page.page_padding}px !important;
    max-width: {cfg.page.max_content_width}px;
    margin: 0 auto;
}}

/* 标题样式 */
h1 {{ font-size: {cfg.page.font_size_h1}px !important; }}
h2 {{ font-size: {cfg.page.font_size_h2}px !important; }}
h3 {{ font-size: {cfg.page.font_size_h3}px !important; }}
h4 {{ font-size: {cfg.page.font_size_h4}px !important; }}

/* 段落间距 */
p {{
    margin-bottom: {cfg.page.paragraph_spacing}px;
}}

.chapter {{
    margin-bottom: {cfg.page.section_spacing}px;
}}

/* KPI卡片优化 - 防止溢出 */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    grid-auto-rows: minmax(auto, 1fr);
    grid-auto-flow: row dense;
    gap: {cfg.grid.gap}px;
    margin: 20px 0;
    align-items: stretch;
}}

.kpi-grid .kpi-card {{
    grid-column: span 2;
}}

/* 单条/双条/三条的特殊列数 */
.chapter .kpi-grid[data-kpi-count="1"] {{
    grid-template-columns: repeat(1, minmax(0, 1fr));
    grid-auto-flow: row;
}}
.chapter .kpi-grid[data-kpi-count="1"] .kpi-card {{
    grid-column: span 1;
}}
.chapter .kpi-grid[data-kpi-count="2"] {{
    grid-template-columns: repeat(4, minmax(0, 1fr));
}}
.chapter .kpi-grid[data-kpi-count="2"] .kpi-card {{
    grid-column: span 2;
}}
.chapter .kpi-grid[data-kpi-count="3"] {{
    grid-template-columns: repeat(6, minmax(0, 1fr));
}}

/* 四条时采用2x2排布 */
.chapter .kpi-grid[data-kpi-count="4"] {{
    grid-template-columns: repeat(4, minmax(0, 1fr));
}}
.chapter .kpi-grid[data-kpi-count="4"] .kpi-card {{
    grid-column: span 2;
}}

/* 五条及以上默认三列（6栅格，每卡占2） */
.chapter .kpi-grid[data-kpi-count="5"],
.chapter .kpi-grid[data-kpi-count="6"],
.chapter .kpi-grid[data-kpi-count="7"],
.chapter .kpi-grid[data-kpi-count="8"],
.chapter .kpi-grid[data-kpi-count="9"],
.chapter .kpi-grid[data-kpi-count="10"],
.chapter .kpi-grid[data-kpi-count="11"],
.chapter .kpi-grid[data-kpi-count="12"],
.chapter .kpi-grid[data-kpi-count="13"],
.chapter .kpi-grid[data-kpi-count="14"],
.chapter .kpi-grid[data-kpi-count="15"],
.chapter .kpi-grid[data-kpi-count="16"] {{
    grid-template-columns: repeat(6, minmax(0, 1fr));
}}

/* 余数为2时，最后两张平分全宽 */
.chapter .kpi-grid[data-kpi-count="5"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="8"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="11"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="14"] .kpi-card:nth-last-child(-n+2) {{
    grid-column: span 3;
}}

/* 余数为1时，最后一张占满全宽 */
.chapter .kpi-grid[data-kpi-count="7"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="10"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="13"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="16"] .kpi-card:last-child {{
    grid-column: 1 / -1;
}}

.kpi-card {{
    padding: {cfg.kpi_card.padding}px !important;
    min-height: {cfg.kpi_card.min_height}px;
    break-inside: avoid;
    page-break-inside: avoid;
    box-sizing: border-box;
    max-width: 100%;
    height: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
}}

.kpi-card .kpi-value {{
    font-size: {body_kpi_value}px !important;
    line-height: 1.25;
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
    display: flex;
    flex-wrap: nowrap;
    align-items: baseline;
    gap: 4px 6px;
}}
.kpi-card .kpi-value small {{
    font-size: 0.65em;
    white-space: nowrap;
    align-self: baseline;
}}
.kpi-card .kpi-label {{
    font-size: {body_kpi_label}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
    line-height: 1.35;
}}

.kpi-card .change,
.kpi-card .delta {{
    font-size: {body_kpi_delta}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: 1.3;
}}

/* 提示框优化 - 防止溢出 */
.callout {{
    padding: {cfg.callout.padding}px !important;
    margin: 20px 0;
    line-height: {cfg.callout.line_height};
    font-size: {body_callout_content}px !important;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 防止溢出 */
    overflow: hidden;
    box-sizing: border-box;
    max-width: 100%;
}}

.callout-title {{
    font-size: {body_callout_title}px !important;
    margin-bottom: 10px;
    word-break: break-word;
    line-height: 1.4;
}}

.callout-content {{
    font-size: {body_callout_content}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: {cfg.callout.line_height};
}}

.callout strong {{
    font-size: {body_callout_title}px !important;
}}

.callout p,
.callout li,
.callout table,
.callout td,
.callout th {{
    font-size: {body_callout_content}px !important;
}}

/* 确保 callout 内部最后一个元素不会溢出底部 */
.callout > *:last-child,
.callout > *:last-child > *:last-child {{
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}}

/* 表格优化 - 严格防止溢出 */
table {{
    width: 100%;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 表格布局固定 */
    table-layout: fixed;
    max-width: 100%;
    overflow: hidden;
}}

th {{
    font-size: {body_table_header}px !important;
    padding: {cfg.table.cell_padding}px !important;
    /* 表头文字控制 */
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
}}

td {{
    font-size: {body_table_body}px !important;
    padding: {cfg.table.cell_padding}px !important;
    max-width: {cfg.table.max_cell_width}px;
    /* 强制换行，防止溢出 */
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
    white-space: normal;
}}

/* 图表优化 */
.chart-card {{
    min-height: {cfg.chart.min_height}px;
    max-height: {cfg.chart.max_height}px;
    padding: {cfg.chart.padding}px;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 防止图表溢出 */
    overflow: hidden;
    max-width: 100%;
    box-sizing: border-box;
}}

.chart-title {{
    font-size: {body_chart_title}px !important;
    word-break: break-word;
}}

/* Hero区域合并版本 - 去掉大色块，首屏以卡片化排布呈现文章总览 */
.hero-section-combined {{
    padding: 38px 44px !important;
    margin: 0 auto 34px auto !important;
    min-height: 420px;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box;
    overflow: visible;
    border-radius: 26px !important;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 18px 44px rgba(15, 23, 42, 0.06);
    page-break-after: always !important;
    page-break-inside: avoid;
}}

/* Hero标题区域 */
.hero-header {{
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    row-gap: 6px;
    margin-bottom: 22px;
    padding-bottom: 16px;
    border-bottom: 1px solid #eef1f5;
    text-align: left;
}}

.hero-hint {{
    font-size: {max(cfg.page.font_size_base - 2, 11)}px !important;
    color: #556070;
    margin: 0;
    font-weight: 600;
    letter-spacing: 0.04em;
}}

.hero-title {{
    font-size: {max(cfg.page.font_size_base + 5, 19)}px !important;
    font-weight: 700;
    margin: 0;
    color: #0f172a;
    line-height: 1.25;
    letter-spacing: -0.01em;
}}

.hero-subtitle {{
    font-size: {max(cfg.page.font_size_base - 1, 12)}px !important;
    color: #475467;
    margin: 2px 0 0 0;
    font-weight: 500;
}}

/* Hero主体区域 - 网格分栏 */
.hero-body {{
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
    gap: 22px 28px;
    align-items: flex-start;
    align-content: start;
}}

/* 左侧摘要/亮点 */
.hero-content {{
    display: grid;
    gap: 14px;
    min-width: 0;
    align-content: start;
}}

/* 右侧KPI区域 */
.hero-side {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: {max(cfg.grid.gap - 2, 10)}px;
    overflow: hidden;
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 0;
    align-content: flex-start;
}}

/* Hero区域的KPI卡片 */
.hero-kpi {{
    background: #fdfdfd;
    border-radius: 14px !important;
    border: 1px solid #e5e7eb;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
    padding: 14px 16px !important;
    overflow: hidden;
    box-sizing: border-box;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}}

.hero-kpi .label {{
    font-size: {overview_kpi_label}px !important;
    word-break: break-word;
    max-width: 100%;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #556070;
}}

.hero-kpi .value {{
    font-size: {overview_kpi_value}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
    line-height: 1.1;
    display: block;
    hyphens: auto;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 2px;
    color: #0f172a;
}}

.hero-kpi .delta {{
    font-size: {overview_kpi_delta}px !important;
    word-break: break-word;
    margin-top: 2px;
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
}}

/* Hero summary文本 */
.hero-summary {{
    font-size: {overview_summary_font}px !important;
    line-height: 1.65;
    margin: 0 0 12px 0;
    padding: 0;
    word-break: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    width: 100%;
    box-sizing: border-box;
    align-self: start;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
}}

/* Hero highlights列表 - 网格排布 */
.hero-highlights {{
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px 12px;
}}

.hero-highlights li {{
    margin: 0;
    max-width: 100%;
    flex-shrink: 0;
    flex-grow: 0;
}}

/* hero highlights中的badge - 卡片化的小条目 */
.hero-highlights .badge {{
    font-size: {overview_badge_font}px !important;
    padding: 10px 12px !important;
    max-width: 100%;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    word-wrap: break-word;
    white-space: normal;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
    line-height: 1.5;
    min-height: 40px;
    background: #f3f4f6 !important;
    border-radius: 12px !important;
    border: 1px solid #e5e7eb;
    color: #111827;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    align-items: flex-start;
    justify-content: flex-start;
}}

/* Hero actions按钮 - PDF中仍隐藏，保留缩进样式 */
.hero-actions {{
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    max-width: 100%;
    overflow: hidden;
}}

.hero-actions button {{
    font-size: {max(cfg.page.font_size_base - 2, 11)}px !important;
    padding: 5px 10px !important;
    max-width: 200px;
    word-break: break-word;
    white-space: normal;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
}}

/* 防止标题孤行 */
h1, h2, h3, h4, h5, h6 {{
    break-after: avoid;
    page-break-after: avoid;
    word-break: break-word;
    overflow-wrap: break-word;
}}

/* ===== 强制页面分离规则 ===== */

/* 目录section强制开始新页并在之后强制分页 */
.toc-section {{
    page-break-before: always !important;
    page-break-after: always !important;
}}

/* 第一个章节强制开始新页（正文从第三页开始） */
main > .chapter:first-of-type {{
    page-break-before: always !important;
}}

/* 确保内容块不被分页且不溢出 */
.content-block {{
    break-inside: avoid;
    page-break-inside: avoid;
    overflow: hidden;
    max-width: 100%;
}}

/* 全局溢出防护 */
* {{
    box-sizing: border-box;
    max-width: 100%;
}}

/* 特别控制数字和长单词 */
.kpi-value, .value, .delta {{
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;  /* 稍微紧缩间距以节省空间 */
}}

/* 色块（badge）样式控制 - 防止过大 */
.badge {{
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: normal;
    /* 限制badge的最大尺寸 */
    padding: 4px 12px !important;
    font-size: {body_badge_font}px !important;
    line-height: 1.4 !important;
    /* 防止badge异常过大 */
    word-break: break-word;
    hyphens: auto;
}}

/* 确保callout不会过大 */
.callout {{
    max-width: 100% !important;
    margin: 16px 0 !important;
    padding: {cfg.callout.padding}px !important;
    box-sizing: border-box;
    overflow: hidden;
}}

/* 响应式调整 */
@media print {{
    /* 打印时更严格的控制 */
    * {{
        overflow: visible !important;
        max-width: 100% !important;
    }}

    .kpi-card, .callout, .chart-card {{
        overflow: hidden !important;
    }}
}}
"""

        return css


__all__ = [
    'PDFLayoutOptimizer',
    'PDFLayoutConfig',
    'PageLayout',
    'KPICardLayout',
    'CalloutLayout',
    'TableLayout',
    'ChartLayout',
    'GridLayout',
    'DataBlockLayout',
]
