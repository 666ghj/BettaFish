"""
Forum日志读取工具
用于读取forum.log中的最新HOST发言
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
from loguru import logger

def get_latest_host_speech(log_dir: str = "logs") -> Optional[str]:
    """
    获取forum.log中最新的HOST发言(仅匹配当前搜索会话ID)

    Args:
        log_dir: 日志目录路径

    Returns:
        最新的HOST发言内容，如果没有则返回None
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"

        if not forum_log_path.exists():
            logger.debug("forum.log文件不存在")
            return None

        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # 首先获取当前搜索会话ID
        current_search_id = None
        for line in lines:
            # 匹配格式: [时间] [SYSTEM] [session_id] === 搜索会话ID: xxxxx ===
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[SYSTEM\]\s*\[(\S+)\]\s*===\s*搜索会话ID:\s*(\S+)\s*===', line)
            if match:
                current_search_id = match.group(3)  # 第三个分组是搜索会话ID
                # 继续遍历以获取最新的search_id（如果有多次搜索）

        if not current_search_id:
            logger.debug("未找到搜索会话ID，无法过滤HOST发言")
            return None

        logger.debug(f"当前搜索会话ID: {current_search_id}")

        # 从后往前查找最新的HOST发言（需匹配search_id）
        host_speech = None
        for line in reversed(lines):
            # 匹配格式: [时间] [HOST] [search_id] 内容
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[HOST\]\s*\[(\S+)\]\s*(.+)', line)
            if match:
                _, speech_search_id, content = match.groups()
                # 只接受与当前搜索会话ID匹配的HOST发言
                if speech_search_id == current_search_id:
                    # 处理转义的换行符，还原为实际换行
                    host_speech = content.replace('\\n', '\n').strip()
                    break

        if host_speech:
            logger.info(f"找到最新的HOST发言(搜索ID: {current_search_id})，长度: {len(host_speech)}字符")
        else:
            logger.debug(f"未找到匹配当前搜索会话(ID: {current_search_id})的HOST发言")

        return host_speech

    except Exception as e:
        logger.error(f"读取forum.log失败: {str(e)}")
        return None


def get_all_host_speeches(log_dir: str = "logs") -> List[Dict[str, str]]:
    """
    获取forum.log中所有的HOST发言
    
    Args:
        log_dir: 日志目录路径
        
    Returns:
        包含所有HOST发言的列表，每个元素是包含timestamp和content的字典
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"
        
        if not forum_log_path.exists():
            logger.debug("forum.log文件不存在")
            return []
            
        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        host_speeches = []
        for line in lines:
            # 匹配格式: [时间] [HOST] 内容
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[HOST\]\s*(.+)', line)
            if match:
                timestamp, content = match.groups()
                # 处理转义的换行符
                content = content.replace('\\n', '\n').strip()
                host_speeches.append({
                    'timestamp': timestamp,
                    'content': content
                })
        
        logger.info(f"找到{len(host_speeches)}条HOST发言")
        return host_speeches
        
    except Exception as e:
        logger.error(f"读取forum.log失败: {str(e)}")
        return []


def get_recent_agent_speeches(log_dir: str = "logs", limit: int = 5) -> List[Dict[str, str]]:
    """
    获取forum.log中最近的Agent发言（不包括HOST）
    
    Args:
        log_dir: 日志目录路径
        limit: 返回的最大发言数量
        
    Returns:
        包含最近Agent发言的列表
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"
        
        if not forum_log_path.exists():
            return []
            
        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        agent_speeches = []
        for line in reversed(lines):  # 从后往前读取
            # 匹配格式: [时间] [AGENT_NAME] 内容
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[(INSIGHT|MEDIA|QUERY)\]\s*(.+)', line)
            if match:
                timestamp, agent, content = match.groups()
                # 处理转义的换行符
                content = content.replace('\\n', '\n').strip()
                agent_speeches.append({
                    'timestamp': timestamp,
                    'agent': agent,
                    'content': content
                })
                if len(agent_speeches) >= limit:
                    break
        
        agent_speeches.reverse()  # 恢复时间顺序
        return agent_speeches
        
    except Exception as e:
        logger.error(f"读取forum.log失败: {str(e)}")
        return []


def format_host_speech_for_prompt(host_speech: str) -> str:
    """
    格式化HOST发言，用于添加到prompt中
    
    Args:
        host_speech: HOST发言内容
        
    Returns:
        格式化后的内容
    """
    if not host_speech:
        return ""
    
    return f"""
### 论坛主持人最新总结
以下是论坛主持人对各Agent讨论的最新总结和引导，请参考其中的观点和建议：

{host_speech}

---
"""
