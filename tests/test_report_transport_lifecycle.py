"""Report requests own their cancellation, socket and worker lifecycle."""

import asyncio
from concurrent.futures import CancelledError
from threading import Event
from time import monotonic

import httpx
import pytest

from common.cancellation import CancellationToken, cancellation_scope
from ReportEngine.llms import base as llm_module
from tests.report_network_test_support import BackgroundCall, LocalCompletionServer, ResponseStep


@pytest.fixture(autouse=True)
def bounded_request_failures(monkeypatch):
    monkeypatch.setattr(llm_module.LLM_RETRY_CONFIG, "max_retries", 0)


@pytest.fixture
def transports(monkeypatch):
    """Observe real request-owned workers without replacing their transport."""
    actual = llm_module.CancellableCompletion
    created = []

    def capture(*args, **kwargs):
        completion = actual(*args, **kwargs)
        created.append(completion)
        return completion

    monkeypatch.setattr(llm_module, "CancellableCompletion", capture)
    return created


def _client(server):
    client = llm_module.LLMClient("offline-key", "offline", server.base_url)
    client.timeout = 3
    return client


def _scoped(token, callback):
    with cancellation_scope(token):
        return callback()


def _assert_cancelled(caller):
    assert caller.done.wait(2), "The cancelled request did not exit"
    caller.thread.join(1)
    assert not caller.thread.is_alive()
    assert isinstance(caller.error, CancelledError), repr(caller.error)


@pytest.mark.parametrize("method", ["invoke", "stream", "joined_stream"])
def test_pre_cancelled_report_request_never_reaches_http_peer(method, transports):
    token = CancellationToken()
    token.cancel()
    with LocalCompletionServer() as server:
        client = _client(server)

        def request():
            if method == "invoke":
                return client.invoke("offline", "offline")
            if method == "joined_stream":
                return client.stream_invoke_to_string("offline", "offline")
            return list(client.stream_invoke("offline", "offline"))

        caller = BackgroundCall(lambda: _scoped(token, request))
        try:
            _assert_cancelled(caller)
            assert server.request_count == 0
            assert not transports, "A cancelled request allocated a model worker"
            assert not server.errors
        finally:
            server.close()
            caller.done.wait(3)
            client.client.close()


def test_cancelling_one_concurrent_request_keeps_other_token_and_socket_live(transports):
    first = ResponseStep("before_token")
    second = ResponseStep("after_token", "second task delta")
    token_a, token_b = CancellationToken(), CancellationToken()
    consumed_b = Event()

    with LocalCompletionServer(first, second) as server:
        client = _client(server)

        def consume(token, consumed=None):
            def request():
                for _chunk in client.stream_invoke("offline", "offline"):
                    if consumed is not None:
                        consumed.set()

            return _scoped(token, request)

        caller_a = BackgroundCall(lambda: consume(token_a))
        caller_b = None
        try:
            assert first.headers_sent.wait(5), "Task A did not reach its stalled socket"
            caller_b = BackgroundCall(lambda: consume(token_b, consumed_b))
            assert consumed_b.wait(5), "Task B did not receive its real SSE delta"

            BackgroundCall(token_a.cancel).finish(2)
            _assert_cancelled(caller_a)
            assert first.peer_closed.wait(2), "Task A left its HTTP connection open"
            assert not token_b.is_cancelled()
            assert not caller_b.done.wait(0.15), "Cancelling task A also ended task B"
            assert not second.peer_closed.is_set(), "Task A closed task B's socket"
            assert not transports[0]._thread.is_alive()
            assert transports[1]._thread.is_alive()

            BackgroundCall(token_b.cancel).finish(2)
            _assert_cancelled(caller_b)
            assert second.peer_closed.wait(2)
            assert not any(item._thread.is_alive() for item in transports)
            assert server.request_count == 2
            assert not server.errors
        finally:
            token_a.cancel()
            token_b.cancel()
            server.close()
            caller_a.done.wait(3)
            if caller_b is not None:
                caller_b.done.wait(3)
            client.client.close()


def test_consumer_closing_report_stream_joins_worker_and_closes_real_socket(transports):
    step = ResponseStep("after_token", "only wanted delta")
    token = CancellationToken()
    with LocalCompletionServer(step) as server:
        client = _client(server)

        def consume_one():
            with cancellation_scope(token):
                stream = client.stream_invoke("offline", "offline")
                try:
                    return next(stream)
                finally:
                    stream.close()

        caller = BackgroundCall(consume_one)
        try:
            assert caller.finish(5) == "only wanted delta"
            assert not token.is_cancelled(), "Closing a consumer cancelled its task token"
            assert step.peer_closed.wait(2), "Closing the consumer left the SSE socket open"
            assert len(transports) == 1
            assert not transports[0]._thread.is_alive(), "Consumer close returned before worker teardown"
            assert server.request_count == 1
            assert not server.errors
        finally:
            token.cancel()
            server.close()
            caller.done.wait(3)
            client.client.close()


def test_invoke_waits_for_async_client_close_before_returning(monkeypatch, transports):
    close_entered, release_close, close_finished = Event(), Event(), Event()
    original_aclose = httpx.AsyncClient.aclose

    async def controlled_aclose(client):
        close_entered.set()
        deadline = monotonic() + 5
        try:
            while not release_close.is_set():
                if monotonic() >= deadline:
                    raise AssertionError("The test did not release async client cleanup")
                await asyncio.sleep(0.01)
            await original_aclose(client)
            close_finished.set()
        finally:
            # A failed assertion or cancellation must still release real sockets.
            if not client.is_closed:
                await original_aclose(client)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", controlled_aclose)
    token = CancellationToken()
    with LocalCompletionServer(ResponseStep("json", "complete response")) as server:
        client = _client(server)
        caller = BackgroundCall(lambda: _scoped(token, lambda: client.invoke("offline", "offline")))
        try:
            assert close_entered.wait(5), "The real response did not reach async client cleanup"
            assert not caller.done.wait(0.15), "invoke returned before async cleanup finished"
            assert not close_finished.is_set()
            release_close.set()
            assert caller.finish(3) == "complete response"
            assert close_finished.is_set()
            assert not token.is_cancelled()
            assert len(transports) == 1
            assert not transports[0]._thread.is_alive()
            assert server.request_count == 1
            assert not server.errors
        finally:
            release_close.set()
            token.cancel()
            server.close()
            caller.done.wait(3)
            client.client.close()


def test_cancel_during_client_cleanup_waits_for_real_keepalive_socket_close(monkeypatch, transports):
    close_entered, release_close, close_finished = Event(), Event(), Event()
    original_aclose = httpx.AsyncClient.aclose
    held_clients = []

    async def controlled_aclose(client):
        # Keep the client alive: garbage collection must not stand in for the
        # transport's explicit cleanup, or it could hide this cancellation bug.
        held_clients.append(client)
        close_entered.set()
        deadline = monotonic() + 5
        while not release_close.is_set():
            if monotonic() >= deadline:
                raise AssertionError("The test did not release async client cleanup")
            await asyncio.sleep(0.01)
        await original_aclose(client)
        close_finished.set()

    monkeypatch.setattr(httpx.AsyncClient, "aclose", controlled_aclose)
    step = ResponseStep("keepalive_json", "response before cleanup")
    token = CancellationToken()
    with LocalCompletionServer(step) as server:
        client = _client(server)
        caller = BackgroundCall(lambda: _scoped(token, lambda: client.invoke("offline", "offline")))
        try:
            assert close_entered.wait(5), "The request did not begin async client cleanup"
            assert step.token_sent.wait(2), "No complete JSON response reached the client"
            assert not step.peer_closed.is_set(), "The peer closed before client cleanup began"
            BackgroundCall(token.cancel).finish(2)
            assert not caller.done.wait(0.15), "Cancellation returned before client cleanup completed"
            assert not close_finished.is_set()
            assert not step.peer_closed.is_set()

            release_close.set()
            _assert_cancelled(caller)
            assert close_finished.is_set(), "Cancellation interrupted explicit client cleanup"
            assert step.peer_closed.wait(2), "The keepalive HTTP socket remained open"
            assert len(transports) == 1
            assert not transports[0]._thread.is_alive()
            assert server.request_count == 1
            assert not server.errors
        finally:
            release_close.set()
            token.cancel()
            caller.done.wait(3)
            # This fallback runs only after the assertions. It bounds resource
            # cleanup on the failing implementation without hiding that failure.
            for held in held_clients:
                if not held.is_closed:
                    try:
                        asyncio.run(original_aclose(held))
                    except RuntimeError:
                        pass  # The regression can destroy its loop before close.
            server.close()
            client.client.close()


def test_cancellation_after_worker_completion_is_not_mistaken_for_stream_success(transports):
    token = CancellationToken()
    with LocalCompletionServer(ResponseStep("stream", "completed delta")) as server:
        client = _client(server)

        def consume():
            with cancellation_scope(token):
                stream = client.stream_invoke("offline", "offline")
                try:
                    assert next(stream) == "completed delta"
                    assert len(transports) == 1
                    transports[0]._thread.join(2)
                    assert not transports[0]._thread.is_alive(), "The request worker did not finish naturally"
                    token.cancel()
                    return next(stream)
                finally:
                    stream.close()

        caller = BackgroundCall(consume)
        try:
            _assert_cancelled(caller)
            assert server.request_count == 1
            assert not server.errors
        finally:
            token.cancel()
            server.close()
            caller.done.wait(3)
            client.client.close()
