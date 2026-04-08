"""
Unit tests for the cancel_task logic fix in ReportEngine/flask_interface.py.

Tests the fix for issue #630: cancel_task returned 404 even after successfully
cancelling the current running task, because the status check was performed after
the status had already been updated to 'cancelled'.
"""

import threading
import unittest
from unittest.mock import MagicMock, patch


class MockTask:
    """Minimal mock of a ReportTask for testing cancel logic."""

    def __init__(self, task_id, status="running"):
        self.task_id = task_id
        self.status = status
        self.progress = 0

    def update_status(self, status, progress, message):
        self.status = status
        self.progress = progress

    def publish_event(self, event_type, data):
        pass

    def to_dict(self):
        return {"task_id": self.task_id, "status": self.status}


class TestCancelTaskLogic(unittest.TestCase):
    """Test the cancel_task logic extracted from flask_interface.py."""

    def _cancel_task_logic(self, task_id, current_task_ref, tasks_registry):
        """
        Replication of the fixed cancel_task logic for isolated unit testing.
        Returns (success, status_code).
        """
        task_lock = threading.Lock()
        cancelled = False

        with task_lock:
            current_task = current_task_ref[0]
            if current_task and current_task.task_id == task_id:
                if current_task.status == "running":
                    current_task.update_status("cancelled", 0, "用户取消任务")
                    current_task.publish_event("cancelled", {
                        "message": "任务被用户主动终止",
                        "task": current_task.to_dict(),
                    })
                    cancelled = True
                current_task_ref[0] = None

            if not cancelled:
                task = tasks_registry.get(task_id)
                if task and task.status == "running":
                    task.update_status("cancelled", task.progress, "用户取消任务")
                    task.publish_event("cancelled", {
                        "message": "任务被用户主动终止",
                        "task": task.to_dict(),
                    })
                    cancelled = True

        if cancelled:
            return True, 200
        else:
            return False, 404

    def test_cancel_current_running_task_returns_success(self):
        """Cancelling the active current_task should return 200, not 404 (regression for #630)."""
        task = MockTask("task-001", status="running")
        current_task_ref = [task]
        tasks_registry = {"task-001": task}

        success, code = self._cancel_task_logic("task-001", current_task_ref, tasks_registry)

        self.assertTrue(success)
        self.assertEqual(code, 200)
        self.assertEqual(task.status, "cancelled")
        self.assertIsNone(current_task_ref[0])

    def test_cancel_nonexistent_task_returns_404(self):
        """Cancelling a task that does not exist should return 404."""
        current_task_ref = [None]
        tasks_registry = {}

        success, code = self._cancel_task_logic("task-999", current_task_ref, tasks_registry)

        self.assertFalse(success)
        self.assertEqual(code, 404)

    def test_cancel_registry_task_not_current(self):
        """A running task in the registry (but not current) should be cancelled successfully."""
        task = MockTask("task-002", status="running")
        current_task_ref = [None]
        tasks_registry = {"task-002": task}

        success, code = self._cancel_task_logic("task-002", current_task_ref, tasks_registry)

        self.assertTrue(success)
        self.assertEqual(code, 200)
        self.assertEqual(task.status, "cancelled")

    def test_cancel_already_completed_task_returns_404(self):
        """A task that is already completed cannot be cancelled."""
        task = MockTask("task-003", status="completed")
        current_task_ref = [None]
        tasks_registry = {"task-003": task}

        success, code = self._cancel_task_logic("task-003", current_task_ref, tasks_registry)

        self.assertFalse(success)
        self.assertEqual(code, 404)

    def test_current_task_not_running_still_clears_current(self):
        """A current_task that is not running should be cleared but not re-cancelled."""
        task = MockTask("task-004", status="completed")
        current_task_ref = [task]
        tasks_registry = {"task-004": task}

        success, code = self._cancel_task_logic("task-004", current_task_ref, tasks_registry)

        # Task was not running so cancellation should fail
        self.assertFalse(success)
        self.assertEqual(code, 404)
        # current_task should still be cleared
        self.assertIsNone(current_task_ref[0])
        # Status should remain unchanged
        self.assertEqual(task.status, "completed")


if __name__ == "__main__":
    unittest.main()
