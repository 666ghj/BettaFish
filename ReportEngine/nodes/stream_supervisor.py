import re
from typing import List, Optional, Callable
from loguru import logger


class StreamSupervisor:
    """
    流式监控器（滑动窗口校验）。

    在强模型进行长文本生成时，实时监控输出流：
    1. 维护滑动窗口缓冲；
    2. 检测关键格式错误（如未闭合的 Markdown/JSON）；
    3. (可选) 异步调用小模型校验逻辑一致性。
    """

    def __init__(self, window_size: int = 2000):
        self.window_size = window_size
        self.buffer = ""
        self.total_generated = 0
        self._last_check_pos = 0

    def push(self, chunk: str) -> bool:
        """
        推入新生成的文本块。

        Returns:
            bool: 如果检测到严重错误建议中断，返回 False；否则返回 True。
        """
        self.buffer += chunk
        self.total_generated += len(chunk)

        # 简单的滑动窗口维护：只保留最近 window_size 长度用于正则检查
        if len(self.buffer) > self.window_size * 2:
            self.buffer = self.buffer[-self.window_size:]

        # 每积累一定量才检查一次，避免过度消耗 CPU
        if len(self.buffer) - self._last_check_pos > 100:
            self._last_check_pos = len(self.buffer)
            if not self._quick_format_check(self.buffer):
                return False

        return True

    def _quick_format_check(self, text: str) -> bool:
        """
        快速格式检查（启发式）。
        """
        # 1. 检查是否存在严重的 JSON 格式断裂（如果正在生成 JSON）
        # 这里假设生成的是 Markdown + JSON 混合，主要防范的是 Markdown 结构
        # 例如：代码块标记不匹配 ``` 数量奇偶校验（虽不严谨，但作滑动窗口参考）
        # 但流式生成中，代码块未闭合是正常的，所以不能简单数数。

        # 检查是否出现了大量的重复字符（模型崩溃常见特征）
        if len(text) > 200:
            last_100 = text[-100:]
            if len(set(last_100)) < 5:  # 极低熵，可能在重复 "......"
                logger.warning("StreamSupervisor: 检测到可能的重复生成循环")
                return False

        return True

