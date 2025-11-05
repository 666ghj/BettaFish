"""
HTML生成节点
将整合后的内容转换为美观的HTML报告
"""

import json
from datetime import datetime
from typing import Dict, Any
from loguru import logger

from .base_node import StateMutationNode
from ..llms.base import LLMClient
from ..state.state import ReportState
from ..prompts import SYSTEM_PROMPT_HTML_GENERATION
# 不再需要text_processing依赖


class HTMLGenerationNode(StateMutationNode):
    """HTML生成处理节点"""
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化HTML生成节点
        
        Args:
            llm_client: LLM客户端
        """
        super().__init__(llm_client, "HTMLGenerationNode")
    
    def run(self, input_data: Dict[str, Any], **kwargs) -> str:
        """
        执行HTML生成
        
        Args:
            input_data: 包含报告数据的字典
                - query: 原始查询
                - query_engine_report: QueryEngine报告内容
                - media_engine_report: MediaEngine报告内容  
                - insight_engine_report: InsightEngine报告内容
                - forum_logs: 论坛日志内容
                - selected_template: 选择的模板内容
                
        Returns:
            生成的HTML内容
        """
        logger.info("开始生成HTML报告...")
        
        try:
            # 准备LLM输入数据
            llm_input = {
                "query": input_data.get('query', ''),
                "query_engine_report": input_data.get('query_engine_report', ''),
                "media_engine_report": input_data.get('media_engine_report', ''),
                "insight_engine_report": input_data.get('insight_engine_report', ''),
                "forum_logs": input_data.get('forum_logs', ''),
                "selected_template": input_data.get('selected_template', '')
            }
            
            # 转换为JSON格式传递给LLM
            message = json.dumps(llm_input, ensure_ascii=False, indent=2)
            
            # 调用LLM生成HTML
            response = self.llm_client.invoke(SYSTEM_PROMPT_HTML_GENERATION, message)
            
            # 处理响应（简化版）
            processed_response = self.process_output(response)
            
            logger.info("HTML报告生成完成")
            return processed_response
            
        except Exception as e:
            logger.exception(f"HTML生成失败: {str(e)}")
            # 返回备用HTML
            return self._generate_fallback_html(input_data)
    
    def mutate_state(self, input_data: Dict[str, Any], state: ReportState, **kwargs) -> ReportState:
        """
        修改报告状态，添加生成的HTML内容
        
        Args:
            input_data: 输入数据
            state: 当前报告状态
            **kwargs: 额外参数
            
        Returns:
            更新后的报告状态
        """
        # 生成HTML
        html_content = self.run(input_data, **kwargs)
        
        # 更新状态
        state.html_content = html_content
        state.mark_completed()
        
        return state
    
    def process_output(self, output: str) -> str:
        """
        处理LLM输出，提取HTML内容
        
        Args:
            output: LLM原始输出
            
        Returns:
            HTML内容
        """
        try:
            logger.info(f"处理LLM原始输出，长度: {len(output)} 字符")
            
            html_content = output.strip()
            
            # 清理markdown代码块标记（如果存在）
            if html_content.startswith('```html'):
                html_content = html_content[7:]  # 移除 '```html'
                if html_content.endswith('```'):
                    html_content = html_content[:-3]  # 移除结尾的 '```'
            elif html_content.startswith('```') and html_content.endswith('```'):
                html_content = html_content[3:-3]  # 移除前后的 '```'
            
            html_content = html_content.strip()
            
            # 如果内容为空，返回原始输出
            if not html_content:
                logger.info("处理后内容为空，返回原始输出")
                html_content = output
            
            logger.info(f"HTML处理完成，最终长度: {len(html_content)} 字符")
            return html_content
            
        except Exception as e:
            logger.exception(f"处理HTML输出失败: {str(e)}，返回原始输出")
            return output
    
    def _generate_fallback_html(self, input_data: Dict[str, Any]) -> str:
        """
        生成备用HTML报告（当LLM失败时使用）
        
        Args:
            input_data: 输入数据
            
        Returns:
            备用HTML内容
        """
        logger.info("使用备用HTML生成方法")
        
        query = input_data.get('query', '智能舆情分析报告')
        query_report = input_data.get('query_engine_report', '')
        media_report = input_data.get('media_engine_report', '')
        insight_report = input_data.get('insight_engine_report', '')
        forum_logs = input_data.get('forum_logs', '')
        
        generation_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{query} - 智能舆情分析报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .section {{
            margin-bottom: 30px;
            padding: 20px;
            border-left: 4px solid #3498db;
            background: #f8f9fa;
        }}
        .meta {{
            background: #e9ecef;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
            color: #666;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{query}</h1>
        
        <div class="meta">
            <strong>报告生成时间:</strong> {generation_time}<br>
            <strong>数据来源:</strong> QueryEngine、MediaEngine、InsightEngine、ForumEngine<br>
            <strong>报告类型:</strong> 综合舆情分析报告
        </div>
        
        <h2>执行摘要</h2>
        <div class="section">
            本报告整合了多个分析引擎的研究结果，为您提供全面的舆情分析洞察。
            通过对查询主题"{query}"的深度分析，我们从多个维度展现了当前的舆情态势。
        </div>
        
        {f'<h2>QueryEngine分析结果</h2><div class="section"><pre>{query_report}</pre></div>' if query_report else ''}
        
        {f'<h2>MediaEngine分析结果</h2><div class="section"><pre>{media_report}</pre></div>' if media_report else ''}
        
        {f'<h2>InsightEngine分析结果</h2><div class="section"><pre>{insight_report}</pre></div>' if insight_report else ''}
        
        {f'<h2>论坛监控数据</h2><div class="section"><pre>{forum_logs}</pre></div>' if forum_logs else ''}
        
        <h2>综合结论</h2>
        <div class="section">
            基于多个分析引擎的综合研究，我们对"{query}"主题进行了全面分析。
            各引擎从不同角度提供了深入洞察，为决策提供了重要参考。
        </div>
        
        <div class="footer">
            <p>本报告由智能舆情分析平台自动生成</p>
            <p>ReportEngine v1.0 | 生成时间: {generation_time}</p>
        </div>
    </div>
</body>
</html>"""
        
        return html_content
    

