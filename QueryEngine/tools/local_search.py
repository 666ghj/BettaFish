"""
本地搜索引擎 - 替换Tavily API
使用自建爬虫实现完全独立的搜索功能
"""

import os
import sys
from typing import List, Optional
from dataclasses import dataclass, field

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

try:
    from utils.web_search import UnifiedWebSearch, SearchResult
except ImportError:
    # 兼容性：如果utils不在路径中
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    utils_dir = os.path.join(root_dir, 'utils')
    if utils_dir not in sys.path:
        sys.path.insert(0, utils_dir)
    from web_search import UnifiedWebSearch, SearchResult

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG

# 保持与原有TavilyResponse接口兼容
@dataclass
class ImageResult:
    """图片搜索结果数据类"""
    url: str
    description: Optional[str] = None

@dataclass
class TavilyResponse:
    """封装搜索结果，保持与Tavily API的兼容接口"""
    query: str
    answer: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    response_time: Optional[float] = None


class LocalNewsAgency:
    """
    本地新闻搜索服务
    替换TavilyNewsAgency，保持相同的接口
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化本地搜索服务
        
        Args:
            api_key: 保留参数以保持接口兼容（本地搜索不需要key）
        """
        self.search_engine = UnifiedWebSearch(primary_engine="duckduckgo")
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=TavilyResponse(query="搜索失败"))
    def _search_internal(self, **kwargs) -> TavilyResponse:
        """内部通用的搜索执行器"""
        import time
        start_time = time.time()
        
        query = kwargs.get('query', '')
        max_results = kwargs.get('max_results', 10)
        time_range = kwargs.get('time_range')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        # 执行搜索
        results = self.search_engine.search(
            query=query,
            max_results=max_results,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        response_time = time.time() - start_time
        
        return TavilyResponse(
            query=query,
            results=results,
            images=[],  # 图片搜索功能暂不支持
            answer=None,  # 不使用AI摘要
            response_time=response_time
        )
    
    # 保持与TavilyNewsAgency相同的接口
    
    def basic_search_news(self, query: str, max_results: int = 7) -> TavilyResponse:
        """
        【工具】基础新闻搜索: 执行一次标准、快速的新闻搜索
        """
        print(f"--- TOOL: 本地基础新闻搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            max_results=max_results,
        )
    
    def deep_search_news(self, query: str) -> TavilyResponse:
        """
        【工具】深度新闻分析: 对一个主题进行深入搜索
        注意：本地搜索不区分深度和基础，都执行相同搜索
        """
        print(f"--- TOOL: 本地深度新闻分析 (query: {query}) ---")
        return self._search_internal(
            query=query,
            max_results=20,  # 深度搜索返回更多结果
        )
    
    def search_news_last_24_hours(self, query: str) -> TavilyResponse:
        """
        【工具】搜索24小时内新闻: 获取关于某个主题的最新动态
        """
        print(f"--- TOOL: 本地搜索24小时内新闻 (query: {query}) ---")
        return self._search_internal(
            query=query,
            time_range='d',
            max_results=10
        )
    
    def search_news_last_week(self, query: str) -> TavilyResponse:
        """
        【工具】搜索本周新闻: 获取关于某个主题过去一周内的主要新闻报道
        """
        print(f"--- TOOL: 本地搜索本周新闻 (query: {query}) ---")
        return self._search_internal(
            query=query,
            time_range='w',
            max_results=10
        )
    
    def search_images_for_news(self, query: str) -> TavilyResponse:
        """
        【工具】查找新闻图片: 搜索与某个新闻主题相关的图片
        注意：本地搜索暂不支持图片搜索，返回空列表
        """
        print(f"--- TOOL: 本地搜索新闻图片 (query: {query}) ---")
        print("⚠️  警告: 本地搜索暂不支持图片搜索功能")
        return self._search_internal(
            query=query,
            max_results=5
        )
    
    def search_news_by_date(self, query: str, start_date: str, end_date: str) -> TavilyResponse:
        """
        【工具】按指定日期范围搜索新闻: 在一个明确的历史时间段内搜索新闻
        """
        print(f"--- TOOL: 本地按日期范围搜索新闻 (query: {query}, from: {start_date}, to: {end_date}) ---")
        return self._search_internal(
            query=query,
            start_date=start_date,
            end_date=end_date,
            max_results=15
        )

