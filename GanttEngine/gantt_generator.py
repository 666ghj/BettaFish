"""
甘特图生成器
使用Plotly创建交互式项目时间轴甘特图
"""

import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GanttGenerator:
    """甘特图生成器，创建美观的交互式甘特图"""

    # 颜色方案
    COLOR_SCHEMES = {
        'default': px.colors.qualitative.Plotly,
        'pastel': px.colors.qualitative.Pastel,
        'bold': px.colors.qualitative.Bold,
        'vivid': px.colors.qualitative.Vivid,
        'safe': px.colors.qualitative.Safe,
    }

    def __init__(self, tasks: List[Dict[str, Any]], color_scheme: str = 'default'):
        """
        初始化甘特图生成器

        Args:
            tasks: 任务列表
            color_scheme: 颜色方案名称
        """
        self.tasks = tasks
        self.color_scheme = color_scheme
        self.fig = None

    def generate(self,
                 title: str = "项目时间轴甘特图",
                 group_by: str = 'category',
                 show_progress: bool = True,
                 height: int = 600) -> go.Figure:
        """
        生成甘特图

        Args:
            title: 图表标题
            group_by: 分组方式 ('category', 'owner', 'none')
            show_progress: 是否显示进度条
            height: 图表高度（像素）

        Returns:
            Plotly Figure对象
        """
        try:
            logger.info(f"开始生成甘特图，共 {len(self.tasks)} 个任务")

            # 准备数据
            df_data = self._prepare_data(group_by)

            # 创建甘特图
            if show_progress:
                self.fig = self._create_gantt_with_progress(df_data, title, group_by, height)
            else:
                self.fig = self._create_simple_gantt(df_data, title, group_by, height)

            # 自定义布局
            self._customize_layout(title, height)

            logger.info("甘特图生成成功")
            return self.fig

        except Exception as e:
            logger.error(f"生成甘特图失败: {str(e)}")
            raise

    def _prepare_data(self, group_by: str) -> List[Dict[str, Any]]:
        """
        准备用于绘图的数据

        Args:
            group_by: 分组字段

        Returns:
            格式化的数据列表
        """
        data = []

        # 按分组排序
        if group_by != 'none':
            sorted_tasks = sorted(self.tasks, key=lambda x: (x.get(group_by, '未分类'), x['start_date']))
        else:
            sorted_tasks = sorted(self.tasks, key=lambda x: x['start_date'])

        for task in sorted_tasks:
            data.append({
                'Task': task['task_name'],
                'Start': task['start_date'],
                'Finish': task['end_date'],
                'Resource': task.get(group_by, '未分类') if group_by != 'none' else '所有任务',
                'Progress': task.get('progress', 0),
                'Owner': task.get('owner', '未指定'),
                'Category': task.get('category', '未分类'),
                'Duration': task.get('duration', 0)
            })

        return data

    def _create_simple_gantt(self, data: List[Dict], title: str, group_by: str, height: int) -> go.Figure:
        """
        创建简单甘特图（不显示进度）

        Args:
            data: 数据列表
            title: 标题
            group_by: 分组字段
            height: 高度

        Returns:
            Plotly Figure对象
        """
        # 使用Plotly Express创建基础甘特图
        fig = px.timeline(
            data,
            x_start="Start",
            x_end="Finish",
            y="Task",
            color="Resource",
            color_discrete_sequence=self.COLOR_SCHEMES.get(self.color_scheme, self.COLOR_SCHEMES['default']),
            hover_data={
                'Task': True,
                'Start': '|%Y-%m-%d',
                'Finish': '|%Y-%m-%d',
                'Owner': True,
                'Category': True,
                'Duration': True,
                'Progress': ':.0f'
            },
            labels={
                'Task': '任务',
                'Resource': '分组',
                'Start': '开始日期',
                'Finish': '结束日期',
                'Owner': '负责人',
                'Category': '分类',
                'Duration': '持续天数',
                'Progress': '进度(%)'
            }
        )

        return fig

    def _create_gantt_with_progress(self, data: List[Dict], title: str, group_by: str, height: int) -> go.Figure:
        """
        创建带进度显示的甘特图

        Args:
            data: 数据列表
            title: 标题
            group_by: 分组字段
            height: 高度

        Returns:
            Plotly Figure对象
        """
        fig = go.Figure()

        # 获取唯一的资源/分组
        resources = list(set(item['Resource'] for item in data))
        colors = self.COLOR_SCHEMES.get(self.color_scheme, self.COLOR_SCHEMES['default'])
        color_map = {resource: colors[i % len(colors)] for i, resource in enumerate(resources)}

        # 为每个任务添加两个条形：背景条（完整时间）和前景条（已完成部分）
        for item in data:
            resource = item['Resource']
            color = color_map[resource]

            # 背景条（未完成部分）
            fig.add_trace(go.Bar(
                name=resource,
                y=[item['Task']],
                x=[(item['Finish'] - item['Start']).total_seconds() / 86400],
                base=item['Start'],
                orientation='h',
                marker=dict(
                    color=color,
                    opacity=0.3,
                    line=dict(color=color, width=1)
                ),
                text=f"{item['Task']}<br>进度: {item['Progress']:.0f}%",
                textposition='inside',
                hovertemplate=(
                    f"<b>{item['Task']}</b><br>" +
                    f"开始: {item['Start'].strftime('%Y-%m-%d')}<br>" +
                    f"结束: {item['Finish'].strftime('%Y-%m-%d')}<br>" +
                    f"负责人: {item['Owner']}<br>" +
                    f"分类: {item['Category']}<br>" +
                    f"持续: {item['Duration']} 天<br>" +
                    f"进度: {item['Progress']:.0f}%<br>" +
                    "<extra></extra>"
                ),
                showlegend=False
            ))

            # 前景条（已完成部分）
            if item['Progress'] > 0:
                completed_duration = (item['Finish'] - item['Start']).total_seconds() / 86400 * (item['Progress'] / 100)
                fig.add_trace(go.Bar(
                    name=resource,
                    y=[item['Task']],
                    x=[completed_duration],
                    base=item['Start'],
                    orientation='h',
                    marker=dict(
                        color=color,
                        opacity=0.8,
                        line=dict(color=color, width=1)
                    ),
                    hovertemplate=(
                        f"<b>{item['Task']}</b><br>" +
                        f"已完成: {item['Progress']:.0f}%<br>" +
                        "<extra></extra>"
                    ),
                    showlegend=False
                ))

        # 添加图例（每个资源只添加一次）
        for resource in resources:
            fig.add_trace(go.Bar(
                name=resource,
                y=[None],
                x=[None],
                marker=dict(color=color_map[resource]),
                showlegend=True
            ))

        return fig

    def _customize_layout(self, title: str, height: int):
        """
        自定义图表布局

        Args:
            title: 标题
            height: 高度
        """
        # 计算合适的高度（根据任务数量）
        task_count = len(self.tasks)
        dynamic_height = max(height, task_count * 40 + 200)

        self.fig.update_layout(
            title={
                'text': title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 24, 'color': '#2c3e50'}
            },
            xaxis={
                'title': '时间轴',
                'type': 'date',
                'tickformat': '%Y-%m-%d',
                'tickangle': -45,
                'showgrid': True,
                'gridcolor': '#ecf0f1',
                'zeroline': False
            },
            yaxis={
                'title': '任务',
                'autorange': 'reversed',  # 从上到下显示
                'showgrid': True,
                'gridcolor': '#ecf0f1'
            },
            height=dynamic_height,
            margin=dict(l=200, r=50, t=100, b=100),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            bargap=0.2,
            barmode='overlay',  # 允许条形重叠（用于进度显示）
            font=dict(family="Microsoft YaHei, Arial, sans-serif", size=12),
            legend=dict(
                title=dict(text='分组'),
                orientation='v',
                yanchor='top',
                y=1,
                xanchor='left',
                x=1.02
            )
        )

        # 添加今天的日期线
        today = datetime.now()
        min_date = min(task['start_date'] for task in self.tasks)
        max_date = max(task['end_date'] for task in self.tasks)

        if min_date <= today <= max_date:
            self.fig.add_vline(
                x=today.timestamp() * 1000,
                line_dash="dash",
                line_color="red",
                annotation_text="今天",
                annotation_position="top"
            )

    def save_html(self, file_path: str, auto_open: bool = False):
        """
        保存为HTML文件

        Args:
            file_path: 保存路径
            auto_open: 是否自动在浏览器中打开
        """
        if self.fig is None:
            raise ValueError("请先调用 generate() 方法生成图表")

        try:
            self.fig.write_html(
                file_path,
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': 'gantt_chart',
                        'height': 800,
                        'width': 1200,
                        'scale': 2
                    }
                },
                auto_open=auto_open
            )
            logger.info(f"甘特图已保存到: {file_path}")

        except Exception as e:
            logger.error(f"保存HTML文件失败: {str(e)}")
            raise

    def save_image(self, file_path: str, format: str = 'png', width: int = 1200, height: int = 800):
        """
        保存为图片文件

        Args:
            file_path: 保存路径
            format: 图片格式 ('png', 'jpg', 'svg', 'pdf')
            width: 图片宽度
            height: 图片高度
        """
        if self.fig is None:
            raise ValueError("请先调用 generate() 方法生成图表")

        try:
            self.fig.write_image(file_path, format=format, width=width, height=height, scale=2)
            logger.info(f"甘特图已保存为图片: {file_path}")

        except Exception as e:
            logger.error(f"保存图片失败: {str(e)}")
            logger.warning("图片导出需要安装 kaleido 库: pip install kaleido")
            raise

    def get_html_string(self) -> str:
        """
        获取HTML字符串

        Returns:
            完整的HTML字符串
        """
        if self.fig is None:
            raise ValueError("请先调用 generate() 方法生成图表")

        return self.fig.to_html(
            config={
                'displayModeBar': True,
                'displaylogo': False
            },
            include_plotlyjs='cdn',
            full_html=True
        )

    def get_json(self) -> str:
        """
        获取JSON格式的图表数据

        Returns:
            JSON字符串
        """
        if self.fig is None:
            raise ValueError("请先调用 generate() 方法生成图表")

        return self.fig.to_json()
