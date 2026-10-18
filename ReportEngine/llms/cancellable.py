"""A synchronous iterator over an interruptible, request-owned async transport."""

import asyncio
from concurrent.futures import CancelledError
from queue import SimpleQueue
import threading

from openai import AsyncOpenAI


class CancellableCompletion:
    """Cancel the HTTP task itself, then join it after response/client cleanup.

    Each call owns its loop and client. Closing this request never closes a
    shared Report/repair client or another task's connection pool.
    """

    def __init__(self, client_options, request_options, token):
        self._client_options = client_options
        self._request_options = request_options
        self._token = token
        self._messages = SimpleQueue()
        self._lock = threading.Lock()
        self._loop = None
        self._task = None
        self._slots = None
        self._stop_requested = False
        self._thread = threading.Thread(
            target=self._worker, name="report-model-request", daemon=True,
        )

    def _cancel(self):
        with self._lock:
            if self._stop_requested:
                return
            self._stop_requested = True
            loop, task = self._loop, self._task
        if loop is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # The request loop already completed and closed.

    async def _run(self):
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.current_task()
            stopped = self._stop_requested
        unregister = self._token.register(self._cancel)
        try:
            self._token.raise_if_cancelled()
            if stopped:
                raise asyncio.CancelledError()
            self._slots = asyncio.Semaphore(16)
            client = AsyncOpenAI(**self._client_options)
            response = None
            try:
                response = await client.chat.completions.create(**self._request_options)
                if self._request_options.get("stream"):
                    async for chunk in response:
                        await self._slots.acquire()
                        self._messages.put(("value", chunk))
            finally:
                # The first cancellation can arrive during normal teardown.
                # Shield its own task, then await it before reporting exit.
                cleanup = asyncio.create_task(self._close_request(client, response))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    raise
            # A non-streaming consumer closes after its single value. Publish
            # only after the client has finished closing its sockets.
            if not self._request_options.get("stream"):
                self._messages.put(("value", response))
        finally:
            unregister()

    async def _close_request(self, client, response):
        try:
            if response is not None and self._request_options.get("stream"):
                await response.close()
        finally:
            await client.close()

    def _worker(self):
        try:
            asyncio.run(self._run())
        except asyncio.CancelledError:
            self._messages.put(("error", CancelledError("报告任务已取消")))
        except BaseException as error:
            self._messages.put(("error", error))
        finally:
            self._messages.put(("done", None))

    def __iter__(self):
        self._token.raise_if_cancelled()
        self._thread.start()
        try:
            while True:
                kind, value = self._messages.get()
                if kind == "done":
                    self._token.raise_if_cancelled()
                    return
                if kind == "error":
                    raise value
                self._token.raise_if_cancelled()
                if self._request_options.get("stream"):
                    try:
                        self._loop.call_soon_threadsafe(self._slots.release)
                    except RuntimeError:
                        pass  # All buffered chunks arrived before loop shutdown.
                yield value
        finally:
            self._cancel()
            self._thread.join()
