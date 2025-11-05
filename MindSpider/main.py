#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MindSpider - AI爬虫项目主程序
集成BroadTopicExtraction和DeepSentimentCrawling两个核心模块
"""

import os
import sys
import argparse
from datetime import date, datetime
from pathlib import Path
import subprocess
import asyncio
import pymysql
from pymysql.cursors import DictCursor
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import inspect, text
from config import settings
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

try:
    import config
except ImportError:
    logger.error("错误：无法导入config.py配置文件")
    logger.error("请确保项目根目录下存在config.py文件，并包含数据库和API配置信息")
    sys.exit(1)

class MindSpider:
    """MindSpider主程序"""
    
    def __init__(self):
        """初始化MindSpider"""
        self.project_root = project_root
        self.broad_topic_path = self.project_root / "BroadTopicExtraction"
        self.deep_sentiment_path = self.project_root / "DeepSentimentCrawling"
        self.schema_path = self.project_root / "schema"
        
        logger.info("MindSpider AI爬虫项目")
        logger.info(f"项目路径: {self.project_root}")
    
    def check_config(self) -> bool:
        """检查基础配置"""
        logger.info("检查基础配置...")
        
        # 检查settings配置项
        required_configs = [
            'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME', 'DB_CHARSET',
            'MINDSPIDER_API_KEY', 'MINDSPIDER_BASE_URL', 'MINDSPIDER_MODEL_NAME'
        ]
        
        missing_configs = []
        for config_name in required_configs:
            if not hasattr(settings, config_name) or not getattr(settings, config_name):
                missing_configs.append(config_name)
        
        if missing_configs:
            logger.error(f"配置缺失: {', '.join(missing_configs)}")
            logger.error("请检查.env文件中的环境变量配置信息")
            return False
        
        logger.info("基础配置检查通过")
        return True
    
    def check_database_connection(self) -> bool:
        """检查数据库连接"""
        logger.info("检查数据库连接...")
        
        def build_async_url() -> str:
            dialect = (settings.DB_DIALECT or "mysql").lower()
            if dialect == "postgresql":
                return f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            # 默认使用 mysql 异步驱动 asyncmy
            return (
                f"mysql+asyncmy://{settings.DB_USER}:{settings.DB_PASSWORD}"
                f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset={settings.DB_CHARSET}"
            )

        async def _test_connection(db_url: str) -> None:
            engine: AsyncEngine = create_async_engine(db_url, pool_pre_ping=True)
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            finally:
                await engine.dispose()

        try:
            db_url: str = build_async_url()
            asyncio.run(_test_connection(db_url))
            logger.info("数据库连接正常")
            return True
        except Exception as e:
            logger.exception(f"数据库连接失败: {e}")
            return False
    
    def check_database_tables(self) -> bool:
        """检查数据库表是否存在"""
        logger.info("检查数据库表...")
        
        def build_async_url() -> str:
            dialect = (settings.DB_DIALECT or "mysql").lower()
            if dialect == "postgresql":
                return f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            return (
                f"mysql+asyncmy://{settings.DB_USER}:{settings.DB_PASSWORD}"
                f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset={settings.DB_CHARSET}"
            )

        async def _check_tables(db_url: str) -> list[str]:
            engine: AsyncEngine = create_async_engine(db_url, pool_pre_ping=True)
            try:
                async with engine.connect() as conn:
                    def _get_tables(sync_conn):
                        return inspect(sync_conn).get_table_names()
                    tables = await conn.run_sync(_get_tables)
                    return tables
            finally:
                await engine.dispose()

        try:
            db_url: str = build_async_url()
            existing_tables = asyncio.run(_check_tables(db_url))
            required_tables = ['daily_news', 'daily_topics']
            missing_tables = [t for t in required_tables if t not in existing_tables]
            if missing_tables:
                logger.error(f"缺少数据库表: {', '.join(missing_tables)}")
                return False
            logger.info("数据库表检查通过")
            return True
        except Exception as e:
            logger.exception(f"检查数据库表失败: {e}")
            return False
    
    def initialize_database(self) -> bool:
        """初始化数据库"""
        logger.info("初始化数据库...")
        
        try:
            # 运行数据库初始化脚本
            init_script = self.schema_path / "init_database.py"
            if not init_script.exists():
                logger.error("错误：找不到数据库初始化脚本")
                return False
            
            result = subprocess.run(
                [sys.executable, str(init_script)],
                cwd=self.schema_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("数据库初始化成功")
                return True
            else:
                logger.error(f"数据库初始化失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.exception(f"数据库初始化异常: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """检查依赖环境"""
        logger.info("检查依赖环境...")
        
        # 检查Python包
        required_packages = ['pymysql', 'requests', 'playwright']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"缺少Python包: {', '.join(missing_packages)}")
            logger.info("请运行: pip install -r requirements.txt")
            return False
        
        # 检查MediaCrawler依赖
        mediacrawler_path = self.deep_sentiment_path / "MediaCrawler"
        if not mediacrawler_path.exists():
            logger.error("错误：找不到MediaCrawler目录")
            return False
        
        logger.info("依赖环境检查通过")
        return True
    
    def run_broad_topic_extraction(self, extract_date: date = None, keywords_count: int = 100) -> bool:
        """运行BroadTopicExtraction模块"""
        logger.info("运行BroadTopicExtraction模块...")
        
        if not extract_date:
            extract_date = date.today()
        
        try:
            cmd = [
                sys.executable, "main.py",
                "--keywords", str(keywords_count)
            ]
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=self.broad_topic_path,
                timeout=1800  # 30分钟超时
            )
            
            if result.returncode == 0:
                logger.info("BroadTopicExtraction模块执行成功")
                return True
            else:
                logger.error(f"BroadTopicExtraction模块执行失败，返回码: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("BroadTopicExtraction模块执行超时")
            return False
        except Exception as e:
            logger.exception(f"BroadTopicExtraction模块执行异常: {e}")
            return False
    
    def run_deep_sentiment_crawling(self, target_date: date = None, platforms: list = None,
                                   max_keywords: int = 50, max_notes: int = 50,
                                   test_mode: bool = False) -> bool:
        """运行DeepSentimentCrawling模块"""
        logger.info("运行DeepSentimentCrawling模块...")
        
        if not target_date:
            target_date = date.today()
        
        try:
            cmd = [sys.executable, "main.py"]
            
            if target_date:
                cmd.extend(["--date", target_date.strftime("%Y-%m-%d")])
            
            if platforms:
                cmd.extend(["--platforms"] + platforms)
            
            cmd.extend([
                "--max-keywords", str(max_keywords),
                "--max-notes", str(max_notes)
            ])
            
            if test_mode:
                cmd.append("--test")
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=self.deep_sentiment_path,
                timeout=3600  # 60分钟超时
            )
            
            if result.returncode == 0:
                logger.info("DeepSentimentCrawling模块执行成功")
                return True
            else:
                logger.error(f"DeepSentimentCrawling模块执行失败，返回码: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("DeepSentimentCrawling模块执行超时")
            return False
        except Exception as e:
            logger.exception(f"DeepSentimentCrawling模块执行异常: {e}")
            return False
    
    def run_complete_workflow(self, target_date: date = None, platforms: list = None,
                             keywords_count: int = 100, max_keywords: int = 50,
                             max_notes: int = 50, test_mode: bool = False) -> bool:
        """运行完整工作流程"""
        logger.info("开始完整的MindSpider工作流程")
        
        if not target_date:
            target_date = date.today()
        
        logger.info(f"目标日期: {target_date}")
        logger.info(f"平台列表: {platforms if platforms else '所有支持的平台'}")
        logger.info(f"测试模式: {'是' if test_mode else '否'}")
        
        # 第一步：运行话题提取
        logger.info("=== 第一步：话题提取 ===")
        if not self.run_broad_topic_extraction(target_date, keywords_count):
            logger.error("话题提取失败，终止流程")
            return False
        
        # 第二步：运行情感爬取
        logger.info("=== 第二步：情感爬取 ===")
        if not self.run_deep_sentiment_crawling(target_date, platforms, max_keywords, max_notes, test_mode):
            logger.error("情感爬取失败，但话题提取已完成")
            return False
        
        logger.info("完整工作流程执行成功！")
        return True
    
    def show_status(self):
        """显示项目状态"""
        logger.info("MindSpider项目状态:")
        logger.info(f"项目路径: {self.project_root}")
        
        # 配置状态
        config_ok = self.check_config()
        logger.info(f"配置状态: {'正常' if config_ok else '异常'}")
        
        # 数据库状态
        if config_ok:
            db_conn_ok = self.check_database_connection()
            logger.info(f"数据库连接: {'正常' if db_conn_ok else '异常'}")
            
            if db_conn_ok:
                db_tables_ok = self.check_database_tables()
                logger.info(f"数据库表: {'正常' if db_tables_ok else '需要初始化'}")
        
        # 依赖状态
        deps_ok = self.check_dependencies()
        logger.info(f"依赖环境: {'正常' if deps_ok else '异常'}")
        
        # 模块状态
        broad_topic_exists = self.broad_topic_path.exists()
        deep_sentiment_exists = self.deep_sentiment_path.exists()
        logger.info(f"BroadTopicExtraction模块: {'存在' if broad_topic_exists else '缺失'}")
        logger.info(f"DeepSentimentCrawling模块: {'存在' if deep_sentiment_exists else '缺失'}")
    
    def setup_project(self) -> bool:
        """项目初始化设置"""
        logger.info("开始MindSpider项目初始化...")
        
        # 1. 检查配置
        if not self.check_config():
            return False
        
        # 2. 检查依赖
        if not self.check_dependencies():
            return False
        
        # 3. 检查数据库连接
        if not self.check_database_connection():
            return False
        
        # 4. 检查并初始化数据库表
        if not self.check_database_tables():
            logger.info("需要初始化数据库表...")
            if not self.initialize_database():
                return False
        
        logger.info("MindSpider项目初始化完成！")
        return True

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="MindSpider - AI爬虫项目主程序")
    
    # 基本操作
    parser.add_argument("--setup", action="store_true", help="初始化项目设置")
    parser.add_argument("--status", action="store_true", help="显示项目状态")
    parser.add_argument("--init-db", action="store_true", help="初始化数据库")
    
    # 模块运行
    parser.add_argument("--broad-topic", action="store_true", help="只运行话题提取模块")
    parser.add_argument("--deep-sentiment", action="store_true", help="只运行情感爬取模块")
    parser.add_argument("--complete", action="store_true", help="运行完整工作流程")
    
    # 参数配置
    parser.add_argument("--date", type=str, help="目标日期 (YYYY-MM-DD)，默认为今天")
    parser.add_argument("--platforms", type=str, nargs='+', 
                       choices=['xhs', 'dy', 'ks', 'bili', 'wb', 'tieba', 'zhihu'],
                       help="指定爬取平台")
    parser.add_argument("--keywords-count", type=int, default=100, help="话题提取的关键词数量")
    parser.add_argument("--max-keywords", type=int, default=50, help="每个平台最大关键词数量")
    parser.add_argument("--max-notes", type=int, default=50, help="每个关键词最大爬取内容数量")
    parser.add_argument("--test", action="store_true", help="测试模式（少量数据）")
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("错误：日期格式不正确，请使用 YYYY-MM-DD 格式")
            return
    
    # 创建MindSpider实例
    spider = MindSpider()
    
    try:
        # 显示状态
        if args.status:
            spider.show_status()
            return
        
        # 项目设置
        if args.setup:
            if spider.setup_project():
                logger.info("项目设置完成，可以开始使用MindSpider！")
            else:
                logger.error("项目设置失败，请检查配置和环境")
            return
        
        # 初始化数据库
        if args.init_db:
            if spider.initialize_database():
                logger.info("数据库初始化成功")
            else:
                logger.error("数据库初始化失败")
            return
        
        # 运行模块
        if args.broad_topic:
            spider.run_broad_topic_extraction(target_date, args.keywords_count)
        elif args.deep_sentiment:
            spider.run_deep_sentiment_crawling(
                target_date, args.platforms, args.max_keywords, args.max_notes, args.test
            )
        elif args.complete:
            spider.run_complete_workflow(
                target_date, args.platforms, args.keywords_count, 
                args.max_keywords, args.max_notes, args.test
            )
        else:
            # 默认运行完整工作流程
            logger.info("运行完整MindSpider工作流程...")
            spider.run_complete_workflow(
                target_date, args.platforms, args.keywords_count,
                args.max_keywords, args.max_notes, args.test
            )
    
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.exception(f"执行出错: {e}")

if __name__ == "__main__":
    main()
