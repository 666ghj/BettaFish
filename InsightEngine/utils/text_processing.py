"""
文本处理工具函数
用于清理LLM输出、解析JSON等
"""

import re
import json
from typing import Dict, Any, List
from json.decoder import JSONDecodeError


def clean_json_tags(text: str) -> str:
    """
    清理文本中的JSON标签
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 移除```json 和 ```标签
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = re.sub(r'```', '', text)
    
    return text.strip()


def clean_markdown_tags(text: str) -> str:
    """
    清理文本中的Markdown标签
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 移除```markdown 和 ```标签
    text = re.sub(r'```markdown\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = re.sub(r'```', '', text)
    
    return text.strip()


def remove_reasoning_from_output(text: str) -> str:
    """
    移除输出中的推理过程文本
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 查找JSON开始位置
    json_start = -1
    
    # 尝试找到第一个 { 或 [
    for i, char in enumerate(text):
        if char in '{[':
            json_start = i
            break
    
    if json_start != -1:
        # 从JSON开始位置截取
        return text[json_start:].strip()
    
    # 如果没有找到JSON标记，尝试其他方法
    # 移除常见的推理标识
    patterns = [
        r'(?:reasoning|推理|思考|分析)[:：]\s*.*?(?=\{|\[)',  # 移除推理部分
        r'(?:explanation|解释|说明)[:：]\s*.*?(?=\{|\[)',   # 移除解释部分
        r'^.*?(?=\{|\[)',  # 移除JSON前的所有文本
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()


def extract_clean_response(text: str) -> Dict[str, Any]:
    """
    提取并清理响应中的JSON内容
    
    Args:
        text: 原始响应文本
        
    Returns:
        解析后的JSON字典
    """
    # 清理文本
    cleaned_text = clean_json_tags(text)
    cleaned_text = remove_reasoning_from_output(cleaned_text)
    
    # 尝试直接解析
    try:
        return json.loads(cleaned_text)
    except JSONDecodeError:
        pass
    
    # 尝试修复不完整的JSON
    fixed_text = fix_incomplete_json(cleaned_text)
    if fixed_text:
        try:
            return json.loads(fixed_text)
        except JSONDecodeError:
            pass
    
    # 尝试查找JSON对象
    json_pattern = r'\{.*\}'
    match = re.search(json_pattern, cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except JSONDecodeError:
            pass
    
    # 尝试查找JSON数组
    array_pattern = r'\[.*\]'
    match = re.search(array_pattern, cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except JSONDecodeError:
            pass
    
    # 如果所有方法都失败，返回错误信息
    print(f"无法解析JSON响应: {cleaned_text[:200]}...")
    return {"error": "JSON解析失败", "raw_text": cleaned_text}


def fix_incomplete_json(text: str) -> str:
    """
    修复不完整的JSON响应
    
    Args:
        text: 原始文本
        
    Returns:
        修复后的JSON文本，如果无法修复则返回空字符串
    """
    # 移除多余的逗号和空白
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    
    # 检查是否已经是有效的JSON
    try:
        json.loads(text)
        return text
    except JSONDecodeError:
        pass
    
    # 检查是否缺少开头的数组符号
    if text.strip().startswith('{') and not text.strip().startswith('['):
        # 如果以对象开始，尝试包装成数组
        if text.count('{') > 1:
            # 多个对象，包装成数组
            text = '[' + text + ']'
        else:
            # 单个对象，包装成数组
            text = '[' + text + ']'
    
    # 检查是否缺少结尾的数组符号
    if text.strip().endswith('}') and not text.strip().endswith(']'):
        # 如果以对象结束，尝试包装成数组
        if text.count('}') > 1:
            # 多个对象，包装成数组
            text = '[' + text + ']'
        else:
            # 单个对象，包装成数组
            text = '[' + text + ']'
    
    # 检查括号是否匹配（忽略字符串内的括号）
    open_braces = 0
    close_braces = 0
    open_brackets = 0
    close_brackets = 0
    in_string = False
    escape_next = False
    for char in text:
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not in_string:
            in_string = True
            continue
        if char == '"' and in_string:
            in_string = False
            continue
        if in_string:
            continue
        if char == '{':
            open_braces += 1
        elif char == '}':
            close_braces += 1
        elif char == '[':
            open_brackets += 1
        elif char == ']':
            close_brackets += 1
    
    # 修复不匹配的括号
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)
    
    # 验证修复后的JSON是否有效
    try:
        json.loads(text)
        return text
    except JSONDecodeError:
        # 如果仍然无效，尝试更激进的修复
        return fix_aggressive_json(text)


def fix_aggressive_json(text: str) -> str:
    """
    更激进的JSON修复方法
    
    Args:
        text: 原始文本
        
    Returns:
        修复后的JSON文本
    """
    # 查找所有可能的JSON对象（支持嵌套）
    objects = []
    depth = 0
    start = -1
    in_string = False
    escape_next = False
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not in_string:
            in_string = True
            continue
        if char == '"' and in_string:
            in_string = False
            continue
        if in_string:
            continue
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start != -1:
                objects.append(text[start:i+1])
                start = -1
    
    if len(objects) >= 2:
        return '[' + ','.join(objects) + ']'
    elif len(objects) == 1:
        return '[' + objects[0] + ']'
    else:
        return '[]'


def update_state_with_search_results(search_results: List[Dict[str, Any]], 
                                   paragraph_index: int, state: Any) -> Any:
    """
    将搜索结果更新到状态中
    
    Args:
        search_results: 搜索结果列表
        paragraph_index: 段落索引
        state: 状态对象
        
    Returns:
        更新后的状态对象
    """
    if 0 <= paragraph_index < len(state.paragraphs):
        # 获取最后一次搜索的查询（假设是当前查询）
        current_query = ""
        if search_results:
            # 从搜索结果推断查询（这里需要改进以获取实际查询）
            current_query = "搜索查询"
        
        # 添加搜索结果到状态
        state.paragraphs[paragraph_index].research.add_search_results(
            current_query, search_results
        )
    
    return state


def validate_json_schema(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """
    验证JSON数据是否包含必需字段
    
    Args:
        data: 要验证的数据
        required_fields: 必需字段列表
        
    Returns:
        验证是否通过
    """
    return all(field in data for field in required_fields)


def truncate_content(content: str, max_length: int = 20000) -> str:
    """
    截断内容到指定长度
    
    Args:
        content: 原始内容
        max_length: 最大长度
        
    Returns:
        截断后的内容
    """
    if len(content) <= max_length:
        return content
    
    # 尝试在单词边界截断
    truncated = content[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # 如果最后一个空格位置合理
        return truncated[:last_space] + "..."
    else:
        return truncated + "..."


def format_search_results_for_prompt(search_results: List[Dict[str, Any]], 
                                   max_length: int = 20000) -> List[str]:
    """
    格式化搜索结果用于提示词
    
    Args:
        search_results: 搜索结果列表
        max_length: 每个结果的最大长度
        
    Returns:
        格式化后的内容列表
    """
    formatted_results = []
    
    for result in search_results:
        content = result.get('content', '')
        if content:
            truncated_content = truncate_content(content, max_length)
            formatted_results.append(truncated_content)
    
    return formatted_results
