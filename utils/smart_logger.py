"""
智能日志压缩模块

收集全局日志，合并相同内容（仅时间戳不同）的日志记录，周期性输出压缩后的文件。
"""

from __future__ import annotations

import atexit
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%H:%M:%S")


def _parse_timestamp(ts_str: str) -> datetime:
    """尝试解析日志行中的时间戳，失败则返回当前时间。"""
    for fmt in _TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(ts_str, fmt)
            if fmt == "%H:%M:%S":
                today = datetime.now()
                parsed = parsed.replace(year=today.year, month=today.month, day=today.day)
            return parsed
        except ValueError:
            continue
    return datetime.now()


def _safe_extract_timestamp(line: str) -> Optional[Tuple[str, str]]:
    """
    尝试从类似 `[timestamp] content` 的文本中解析时间戳。

    为避免使用复杂正则导致的灾难性回溯，改用简单的字符串查找。
    返回 (timestamp_str, remaining_content)，若格式不符合则返回 None。
    """
    if not line.startswith("["):
        return None

    closing = line.find("]")
    if closing <= 1:  # 至少需要 "[x]"
        return None

    ts_part = line[1:closing].strip()
    remaining = line[closing + 1 :].lstrip()
    if not ts_part or not remaining:
        return None

    return ts_part, remaining


@dataclass
class AggregatedLog:
    """单条聚合日志条目"""

    level: str
    message: str
    source: str
    first_dt: datetime
    last_dt: datetime
    first_timestamp: str
    last_timestamp: str
    count: int = 1
    samples: Optional[List[str]] = field(default_factory=list)

    def update(self, dt: datetime, ts_str: str, sample_limit: int) -> None:
        self.count += 1
        self.last_dt = dt
        self.last_timestamp = ts_str

        if self.samples is not None:
            if len(self.samples) < sample_limit:
                self.samples.append(ts_str)
            else:
                # 达到上限后不再追加，避免样本无限增长
                self.samples = None


class SmartLogManager:
    """后台日志压缩管理器"""

    def __init__(self, log_dir: Path, flush_interval: int = 60, sample_limit: int = 10):
        self.log_dir = log_dir
        self.compressed_dir = self.log_dir / "compressed"
        self.compressed_dir.mkdir(parents=True, exist_ok=True)
        self.flush_interval = flush_interval
        self.sample_limit = sample_limit

        self._lock = threading.Lock()
        self._cache: Dict[Tuple[str, str, str], AggregatedLog] = {}
        self._stop_event = threading.Event()

        self._flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self._flush_thread.start()

    # ------------------------------------------------------------------ #
    # 记录入口
    # ------------------------------------------------------------------ #

    def record(self, level: str, message: str, *, timestamp: Optional[datetime] = None, source: str = "core") -> None:
        if not message:
            return

        dt = timestamp or datetime.now()
        ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        key = (source, level, message)

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                entry = AggregatedLog(
                    level=level,
                    message=message,
                    source=source,
                    first_dt=dt,
                    last_dt=dt,
                    first_timestamp=ts_str,
                    last_timestamp=ts_str,
                    samples=[ts_str],
                )
                self._cache[key] = entry
            else:
                entry.update(dt, ts_str, self.sample_limit)

    def record_manual_line(self, line: str, source: str) -> None:
        line = line.strip()
        if not line:
            return

        parsed = _safe_extract_timestamp(line)
        if parsed is None:
            message = line
            dt = datetime.now()
        else:
            ts_str, message = parsed
            dt = _parse_timestamp(ts_str)

        level = "ERROR" if "error" in message.lower() else "INFO"
        self.record(level, message, timestamp=dt, source=source)

    # ------------------------------------------------------------------ #
    # 刷新与停止
    # ------------------------------------------------------------------ #

    def flush(self) -> None:
        with self._lock:
            if not self._cache:
                return
            snapshot = self._cache
            self._cache = {}

        grouped: Dict[Tuple[str, str], List[AggregatedLog]] = {}
        for entry in snapshot.values():
            date_key = entry.first_dt.strftime("%Y-%m-%d")
            grouped.setdefault((entry.source, date_key), []).append(entry)

        for (source, date_key), entries in grouped.items():
            file_path = self.compressed_dir / f"{source}_{date_key}.log"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as f:
                for entry in sorted(entries, key=lambda item: item.first_dt):
                    self._write_entry(f, entry)

    def stop(self) -> None:
        self._stop_event.set()
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)
        self.flush()

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    def _periodic_flush(self) -> None:
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.flush_interval):
                break
            try:
                self.flush()
            except Exception as exc:  # pragma: no cover - 防止后台线程异常退出
                # 避免递归调用 loguru，再退回标准错误输出
                print(f"[SmartLogManager] 压缩日志定时刷新失败: {exc}", flush=True)

    def _write_entry(self, file_obj, entry: AggregatedLog) -> None:
        source_tag = f"[{entry.source}]" if entry.source else "[core]"
        if entry.count == 1:
            file_obj.write(f"[{entry.first_timestamp}] {entry.level} {source_tag} {entry.message}\n")
            return

        file_obj.write(f"[{entry.level}] {source_tag} {entry.message}\n")
        file_obj.write(f"  ↳ 重复 {entry.count} 次: {entry.first_timestamp} -> {entry.last_timestamp}\n")

        samples = entry.samples[:] if entry.samples else []
        if samples and samples[-1] != entry.last_timestamp:
            samples.append(entry.last_timestamp)

        if samples:
            label = "时间戳" if entry.count <= self.sample_limit else f"采样（最多 {len(samples)} 条）"
            file_obj.write(f"  ↳ {label}: {', '.join(samples)}\n")

        file_obj.write("\n")

    # ------------------------------------------------------------------ #
    # Loguru sink
    # ------------------------------------------------------------------ #

    def loguru_sink(self, message) -> None:
        record = message.record
        level = record["level"].name
        text = record["message"]
        dt = record["time"].datetime
        source = record["extra"].get("component") if record["extra"] else None
        self.record(level, text, timestamp=dt, source=source or "core")


_SMART_LOGGER: Optional[SmartLogManager] = None
_LOGGER_SINK_ID: Optional[int] = None


def setup_smart_logging(log_dir: Path, flush_interval: int = 60, sample_limit: int = 10) -> SmartLogManager:
    """初始化全局智能日志压缩器（单例）。"""
    global _SMART_LOGGER, _LOGGER_SINK_ID

    if _SMART_LOGGER is not None:
        return _SMART_LOGGER

    manager = SmartLogManager(log_dir, flush_interval=flush_interval, sample_limit=sample_limit)
    sink_id = logger.add(manager.loguru_sink, level="INFO")

    _SMART_LOGGER = manager
    _LOGGER_SINK_ID = sink_id

    atexit.register(manager.stop)
    return manager


def get_smart_logger() -> Optional[SmartLogManager]:
    return _SMART_LOGGER


def smart_log(level: str, message: str, *, source: str = "manual") -> None:
    """提供给外部模块的手动记录接口"""
    manager = get_smart_logger()
    if manager is None:
        return
    manager.record(level.upper(), message, source=source)


def smart_log_line(line: str, *, source: str = "manual") -> None:
    """针对已有日志文本（如子进程输出）的快捷入口"""
    manager = get_smart_logger()
    if manager is None:
        return
    manager.record_manual_line(line, source)


__all__ = [
    "setup_smart_logging",
    "get_smart_logger",
    "smart_log",
    "smart_log_line",
    "SmartLogManager",
]

