from pathlib import Path
import unittest


class FrontendRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (
            Path(__file__).resolve().parents[1] / "templates" / "index.html"
        ).read_text(encoding="utf-8")

    def test_main_page_uses_inline_favicon(self):
        self.assertIn('<link rel="icon" href="data:,">', self.template)

    def test_unload_cleanup_is_idempotent_and_only_disconnects_open_socket(self):
        cleanup = self.template.split("function cleanupOnUnload() {", 1)[1].split(
            "class LogVirtualList", 1
        )[0]

        self.assertIn("if (cleanupStarted)", cleanup)
        self.assertIn("cleanupStarted = true", cleanup)
        self.assertIn("if (socket && socketConnected)", cleanup)
        self.assertIn("socket.disconnect()", cleanup)
        self.assertNotIn("socket.close()", cleanup)

    def test_missing_socketio_client_falls_back_without_blocking_page_startup(self):
        initializer = self.template.split("function initializeSocket() {", 1)[1].split(
            "// 事件监听器", 1
        )[0]

        self.assertIn("typeof window.io !== 'function'", initializer)
        self.assertIn("socket = null", initializer)
        self.assertIn("socketConnected = false", initializer)
        self.assertIn("return", initializer)
        self.assertIn("socket = window.io()", initializer)

    def test_streamlit_urls_share_the_server_injected_port_map(self):
        self.assertIn("const APP_PORTS = {{ app_ports | tojson }};", self.template)
        self.assertEqual(self.template.count("const ports = APP_PORTS;"), 2)
        self.assertNotIn("const ports = { insight: 8501", self.template)

    def test_search_submission_is_single_flight_and_discards_stale_responses(self):
        search = self.template.split("async function performSearch() {", 1)[1].split(
            "// 切换应用", 1
        )[0]

        self.assertIn("if (button.disabled)", search)
        self.assertIn("const submissionSequence = ++searchSubmissionSequence", search)
        self.assertGreaterEqual(
            search.count("submissionSequence !== searchSubmissionSequence"), 2
        )
        self.assertIn("submittedRunId = result.run_id", search)
        self.assertIn("setProvenanceRunId(submittedRunId)", search)
        self.assertIn("encodeURIComponent(submittedRunId)", search)

    def test_report_generation_requires_and_retains_current_run_id(self):
        generation = self.template.split("function generateReport() {", 1)[1].split(
            "// 【修复】启动Report Engine日志实时刷新", 1
        )[0]

        self.assertIn("if (!provenanceRunId)", generation)
        self.assertIn("run_id: provenanceRunId", generation)
        self.assertNotIn("clearProvenanceRunId()", generation)

        completion = self.template.split("case 'completed':", 1)[1].split(
            "case 'error':", 1
        )[0]
        self.assertNotIn("clearProvenanceRunId()", completion)


if __name__ == "__main__":
    unittest.main()
