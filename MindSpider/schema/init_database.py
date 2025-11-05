#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MindSpider AI爬虫项目 - 数据库初始化脚本
用于创建项目所需的所有数据库表
"""

import os
import sys
import pymysql
from pathlib import Path
from MindSpider.config import settings

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# 导入配置
try:
    import config
except ImportError:
    print("错误: 无法导入config.py配置文件")
    print("请确保config.py文件存在于项目根目录")
    sys.exit(1)

def create_database_connection():
    """创建数据库连接"""
    try:
        connection = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            charset=settings.db_charset,
            autocommit=True
        )
        print(f"成功连接到MySQL服务器: {settings.db_host}:{settings.db_port}")
        return connection
    except Exception as e:
        print(f"连接数据库失败: {e}")
        return None

def create_database(connection):
    """创建数据库"""
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE `{settings.db_name}`")
        print(f"数据库 '{settings.db_name}' 创建/选择成功")
        return True
    except Exception as e:
        print(f"创建数据库失败: {e}")
        return False

def execute_sql_file(connection, sql_file_path, description=""):
    """执行SQL文件"""
    if not os.path.exists(sql_file_path):
        print(f"警告: SQL文件不存在: {sql_file_path}")
        return False

    try:
        cursor = connection.cursor()
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割SQL语句（简单实现，按分号分割）
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        success_count = 0
        error_count = 0

        for stmt in sql_statements:
            if not stmt or stmt.startswith('--'):
                continue
            try:
                cursor.execute(stmt)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"执行SQL语句失败: {str(e)[:100]}...")

        print(f"{description} - 成功执行: {success_count} 条语句, 失败: {error_count} 条语句")
        return error_count == 0

    except Exception as e:
        print(f"执行SQL文件失败 {sql_file_path}: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("MindSpider AI爬虫项目 - 数据库初始化")
    print("=" * 60)

    # 检查配置
    print("检查数据库配置...")
    print(f"数据库主机: {settings.db_host}")
    print(f"数据库端口: {settings.db_port}")
    print(f"数据库名称: {settings.db_name}")
    print(f"数据库用户: {settings.db_user}")
    print(f"字符集: {settings.db_charset}")
    print()

    # 创建数据库连接
    print("正在连接数据库...")
    connection = create_database_connection()
    if not connection:
        print("数据库初始化失败！")
        return False

    try:
        # 创建数据库
        print("正在创建/选择数据库...")
        if not create_database(connection):
            return False

        # 获取SQL文件路径
        schema_dir = Path(__file__).parent
        mediacrawler_sql = schema_dir.parent / "DeepSentimentCrawling" / "MediaCrawler" / "schema" / "tables.sql"
        mindspider_sql = schema_dir / "mindspider_tables.sql"

        print()
        print("开始执行SQL脚本...")

        # 1. 执行MediaCrawler的原始表结构
        if mediacrawler_sql.exists():
            print("1. 创建MediaCrawler基础表...")
            execute_sql_file(connection, str(mediacrawler_sql), "MediaCrawler基础表")
        else:
            print("警告: MediaCrawler SQL文件不存在，跳过基础表创建")

        # 2. 执行MindSpider扩展表结构
        print("2. 创建MindSpider扩展表...")
        if mindspider_sql.exists():
            execute_sql_file(connection, str(mindspider_sql), "MindSpider扩展表")
        else:
            print("错误: MindSpider SQL文件不存在")
            return False

        print()
        print("=" * 60)
        print("数据库初始化完成！")
        print("=" * 60)

        # 显示创建的表
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        print(f"数据库 '{settings.db_name}' 中共创建了 {len(tables)} 个表:")
        for table in tables:
            print(f"  - {table[0]}")
        
        print()
        print("数据库初始化成功完成！您现在可以开始使用MindSpider了。")
        return True
        
    except Exception as e:
        print(f"数据库初始化过程中发生错误: {e}")
        return False
    
    finally:
        if connection:
            connection.close()
            print("数据库连接已关闭")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
