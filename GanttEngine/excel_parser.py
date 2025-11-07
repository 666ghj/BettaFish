"""
Excel文件解析器
读取Excel文件中的任务数据并转换为标准格式
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ExcelParser:
    """Excel文件解析器，支持多种列名格式"""

    # 支持的列名映射（中英文）
    COLUMN_MAPPINGS = {
        'task_name': ['任务名称', '任务', 'Task Name', 'Task', 'task', 'task_name', '项目名称', '项目'],
        'start_date': ['开始日期', '开始时间', 'Start Date', 'Start', 'start', 'start_date', '开始'],
        'end_date': ['结束日期', '结束时间', 'End Date', 'End', 'end', 'end_date', '结束', '完成日期'],
        'owner': ['负责人', '责任人', 'Owner', 'Assignee', 'owner', 'assignee', '成员'],
        'progress': ['进度', '完成度', 'Progress', 'Complete', 'progress', 'complete', '百分比', '完成百分比'],
        'category': ['分类', '类型', 'Category', 'Type', 'category', 'type', '标签']
    }

    def __init__(self, file_path: str):
        """
        初始化解析器

        Args:
            file_path: Excel文件路径
        """
        self.file_path = file_path
        self.df = None
        self.tasks = []

    def parse(self) -> List[Dict[str, Any]]:
        """
        解析Excel文件

        Returns:
            任务列表，每个任务是一个字典
        """
        try:
            # 读取Excel文件
            logger.info(f"正在读取Excel文件: {self.file_path}")
            self.df = pd.read_excel(self.file_path)

            # 检查是否为空
            if self.df.empty:
                raise ValueError("Excel文件为空")

            # 映射列名
            column_map = self._map_columns()
            logger.info(f"列映射结果: {column_map}")

            # 验证必需的列
            required_fields = ['task_name', 'start_date', 'end_date']
            missing_fields = [field for field in required_fields if field not in column_map]
            if missing_fields:
                raise ValueError(f"缺少必需的列: {missing_fields}. 请确保Excel包含任务名称、开始日期和结束日期")

            # 转换数据
            self.tasks = self._convert_to_tasks(column_map)
            logger.info(f"成功解析 {len(self.tasks)} 个任务")

            return self.tasks

        except Exception as e:
            logger.error(f"解析Excel文件失败: {str(e)}")
            raise

    def _map_columns(self) -> Dict[str, str]:
        """
        映射Excel列名到标准字段名

        Returns:
            字段映射字典 {标准字段名: Excel列名}
        """
        column_map = {}
        df_columns = self.df.columns.tolist()

        for standard_name, possible_names in self.COLUMN_MAPPINGS.items():
            for col_name in df_columns:
                if col_name.strip() in possible_names:
                    column_map[standard_name] = col_name
                    break

        return column_map

    def _convert_to_tasks(self, column_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        将DataFrame转换为任务列表

        Args:
            column_map: 列名映射

        Returns:
            任务列表
        """
        tasks = []

        for idx, row in self.df.iterrows():
            try:
                task = {}

                # 必需字段
                task['task_name'] = str(row[column_map['task_name']]).strip()
                task['start_date'] = self._parse_date(row[column_map['start_date']])
                task['end_date'] = self._parse_date(row[column_map['end_date']])

                # 验证日期
                if task['start_date'] > task['end_date']:
                    logger.warning(f"任务 '{task['task_name']}' 的开始日期晚于结束日期，已自动调整")
                    task['start_date'], task['end_date'] = task['end_date'], task['start_date']

                # 可选字段
                if 'owner' in column_map:
                    task['owner'] = str(row[column_map['owner']]).strip() if pd.notna(row[column_map['owner']]) else '未指定'
                else:
                    task['owner'] = '未指定'

                if 'progress' in column_map:
                    progress = row[column_map['progress']]
                    if pd.notna(progress):
                        # 处理百分比字符串（如 "50%"）
                        if isinstance(progress, str) and '%' in progress:
                            progress = float(progress.replace('%', '').strip())
                        else:
                            progress = float(progress)
                        task['progress'] = max(0, min(100, progress))  # 限制在0-100之间
                    else:
                        task['progress'] = 0
                else:
                    task['progress'] = 0

                if 'category' in column_map:
                    task['category'] = str(row[column_map['category']]).strip() if pd.notna(row[column_map['category']]) else '未分类'
                else:
                    task['category'] = '未分类'

                # 计算任务持续天数
                task['duration'] = (task['end_date'] - task['start_date']).days + 1

                tasks.append(task)

            except Exception as e:
                logger.error(f"解析第 {idx + 2} 行数据失败: {str(e)}")
                continue

        return tasks

    def _parse_date(self, date_value) -> datetime:
        """
        解析日期值，支持多种格式

        Args:
            date_value: 日期值（字符串、datetime或pandas Timestamp）

        Returns:
            datetime对象
        """
        if pd.isna(date_value):
            raise ValueError("日期不能为空")

        # 如果已经是datetime对象
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return pd.to_datetime(date_value)

        # 如果是字符串，尝试多种格式
        if isinstance(date_value, str):
            date_formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%Y.%m.%d',
                '%Y年%m月%d日',
                '%m/%d/%Y',
                '%d/%m/%Y',
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_value.strip(), fmt)
                except ValueError:
                    continue

            # 如果所有格式都失败，尝试pandas的智能解析
            try:
                return pd.to_datetime(date_value)
            except:
                raise ValueError(f"无法解析日期: {date_value}")

        # 尝试直接转换
        try:
            return pd.to_datetime(date_value)
        except:
            raise ValueError(f"无法解析日期: {date_value}")

    def get_date_range(self) -> tuple:
        """
        获取所有任务的日期范围

        Returns:
            (最早开始日期, 最晚结束日期)
        """
        if not self.tasks:
            return None, None

        start_dates = [task['start_date'] for task in self.tasks]
        end_dates = [task['end_date'] for task in self.tasks]

        return min(start_dates), max(end_dates)

    def get_summary(self) -> Dict[str, Any]:
        """
        获取解析摘要

        Returns:
            摘要信息字典
        """
        if not self.tasks:
            return {}

        start_date, end_date = self.get_date_range()
        categories = list(set(task['category'] for task in self.tasks))
        owners = list(set(task['owner'] for task in self.tasks))

        return {
            'total_tasks': len(self.tasks),
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'total_days': (end_date - start_date).days + 1 if start_date and end_date else 0,
            'categories': categories,
            'owners': owners,
            'avg_progress': sum(task['progress'] for task in self.tasks) / len(self.tasks)
        }
