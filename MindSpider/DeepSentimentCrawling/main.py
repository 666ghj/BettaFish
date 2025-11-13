#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSentimentCrawling模块 - 主工作流程
基于BroadTopicExtraction提取的话题进行全平台关键词爬取
"""

import sys
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from keyword_manager import KeywordManager
from platform_crawler import PlatformCrawler

class DeepSentimentCrawling:
    """深度情感爬取主工作流程"""
    
    def __init__(self):
        """初始化深度情感爬取"""
        self.keyword_manager = KeywordManager()
        self.platform_crawler = PlatformCrawler()
        self.supported_platforms = ['xhs', 'dy', 'ks', 'bili', 'wb', 'tieba', 'zhihu']
    
    def run_daily_crawling(self, target_date: date = None, platforms: List[str] = None, 
                          max_keywords_per_platform: int = 50, 
                          max_notes_per_platform: int = 50,
                          login_type: str = "qrcode",
                          custom_keywords: Optional[List[str]] = None) -> Dict:
        """
        执行每日爬取任务
        
        Args:
            target_date: 目标日期，默认为今天
            platforms: 要爬取的平台列表，默认为所有支持的平台
            max_keywords_per_platform: 每个平台最大关键词数量
            max_notes_per_platform: 每个平台最大爬取内容数量
            login_type: 登录方式
            custom_keywords: 用户自定义关键词列表（可选）
        
        Returns:
            爬取结果统计
        """
        if not target_date:
            target_date = date.today()
        
        if not platforms:
            platforms = self.supported_platforms
        
        print(f"🚀 开始执行 {target_date} 的深度情感爬取任务")
        print(f"目标平台: {platforms}")
        
        # 1. 获取关键词摘要
        summary = self.keyword_manager.get_crawling_summary(target_date)
        print(f"📊 关键词摘要: {summary}")
        
        manual_keywords = self._normalize_keywords(custom_keywords, max_keywords_per_platform)
        if not summary['has_data'] and not manual_keywords:
            print("⚠️ 没有找到话题数据，无法进行爬取（可通过 --keywords 手动指定）")
            return {"success": False, "error": "没有话题数据"}
        elif manual_keywords and not summary['has_data']:
            print("ℹ️ 未找到数据库数据，使用用户指定关键词继续执行")
    
        # 2. 获取关键词（不分配，所有平台使用相同关键词）
        if manual_keywords:
            keywords = manual_keywords
            print(f"\n📝 使用用户提供的关键词: {keywords}")
        else:
            print(f"\n📝 获取关键词...")
            keywords = self.keyword_manager.get_latest_keywords(target_date, max_keywords_per_platform)
            
            if not keywords:
                print("⚠️ 没有找到关键词，无法进行爬取")
                return {"success": False, "error": "没有关键词"}
        
        print(f"   获取到 {len(keywords)} 个关键词")
        print(f"   将在 {len(platforms)} 个平台上爬取每个关键词")
        print(f"   总爬取任务: {len(keywords)} × {len(platforms)} = {len(keywords) * len(platforms)}")
        
        # 3. 执行全平台关键词爬取
        print(f"\n🔄 开始全平台关键词爬取...")
        crawl_results = self.platform_crawler.run_multi_platform_crawl_by_keywords(
            keywords, platforms, login_type, max_notes_per_platform
        )
        
        # 4. 生成最终报告
        final_report = {
            "date": target_date.isoformat(),
            "summary": summary,
            "crawl_results": crawl_results,
            "success": crawl_results["successful_tasks"] > 0
        }
        
        print(f"\n✅ 深度情感爬取任务完成!")
        print(f"   日期: {target_date}")
        print(f"   成功任务: {crawl_results['successful_tasks']}/{crawl_results['total_tasks']}")
        print(f"   总关键词: {crawl_results['total_keywords']} 个")
        print(f"   总平台: {crawl_results['total_platforms']} 个")
        print(f"   总内容: {crawl_results['total_notes']} 条")
        
        return final_report
    
    def run_platform_crawling(self, platform: str, target_date: date = None,
                             max_keywords: int = 50, max_notes: int = 50,
                             login_type: str = "qrcode",
                             custom_keywords: Optional[List[str]] = None) -> Dict:
        """
        执行单个平台的爬取任务
        
        Args:
            platform: 平台名称
            target_date: 目标日期
            max_keywords: 最大关键词数量
            max_notes: 最大爬取内容数量
            login_type: 登录方式
            custom_keywords: 用户自定义关键词列表（可选）
        
        Returns:
            爬取结果
        """
        if platform not in self.supported_platforms:
            raise ValueError(f"不支持的平台: {platform}")
        
        if not target_date:
            target_date = date.today()
        
        print(f"🎯 开始执行 {platform} 平台的爬取任务 ({target_date})")
        
        # 获取关键词
        manual_keywords = self._normalize_keywords(custom_keywords, max_keywords)
        if manual_keywords:
            keywords = manual_keywords
            print(f"\n📝 使用用户提供的关键词: {keywords}")
        else:
            keywords = self.keyword_manager.get_keywords_for_platform(
                platform, target_date, max_keywords
            )
        
            if not keywords:
                print(f"⚠️ 没有找到 {platform} 平台的关键词")
                return {"success": False, "error": "没有关键词"}
        
        print(f"📝 准备爬取 {len(keywords)} 个关键词")
        
        # 执行爬取
        result = self.platform_crawler.run_crawler(
            platform, keywords, login_type, max_notes
        )
        
        return result

    def _normalize_keywords(self, keywords: Optional[List[str]], limit: Optional[int]) -> List[str]:
        """清洗并限制关键词列表"""
        if not keywords:
            return []
        
        cleaned: List[str] = []
        seen = set()
        for keyword in keywords:
            if keyword is None:
                continue
            normalized = keyword.strip()
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
            if limit and len(cleaned) >= limit:
                break
        return cleaned
    
    def list_available_topics(self, days: int = 7):
        """列出最近可用的话题"""
        print(f"📋 最近 {days} 天的话题数据:")
        
        recent_topics = self.keyword_manager.db_manager.get_recent_topics(days)
        
        if not recent_topics:
            print("   暂无话题数据")
            return
        
        for topic in recent_topics:
            extract_date = topic['extract_date']
            keywords_count = len(topic.get('keywords', []))
            summary_preview = topic.get('summary', '')[:100] + "..." if len(topic.get('summary', '')) > 100 else topic.get('summary', '')
            
            print(f"   📅 {extract_date}: {keywords_count} 个关键词")
            print(f"      摘要: {summary_preview}")
            print()
    
    def show_platform_guide(self):
        """显示平台使用指南"""
        print("🔧 平台爬取指南:")
        print()
        
        platform_info = {
            'xhs': '小红书 - 美妆、生活、时尚内容为主',
            'dy': '抖音 - 短视频、娱乐、生活内容',
            'ks': '快手 - 生活、娱乐、农村题材内容',
            'bili': 'B站 - 科技、学习、游戏、动漫内容',
            'wb': '微博 - 热点新闻、明星、社会话题',
            'tieba': '百度贴吧 - 兴趣讨论、游戏、学习',
            'zhihu': '知乎 - 知识问答、深度讨论'
        }
        
        for platform, desc in platform_info.items():
            print(f"   {platform}: {desc}")
        
        print()
        print("💡 使用建议:")
        print("   1. 首次使用需要扫码登录各平台")
        print("   2. 建议先测试单个平台，确认登录正常")
        print("   3. 爬取数量不宜过大，避免被限制")
        print("   4. 可以使用 --test 模式进行小规模测试")
    
    def close(self):
        """关闭资源"""
        if self.keyword_manager:
            self.keyword_manager.close()

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="DeepSentimentCrawling - 基于话题的深度情感爬取")
    
    # 基本参数
    parser.add_argument("--date", type=str, help="目标日期 (YYYY-MM-DD)，默认为今天")
    parser.add_argument("--platform", type=str, choices=['xhs', 'dy', 'ks', 'bili', 'wb', 'tieba', 'zhihu'], 
                       help="指定单个平台进行爬取")
    parser.add_argument("--platforms", type=str, nargs='+', 
                       choices=['xhs', 'dy', 'ks', 'bili', 'wb', 'tieba', 'zhihu'],
                       help="指定多个平台进行爬取")
    parser.add_argument("--keywords", nargs="+", help="手动指定关键词（空格分隔）")
    parser.add_argument("--keywords-file", type=str, help="从文本文件读取关键词（每行一个）")
    
    # 爬取参数
    parser.add_argument("--max-keywords", type=int, default=50, 
                       help="每个平台最大关键词数量 (默认: 50)")
    parser.add_argument("--max-notes", type=int, default=50,
                       help="每个平台最大爬取内容数量 (默认: 50)")
    parser.add_argument("--login-type", type=str, choices=['qrcode', 'phone', 'cookie'], 
                       default='qrcode', help="登录方式 (默认: qrcode)")
    
    # 功能参数
    parser.add_argument("--list-topics", action="store_true", help="列出最近的话题数据")
    parser.add_argument("--days", type=int, default=7, help="查看最近几天的话题 (默认: 7)")
    parser.add_argument("--guide", action="store_true", help="显示平台使用指南")
    parser.add_argument("--test", action="store_true", help="测试模式 (少量数据)")
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("❌ 日期格式错误，请使用 YYYY-MM-DD 格式")
            return
    
    # 加载用户自定义关键词
    custom_keywords: Optional[List[str]] = None
    user_keywords: List[str] = []
    if args.keywords:
        user_keywords.extend(args.keywords)
    if args.keywords_file:
        keywords_file = Path(args.keywords_file)
        if not keywords_file.exists():
            print(f"❌ 无法找到关键词文件: {keywords_file}")
            return
        file_keywords = [line.strip() for line in keywords_file.read_text(encoding="utf-8").splitlines()]
        user_keywords.extend([kw for kw in file_keywords if kw])
    if user_keywords:
        filtered_keywords = [kw.strip() for kw in user_keywords if kw.strip()]
        if filtered_keywords:
            custom_keywords = filtered_keywords
            print(f"📝 将使用用户提供的关键词，共 {len(custom_keywords)} 个")
    
    # 创建爬取实例
    crawler = DeepSentimentCrawling()
    
    try:
        # 显示指南
        if args.guide:
            crawler.show_platform_guide()
            return
        
        # 列出话题
        if args.list_topics:
            crawler.list_available_topics(args.days)
            return
        
        # 测试模式调整参数
        if args.test:
            args.max_keywords = min(args.max_keywords, 10)
            args.max_notes = min(args.max_notes, 10)
            print("测试模式：限制关键词和内容数量")
        
        # 单平台爬取
        if args.platform:
            result = crawler.run_platform_crawling(
                args.platform, target_date, args.max_keywords, 
                args.max_notes, args.login_type, custom_keywords
            )
            
            if result['success']:
                print(f"\n{args.platform} 爬取成功！")
            else:
                print(f"\n{args.platform} 爬取失败: {result.get('error', '未知错误')}")
            
            return
        
        # 多平台爬取
        platforms = args.platforms if args.platforms else None
        result = crawler.run_daily_crawling(
            target_date, platforms, args.max_keywords, 
            args.max_notes, args.login_type, custom_keywords
        )
        
        if result['success']:
            print(f"\n多平台爬取任务完成！")
        else:
            print(f"\n多平台爬取失败: {result.get('error', '未知错误')}")
    
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"\n执行出错: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()
