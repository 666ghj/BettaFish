"""
Report Agent主类
整合所有模块，实现完整的报告生成流程
"""

import json
import os
from loguru import logger
from datetime import datetime
from typing import Optional, Dict, Any, List

from .llms import LLMClient
from .nodes import (
    TemplateSelectionNode,
    HTMLGenerationNode
)
from .state import ReportState
from .utils.config import settings, Settings


class FileCountBaseline:
    """文件数量基准管理器"""
    
    def __init__(self):
        self.baseline_file = 'logs/report_baseline.json'
        self.baseline_data = self._load_baseline()
    
    def _load_baseline(self) -> Dict[str, int]:
        """加载基准数据"""
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.exception(f"加载基准数据失败: {e}")
        return {}
    
    def _save_baseline(self):
        """保存基准数据"""
        try:
            os.makedirs(os.path.dirname(self.baseline_file), exist_ok=True)
            with open(self.baseline_file, 'w', encoding='utf-8') as f:
                json.dump(self.baseline_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception(f"保存基准数据失败: {e}")
    
    def initialize_baseline(self, directories: Dict[str, str]) -> Dict[str, int]:
        """初始化文件数量基准"""
        current_counts = {}
        
        for engine, directory in directories.items():
            if os.path.exists(directory):
                md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
                current_counts[engine] = len(md_files)
            else:
                current_counts[engine] = 0
        
        # 保存基准数据
        self.baseline_data = current_counts.copy()
        self._save_baseline()
        
        logger.info(f"文件数量基准已初始化: {current_counts}")
        return current_counts
    
    def check_new_files(self, directories: Dict[str, str]) -> Dict[str, Any]:
        """检查是否有新文件"""
        current_counts = {}
        new_files_found = {}
        all_have_new = True
        
        for engine, directory in directories.items():
            if os.path.exists(directory):
                md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
                current_counts[engine] = len(md_files)
                baseline_count = self.baseline_data.get(engine, 0)
                
                if current_counts[engine] > baseline_count:
                    new_files_found[engine] = current_counts[engine] - baseline_count
                else:
                    new_files_found[engine] = 0
                    all_have_new = False
            else:
                current_counts[engine] = 0
                new_files_found[engine] = 0
                all_have_new = False
        
        return {
            'ready': all_have_new,
            'baseline_counts': self.baseline_data,
            'current_counts': current_counts,
            'new_files_found': new_files_found,
            'missing_engines': [engine for engine, count in new_files_found.items() if count == 0]
        }
    
    def get_latest_files(self, directories: Dict[str, str]) -> Dict[str, str]:
        """获取每个目录的最新文件"""
        latest_files = {}
        
        for engine, directory in directories.items():
            if os.path.exists(directory):
                md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
                if md_files:
                    latest_file = max(md_files, key=lambda x: os.path.getmtime(os.path.join(directory, x)))
                    latest_files[engine] = os.path.join(directory, latest_file)
        
        return latest_files


class ReportAgent:
    """Report Agent主类"""
    
    def __init__(self, config: Optional[Settings] = None):
        """
        初始化Report Agent
        
        Args:
            config: 配置对象，如果不提供则自动加载
        """
        # 加载配置
        self.config = config or settings
        
        # 初始化文件基准管理器
        self.file_baseline = FileCountBaseline()
        
        # 初始化日志
        self._setup_logging()
        
        # 初始化LLM客户端
        self.llm_client = self._initialize_llm()
        
        # 初始化节点
        self._initialize_nodes()
        
        # 初始化文件数量基准
        self._initialize_file_baseline()
        
        # 状态
        self.state = ReportState()
        
        # 确保输出目录存在
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        logger.info("Report Agent已初始化")
        logger.info(f"使用LLM: {self.llm_client.get_model_info()}")
        
    def _setup_logging(self):
        """设置日志"""
        # 确保日志目录存在
        log_dir = os.path.dirname(self.config.LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建专用的logger，避免与其他模块冲突
        logger.add(self.config.LOG_FILE, level="INFO")
        
    def _initialize_file_baseline(self):
        """初始化文件数量基准"""
        directories = {
            'insight': 'insight_engine_streamlit_reports',
            'media': 'media_engine_streamlit_reports',
            'query': 'query_engine_streamlit_reports'
        }
        self.file_baseline.initialize_baseline(directories)
    
    def _initialize_llm(self) -> LLMClient:
        """初始化LLM客户端"""
        return LLMClient(
            api_key=self.config.REPORT_ENGINE_API_KEY,
            model_name=self.config.REPORT_ENGINE_MODEL_NAME,
            base_url=self.config.REPORT_ENGINE_BASE_URL,
        )
    
    def _initialize_nodes(self):
        """初始化处理节点"""
        self.template_selection_node = TemplateSelectionNode(
            self.llm_client,
            self.config.TEMPLATE_DIR
        )
        self.html_generation_node = HTMLGenerationNode(self.llm_client)
    
    def generate_report(self, query: str, reports: List[Any], forum_logs: str = "", 
                       custom_template: str = "", save_report: bool = True) -> str:
        """
        生成综合报告
        
        Args:
            query: 原始查询
            reports: 三个子agent的报告列表（按顺序：QueryEngine, MediaEngine, InsightEngine）
            forum_logs: 论坛日志内容
            custom_template: 用户自定义模板（可选）
            save_report: 是否保存报告到文件
            
        Returns:
            dict: 包含HTML内容与保存文件信息
        """
        start_time = datetime.now()
        
        # 为新的查询重置状态，确保文件命名信息完整
        self.state = ReportState(query=query)
        self.state.metadata.query = query
        self.state.query = query
        self.state.mark_processing()
        
        logger.info(f"开始生成报告: {query}")
        logger.info(f"输入数据 - 报告数量: {len(reports)}, 论坛日志长度: {len(forum_logs)}")
        
        try:
            # Step 1: 模板选择
            template_result = self._select_template(query, reports, forum_logs, custom_template)
            
            # Step 2: 直接生成HTML报告
            html_report = self._generate_html_report(query, reports, forum_logs, template_result)
            
            # Step 3: 保存报告
            saved_files = {}
            if save_report:
                saved_files = self._save_report(html_report)
            
            # 更新生成时间
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            self.state.metadata.generation_time = generation_time
            
            logger.info(f"报告生成完成，耗时: {generation_time:.2f} 秒")
            
            return {
                'html_content': html_report,
                **saved_files
            }
            
        except Exception as e:
            logger.exception(f"报告生成过程中发生错误: {str(e)}")
            raise e
    
    def _select_template(self, query: str, reports: List[Any], forum_logs: str, custom_template: str):
        """选择报告模板"""
        logger.info("选择报告模板...")
        
        # 如果用户提供了自定义模板，直接使用
        if custom_template:
            logger.info("使用用户自定义模板")
            return {
                'template_name': 'custom',
                'template_content': custom_template,
                'selection_reason': '用户指定的自定义模板'
            }
        
        template_input = {
            'query': query,
            'reports': reports,
            'forum_logs': forum_logs
        }
        
        try:
            template_result = self.template_selection_node.run(template_input)
            
            # 更新状态
            self.state.metadata.template_used = template_result['template_name']
            
            logger.info(f"选择模板: {template_result['template_name']}")
            logger.info(f"选择理由: {template_result['selection_reason']}")
            
            return template_result
        except Exception as e:
            logger.error(f"模板选择失败，使用默认模板: {str(e)}")
            # 直接使用备用模板
            fallback_template = {
                'template_name': '社会公共热点事件分析报告模板',
                'template_content': self._get_fallback_template_content(),
                'selection_reason': '模板选择失败，使用默认社会热点事件分析模板'
            }
            self.state.metadata.template_used = fallback_template['template_name']
            return fallback_template
    
    def _generate_html_report(self, query: str, reports: List[Any], forum_logs: str, template_result: Dict[str, Any]) -> str:
        """生成HTML报告"""
        logger.info("多轮生成HTML报告...")
        
        # 准备报告内容，确保有3个报告
        query_report = reports[0] if len(reports) > 0 else ""
        media_report = reports[1] if len(reports) > 1 else ""
        insight_report = reports[2] if len(reports) > 2 else ""
        
        # 转换为字符串格式
        query_report = str(query_report) if query_report else ""
        media_report = str(media_report) if media_report else ""
        insight_report = str(insight_report) if insight_report else ""
        
        html_input = {
            'query': query,
            'query_engine_report': query_report,
            'media_engine_report': media_report,
            'insight_engine_report': insight_report,
            'forum_logs': forum_logs,
            'selected_template': template_result.get('template_content', '')
        }
        
        # 使用HTML生成节点生成报告
        html_content = self.html_generation_node.run(html_input)
        
        # 更新状态
        self.state.html_content = html_content
        self.state.mark_completed()
        
        logger.info("HTML报告生成完成")
        return html_content
    
    def _get_fallback_template_content(self) -> str:
        """获取备用模板内容"""
        return """# 社会公共热点事件分析报告

## 执行摘要
本报告针对当前社会热点事件进行综合分析，整合了多方信息源的观点和数据。

## 事件概况
### 基本信息
- 事件性质：{event_nature}
- 发生时间：{event_time}
- 涉及范围：{event_scope}

## 舆情态势分析
### 整体趋势
{sentiment_analysis}

### 主要观点分布
{opinion_distribution}

## 媒体报道分析
### 主流媒体态度
{media_analysis}

### 报道重点
{report_focus}

## 社会影响评估
### 直接影响
{direct_impact}

### 潜在影响
{potential_impact}

## 应对建议
### 即时措施
{immediate_actions}

### 长期策略
{long_term_strategy}

## 结论与展望
{conclusion}

---
*报告类型：社会公共热点事件分析*
*生成时间：{generation_time}*
"""
    
    def _save_report(self, html_content: str):
        """保存报告到文件"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(c for c in self.state.metadata.query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        query_safe = query_safe.replace(' ', '_')[:30]
        
        filename = f"final_report_{query_safe}_{timestamp}.html"
        filepath = os.path.join(self.config.OUTPUT_DIR, filename)
        
        # 保存HTML报告
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        abs_report_path = os.path.abspath(filepath)
        rel_report_path = os.path.relpath(abs_report_path, os.getcwd())
        logger.info(f"报告已保存到: {abs_report_path}")
        
        # 保存状态
        state_filename = f"report_state_{query_safe}_{timestamp}.json"
        state_filepath = os.path.join(self.config.OUTPUT_DIR, state_filename)
        self.state.save_to_file(state_filepath)
        abs_state_path = os.path.abspath(state_filepath)
        rel_state_path = os.path.relpath(abs_state_path, os.getcwd())
        logger.info(f"状态已保存到: {abs_state_path}")
        
        return {
            'report_filename': filename,
            'report_filepath': abs_report_path,
            'report_relative_path': rel_report_path,
            'state_filename': state_filename,
            'state_filepath': abs_state_path,
            'state_relative_path': rel_state_path
        }
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return self.state.to_dict()
    
    def load_state(self, filepath: str):
        """从文件加载状态"""
        self.state = ReportState.load_from_file(filepath)
        logger.info(f"状态已从 {filepath} 加载")
    
    def save_state(self, filepath: str):
        """保存状态到文件"""
        self.state.save_to_file(filepath)
        logger.info(f"状态已保存到 {filepath}")
    
    def check_input_files(self, insight_dir: str, media_dir: str, query_dir: str, forum_log_path: str) -> Dict[str, Any]:
        """
        检查输入文件是否准备就绪（基于文件数量增加）
        
        Args:
            insight_dir: InsightEngine报告目录
            media_dir: MediaEngine报告目录
            query_dir: QueryEngine报告目录
            forum_log_path: 论坛日志文件路径
            
        Returns:
            检查结果字典
        """
        # 检查各个报告目录的文件数量变化
        directories = {
            'insight': insight_dir,
            'media': media_dir,
            'query': query_dir
        }
        
        # 使用文件基准管理器检查新文件
        check_result = self.file_baseline.check_new_files(directories)
        
        # 检查论坛日志
        forum_ready = os.path.exists(forum_log_path)
        
        # 构建返回结果
        result = {
            'ready': check_result['ready'] and forum_ready,
            'baseline_counts': check_result['baseline_counts'],
            'current_counts': check_result['current_counts'],
            'new_files_found': check_result['new_files_found'],
            'missing_files': [],
            'files_found': [],
            'latest_files': {}
        }
        
        # 构建详细信息
        for engine, new_count in check_result['new_files_found'].items():
            current_count = check_result['current_counts'][engine]
            baseline_count = check_result['baseline_counts'].get(engine, 0)
            
            if new_count > 0:
                result['files_found'].append(f"{engine}: {current_count}个文件 (新增{new_count}个)")
            else:
                result['missing_files'].append(f"{engine}: {current_count}个文件 (基准{baseline_count}个，无新增)")
        
        # 检查论坛日志
        if forum_ready:
            result['files_found'].append(f"forum: {os.path.basename(forum_log_path)}")
        else:
            result['missing_files'].append("forum: 日志文件不存在")
        
        # 获取最新文件路径（用于实际报告生成）
        if result['ready']:
            result['latest_files'] = self.file_baseline.get_latest_files(directories)
            if forum_ready:
                result['latest_files']['forum'] = forum_log_path
        
        return result
    
    def load_input_files(self, file_paths: Dict[str, str]) -> Dict[str, Any]:
        """
        加载输入文件内容
        
        Args:
            file_paths: 文件路径字典
            
        Returns:
            加载的内容字典
        """
        content = {
            'reports': [],
            'forum_logs': ''
        }
        
        # 加载报告文件
        engines = ['query', 'media', 'insight']
        for engine in engines:
            if engine in file_paths:
                try:
                    with open(file_paths[engine], 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    content['reports'].append(report_content)
                    logger.info(f"已加载 {engine} 报告: {len(report_content)} 字符")
                except Exception as e:
                    logger.exception(f"加载 {engine} 报告失败: {str(e)}")
                    content['reports'].append("")
        
        # 加载论坛日志
        if 'forum' in file_paths:
            try:
                with open(file_paths['forum'], 'r', encoding='utf-8') as f:
                    content['forum_logs'] = f.read()
                logger.info(f"已加载论坛日志: {len(content['forum_logs'])} 字符")
            except Exception as e:
                logger.exception(f"加载论坛日志失败: {str(e)}")
        
        return content


def create_agent(config_file: Optional[str] = None) -> ReportAgent:
    """
    创建Report Agent实例的便捷函数
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        ReportAgent实例
    """
    
    config = Settings() # 以空配置初始化，而从从环境变量初始化
    return ReportAgent(config)
