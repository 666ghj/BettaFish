"""
日志监控器 - 实时监控三个log文件中的SummaryNode输出
"""

import os
import time
import threading
from pathlib import Path
from datetime import datetime
import re
import json
from typing import Dict, Optional, List
from threading import Lock
from loguru import logger

# 导入论坛主持人模块
try:
    from .llm_host import generate_host_speech
    HOST_AVAILABLE = True
except ImportError:
    logger.warning("ForumEngine: 论坛主持人模块未找到，将以纯监控模式运行")
    HOST_AVAILABLE = False

class LogMonitor:
    """基于文件变化的智能日志监控器"""
   
    def __init__(self, log_dir: str = "logs"):
        """初始化日志监控器"""
        self.log_dir = Path(log_dir)
        self.forum_log_file = self.log_dir / "forum.log"
       
        # 要监控的日志文件
        self.monitored_logs = {
            'insight': self.log_dir / 'insight.log',
            'media': self.log_dir / 'media.log',
            'query': self.log_dir / 'query.log'
        }
       
        # 监控状态
        self.is_monitoring = False
        self.monitor_thread = None
        self.file_positions = {}  # 记录每个文件的读取位置
        self.file_line_counts = {}  # 记录每个文件的行数
        self.is_searching = False  # 是否正在搜索
        self.search_inactive_count = 0  # 搜索非活跃计数器
        self.write_lock = Lock()  # 写入锁，防止并发写入冲突
        
        # 主持人相关状态
        self.agent_speeches_buffer = []  # agent发言缓冲区
        self.host_speech_threshold = 5  # 每5条agent发言触发一次主持人发言
        self.is_host_generating = False  # 主持人是否正在生成发言
       
        # 目标节点名称 - 直接匹配字符串
        self.target_nodes = [
            'FirstSummaryNode',
            'ReflectionSummaryNode'
        ]
        
        # 多行内容捕获状态
        self.capturing_json = {}  # 每个app的JSON捕获状态
        self.json_buffer = {}     # 每个app的JSON缓冲区
        self.json_start_line = {} # 每个app的JSON开始行
       
        # 确保logs目录存在
        self.log_dir.mkdir(exist_ok=True)
   
    def clear_forum_log(self):
        """清空forum.log文件"""
        try:
            if self.forum_log_file.exists():
                self.forum_log_file.unlink()
           
            # 创建新的forum.log文件并写入开始标记
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 使用write_to_forum_log函数来写入开始标记，确保格式一致
            with open(self.forum_log_file, 'w', encoding='utf-8') as f:
                pass  # 先创建空文件
            self.write_to_forum_log(f"=== ForumEngine 监控开始 - {start_time} ===", "SYSTEM")
               
            logger.info(f"ForumEngine: forum.log 已清空并初始化")
            
            # 重置JSON捕获状态
            self.capturing_json = {}
            self.json_buffer = {}
            self.json_start_line = {}
            
            # 重置主持人相关状态
            self.agent_speeches_buffer = []
            self.is_host_generating = False
           
        except Exception as e:
            logger.exception(f"ForumEngine: 清空forum.log失败: {e}")
   
    def write_to_forum_log(self, content: str, source: str = None):
        """写入内容到forum.log（线程安全）"""
        try:
            with self.write_lock:  # 使用锁确保线程安全
                with open(self.forum_log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    # 将内容中的实际换行符转换为\n字符串，确保整个记录在一行
                    content_one_line = content.replace('\n', '\\n').replace('\r', '\\r')
                    # 如果提供了来源标签，则在时间戳后添加
                    if source:
                        f.write(f"[{timestamp}] [{source}] {content_one_line}\n")
                    else:
                        f.write(f"[{timestamp}] {content_one_line}\n")
                    f.flush()
        except Exception as e:
            logger.exception(f"ForumEngine: 写入forum.log失败: {e}")
   
    def is_target_log_line(self, line: str) -> bool:
        """检查是否是目标日志行（SummaryNode）"""
        # 简单字符串包含检查，更可靠
        for node_name in self.target_nodes:
            if node_name in line:
                return True
        return False
    
    def is_valuable_content(self, line: str) -> bool:
        """判断是否是有价值的内容（排除短小的提示信息和错误信息）"""
        # 如果包含"清理后的输出"，则认为是有价值的
        if "清理后的输出" in line:
            return True
        
        # 排除常见的短小提示信息和错误信息
        exclude_patterns = [
            "JSON解析失败",
            "JSON修复失败",
            "直接使用清理后的文本",
            "JSON解析成功",
            "成功生成",
            "已更新段落",
            "正在生成",
            "开始处理",
            "处理完成",
            "已读取HOST发言",
            "读取HOST发言失败",
            "未找到HOST发言",
            "调试输出",
            "信息记录"
        ]
        
        for pattern in exclude_patterns:
            if pattern in line:
                return False
        
        # 如果行长度过短，也认为不是有价值的内容
        # 移除时间戳：支持旧格式和新格式
        clean_line = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', line)
        clean_line = re.sub(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', clean_line)
        clean_line = clean_line.strip()
        if len(clean_line) < 30:  # 阈值可以调整
            return False
            
        return True
    
    def is_json_start_line(self, line: str) -> bool:
        """判断是否是JSON开始行"""
        return "清理后的输出: {" in line
    
    def is_json_end_line(self, line: str) -> bool:
        """判断是否是JSON结束行
        
        只判断纯粹的结束标记行，不包含任何日志格式信息（时间戳等）。
        如果行包含时间戳，应该先清理再判断，但这里返回False表示需要进一步处理。
        """
        stripped = line.strip()
        
        # 如果行包含时间戳（旧格式或新格式），说明不是纯粹的结束行
        # 旧格式：[HH:MM:SS]
        if re.match(r'^\[\d{2}:\d{2}:\d{2}\]', stripped):
            return False
        # 新格式：YYYY-MM-DD HH:mm:ss.SSS
        if re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}', stripped):
            return False
        
        # 不包含时间戳的行，检查是否是纯结束标记
        if stripped == "}" or stripped == "] }":
            return True
        return False
    
    def extract_json_content(self, json_lines: List[str]) -> Optional[str]:
        """从多行中提取并解析JSON内容"""
        try:
            # 找到JSON开始的位置
            json_start_idx = -1
            for i, line in enumerate(json_lines):
                if "清理后的输出: {" in line:
                    json_start_idx = i
                    break
            
            if json_start_idx == -1:
                return None
            
            # 提取JSON部分
            first_line = json_lines[json_start_idx]
            json_start_pos = first_line.find("清理后的输出: {")
            if json_start_pos == -1:
                return None
            
            json_part = first_line[json_start_pos + len("清理后的输出: "):]
            
            # 如果第一行就包含完整JSON，直接处理
            if json_part.strip().endswith("}") and json_part.count("{") == json_part.count("}"):
                try:
                    json_obj = json.loads(json_part.strip())
                    return self.format_json_content(json_obj)
                except json.JSONDecodeError:
                    # 单行JSON解析失败，尝试修复
                    fixed_json = self.fix_json_string(json_part.strip())
                    if fixed_json:
                        try:
                            json_obj = json.loads(fixed_json)
                            return self.format_json_content(json_obj)
                        except json.JSONDecodeError:
                            pass
                    return None
            
            # 处理多行JSON
            json_text = json_part
            for line in json_lines[json_start_idx + 1:]:
                # 移除时间戳：支持旧格式 [HH:MM:SS] 和新格式 loguru (YYYY-MM-DD HH:mm:ss.SSS | LEVEL | ...)
                # 旧格式：[HH:MM:SS]
                clean_line = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]\s*', '', line)
                # 新格式：移除 loguru 格式的时间戳和级别信息
                # 格式: YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
                clean_line = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', clean_line)
                json_text += clean_line
            
            # 尝试解析JSON
            try:
                json_obj = json.loads(json_text.strip())
                return self.format_json_content(json_obj)
            except json.JSONDecodeError:
                # 多行JSON解析失败，尝试修复
                fixed_json = self.fix_json_string(json_text.strip())
                if fixed_json:
                    try:
                        json_obj = json.loads(fixed_json)
                        return self.format_json_content(json_obj)
                    except json.JSONDecodeError:
                        pass
                return None
            
        except Exception as e:
            # 其他异常也不打印错误信息，直接返回None
            return None
    
    def format_json_content(self, json_obj: dict) -> str:
        """格式化JSON内容为可读形式"""
        try:
            # 提取主要内容，优先选择反思总结，其次是首次总结
            content = None
            
            if "updated_paragraph_latest_state" in json_obj:
                content = json_obj["updated_paragraph_latest_state"]
            elif "paragraph_latest_state" in json_obj:
                content = json_obj["paragraph_latest_state"]
            
            # 如果找到了内容，直接返回（保持换行符为\n）
            if content:
                return content
            
            # 如果没有找到预期的字段，返回整个JSON的字符串表示
            return f"清理后的输出: {json.dumps(json_obj, ensure_ascii=False, indent=2)}"
            
        except Exception as e:
            logger.exception(f"ForumEngine: 格式化JSON时出错: {e}")
            return f"清理后的输出: {json.dumps(json_obj, ensure_ascii=False, indent=2)}"

    def extract_node_content(self, line: str) -> Optional[str]:
        """提取节点内容，去除时间戳、节点名称等前缀"""
        content = line
        
        # 移除时间戳部分：支持旧格式和新格式
        # 旧格式: [HH:MM:SS]
        match_old = re.search(r'\[\d{2}:\d{2}:\d{2}\]\s*(.+)', content)
        if match_old:
            content = match_old.group(1).strip()
        else:
            # 新格式: YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
            match_new = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*(.+)', content)
            if match_new:
                content = match_new.group(1).strip()
        
        if not content:
            return line.strip()
        
        # 移除所有的方括号标签（包括节点名称和应用名称）
        content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # 继续移除可能的多个连续标签
        while re.match(r'^\[.*?\]\s*', content):
            content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # 移除常见前缀（如"首次总结: "、"反思总结: "等）
        prefixes_to_remove = [
            "首次总结: ",
            "反思总结: ",
            "清理后的输出: "
        ]
        
        for prefix in prefixes_to_remove:
            if content.startswith(prefix):
                content = content[len(prefix):]
                break
        
        # 移除可能存在的应用名标签（不在方括号内的）
        app_names = ['INSIGHT', 'MEDIA', 'QUERY']
        for app_name in app_names:
            # 移除单独的APP_NAME（在行首）
            content = re.sub(rf'^{app_name}\s+', '', content, flags=re.IGNORECASE)
        
        # 清理多余的空格
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
   
    def get_file_size(self, file_path: Path) -> int:
        """获取文件大小"""
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except:
            return 0
   
    def get_file_line_count(self, file_path: Path) -> int:
        """获取文件行数"""
        try:
            if not file_path.exists():
                return 0
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except:
            return 0
   
    def read_new_lines(self, file_path: Path, app_name: str) -> List[str]:
        """读取文件中的新行"""
        new_lines = []
       
        try:
            if not file_path.exists():
                return new_lines
           
            current_size = self.get_file_size(file_path)
            last_position = self.file_positions.get(app_name, 0)
           
            # 如果文件变小了，说明被清空了，重新从头开始
            if current_size < last_position:
                last_position = 0
                # 重置JSON捕获状态
                self.capturing_json[app_name] = False
                self.json_buffer[app_name] = []
           
            if current_size > last_position:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    new_lines = new_content.split('\n')
                   
                    # 更新位置
                    self.file_positions[app_name] = f.tell()
                   
                    # 过滤空行
                    new_lines = [line.strip() for line in new_lines if line.strip()]
                   
        except Exception as e:
            logger.exception(f"ForumEngine: 读取{app_name}日志失败: {e}")
       
        return new_lines
   
    def process_lines_for_json(self, lines: List[str], app_name: str) -> List[str]:
        """处理行以捕获多行JSON内容"""
        captured_contents = []
        
        # 初始化状态
        if app_name not in self.capturing_json:
            self.capturing_json[app_name] = False
            self.json_buffer[app_name] = []
        
        for line in lines:
            if not line.strip():
                continue
                
            # 检查是否是目标节点行或包含JSON开始标记的行
            is_target = self.is_target_log_line(line)
            is_json_start = self.is_json_start_line(line)
            
            if is_target or is_json_start:
                if is_json_start:
                    # 开始捕获JSON（即使不是目标节点，只要包含"清理后的输出: {"就处理）
                    self.capturing_json[app_name] = True
                    self.json_buffer[app_name] = [line]
                    self.json_start_line[app_name] = line
                    
                    # 检查是否是单行JSON
                    if line.strip().endswith("}"):
                        # 单行JSON，立即处理
                        content = self.extract_json_content([line])
                        if content:  # 只有成功解析的内容才会被记录
                            # 去除重复的标签和格式化
                            clean_content = self._clean_content_tags(content, app_name)
                            captured_contents.append(f"{clean_content}")
                        self.capturing_json[app_name] = False
                        self.json_buffer[app_name] = []
                        
                elif is_target and self.is_valuable_content(line):
                    # 其他有价值的SummaryNode内容（必须是目标节点且有价值）
                    clean_content = self._clean_content_tags(self.extract_node_content(line), app_name)
                    captured_contents.append(f"{clean_content}")
                    
            elif self.capturing_json[app_name]:
                # 正在捕获JSON的后续行
                self.json_buffer[app_name].append(line)
                
                # 检查是否是JSON结束
                # 先清理时间戳，然后判断清理后的行是否是结束标记
                cleaned_line = line.strip()
                # 清理旧格式时间戳：[HH:MM:SS]
                cleaned_line = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]\s*', '', cleaned_line)
                # 清理新格式时间戳：YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
                cleaned_line = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', cleaned_line)
                cleaned_line = cleaned_line.strip()
                
                # 清理后判断是否是结束标记
                if cleaned_line == "}" or cleaned_line == "] }":
                    # JSON结束，处理完整的JSON
                    content = self.extract_json_content(self.json_buffer[app_name])
                    if content:  # 只有成功解析的内容才会被记录
                        # 去除重复的标签和格式化
                        clean_content = self._clean_content_tags(content, app_name)
                        captured_contents.append(f"{clean_content}")
                    
                    # 重置状态
                    self.capturing_json[app_name] = False
                    self.json_buffer[app_name] = []
        
        return captured_contents
    
    def _trigger_host_speech(self):
        """触发主持人发言（同步执行）"""
        if not HOST_AVAILABLE or self.is_host_generating:
            return
        
        try:
            # 设置生成标志
            self.is_host_generating = True
            
            # 获取缓冲区的5条发言
            recent_speeches = self.agent_speeches_buffer[:5]
            if len(recent_speeches) < 5:
                self.is_host_generating = False
                return
            
            logger.info("ForumEngine: 正在生成主持人发言...")
            
            # 调用主持人生成发言（传入最近5条）
            host_speech = generate_host_speech(recent_speeches)
            
            if host_speech:
                # 写入主持人发言到forum.log
                self.write_to_forum_log(host_speech, "HOST")
                logger.info(f"ForumEngine: 主持人发言已记录")
                
                # 清空已处理的5条发言
                self.agent_speeches_buffer = self.agent_speeches_buffer[5:]
            else:
                logger.error("ForumEngine: 主持人发言生成失败")
            
            # 重置生成标志
            self.is_host_generating = False
                
        except Exception as e:
            logger.exception(f"ForumEngine: 触发主持人发言时出错: {e}")
            self.is_host_generating = False
    
    def _clean_content_tags(self, content: str, app_name: str) -> str:
        """清理内容中的重复标签和多余前缀"""
        if not content:
            return content
            
        # 先去除所有可能的标签格式（包括 [INSIGHT]、[MEDIA]、[QUERY] 等）
        # 使用更强力的清理方式
        all_app_names = ['INSIGHT', 'MEDIA', 'QUERY']
        
        for name in all_app_names:
            # 去除 [APP_NAME] 格式（大小写不敏感）
            content = re.sub(rf'\[{name}\]\s*', '', content, flags=re.IGNORECASE)
            # 去除单独的 APP_NAME 格式
            content = re.sub(rf'^{name}\s+', '', content, flags=re.IGNORECASE)
        
        # 去除任何其他的方括号标签
        content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # 去除可能的重复空格
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
   
    def monitor_logs(self):
        """智能监控日志文件"""
        logger.info("ForumEngine: 论坛创建中...")
       
        # 初始化文件行数和位置 - 记录当前状态作为基线
        for app_name, log_file in self.monitored_logs.items():
            self.file_line_counts[app_name] = self.get_file_line_count(log_file)
            self.file_positions[app_name] = self.get_file_size(log_file)
            self.capturing_json[app_name] = False
            self.json_buffer[app_name] = []
            # logger.info(f"ForumEngine: {app_name} 基线行数: {self.file_line_counts[app_name]}")
       
        while self.is_monitoring:
            try:
                # 同时检测三个log文件的变化
                any_growth = False
                any_shrink = False
                captured_any = False
               
                # 为每个log文件独立处理
                for app_name, log_file in self.monitored_logs.items():
                    current_lines = self.get_file_line_count(log_file)
                    previous_lines = self.file_line_counts.get(app_name, 0)
                   
                    if current_lines > previous_lines:
                        any_growth = True
                        # 立即读取新增内容
                        new_lines = self.read_new_lines(log_file, app_name)
                       
                        # 先检查是否需要触发搜索（只触发一次）
                        if not self.is_searching:
                            for line in new_lines:
                                if line.strip() and 'FirstSummaryNode' in line:
                                    logger.info(f"ForumEngine: 在{app_name}中检测到第一次论坛发表内容")
                                    self.is_searching = True
                                    self.search_inactive_count = 0
                                    # 清空forum.log开始新会话
                                    self.clear_forum_log()
                                    break  # 找到一个就够了，跳出循环
                       
                        # 处理所有新增内容（如果正在搜索状态）
                        if self.is_searching:
                            # 使用新的处理逻辑
                            captured_contents = self.process_lines_for_json(new_lines, app_name)
                            
                            for content in captured_contents:
                                # 将app_name转换为大写作为标签（如 insight -> INSIGHT）
                                source_tag = app_name.upper()
                                self.write_to_forum_log(content, source_tag)
                                # logger.info(f"ForumEngine: 捕获 - {content}")
                                captured_any = True
                                
                                # 将发言添加到缓冲区（格式化为完整的日志行）
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                log_line = f"[{timestamp}] [{source_tag}] {content}"
                                self.agent_speeches_buffer.append(log_line)
                                
                                # 检查是否需要触发主持人发言
                                if len(self.agent_speeches_buffer) >= self.host_speech_threshold and not self.is_host_generating:
                                    # 同步触发主持人发言
                                    self._trigger_host_speech()
                   
                    elif current_lines < previous_lines:
                        any_shrink = True
                        # logger.info(f"ForumEngine: 检测到 {app_name} 日志缩短，将重置基线")
                        # 重置文件位置到新的文件末尾
                        self.file_positions[app_name] = self.get_file_size(log_file)
                        # 重置JSON捕获状态
                        self.capturing_json[app_name] = False
                        self.json_buffer[app_name] = []
                   
                    # 更新行数记录
                    self.file_line_counts[app_name] = current_lines
               
                # 检查是否应该结束当前搜索会话
                if self.is_searching:
                    if any_shrink:
                        # log变短，结束当前搜索会话，重置为等待状态
                        # logger.info("ForumEngine: 日志缩短，结束当前搜索会话，回到等待状态")
                        self.is_searching = False
                        self.search_inactive_count = 0
                        # 重置主持人相关状态
                        self.agent_speeches_buffer = []
                        self.is_host_generating = False
                        # 写入结束标记
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.write_to_forum_log(f"=== ForumEngine 论坛结束 - {end_time} ===", "SYSTEM")
                        # logger.info("ForumEngine: 已重置基线，等待下次FirstSummaryNode触发")
                    elif not any_growth and not captured_any:
                        # 没有增长也没有捕获内容，增加非活跃计数
                        self.search_inactive_count += 1
                        if self.search_inactive_count >= 900:  # 15分钟无活动才结束
                            logger.info("ForumEngine: 长时间无活动，结束论坛")
                            self.is_searching = False
                            self.search_inactive_count = 0
                            # 重置主持人相关状态
                            self.agent_speeches_buffer = []
                            self.is_host_generating = False
                            # 写入结束标记
                            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            self.write_to_forum_log(f"=== ForumEngine 论坛结束 - {end_time} ===", "SYSTEM")
                    else:
                        self.search_inactive_count = 0  # 重置计数器
               
                # 短暂休眠
                time.sleep(1)
               
            except Exception as e:
                logger.exception(f"ForumEngine: 论坛记录中出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(2)
       
        logger.info("ForumEngine: 停止论坛日志文件")
   
    def start_monitoring(self):
        """开始智能监控"""
        if self.is_monitoring:
            logger.info("ForumEngine: 论坛已经在运行中")
            return False
       
        try:
            # 启动监控
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_logs, daemon=True)
            self.monitor_thread.start()
           
            logger.info("ForumEngine: 论坛已启动")
            return True
           
        except Exception as e:
            logger.exception(f"ForumEngine: 启动论坛失败: {e}")
            self.is_monitoring = False
            return False
   
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            logger.info("ForumEngine: 论坛未运行")
            return
       
        try:
            self.is_monitoring = False
           
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2)
           
            # 写入结束标记
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.write_to_forum_log(f"=== ForumEngine 论坛结束 - {end_time} ===", "SYSTEM")
           
            logger.info("ForumEngine: 论坛已停止")
           
        except Exception as e:
            logger.exception(f"ForumEngine: 停止论坛失败: {e}")
   
    def get_forum_log_content(self) -> List[str]:
        """获取forum.log的内容"""
        try:
            if not self.forum_log_file.exists():
                return []
           
            with open(self.forum_log_file, 'r', encoding='utf-8') as f:
                return [line.rstrip('\n\r') for line in f.readlines()]
               
        except Exception as e:
            logger.exception(f"ForumEngine: 读取forum.log失败: {e}")
            return []

    def fix_json_string(self, json_text: str) -> str:
        """修复JSON字符串中的常见问题，特别是未转义的双引号"""
        try:
            # 尝试直接解析，如果成功则返回原文本
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError:
            pass
        
        # 修复未转义的双引号问题
        # 这是一个更智能的修复方法，专门处理字符串值中的双引号
        
        try:
            # 使用状态机方法修复JSON
            # 遍历字符，跟踪是否在字符串值内部
            
            fixed_text = ""
            i = 0
            in_string = False
            escape_next = False
            
            while i < len(json_text):
                char = json_text[i]
                
                if escape_next:
                    # 处理转义字符
                    fixed_text += char
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    # 转义字符
                    fixed_text += char
                    escape_next = True
                    i += 1
                    continue
                
                if char == '"' and not escape_next:
                    # 遇到双引号
                    if in_string:
                        # 在字符串内部，检查下一个字符
                        # 如果下一个字符是冒号或者逗号或者大括号，说明这是字符串结束
                        next_char_pos = i + 1
                        while next_char_pos < len(json_text) and json_text[next_char_pos].isspace():
                            next_char_pos += 1
                        
                        if next_char_pos < len(json_text):
                            next_char = json_text[next_char_pos]
                            if next_char in [':', ',', '}']:
                                # 这是字符串结束，退出字符串状态
                                in_string = False
                                fixed_text += char
                            else:
                                # 这是字符串内部的引号，需要转义
                                fixed_text += '\\"'
                        else:
                            # 文件结束，退出字符串状态
                            in_string = False
                            fixed_text += char
                    else:
                        # 字符串开始
                        in_string = True
                        fixed_text += char
                else:
                    # 其他字符
                    fixed_text += char
                
                i += 1
            
            # 尝试解析修复后的JSON
            try:
                json.loads(fixed_text)
                return fixed_text
            except json.JSONDecodeError:
                # 修复失败，返回None
                return None
                
        except Exception:
            return None

# 全局监控器实例
_monitor_instance = None

def get_monitor() -> LogMonitor:
    """获取全局监控器实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = LogMonitor()
    return _monitor_instance

def start_forum_monitoring():
    """启动ForumEngine智能监控"""
    return get_monitor().start_monitoring()

def stop_forum_monitoring():
    """停止ForumEngine监控"""
    get_monitor().stop_monitoring()

def get_forum_log():
    """获取forum.log内容"""
    return get_monitor().get_forum_log_content()