"""
本地多模态搜索服务 - 替换Bocha API
使用自建爬虫实现完全独立的搜索功能
"""

import os
import sys
from typing import List, Dict, Any, Optional
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

# 保持与原有BochaResponse接口兼容
@dataclass
class WebpageResult:
    """网页搜索结果"""
    name: str
    url: str
    snippet: str
    display_url: Optional[str] = None
    date_last_crawled: Optional[str] = None

@dataclass
class ImageResult:
    """图片搜索结果"""
    name: str
    content_url: str
    host_page_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class ModalCardResult:
    """模态卡结构化数据结果（本地搜索暂不支持）"""
    card_type: str
    content: Dict[str, Any]

@dataclass
class BochaResponse:
    """封装搜索结果，保持与Bocha API的兼容接口"""
    query: str
    conversation_id: Optional[str] = None
    answer: Optional[str] = None
    follow_ups: List[str] = field(default_factory=list)
    webpages: List[WebpageResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    modal_cards: List[ModalCardResult] = field(default_factory=list)


class LocalMultimodalSearch:
    """
    本地多模态搜索服务
    替换BochaMultimodalSearch，保持相同的接口
    """
    
    BASE_URL = "local"  # 本地搜索，不使用远程API
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化本地搜索服务
        
        Args:
            api_key: 保留参数以保持接口兼容（本地搜索不需要key）
        """
        self.search_engine = UnifiedWebSearch(primary_engine="duckduckgo")
    
    def _parse_search_response(self, search_results: List[SearchResult], query: str) -> BochaResponse:
        """将搜索结果转换为BochaResponse格式"""
        response = BochaResponse(query=query)
        
        for result in search_results:
            response.webpages.append(WebpageResult(
                name=result.title,
                url=result.url,
                snippet=result.content,
                display_url=result.url,
                date_last_crawled=result.published_date
            ))
        
        return response
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=BochaResponse(query="搜索失败"))
    def _search_internal(self, **kwargs) -> BochaResponse:
        """内部通用的搜索执行器"""
        query = kwargs.get("query", "Unknown Query")
        max_results = kwargs.get("count", kwargs.get("max_results", 10))
        freshness = kwargs.get("freshness")  # 'oneDay' 或 'oneWeek'
        
        # 转换freshness为time_range
        time_range = None
        if freshness == 'oneDay':
            time_range = 'd'
        elif freshness == 'oneWeek':
            time_range = 'w'
        
        # 执行搜索
        results = self.search_engine.search(
            query=query,
            max_results=max_results,
            time_range=time_range
        )
        
        return self._parse_search_response(results, query)
    
    # 保持与BochaMultimodalSearch相同的接口
    
    def comprehensive_search(self, query: str, max_results: int = 10) -> BochaResponse:
        """
        【工具】全面综合搜索: 执行一次标准的、包含所有信息类型的综合搜索
        """
        print(f"--- TOOL: 本地全面综合搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            count=max_results
        )
    
    def web_search_only(self, query: str, max_results: int = 15) -> BochaResponse:
        """
        【工具】纯网页搜索: 只获取网页链接和摘要
        """
        print(f"--- TOOL: 本地纯网页搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            count=max_results
        )
    
    def search_for_structured_data(self, query: str) -> BochaResponse:
        """
        【工具】结构化数据查询: 专门用于可能触发"模态卡"的查询
        注意：本地搜索暂不支持模态卡，返回普通网页结果
        """
        print(f"--- TOOL: 本地结构化数据查询 (query: {query}) ---")
        print("⚠️  警告: 本地搜索暂不支持模态卡功能，返回普通搜索结果")
        return self._search_internal(
            query=query,
            count=5
        )
    
    def search_last_24_hours(self, query: str) -> BochaResponse:
        """
        【工具】搜索24小时内信息: 获取关于某个主题的最新动态
        """
        print(f"--- TOOL: 本地搜索24小时内信息 (query: {query}) ---")
        return self._search_internal(
            query=query,
            freshness='oneDay'
        )
    
    def search_last_week(self, query: str) -> BochaResponse:
        """
        【工具】搜索本周信息: 获取关于某个主题过去一周内的主要报道
        """
        print(f"--- TOOL: 本地搜索本周信息 (query: {query}) ---")
        return self._search_internal(
            query=query,
            freshness='oneWeek'
        )

