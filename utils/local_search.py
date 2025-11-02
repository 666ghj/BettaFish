"""
本地搜索引擎服务
使用DuckDuckGo和网页爬取实现完全独立的搜索功能
替换Tavily和Bocha API

版本: 1.0
"""

import os
import sys
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin, urlparse
import json

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# 添加utils目录到路径以导入重试助手
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG

# ===== 数据结构定义 =====

@dataclass
class SearchResult:
    """网页搜索结果"""
    title: str
    url: str
    content: str
    score: Optional[float] = None
    raw_content: Optional[str] = None
    published_date: Optional[str] = None

@dataclass
class ImageResult:
    """图片搜索结果"""
    url: str
    description: Optional[str] = None

@dataclass
class LocalSearchResponse:
    """本地搜索结果响应"""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    answer: Optional[str] = None
    response_time: Optional[float] = None


# ===== 核心搜索引擎类 =====

class LocalSearchEngine:
    """
    本地搜索引擎
    使用DuckDuckGo和直接网页爬取实现搜索功能
    """
    
    def __init__(self, user_agent: Optional[str] = None):
        """
        初始化本地搜索引擎
        
        Args:
            user_agent: 自定义User-Agent，默认使用常见浏览器UA
        """
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def _fetch_url(self, url: str, timeout: int = 10) -> Optional[str]:
        """获取URL内容"""
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except Exception as e:
            print(f"获取URL失败 {url}: {str(e)}")
            return None
    
    def _extract_text_from_html(self, html: str, max_length: int = 1000) -> str:
        """从HTML中提取文本内容"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            # 移除script和style标签
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            # 尝试提取主要内容
            # 优先查找article, main, content等标签
            main_content = (
                soup.find('article') or 
                soup.find('main') or 
                soup.find('div', class_=re.compile(r'content|article|post', re.I)) or
                soup.find('body') or
                soup
            )
            
            text = main_content.get_text(separator=' ', strip=True)
            # 清理多余空白
            text = re.sub(r'\s+', ' ', text)
            # 截断到指定长度
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text.strip()
        except Exception as e:
            print(f"HTML解析失败: {str(e)}")
            return ""
    
    def _parse_date_from_text(self, text: str) -> Optional[str]:
        """从文本中尝试解析日期"""
        # 常见日期模式
        date_patterns = [
            r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
            r'(\d{4}/\d{1,2}/\d{1,2})',
            r'(\d{1,2}[-月]\d{1,2}[日]?[-年]?\d{4})',
            r'发布于[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2})',
            r'发布时间[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(1)
                    # 尝试解析日期
                    date_obj = date_parser.parse(date_str, fuzzy=True)
                    return date_obj.strftime('%Y-%m-%d')
                except:
                    continue
        
        return None
    
    def _parse_date_from_html(self, html: str) -> Optional[str]:
        """从HTML的meta标签中提取发布日期"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 查找常见的日期meta标签
            date_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publishdate"]',
                'meta[name="pubdate"]',
                'meta[name="date"]',
                'time[datetime]',
                'time[pubdate]',
            ]
            
            for selector in date_selectors:
                element = soup.select_one(selector)
                if element:
                    date_str = element.get('content') or element.get('datetime')
                    if date_str:
                        try:
                            date_obj = date_parser.parse(date_str)
                            return date_obj.strftime('%Y-%m-%d')
                        except:
                            continue
            
            return None
        except:
            return None
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=None)
    def search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        使用DuckDuckGo搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            
        Returns:
            搜索结果列表
        """
        try:
            # DuckDuckGo HTML搜索接口
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            html = self._fetch_url(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'lxml')
            results = []
            
            # DuckDuckGo的搜索结果在result类中
            result_elements = soup.find_all('div', class_='result')[:max_results]
            
            for element in result_elements:
                try:
                    # 提取标题和链接
                    title_elem = element.find('a', class_='result__a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    
                    # 修复相对URL
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/l/?kh='):
                        # DuckDuckGo的跳转链接，提取真实URL
                        match = re.search(r'uddg=([^&]+)', url)
                        if match:
                            url = match.group(1)
                    
                    # 提取摘要
                    snippet_elem = element.find('a', class_='result__snippet')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet,
                        })
                except Exception as e:
                    print(f"解析搜索结果项失败: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"DuckDuckGo搜索失败: {str(e)}")
            return []
    
    def enrich_result_content(self, result: Dict[str, Any], max_content_length: int = 500) -> Dict[str, Any]:
        """
        丰富搜索结果的内容，通过爬取目标网页
        
        Args:
            result: 基础搜索结果
            max_content_length: 最大内容长度
            
        Returns:
            丰富后的结果
        """
        url = result.get('url')
        if not url:
            return result
        
        # 爬取网页内容
        html = self._fetch_url(url, timeout=8)
        if html:
            # 提取文本内容
            content = self._extract_text_from_html(html, max_length=max_content_length)
            if content:
                result['content'] = content
                result['raw_content'] = content
            
            # 尝试提取发布日期
            date = self._parse_date_from_html(html)
            if not date:
                date = self._parse_date_from_text(content)
            if date:
                result['published_date'] = date
        
        # 如果没有提取到内容，使用snippet
        if 'content' not in result or not result['content']:
            result['content'] = result.get('snippet', '')
            result['raw_content'] = result.get('snippet', '')
        
        return result
    
    def search(
        self, 
        query: str, 
        max_results: int = 10,
        enrich_content: bool = True,
        date_filter: Optional[Dict[str, str]] = None
    ) -> LocalSearchResponse:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            enrich_content: 是否爬取目标网页丰富内容
            date_filter: 日期过滤器 {'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD'}
            
        Returns:
            LocalSearchResponse对象
        """
        start_time = time.time()
        
        # 执行搜索
        raw_results = self.search_duckduckgo(query, max_results=max_results * 2)  # 多搜一些，以便过滤
        
        # 丰富内容
        enriched_results = []
        for result in raw_results[:max_results * 2]:  # 限制并发请求
            if enrich_content:
                result = self.enrich_result_content(result, max_content_length=500)
            else:
                result['content'] = result.get('snippet', '')
                result['raw_content'] = result.get('snippet', '')
            
            # 日期过滤
            if date_filter:
                pub_date = result.get('published_date')
                if pub_date:
                    try:
                        date_obj = date_parser.parse(pub_date).date()
                        start = date_parser.parse(date_filter['start_date']).date()
                        end = date_parser.parse(date_filter['end_date']).date()
                        if not (start <= date_obj <= end):
                            continue
                    except:
                        pass  # 日期解析失败，保留结果
            
            enriched_results.append(SearchResult(
                title=result['title'],
                url=result['url'],
                content=result.get('content', result.get('snippet', '')),
                score=None,  # 本地搜索不提供相关性分数
                raw_content=result.get('raw_content', result.get('content', '')),
                published_date=result.get('published_date')
            ))
            
            # 限制结果数量
            if len(enriched_results) >= max_results:
                break
            
            # 添加小延迟避免请求过快
            time.sleep(0.3)
        
        response_time = time.time() - start_time
        
        return LocalSearchResponse(
            query=query,
            results=enriched_results[:max_results],
            images=[],
            answer=None,
            response_time=response_time
        )
    
    def search_by_time_range(
        self, 
        query: str, 
        time_range: str = '24h',
        max_results: int = 10
    ) -> LocalSearchResponse:
        """
        按时间范围搜索
        
        Args:
            query: 搜索查询
            time_range: 时间范围 ('24h', 'week', 'month')
            max_results: 最大结果数
            
        Returns:
            LocalSearchResponse对象
        """
        # 计算日期范围
        end_date = datetime.now().date()
        if time_range == '24h' or time_range == 'd':
            start_date = end_date - timedelta(days=1)
        elif time_range == 'week' or time_range == 'w':
            start_date = end_date - timedelta(weeks=1)
        elif time_range == 'month' or time_range == 'm':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=1)
        
        date_filter = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
        
        # 添加时间相关的搜索关键词
        if time_range in ['24h', 'd']:
            query_with_time = f"{query} 最新 今天"
        elif time_range in ['week', 'w']:
            query_with_time = f"{query} 本周 最近一周"
        else:
            query_with_time = query
        
        return self.search(
            query=query_with_time,
            max_results=max_results,
            enrich_content=True,
            date_filter=date_filter
        )


# ===== 单例实例 =====

_local_search_engine = None

def get_local_search_engine() -> LocalSearchEngine:
    """获取本地搜索引擎单例"""
    global _local_search_engine
    if _local_search_engine is None:
        _local_search_engine = LocalSearchEngine()
    return _local_search_engine

