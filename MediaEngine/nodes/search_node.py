"""
搜索节点实现
负责生成搜索查询和反思查询
"""

import json
from typing import Dict, Any, List, Tuple
from json.decoder import JSONDecodeError
from loguru import logger

from .base_node import BaseNode
from ..prompts import SYSTEM_PROMPT_FIRST_SEARCH, SYSTEM_PROMPT_REFLECTION
from ..utils.text_processing import (
    remove_reasoning_from_output,
    clean_json_tags,
    extract_clean_response,
    fix_incomplete_json
)


class ValidationError(Exception):
    """输入验证错误"""
    pass


class InputValidator:
    """输入验证器，提供统一的验证逻辑"""
    
    # 配置常量
    MAX_TITLE_LENGTH = 500
    MAX_CONTENT_LENGTH = 10000
    MAX_PARAGRAPH_STATE_LENGTH = 50000
    MIN_TITLE_LENGTH = 1
    MIN_CONTENT_LENGTH = 1
    
    @staticmethod
    def sanitize_string(value: Any, field_name: str) -> str:
        """
        清理和验证字符串字段
        
        Args:
            value: 待清理的值
            field_name: 字段名称（用于错误消息）
            
        Returns:
            清理后的字符串
            
        Raises:
            ValidationError: 如果值无效
        """
        if value is None:
            raise ValidationError(f"字段 '{field_name}' 不能为 None")
        
        if not isinstance(value, str):
            # 尝试转换为字符串
            try:
                value = str(value)
            except Exception:
                raise ValidationError(f"字段 '{field_name}' 必须是字符串类型，当前类型: {type(value).__name__}")
        
        # 去除首尾空白
        value = value.strip()
        
        if not value:
            raise ValidationError(f"字段 '{field_name}' 不能为空")
        
        return value
    
    @staticmethod
    def validate_string_length(value: str, field_name: str, min_len: int, max_len: int):
        """
        验证字符串长度
        
        Args:
            value: 待验证的字符串
            field_name: 字段名称
            min_len: 最小长度
            max_len: 最大长度
            
        Raises:
            ValidationError: 如果长度不符合要求
        """
        length = len(value)
        if length < min_len:
            raise ValidationError(
                f"字段 '{field_name}' 长度过短 ({length} 字符)，"
                f"最小要求: {min_len} 字符"
            )
        if length > max_len:
            raise ValidationError(
                f"字段 '{field_name}' 长度过长 ({length} 字符)，"
                f"最大限制: {max_len} 字符"
            )
    
    @staticmethod
    def validate_title(title: str) -> str:
        """
        验证并清理标题字段
        
        Args:
            title: 标题字符串
            
        Returns:
            清理后的标题
            
        Raises:
            ValidationError: 如果标题无效
        """
        title = InputValidator.sanitize_string(title, "title")
        InputValidator.validate_string_length(
            title, "title", 
            InputValidator.MIN_TITLE_LENGTH, 
            InputValidator.MAX_TITLE_LENGTH
        )
        return title
    
    @staticmethod
    def validate_content(content: str) -> str:
        """
        验证并清理内容字段
        
        Args:
            content: 内容字符串
            
        Returns:
            清理后的内容
            
        Raises:
            ValidationError: 如果内容无效
        """
        content = InputValidator.sanitize_string(content, "content")
        InputValidator.validate_string_length(
            content, "content",
            InputValidator.MIN_CONTENT_LENGTH,
            InputValidator.MAX_CONTENT_LENGTH
        )
        return content
    
    @staticmethod
    def validate_paragraph_state(paragraph_state: Any) -> str:
        """
        验证段落状态字段
        
        Args:
            paragraph_state: 段落状态（可以是字符串或字典）
            
        Returns:
            验证后的段落状态字符串
            
        Raises:
            ValidationError: 如果段落状态无效
        """
        if paragraph_state is None:
            raise ValidationError("字段 'paragraph_latest_state' 不能为 None")
        
        # 如果是字典，转换为JSON字符串
        if isinstance(paragraph_state, dict):
            try:
                paragraph_state = json.dumps(paragraph_state, ensure_ascii=False)
            except Exception as e:
                raise ValidationError(f"无法序列化 'paragraph_latest_state': {str(e)}")
        
        # 验证为字符串
        paragraph_state = InputValidator.sanitize_string(
            paragraph_state, "paragraph_latest_state"
        )
        
        # 验证长度（段落状态可能较长，使用更大的限制）
        InputValidator.validate_string_length(
            paragraph_state, "paragraph_latest_state",
            1,  # 最小长度
            InputValidator.MAX_PARAGRAPH_STATE_LENGTH
        )
        
        return paragraph_state
    
    @staticmethod
    def parse_and_validate_json(input_data: str) -> Dict[str, Any]:
        """
        解析并验证JSON字符串
        
        Args:
            input_data: JSON字符串
            
        Returns:
            解析后的字典
            
        Raises:
            ValidationError: 如果JSON无效
        """
        if not isinstance(input_data, str):
            raise ValidationError(f"输入必须是字符串类型，当前类型: {type(input_data).__name__}")
        
        if not input_data.strip():
            raise ValidationError("输入JSON字符串不能为空")
        
        try:
            data = json.loads(input_data)
        except JSONDecodeError as e:
            raise ValidationError(f"无效的JSON格式: {str(e)}")
        
        if not isinstance(data, dict):
            raise ValidationError(f"JSON根对象必须是字典类型，当前类型: {type(data).__name__}")
        
        return data
    
    @staticmethod
    def validate_first_search_input(input_data: Any) -> Tuple[Dict[str, Any], List[str]]:
        """
        验证首次搜索节点的输入
        
        Args:
            input_data: 输入数据（字符串或字典）
            
        Returns:
            (验证后的数据字典, 警告消息列表)
            
        Raises:
            ValidationError: 如果验证失败
        """
        warnings = []
        
        # 解析输入
        if isinstance(input_data, str):
            data = InputValidator.parse_and_validate_json(input_data)
        elif isinstance(input_data, dict):
            data = input_data
        else:
            raise ValidationError(
                f"输入数据类型错误，期望 str 或 dict，当前类型: {type(input_data).__name__}"
            )
        
        # 检查必需字段
        if "title" not in data:
            raise ValidationError("缺少必需字段: 'title'")
        if "content" not in data:
            raise ValidationError("缺少必需字段: 'content'")
        
        # 验证并清理字段
        validated_data = {}
        validated_data["title"] = InputValidator.validate_title(data["title"])
        validated_data["content"] = InputValidator.validate_content(data["content"])
        
        # 检查是否有额外的未知字段（给出警告但不失败）
        known_fields = {"title", "content"}
        unknown_fields = set(data.keys()) - known_fields
        if unknown_fields:
            warnings.append(f"发现未知字段: {', '.join(unknown_fields)}，将被忽略")
        
        return validated_data, warnings
    
    @staticmethod
    def validate_reflection_input(input_data: Any) -> Tuple[Dict[str, Any], List[str]]:
        """
        验证反思节点的输入
        
        Args:
            input_data: 输入数据（字符串或字典）
            
        Returns:
            (验证后的数据字典, 警告消息列表)
            
        Raises:
            ValidationError: 如果验证失败
        """
        warnings = []
        
        # 解析输入
        if isinstance(input_data, str):
            data = InputValidator.parse_and_validate_json(input_data)
        elif isinstance(input_data, dict):
            data = input_data
        else:
            raise ValidationError(
                f"输入数据类型错误，期望 str 或 dict，当前类型: {type(input_data).__name__}"
            )
        
        # 检查必需字段
        required_fields = ["title", "content", "paragraph_latest_state"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"缺少必需字段: {', '.join(missing_fields)}")
        
        # 验证并清理字段
        validated_data = {}
        validated_data["title"] = InputValidator.validate_title(data["title"])
        validated_data["content"] = InputValidator.validate_content(data["content"])
        validated_data["paragraph_latest_state"] = InputValidator.validate_paragraph_state(
            data["paragraph_latest_state"]
        )
        
        # 检查是否有额外的未知字段
        unknown_fields = set(data.keys()) - set(required_fields)
        if unknown_fields:
            warnings.append(f"发现未知字段: {', '.join(unknown_fields)}，将被忽略")
        
        return validated_data, warnings


class FirstSearchNode(BaseNode):
    """为段落生成首次搜索查询的节点"""
    
    def __init__(self, llm_client):
        """
        初始化首次搜索节点
        
        Args:
            llm_client: LLM客户端
        """
        super().__init__(llm_client, "FirstSearchNode")
        self._last_validation_warnings: List[str] = []
    
    def validate_input(self, input_data: Any) -> bool:
        """
        验证输入数据
        
        Args:
            input_data: 输入数据（字符串或字典）
            
        Returns:
            验证是否通过
        """
        try:
            validated_data, warnings = InputValidator.validate_first_search_input(input_data)
            self._last_validation_warnings = warnings
            
            # 记录警告（如果有）
            for warning in warnings:
                self.log_warning(warning)
            
            return True
        except ValidationError as e:
            self.log_error(f"输入验证失败: {str(e)}")
            return False
        except Exception as e:
            self.log_error(f"输入验证时发生意外错误: {str(e)}")
            return False
    
    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        """
        调用LLM生成搜索查询和理由
        
        Args:
            input_data: 包含title和content的字符串或字典
            **kwargs: 额外参数
            
        Returns:
            包含search_query和reasoning的字典
            
        Raises:
            ValidationError: 如果输入验证失败
        """
        try:
            # 验证并清理输入
            validated_data, warnings = InputValidator.validate_first_search_input(input_data)
            
            # 记录警告（如果有）
            for warning in warnings:
                self.log_warning(warning)
            
            # 使用验证后的数据准备消息
            message = json.dumps(validated_data, ensure_ascii=False)
            
            logger.info("正在生成首次搜索查询")
            
            # 调用LLM
            response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_FIRST_SEARCH, message)
            
            # 处理响应
            processed_response = self.process_output(response)
            
            logger.info(f"生成搜索查询: {processed_response.get('search_query', 'N/A')}")
            return processed_response
            
        except ValidationError as e:
            self.log_error(f"输入验证失败: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"生成首次搜索查询失败: {str(e)}")
            raise
    
    def process_output(self, output: str) -> Dict[str, str]:
        """
        处理LLM输出，提取搜索查询和推理
        
        Args:
            output: LLM原始输出
            
        Returns:
            包含search_query和reasoning的字典
        """
        try:
            # 清理响应文本
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            
            # 记录清理后的输出用于调试
            logger.info(f"清理后的输出: {cleaned_output}")
            
            # 解析JSON
            try:
                result = json.loads(cleaned_output)
                logger.info("JSON解析成功")
            except JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                # 使用更强大的提取方法
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    logger.error("JSON解析失败，尝试修复...")
                    # 尝试修复JSON
                    fixed_json = fix_incomplete_json(cleaned_output)
                    if fixed_json:
                        try:
                            result = json.loads(fixed_json)
                            logger.info("JSON修复成功")
                        except JSONDecodeError:
                            logger.error("JSON修复失败")
                            # 返回默认查询
                            return self._get_default_search_query()
                    else:
                        logger.error("无法修复JSON，使用默认查询")
                        return self._get_default_search_query()
            
            # 验证和清理结果
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")
            
            if not search_query:
                logger.warning("未找到搜索查询，使用默认查询")
                return self._get_default_search_query()
            
            return {
                "search_query": search_query,
                "reasoning": reasoning
            }
            
        except Exception as e:
            self.log_error(f"处理输出失败: {str(e)}")
            # 返回默认查询
            return self._get_default_search_query()
    
    def _get_default_search_query(self) -> Dict[str, str]:
        """
        获取默认搜索查询
        
        Returns:
            默认的搜索查询字典
        """
        return {
            "search_query": "相关主题研究",
            "reasoning": "由于解析失败，使用默认搜索查询"
        }


class ReflectionNode(BaseNode):
    """反思段落并生成新搜索查询的节点"""
    
    def __init__(self, llm_client):
        """
        初始化反思节点
        
        Args:
            llm_client: LLM客户端
        """
        super().__init__(llm_client, "ReflectionNode")
        self._last_validation_warnings: List[str] = []
    
    def validate_input(self, input_data: Any) -> bool:
        """
        验证输入数据
        
        Args:
            input_data: 输入数据（字符串或字典）
            
        Returns:
            验证是否通过
        """
        try:
            validated_data, warnings = InputValidator.validate_reflection_input(input_data)
            self._last_validation_warnings = warnings
            
            # 记录警告（如果有）
            for warning in warnings:
                self.log_warning(warning)
            
            return True
        except ValidationError as e:
            self.log_error(f"输入验证失败: {str(e)}")
            return False
        except Exception as e:
            self.log_error(f"输入验证时发生意外错误: {str(e)}")
            return False
    
    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        """
        调用LLM反思并生成搜索查询
        
        Args:
            input_data: 包含title、content和paragraph_latest_state的字符串或字典
            **kwargs: 额外参数
            
        Returns:
            包含search_query和reasoning的字典
            
        Raises:
            ValidationError: 如果输入验证失败
        """
        try:
            # 验证并清理输入
            validated_data, warnings = InputValidator.validate_reflection_input(input_data)
            
            # 记录警告（如果有）
            for warning in warnings:
                self.log_warning(warning)
            
            # 使用验证后的数据准备消息
            message = json.dumps(validated_data, ensure_ascii=False)
            
            logger.info("正在进行反思并生成新搜索查询")
            
            # 调用LLM
            response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_REFLECTION, message)
            
            # 处理响应
            processed_response = self.process_output(response)
            
            logger.info(f"反思生成搜索查询: {processed_response.get('search_query', 'N/A')}")
            return processed_response
            
        except ValidationError as e:
            self.log_error(f"输入验证失败: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"反思生成搜索查询失败: {str(e)}")
            raise
    
    def process_output(self, output: str) -> Dict[str, str]:
        """
        处理LLM输出，提取搜索查询和推理
        
        Args:
            output: LLM原始输出
            
        Returns:
            包含search_query和reasoning的字典
        """
        try:
            # 清理响应文本
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            
            # 记录清理后的输出用于调试
            logger.info(f"清理后的输出: {cleaned_output}")
            
            # 解析JSON
            try:
                result = json.loads(cleaned_output)
                logger.info("JSON解析成功")
            except JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                # 使用更强大的提取方法
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    logger.error("JSON解析失败，尝试修复...")
                    # 尝试修复JSON
                    fixed_json = fix_incomplete_json(cleaned_output)
                    if fixed_json:
                        try:
                            result = json.loads(fixed_json)
                            logger.info("JSON修复成功")
                        except JSONDecodeError:
                            logger.error("JSON修复失败")
                            # 返回默认查询
                            return self._get_default_reflection_query()
                    else:
                        logger.error("无法修复JSON，使用默认查询")
                        return self._get_default_reflection_query()
            
            # 验证和清理结果
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")
            
            if not search_query:
                logger.warning("未找到搜索查询，使用默认查询")
                return self._get_default_reflection_query()
            
            return {
                "search_query": search_query,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.exception(f"处理输出失败: {str(e)}")
            # 返回默认查询
            return self._get_default_reflection_query()
    
    def _get_default_reflection_query(self) -> Dict[str, str]:
        """
        获取默认反思搜索查询
        
        Returns:
            默认的反思搜索查询字典
        """
        return {
            "search_query": "深度研究补充信息",
            "reasoning": "由于解析失败，使用默认反思搜索查询"
        }
