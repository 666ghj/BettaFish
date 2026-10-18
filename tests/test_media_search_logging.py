from unittest.mock import Mock

import pytest
import requests

from MediaEngine.tools import search as search_module


@pytest.mark.parametrize(
    ("client_type", "request_method"),
    [
        (search_module.BochaMultimodalSearch, "post"),
        (search_module.AnspireAISearch, "get"),
    ],
)
def test_search_network_failure_does_not_dump_auth_header(
    monkeypatch, client_type, request_method
):
    secret = "test-secret-that-must-not-be-logged"
    client = client_type(api_key=secret)
    fake_logger = Mock()
    monkeypatch.setattr(search_module, "logger", fake_logger)
    monkeypatch.setattr(
        search_module.requests,
        request_method,
        Mock(side_effect=requests.exceptions.ReadTimeout("timed out")),
    )

    undecorated_search = type(client)._search_internal.__wrapped__
    with pytest.raises(requests.exceptions.ReadTimeout):
        undecorated_search(client, query="BettaFish")

    fake_logger.exception.assert_not_called()
    fake_logger.warning.assert_called_once()
    assert secret not in str(fake_logger.mock_calls)
