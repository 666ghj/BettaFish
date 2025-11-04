"""
传感器数据库测试脚本
用于测试传感器数据查询功能
"""

import os
from InsightEngine.utils.config import load_config
from InsightEngine.tools.sensor_search import SensorDataDB


def test_database_connection(config):
    """测试数据库连接"""
    print("\n" + "="*60)
    print("测试 1: 数据库连接")
    print("="*60)

    try:
        # 从配置获取表名
        db = SensorDataDB(table_name=config.sensor_table_name)
        print("✅ 数据库客户端创建成功")
        print(f"   使用表名: {db.table_name}")
        return db
    except Exception as e:
        print(f"❌ 数据库客户端创建失败: {e}")
        return None


def test_query_latest_data(db: SensorDataDB):
    """测试查询最新数据"""
    print("\n" + "="*60)
    print("测试 2: 查询最新数据")
    print("="*60)

    try:
        response = db.query_latest_data(limit=5)

        if response.error_message:
            print(f"❌ 查询失败: {response.error_message}")
            return

        print(f"✅ 查询成功，共 {response.results_count} 条数据")

        for i, data_point in enumerate(response.results[:3], 1):
            print(f"\n数据点 {i}:")
            print(f"  ID: {data_point.id}")
            print(f"  时间: {data_point.timestamp}")
            print(f"  传感器类型: {', '.join(data_point.sensor_types)}")
            print(f"  数据: {data_point.sensor_data}")

    except Exception as e:
        print(f"❌ 查询出错: {e}")


def test_query_by_time_range(db: SensorDataDB):
    """测试按时间范围查询"""
    print("\n" + "="*60)
    print("测试 3: 按时间范围查询")
    print("="*60)

    try:
        from datetime import datetime, timedelta

        # 查询最近24小时的数据
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        response = db.query_by_time_range(
            start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
            limit=10
        )

        if response.error_message:
            print(f"❌ 查询失败: {response.error_message}")
            return

        print(f"✅ 查询最近24小时数据成功")
        print(f"   时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   共 {response.results_count} 条数据")

        if response.results:
            print(f"\n最新一条数据:")
            data = response.results[0]
            print(f"  时间: {data.timestamp}")
            print(f"  数据: {data.sensor_data}")

    except Exception as e:
        print(f"❌ 查询出错: {e}")


def test_statistical_summary(db: SensorDataDB):
    """测试统计摘要"""
    print("\n" + "="*60)
    print("测试 4: 统计摘要")
    print("="*60)

    try:
        from datetime import datetime, timedelta

        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        response = db.query_statistical_summary(
            start_time=start_time.strftime('%Y-%m-%d'),
            end_time=end_time.strftime('%Y-%m-%d')
        )

        if response.error_message:
            print(f"❌ 统计失败: {response.error_message}")
            return

        print(f"✅ 统计成功，共分析 {len(response.statistics)} 个传感器类型")
        print(f"   时间范围: {start_time.strftime('%Y-%m-%d')} ~ {end_time.strftime('%Y-%m-%d')}")

        if response.statistics:
            print("\n统计结果:")
            print(f"{'传感器类型':<15} {'样本数':<8} {'最小值':<12} {'平均值':<12} {'最大值':<12} {'标准差':<12}")
            print("-" * 80)

            for stat in response.statistics[:5]:
                print(f"{stat.sensor_type:<15} {stat.count:<8} "
                      f"{stat.min_value:<12.2f} {stat.avg_value:<12.2f} "
                      f"{stat.max_value:<12.2f} {stat.std_dev:<12.2f}")

    except Exception as e:
        print(f"❌ 统计出错: {e}")


def test_anomaly_detection(db: SensorDataDB):
    """测试异常检测"""
    print("\n" + "="*60)
    print("测试 5: 异常检测")
    print("="*60)

    try:
        # 获取可用的传感器类型
        latest_response = db.query_latest_data(limit=1)
        if not latest_response.results:
            print("❌ 没有可用数据进行异常检测")
            return

        sensor_types = latest_response.results[0].sensor_types
        if not sensor_types:
            print("❌ 没有可用的传感器类型")
            return

        # 选择第一个传感器进行异常检测
        sensor_type = sensor_types[0]
        print(f"正在检测传感器: {sensor_type}")

        response = db.query_anomaly_detection(
            sensor_type=sensor_type,
            threshold_std_dev=2.0,
            time_range_hours=24
        )

        if response.error_message:
            print(f"❌ 异常检测失败: {response.error_message}")
            return

        print(f"✅ 异常检测完成")
        print(f"   检测的传感器: {sensor_type}")
        print(f"   时间范围: 最近24小时")
        print(f"   检测到异常: {response.results_count} 条")

        if response.results:
            print("\n异常数据点:")
            for i, data in enumerate(response.results[:5], 1):
                value = data.sensor_data.get(sensor_type, 'N/A')
                print(f"  {i}. 时间: {data.timestamp}, 值: {value}")

    except Exception as e:
        print(f"❌ 异常检测出错: {e}")


def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("传感器数据库测试开始")
    print("="*60)

    # 1. 加载配置
    print("\n步骤 1: 加载配置文件")
    try:
        config = load_config()
        print("✅ 配置文件加载成功")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        print("   请确保已创建 config.py 文件（可以从 config.py.example 复制）")
        return

    # 2. 设置数据库环境变量（用于SensorDataDB的连接）
    print("\n步骤 2: 设置数据库连接环境变量")
    os.environ["DB_HOST"] = config.db_host or ""
    os.environ["DB_USER"] = config.db_user or ""
    os.environ["DB_PASSWORD"] = config.db_password or ""
    os.environ["DB_NAME"] = config.db_name or ""
    os.environ["DB_PORT"] = str(config.db_port)
    os.environ["DB_CHARSET"] = config.db_charset
    print(f"✅ 数据库配置: {config.db_host}:{config.db_port}/{config.db_name}")
    print(f"✅ 传感器表名: {config.sensor_table_name}")

    # 3. 测试数据库连接
    print("\n步骤 3: 测试数据库连接")
    db = test_database_connection(config)
    if not db:
        print("\n❌ 数据库连接失败，测试终止")
        return

    # 4. 测试各项功能
    test_query_latest_data(db)
    test_query_by_time_range(db)
    test_statistical_summary(db)
    test_anomaly_detection(db)

    print("\n" + "="*60)
    print("所有测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
