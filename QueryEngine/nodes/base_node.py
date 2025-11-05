"""
节点基类
定义所有处理节点的基础接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loguru import logger
from ..llms.base import LLMClient
from ..state.state import State


class BaseNode(ABC):
    """节点基类"""

    def __init__(self, llm_client: LLMClient, node_name: str = ""):
        """
        初始化节点

        Args:
            llm_client: LLM客户端
            node_name: 节点名称
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
        验证输入数据

        Args:
            input_data: 输入数据

        Returns:
            验证是否通过
        """
        return True

    def process_output(self, output: Any) -> Any:
        """
        处理输出数据

        Args:
            output: 原始输出

        Returns:
            处理后的输出
        """
        return output

    def log_info(self, message: str):
        """记录信息日志"""
        logger.info(f"[{self.node_name}] {message}")
    
    def log_warning(self, message: str):
        """记录警告日志"""
        logger.warning(f"[{self.node_name}] 警告: {message}")

    def log_error(self, message: str):
        """记录错误日志"""
        logger.error(f"[{self.node_name}] 错误: {message}")


class StateMutationNode(BaseNode):
    """带状态修改功能的节点基类"""
    
    @abstractmethod
    def mutate_state(self, input_data: Any, state: State, **kwargs) -> State:
        """
        修改状态
        
        Args:
            input_data: 输入数据
            state: 当前状态
            **kwargs: 额外参数
            
        Returns:
            修改后的状态
        """
        pass
