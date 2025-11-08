"""
Deep Search Agent主类
整合所有模块，实现完整的深度搜索流程
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from .llms import LLMClient
from .nodes import (
    ReportStructureNode,
    FirstSearchNode, 
    ReflectionNode,
    FirstSummaryNode,
    ReflectionSummaryNode,
    ReportFormattingNode
)
from .state import State
from .tools import TavilyNewsAgency, TavilyResponse, SearchResult, ImageResult
from .utils import Settings, format_search_results_for_prompt
from loguru import logger

class DeepSearchAgent:
    """Deep Search Agent主类"""
    
    def __init__(self, config: Optional[Settings] = None):
        """
        初始化Deep Search Agent
        
        Args:
            config: 配置对象，如果不提供则自动加载
        """
        # 加载配置
        from .utils.config import settings
        self.config = config or settings
        
        # 初始化LLM客户端
        self.llm_client = self._initialize_llm()
        
        # 初始化搜索工具集
        self.search_agency = TavilyNewsAgency(api_key=self.config.TAVILY_API_KEY)
        
        # 初始化节点
        self._initialize_nodes()
        
        # 状态
        self.state = State()
        
        # 确保输出目录存在
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        logger.info(f"Query Agent已初始化")
        logger.info(f"使用LLM: {self.llm_client.get_model_info()}")
        logger.info(f"搜索工具集: TavilyNewsAgency (支持6种搜索工具)")
    
    def _initialize_llm(self) -> LLMClient:
        """初始化LLM客户端"""
        return LLMClient(
            api_key=self.config.QUERY_ENGINE_API_KEY,
            model_name=self.config.QUERY_ENGINE_MODEL_NAME,
            base_url=self.config.QUERY_ENGINE_BASE_URL,
        )
    
    def _initialize_nodes(self):
        """初始化处理节点"""
        self.first_search_node = FirstSearchNode(self.llm_client)
        self.reflection_node = ReflectionNode(self.llm_client)
        self.first_summary_node = FirstSummaryNode(self.llm_client)
        self.reflection_summary_node = ReflectionSummaryNode(self.llm_client)
        self.report_formatting_node = ReportFormattingNode(self.llm_client)
    
    def _validate_date_format(self, date_str: str) -> bool:
        """
        验证日期格式是否为YYYY-MM-DD
        
        Args:
            date_str: 日期字符串
            
        Returns:
            是否为有效格式
        """
        if not date_str:
            return False
        
        # 检查格式
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, date_str):
            return False
        
        # 检查日期是否有效
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _normalize_search_response(self, search_response: Any) -> Optional[TavilyResponse]:
        """
        规范化搜索响应，处理不同类型的返回值
        
        此方法解决了当搜索API返回dict而不是TavilyResponse对象时的类型错误问题。
        同时提供错误恢复机制，确保系统在异常情况下仍能继续运行。
        
        Args:
            search_response: 可能是TavilyResponse对象、dict或None
            
        Returns:
            规范化后的TavilyResponse对象，如果无法规范化则返回None
        """
        if search_response is None:
            return None
        
        # 如果已经是TavilyResponse对象，直接返回
        if isinstance(search_response, TavilyResponse):
            return search_response
        
        # 如果是dict，尝试转换为TavilyResponse对象
        if isinstance(search_response, dict):
            try:
                # 从dict中提取结果
                results = []
                if 'results' in search_response:
                    for item in search_response['results']:
                        if isinstance(item, dict):
                            results.append(SearchResult(
                                title=item.get('title', ''),
                                url=item.get('url', ''),
                                content=item.get('content', ''),
                                score=item.get('score'),
                                raw_content=item.get('raw_content'),
                                published_date=item.get('published_date')
                            ))
                        elif hasattr(item, '__dict__'):
                            # 如果已经是SearchResult对象
                            results.append(item)
                
                images = []
                if 'images' in search_response:
                    for item in search_response['images']:
                        if isinstance(item, dict):
                            images.append(ImageResult(
                                url=item.get('url', ''),
                                description=item.get('description')
                            ))
                        elif hasattr(item, '__dict__'):
                            images.append(item)
                
                return TavilyResponse(
                    query=search_response.get('query', ''),
                    answer=search_response.get('answer'),
                    results=results,
                    images=images,
                    response_time=search_response.get('response_time')
                )
            except Exception as e:
                logger.warning(f"无法规范化搜索响应为TavilyResponse对象: {str(e)}")
                logger.debug(f"原始响应类型: {type(search_response)}, 内容: {search_response}")
                return None
        
        # 其他类型，记录警告并返回None
        logger.warning(f"未知的搜索响应类型: {type(search_response)}")
        return None
    
    def _validate_and_filter_search_results(self, results: List[SearchResult], query: str) -> List[SearchResult]:
        """
        验证和过滤搜索结果，防止幻觉问题
        
        此方法实现了搜索结果验证机制，通过以下方式防止AI生成虚假引用：
        1. 验证URL有效性
        2. 检查内容相关性
        3. 过滤空结果和无效数据
        
        Args:
            results: 原始搜索结果列表
            query: 搜索查询，用于相关性验证
            
        Returns:
            验证和过滤后的搜索结果列表
        """
        if not results:
            return []
        
        validated_results = []
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        
        for result in results:
            # 跳过空结果
            if not result or not result.title:
                continue
            
            # 验证URL格式
            if result.url and not (result.url.startswith('http://') or result.url.startswith('https://')):
                logger.debug(f"跳过无效URL: {result.url}")
                continue
            
            # 基本相关性检查：至少包含一个查询关键词
            title_lower = result.title.lower()
            content_lower = (result.content or '').lower()
            
            # 检查标题或内容中是否包含查询关键词
            has_relevance = any(keyword in title_lower or keyword in content_lower 
                              for keyword in query_keywords if len(keyword) > 2)
            
            if has_relevance or len(query_keywords) == 0:
                validated_results.append(result)
            else:
                logger.debug(f"过滤低相关性结果: {result.title[:50]}...")
        
        return validated_results

    def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> TavilyResponse:
        """
        执行指定的搜索工具
        
        Args:
            tool_name: 工具名称，可选值：
                - "basic_search_news": 基础新闻搜索（快速、通用）
                - "deep_search_news": 深度新闻分析
                - "search_news_last_24_hours": 24小时内最新新闻
                - "search_news_last_week": 本周新闻
                - "search_images_for_news": 新闻图片搜索
                - "search_news_by_date": 按日期范围搜索新闻
            query: 搜索查询
            **kwargs: 额外参数（如start_date, end_date, max_results）
            
        Returns:
            TavilyResponse对象
        """
        logger.info(f"  → 执行搜索工具: {tool_name}")
        
        if tool_name == "basic_search_news":
            max_results = kwargs.get("max_results", 7)
            return self.search_agency.basic_search_news(query, max_results)
        elif tool_name == "deep_search_news":
            return self.search_agency.deep_search_news(query)
        elif tool_name == "search_news_last_24_hours":
            return self.search_agency.search_news_last_24_hours(query)
        elif tool_name == "search_news_last_week":
            return self.search_agency.search_news_last_week(query)
        elif tool_name == "search_images_for_news":
            return self.search_agency.search_images_for_news(query)
        elif tool_name == "search_news_by_date":
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            if not start_date or not end_date:
                raise ValueError("search_news_by_date工具需要start_date和end_date参数")
            return self.search_agency.search_news_by_date(query, start_date, end_date)
        else:
            logger.warning(f"  ⚠️  未知的搜索工具: {tool_name}，使用默认基础搜索")
            return self.search_agency.basic_search_news(query)
    
    def research(self, query: str, save_report: bool = True) -> str:
        """
        执行深度研究
        
        Args:
            query: 研究查询
            save_report: 是否保存报告到文件
            
        Returns:
            最终报告内容
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"开始深度研究: {query}")
        logger.info(f"{'='*60}")
        
        try:
            # Step 1: 生成报告结构
            self._generate_report_structure(query)
            
            # Step 2: 处理每个段落
            self._process_paragraphs()
            
            # Step 3: 生成最终报告
            final_report = self._generate_final_report()
            
            # Step 4: 保存报告
            if save_report:
                self._save_report(final_report)
            
            logger.info(f"\n{'='*60}")
            logger.info("深度研究完成！")
            logger.info(f"{'='*60}")
            
            return final_report
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"研究过程中发生错误: {str(e)} \n错误堆栈: {error_traceback}")
            raise e
    
    def _generate_report_structure(self, query: str):
        """生成报告结构"""
        logger.info(f"\n[步骤 1] 生成报告结构...")
        
        # 创建报告结构节点
        report_structure_node = ReportStructureNode(self.llm_client, query)
        
        # 生成结构并更新状态
        self.state = report_structure_node.mutate_state(state=self.state)
        
        _message = f"报告结构已生成，共 {len(self.state.paragraphs)} 个段落:"
        for i, paragraph in enumerate(self.state.paragraphs, 1):
            _message += f"\n  {i}. {paragraph.title}"
        logger.info(_message)
    
    def _process_paragraphs(self):
        """处理所有段落"""
        total_paragraphs = len(self.state.paragraphs)
        
        for i in range(total_paragraphs):
            logger.info(f"\n[步骤 2.{i+1}] 处理段落: {self.state.paragraphs[i].title}")
            logger.info("-" * 50)
            
            # 初始搜索和总结
            self._initial_search_and_summary(i)
            
            # 反思循环
            self._reflection_loop(i)
            
            # 标记段落完成
            self.state.paragraphs[i].research.mark_completed()
            
            progress = (i + 1) / total_paragraphs * 100
            logger.info(f"段落处理完成 ({progress:.1f}%)")
    
    def _initial_search_and_summary(self, paragraph_index: int):
        """执行初始搜索和总结"""
        paragraph = self.state.paragraphs[paragraph_index]
        
        # 准备搜索输入
        search_input = {
            "title": paragraph.title,
            "content": paragraph.content
        }
        
        # 生成搜索查询和工具选择
        logger.info("  - 生成搜索查询...")
        search_output = self.first_search_node.run(search_input)
        search_query = search_output["search_query"]
        search_tool = search_output.get("search_tool", "basic_search_news")  # 默认工具
        reasoning = search_output["reasoning"]
        
        logger.info(f"  - 搜索查询: {search_query}")
        logger.info(f"  - 选择的工具: {search_tool}")
        logger.info(f"  - 推理: {reasoning}")
        
        # 执行搜索
        logger.info("  - 执行网络搜索...")
        
        # 处理search_news_by_date的特殊参数
        search_kwargs = {}
        if search_tool == "search_news_by_date":
            start_date = search_output.get("start_date")
            end_date = search_output.get("end_date")
            
            if start_date and end_date:
                # 验证日期格式
                if self._validate_date_format(start_date) and self._validate_date_format(end_date):
                    search_kwargs["start_date"] = start_date
                    search_kwargs["end_date"] = end_date
                    logger.info(f"  - 时间范围: {start_date} 到 {end_date}")
                else:
                    logger.info(f"  ⚠️  日期格式错误（应为YYYY-MM-DD），改用基础搜索")
                    logger.info(f"      提供的日期: start_date={start_date}, end_date={end_date}")
                    search_tool = "basic_search_news"
            else:
                logger.info(f"  ⚠️  search_news_by_date工具缺少时间参数，改用基础搜索")
                search_tool = "basic_search_news"
        
        search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
        
        # 规范化搜索响应，处理dict类型返回值
        normalized_response = self._normalize_search_response(search_response)
        
        # 转换为兼容格式
        search_results = []
        if normalized_response and normalized_response.results:
            # 验证和过滤搜索结果，防止幻觉问题
            validated_results = self._validate_and_filter_search_results(
                normalized_response.results, search_query
            )
            
            # 每种搜索工具都有其特定的结果数量，这里取前10个作为上限
            max_results = min(len(validated_results), 10)
            for result in validated_results[:max_results]:
                search_results.append({
                    'title': result.title,
                    'url': result.url,
                    'content': result.content,
                    'score': result.score,
                    'raw_content': result.raw_content,
                    'published_date': result.published_date  # 新增字段
                })
        
        if search_results:
            _message = f"  - 找到 {len(search_results)} 个搜索结果"
            for j, result in enumerate(search_results, 1):
                date_info = f" (发布于: {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
                _message += f"\n    {j}. {result['title'][:50]}...{date_info}"
            logger.info(_message)
        else:
            logger.info("  - 未找到搜索结果")
        # 更新状态中的搜索历史
        paragraph.research.add_search_results(search_query, search_results)
        
        # 生成初始总结
        logger.info("  - 生成初始总结...")
        summary_input = {
            "title": paragraph.title,
            "content": paragraph.content,
            "search_query": search_query,
            "search_results": format_search_results_for_prompt(
                search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
            )
        }
        
        # 更新状态
        self.state = self.first_summary_node.mutate_state(
            summary_input, self.state, paragraph_index
        )
        
        logger.info("  - 初始总结完成")
    
    def _reflection_loop(self, paragraph_index: int):
        """执行反思循环"""
        paragraph = self.state.paragraphs[paragraph_index]
        
        for reflection_i in range(self.config.MAX_REFLECTIONS):
            logger.info(f"  - 反思 {reflection_i + 1}/{self.config.MAX_REFLECTIONS}...")
            
            # 准备反思输入
            reflection_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "paragraph_latest_state": paragraph.research.latest_summary
            }
            
            # 生成反思搜索查询
            reflection_output = self.reflection_node.run(reflection_input)
            search_query = reflection_output["search_query"]
            search_tool = reflection_output.get("search_tool", "basic_search_news")  # 默认工具
            reasoning = reflection_output["reasoning"]
            
            logger.info(f"    反思查询: {search_query}")
            logger.info(f"    选择的工具: {search_tool}")
            logger.info(f"    反思推理: {reasoning}")
            
            # 执行反思搜索
            # 处理search_news_by_date的特殊参数
            search_kwargs = {}
            if search_tool == "search_news_by_date":
                start_date = reflection_output.get("start_date")
                end_date = reflection_output.get("end_date")
                
                if start_date and end_date:
                    # 验证日期格式
                    if self._validate_date_format(start_date) and self._validate_date_format(end_date):
                        search_kwargs["start_date"] = start_date
                        search_kwargs["end_date"] = end_date
                        logger.info(f"    时间范围: {start_date} 到 {end_date}")
                    else:
                        logger.info(f"    ⚠️  日期格式错误（应为YYYY-MM-DD），改用基础搜索")
                        logger.info(f"        提供的日期: start_date={start_date}, end_date={end_date}")
                        search_tool = "basic_search_news"
                else:
                    logger.info(f"    ⚠️  search_news_by_date工具缺少时间参数，改用基础搜索")
                    search_tool = "basic_search_news"
            
            search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
            
            # 规范化搜索响应，处理dict类型返回值
            normalized_response = self._normalize_search_response(search_response)
            
            # 转换为兼容格式
            search_results = []
            if normalized_response and normalized_response.results:
                # 验证和过滤搜索结果，防止幻觉问题
                validated_results = self._validate_and_filter_search_results(
                    normalized_response.results, search_query
                )
                
                # 每种搜索工具都有其特定的结果数量，这里取前10个作为上限
                max_results = min(len(validated_results), 10)
                for result in validated_results[:max_results]:
                    search_results.append({
                        'title': result.title,
                        'url': result.url,
                        'content': result.content,
                        'score': result.score,
                        'raw_content': result.raw_content,
                        'published_date': result.published_date
                    })
            
            if search_results:
                logger.info(f"    找到 {len(search_results)} 个反思搜索结果")
                for j, result in enumerate(search_results, 1):
                    date_info = f" (发布于: {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
                    logger.info(f"      {j}. {result['title'][:50]}...{date_info}")
            else:
                logger.info("    未找到反思搜索结果")
            
            # 更新搜索历史
            paragraph.research.add_search_results(search_query, search_results)
            
            # 生成反思总结
            reflection_summary_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "search_query": search_query,
                "search_results": format_search_results_for_prompt(
                    search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
                ),
                "paragraph_latest_state": paragraph.research.latest_summary
            }
            
            # 更新状态
            self.state = self.reflection_summary_node.mutate_state(
                reflection_summary_input, self.state, paragraph_index
            )
            
            logger.info(f"    反思 {reflection_i + 1} 完成")
    
    def _generate_final_report(self) -> str:
        """生成最终报告"""
        logger.info(f"\n[步骤 3] 生成最终报告...")
        
        # 准备报告数据
        report_data = []
        for paragraph in self.state.paragraphs:
            report_data.append({
                "title": paragraph.title,
                "paragraph_latest_state": paragraph.research.latest_summary
            })
        
        # 格式化报告
        try:
            final_report = self.report_formatting_node.run(report_data)
        except Exception as e:
            logger.error(f"LLM格式化失败，使用备用方法: {str(e)}")
            final_report = self.report_formatting_node.format_report_manually(
                report_data, self.state.report_title
            )
        
        # 更新状态
        self.state.final_report = final_report
        self.state.mark_completed()
        
        logger.info("最终报告生成完成")
        return final_report
    
    def _save_report(self, report_content: str):
        """保存报告到文件"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(c for c in self.state.query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        query_safe = query_safe.replace(' ', '_')[:30]
        
        filename = f"deep_search_report_{query_safe}_{timestamp}.md"
        filepath = os.path.join(self.config.OUTPUT_DIR, filename)
        
        # 保存报告
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"报告已保存到: {filepath}")
        
        # 保存状态（如果配置允许）
        if self.config.SAVE_INTERMEDIATE_STATES:
            state_filename = f"state_{query_safe}_{timestamp}.json"
            state_filepath = os.path.join(self.config.OUTPUT_DIR, state_filename)
            self.state.save_to_file(state_filepath)
            logger.info(f"状态已保存到: {state_filepath}")
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return self.state.get_progress_summary()
    
    def load_state(self, filepath: str):
        """从文件加载状态"""
        self.state = State.load_from_file(filepath)
        logger.info(f"状态已从 {filepath} 加载")
    
    def save_state(self, filepath: str):
        """保存状态到文件"""
        self.state.save_to_file(filepath)
        logger.info(f"状态已保存到 {filepath}")


def create_agent() -> DeepSearchAgent:
    """
    创建Deep Search Agent实例的便捷函数
    
    Returns:
        DeepSearchAgent实例
    """
    from .utils.config import Settings
    config = Settings()
    return DeepSearchAgent(config)
