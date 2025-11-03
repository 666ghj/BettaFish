#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MindSpider AI爬虫项目 - 数据库管理工具
提供数据库状态查看、数据统计、清理等功能
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    import config
except ImportError:
    logger.error("错误: 无法导入config.py配置文件")
    sys.exit(1)

from MindSpider.config import settings

class DatabaseManager:
    def __init__(self):
        self.engine: Engine = None
        self.connect()
    
    def connect(self):
        """连接数据库"""
        try:
            dialect = (settings.DB_DIALECT or "mysql").lower()
            if dialect in ("postgresql", "postgres"):
                url = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            else:
                url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset={settings.DB_CHARSET}"
            self.engine = create_engine(url, future=True)
            logger.info(f"成功连接到数据库: {settings.DB_NAME}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            sys.exit(1)
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
    
    def show_tables(self):
        """显示所有表"""
        data_list_message = ""
        data_list_message += "\n" + "=" * 60
        data_list_message += "数据库表列表"
        data_list_message += "=" * 60
        logger.info(data_list_message)
        
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        
        if not tables:
            logger.info("数据库中没有表")
            return
        
        # 分类显示表
        mindspider_tables = []
        mediacrawler_tables = []
        
        for table_name in tables:
            if table_name in ['daily_news', 'daily_topics', 'topic_news_relation', 'crawling_tasks']:
                mindspider_tables.append(table_name)
            else:
                mediacrawler_tables.append(table_name)
        
        data_list_message += "MindSpider核心表:"
        data_list_message += "\n"
        for table in mindspider_tables:
            with self.engine.connect() as conn:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            data_list_message += f"  - {table:<25} ({count:>6} 条记录)"
            data_list_message += "\n"
        
        data_list_message += "\nMediaCrawler平台表:"
        data_list_message += "\n"
        for table in mediacrawler_tables:
            try:
                with self.engine.connect() as conn:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                data_list_message += f"  - {table:<25} ({count:>6} 条记录)"
                data_list_message += "\n"
            except:
                data_list_message += f"  - {table:<25} (查询失败)"
                data_list_message += "\n"
        logger.info(data_list_message)
    
    def show_statistics(self):
        """显示数据统计"""
        data_statistics_message = ""
        data_statistics_message += "\n" + "=" * 60
        data_statistics_message += "数据统计"
        data_statistics_message += "=" * 60
        data_statistics_message += "\n"
        
        try:
            # 新闻统计
            with self.engine.connect() as conn:
                news_count = conn.execute(text("SELECT COUNT(*) FROM daily_news")).scalar_one()
                news_days = conn.execute(text("SELECT COUNT(DISTINCT crawl_date) FROM daily_news")).scalar_one()
                platforms = conn.execute(text("SELECT COUNT(DISTINCT source_platform) FROM daily_news")).scalar_one()
            
            data_statistics_message += "新闻数据:"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 总新闻数: {news_count}"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 覆盖天数: {news_days}"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 新闻平台: {platforms}"
            data_statistics_message += "\n"
            # 话题统计
            with self.engine.connect() as conn:
                topic_count = conn.execute(text("SELECT COUNT(*) FROM daily_topics")).scalar_one()
                topic_days = conn.execute(text("SELECT COUNT(DISTINCT extract_date) FROM daily_topics")).scalar_one()
            
            data_statistics_message += "话题数据:"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 总话题数: {topic_count}"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 提取天数: {topic_days}"
            data_statistics_message += "\n"
            
            # 爬取任务统计
            with self.engine.connect() as conn:
                task_count = conn.execute(text("SELECT COUNT(*) FROM crawling_tasks")).scalar_one()
                task_status = conn.execute(text("SELECT task_status, COUNT(*) FROM crawling_tasks GROUP BY task_status")).all()
            
            data_statistics_message += "爬取任务:"
            data_statistics_message += "\n"
            data_statistics_message += f"  - 总任务数: {task_count}"
            data_statistics_message += "\n"
            for status, count in task_status:
                data_statistics_message += f"  - {status}: {count}"
                data_statistics_message += "\n"
            
            # 爬取内容统计
            data_statistics_message += "平台内容统计:"
            data_statistics_message += "\n"
            platform_tables = {
                'xhs_note': '小红书',
                'douyin_aweme': '抖音',
                'kuaishou_video': '快手',
                'bilibili_video': 'B站',
                'weibo_note': '微博',
                'tieba_note': '贴吧',
                'zhihu_content': '知乎'
            }
            
            for table, platform in platform_tables.items():
                try:
                    with self.engine.connect() as conn:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                    data_statistics_message += f"  - {platform}: {count}"
                    data_statistics_message += "\n"
                except:
                    data_statistics_message += f"  - {platform}: 表不存在"
                    data_statistics_message += "\n"
            logger.info(data_statistics_message)
        except Exception as e:
            data_statistics_message += f"统计查询失败: {e}"
            data_statistics_message += "\n"
            logger.error(data_statistics_message)
    
    def show_recent_data(self, days=7):
        """显示最近几天的数据"""
        data_recent_message = ""
        data_recent_message += "\n" + "=" * 60
        data_recent_message += "最近" + str(days) + "天的数据"
        data_recent_message += "=" * 60
        
        from datetime import date, timedelta
        start_date = date.today() - timedelta(days=days)
        # 最近的新闻
        with self.engine.connect() as conn:
            news_data = conn.execute(
                text(
                    """
                    SELECT crawl_date, COUNT(*) as news_count, COUNT(DISTINCT source_platform) as platforms
                    FROM daily_news 
                    WHERE crawl_date >= :start_date
                    GROUP BY crawl_date 
                    ORDER BY crawl_date DESC
                    """
                ),
                {"start_date": start_date},
            ).all()
        if news_data:
            data_recent_message += "每日新闻统计:"
            data_recent_message += "\n"
            for date, count, platforms in news_data:
                data_recent_message += f"  {date}: {count} 条新闻, {platforms} 个平台"
                data_recent_message += "\n"
        
        # 最近的话题
        with self.engine.connect() as conn:
            topic_data = conn.execute(
                text(
                    """
                    SELECT extract_date, COUNT(*) as topic_count
                    FROM daily_topics 
                    WHERE extract_date >= :start_date
                    GROUP BY extract_date 
                    ORDER BY extract_date DESC
                    """
                ),
                {"start_date": start_date},
            ).all()
        if topic_data:
            data_recent_message += "每日话题统计:"
            data_recent_message += "\n"
            for date, count in topic_data:
                data_recent_message += f"  {date}: {count} 个话题"
                data_recent_message += "\n"
        logger.info(data_recent_message)
    
    def cleanup_old_data(self, days=90, dry_run=True):
        """清理旧数据"""
        cleanup_message = ""
        cleanup_message += "\n" + "=" * 60
        cleanup_message += f"清理{days}天前的数据 ({'预览模式' if dry_run else '执行模式'})"
        cleanup_message += "=" * 60
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 检查要删除的数据
        cleanup_queries = [
            ("daily_news", f"SELECT COUNT(*) FROM daily_news WHERE crawl_date < '{cutoff_date.date()}'"),
            ("daily_topics", f"SELECT COUNT(*) FROM daily_topics WHERE extract_date < '{cutoff_date.date()}'"),
            ("crawling_tasks", f"SELECT COUNT(*) FROM crawling_tasks WHERE scheduled_date < '{cutoff_date.date()}'")
        ]
        
        with self.engine.begin() as conn:
            for table, query in cleanup_queries:
                count = conn.execute(text(query)).scalar_one()
                if count > 0:
                    cleanup_message += f"  {table}: {count} 条记录将被删除"
                    cleanup_message += "\n"
                    if not dry_run:
                        delete_query = query.replace("SELECT COUNT(*)", "DELETE")
                        conn.execute(text(delete_query))
                        cleanup_message += f"    已删除 {count} 条记录"
                        cleanup_message += "\n"
                else:
                    cleanup_message += f"  {table}: 无需清理"
                    cleanup_message += "\n"
        
        if dry_run:
            cleanup_message += "\n这是预览模式，没有实际删除数据。使用 --execute 参数执行实际清理。"
            cleanup_message += "\n"
        logger.info(cleanup_message)

def main():
    parser = argparse.ArgumentParser(description="MindSpider数据库管理工具")
    parser.add_argument("--tables", action="store_true", help="显示所有表")
    parser.add_argument("--stats", action="store_true", help="显示数据统计")
    parser.add_argument("--recent", type=int, default=7, help="显示最近N天的数据 (默认7天)")
    parser.add_argument("--cleanup", type=int, help="清理N天前的数据")
    parser.add_argument("--execute", action="store_true", help="执行实际清理操作")
    
    args = parser.parse_args()
    
    # 如果没有参数，显示所有信息
    if not any([args.tables, args.stats, args.recent != 7, args.cleanup]):
        args.tables = True
        args.stats = True
    
    db_manager = DatabaseManager()
    
    try:
        if args.tables:
            db_manager.show_tables()
        
        if args.stats:
            db_manager.show_statistics()
        
        if args.recent != 7 or not any([args.tables, args.stats, args.cleanup]):
            db_manager.show_recent_data(args.recent)
        
        if args.cleanup:
            db_manager.cleanup_old_data(args.cleanup, dry_run=not args.execute)
    
    finally:
        db_manager.close()

if __name__ == "__main__":
    main()
