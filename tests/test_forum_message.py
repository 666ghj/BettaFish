import unittest

from ForumEngine.monitor import ForumMessage, LogMonitor


class ForumMessageTests(unittest.TestCase):
    def test_round_trip_preserves_source_content_and_evidence(self):
        message = ForumMessage(
            content="第一行\n第二行",
            source="query",
            timestamp="12:34:56",
            referenced_evidence_ids=["e1", "e1", "e2"],
        )

        parsed = ForumMessage.from_log_line(message.to_log_line())

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.content, message.content)
        self.assertEqual(parsed.source, "QUERY")
        self.assertEqual(parsed.timestamp, message.timestamp)
        self.assertEqual(parsed.referenced_evidence_ids, ["e1", "e2"])

    def test_legacy_line_without_evidence_is_supported(self):
        parsed = ForumMessage.from_log_line("[01:02:03] [MEDIA] legacy content")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.content, "legacy content")
        self.assertEqual(parsed.referenced_evidence_ids, [])

    def test_invalid_evidence_json_does_not_drop_content(self):
        parsed = ForumMessage.from_log_line(
            "[01:02:03] [INSIGHT] [EVIDENCE_IDS:[bad]] retained content"
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.content, "retained content")
        self.assertEqual(parsed.referenced_evidence_ids, [])

    def test_unstructured_line_is_rejected(self):
        self.assertIsNone(ForumMessage.from_log_line("plain text"))


class LogMonitorTests(unittest.TestCase):
    def test_real_ansi_loguru_multiline_json_is_captured(self):
        monitor = LogMonitor()
        lines = [
            "[12:34:56] \x1b[32m2026-09-09 12:34:56.123\x1b[0m | "
            "\x1b[1mINFO    \x1b[0m | "
            "\x1b[36mQueryEngine.nodes.summary_node\x1b[0m:"
            "\x1b[36mprocess_output\x1b[0m:\x1b[36m134\x1b[0m - "
            "\x1b[1m清理后的输出: {\x1b[0m",
            '[12:34:56] "paragraph_latest_state": "第一行\\n第二行"',
            "[12:34:56] }\x1b[0m",
        ]

        captured = monitor.process_lines_for_json(lines, "query")

        self.assertEqual(captured, ["第一行 第二行"])

    def test_ansi_error_line_is_not_treated_as_summary_content(self):
        monitor = LogMonitor()
        line = (
            "[12:34:56] \x1b[31m2026-09-09 12:34:56.123\x1b[0m | "
            "\x1b[31mERROR   \x1b[0m | "
            "\x1b[36mQueryEngine.nodes.summary_node\x1b[0m:run:1 - "
            "清理后的输出: {"
        )

        self.assertEqual(monitor.get_log_level(line), "ERROR")
        self.assertFalse(monitor.is_target_log_line(line))


if __name__ == "__main__":
    unittest.main()
