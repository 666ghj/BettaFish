# agno_team/forum_state.py
# 论坛共享状态：替代 BettaFish 的 logs/forum.log 文件
# 三个 Agent 通过这个对象传递段落总结，ForumHost 通过它获取上下文并写回引导发言

from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable, Awaitable


@dataclass
class ForumEntry:
    """单条论坛发言"""
    timestamp: float
    role: str  # "INSIGHT" / "MEDIA" / "QUERY" / "HOST" / "SYSTEM"
    content: str

    def format_human(self) -> str:
        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        return f"[{ts}] [{self.role}] {self.content}"


class ForumState:
    """
    线程/协程安全的论坛状态。
    提供两个核心能力：
    1. write_to_forum(role, content): 任何 agent 都可以写入段落总结，
       自动触发 Host 阈值检查
    2. get_latest_host_speech(): 任何 agent 在生成 SummaryNode 前可以读取
       最新的主持人引导发言，塞进 prompt 前缀
    """

    def __init__(
        self,
        host_threshold: int = 5,
        host_callback: Optional[Callable[[List[ForumEntry]], Awaitable[Optional[str]]]] = None,
    ):
        """
        Args:
            host_threshold: 累计多少条 agent 发言触发一次 Host 总结，默认 5
            host_callback: Host LLM 调用函数，接收最近 N 条发言，返回主持人发言文本
        """
        self.entries: List[ForumEntry] = []
        self.host_threshold = host_threshold
        self.host_callback = host_callback

        self._agent_speech_count = 0
        self._host_lock = asyncio.Lock()
        self._is_host_generating = False

    async def write(self, role: str, content: str) -> None:
        """
        写入一条发言。如果是 agent 发言（INSIGHT/MEDIA/QUERY），
        累加计数；累计到阈值时自动触发 Host 总结。
        """
        entry = ForumEntry(timestamp=time.time(), role=role, content=content)
        self.entries.append(entry)
        print(f"📝 [{role}] {content[:80]}...")

        if role in ("INSIGHT", "MEDIA", "QUERY"):
            self._agent_speech_count += 1

            if (
                self._agent_speech_count >= self.host_threshold
                and not self._is_host_generating
                and self.host_callback is not None
            ):
                # 触发 Host 总结
                async with self._host_lock:
                    if self._agent_speech_count >= self.host_threshold and not self._is_host_generating:
                        self._is_host_generating = True
                        try:
                            recent = self._get_recent_agent_entries(self.host_threshold)
                            host_speech = await self.host_callback(recent)
                            if host_speech:
                                host_entry = ForumEntry(
                                    timestamp=time.time(),
                                    role="HOST",
                                    content=host_speech,
                                )
                                self.entries.append(host_entry)
                                self._agent_speech_count = 0
                                print(f"\n🎤 [HOST] {host_speech[:200]}...\n")
                        finally:
                            self._is_host_generating = False

    def get_latest_host_speech(self) -> Optional[str]:
        """获取最新的 HOST 发言（供 agent 在 SummaryNode 前读取）"""
        for entry in reversed(self.entries):
            if entry.role == "HOST":
                return entry.content
        return None

    def _get_recent_agent_entries(self, n: int) -> List[ForumEntry]:
        """获取最近 n 条 agent 发言（不包括 HOST/SYSTEM）"""
        result = []
        for entry in reversed(self.entries):
            if entry.role in ("INSIGHT", "MEDIA", "QUERY"):
                result.append(entry)
                if len(result) >= n:
                    break
        result.reverse()
        return result

    def get_all_host_speeches(self) -> List[ForumEntry]:
        """获取所有 HOST 发言"""
        return [e for e in self.entries if e.role == "HOST"]

    def format_full_log(self) -> str:
        """格式化完整论坛日志为字符串（供 ReportAgent 消费）"""
        return "\n".join(e.format_human() for e in self.entries)

    def save_to_file(self, path: Path) -> None:
        """落盘备份"""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self.entries]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def format_host_speech_for_prompt(host_speech: str) -> str:
    """格式化 HOST 发言以插入 agent prompt 前缀（与 BettaFish forum_reader.py 一致）"""
    if not host_speech:
        return ""
    return f"""
### 论坛主持人最新总结
以下是论坛主持人对各 Agent 讨论的最新总结和引导，请参考其中的观点和建议：

{host_speech}

---
"""
