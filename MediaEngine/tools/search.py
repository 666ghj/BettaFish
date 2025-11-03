"""
专为 AI Agent 设计的多模态搜索工具集 (Bocha)

版本: 1.1
最后更新: 2025-08-22

此脚本将复杂的 Bocha AI Search 功能分解为一系列目标明确、参数极少的独立工具，
专为 AI Agent 调用而设计。Agent 只需根据任务意图（如常规搜索、查找结构化数据或时效性新闻）
选择合适的工具，无需理解复杂的参数组合。

核心特性:
- 强大多模态能力: 能同时返回网页、图片、AI总结、追问建议，以及丰富的“模态卡”结构化数据。
- 模态卡支持: 针对天气、股票、汇率、百科、医疗等特定查询，可直接返回结构化数据卡片，便于Agent直接解析和使用。

主要工具:
- comprehensive_search: 执行全面搜索，返回网页、图片、AI总结及可能的模态卡。
- search_for_structured_data: 专门用于查询天气、股票、汇率等可触发“模态卡”的结构化信息。
- web_search_only: 执行纯网页搜索，不请求AI总结，速度更快。
- search_last_24_hours: 获取过去24小时内的最新信息。
- search_last_week: 获取过去一周内的主要报道。
"""

import os
import json
import sys
from typing import List, Dict, Any, Optional, Literal

# 运行前请确保已安装 requests 库: pip install requests
try:
    import requests
except ImportError:
    raise ImportError("requests 库未安装，请运行 `pip install requests` 进行安装。")

# 添加utils目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from utils.retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG

# --- 1. 数据结构定义 ---
from dataclasses import dataclass, field

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
    """
    模态卡结构化数据结果
    这是 Bocha 搜索的核心特色，用于返回特定类型的结构化信息。
    """
    card_type: str  # 例如: weather_china, stock, baike_pro, medical_common
    content: Dict[str, Any]  # 解析后的JSON内容

@dataclass
class BochaResponse:
    """封装 Bocha API 的完整返回结果，以便在工具间传递"""
    query: str
    conversation_id: Optional[str] = None
    answer: Optional[str] = None  # AI生成的总结答案
    follow_ups: List[str] = field(default_factory=list) # AI生成的追问
    webpages: List[WebpageResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    modal_cards: List[ModalCardResult] = field(default_factory=list)


# --- 2. 核心客户端与专用工具集 ---

class BochaMultimodalSearch:
    """
    一个包含多种专用多模态搜索工具的客户端。
    每个公共方法都设计为供 AI Agent 独立调用的工具。
    """
    
    BASE_URL = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化客户端。
        Args:
            api_key: Bocha API密钥，若不提供则从环境变量 BOCHA_API_KEY 读取。
        """
        if api_key is None:
            api_key = os.getenv("BOCHA_API_KEY")
            if not api_key:
                raise ValueError("Bocha API Key未找到！请设置 BOCHA_API_KEY 环境变量或在初始化时提供")
        
        self._headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }

    def _parse_search_response(self, response_dict: Dict[str, Any], query: str) -> BochaResponse:
        """从API的原始字典响应中解析出结构化的BochaResponse对象"""
        
        final_response = BochaResponse(query=query)
        final_response.conversation_id = response_dict.get('conversation_id')

        messages = response_dict.get('messages', [])
        for msg in messages:
            role = msg.get('role')
            if role != 'assistant':
                continue

            msg_type = msg.get('type')
            content_type = msg.get('content_type')
            content_str = msg.get('content', '{}')
            
            try:
                content_data = json.loads(content_str)
            except json.JSONDecodeError:
                # 如果内容不是合法的JSON字符串（例如纯文本的answer），则直接使用
                content_data = content_str

            if msg_type == 'answer' and content_type == 'text':
                final_response.answer = content_data
            
            elif msg_type == 'follow_up' and content_type == 'text':
                final_response.follow_ups.append(content_data)

            elif msg_type == 'source':
                if content_type == 'webpage':
                    web_results = content_data.get('value', [])
                    for item in web_results:
                        final_response.webpages.append(WebpageResult(
                            name=item.get('name'),
                            url=item.get('url'),
                            snippet=item.get('snippet'),
                            display_url=item.get('displayUrl'),
                            date_last_crawled=item.get('dateLastCrawled')
                        ))
                elif content_type == 'image':
                    final_response.images.append(ImageResult(
                        name=content_data.get('name'),
                        content_url=content_data.get('contentUrl'),
                        host_page_url=content_data.get('hostPageUrl'),
                        thumbnail_url=content_data.get('thumbnailUrl'),
                        width=content_data.get('width'),
                        height=content_data.get('height')
                    ))
                # 所有其他 content_type 都视为模态卡
                else:
                    final_response.modal_cards.append(ModalCardResult(
                        card_type=content_type,
                        content=content_data
                    ))
                    
        return final_response


    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=BochaResponse(query="搜索失败"))
    def _search_internal(self, **kwargs) -> BochaResponse:
        """内部通用的搜索执行器，所有工具最终都调用此方法"""
        query = kwargs.get("query", "Unknown Query")
        payload = {
            "stream": False,  # Agent工具通常使用非流式以获取完整结果
        }
        payload.update(kwargs)
        
        try:
            response = requests.post(self.BASE_URL, headers=self._headers, json=payload, timeout=30)
            response.raise_for_status()  # 如果HTTP状态码是4xx或5xx，则抛出异常
            
            response_dict = response.json()
            if response_dict.get("code") != 200:
                print(f"API返回错误: {response_dict.get('msg', '未知错误')}")
                return BochaResponse(query=query)

            return self._parse_search_response(response_dict, query)

        except requests.exceptions.RequestException as e:
            print(f"搜索时发生网络错误: {str(e)}")
            raise e  # 让重试机制捕获并处理
        except Exception as e:
            print(f"处理响应时发生未知错误: {str(e)}")
            raise e  # 让重试机制捕获并处理

    # --- Agent 可用的工具方法 ---

    def comprehensive_search(self, query: str, max_results: int = 10) -> BochaResponse:
        """
        【工具】全面综合搜索: 执行一次标准的、包含所有信息类型的综合搜索。
        返回网页、图片、AI总结、追问建议和可能的模态卡。这是最常用的通用搜索工具。
        Agent可提供搜索查询(query)和可选的最大结果数(max_results)。
        """
        print(f"--- TOOL: 全面综合搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            count=max_results,
            answer=True  # 开启AI总结
        )
        
    def web_search_only(self, query: str, max_results: int = 15) -> BochaResponse:
        """
        【工具】纯网页搜索: 只获取网页链接和摘要，不请求AI生成答案。
        适用于需要快速获取原始网页信息，而不需要AI额外分析的场景。速度更快，成本更低。
        """
        print(f"--- TOOL: 纯网页搜索 (query: {query}) ---")
        return self._search_internal(
            query=query,
            count=max_results,
            answer=False # 关闭AI总结
        )

    def search_for_structured_data(self, query: str) -> BochaResponse:
        """
        【工具】结构化数据查询: 专门用于可能触发“模态卡”的查询。
        当Agent意图是查询天气、股票、汇率、百科定义、火车票、汽车参数等结构化信息时，应优先使用此工具。
        它会返回所有信息，但Agent应重点关注结果中的 `modal_cards` 部分。
        """
        print(f"--- TOOL: 结构化数据查询 (query: {query}) ---")
        # 实现上与 comprehensive_search 相同，但通过命名和文档引导Agent的意图
        return self._search_internal(
            query=query,
            count=5, # 结构化查询通常不需要太多网页结果
            answer=True
        )

    def search_last_24_hours(self, query: str) -> BochaResponse:
        """
        【工具】搜索24小时内信息: 获取关于某个主题的最新动态。
        此工具专门查找过去24小时内发布的内容。适用于追踪突发事件或最新进展。
        """
        print(f"--- TOOL: 搜索24小时内信息 (query: {query}) ---")
        return self._search_internal(query=query, freshness='oneDay', answer=True)

    def search_last_week(self, query: str) -> BochaResponse:
        """
        【工具】搜索本周信息: 获取关于某个主题过去一周内的主要报道。
        适用于进行周度舆情总结或回顾。
        """
        print(f"--- TOOL: 搜索本周信息 (query: {query}) ---")
        return self._search_internal(query=query, freshness='oneWeek', answer=True)


# --- 3. 测试与使用示例 ---

def print_response_summary(response: BochaResponse):
    """简化的打印函数，用于展示测试结果"""
    if not response or not response.query:
        print("未能获取有效响应。")
        return
        
    print(f"\n查询: '{response.query}' | 会话ID: {response.conversation_id}")
    if response.answer:
        print(f"AI摘要: {response.answer[:150]}...")
    
    print(f"找到 {len(response.webpages)} 个网页, {len(response.images)} 张图片, {len(response.modal_cards)} 个模态卡。")

    if response.modal_cards:
        first_card = response.modal_cards[0]
        print(f"第一个模态卡类型: {first_card.card_type}")

    if response.webpages:
        first_result = response.webpages[0]
        print(f"第一条网页结果: {first_result.name}")

    if response.follow_ups:
        print(f"建议追问: {response.follow_ups}")

    print("-" * 60)


if __name__ == "__main__":
    # 在运行前，请确保您已设置 BOCHA_API_KEY 环境变量
    
    try:
        # 初始化多模态搜索客户端，它内部包含了所有工具
        search_client = BochaMultimodalSearch()

        # 场景1: Agent进行一次常规的、需要AI总结的综合搜索
        response1 = search_client.comprehensive_search(query="人工智能对未来教育的影响")
        print_response_summary(response1)

        # 场景2: Agent需要查询特定结构化信息 - 天气
        response2 = search_client.search_for_structured_data(query="上海明天天气怎么样")
        print_response_summary(response2)
        # 深度解析第一个模态卡
        if response2.modal_cards and response2.modal_cards[0].card_type == 'weather_china':
             print("天气模态卡详情:", json.dumps(response2.modal_cards[0].content, indent=2, ensure_ascii=False))


        # 场景3: Agent需要查询特定结构化信息 - 股票
        response3 = search_client.search_for_structured_data(query="东方财富股票")
        print_response_summary(response3)

        # 场景4: Agent需要追踪某个事件的最新进展
        response4 = search_client.search_last_24_hours(query="C929大飞机最新消息")
        print_response_summary(response4)

        # 场景5: Agent只需要快速获取网页信息，不需要AI总结
        response5 = search_client.web_search_only(query="Python dataclasses用法")
        print_response_summary(response5)
        
        # 场景6: Agent需要回顾一周内关于某项技术的新闻
        response6 = search_client.search_last_week(query="量子计算商业化")
        print_response_summary(response6)
        
        '''下面是测试程序的输出：
        --- TOOL: 全面综合搜索 (query: 人工智能对未来教育的影响) ---

查询: '人工智能对未来教育的影响' | 会话ID: bf43bfe4c7bb4f7b8a3945515d8ab69e
AI摘要: 人工智能对未来教育有着多方面的影响。

从积极影响来看：
- 在教学资源方面，人工智能有助于教育资源的均衡分配[引用:4]。例如通过人工智能云平台，可以实现优质资源的共享，这对于偏远地区来说意义重大，能让那里的学生也接触到优质的教育内 容，一定程度上缓解师资短缺的问题，因为AI驱动的智能教学助手或虚拟...
找到 10 个网页, 1 张图片, 1 个模态卡。
第一个模态卡类型: video
第一条网页结果: 人工智能如何影响教育变革
建议追问: [['人工智能将如何改变未来的教育模式？', '在未来教育中，人工智能会给教师带来哪些挑战？', '未来教育中，学生如何利用人工智能提升学习效果？']]
------------------------------------------------------------
--- TOOL: 结构化数据查询 (query: 上海明天天气怎么样) ---

查询: '上海明天天气怎么样' | 会话ID: e412aa1548cd43a295430e47a62adda2
AI摘要: 根据所给信息，无法确定上海明天的天气情况。

首先，所提供的信息都是关于2025年8月22日的天气状况，包括当天的气温、降水、风力、湿度以及高温预警等信息[引用:1][引用:2][引用:3][引用:5]。然而，这些信息没有涉及到明天（8月23 日）天气的预测内容。虽然提到了副热带高压一直到8月底高温都...
找到 5 个网页, 1 张图片, 2 个模态卡。
第一个模态卡类型: video
第一条网页结果: 今日冲击38!上海八月高温天数和夏季持续高温天数有望双双破纪录_天气_低压_气象站
建议追问: [['能告诉我上海明天的气温范围吗？', '上海明天会有降雨吗？', '上海明天的天气是晴天还是阴天呢？']]
------------------------------------------------------------
--- TOOL: 结构化数据查询 (query: 东方财富股票) ---

查询: '东方财富股票' | 会话ID: 584d62ed97834473b967127852e1eaa0
AI摘要: 仅根据提供的上下文，无法确切获取东方财富股票的相关信息。

从给出的这些数据来看，并没有直接表明与东方财富股票相关的特定数据。例如，没有东方财富股票的涨跌幅情况、成交量、市值等具体数据[引用:1][引用:3]。也没有涉及东方财富股票在研报 、评级方面的信息[引用:2]。同时，上下文里关于股票价格、成交...
找到 5 个网页, 1 张图片, 2 个模态卡。
第一个模态卡类型: video
第一条网页结果: 股票价格_分时成交_行情_走势图—东方财富网
建议追问: [['东方财富股票近期的走势如何？', '东方财富股票有哪些主要的投资亮点？', '东方财富股票的历史最高和最低股价是多少？']]
------------------------------------------------------------
--- TOOL: 搜索24小时内信息 (query: C929大飞机最新消息) ---

查询: 'C929大飞机最新消息' | 会话ID: 5904021dc29d497e938e04db18d7f2e2
AI摘要: 根据提供的上下文，没有关于C929大飞机的直接消息，无法确切给出C929大飞机的最新消息。

目前提供的上下文涵盖了众多航空领域相关事件，但多是围绕波音787、空客A380相关专家的人事变动、国产飞机“C909云端之旅”、科德数控的营收情况、俄制航空发动机供应相关以及其他非C929大飞机相关的内容。...
找到 10 个网页, 1 张图片, 1 个模态卡。
第一个模态卡类型: video
第一条网页结果: 放弃美国千万年薪,波音787顶尖专家回国,或可协助破解C929
建议追问: [['C929大飞机目前的研发进度如何？', '有没有关于C929大飞机预计首飞时间的消息？', 'C929大飞机在技术创新方面有哪些新进展？']]
------------------------------------------------------------
--- TOOL: 纯网页搜索 (query: Python dataclasses用法) ---

查询: 'Python dataclasses用法' | 会话ID: 74c742759d2e4b17b52d8b735ce24537
找到 15 个网页, 1 张图片, 1 个模态卡。
第一个模态卡类型: video
第一条网页结果: 不可不知的dataclasses  python小知识_python dataclasses-CSDN博客
------------------------------------------------------------
--- TOOL: 搜索本周信息 (query: 量子计算商业化) ---

AI摘要: 量子计算商业化正在逐步推进。

量子计算商业化有着多方面的体现和推动因素。从国际上看，美国能源部橡树岭国家实验室选择IQM Radiance作为其首台本地部署的量子计算机，计划于2025年第三季度交付并集成至高性能计算系统中[引用:4]；英国量子计算公司Oxford Ionics的全栈离子阱量子计算...
找到 10 个网页, 1 张图片, 1 个模态卡。
第一个模态卡类型: video
第一条网页结果: 量子计算商业潜力释放正酣,微美全息(WIMI.US)创新科技卡位“生态高地”
建议追问: [['量子计算商业化目前有哪些成功的案例？', '哪些公司在推动量子计算商业化进程？', '量子计算商业化面临的主要挑战是什么？']]
------------------------------------------------------------'''

    except ValueError as e:
        print(f"初始化失败: {e}")
        print("请确保 BOCHA_API_KEY 环境变量已正确设置。")
    except Exception as e:
        print(f"测试过程中发生未知错误: {e}")