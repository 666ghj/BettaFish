from concurrent.futures import CancelledError
import threading

import pytest


def test_cancel_is_idempotent_and_callbacks_can_unregister():
    from common.cancellation import CancellationToken

    token = CancellationToken()
    calls = []
    token.register(lambda: calls.append('kept'))
    remove = token.register(lambda: calls.append('removed'))
    remove()
    token.cancel()
    token.cancel()

    assert calls == ['kept']
    assert token.is_cancelled()
    assert token.wait(0)
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()
    token.register(lambda: calls.append('late'))
    assert calls == ['kept', 'late']


def test_scope_restores_context_and_does_not_cancel_unrelated_thread():
    from common.cancellation import (
        CancellationToken, cancellation_scope, check_cancelled,
        current_cancellation_token,
    )

    outer, inner = CancellationToken(), CancellationToken()
    observed = []
    with cancellation_scope(outer):
        with cancellation_scope(inner):
            inner.cancel()
            with pytest.raises(CancelledError):
                check_cancelled()
        assert current_cancellation_token() is outer
        thread = threading.Thread(target=lambda: observed.append(current_cancellation_token()))
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        assert observed == [None]
    assert current_cancellation_token() is None


def test_cancel_callbacks_do_not_hold_registry_lock():
    from common.cancellation import CancellationToken

    token = CancellationToken()
    registered = threading.Event()

    def callback():
        thread = threading.Thread(target=lambda: (token.register(lambda: None), registered.set()))
        thread.start()
        assert registered.wait(1)
        thread.join(timeout=1)

    token.register(callback)
    token.cancel()
    assert registered.is_set()
