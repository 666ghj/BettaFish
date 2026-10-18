"""
Deep Search Agent状态管理
定义所有状态数据结构和操作方法
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from common.provenance.io import restore_engine_state, serialize_engine_state
from common.provenance.models import ProvenanceBundle


@dataclass
class Search:
    """单个搜索结果的状态"""
    query: str = ""                    # 搜索查询
    url: str = ""                      # 搜索结果的链接
    title: str = ""                    # 搜索结果标题
    content: str = ""                  # 搜索返回的内容
    raw_content: str = ""              # 可引用的正文片段
    publish_time: str = ""             # 来源发布时间
    domain: str = ""                   # 来源域名
    locator: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None      # 相关度评分
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "query": self.query,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "raw_content": self.raw_content,
            "publish_time": self.publish_time,
            "domain": self.domain,
            "locator": self.locator,
            "score": self.score,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Search":
        """从字典创建Search对象"""
        return cls(
            query=data.get("query", ""),
            url=data.get("url", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            raw_content=data.get("raw_content", ""),
            publish_time=data.get("publish_time", data.get("published_date", "")),
            domain=data.get("domain", ""),
            locator=data.get("locator", {}) or {},
            score=data.get("score"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class Research:
    """段落研究过程的状态"""
    search_history: List[Search] = field(default_factory=list)     # 搜索记录列表
    latest_summary: str = ""                                       # 当前段落的最新总结
    reflection_iteration: int = 0                                  # 反思迭代次数
    is_completed: bool = False                                     # 是否完成研究
    
    def add_search(self, search: Search):
        """添加搜索记录"""
        self.search_history.append(search)
    
    def add_search_results(self, query: str, results: List[Dict[str, Any]]):
        """批量添加搜索结果"""
        for result in results:
            search = Search(
                query=query,
                url=result.get("url", ""),
                title=result.get("title", ""),
                content=result.get("content", ""),
                raw_content=result.get("raw_content", ""),
                publish_time=result.get("publish_time", result.get("published_date", "")),
                domain=result.get("domain", ""),
                locator=result.get("locator", {}) or {},
                score=result.get("score")
            )
            self.add_search(search)
    
    def get_search_count(self) -> int:
        """获取搜索次数"""
        return len(self.search_history)
    
    def increment_reflection(self):
        """增加反思次数"""
        self.reflection_iteration += 1
    
    def mark_completed(self):
        """标记为完成"""
        self.is_completed = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "search_history": [search.to_dict() for search in self.search_history],
            "latest_summary": self.latest_summary,
            "reflection_iteration": self.reflection_iteration,
            "is_completed": self.is_completed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Research":
        """从字典创建Research对象"""
        search_history = [Search.from_dict(search_data) for search_data in data.get("search_history", [])]
        return cls(
            search_history=search_history,
            latest_summary=data.get("latest_summary", ""),
            reflection_iteration=data.get("reflection_iteration", 0),
            is_completed=data.get("is_completed", False)
        )


@dataclass
class Paragraph:
    """报告中单个段落的状态"""
    title: str = ""                                                # 段落标题
    content: str = ""                                              # 段落的预期内容（初始规划）
    research: Research = field(default_factory=Research)          # 研究进度
    order: int = 0                                                 # 段落顺序
    
    def is_completed(self) -> bool:
        """检查段落是否完成"""
        return self.research.is_completed and bool(self.research.latest_summary)
    
    def get_final_content(self) -> str:
        """获取最终内容"""
        return self.research.latest_summary or self.content
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "title": self.title,
            "content": self.content,
            "research": self.research.to_dict(),
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Paragraph":
        """从字典创建Paragraph对象"""
        research_data = data.get("research", {})
        research = Research.from_dict(research_data) if research_data else Research()
        
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            research=research,
            order=data.get("order", 0)
        )


@dataclass
class State:
    """整个报告的状态"""
    query: str = ""                                                # 原始查询
    report_title: str = ""                                         # 报告标题
    paragraphs: List[Paragraph] = field(default_factory=list)     # 段落列表
    final_report: str = ""                                         # 最终报告内容
    provenance_bundle: ProvenanceBundle = field(default_factory=lambda: ProvenanceBundle(agent="query_engine"))
    is_completed: bool = False                                     # 是否完成
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_paragraph(self, title: str, content: str) -> int:
        """
        添加段落
        
        Args:
            title: 段落标题
            content: 段落内容
            
        Returns:
            段落索引
        """
        order = len(self.paragraphs)
        paragraph = Paragraph(title=title, content=content, order=order)
        self.paragraphs.append(paragraph)
        self.update_timestamp()
        return order
    
    def get_paragraph(self, index: int) -> Optional[Paragraph]:
        """获取指定索引的段落"""
        if 0 <= index < len(self.paragraphs):
            return self.paragraphs[index]
        return None
    
    def get_completed_paragraphs_count(self) -> int:
        """获取已完成段落数量"""
        return sum(1 for p in self.paragraphs if p.is_completed())
    
    def get_total_paragraphs_count(self) -> int:
        """获取总段落数量"""
        return len(self.paragraphs)
    
    def is_all_paragraphs_completed(self) -> bool:
        """检查是否所有段落都完成"""
        return all(p.is_completed() for p in self.paragraphs) if self.paragraphs else False
    
    def mark_completed(self):
        """标记整个报告为完成"""
        self.is_completed = True
        self.update_timestamp()
    
    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now().isoformat()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        completed = self.get_completed_paragraphs_count()
        total = self.get_total_paragraphs_count()
        
        return {
            "total_paragraphs": total,
            "completed_paragraphs": completed,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "is_completed": self.is_completed,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return serialize_engine_state(self)
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "State":
        """从字典创建State对象"""
        return restore_engine_state(cls, Paragraph, data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "State":
        """从JSON字符串创建State对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def save_to_file(self, filepath: str):
        """保存状态到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "State":
        """从文件加载状态"""
        with open(filepath, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return cls.from_json(json_str)
