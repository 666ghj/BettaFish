"""
工具调用模块
提供外部工具接口，如多模态搜索等
优先使用本地搜索，向后兼容Bocha
"""

# 优先使用本地搜索
try:
    from .local_search import (
        LocalMultimodalSearch,
        BochaResponse,
        WebpageResult,
        ImageResult,
        ModalCardResult
    )
    
    # 使用别名保持接口兼容
    BochaMultimodalSearch = LocalMultimodalSearch
    USE_LOCAL_SEARCH = True
    
    # 本地搜索不需要print_response_summary，创建函数
    def print_response_summary(response):
        """打印搜索结果摘要（本地搜索版本）"""
        if not response or not response.query:
            print("未能获取有效响应。")
            return
        print(f"\n查询: '{response.query}'")
        print(f"找到 {len(response.webpages)} 个网页, {len(response.images)} 张图片")
        if response.webpages:
            first_result = response.webpages[0]
            print(f"第一条网页结果: {first_result.name}")
        print("-" * 60)
        
except ImportError as e:
    # 如果本地搜索不可用，回退到Bocha（向后兼容）
    print(f"警告: 本地搜索模块导入失败 ({e})，使用Bocha API")
    from .search import (
        BochaMultimodalSearch,
        WebpageResult,
        ImageResult,
        ModalCardResult,
        BochaResponse,
        print_response_summary
    )
    USE_LOCAL_SEARCH = False

__all__ = [
    "BochaMultimodalSearch",
    "WebpageResult",
    "ImageResult",
    "ModalCardResult",
    "BochaResponse",
    "print_response_summary",
    "USE_LOCAL_SEARCH",
]
