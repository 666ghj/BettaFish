"""
模板选择节点
根据查询内容和可用模板选择最合适的报告模板
"""

import os
import json
from typing import Dict, Any, List, Optional
from loguru import logger

from .base_node import BaseNode
from ..prompts import SYSTEM_PROMPT_TEMPLATE_SELECTION


class TemplateSelectionNode(BaseNode):
    """模板选择处理节点"""
    
    def __init__(self, llm_client, template_dir: str = "ReportEngine/report_template"):
        """
        初始化模板选择节点
        
        Args:
            llm_client: LLM客户端
            template_dir: 模板目录路径
        """
        super().__init__(llm_client, "TemplateSelectionNode")
        self.template_dir = template_dir
        
    def run(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行模板选择
        
        Args:
            input_data: 包含查询和报告内容的字典
                - query: 原始查询
                - reports: 三个子agent的报告列表
                - forum_logs: 论坛日志内容
                
        Returns:
            选择的模板信息
        """
        logger.info("开始模板选择...")
        
        query = input_data.get('query', '')
        reports = input_data.get('reports', [])
        forum_logs = input_data.get('forum_logs', '')
        
        # 获取可用模板
        available_templates = self._get_available_templates()
        
        if not available_templates:
            logger.info("未找到预设模板，使用内置默认模板")
            return self._get_fallback_template()
        
        # 使用LLM进行模板选择
        try:
            llm_result = self._llm_template_selection(query, reports, forum_logs, available_templates)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.exception(f"LLM模板选择失败: {str(e)}")
        
        # 如果LLM选择失败，使用备选方案
        return self._get_fallback_template()
    

    
    def _llm_template_selection(self, query: str, reports: List[Any], forum_logs: str, 
                              available_templates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """使用LLM进行模板选择"""
        logger.info("尝试使用LLM进行模板选择...")
        
        # 构建模板列表
        template_list = "\n".join([f"- {t['name']}: {t['description']}" for t in available_templates])
        
        # 构建报告内容摘要
        reports_summary = ""
        if reports:
            reports_summary = "\n\n=== 分析引擎报告内容 ===\n"
            for i, report in enumerate(reports, 1):
                # 获取报告内容，支持不同的数据格式
                if isinstance(report, dict):
                    content = report.get('content', str(report))
                elif hasattr(report, 'content'):
                    content = report.content
                else:
                    content = str(report)
                
                # 截断过长的内容，保留前1000个字符
                if len(content) > 1000:
                    content = content[:1000] + "...(内容已截断)"
                
                reports_summary += f"\n报告{i}内容:\n{content}\n"
        
        # 构建论坛日志摘要
        forum_summary = ""
        if forum_logs and forum_logs.strip():
            forum_summary = "\n\n=== 三个引擎的讨论内容 ===\n"
            # 截断过长的日志内容，保留前800个字符
            if len(forum_logs) > 800:
                forum_content = forum_logs[:800] + "...(讨论内容已截断)"
            else:
                forum_content = forum_logs
            forum_summary += forum_content
        
        user_message = f"""查询内容: {query}

报告数量: {len(reports)} 个分析引擎报告
论坛日志: {'有' if forum_logs else '无'}
{reports_summary}{forum_summary}

可用模板:
{template_list}

请根据查询内容、报告内容和论坛日志的具体情况，选择最合适的模板。"""
        
        # 调用LLM
        response = self.llm_client.invoke(SYSTEM_PROMPT_TEMPLATE_SELECTION, user_message)
        
        # 检查响应是否为空
        if not response or not response.strip():
            logger.error("LLM返回空响应")
            return None
        
        logger.info(f"LLM原始响应: {response}")
        
        # 尝试解析JSON响应
        try:
            # 清理响应文本
            cleaned_response = self._clean_llm_response(response)
            result = json.loads(cleaned_response)
            
            # 验证选择的模板是否存在
            selected_template_name = result.get('template_name', '')
            for template in available_templates:
                if template['name'] == selected_template_name or selected_template_name in template['name']:
                    logger.info(f"LLM选择模板: {selected_template_name}")
                    return {
                        'template_name': template['name'],
                        'template_content': template['content'],
                        'selection_reason': result.get('selection_reason', 'LLM智能选择')
                    }
            
            logger.error(f"LLM选择的模板不存在: {selected_template_name}")
            return None
            
        except json.JSONDecodeError as e:
            logger.exception(f"JSON解析失败: {str(e)}")
            # 尝试从文本响应中提取模板信息
            return self._extract_template_from_text(response, available_templates)
    
    def _clean_llm_response(self, response: str) -> str:
        """清理LLM响应"""
        # 移除可能的markdown代码块标记
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        
        # 移除前后空白
        response = response.strip()
        
        return response
    
    def _extract_template_from_text(self, response: str, available_templates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """从文本响应中提取模板信息"""
        logger.info("尝试从文本响应中提取模板信息")
        
        # 查找响应中是否包含模板名称
        for template in available_templates:
            template_name_variants = [
                template['name'],
                template['name'].replace('.md', ''),
                template['name'].replace('模板', ''),
            ]
            
            for variant in template_name_variants:
                if variant in response:
                    logger.info(f"在响应中找到模板: {template['name']}")
                    return {
                        'template_name': template['name'],
                        'template_content': template['content'],
                        'selection_reason': '从文本响应中提取'
                    }
        
        return None
    
    def _get_available_templates(self) -> List[Dict[str, Any]]:
        """获取可用的模板列表"""
        templates = []
        
        if not os.path.exists(self.template_dir):
            logger.error(f"模板目录不存在: {self.template_dir}")
            return templates
        
        # 查找所有markdown模板文件
        for filename in os.listdir(self.template_dir):
            if filename.endswith('.md'):
                template_path = os.path.join(self.template_dir, filename)
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    template_name = filename.replace('.md', '')
                    description = self._extract_template_description(template_name)
                    
                    templates.append({
                        'name': template_name,
                        'path': template_path,
                        'content': content,
                        'description': description
                    })
                except Exception as e:
                    logger.exception(f"读取模板文件失败 {filename}: {str(e)}")
        
        return templates
    
    def _extract_template_description(self, template_name: str) -> str:
        """根据模板名称生成描述"""
        if '企业品牌' in template_name:
            return "适用于企业品牌声誉和形象分析"
        elif '市场竞争' in template_name:
            return "适用于市场竞争格局和对手分析"
        elif '日常' in template_name or '定期' in template_name:
            return "适用于日常监测和定期汇报"
        elif '政策' in template_name or '行业' in template_name:
            return "适用于政策影响和行业动态分析"
        elif '热点' in template_name or '社会' in template_name:
            return "适用于社会热点和公共事件分析"
        elif '突发' in template_name or '危机' in template_name:
            return "适用于突发事件和危机公关"
        
        return "通用报告模板"
    

    
    def _get_fallback_template(self) -> Dict[str, Any]:
        """获取备用默认模板（空模板，让LLM自行发挥）"""
        logger.info("未找到合适模板，使用空模板让LLM自行发挥")
        
        return {
            'template_name': '自由发挥模板',
            'template_content': '',
            'selection_reason': '未找到合适的预设模板，让LLM根据内容自行设计报告结构'
        }
