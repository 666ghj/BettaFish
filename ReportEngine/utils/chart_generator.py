"""
图表生成工具
使用ECharts生成各种数据可视化图表
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime


class ChartGenerator:
    """图表生成器"""

    @staticmethod
    def generate_time_series_chart(
        data_points: List[Dict[str, Any]],
        sensor_type: str,
        title: Optional[str] = None,
        chart_id: str = "chart1"
    ) -> str:
        """
        生成时间序列折线图

        Args:
            data_points: 数据点列表，每个点包含timestamp和value
            sensor_type: 传感器类型（用于标签）
            title: 图表标题
            chart_id: 图表容器ID

        Returns:
            ECharts配置的JavaScript代码
        """
        if not data_points:
            return ""

        # 提取时间戳和数值
        timestamps = []
        values = []

        for point in data_points:
            if 'timestamp' in point and sensor_type in point:
                try:
                    ts = point['timestamp']
                    if isinstance(ts, datetime):
                        timestamps.append(ts.strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        timestamps.append(str(ts))

                    value = point[sensor_type]
                    values.append(float(value) if value is not None else 0)
                except (ValueError, TypeError, KeyError):
                    continue

        if not timestamps or not values:
            return ""

        chart_title = title or f"{sensor_type} 时间序列图"

        chart_config = {
            "title": {
                "text": chart_title,
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis"
            },
            "xAxis": {
                "type": "category",
                "data": timestamps,
                "axisLabel": {
                    "rotate": 45
                }
            },
            "yAxis": {
                "type": "value",
                "name": sensor_type
            },
            "series": [{
                "name": sensor_type,
                "type": "line",
                "data": values,
                "smooth": True,
                "lineStyle": {
                    "width": 2
                },
                "itemStyle": {
                    "color": "#5470c6"
                }
            }],
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "15%",
                "containLabel": True
            }
        }

        js_code = f"""
        <div id="{chart_id}" style="width: 100%; height: 400px;"></div>
        <script>
            var {chart_id}_chart = echarts.init(document.getElementById('{chart_id}'));
            var {chart_id}_option = {json.dumps(chart_config, ensure_ascii=False)};
            {chart_id}_chart.setOption({chart_id}_option);
        </script>
        """

        return js_code

    @staticmethod
    def generate_statistical_chart(
        statistics: List[Dict[str, Any]],
        chart_id: str = "chart2"
    ) -> str:
        """
        生成统计柱状图（显示多个传感器的统计指标）

        Args:
            statistics: 统计数据列表，每项包含sensor_type和统计指标
            chart_id: 图表容器ID

        Returns:
            ECharts配置的JavaScript代码
        """
        if not statistics:
            return ""

        sensor_types = []
        min_values = []
        max_values = []
        avg_values = []

        for stat in statistics:
            try:
                sensor_types.append(stat.get('sensor_type', ''))
                min_values.append(float(stat.get('min_value', 0)))
                max_values.append(float(stat.get('max_value', 0)))
                avg_values.append(float(stat.get('avg_value', 0)))
            except (ValueError, TypeError, KeyError):
                continue

        if not sensor_types:
            return ""

        chart_config = {
            "title": {
                "text": "传感器数据统计",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {
                    "type": "shadow"
                }
            },
            "legend": {
                "data": ["最小值", "平均值", "最大值"],
                "top": "10%"
            },
            "xAxis": {
                "type": "category",
                "data": sensor_types
            },
            "yAxis": {
                "type": "value",
                "name": "数值"
            },
            "series": [
                {
                    "name": "最小值",
                    "type": "bar",
                    "data": min_values,
                    "itemStyle": {"color": "#91cc75"}
                },
                {
                    "name": "平均值",
                    "type": "bar",
                    "data": avg_values,
                    "itemStyle": {"color": "#fac858"}
                },
                {
                    "name": "最大值",
                    "type": "bar",
                    "data": max_values,
                    "itemStyle": {"color": "#ee6666"}
                }
            ],
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "containLabel": True
            }
        }

        js_code = f"""
        <div id="{chart_id}" style="width: 100%; height: 400px;"></div>
        <script>
            var {chart_id}_chart = echarts.init(document.getElementById('{chart_id}'));
            var {chart_id}_option = {json.dumps(chart_config, ensure_ascii=False)};
            {chart_id}_chart.setOption({chart_id}_option);
        </script>
        """

        return js_code

    @staticmethod
    def generate_anomaly_chart(
        normal_points: List[Dict[str, Any]],
        anomaly_points: List[Dict[str, Any]],
        sensor_type: str,
        chart_id: str = "chart3"
    ) -> str:
        """
        生成异常检测散点图

        Args:
            normal_points: 正常数据点
            anomaly_points: 异常数据点
            sensor_type: 传感器类型
            chart_id: 图表容器ID

        Returns:
            ECharts配置的JavaScript代码
        """
        # 处理正常点
        normal_data = []
        for point in normal_points:
            try:
                ts = point.get('timestamp', '')
                if isinstance(ts, datetime):
                    ts = ts.strftime('%Y-%m-%d %H:%M:%S')
                value = float(point.get(sensor_type, 0))
                normal_data.append([ts, value])
            except (ValueError, TypeError, KeyError):
                continue

        # 处理异常点
        anomaly_data = []
        for point in anomaly_points:
            try:
                ts = point.get('timestamp', '')
                if isinstance(ts, datetime):
                    ts = ts.strftime('%Y-%m-%d %H:%M:%S')
                value = float(point.get(sensor_type, 0))
                anomaly_data.append([ts, value])
            except (ValueError, TypeError, KeyError):
                continue

        if not normal_data and not anomaly_data:
            return ""

        chart_config = {
            "title": {
                "text": f"{sensor_type} 异常检测",
                "left": "center"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{a}<br/>{c}"
            },
            "legend": {
                "data": ["正常数据", "异常数据"],
                "top": "10%"
            },
            "xAxis": {
                "type": "category",
                "name": "时间"
            },
            "yAxis": {
                "type": "value",
                "name": sensor_type
            },
            "series": [
                {
                    "name": "正常数据",
                    "type": "scatter",
                    "data": normal_data,
                    "symbolSize": 6,
                    "itemStyle": {
                        "color": "#5470c6",
                        "opacity": 0.6
                    }
                },
                {
                    "name": "异常数据",
                    "type": "scatter",
                    "data": anomaly_data,
                    "symbolSize": 10,
                    "itemStyle": {
                        "color": "#ee6666",
                        "borderColor": "#d4380d",
                        "borderWidth": 2
                    }
                }
            ],
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "10%",
                "containLabel": True
            }
        }

        js_code = f"""
        <div id="{chart_id}" style="width: 100%; height: 400px;"></div>
        <script>
            var {chart_id}_chart = echarts.init(document.getElementById('{chart_id}'));
            var {chart_id}_option = {json.dumps(chart_config, ensure_ascii=False)};
            {chart_id}_chart.setOption({chart_id}_option);
        </script>
        """

        return js_code

    @staticmethod
    def generate_multi_sensor_chart(
        data_points: List[Dict[str, Any]],
        sensor_types: List[str],
        title: str = "多传感器数据对比",
        chart_id: str = "chart4"
    ) -> str:
        """
        生成多传感器对比图（多条折线）

        Args:
            data_points: 数据点列表
            sensor_types: 要显示的传感器类型列表
            title: 图表标题
            chart_id: 图表容器ID

        Returns:
            ECharts配置的JavaScript代码
        """
        if not data_points or not sensor_types:
            return ""

        # 提取时间戳
        timestamps = []
        for point in data_points:
            ts = point.get('timestamp', '')
            if isinstance(ts, datetime):
                ts = ts.strftime('%Y-%m-%d %H:%M:%S')
            if ts and ts not in timestamps:
                timestamps.append(ts)

        # 为每个传感器准备数据
        series_list = []
        colors = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272"]

        for idx, sensor_type in enumerate(sensor_types):
            values = []
            for point in data_points:
                try:
                    value = point.get(sensor_type)
                    values.append(float(value) if value is not None else None)
                except (ValueError, TypeError):
                    values.append(None)

            series_list.append({
                "name": sensor_type,
                "type": "line",
                "data": values,
                "smooth": True,
                "itemStyle": {
                    "color": colors[idx % len(colors)]
                }
            })

        chart_config = {
            "title": {
                "text": title,
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis"
            },
            "legend": {
                "data": sensor_types,
                "top": "10%"
            },
            "xAxis": {
                "type": "category",
                "data": timestamps,
                "axisLabel": {
                    "rotate": 45
                }
            },
            "yAxis": {
                "type": "value",
                "name": "数值"
            },
            "series": series_list,
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "15%",
                "containLabel": True
            }
        }

        js_code = f"""
        <div id="{chart_id}" style="width: 100%; height: 400px;"></div>
        <script>
            var {chart_id}_chart = echarts.init(document.getElementById('{chart_id}'));
            var {chart_id}_option = {json.dumps(chart_config, ensure_ascii=False)};
            {chart_id}_chart.setOption({chart_id}_option);
        </script>
        """

        return js_code

    @staticmethod
    def get_echarts_header() -> str:
        """获取ECharts库引用的HTML头部代码"""
        return """
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        """


# 便捷函数
def create_time_series_chart(data_points, sensor_type, **kwargs):
    """创建时间序列图表的便捷函数"""
    return ChartGenerator.generate_time_series_chart(data_points, sensor_type, **kwargs)


def create_statistical_chart(statistics, **kwargs):
    """创建统计图表的便捷函数"""
    return ChartGenerator.generate_statistical_chart(statistics, **kwargs)


def create_anomaly_chart(normal_points, anomaly_points, sensor_type, **kwargs):
    """创建异常检测图表的便捷函数"""
    return ChartGenerator.generate_anomaly_chart(normal_points, anomaly_points, sensor_type, **kwargs)


def create_multi_sensor_chart(data_points, sensor_types, **kwargs):
    """创建多传感器对比图表的便捷函数"""
    return ChartGenerator.generate_multi_sensor_chart(data_points, sensor_types, **kwargs)
