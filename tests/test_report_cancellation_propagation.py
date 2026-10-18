"""Cancellation must leave retry and model fallback paths immediately."""

from concurrent.futures import CancelledError
from queue import Queue
import threading
from unittest.mock import Mock

import pytest

from ReportEngine.core import TemplateSection
from ReportEngine.ir import IRValidator
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode
from ReportEngine.nodes.template_selection_node import TemplateSelectionNode
from ReportEngine.utils import chart_repair_api
from ReportEngine.utils.chart_validator import ChartRepairer, ChartValidator, ValidationResult
from common.cancellation import CancellationToken, cancellation_scope
from utils import retry_helper


@pytest.mark.parametrize("decorator", [retry_helper.with_retry, retry_helper.with_graceful_retry])
def test_cancelled_error_is_never_retried_or_swallowed(monkeypatch, decorator):
    request = Mock(side_effect=CancelledError("cancelled"))
    request.__name__ = "cancelled_request"
    sleep = Mock()
    monkeypatch.setattr(retry_helper.time, "sleep", sleep)

    with pytest.raises(CancelledError):
        decorator(retry_helper.RetryConfig(max_retries=2))(request)()

    assert request.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("decorator", [retry_helper.with_retry, retry_helper.with_graceful_retry])
def test_retry_backoff_uses_cancellable_token_wait(monkeypatch, decorator):
    class Token:
        cancelled = False

        def wait(self, delay):
            assert delay == 60
            self.cancelled = True
            return True

        def raise_if_cancelled(self):
            if self.cancelled:
                raise CancelledError("cancelled during retry wait")

    token = Token()
    monkeypatch.setattr(retry_helper, "current_cancellation_token", lambda: token, raising=False)
    monkeypatch.setattr(retry_helper, "check_cancelled", token.raise_if_cancelled, raising=False)
    sleep = Mock()
    monkeypatch.setattr(retry_helper.time, "sleep", sleep)
    request = Mock(side_effect=ConnectionError("transient"))
    request.__name__ = "transient_request"

    with pytest.raises(CancelledError):
        decorator(retry_helper.RetryConfig(max_retries=2, initial_delay=60))(request)()

    assert request.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("decorator", [retry_helper.with_retry, retry_helper.with_graceful_retry])
def test_real_token_cancellation_interrupts_long_retry_backoff(decorator):
    waiting = threading.Event()

    class ObservedToken(CancellationToken):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)

    token = ObservedToken()
    outcomes = Queue()
    attempts = []

    @decorator(retry_helper.RetryConfig(max_retries=2, initial_delay=60))
    def request():
        attempts.append(1)
        raise ConnectionError("offline transient error")

    def run():
        try:
            with cancellation_scope(token):
                request()
        except BaseException as exc:
            outcomes.put(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        assert waiting.wait(2), "request did not enter its retry backoff"
        token.cancel()
        worker.join(2)
        assert not worker.is_alive(), "cancelled worker remained in a 60-second backoff"
        assert isinstance(outcomes.get_nowait(), CancelledError)
        assert len(attempts) == 1
    finally:
        token.cancel()
        worker.join(2)


def test_template_selection_does_not_turn_cancellation_into_default_template(tmp_path):
    node = TemplateSelectionNode(None, str(tmp_path))
    node._get_available_templates = Mock(return_value=[{"name": "offline"}])
    node._llm_template_selection = Mock(side_effect=CancelledError("cancelled"))
    node._get_fallback_template = Mock(return_value={"template_name": "fallback"})

    with pytest.raises(CancelledError):
        node.run({"query": "topic"})

    node._get_fallback_template.assert_not_called()


@pytest.mark.parametrize("parse_cancel", [False, True])
def test_chapter_rescue_stops_before_the_next_model(tmp_path, parse_cancel):
    first, second = Mock(), Mock()
    if parse_cancel:
        first.invoke.return_value = "{}"
    else:
        first.invoke.side_effect = CancelledError("cancelled")
    node = ChapterGenerationNode(first, IRValidator(), None,
                                 fallback_llm_clients=[("first", first), ("second", second)],
                                 error_log_dir=tmp_path / "errors")
    if parse_cancel:
        node._parse_chapter = Mock(side_effect=CancelledError("cancelled during parse"))
    section = TemplateSection("Overview", "overview", 10, 2, "Overview", chapter_id="S1")

    with pytest.raises(CancelledError):
        node._attempt_cross_engine_json_rescue(section, {}, "{broken", "run")

    first.invoke.assert_called_once()
    second.invoke.assert_not_called()


@pytest.mark.parametrize("parse_cancel", [False, True])
def test_chapter_structural_repair_preserves_cancellation(tmp_path, parse_cancel):
    client = Mock()
    client.invoke.return_value = "{}"
    if not parse_cancel:
        client.invoke.side_effect = CancelledError("cancelled")
    node = ChapterGenerationNode(client, IRValidator(), None, error_log_dir=tmp_path / "errors")
    if parse_cancel:
        node._parse_chapter = Mock(side_effect=CancelledError("cancelled during parse"))

    with pytest.raises(CancelledError):
        node._attempt_llm_structural_repair({"blocks": []}, ["invalid"])

    client.invoke.assert_called_once()


@pytest.mark.parametrize("factory", ["create_llm_repair_functions", "create_table_repair_functions", "create_wordcloud_repair_functions"])
@pytest.mark.parametrize("cancel_on_return", [False, True])
def test_chart_repair_closures_preserve_cancellation(monkeypatch, factory, cancel_on_return):
    for prefix in ("REPORT_ENGINE", "FORUM_HOST", "INSIGHT_ENGINE", "MEDIA_ENGINE"):
        monkeypatch.setattr(chart_repair_api.settings, f"{prefix}_API_KEY", "offline-placeholder")
        monkeypatch.setattr(chart_repair_api.settings, f"{prefix}_BASE_URL", "https://example.invalid")
        monkeypatch.setattr(chart_repair_api.settings, f"{prefix}_MODEL_NAME", "offline")
    client = Mock()
    monkeypatch.setattr("ReportEngine.llms.LLMClient", Mock(return_value=client))
    repairs = getattr(chart_repair_api, factory)()

    for repair in repairs:
        token = CancellationToken()

        def invoke(*args, **kwargs):
            if cancel_on_return:
                token.cancel()
                return "{}"
            raise CancelledError("cancelled")

        client.invoke.side_effect = invoke
        with cancellation_scope(token), pytest.raises(CancelledError):
            repair({"widgetId": "offline", "type": "widget"}, ["invalid"])


def test_chart_api_repair_does_not_fall_through_to_next_engine():
    first = Mock(side_effect=CancelledError("cancelled"))
    second = Mock()
    repairer = ChartRepairer(ChartValidator(), [first, second])

    with pytest.raises(CancelledError):
        repairer.repair_with_api({"widgetId": "offline"}, ValidationResult(False, ["invalid"], []))

    first.assert_called_once()
    second.assert_not_called()
