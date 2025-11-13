"""
Report Agent主类
整合所有模块，实现完整的报告生成流程
"""

import json
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import Optional, Dict, Any, List

from loguru import logger

from .core import (
    ChapterStorage,
    DocumentComposer,
    TemplateSection,
    parse_template_sections,
)
from .ir import IRValidator
from .llms import LLMClient
from .nodes import (
    TemplateSelectionNode,
    ChapterGenerationNode,
    DocumentLayoutNode,
    WordBudgetNode,
)
from .renderers import HTMLRenderer
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
        
        # 初始化章级存储/校验/渲染组件
        self.chapter_storage = ChapterStorage(self.config.CHAPTER_OUTPUT_DIR)
        self.document_composer = DocumentComposer()
        self.validator = IRValidator()
        self.renderer = HTMLRenderer()
        
        # 初始化节点
        self._initialize_nodes()
        
        # 初始化文件数量基准
        self._initialize_file_baseline()
        
        # 状态
        self.state = ReportState()
        
        # 确保输出目录存在
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.config.DOCUMENT_IR_OUTPUT_DIR, exist_ok=True)
        
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
        self.document_layout_node = DocumentLayoutNode(self.llm_client)
        self.word_budget_node = WordBudgetNode(self.llm_client)
        self.chapter_generation_node = ChapterGenerationNode(
            self.llm_client,
            self.validator,
            self.chapter_storage
        )
    
    def generate_report(self, query: str, reports: List[Any], forum_logs: str = "",
                        custom_template: str = "", save_report: bool = True) -> str:
        """
        生成综合报告（章节JSON → IR → HTML）
        
        Returns:
            dict: HTML内容以及保存的文件路径信息
        """
        start_time = datetime.now()
        report_id = f"report-{uuid4().hex[:8]}"
        self.state.task_id = report_id
        self.state.query = query
        self.state.metadata.query = query
        self.state.mark_processing()

        normalized_reports = self._normalize_reports(reports)
        logger.info(f"开始生成报告 {report_id}: {query}")
        logger.info(f"输入数据 - 报告数量: {len(reports)}, 论坛日志长度: {len(str(forum_logs))}")

        try:
            template_result = self._select_template(query, reports, forum_logs, custom_template)
            self.state.metadata.template_used = template_result.get('template_name', '')
            sections = self._slice_template(template_result.get('template_content', ''))
            if not sections:
                raise ValueError("模板无法解析出章节，请检查模板内容。")

            template_text = template_result.get('template_content', '')
            template_overview = self._build_template_overview(template_text, sections)
            # 基于模板骨架+三引擎内容设计全局标题、目录与视觉主题
            layout_design = self.document_layout_node.run(
                sections,
                template_text,
                normalized_reports,
                forum_logs,
                query,
                template_overview,
            )
            # 使用刚生成的设计稿对全书进行篇幅规划，约束各章字数与重点
            word_plan = self.word_budget_node.run(
                sections,
                layout_design,
                normalized_reports,
                forum_logs,
                query,
                template_overview,
            )
            # 记录每个章节的目标字数/强调点，后续传给章节LLM
            chapter_targets = {
                entry.get("chapterId"): entry
                for entry in word_plan.get("chapters", [])
                if entry.get("chapterId")
            }

            generation_context = self._build_generation_context(
                query,
                normalized_reports,
                forum_logs,
                template_result,
                layout_design,
                chapter_targets,
                word_plan,
                template_overview,
            )
            # IR/渲染需要的全局元数据，带上设计稿给出的标题/主题/目录/篇幅信息
            manifest_meta = {
                "query": query,
                "title": layout_design.get("title") or (f"{query} - 舆情洞察报告" if query else template_result.get("template_name")),
                "subtitle": layout_design.get("subtitle"),
                "tagline": layout_design.get("tagline"),
                "templateName": template_result.get("template_name"),
                "selectionReason": template_result.get("selection_reason"),
                "themeTokens": generation_context.get("theme_tokens", {}),
                "toc": {
                    "depth": 3,
                    "autoNumbering": True,
                    "title": layout_design.get("tocTitle") or "目录",
                },
                "hero": layout_design.get("hero"),
                "layoutNotes": layout_design.get("layoutNotes"),
                "wordPlan": {
                    "totalWords": word_plan.get("totalWords"),
                    "globalGuidelines": word_plan.get("globalGuidelines"),
                },
                "templateOverview": template_overview,
            }
            if layout_design.get("themeTokens"):
                manifest_meta["themeTokens"] = layout_design["themeTokens"]
            if layout_design.get("tocPlan"):
                manifest_meta["toc"]["customEntries"] = layout_design["tocPlan"]
            # 初始化章节输出目录并写入manifest，方便流式存盘
            run_dir = self.chapter_storage.start_session(report_id, manifest_meta)
            self._persist_planning_artifacts(run_dir, layout_design, word_plan, template_overview)

            chapters = []
            for section in sections:
                logger.info(f"生成章节: {section.title}")
                chapter = self.chapter_generation_node.run(
                    section,
                    generation_context,
                    run_dir
                )
                chapters.append(chapter)

            document_ir = self.document_composer.build_document(
                report_id,
                manifest_meta,
                chapters
            )
            html_report = self.renderer.render(document_ir)

            self.state.html_content = html_report
            self.state.mark_completed()

            saved_files = {}
            if save_report:
                saved_files = self._save_report(html_report, document_ir, report_id)

            generation_time = (datetime.now() - start_time).total_seconds()
            self.state.metadata.generation_time = generation_time
            logger.info(f"报告生成完成，耗时: {generation_time:.2f} 秒")
            return {
                'html_content': html_report,
                'report_id': report_id,
                **saved_files
            }

        except Exception as e:
            self.state.mark_failed(str(e))
            logger.exception(f"报告生成过程中发生错误: {str(e)}")
            raise
    
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
    
    def _slice_template(self, template_markdown: str) -> List[TemplateSection]:
        """将模板切成章节列表，若为空则提供fallback"""
        sections = parse_template_sections(template_markdown)
        if sections:
            return sections
        logger.warning("模板未解析出章节，使用默认章节骨架")
        fallback = TemplateSection(
            title="1.0 综合分析",
            slug="section-1-0",
            order=10,
            depth=1,
            raw_title="1.0 综合分析",
            number="1.0",
            chapter_id="S1",
            outline=["1.1 摘要", "1.2 数据亮点", "1.3 风险提示"],
        )
        return [fallback]

    def _build_generation_context(
        self,
        query: str,
        reports: Dict[str, str],
        forum_logs: str,
        template_result: Dict[str, Any],
        layout_design: Dict[str, Any],
        chapter_directives: Dict[str, Any],
        word_plan: Dict[str, Any],
        template_overview: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构造章节生成所需的共享上下文

        这里把“全书设计稿”“章节篇幅约束”“统一主题配色”等一次性整理好，
        避免每次章节调用都重新拼装上下文。
        """
        # 优先使用设计稿定制的主题色，否则退回默认主题
        theme_tokens = (
            layout_design.get("themeTokens")
            if layout_design else None
        ) or self._default_theme_tokens()

        return {
            "query": query,
            "template_name": template_result.get("template_name"),
            "reports": reports,
            "forum_logs": self._stringify(forum_logs),
            "theme_tokens": theme_tokens,
            "style_directives": {
                "tone": "analytical",
                "audience": "executive",
                "language": "zh-CN",
            },
            "data_bundles": [],
            "max_tokens": min(self.config.MAX_CONTENT_LENGTH, 6000),
            "layout": layout_design or {},
            "template_overview": template_overview or {},
            "chapter_directives": chapter_directives or {},
            "word_plan": word_plan or {},
        }

    def _normalize_reports(self, reports: List[Any]) -> Dict[str, str]:
        """将不同来源的报告统一转为字符串"""
        keys = ["query_engine", "media_engine", "insight_engine"]
        normalized: Dict[str, str] = {}
        for idx, key in enumerate(keys):
            value = reports[idx] if idx < len(reports) else ""
            normalized[key] = self._stringify(value)
        return normalized

    def _stringify(self, value: Any) -> str:
        """安全地将对象转成字符串"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, indent=2)
            except Exception:
                return str(value)
        return str(value)

    def _default_theme_tokens(self) -> Dict[str, Any]:
        """默认的主题变量，供渲染器/LLM共用"""
        return {
            "colors": {
                "bg": "#f8f9fa",
                "text": "#212529",
                "primary": "#007bff",
                "secondary": "#6c757d",
                "card": "#ffffff",
                "border": "#dee2e6",
                "accent1": "#17a2b8",
                "accent2": "#28a745",
                "accent3": "#ffc107",
                "accent4": "#dc3545",
            },
            "fonts": {
                "body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif",
                "heading": "'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
            },
            "spacing": {"container": "1200px", "gutter": "24px"},
            "vars": {
                "header_sticky": True,
                "toc_depth": 3,
                "enable_dark_mode": True,
            },
        }

    def _build_template_overview(
        self,
        template_markdown: str,
        sections: List[TemplateSection],
    ) -> Dict[str, Any]:
        """提取模板标题与章节骨架，供设计/篇幅规划统一引用"""
        fallback_title = sections[0].title if sections else ""
        overview = {
            "title": self._extract_template_title(template_markdown, fallback_title),
            "chapters": [],
        }
        for section in sections:
            overview["chapters"].append(
                {
                    "chapterId": section.chapter_id,
                    "title": section.title,
                    "rawTitle": section.raw_title,
                    "number": section.number,
                    "slug": section.slug,
                    "order": section.order,
                    "depth": section.depth,
                    "outline": section.outline,
                }
            )
        return overview

    @staticmethod
    def _extract_template_title(template_markdown: str, fallback: str = "") -> str:
        """尝试从Markdown中提取首个标题，找不到时使用fallback"""
        for line in template_markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if stripped:
                fallback = fallback or stripped
        return fallback or "智能舆情分析报告"
    
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
    
    def _save_report(self, html_content: str, document_ir: Dict[str, Any], report_id: str) -> Dict[str, Any]:
        """保存HTML与IR到文件并返回路径信息"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(
            c for c in self.state.metadata.query if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        query_safe = query_safe.replace(" ", "_")[:30] or "report"

        html_filename = f"final_report_{query_safe}_{timestamp}.html"
        html_path = Path(self.config.OUTPUT_DIR) / html_filename
        html_path.write_text(html_content, encoding="utf-8")
        html_abs = str(html_path.resolve())
        html_rel = os.path.relpath(html_abs, os.getcwd())

        ir_path = self._save_document_ir(document_ir, query_safe, timestamp)
        ir_abs = str(ir_path.resolve())
        ir_rel = os.path.relpath(ir_abs, os.getcwd())

        state_filename = f"report_state_{query_safe}_{timestamp}.json"
        state_path = Path(self.config.OUTPUT_DIR) / state_filename
        self.state.save_to_file(str(state_path))
        state_abs = str(state_path.resolve())
        state_rel = os.path.relpath(state_abs, os.getcwd())

        logger.info(f"HTML报告已保存: {html_path}")
        logger.info(f"Document IR已保存: {ir_path}")
        logger.info(f"状态已保存到: {state_path}")
        
        return {
            'report_filename': html_filename,
            'report_filepath': html_abs,
            'report_relative_path': html_rel,
            'ir_filename': ir_path.name,
            'ir_filepath': ir_abs,
            'ir_relative_path': ir_rel,
            'state_filename': state_filename,
            'state_filepath': state_abs,
            'state_relative_path': state_rel,
        }

    def _save_document_ir(self, document_ir: Dict[str, Any], query_safe: str, timestamp: str) -> Path:
        """将整本IR写入独立目录"""
        filename = f"report_ir_{query_safe}_{timestamp}.json"
        ir_path = Path(self.config.DOCUMENT_IR_OUTPUT_DIR) / filename
        ir_path.write_text(
            json.dumps(document_ir, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ir_path
    
    def _persist_planning_artifacts(
        self,
        run_dir: Path,
        layout_design: Dict[str, Any],
        word_plan: Dict[str, Any],
        template_overview: Dict[str, Any],
    ):
        """
        将文档设计稿、篇幅规划与模板概览另存成JSON

        方便在调试或复盘时快速定位：标题/目录/主题是如何确定的、
        字数分配有什么要求，以便后续人工校正。
        """
        artifacts = {
            "document_layout": layout_design,
            "word_plan": word_plan,
            "template_overview": template_overview,
        }
        for name, payload in artifacts.items():
            if not payload:
                continue
            path = run_dir / f"{name}.json"
            try:
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                logger.warning(f"写入{name}失败: {exc}")
    
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
