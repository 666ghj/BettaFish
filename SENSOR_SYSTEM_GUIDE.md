# 传感器数据分析系统改造指南

## 系统概述

将原有的舆情分析系统改造为城市传感器数据分析系统，主要功能：
- 查询传感器数据库（结构：ID + JSON数据 + 时间戳）
- 根据用户需求智能分析数据
- 生成包含图表的可视化报告
- 保留ForumEngine用于多维度数据分析协作

## 数据库结构

### 传感器数据表
```sql
CREATE TABLE sensor_data (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sensor_data JSON NOT NULL COMMENT '传感器JSON数据',
    timestamp DATETIME NOT NULL COMMENT '数据时间戳',
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### JSON数据示例
```json
{
    "temperature": 25.5,
    "humidity": 60.2,
    "pressure": 1013.25,
    "pm25": 35,
    "location": "sensor_001"
}
```

## 核心功能模块

### 1. 传感器数据查询工具 (✅ 已完成)

文件：`InsightEngine/tools/sensor_search.py`

**主要工具**：
- `query_by_time_range`: 按时间范围查询
- `query_latest_data`: 查询最新数据
- `query_statistical_summary`: 统计摘要
- `query_anomaly_detection`: 异常检测

### 2. InsightAgent 改造

需要修改的文件：
- `InsightEngine/agent.py` - 使用传感器工具替代社交媒体工具
- `InsightEngine/prompts/prompts.py` - 更新为传感器分析prompts
- `InsightEngine/utils/config.py` - 添加传感器数据配置

**关键改造点**：
1. 移除社交媒体相关工具引用
2. 移除情感分析功能
3. 简化查询逻辑，不需要关键词优化
4. 更新prompts以适配传感器数据分析场景

### 3. 报告生成增强

需要添加图表支持：
- 使用 ECharts 生成交互式图表
- 支持时间序列图、统计图、异常点标记

**报告类型**：
1. **历史数据分析报告**
   - 显示指定时间范围内的数据趋势
   - 包含基本统计信息（最大/最小/平均值）

2. **周期对比分析报告**
   - 按小时/天/周/月聚合数据
   - 对比不同周期的数据变化

3. **异常检测报告**
   - 标记异常数据点
   - 分析异常原因和趋势

### 4. ForumEngine 用途调整

保留ForumEngine，用于：
- 多传感器类型的协同分析
- 不同时间段的对比讨论
- 异常原因的推理和讨论

## 配置步骤

### Step 1: 数据库设置

```bash
# 在config.py中设置
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "your_username"
DB_PASSWORD = "your_password"
DB_NAME = "sensor_database"
SENSOR_TABLE_NAME = "sensor_data"
```

### Step 2: 更新配置文件

创建 `InsightEngine/utils/sensor_config.py`：
```python
@dataclass
class SensorConfig:
    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = ""
    db_password: str = ""
    db_name: str = "sensor_database"
    sensor_table_name: str = "sensor_data"

    # 查询配置
    default_query_limit: int = 1000
    default_statistical_hours: int = 24
    anomaly_threshold_std_dev: float = 2.0

    # LLM配置
    llm_api_key: str = ""
    llm_model_name: str = "gpt-4"
    llm_base_url: str = "https://api.openai.com/v1"
```

### Step 3: 更新Agent Prompts

传感器数据分析的system prompt应该包含：

```
你是一位专业的城市传感器数据分析师。你的任务是：
1. 理解用户对传感器数据的分析需求
2. 选择合适的查询工具获取数据
3. 进行统计分析和异常检测
4. 生成包含图表的可视化报告

可用工具：
- query_by_time_range: 查询指定时间范围的传感器数据
- query_latest_data: 获取最新的传感器读数
- query_statistical_summary: 计算统计摘要（最大/最小/平均/标准差）
- query_anomaly_detection: 检测异常数据点

数据库包含的传感器类型：
- temperature: 温度（℃）
- humidity: 湿度（%）
- pressure: 气压（hPa）
- pm25: PM2.5浓度（μg/m³）
- 其他自定义传感器...
```

### Step 4: 图表生成

在 `ReportEngine/utils/chart_generator.py` 中实现：

```python
def generate_time_series_chart(data_points, sensor_type):
    """生成时间序列图表（ECharts配置）"""
    return {
        'type': 'line',
        'data': {
            'timestamps': [...],
            'values': [...]
        },
        'options': {
            'title': f'{sensor_type} 趋势图',
            'smooth': True
        }
    }

def generate_statistical_chart(statistics):
    """生成统计图表"""
    pass

def generate_anomaly_chart(data_points, anomalies):
    """生成异常检测图表"""
    pass
```

## 使用示例

### 用户请求示例 1：历史数据分析
```
用户: "分析最近24小时的温度和湿度数据趋势"

系统处理流程:
1. InsightAgent理解需求：查询24小时数据
2. 调用query_by_time_range工具
3. 选择sensor_types=['temperature', 'humidity']
4. 生成包含时间序列图的报告
```

### 用户请求示例 2：异常检测
```
用户: "检测PM2.5是否有异常值"

系统处理流程:
1. InsightAgent选择query_anomaly_detection工具
2. 指定sensor_type='pm25'
3. 标记超过2个标准差的异常点
4. 生成异常检测报告
```

### 用户请求示例 3：周期对比
```
用户: "对比本周和上周的温度变化"

系统处理流程:
1. 分别查询两个时间段的数据
2. 计算统计摘要
3. 生成对比图表
4. ForumEngine分析差异原因
```

## 实施优先级

### 高优先级（核心功能）
1. ✅ 创建传感器数据查询工具
2. 🔄 更新InsightAgent使用传感器工具
3. 🔄 更新Prompts为传感器分析场景
4. ⏳ 移除情感分析和社交媒体功能
5. ⏳ 添加基础图表生成

### 中优先级（增强功能）
6. ⏳ 创建传感器报告模板
7. ⏳ 优化ForumEngine用于传感器数据协作
8. ⏳ 添加更多图表类型

### 低优先级（扩展功能）
9. ⏳ 添加实时数据监控
10. ⏳ 添加预测功能
11. ⏳ 添加告警功能

## 后续开发建议

1. **数据可视化**：集成更丰富的图表库（D3.js, Plotly）
2. **实时分析**：添加WebSocket支持实时数据推送
3. **机器学习**：添加时序预测模型
4. **告警系统**：当检测到异常时自动发送通知

## 文件清单

### 新增文件
- `InsightEngine/tools/sensor_search.py` ✅
- `InsightEngine/utils/sensor_config.py` ⏳
- `ReportEngine/utils/chart_generator.py` ⏳
- `ReportEngine/report_template/传感器数据分析.md` ⏳

### 需要修改的文件
- `InsightEngine/agent.py` ⏳
- `InsightEngine/prompts/prompts.py` ⏳
- `InsightEngine/__init__.py` ⏳
- `ReportEngine/nodes/html_generation_node.py` ⏳
- `app.py` ⏳
- `README.md` ⏳

## 测试用例

```python
# 测试传感器数据查询
from InsightEngine.tools.sensor_search import SensorDataDB

db = SensorDataDB()

# 测试1：按时间范围查询
response = db.query_by_time_range(
    start_time='2025-01-01 00:00:00',
    end_time='2025-01-02 00:00:00',
    sensor_types=['temperature', 'humidity']
)

# 测试2：统计摘要
summary = db.query_statistical_summary(
    start_time='2025-01-01',
    end_time='2025-01-02',
    sensor_types=['pm25']
)

# 测试3：异常检测
anomalies = db.query_anomaly_detection(
    sensor_type='temperature',
    threshold_std_dev=2.0
)
```
