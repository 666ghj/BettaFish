from types import SimpleNamespace

from flask import Flask
import pytest

from common.cancellation import current_cancellation_token


@pytest.mark.parametrize('status', ['pending', 'running'])
def test_cancel_endpoint_signals_the_exact_task_token(monkeypatch, status):
    from ReportEngine import flask_interface as interface

    task = interface.ReportTask('offline', 'cancel-request')
    task.update_status(status, 30)
    monkeypatch.setattr(interface, 'current_task', task)
    monkeypatch.setattr(interface, 'tasks_registry', {task.task_id: task})
    app = Flask(__name__)
    app.register_blueprint(interface.report_bp, url_prefix='/api/report')

    response = app.test_client().post('/api/report/cancel/cancel-request')

    assert response.status_code == 200
    assert task.cancellation_token.is_cancelled()
    assert task.status == 'cancelled'


def test_report_worker_binds_and_restores_task_cancellation_scope(monkeypatch):
    from ReportEngine import flask_interface as interface

    task = interface.ReportTask('offline', 'worker-context')
    observed = []

    def generate(**kwargs):
        observed.append(current_cancellation_token())
        task.update_status('cancelled', 20)
        current_cancellation_token().raise_if_cancelled()

    monkeypatch.setattr(interface, 'report_agent', SimpleNamespace(
        load_input_files=lambda *args, **kwargs: {'reports': [], 'forum_logs': ''},
        generate_report=generate,
    ))
    monkeypatch.setattr(interface, 'current_task', task)
    monkeypatch.setattr(interface, 'check_engines_ready', lambda run: {'ready': True, 'latest_files': {}})
    interface.run_report_generation(task, 'offline')

    assert observed == [task.cancellation_token]
    assert current_cancellation_token() is None
    assert task.worker_running is False
    assert task.status == 'cancelled'
    assert not any(event['type'] in {'error', 'completed'} for event in task.event_history)
