#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MindSpider - AI爬虫项目主程序
集成BroadTopicExtraction和DeepSentimentCrawling两个核心模块
"""

import os
import sys
import argparse
import difflib
import re
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
from urllib.parse import quote_plus

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
            if dialect in ("postgresql", "postgres"):
                return f"postgresql+asyncpg://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            # 默认使用 mysql 异步驱动 asyncmy
            return (
                f"mysql+asyncmy://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
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
    
    def check_database_tables(self, log_missing_as_error: bool = True, hint_init: bool = False) -> bool:
        """检查数据库表是否存在"""
        logger.info("检查数据库表...")
        
        def build_async_url() -> str:
            dialect = (settings.DB_DIALECT or "mysql").lower()
            if dialect in ("postgresql", "postgres"):
                return f"postgresql+asyncpg://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            return (
                f"mysql+asyncmy://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
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
                message = f"缺少数据库表: {', '.join(missing_tables)}"
                if log_missing_as_error:
                    logger.error(message)
                else:
                    logger.warning(message)
                if hint_init:
                    logger.info("可运行: python MindSpider/main.py --init-db")
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
    
    def _ensure_database_ready(self) -> bool:
        """确保数据库表已就绪，如不存在则自动初始化"""
        if not self.check_database_connection():
            logger.error("数据库连接失败，无法继续")
            return False
        
        if not self.check_database_tables():
            logger.warning("数据库表不存在，自动初始化中...")
            if not self.initialize_database():
                logger.error("数据库自动初始化失败")
                return False
            logger.info("数据库表自动初始化成功")
        
        return True

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
        
        # 检查并安装MediaCrawler依赖
        mediacrawler_path = self.deep_sentiment_path / "MediaCrawler"
        if not mediacrawler_path.exists():
            logger.error("错误：找不到MediaCrawler目录")
            return False
        
        # 自动安装MediaCrawler的依赖
        self._install_mediacrawler_dependencies()
        
        logger.info("依赖环境检查通过")
        return True
    
    def _install_mediacrawler_dependencies(self) -> bool:
        """自动安装MediaCrawler子模块的依赖"""
        mediacrawler_req = self.deep_sentiment_path / "MediaCrawler" / "requirements.txt"
        
        if not mediacrawler_req.exists():
            logger.warning(f"MediaCrawler requirements.txt 不存在: {mediacrawler_req}")
            return False
        
        # 检查是否已安装过（使用标记文件）
        marker_file = self.deep_sentiment_path / "MediaCrawler" / ".deps_installed"
        req_mtime = mediacrawler_req.stat().st_mtime
        
        if marker_file.exists():
            marker_mtime = marker_file.stat().st_mtime
            if marker_mtime >= req_mtime:
                logger.debug("MediaCrawler依赖已安装，跳过")
                return True
        
        logger.info("正在安装MediaCrawler依赖...")
        install_commands = [
            [sys.executable, "-m", "pip", "install", "-r", str(mediacrawler_req), "-q"],
            ["uv", "pip", "install", "-r", str(mediacrawler_req), "-q"],
        ]
        try:
            for cmd in install_commands:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                if result.returncode == 0:
                    marker_file.touch()
                    logger.info(f"MediaCrawler依赖安装成功 (via {cmd[0]})")
                    return True
                logger.debug(f"{cmd[0]} 安装失败，尝试下一种方式: {result.stderr.strip()}")

            logger.error("MediaCrawler依赖安装失败：所有安装方式均不可用")
            return False

        except subprocess.TimeoutExpired:
            logger.error("MediaCrawler依赖安装超时")
            return False
        except Exception as e:
            logger.exception(f"MediaCrawler依赖安装异常: {e}")
            return False

    def run_broad_topic_extraction(self, extract_date: date = None, keywords_count: int = 100) -> bool:
        """运行BroadTopicExtraction模块"""
        logger.info("运行BroadTopicExtraction模块...")
        
        # 自动检查并初始化数据库表
        if not self._ensure_database_ready():
            return False
        
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

        # 自动检查并初始化数据库表
        if not self._ensure_database_ready():
            return False

        # 自动安装MediaCrawler依赖
        self._install_mediacrawler_dependencies()
        
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
        
        # 自动检查并初始化数据库表（确保独立调用时也能自动初始化）
        if not self._ensure_database_ready():
            return False
        
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
                db_tables_ok = self.check_database_tables(log_missing_as_error=False, hint_init=True)
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

PLATFORM_CHOICES = ['xhs', 'dy', 'ks', 'bili', 'wb', 'tieba', 'zhihu']

PLATFORM_ALIASES = {
    'weibo': 'wb', 'webo': 'wb', '微博': 'wb',
    'douyin': 'dy', '抖音': 'dy',
    'kuaishou': 'ks', '快手': 'ks',
    'bilibili': 'bili', 'b站': 'bili', 'bstation': 'bili',
    'xiaohongshu': 'xhs', '小红书': 'xhs', 'redbook': 'xhs',
    'zhihu': 'zhihu', '知乎': 'zhihu',
    'tieba': 'tieba', '贴吧': 'tieba',
}

class SuggestiveArgumentParser(argparse.ArgumentParser):
    """在参数错误时给出相似候选项提示"""

    def error(self, message: str):
        match = re.search(r"invalid choice: '([^']+)'", message)
        if match:
            bad = match.group(1)
            alias = PLATFORM_ALIASES.get(bad.lower())
            suggestions = difflib.get_close_matches(bad, PLATFORM_CHOICES, n=3, cutoff=0.3)
            if alias:
                print(f"错误: '{bad}' 不是合法的平台代码。您是否想输入 '{alias}'？", file=sys.stderr)
            elif suggestions:
                print(f"错误: '{bad}' 不是合法的平台代码。最接近的选项: {suggestions}", file=sys.stderr)
            else:
                print(f"错误: '{bad}' 不是合法的平台代码。合法平台: {PLATFORM_CHOICES}", file=sys.stderr)
            print(f"完整错误: {message}", file=sys.stderr)
        else:
            print(f"错误: {message}", file=sys.stderr)
        self.print_usage(sys.stderr)
        sys.exit(2)

def main():
    """命令行入口"""
    parser = SuggestiveArgumentParser(description="MindSpider - AI爬虫项目主程序")
    
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
                       choices=PLATFORM_CHOICES,
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
