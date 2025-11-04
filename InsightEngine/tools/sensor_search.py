"""
专为 AI Agent 设计的传感器数据库查询工具集 (SensorDataDB)

版本: 1.0
创建日期: 2025-01-XX

此脚本将传感器数据查询功能封装成一系列目标明确、参数清晰的独立工具，
专为AI Agent调用而设计。Agent根据用户需求选择合适的查询工具。

数据表结构:
- id: 数据唯一ID
- sensor_data: JSON数据（包含多个传感器的数据）
- timestamp: 数据时间戳

主要工具:
- query_by_time_range: 按时间范围查询传感器数据
- query_latest_data: 查询最新的传感器数据
- query_by_sensor_type: 按传感器类型查询数据
- query_statistical_summary: 查询时间段内的统计摘要
- query_anomaly_detection: 查询异常数据
"""

import os
import json
import pymysql
import pymysql.cursors
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics

# --- 1. 数据结构定义 ---

@dataclass
class SensorDataPoint:
    """传感器数据点"""
    id: str
    timestamp: datetime
    sensor_data: Dict[str, Any]  # JSON数据解析后的字典
    sensor_types: List[str] = field(default_factory=list)  # 包含的传感器类型列表

@dataclass
class StatisticalSummary:
    """统计摘要"""
    sensor_type: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    median_value: float
    std_dev: float

@dataclass
class DBResponse:
    """封装工具的完整返回结果"""
    tool_name: str
    parameters: Dict[str, Any]
    results: List[SensorDataPoint] = field(default_factory=list)
    statistics: List[StatisticalSummary] = field(default_factory=list)
    results_count: int = 0
    error_message: Optional[str] = None

# --- 2. 核心客户端与专用工具集 ---

class SensorDataDB:
    """传感器数据库查询工具客户端"""

    def __init__(self, table_name: str = "sensor_data"):
        """
        初始化客户端。连接信息从环境变量自动读取:
        - DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
        - DB_PORT (可选, 默认 3306)
        - DB_CHARSET (可选, 默认 utf8mb4)

        Args:
            table_name: 传感器数据表名，默认为 "sensor_data"。
                       建议从 config.py 的 SENSOR_TABLE_NAME 配置项获取。
        """
        self.table_name = table_name
        self.db_config = {
            'host': os.getenv("DB_HOST"),
            'user': os.getenv("DB_USER"),
            'password': os.getenv("DB_PASSWORD"),
            'db': os.getenv("DB_NAME"),
            'port': int(os.getenv("DB_PORT", 3306)),
            'charset': os.getenv("DB_CHARSET", "utf8mb4"),
            'cursorclass': pymysql.cursors.DictCursor
        }
        required = ['host', 'user', 'password', 'db']
        if missing := [k for k in required if not self.db_config[k]]:
            raise ValueError(f"数据库配置缺失! 请设置环境变量: {', '.join([f'DB_{k.upper()}' for k in missing])}")

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except pymysql.Error as e:
            print(f"数据库查询时发生错误: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def _parse_sensor_data(self, row: Dict[str, Any]) -> SensorDataPoint:
        """解析数据库行为SensorDataPoint对象"""
        sensor_data_json = row.get('sensor_data', '{}')
        if isinstance(sensor_data_json, str):
            try:
                sensor_data = json.loads(sensor_data_json)
            except json.JSONDecodeError:
                sensor_data = {}
        else:
            sensor_data = sensor_data_json

        timestamp = row.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        sensor_types = list(sensor_data.keys()) if isinstance(sensor_data, dict) else []

        return SensorDataPoint(
            id=str(row.get('id', '')),
            timestamp=timestamp,
            sensor_data=sensor_data,
            sensor_types=sensor_types
        )

    def query_by_time_range(
        self,
        start_time: str,
        end_time: str,
        limit: int = 1000,
        sensor_types: Optional[List[str]] = None
    ) -> DBResponse:
        """
        【工具】按时间范围查询传感器数据

        Args:
            start_time: 开始时间，格式 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'
            end_time: 结束时间，格式 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'
            limit: 返回结果的最大数量，默认为 1000
            sensor_types: 要查询的传感器类型列表，如果为None则返回所有类型

        Returns:
            DBResponse: 包含查询结果的响应对象
        """
        params_for_log = {
            'start_time': start_time,
            'end_time': end_time,
            'limit': limit,
            'sensor_types': sensor_types
        }
        print(f"--- TOOL: 按时间范围查询传感器数据 (params: {params_for_log}) ---")

        try:
            # 解析时间
            start_dt = datetime.fromisoformat(start_time.replace(' ', 'T'))
            end_dt = datetime.fromisoformat(end_time.replace(' ', 'T'))
        except ValueError as e:
            return DBResponse(
                "query_by_time_range",
                params_for_log,
                error_message=f"时间格式错误: {e}"
            )

        query = f"""
            SELECT id, sensor_data, timestamp
            FROM {self.table_name}
            WHERE timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp DESC
            LIMIT %s
        """

        raw_results = self._execute_query(query, (start_dt, end_dt, limit))

        results = []
        for row in raw_results:
            data_point = self._parse_sensor_data(row)

            # 如果指定了传感器类型，过滤数据
            if sensor_types:
                filtered_data = {k: v for k, v in data_point.sensor_data.items() if k in sensor_types}
                if filtered_data:
                    data_point.sensor_data = filtered_data
                    data_point.sensor_types = list(filtered_data.keys())
                    results.append(data_point)
            else:
                results.append(data_point)

        return DBResponse(
            "query_by_time_range",
            params_for_log,
            results=results,
            results_count=len(results)
        )

    def query_latest_data(
        self,
        limit: int = 100,
        sensor_types: Optional[List[str]] = None
    ) -> DBResponse:
        """
        【工具】查询最新的传感器数据

        Args:
            limit: 返回结果的最大数量，默认为 100
            sensor_types: 要查询的传感器类型列表，如果为None则返回所有类型

        Returns:
            DBResponse: 包含查询结果的响应对象
        """
        params_for_log = {'limit': limit, 'sensor_types': sensor_types}
        print(f"--- TOOL: 查询最新传感器数据 (params: {params_for_log}) ---")

        query = f"""
            SELECT id, sensor_data, timestamp
            FROM {self.table_name}
            ORDER BY timestamp DESC
            LIMIT %s
        """

        raw_results = self._execute_query(query, (limit,))

        results = []
        for row in raw_results:
            data_point = self._parse_sensor_data(row)

            if sensor_types:
                filtered_data = {k: v for k, v in data_point.sensor_data.items() if k in sensor_types}
                if filtered_data:
                    data_point.sensor_data = filtered_data
                    data_point.sensor_types = list(filtered_data.keys())
                    results.append(data_point)
            else:
                results.append(data_point)

        return DBResponse(
            "query_latest_data",
            params_for_log,
            results=results,
            results_count=len(results)
        )

    def query_statistical_summary(
        self,
        start_time: str,
        end_time: str,
        sensor_types: Optional[List[str]] = None,
        group_by_hours: int = 1
    ) -> DBResponse:
        """
        【工具】查询时间段内的统计摘要

        Args:
            start_time: 开始时间，格式 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'
            end_time: 结束时间，格式 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'
            sensor_types: 要统计的传感器类型列表
            group_by_hours: 按小时分组，默认为1小时

        Returns:
            DBResponse: 包含统计摘要的响应对象
        """
        params_for_log = {
            'start_time': start_time,
            'end_time': end_time,
            'sensor_types': sensor_types,
            'group_by_hours': group_by_hours
        }
        print(f"--- TOOL: 查询统计摘要 (params: {params_for_log}) ---")

        try:
            start_dt = datetime.fromisoformat(start_time.replace(' ', 'T'))
            end_dt = datetime.fromisoformat(end_time.replace(' ', 'T'))
        except ValueError as e:
            return DBResponse(
                "query_statistical_summary",
                params_for_log,
                error_message=f"时间格式错误: {e}"
            )

        # 查询数据
        query = f"""
            SELECT sensor_data, timestamp
            FROM {self.table_name}
            WHERE timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        raw_results = self._execute_query(query, (start_dt, end_dt))

        # 解析并统计
        sensor_values = {}  # {sensor_type: [values]}

        for row in raw_results:
            data_point = self._parse_sensor_data(row)

            for sensor_type, value in data_point.sensor_data.items():
                if sensor_types and sensor_type not in sensor_types:
                    continue

                if sensor_type not in sensor_values:
                    sensor_values[sensor_type] = []

                # 尝试转换为数值
                try:
                    if isinstance(value, (int, float)):
                        sensor_values[sensor_type].append(float(value))
                    elif isinstance(value, str):
                        sensor_values[sensor_type].append(float(value))
                except (ValueError, TypeError):
                    continue

        # 计算统计信息
        statistics_list = []
        for sensor_type, values in sensor_values.items():
            if not values:
                continue

            statistics_list.append(StatisticalSummary(
                sensor_type=sensor_type,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                avg_value=statistics.mean(values),
                median_value=statistics.median(values),
                std_dev=statistics.stdev(values) if len(values) > 1 else 0.0
            ))

        return DBResponse(
            "query_statistical_summary",
            params_for_log,
            statistics=statistics_list,
            results_count=len(statistics_list)
        )

    def query_anomaly_detection(
        self,
        sensor_type: str,
        threshold_std_dev: float = 2.0,
        time_range_hours: int = 24,
        limit: int = 100
    ) -> DBResponse:
        """
        【工具】查询异常数据（基于标准差的简单异常检测）

        Args:
            sensor_type: 要检测异常的传感器类型
            threshold_std_dev: 标准差倍数阈值，默认为2.0（超过2个标准差视为异常）
            time_range_hours: 查询最近多少小时的数据，默认24小时
            limit: 返回异常数据的最大数量，默认为100

        Returns:
            DBResponse: 包含异常数据点的响应对象
        """
        params_for_log = {
            'sensor_type': sensor_type,
            'threshold_std_dev': threshold_std_dev,
            'time_range_hours': time_range_hours,
            'limit': limit
        }
        print(f"--- TOOL: 异常检测 (params: {params_for_log}) ---")

        # 查询最近的数据
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_range_hours)

        query = f"""
            SELECT id, sensor_data, timestamp
            FROM {self.table_name}
            WHERE timestamp >= %s
            ORDER BY timestamp DESC
        """

        raw_results = self._execute_query(query, (start_time,))

        # 收集数值
        values = []
        data_points = []

        for row in raw_results:
            data_point = self._parse_sensor_data(row)

            if sensor_type in data_point.sensor_data:
                try:
                    value = float(data_point.sensor_data[sensor_type])
                    values.append(value)
                    data_points.append((data_point, value))
                except (ValueError, TypeError):
                    continue

        if len(values) < 2:
            return DBResponse(
                "query_anomaly_detection",
                params_for_log,
                error_message="数据不足，无法进行异常检测"
            )

        # 计算统计量
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        threshold = threshold_std_dev * std_val

        # 找出异常点
        anomalies = []
        for data_point, value in data_points:
            if abs(value - mean_val) > threshold:
                anomalies.append(data_point)
                if len(anomalies) >= limit:
                    break

        print(f"  - 检测到 {len(anomalies)} 个异常数据点")
        print(f"  - 正常范围: {mean_val - threshold:.2f} ~ {mean_val + threshold:.2f}")

        return DBResponse(
            "query_anomaly_detection",
            params_for_log,
            results=anomalies,
            results_count=len(anomalies)
        )


# --- 3. 工厂函数 ---

def create_sensor_db_client(table_name: str = "sensor_data") -> SensorDataDB:
    """
    创建传感器数据库客户端的工厂函数

    Args:
        table_name: 传感器数据表名，默认为 "sensor_data"。
                   建议从 config.py 的 SENSOR_TABLE_NAME 配置项获取。

    Returns:
        SensorDataDB: 传感器数据库客户端实例
    """
    return SensorDataDB(table_name)
