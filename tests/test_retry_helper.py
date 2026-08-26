from unittest.mock import patch

import pytest
import requests

from utils.retry_helper import RetryConfig, with_graceful_retry, with_retry


class HTTPStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class ResponseStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_permanent_http_errors_fail_without_retry(status_code):
    calls = 0
    config = RetryConfig(max_retries=3, initial_delay=1)

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        raise HTTPStatusError(status_code)

    with patch("utils.retry_helper.time.sleep") as sleep:
        with pytest.raises(HTTPStatusError):
            request()

    assert calls == 1
    sleep.assert_not_called()


def test_transient_http_error_is_retried():
    calls = 0
    config = RetryConfig(max_retries=2, initial_delay=1)

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPStatusError(503)
        return "ok"

    with patch("utils.retry_helper.time.sleep") as sleep:
        assert request() == "ok"

    assert calls == 2
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("status_code", [408, 409, 424, 425, 429])
def test_retryable_client_errors_are_retried(status_code):
    calls = 0
    config = RetryConfig(max_retries=2, initial_delay=1)

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPStatusError(status_code)
        return "ok"

    with patch("utils.retry_helper.time.sleep") as sleep:
        assert request() == "ok"

    assert calls == 2
    sleep.assert_called_once_with(1)


def test_status_code_is_read_from_exception_response():
    calls = 0
    config = RetryConfig(max_retries=2, initial_delay=1)

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        raise ResponseStatusError(404)

    with patch("utils.retry_helper.time.sleep") as sleep:
        with pytest.raises(ResponseStatusError):
            request()

    assert calls == 1
    sleep.assert_not_called()


def test_requests_http_error_fails_without_retry():
    calls = 0
    config = RetryConfig(max_retries=3, initial_delay=1)
    response = requests.Response()
    response.status_code = 404
    response.url = "https://example.invalid/models/missing"

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        response.raise_for_status()

    with patch("utils.retry_helper.time.sleep") as sleep:
        with pytest.raises(requests.HTTPError):
            request()

    assert calls == 1
    sleep.assert_not_called()


def test_exception_without_http_status_keeps_existing_retry_behavior():
    calls = 0
    config = RetryConfig(max_retries=1, initial_delay=0.5)

    @with_retry(config)
    def request():
        nonlocal calls
        calls += 1
        raise ConnectionError("connection reset")

    with patch("utils.retry_helper.time.sleep") as sleep:
        with pytest.raises(ConnectionError):
            request()

    assert calls == 2
    sleep.assert_called_once_with(0.5)


def test_graceful_retry_returns_default_immediately_for_permanent_error():
    calls = 0
    config = RetryConfig(max_retries=3, initial_delay=1)

    @with_graceful_retry(config, default_return=[])
    def request():
        nonlocal calls
        calls += 1
        raise HTTPStatusError(404)

    with patch("utils.retry_helper.time.sleep") as sleep:
        assert request() == []

    assert calls == 1
    sleep.assert_not_called()


def test_graceful_retry_returns_default_after_transient_errors_are_exhausted():
    calls = 0
    config = RetryConfig(max_retries=2, initial_delay=1)

    @with_graceful_retry(config, default_return=[])
    def request():
        nonlocal calls
        calls += 1
        raise HTTPStatusError(503)

    with patch("utils.retry_helper.time.sleep") as sleep:
        assert request() == []

    assert calls == 3
    assert sleep.call_args_list == [((1,),), ((2,),)]
