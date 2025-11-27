"""
图表到SVG转换器 - 将Chart.js数据转换为矢量SVG图形

支持的图表类型:
- line: 折线图
- bar: 柱状图
- pie: 饼图
- doughnut: 圆环图
- radar: 雷达图
- polarArea: 极地区域图
- scatter: 散点图
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非GUI后端
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm
    from matplotlib.patches import Wedge, Rectangle
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib未安装，PDF图表矢量渲染功能将不可用")

# 可选依赖：scipy用于曲线平滑
try:
    from scipy.interpolate import make_interp_spline
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.info("Scipy未安装，折线图将不支持曲线平滑功能（不影响基本渲染）")


class ChartToSVGConverter:
    """
    将Chart.js图表数据转换为SVG矢量图形
    """

    # 默认颜色调色板（优化版：明亮且易区分）
    DEFAULT_COLORS = [
        '#4A90E2', '#E85D75', '#50C878', '#FFB347',  # 明亮蓝、珊瑚红、翠绿、橙黄
        '#9B59B6', '#3498DB', '#E67E22', '#16A085',  # 紫色、天蓝、橙色、青色
        '#F39C12', '#D35400', '#27AE60', '#8E44AD'   # 金色、深橙、绿色、紫罗兰
    ]

    # CSS变量到颜色的映射表（优化版：使用更明亮、更浅的颜色）
    CSS_VAR_COLOR_MAP = {
        'var(--color-accent)': '#4A90E2',        # 明亮蓝色（从#007AFF改为更浅）
        'var(--re-accent-color)': '#4A90E2',     # 明亮蓝色
        'var(--re-accent-color-translucent)': (0.29, 0.565, 0.886, 0.08),  # 蓝色极浅透明 rgba(74, 144, 226, 0.08)
        'var(--color-kpi-down)': '#E85D75',      # 珊瑚红色（从#DC3545改为更柔和）
        'var(--re-danger-color)': '#E85D75',     # 珊瑚红色
        'var(--re-danger-color-translucent)': (0.91, 0.365, 0.459, 0.08),  # 红色极浅透明 rgba(232, 93, 117, 0.08)
        'var(--color-warning)': '#FFB347',       # 柔和橙黄色（从#FFC107改为更浅）
        'var(--re-warning-color)': '#FFB347',    # 柔和橙黄色
        'var(--re-warning-color-translucent)': (1.0, 0.702, 0.278, 0.08),  # 黄色极浅透明 rgba(255, 179, 71, 0.08)
        'var(--color-success)': '#50C878',       # 翠绿色（从#28A745改为更明亮）
        'var(--re-success-color)': '#50C878',    # 翠绿色
        'var(--re-success-color-translucent)': (0.314, 0.784, 0.471, 0.08),  # 绿色极浅透明 rgba(80, 200, 120, 0.08)
        'var(--color-accent-positive)': '#50C878',
        'var(--color-accent-negative)': '#E85D75',
        'var(--color-text-secondary)': '#6B7280',
        'var(--accentPositive)': '#50C878',
        'var(--accentNegative)': '#E85D75',
        'var(--sentiment-positive, #28A745)': '#28A745',
        'var(--sentiment-negative, #E53E3E)': '#E53E3E',
        'var(--sentiment-neutral, #FFC107)': '#FFC107',
        'var(--sentiment-positive)': '#28A745',
        'var(--sentiment-negative)': '#E53E3E',
        'var(--sentiment-neutral)': '#FFC107',
        'var(--color-primary)': '#3498DB',       # 天蓝色
        'var(--color-secondary)': '#95A5A6',     # 浅灰色
    }

    # 支持解析 rgba(var(--color-primary-rgb), 0.5) 这类格式的兜底映射
    CSS_VAR_RGB_MAP = {
        'color-primary-rgb': (52, 152, 219),
        'color-tone-up-rgb': (80, 200, 120),
        'color-tone-down-rgb': (232, 93, 117),
        'color-accent-positive-rgb': (80, 200, 120),
        'color-accent-neutral-rgb': (149, 165, 166),
    }

    def __init__(self, font_path: Optional[str] = None):
        """
        初始化转换器

        参数:
            font_path: 中文字体路径（可选）
        """
        if not MATPLOTLIB_AVAILABLE:
            raise RuntimeError("Matplotlib未安装，请运行: pip install matplotlib")

        self.font_path = font_path
        self._setup_chinese_font()

    def _setup_chinese_font(self):
        """配置中文字体"""
        if self.font_path:
            try:
                # 添加自定义字体
                fm.fontManager.addfont(self.font_path)
                # 设置默认字体
                font_prop = fm.FontProperties(fname=self.font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
                logger.info(f"已加载中文字体: {self.font_path}")
            except Exception as e:
                logger.warning(f"加载中文字体失败: {e}，将使用系统默认字体")
        else:
            # 尝试使用系统中文字体
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as e:
                logger.warning(f"配置中文字体失败: {e}")

    def convert_widget_to_svg(
        self,
        widget_data: Dict[str, Any],
        width: int = 800,
        height: int = 500,
        dpi: int = 100
    ) -> Optional[str]:
        """
        将widget数据转换为SVG字符串

        参数:
            widget_data: widget块数据（包含widgetType、data、props）
            width: 图表宽度（像素）
            height: 图表高度（像素）
            dpi: DPI设置

        返回:
            str: SVG字符串，失败返回None
        """
        try:
            # 提取图表类型
            widget_type = widget_data.get('widgetType', '')
            if not widget_type or not widget_type.startswith('chart.js'):
                logger.warning(f"不支持的widget类型: {widget_type}")
                return None

            # 从widgetType中提取图表类型，例如 "chart.js/line" -> "line"
            chart_type = widget_type.split('/')[-1] if '/' in widget_type else 'bar'

            # 也检查props中的type
            props = widget_data.get('props', {})
            if props.get('type'):
                chart_type = props['type']

            # Chart.js v4已移除horizontalBar类型，这里自动降级为bar并设置横向坐标
            horizontal_bar = False
            if chart_type and str(chart_type).lower() == 'horizontalbar':
                chart_type = 'bar'
                horizontal_bar = True

            # 支持通过indexAxis: 'y' 强制横向柱状图
            if isinstance(props, dict):
                options = props.get('options') or {}
                index_axis = (options.get('indexAxis') or props.get('indexAxis') or '').lower()
                if index_axis == 'y':
                    horizontal_bar = True

            # 提取数据
            data = widget_data.get('data', {})
            if not data:
                logger.warning("图表数据为空")
                return None

            # 根据图表类型调用相应的渲染方法
            if 'wordcloud' in str(chart_type).lower():
                # 词云由专用渲染逻辑处理，这里跳过SVG转换以避免告警
                logger.debug("检测到词云图表，跳过chart_to_svg转换")
                return None

            # 分派渲染方法，特殊处理横向柱状图
            if chart_type == 'bar':
                return self._render_bar(data, props, width, height, dpi, horizontal=horizontal_bar)
            elif chart_type == 'bubble':
                return self._render_bubble(data, props, width, height, dpi)
            else:
                render_method = getattr(self, f'_render_{chart_type}', None)
                if not render_method:
                    logger.warning(f"不支持的图表类型: {chart_type}")
                    return None

            # 创建图表并转换为SVG
            return render_method(data, props, width, height, dpi)

        except Exception as e:
            logger.error(f"转换图表为SVG失败: {e}", exc_info=True)
            return None

    def _create_figure(
        self,
        width: int,
        height: int,
        dpi: int,
        title: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """
        创建matplotlib图表

        返回:
            tuple: (fig, ax)
        """
        fig, ax = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)

        if title:
            ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        return fig, ax

    def _parse_color(self, color: Any) -> Any:
        """
        解析颜色值，将CSS格式转换为matplotlib支持的格式

        参数:
            color: 颜色值（可能是CSS格式如rgba()或十六进制或CSS变量）

        返回:
            matplotlib支持的颜色格式（hex字符串或RGB(A)元组）
        """
        if color is None:
            return None

        # 处理numpy数组，统一转为原生列表
        _np = globals().get("np")
        if _np is not None and hasattr(_np, "ndarray") and isinstance(color, _np.ndarray):
            color = color.tolist()

        # 直接透传已经是序列的颜色（如 (r,g,b,a)），避免被转成字符串后失效
        if isinstance(color, (list, tuple)):
            if len(color) in (3, 4) and all(isinstance(c, (int, float)) for c in color):
                normalized = []
                for idx, channel in enumerate(color):
                    # Matplotlib接受0-1之间的浮点数，若值>1则按0-255来源归一化
                    value = float(channel)
                    if value > 1:
                        value = value / 255.0
                    # 只对RGB通道做强制裁剪，alpha按0-1裁剪
                    if idx < 3:
                        value = max(0.0, min(value, 1.0))
                    else:
                        value = max(0.0, min(value, 1.0))
                    normalized.append(value)
                return tuple(normalized)

            try:
                return tuple(color)
            except Exception:
                return color

        # 其余非字符串类型保持原有字符串回退策略
        if not isinstance(color, str):
            return str(color)

        color = color.strip()

        # 处理 rgba(var(--color-primary-rgb), 0.5) / rgb(var(--color-primary-rgb))
        var_rgba_pattern = r'rgba?\(var\(--([\w-]+)\)\s*(?:,\s*([\d.]+))?\)'
        match = re.match(var_rgba_pattern, color)
        if match:
            var_name, alpha_str = match.groups()
            rgb_tuple = self.CSS_VAR_RGB_MAP.get(var_name)

            # 兼容缺少 -rgb 后缀的写法
            if not rgb_tuple:
                if var_name.endswith('-rgb'):
                    rgb_tuple = self.CSS_VAR_RGB_MAP.get(var_name[:-4])
                else:
                    rgb_tuple = self.CSS_VAR_RGB_MAP.get(f"{var_name}-rgb")

            if rgb_tuple:
                r, g, b = rgb_tuple
                alpha = float(alpha_str) if alpha_str is not None else 1.0
                return (r / 255, g / 255, b / 255, alpha)

        # 【增强】处理CSS变量，例如 var(--color-accent)
        # 使用预定义的颜色映射表替代CSS变量，确保不同变量有不同的颜色
        if color.startswith('var('):
            # 解析 var(--token, fallback) 形式
            fb_match = re.match(r'^var\(\s*--[^,)+]+,\s*([^)]+)\)', color)
            if fb_match:
                fb_raw = fb_match.group(1).strip()
                fb_color = self._parse_color(fb_raw)
                if fb_color:
                    return fb_color
            # 尝试从映射表中查找对应的颜色
            mapped_color = self.CSS_VAR_COLOR_MAP.get(color)
            if mapped_color:
                return mapped_color
            # 如果映射表中没有，尝试从变量名推断颜色类型
            if 'accent' in color or 'primary' in color:
                return '#007AFF'  # 蓝色
            elif 'danger' in color or 'down' in color or 'error' in color:
                return '#DC3545'  # 红色
            elif 'warning' in color:
                return '#FFC107'  # 黄色
            elif 'success' in color or 'up' in color:
                return '#28A745'  # 绿色
            # 默认返回蓝色
            return '#36A2EB'

        # 处理rgba(r, g, b, a)格式
        rgba_pattern = r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)'
        match = re.match(rgba_pattern, color)
        if match:
            r, g, b, a = match.groups()
            # 转换为matplotlib格式 (r/255, g/255, b/255, a)
            return (int(r)/255, int(g)/255, int(b)/255, float(a))

        # 处理rgb(r, g, b)格式
        rgb_pattern = r'rgb\((\d+),\s*(\d+),\s*(\d+)\)'
        match = re.match(rgb_pattern, color)
        if match:
            r, g, b = match.groups()
            # 转换为matplotlib格式 (r/255, g/255, b/255)
            return (int(r)/255, int(g)/255, int(b)/255)

        # 其他格式（十六进制、颜色名等）直接返回
        return color

    def _ensure_visible_color(self, color: Any, fallback: str, min_alpha: float = 0.6) -> Any:
        """
        确保颜色在渲染时可见：避免透明值并提升过低的不透明度
        """
        base_color = fallback if color in (None, "", "transparent") else color
        parsed = self._parse_color(base_color)
        fallback_parsed = self._parse_color(fallback)

        if isinstance(parsed, tuple):
            if len(parsed) == 4:
                r, g, b, a = parsed
                return (r, g, b, max(a, min_alpha))
            return parsed

        if isinstance(parsed, str) and parsed.lower() == "transparent":
            return fallback_parsed

        return parsed if parsed is not None else fallback_parsed

    def _get_colors(self, datasets: List[Dict[str, Any]]) -> List[str]:
        """
        获取图表颜色

        优先使用dataset中定义的颜色，否则使用默认调色板
        """
        colors = []
        for i, dataset in enumerate(datasets):
            # 尝试获取各种可能的颜色字段
            color = (
                dataset.get('backgroundColor') or
                dataset.get('borderColor') or
                dataset.get('color') or
                self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
            )

            # 如果是颜色数组，取第一个
            if isinstance(color, list):
                color = color[0] if color else self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]

            # 解析颜色格式
            color = self._parse_color(color)

            colors.append(color)

        return colors

    def _align_labels_and_data(
        self,
        labels: Any,
        dataset_data: Any,
        chart_type: str,
        require_positive_sum: bool = False
    ) -> Tuple[List[str], List[float]]:
        """
        对齐类别型图表的标签与数据长度，并清理非数值值。

        Matplotlib的饼图/圆环图要求labels与数据长度一致，否则会抛出错误。
        """
        original_label_len = len(labels) if isinstance(labels, list) else 0
        original_data_len = len(dataset_data) if isinstance(dataset_data, list) else 0

        aligned_labels = [str(label) for label in labels] if isinstance(labels, list) else []
        raw_data = dataset_data if isinstance(dataset_data, list) else []

        cleaned_data: List[float] = []
        for value in raw_data:
            try:
                numeric = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                numeric = 0.0
            if numeric < 0:
                numeric = 0.0
            cleaned_data.append(numeric)

        target_len = max(len(aligned_labels), len(cleaned_data))
        if target_len == 0:
            return [], []

        if len(aligned_labels) < target_len:
            start = len(aligned_labels)
            aligned_labels.extend([f"未命名{start + idx + 1}" for idx in range(target_len - start)])

        if len(cleaned_data) < target_len:
            cleaned_data.extend([0.0] * (target_len - len(cleaned_data)))

        if original_label_len != original_data_len:
            logger.warning(
                f"{chart_type}图labels长度({original_label_len})与data长度({original_data_len})不一致，"
                f"已对齐为{target_len}"
            )

        if require_positive_sum and not any(value > 0 for value in cleaned_data):
            logger.warning(f"{chart_type}图数据为空，跳过渲染")
            return [], []

        return aligned_labels[:target_len], cleaned_data[:target_len]

    def _figure_to_svg(self, fig: Any) -> str:
        """
        将matplotlib图表转换为SVG字符串
        """
        svg_buffer = io.BytesIO()
        fig.savefig(svg_buffer, format='svg', bbox_inches='tight', transparent=False, facecolor='white')
        plt.close(fig)

        svg_buffer.seek(0)
        svg_string = svg_buffer.getvalue().decode('utf-8')

        return svg_string

    def _render_line(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """
        渲染折线图（增强版）

        支持特性：
        - 多y轴（yAxisID: 'y', 'y1', 'y2', 'y3'...）
        - 填充区域（fill: true）
        - 透明度（backgroundColor中的alpha通道）
        - 线条样式（tension曲线平滑）
        """
        try:
            labels = data.get('labels') or []
            datasets = data.get('datasets') or []

            has_object_points = any(
                isinstance(ds, dict)
                and isinstance(ds.get('data'), list)
                and any(isinstance(pt, dict) and ('x' in pt or 'y' in pt) for pt in ds.get('data'))
                for ds in datasets
            )

            if (not datasets) or ((not labels) and not has_object_points):
                return None

            # 收集所有唯一的yAxisID
            y_axis_ids = []
            for dataset in datasets:
                y_axis_id = dataset.get('yAxisID', 'y')
                if y_axis_id not in y_axis_ids:
                    y_axis_ids.append(y_axis_id)

            # 确保'y'是第一个轴
            if 'y' in y_axis_ids:
                y_axis_ids.remove('y')
                y_axis_ids.insert(0, 'y')

            # 检查是否有多个y轴
            has_multiple_axes = len(y_axis_ids) > 1

            title = props.get('title')
            options = props.get('options', {})
            scales = options.get('scales', {})
            x_tick_labels = list(labels) if isinstance(labels, list) else []

            # 创建图表和多个y轴
            fig, ax1 = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)

            if title:
                ax1.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # 创建y轴映射字典
            axes = {'y': ax1}

            if has_multiple_axes:
                # 统计每个位置(left/right)的轴数量,用于计算偏移
                left_axes_count = 0
                right_axes_count = 0

                # 为每个额外的yAxisID创建新的y轴
                for y_axis_id in y_axis_ids[1:]:
                    if y_axis_id == 'y':
                        continue

                    # 创建新的y轴
                    new_ax = ax1.twinx()
                    axes[y_axis_id] = new_ax

                    # 从scales配置中获取轴的位置
                    y_config = scales.get(y_axis_id, {})
                    position = y_config.get('position', 'right')

                    if position == 'left':
                        # 左侧额外轴,向左偏移
                        if left_axes_count > 0:
                            new_ax.spines['left'].set_position(('outward', 60 * left_axes_count))
                        new_ax.yaxis.set_label_position('left')
                        new_ax.yaxis.set_ticks_position('left')
                        left_axes_count += 1
                    else:
                        # 右侧额外轴,向右偏移
                        if right_axes_count > 0:
                            new_ax.spines['right'].set_position(('outward', 60 * right_axes_count))
                        right_axes_count += 1

            colors = self._get_colors(datasets)

            # 收集每个y轴的线条和填充信息用于图例
            axis_lines = {axis_id: [] for axis_id in y_axis_ids}
            legend_handles = []  # 图例句柄
            legend_labels = []   # 图例标签

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 获取配置
                y_axis_id = dataset.get('yAxisID', 'y')
                fill = True  # 强制开启填充，便于对比
                tension = dataset.get('tension', 0)  # 0表示直线，0.4表示平滑曲线
                border_color = self._parse_color(dataset.get('borderColor', color))
                background_color = self._parse_color(dataset.get('backgroundColor', color))

                # 选择对应的坐标轴
                ax = axes.get(y_axis_id, ax1)

                is_object_data = isinstance(dataset_data, list) and any(
                    isinstance(point, dict) and ('x' in point or 'y' in point)
                    for point in dataset_data
                )

                if is_object_data:
                    x_data = []
                    y_data = []
                    annotations = []

                    for idx, point in enumerate(dataset_data):
                        if not isinstance(point, dict):
                            continue

                        label_text = str(point.get('x', f"点{idx + 1}"))
                        if len(x_tick_labels) < len(dataset_data):
                            x_tick_labels.append(label_text)

                        x_data.append(len(x_data))

                        y_val = point.get('y', 0)
                        try:
                            y_val = float(y_val)
                        except (TypeError, ValueError):
                            y_val = 0
                        y_data.append(y_val)
                        annotations.append(point.get('event'))

                    if not x_data:
                        continue

                    line, = ax.plot(x_data, y_data, marker='o', label=label,
                                    color=border_color, linewidth=2, markersize=6)

                    if fill:
                        ax.fill_between(x_data, y_data, alpha=0.2, color=background_color)

                    for pos, y_val, text in zip(x_data, y_data, annotations):
                        if text:
                            ax.annotate(
                                text,
                                (pos, y_val),
                                textcoords='offset points',
                                xytext=(0, 8),
                                ha='center',
                                fontsize=8,
                                rotation=20
                            )
                else:
                    # 绘制折线
                    x_data = range(len(labels))

                    # 根据tension值决定是否平滑
                    if tension > 0 and SCIPY_AVAILABLE:
                        # 使用样条插值平滑曲线（需要scipy）
                        if len(dataset_data) >= 4:  # 至少需要4个点才能平滑
                            try:
                                x_smooth = np.linspace(0, len(labels)-1, len(labels)*3)
                                spl = make_interp_spline(x_data, dataset_data, k=min(3, len(dataset_data)-1))
                                y_smooth = spl(x_smooth)
                                line, = ax.plot(x_smooth, y_smooth, label=label, color=border_color, linewidth=2)

                                # 如果需要填充（使用极低透明度避免遮挡）
                                if fill:
                                    ax.fill_between(x_smooth, y_smooth, alpha=0.2, color=background_color)
                            except:
                                # 如果平滑失败，使用普通折线
                                line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                              color=border_color, linewidth=2, markersize=6)
                                if fill:
                                    ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)
                        else:
                            line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                          color=border_color, linewidth=2, markersize=6)
                            if fill:
                                ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)
                    else:
                        # 直线连接（tension=0或scipy不可用）
                        line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                      color=border_color, linewidth=2, markersize=6)

                        # 如果需要填充（使用极低透明度避免遮挡）
                        if fill:
                            ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)

                # 记录这条线属于哪个轴
                axis_lines[y_axis_id].append(line)

                # 创建图例项：如果有填充，创建带填充背景的图例
                if fill:
                    # 创建一个矩形patch作为填充背景（使用稍高透明度以便在图例中可见）
                    fill_patch = Rectangle((0, 0), 1, 1,
                                          facecolor=background_color,
                                          edgecolor='none',
                                          alpha=0.15)
                    # 组合线条和填充patch
                    legend_handles.append((line, fill_patch))
                    legend_labels.append(label)
                else:
                    legend_handles.append(line)
                    legend_labels.append(label)

            # 设置x轴标签
            if x_tick_labels:
                ax1.set_xticks(range(len(x_tick_labels)))
                ax1.set_xticklabels(x_tick_labels, rotation=45, ha='right')

            # 设置y轴标签和标题
            for y_axis_id, ax in axes.items():
                y_config = scales.get(y_axis_id, {})
                y_title = y_config.get('title', {}).get('text', '')

                if y_title:
                    ax.set_ylabel(y_title, fontsize=11)

                # 设置y轴标签颜色（如果该轴只有一条线，使用该线的颜色）
                if len(axis_lines[y_axis_id]) == 1:
                    line_color = axis_lines[y_axis_id][0].get_color()
                    ax.tick_params(axis='y', labelcolor=line_color)
                    ax.yaxis.label.set_color(line_color)

            # 设置网格（只在主轴显示）
            ax1.grid(True, alpha=0.3, linestyle='--')
            for y_axis_id in y_axis_ids[1:]:
                if y_axis_id in axes:
                    axes[y_axis_id].grid(False)

            # 创建图例
            if has_multiple_axes or len(datasets) > 1:
                # 使用自定义的legend_handles和legend_labels
                from matplotlib.legend_handler import HandlerTuple

                ax1.legend(legend_handles, legend_labels,
                          loc='best',
                          framealpha=0.9,
                          handler_map={tuple: HandlerTuple(ndivide=None)})

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染折线图失败: {e}", exc_info=True)
            return None

    def _render_bar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int,
        horizontal: bool = False
    ) -> Optional[str]:
        """渲染柱状图（支持横向barh）"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # 计算柱子位置
            positions = np.arange(len(labels))
            width_bar = 0.8 / len(datasets) if len(datasets) > 1 else 0.6

            # 横向/纵向绘制
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                offset = (i - len(datasets)/2 + 0.5) * width_bar

                if horizontal:
                    ax.barh(
                        positions + offset,
                        dataset_data,
                        height=width_bar,
                        label=label,
                        color=color,
                        alpha=0.8,
                        edgecolor='white',
                        linewidth=0.5
                    )
                else:
                    ax.bar(
                        positions + offset,
                        dataset_data,
                        width_bar,
                        label=label,
                        color=color,
                        alpha=0.8,
                        edgecolor='white',
                        linewidth=0.5
                    )

            # 轴标签/网格
            if horizontal:
                ax.set_yticks(positions)
                ax.set_yticklabels(labels)
                ax.invert_yaxis()  # 与Chart.js横向排列保持一致
                ax.grid(True, alpha=0.3, linestyle='--', axis='x')
            else:
                ax.set_xticks(positions)
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.grid(True, alpha=0.3, linestyle='--', axis='y')

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染柱状图失败: {e}")
            return None

    def _render_bubble(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染气泡图"""
        try:
            datasets = data.get('datasets', [])
            if not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)
            colors = self._get_colors(datasets)

            def _safe_radius(raw) -> float:
                """将输入半径安全转为浮点并设置最小阈值，避免气泡完全消失"""
                try:
                    val = float(raw)
                    return max(val, 0.5)
                except Exception:
                    return 1.0

            all_x: list[float] = []
            all_y: list[float] = []
            max_r: float = 0.0

            for i, dataset in enumerate(datasets):
                points = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                if points and isinstance(points[0], dict):
                    xs = [p.get('x', 0) for p in points]
                    ys = [p.get('y', 0) for p in points]
                    rs = [_safe_radius(p.get('r', 1)) for p in points]
                else:
                    xs = list(range(len(points)))
                    ys = points
                    rs = [1.0 for _ in points]

                all_x.extend(xs)
                all_y.extend(ys)
                if rs:
                    max_r = max(max_r, max(rs))

                # 适度放大半径，近似Chart.js像素尺寸（动态尺度，避免过大遮挡）
                size_scale = 8.0 if max_r <= 20 else 6.5
                sizes = [(r * size_scale) ** 2 for r in rs]

                ax.scatter(
                    xs,
                    ys,
                    s=sizes,
                    label=label,
                    color=color,
                    alpha=0.45,
                    edgecolors='white',
                    linewidth=0.6
                )

            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # 适度留白，避免大气泡被裁切
            if all_x and all_y:
                x_min, x_max = min(all_x), max(all_x)
                y_min, y_max = min(all_y), max(all_y)
                x_span = max(x_max - x_min, 1e-6)
                y_span = max(y_max - y_min, 1e-6)
                pad_x = max(x_span * 0.12, max_r * 1.2)
                pad_y = max(y_span * 0.12, max_r * 1.2)
                ax.set_xlim(x_min - pad_x, x_max + pad_x)
                ax.set_ylim(y_min - pad_y, y_max + pad_y)
                # 额外安全边距
                ax.margins(x=0.05, y=0.05)

            ax.grid(True, alpha=0.3, linestyle='--')
            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染气泡图失败: {e}", exc_info=True)
            return None

    def _render_pie(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染饼图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 饼图只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="饼",
                require_positive_sum=True
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # 获取颜色
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # 绘制饼图
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 10}
            )

            # 设置百分比文字为白色
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')  # 保持圆形

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染饼图失败: {e}")
            return None

    def _render_doughnut(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染圆环图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 圆环图只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="圆环",
                require_positive_sum=True
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # 获取颜色
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # 绘制圆环图（通过设置wedgeprops实现中空效果）
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops=dict(width=0.5, edgecolor='white'),
                textprops={'fontsize': 10}
            )

            # 设置百分比文字
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染圆环图失败: {e}")
            return None

    def _render_radar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染雷达图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)

            # 创建极坐标子图
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            colors = self._get_colors(datasets)

            # 计算角度
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            angles += angles[:1]  # 闭合图形

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 闭合数据
                values = dataset_data + dataset_data[:1]

                # 绘制雷达图
                ax.plot(angles, values, 'o-', linewidth=2, label=label, color=color)
                ax.fill(angles, values, alpha=0.25, color=color)

            # 设置标签
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels)

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染雷达图失败: {e}")
            return None

    def _render_scatter(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染散点图"""
        try:
            datasets = data.get('datasets', [])

            if not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 提取x和y坐标
                if dataset_data and isinstance(dataset_data[0], dict):
                    x_values = [point.get('x', 0) for point in dataset_data]
                    y_values = [point.get('y', 0) for point in dataset_data]
                else:
                    # 如果不是{x,y}格式，使用索引作为x
                    x_values = range(len(dataset_data))
                    y_values = dataset_data

                ax.scatter(
                    x_values,
                    y_values,
                    label=label,
                    color=color,
                    s=50,
                    alpha=0.6,
                    edgecolors='white',
                    linewidth=0.5
                )

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # 网格
            ax.grid(True, alpha=0.3, linestyle='--')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染散点图失败: {e}")
            return None

    def _render_polarArea(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染极地区域图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="极地区域",
                require_positive_sum=False
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # 获取颜色
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # 计算角度
            theta = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
            width_bar = 2 * np.pi / len(labels)

            # 绘制极地区域图
            bars = ax.bar(
                theta,
                dataset_data,
                width=width_bar,
                bottom=0.0,
                color=colors,
                alpha=0.7,
                edgecolor='white',
                linewidth=1
            )

            # 设置标签
            ax.set_xticks(theta)
            ax.set_xticklabels(labels)

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染极地区域图失败: {e}")
            return None


def create_chart_converter(font_path: Optional[str] = None) -> ChartToSVGConverter:
    """
    创建图表转换器实例

    参数:
        font_path: 中文字体路径（可选）

    返回:
        ChartToSVGConverter: 转换器实例
    """
    return ChartToSVGConverter(font_path=font_path)


__all__ = ["ChartToSVGConverter", "create_chart_converter"]
