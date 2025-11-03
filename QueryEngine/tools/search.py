"""
专为 AI Agent 设计的舆情搜索工具集 (Tavily)

版本: 1.5
最后更新: 2025-08-22

此脚本将复杂的Tavily搜索功能分解为一系列目标明确、参数极少的独立工具，
专为AI Agent调用而设计。Agent只需根据任务意图选择合适的工具，
无需理解复杂的参数组合。所有工具默认搜索“新闻”(topic='news')。

新特性:
- 新增 `basic_search_news` 工具，用于执行标准、通用的新闻搜索。
- 每个搜索结果现在都包含 `published_date` (新闻发布日期)。

主要工具:
- basic_search_news: (新增) 执行标准、快速的通用新闻搜索。
- deep_search_news: 对主题进行最全面的深度分析。
- search_news_last_24_hours: 获取24小时内的最新动态。
- search_news_last_week: 获取过去一周的主要报道。
- search_images_for_news: 查找与新闻主题相关的图片。
- search_news_by_date: 在指定的历史日期范围内搜索。
"""

import os
import sys
from typing import List, Dict, Any, Optional

# 添加utils目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from utils.retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG
from dataclasses import dataclass, field

# 运行前请确保已安装Tavily库: pip install tavily-python
try:
    from tavily import TavilyClient
except ImportError:
    raise ImportError("Tavily库未安装，请运行 `pip install tavily-python` 进行安装。")

# --- 1. 数据结构定义 ---

@dataclass
class SearchResult:
    """
    网页搜索结果数据类
    包含 published_date 属性来存储新闻发布日期
    """
    title: str
    url: str
    content: str
    score: Optional[float] = None
    raw_content: Optional[str] = None
    published_date: Optional[str] = None

@dataclass
class ImageResult:
    """图片搜索结果数据类"""
    url: str
    description: Optional[str] = None

@dataclass
class TavilyResponse:
    """封装Tavily API的完整返回结果，以便在工具间传递"""
    query: str
    answer: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    response_time: Optional[float] = None


# --- 2. 核心客户端与专用工具集 ---

class TavilyNewsAgency:
    """
    一个包含多种专用新闻舆情搜索工具的客户端。
    每个公共方法都设计为供 AI Agent 独立调用的工具。
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化客户端。
        Args:
            api_key: Tavily API密钥，若不提供则从环境变量 TAVILY_API_KEY 读取。
        """
        if api_key is None:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ValueError("Tavily API Key未找到！请设置TAVILY_API_KEY环境变量或在初始化时提供")
        self._client = TavilyClient(api_key=api_key)

    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=TavilyResponse(query="搜索失败"))
    def _search_internal(self, **kwargs) -> TavilyResponse:
        """内部通用的搜索执行器，所有工具最终都调用此方法"""
        try:
            kwargs['topic'] = 'general'
            api_params = {k: v for k, v in kwargs.items() if v is not None}
            response_dict = self._client.search(**api_params)
            
            search_results = [
                SearchResult(
                    title=item.get('title'),
                    url=item.get('url'),
                    content=item.get('content'),
                    score=item.get('score'),
                    raw_content=item.get('raw_content'),
                    published_date=item.get('published_date')
                ) for item in response_dict.get('results', [])
            ]
            
            image_results = [ImageResult(url=item.get('url'), description=item.get('description')) for item in response_dict.get('images', [])]

            return TavilyResponse(
                query=response_dict.get('query'), answer=response_dict.get('answer'),
                results=search_results, images=image_results,
                response_time=response_dict.get('response_time')
            )
        except Exception as e:
            print(f"搜索时发生错误: {str(e)}")
            raise e  # 让重试机制捕获并处理

    # --- Agent 可用的工具方法 ---

    def basic_search_news(self, query: str, max_results: int = 7) -> TavilyResponse:
        """
        【工具】基础新闻搜索: 执行一次标准、快速的新闻搜索。
        这是最常用的通用搜索工具，适用于不确定需要何种特定搜索时。
        Agent可提供搜索查询(query)和可选的最大结果数(max_results)。
        """
        print(f"--- TOOL: 基础新闻搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False
        )

    def deep_search_news(self, query: str) -> TavilyResponse:
        """
        【工具】深度新闻分析: 对一个主题进行最全面、最深入的搜索。
        返回AI生成的“高级”详细摘要答案和最多20条最相关的新闻结果。适用于需要全面了解某个事件背景的场景。
        Agent只需提供搜索查询(query)。
        """
        print(f"--- TOOL: 深度新闻分析 (query: {query}) ---")
        return self._search_internal(
            query=query, search_depth="advanced", max_results=20, include_answer="advanced"
        )

    def search_news_last_24_hours(self, query: str) -> TavilyResponse:
        """
        【工具】搜索24小时内新闻: 获取关于某个主题的最新动态。
        此工具专门查找过去24小时内发布的新闻。适用于追踪突发事件或最新进展。
        Agent只需提供搜索查询(query)。
        """
        print(f"--- TOOL: 搜索24小时内新闻 (query: {query}) ---")
        return self._search_internal(query=query, time_range='d', max_results=10)

    def search_news_last_week(self, query: str) -> TavilyResponse:
        """
        【工具】搜索本周新闻: 获取关于某个主题过去一周内的主要新闻报道。
        适用于进行周度舆情总结或回顾。
        Agent只需提供搜索查询(query)。
        """
        print(f"--- TOOL: 搜索本周新闻 (query: {query}) ---")
        return self._search_internal(query=query, time_range='w', max_results=10)

    def search_images_for_news(self, query: str) -> TavilyResponse:
        """
        【工具】查找新闻图片: 搜索与某个新闻主题相关的图片。
        此工具会返回图片链接及描述，适用于需要为报告或文章配图的场景。
        Agent只需提供搜索查询(query)。
        """
        print(f"--- TOOL: 查找新闻图片 (query: {query}) ---")
        return self._search_internal(
            query=query, include_images=True, include_image_descriptions=True, max_results=5
        )

    def search_news_by_date(self, query: str, start_date: str, end_date: str) -> TavilyResponse:
        """
        【工具】按指定日期范围搜索新闻: 在一个明确的历史时间段内搜索新闻。
        这是唯一需要Agent提供详细时间参数的工具。适用于需要对特定历史事件进行分析的场景。
        Agent需要提供查询(query)、开始日期(start_date)和结束日期(end_date)，格式均为 'YYYY-MM-DD'。
        """
        print(f"--- TOOL: 按指定日期范围搜索新闻 (query: {query}, from: {start_date}, to: {end_date}) ---")
        return self._search_internal(
            query=query, start_date=start_date, end_date=end_date, max_results=15
        )


# --- 3. 测试与使用示例 ---

def print_response_summary(response: TavilyResponse):
    """简化的打印函数，用于展示测试结果，现在会显示发布日期"""
    if not response or not response.query:
        print("未能获取有效响应。")
        return
        
    print(f"\n查询: '{response.query}' | 耗时: {response.response_time}s")
    if response.answer:
        print(f"AI摘要: {response.answer[:120]}...")
    print(f"找到 {len(response.results)} 条网页, {len(response.images)} 张图片。")
    if response.results:
        first_result = response.results[0]
        date_info = f"(发布于: {first_result.published_date})" if first_result.published_date else ""
        print(f"第一条结果: {first_result.title} {date_info}")
    print("-" * 60)


if __name__ == "__main__":
    # 在运行前，请确保您已设置 TAVILY_API_KEY 环境变量
    
    try:
        # 初始化“新闻社”客户端，它内部包含了所有工具
        agency = TavilyNewsAgency()

        # 场景1: Agent 进行一次常规、快速的搜索
        response1 = agency.basic_search_news(query="奥运会最新赛况", max_results=5)
        print_response_summary(response1)

        # 场景2: Agent 需要全面了解“全球芯片技术竞争”的背景
        response2 = agency.deep_search_news(query="全球芯片技术竞争")
        print_response_summary(response2)

        # 场景3: Agent 需要追踪“GTC大会”的最新消息
        response3 = agency.search_news_last_24_hours(query="Nvidia GTC大会 最新发布")
        print_response_summary(response3)
        
        # 场景4: Agent 需要为一篇关于“自动驾驶”的周报查找素材
        response4 = agency.search_news_last_week(query="自动驾驶商业化落地")
        print_response_summary(response4)
        
        # 场景5: Agent 需要查找“韦伯太空望远镜”的新闻图片
        response5 = agency.search_images_for_news(query="韦伯太空望远镜最新发现")
        print_response_summary(response5)

        # 场景6: Agent 需要研究2025年第一季度关于“人工智能法规”的新闻
        response6 = agency.search_news_by_date(
            query="人工智能法规",
            start_date="2025-01-01",
            end_date="2025-03-31"
        )
        print_response_summary(response6)

    except ValueError as e:
        print(f"初始化失败: {e}")
        print("请确保 TAVILY_API_KEY 环境变量已正确设置。")
    except Exception as e:
        print(f"测试过程中发生未知错误: {e}")