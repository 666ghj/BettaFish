"""
工具调用模块
提供外部工具接口，如网络搜索等
优先使用本地搜索，向后兼容Tavily
"""

# 优先使用本地搜索
try:
    from .local_search import (
        LocalNewsAgency,
        TavilyResponse,
        ImageResult
    )
    # 从utils导入SearchResult
    from utils.web_search import SearchResult
    
    # 使用别名保持接口兼容
    TavilyNewsAgency = LocalNewsAgency
    USE_LOCAL_SEARCH = True
    
    # 本地搜索不需要print_response_summary，创建空函数
    def print_response_summary(response):
        """打印搜索结果摘要（本地搜索版本）"""
        if not response or not response.query:
            print("未能获取有效响应。")
            return
        print(f"\n查询: '{response.query}' | 耗时: {response.response_time or 0:.2f}s" if response.response_time else f"\n查询: '{response.query}'")
        print(f"找到 {len(response.results)} 条网页")
        if response.results:
            first_result = response.results[0]
            date_info = f"(发布于: {first_result.published_date})" if first_result.published_date else ""
            print(f"第一条结果: {first_result.title} {date_info}")
        print("-" * 60)
        
except ImportError as e:
    # 如果本地搜索不可用，回退到Tavily（向后兼容）
    print(f"警告: 本地搜索模块导入失败 ({e})，使用Tavily API")
    from .search import (
        TavilyNewsAgency,
        SearchResult,
        TavilyResponse,
        ImageResult,
        print_response_summary
    )
    USE_LOCAL_SEARCH = False

__all__ = [
    "TavilyNewsAgency",
    "SearchResult",
    "TavilyResponse",
    "ImageResult",
    "print_response_summary",
    "USE_LOCAL_SEARCH",
]
