"""
Report Engine节点基类。

所有高阶推理节点都继承于此，统一日志、输入校验与状态变更接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..llms.base import LLMClient
from ..state.state import ReportState
from loguru import logger

class BaseNode(ABC):
    """
    节点基类。

    统一实现日志工具、输入/输出钩子以及LLM客户端依赖注入，
    便于所有节点只专注业务逻辑。
    """
    
    def __init__(self, llm_client: LLMClient, node_name: str = ""):
        """
        初始化节点
        
        Args:
            llm_client: LLM客户端
            node_name: 节点名称

        BaseNode 会保存节点名以便统一输出日志前缀。
        """
        self.llm_client = llm_client
        self.node_name = node_name or self.__class__.__name__
    
    @abstractmethod
    def run(self, input_data: Any, **kwargs) -> Any:
        """
        执行节点处理逻辑
        
        Args:
            input_data: 输入数据
            **kwargs: 额外参数
            
        Returns:
            处理结果
        """
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """
        验证输入数据。
        默认直接通过，子类可按需覆写实现字段检查。
        
        Args:
            input_data: 输入数据
            
        Returns:
            验证是否通过
        """
        return True
    
    def process_output(self, output: Any) -> Any:
        """
        处理输出数据。
        子类可覆写进行结构化或校验。
        
        Args:
            output: 原始输出
            
        Returns:
            处理后的输出
        """
        return output
    
    def log_info(self, message: str):
        """记录信息日志，并自动带上节点名作为前缀。"""
        formatted_message = f"[{self.node_name}] {message}"
        logger.info(formatted_message)
    
    def log_error(self, message: str):
        """记录错误日志，便于排障。"""
        formatted_message = f"[{self.node_name}] {message}"
        logger.error(formatted_message)


class StateMutationNode(BaseNode):
    """
    带状态修改功能的节点基类。

    适用于节点需要直接写入 ReportState 的场景。
    """
    
    @abstractmethod
    def mutate_state(self, input_data: Any, state: ReportState, **kwargs) -> ReportState:
        """
        修改状态。

        子类需返回新的状态对象或在原地修改后回传，供流水线记录。
        
        Args:
            input_data: 输入数据
            state: 当前状态
            **kwargs: 额外参数
            
        Returns:
            修改后的状态
        """
        pass
