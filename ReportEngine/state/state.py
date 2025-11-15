"""
Report Engine状态管理
定义报告生成过程中的简化状态数据结构
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
from datetime import datetime


@dataclass
class ReportMetadata:
    """简化的报告元数据"""
    query: str = ""                      # 原始查询
    template_used: str = ""              # 使用的模板名称
    generation_time: float = 0.0         # 生成耗时（秒）
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "query": self.query,
            "template_used": self.template_used,
            "generation_time": self.generation_time,
            "timestamp": self.timestamp
        }


@dataclass 
class ReportState:
    """
    简化的报告状态管理。

    存储任务基本信息、输入、输出与元数据，供Agent与Flask层共享。
    """
    # 基本信息
    task_id: str = ""                    # 任务ID
    query: str = ""                      # 原始查询
    status: str = "pending"              # 状态: pending, processing, completed, failed
    
    # 输入数据
    query_engine_report: str = ""        # QueryEngine报告
    media_engine_report: str = ""        # MediaEngine报告  
    insight_engine_report: str = ""      # InsightEngine报告
    forum_logs: str = ""                 # 论坛日志
    
    # 处理结果
    selected_template: str = ""          # 选择的模板
    html_content: str = ""               # 最终HTML内容
    
    # 元数据
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.task_id:
            self.task_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metadata.query = self.query
    
    def mark_processing(self):
        """标记为处理中，后台线程开始调度生成流程。"""
        self.status = "processing"
    
    def mark_completed(self):
        """标记为完成，同时意味着 `html_content` 已可用。"""
        self.status = "completed"
    
    def mark_failed(self, error_message: str = ""):
        """标记为失败，并记录最后一次错误消息。"""
        self.status = "failed"
        self.error_message = error_message
    
    def is_completed(self) -> bool:
        """检查是否完成，包括状态为completed且存在HTML内容。"""
        return self.status == "completed" and bool(self.html_content)
    
    def get_progress(self) -> float:
        """获取进度百分比，按照模板/内容两个阶段粗略估算。"""
        if self.status == "completed":
            return 100.0
        elif self.status == "processing":
            # 简单的进度计算
            progress = 0.0
            if self.selected_template:
                progress += 30.0
            if self.html_content:
                progress += 70.0
            return progress
        else:
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，方便序列化给前端。"""
        return {
            "task_id": self.task_id,
            "query": self.query,
            "status": self.status,
            "progress": self.get_progress(),
            "selected_template": self.selected_template,
            "has_html_content": bool(self.html_content),
            "html_content_length": len(self.html_content) if self.html_content else 0,
            "metadata": self.metadata.to_dict()
        }
    
    def save_to_file(self, file_path: str):
        """保存状态到文件，排除HTML正文以控制体积。"""
        try:
            state_data = self.to_dict()
            # 不保存完整的HTML内容到状态文件（太大）
            state_data.pop("html_content", None)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存状态文件失败: {str(e)}")
    
    @classmethod
    def load_from_file(cls, file_path: str) -> Optional["ReportState"]:
        """从文件加载状态，仅恢复关键字段便于调试。"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 创建ReportState对象
            state = cls(
                task_id=data.get("task_id", ""),
                query=data.get("query", ""),
                status=data.get("status", "pending"),
                selected_template=data.get("selected_template", "")
            )
            
            # 设置元数据
            metadata_data = data.get("metadata", {})
            state.metadata.template_used = metadata_data.get("template_used", "")
            state.metadata.generation_time = metadata_data.get("generation_time", 0.0)
            
            return state
            
        except Exception as e:
            print(f"加载状态文件失败: {str(e)}")
            return None
