"""Task-local cancellation shared by model requests and retry waits."""

from concurrent.futures import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
import threading
from typing import Callable, Optional

from loguru import logger


class CancellationToken:
    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks = set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self):
        if self.is_cancelled():
            raise CancelledError("报告任务已取消")

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._event.wait(timeout)

    def cancel(self):
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            callbacks = tuple(self._callbacks)
            self._callbacks.clear()
        for callback in callbacks:
            self._notify(callback)

    def register(self, callback: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            cancelled = self._event.is_set()
            if not cancelled:
                self._callbacks.add(callback)
        if cancelled:
            self._notify(callback)

        def unregister():
            with self._lock:
                self._callbacks.discard(callback)

        return unregister

    @staticmethod
    def _notify(callback):
        try:
            callback()
        except Exception:
            logger.warning("取消回调执行失败")


_current_token: ContextVar[Optional[CancellationToken]] = ContextVar(
    "bettafish_cancellation_token", default=None,
)


@contextmanager
def cancellation_scope(token: CancellationToken):
    binding = _current_token.set(token)
    try:
        yield token
    finally:
        _current_token.reset(binding)


def current_cancellation_token() -> Optional[CancellationToken]:
    return _current_token.get()


def check_cancelled():
    token = current_cancellation_token()
    if token is not None:
        token.raise_if_cancelled()
