"""
自建网络爬虫搜索服务
用于替换Tavily和Bocha API，实现完全本地化的网络搜索功能
"""

import os
import sys
import time
import re
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse
import json

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None
    print("警告: beautifulsoup4未安装，部分功能可能受限，建议安装: pip install beautifulsoup4 lxml")

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG

# 设置请求头，模拟浏览器
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


@dataclass
class SearchResult:
    """通用搜索结果数据类"""
    title: str
    url: str
    content: str
    score: Optional[float] = None
    raw_content: Optional[str] = None
    published_date: Optional[str] = None


class WebSearchEngine:
    """通用网络搜索引擎基类"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """执行搜索，返回结果列表"""
        raise NotImplementedError("子类必须实现search方法")
    
    def _fetch_page_content(self, url: str) -> Optional[str]:
        """获取网页内容"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"获取页面内容失败 {url}: {str(e)}")
            return None
    
    def _extract_published_date(self, html: str, url: str) -> Optional[str]:
        """从HTML中提取发布日期"""
        if not BeautifulSoup:
            return None
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 尝试多种日期格式
            date_patterns = [
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(\d{4}年\d{1,2}月\d{1,2}日)',
            ]
            
            # 查找meta标签中的日期
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date and meta_date.get('content'):
                date_str = meta_date['content']
                # 解析ISO格式日期
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            # 查找time标签
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                date_str = time_tag['datetime']
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            # 从文本中提取日期
            text = soup.get_text()
            for pattern in date_patterns:
                match = re.search(pattern, text[:1000])  # 只搜索前1000字符
                if match:
                    date_str = match.group(1)
                    # 转换为标准格式
                    date_str = date_str.replace('/', '-').replace('年', '-').replace('月', '-').replace('日', '')
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
            
        except Exception as e:
            print(f"提取发布日期失败: {str(e)}")
        
        return None
    
    def _clean_html_text(self, html: str, max_length: int = 500) -> str:
        """清理HTML，提取纯文本"""
        if not BeautifulSoup:
            # 简单清理HTML标签
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:max_length]
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            # 移除script和style标签
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            # 清理空白字符
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:max_length] if len(text) > max_length else text
        except Exception as e:
            print(f"清理HTML失败: {str(e)}")
            return html[:max_length]


class DuckDuckGoSearch(WebSearchEngine):
    """DuckDuckGo搜索引擎（免费，无需API Key）"""
    
    BASE_URL = "https://html.duckduckgo.com/html/"
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=[])
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用DuckDuckGo搜索"""
        try:
            # 构建搜索URL
            params = {
                'q': query,
            }
            
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            if not BeautifulSoup:
                # 如果没有BeautifulSoup，使用简单正则提取
                return self._parse_simple(response.text, max_results)
            
            soup = BeautifulSoup(response.text, 'lxml')
            results = []
            
            # DuckDuckGo的HTML结构
            result_divs = soup.find_all('div', class_='result')
            
            for div in result_divs[:max_results]:
                try:
                    # 提取标题和URL
                    title_elem = div.find('a', class_='result__a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    
                    # 提取摘要
                    snippet_elem = div.find('a', class_='result__snippet')
                    if snippet_elem:
                        content = snippet_elem.get_text(strip=True)
                    else:
                        content = ""
                    
                    # 如果没有摘要或摘要太短，尝试获取更多内容
                    published_date = None
                    if not content or len(content) < 50:
                        # 添加延迟避免请求过快
                        time.sleep(0.2)
                        html_content = self._fetch_page_content(url)
                        if html_content:
                            content = self._clean_html_text(html_content, 300)
                            # 尝试提取发布日期
                            published_date = self._extract_published_date(html_content, url)
                    
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        content=content,
                        score=None,
                        raw_content=content,
                        published_date=published_date
                    ))
                    
                except Exception as e:
                    print(f"解析搜索结果失败: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"DuckDuckGo搜索失败: {str(e)}")
            return []
    
    def _parse_simple(self, html: str, max_results: int) -> List[SearchResult]:
        """简单正则解析（当BeautifulSoup不可用时）"""
        results = []
        
        # 简单的标题和URL提取
        title_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
        matches = re.findall(title_pattern, html)
        
        for url, title in matches[:max_results]:
            if url and title:
                results.append(SearchResult(
                    title=title.strip(),
                    url=url,
                    content="",  # 简单模式下不获取内容
                    score=None
                ))
        
        return results


class BingSearch(WebSearchEngine):
    """Bing搜索引擎（免费，无需API Key）"""
    
    BASE_URL = "https://www.bing.com/search"
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=[])
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用Bing搜索"""
        try:
            params = {
                'q': query,
                'count': max_results,
            }
            
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            if not BeautifulSoup:
                return self._parse_simple(response.text, max_results)
            
            soup = BeautifulSoup(response.text, 'lxml')
            results = []
            
            # Bing的搜索结果结构
            result_items = soup.find_all('li', class_='b_algo')
            
            for item in result_items[:max_results]:
                try:
                    # 提取标题
                    title_elem = item.find('h2')
                    if not title_elem:
                        continue
                    
                    title_link = title_elem.find('a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
                    
                    # 提取摘要
                    snippet_elem = item.find('p')
                    content = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        content=content,
                        score=None,
                        raw_content=content
                    ))
                    
                except Exception as e:
                    print(f"解析Bing搜索结果失败: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"Bing搜索失败: {str(e)}")
            return []
    
    def _parse_simple(self, html: str, max_results: int) -> List[SearchResult]:
        """简单解析"""
        results = []
        # Bing的标题链接模式
        pattern = r'<h2><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></h2>'
        matches = re.findall(pattern, html)
        
        for url, title in matches[:max_results]:
            if url and title:
                results.append(SearchResult(
                    title=title.strip(),
                    url=url,
                    content="",
                    score=None
                ))
        
        return results


class UnifiedWebSearch:
    """
    统一的网络搜索服务
    支持多种搜索引擎，自动回退
    """
    
    def __init__(self, primary_engine: str = "duckduckgo"):
        """
        初始化搜索服务
        
        Args:
            primary_engine: 主要搜索引擎 ("duckduckgo" 或 "bing")
        """
        self.engines = {
            "duckduckgo": DuckDuckGoSearch(),
            "bing": BingSearch(),
        }
        self.primary_engine = primary_engine.lower()
        self.current_engine = self.engines.get(self.primary_engine, self.engines["duckduckgo"])
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[SearchResult]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            time_range: 时间范围 ("d"=24小时, "w"=1周)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        
        Returns:
            搜索结果列表
        """
        # 执行搜索
        results = self.current_engine.search(query, max_results * 2)  # 多获取一些用于筛选
        
        # 如果结果不足，尝试备用引擎
        if len(results) < max_results:
            for engine_name, engine in self.engines.items():
                if engine_name != self.primary_engine:
                    try:
                        additional_results = engine.search(query, max_results)
                        results.extend(additional_results)
                        break
                    except:
                        continue
        
        # 按时间范围筛选
        if time_range or (start_date and end_date):
            results = self._filter_by_date(results, time_range, start_date, end_date)
        
        # 去重（按URL）
        seen_urls = set()
        unique_results = []
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        return unique_results[:max_results]
    
    def _filter_by_date(
        self,
        results: List[SearchResult],
        time_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> List[SearchResult]:
        """按日期筛选结果"""
        filtered = []
        
        # 确定日期范围
        if time_range == "d":
            # 24小时内
            cutoff_date = datetime.now() - timedelta(days=1)
            start_date = cutoff_date.strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif time_range == "w":
            # 1周内
            cutoff_date = datetime.now() - timedelta(weeks=1)
            start_date = cutoff_date.strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if not start_date or not end_date:
            return results
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except:
            return results
        
        for result in results:
            # 如果结果没有发布日期，尝试获取
            if not result.published_date:
                html = self.current_engine._fetch_page_content(result.url)
                if html:
                    result.published_date = self.current_engine._extract_published_date(html, result.url)
            
            # 如果有发布日期，进行筛选
            if result.published_date:
                try:
                    pub_dt = datetime.strptime(result.published_date, '%Y-%m-%d')
                    if start_dt <= pub_dt <= end_dt:
                        filtered.append(result)
                except:
                    # 日期格式不匹配，保留结果
                    filtered.append(result)
            else:
                # 没有发布日期，默认保留（避免过度过滤）
                filtered.append(result)
        
        return filtered


# 创建全局实例
_default_search = UnifiedWebSearch()


def search_web(query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
    """便捷搜索函数"""
    return _default_search.search(query, max_results, **kwargs)

