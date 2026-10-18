"""Small real HTTP peer for cancellation tests; never uses an external service."""

from __future__ import annotations

import json
import socket
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable


@dataclass
class ResponseStep:
    mode: str
    content: str = "offline response"
    received: Event = field(default_factory=Event)
    headers_sent: Event = field(default_factory=Event)
    token_sent: Event = field(default_factory=Event)
    peer_closed: Event = field(default_factory=Event)
    finished: Event = field(default_factory=Event)
    closed_at: float | None = None


class LocalCompletionServer:
    """Serve a finite response script and observe client EOF on stalled sockets."""

    def __init__(self, *steps: ResponseStep):
        self._steps = deque(steps)
        self._all_steps = steps
        self._lock = Lock()
        self._sockets: set[socket.socket] = set()
        self._closed = False
        self.request_count = 0
        self.errors: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                step = None
                with owner._lock:
                    owner._sockets.add(self.connection)
                    owner.request_count += 1
                    if owner._steps:
                        step = owner._steps.popleft()
                try:
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    if step is None:
                        owner.errors.append("Unexpected additional completion request")
                        self._json(500, {"error": {"message": "unexpected local request"}})
                        return
                    step.received.set()
                    if step.mode == "before_headers":
                        self._observe_client_close(step)
                        return
                    if step.mode == "retry":
                        self._json(503, {"error": {"message": "temporary local failure", "type": "server_error"}})
                        return
                    if step.mode in {"json", "keepalive_json"}:
                        self._json(200, {
                            "id": "offline", "object": "chat.completion", "created": 0,
                            "model": "offline", "choices": [{"index": 0,
                                "message": {"role": "assistant", "content": step.content},
                                "finish_reason": "stop"}],
                        }, keepalive=step.mode == "keepalive_json")
                        step.headers_sent.set()
                        step.token_sent.set()
                        if step.mode == "keepalive_json":
                            self._observe_client_close(step)
                        return
                    if step.mode == "before_json_body":
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", "1024")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.wfile.flush()
                        step.headers_sent.set()
                        self._observe_client_close(step)
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.flush()
                    step.headers_sent.set()
                    if step.mode == "before_token":
                        self._observe_client_close(step)
                        return
                    self._chunk(("data: " + json.dumps({
                        "id": "offline", "object": "chat.completion.chunk", "created": 0,
                        "model": "offline", "choices": [{"index": 0,
                            "delta": {"content": step.content}, "finish_reason": None}],
                    }) + "\n\n").encode("utf-8"))
                    step.token_sent.set()
                    if step.mode == "after_token":
                        self._observe_client_close(step)
                        return
                    if step.mode != "stream":
                        owner.errors.append(f"Unknown local response mode: {step.mode}")
                        return
                    self._chunk(b"data: [DONE]\n\n")
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    # Client teardown also interrupts our deliberately stalled peer.
                    pass
                finally:
                    self.close_connection = True
                    with owner._lock:
                        owner._sockets.discard(self.connection)
                    if step is not None:
                        step.finished.set()

            def _json(self, status, value, *, keepalive=False):
                body = json.dumps(value).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "keep-alive" if keepalive else "close")
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

            def _chunk(self, data):
                self.wfile.write(f"{len(data):x}\r\n".encode("ascii") + data + b"\r\n")
                self.wfile.flush()

            def _observe_client_close(self, step):
                # A returned caller alone is insufficient: the actual HTTP peer
                # must receive EOF/reset while the server has sent no more data.
                self.connection.settimeout(10)
                try:
                    if self.connection.recv(1) != b"":
                        owner.errors.append("Unexpected bytes after completion request")
                        return
                except (ConnectionResetError, ConnectionAbortedError):
                    pass
                except OSError:
                    return
                step.closed_at = monotonic()
                step.peer_closed.set()

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = Thread(target=lambda: self._server.serve_forever(poll_interval=0.05), daemon=True)
        self._thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    def close(self):
        # Only sockets accepted by this test-owned listener are touched.
        with self._lock:
            if self._closed:
                return
            self._closed = True
            sockets = tuple(self._sockets)
        for connection in sockets:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        for step in self._all_steps:
            if step.received.is_set():
                step.finished.wait(2)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class BackgroundCall:
    """Run a synchronous caller without hiding its result or exception."""

    def __init__(self, target: Callable):
        self.done = Event()
        self.error: BaseException | None = None
        self.result = None

        def run():
            try:
                self.result = target()
            except BaseException as error:
                self.error = error
            finally:
                self.done.set()

        self.thread = Thread(target=run, daemon=True)
        self.thread.start()

    def finish(self, timeout=5):
        assert self.done.wait(timeout), "The local completion caller did not exit"
        self.thread.join(timeout=1)
        if self.error:
            raise self.error
        return self.result
