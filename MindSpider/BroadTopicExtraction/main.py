#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BroadTopicExtraction模块 - 主程序
整合话题提取的完整工作流程和命令行工具
"""

import sys
import asyncio
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    from BroadTopicExtraction.get_today_news import NewsCollector, SOURCE_NAMES
    from BroadTopicExtraction.topic_extractor import TopicExtractor
    from BroadTopicExtraction.database_manager import DatabaseManager
except ImportError as e:
    logger.exception(f"导入模块失败: {e}")
    logger.error("请确保在项目根目录运行，并且已安装所有依赖")
    sys.exit(1)

class BroadTopicExtraction:
    """BroadTopicExtraction主要工作流程"""
    
    def __init__(self):
        """初始化"""
        self.news_collector = NewsCollector()
        self.topic_extractor = TopicExtractor()
        self.db_manager = DatabaseManager()
        
        logger.info("BroadTopicExtraction 初始化完成")
    
    def close(self):
        """关闭资源"""
        if self.news_collector:
            self.news_collector.close()
        if self.db_manager:
            self.db_manager.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    async def run_daily_extraction(self, 
                                  news_sources: Optional[List[str]] = None,
                                  max_keywords: int = 100) -> Dict:
        """
        运行每日话题提取流程
        
        Args:
            news_sources: 新闻源列表，None表示使用所有支持的源
            max_keywords: 最大关键词数量
            
        Returns:
            包含完整提取结果的字典
        """
        extraction_result_message = ""
        extraction_result_message += "\nMindSpider AI爬虫 - 每日话题提取\n"
        extraction_result_message += f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        extraction_result_message += f"目标日期: {date.today()}\n"
        
        if news_sources:
            extraction_result_message += f"指定平台: {len(news_sources)} 个\n"
            for source in news_sources:
                source_name = SOURCE_NAMES.get(source, source)
                extraction_result_message += f"  - {source_name}\n"
        else:
            extraction_result_message += f"爬取平台: 全部 {len(SOURCE_NAMES)} 个平台\n"
        
        extraction_result_message += f"关键词数: 最多 {max_keywords} 个\n"
        
        logger.info(extraction_result_message)
        
        extraction_result = {
            'success': False,
            'extraction_date': date.today().isoformat(),
            'start_time': datetime.now().isoformat(),
            'news_collection': {},
            'topic_extraction': {},
            'database_save': {},
            'error': None
        }
        
        try:
            # 步骤1: 收集新闻
            logger.info("【步骤1】收集热点新闻...")
            news_result = await self.news_collector.collect_and_save_news(
                sources=news_sources
            )
            
            extraction_result['news_collection'] = {
                'success': news_result['success'],
                'total_news': news_result.get('total_news', 0),
                'successful_sources': news_result.get('successful_sources', 0),
                'total_sources': news_result.get('total_sources', 0)
            }
            
            if not news_result['success'] or not news_result['news_list']:
                raise Exception("新闻收集失败或没有获取到新闻")
            
            # 步骤2: 提取关键词和生成总结
            logger.info("【步骤2】提取关键词和生成总结...")
            keywords, summary = self.topic_extractor.extract_keywords_and_summary(
                news_result['news_list'], 
                max_keywords=max_keywords
            )
            
            extraction_result['topic_extraction'] = {
                'success': len(keywords) > 0,
                'keywords_count': len(keywords),
                'keywords': keywords,
                'summary': summary
            }
            
            if not keywords:
                logger.warning("警告: 没有提取到有效关键词")
            
            # 步骤3: 保存到数据库
            logger.info("【步骤3】保存分析结果到数据库...")
            save_success = self.db_manager.save_daily_topics(
                keywords, summary, date.today()
            )
            
            extraction_result['database_save'] = {
                'success': save_success
            }
            
            extraction_result['success'] = True
            extraction_result['end_time'] = datetime.now().isoformat()
            
            logger.info("每日话题提取流程完成!")
            
            return extraction_result
            
        except Exception as e:
            logger.exception(f"话题提取流程失败: {e}")
            extraction_result['error'] = str(e)
            extraction_result['end_time'] = datetime.now().isoformat()
            return extraction_result
    
    def print_extraction_results(self, extraction_result: Dict):
        """打印提取结果"""
        extraction_result_message = ""
        
        # 新闻收集结果
        news_data = extraction_result.get('news_collection', {})
        extraction_result_message += f"\n📰 新闻收集: {news_data.get('total_news', 0)} 条新闻\n"
        extraction_result_message += f"   成功源数: {news_data.get('successful_sources', 0)}/{news_data.get('total_sources', 0)}\n"
        
        # 话题提取结果
        topic_data = extraction_result.get('topic_extraction', {})
        keywords = topic_data.get('keywords', [])
        summary = topic_data.get('summary', '')
        
        extraction_result_message += f"\n🔑 提取关键词: {len(keywords)} 个\n"
        if keywords:
            # 每行显示5个关键词
            for i in range(0, len(keywords), 5):
                keyword_group = keywords[i:i+5]
                extraction_result_message += f"   {', '.join(keyword_group)}\n"
        
        extraction_result_message += f"\n📝 新闻总结:\n   {summary}\n"
        
        # 数据库保存结果
        db_data = extraction_result.get('database_save', {})
        if db_data.get('success'):
            extraction_result_message += f"\n💾 数据库保存: 成功\n"
        else:
            extraction_result_message += f"\n💾 数据库保存: 失败\n"
        
        logger.info(extraction_result_message)
    
    def get_keywords_for_crawling(self, extract_date: date = None) -> List[str]:
        """
        获取用于爬取的关键词列表
        
        Args:
            extract_date: 提取日期，默认为今天
            
        Returns:
            关键词列表
        """
        try:
            # 从数据库获取话题分析
            topics_data = self.db_manager.get_daily_topics(extract_date)
            
            if not topics_data:
                logger.info(f"没有找到 {extract_date or date.today()} 的话题数据")
                return []
            
            keywords = topics_data['keywords']
            
            # 生成搜索关键词
            search_keywords = self.topic_extractor.get_search_keywords(keywords)
            
            logger.info(f"准备了 {len(search_keywords)} 个关键词用于爬取")
            return search_keywords
            
        except Exception as e:
            logger.error(f"获取爬取关键词失败: {e}")
            return []
    
    def get_daily_analysis(self, target_date: date = None) -> Optional[Dict]:
        """获取指定日期的分析结果"""
        try:
            return self.db_manager.get_daily_topics(target_date)
        except Exception as e:
            logger.error(f"获取每日分析失败: {e}")
            return None
    
    def get_recent_analysis(self, days: int = 7) -> List[Dict]:
        """获取最近几天的分析结果"""
        try:
            return self.db_manager.get_recent_topics(days)
        except Exception as e:
            logger.error(f"获取最近分析失败: {e}")
            return []

# ==================== 命令行工具 ====================

async def run_extraction_command(sources=None, keywords_count=100, show_details=True, source_mode=None, provider=None, queries=None, rss_feeds=None):
    """运行话题提取命令"""
    
    try:
        async with BroadTopicExtraction() as extractor:
            if any(value is not None for value in (source_mode, provider, queries, rss_feeds)):
                extractor.news_collector.close()
                extractor.news_collector = NewsCollector(
                    source_mode=source_mode,
                    provider=provider,
                    queries=queries,
                    rss_feeds=rss_feeds,
                )
            # 运行话题提取
            result = await extractor.run_daily_extraction(
                news_sources=sources,
                max_keywords=keywords_count
            )
            
            if result['success']:
                if show_details:
                    # 显示详细结果
                    extractor.print_extraction_results(result)
                else:
                    # 只显示简要结果
                    news_data = result.get('news_collection', {})
                    topic_data = result.get('topic_extraction', {})
                    
                    logger.info(f"✅ 话题提取成功完成!")
                    logger.info(f"   收集新闻: {news_data.get('total_news', 0)} 条")
                    logger.info(f"   提取关键词: {len(topic_data.get('keywords', []))} 个")
                    logger.info(f"   生成总结: {len(topic_data.get('summary', ''))} 字符")
                
                # 获取爬取关键词
                crawling_keywords = extractor.get_keywords_for_crawling()
                
                if crawling_keywords:
                    logger.info(f"\n🔑 为DeepSentimentCrawling准备的搜索关键词:")
                    logger.info(f"   {', '.join(crawling_keywords)}")
                    
                    # 保存关键词到文件
                    keywords_file = project_root / "data" / "daily_keywords.txt"
                    keywords_file.parent.mkdir(exist_ok=True)
                    
                    with open(keywords_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(crawling_keywords))
                    
                    logger.info(f"   关键词已保存到: {keywords_file}")
                
                return True
                
            else:
                logger.error(f"❌ 话题提取失败: {result.get('error', '未知错误')}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 执行过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MindSpider每日话题提取工具")
    parser.add_argument("--sources", nargs="+", help="指定 source/provider。默认 localized provider；legacy China source requires --source-mode legacy_china.", 
                       choices=list(SOURCE_NAMES.keys()))
    parser.add_argument("--source-mode", choices=["localized", "legacy_china"], default=None, help="source collection mode")
    parser.add_argument("--provider", choices=["searxng", "naver", "brave", "tavily", "serper", "jina"], default=None, help="localized source provider")
    parser.add_argument("--queries", nargs="+", default=None, help="localized provider search queries")
    parser.add_argument("--rss-feeds", nargs="+", default=None, help="RSS feed URLs for localized collection")
    parser.add_argument("--keywords", type=int, default=100, help="最大关键词数量 (默认100)")
    parser.add_argument("--quiet", action="store_true", help="简化输出模式")
    parser.add_argument("--list-sources", action="store_true", help="显示支持的新闻源")
    
    args = parser.parse_args()
    
    # 显示支持的新闻源
    if args.list_sources:
        logger.info("支持的新闻源平台:")
        for source, name in SOURCE_NAMES.items():
            logger.info(f"  {source:<25} {name}")
        return
    
    # 验证参数
    if args.keywords < 1 or args.keywords > 200:
        logger.error("关键词数量应在1-200之间")
        sys.exit(1)
    
    # 运行提取
    try:
        success = asyncio.run(run_extraction_command(
            sources=args.sources,
            keywords_count=args.keywords,
            show_details=not args.quiet,
            source_mode=args.source_mode,
            provider=args.provider,
            queries=args.queries,
            rss_feeds=args.rss_feeds,
        ))
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)

if __name__ == "__main__":
    main()
