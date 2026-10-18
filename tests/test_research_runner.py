import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from InsightEngine.agent import DeepSearchAgent as InsightAgent
from InsightEngine.state import State as InsightState
from MediaEngine.agent import DeepSearchAgent as MediaAgent
from MediaEngine.state import State as MediaState
from QueryEngine.agent import DeepSearchAgent as QueryAgent
from QueryEngine.state import State as QueryState
from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.normalizer import new_provenance_bundle
from SingleEngineApp.research_runner import (
    persist_research_result,
    read_launch_params,
    run_streamlit_research,
)


class _SessionState(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class _Progress:
    def __init__(self):
        self.values = []

    def progress(self, value):
        self.values.append(value)


class _Status:
    def __init__(self):
        self.values = []

    def text(self, value):
        self.values.append(value)


class _Streamlit:
    def __init__(self):
        self.session_state = _SessionState()
        self.progress_bar = _Progress()
        self.status = _Status()
        self.warnings = []
        self.errors = []

    def progress(self, _value):
        return self.progress_bar

    def empty(self):
        return self.status

    def warning(self, value):
        self.warnings.append(value)

    def error(self, value):
        self.errors.append(value)


class _Research:
    def __init__(self, events):
        self.events = events

    def mark_completed(self):
        self.events.append("paragraph-complete")


class _Agent:
    def __init__(self, events, config):
        self.events = events
        self.config = config
        self.state = SimpleNamespace(
            query="topic",
            paragraphs=[SimpleNamespace(title="one", research=_Research(events))],
            provenance_bundle=ProvenanceBundle(agent="query_engine"),
        )

    def _generate_report_structure(self, _query):
        self.events.append("structure")

    def _initial_search_and_summary(self, _index):
        self.events.append("search")

    def _reflection_loop(self, _index):
        self.events.append("reflect")

    def _generate_final_report(self):
        self.events.append("report")
        return "final"


class ResearchRunnerTests(unittest.TestCase):
    def test_read_launch_params_unwraps_legacy_query_parameter_lists(self):
        class LegacyStreamlit:
            def experimental_get_query_params(self):
                return {
                    "query": ["清华鹅腿阿姨"],
                    "auto_search": ["true"],
                    "run_id": ["run-1"],
                }

        _params, query, auto_search, run_id = read_launch_params(LegacyStreamlit())

        self.assertEqual(query, "清华鹅腿阿姨")
        self.assertTrue(auto_search)
        self.assertEqual(run_id, "run-1")

    def test_real_agents_preserve_provenance_identity_when_generating_structure(self):
        class StructureLLM:
            def stream_invoke_to_string(self, _system_prompt, _user_prompt, **_kwargs):
                return '[{"title": "背景", "content": "查询背景"}]'

        engine_types = (
            (QueryAgent, QueryState, "query_engine"),
            (MediaAgent, MediaState, "media_engine"),
            (InsightAgent, InsightState, "insight_engine"),
        )
        for agent_type, state_type, agent_name in engine_types:
            with self.subTest(agent=agent_name):
                agent = agent_type.__new__(agent_type)
                agent.llm_client = StructureLLM()
                agent.state = state_type(query="topic")
                agent.state.provenance_bundle = new_provenance_bundle(
                    agent_name, "topic", run_id="run-structure"
                )
                original_bundle = agent.state.provenance_bundle
                original_identity = (
                    original_bundle.bundle_id,
                    original_bundle.meta.get("query"),
                    original_bundle.meta.get("run_id"),
                )

                agent._generate_report_structure("topic")

                self.assertIs(agent.state.provenance_bundle, original_bundle)
                self.assertEqual(
                    (
                        agent.state.provenance_bundle.bundle_id,
                        agent.state.provenance_bundle.meta.get("query"),
                        agent.state.provenance_bundle.meta.get("run_id"),
                    ),
                    original_identity,
                )

    def test_real_engine_types_satisfy_runner_method_contract(self):
        required_methods = (
            "_generate_report_structure",
            "_initial_search_and_summary",
            "_reflection_loop",
            "_generate_final_report",
        )

        for agent_type in (QueryAgent, MediaAgent, InsightAgent):
            with self.subTest(agent=agent_type.__module__):
                for method_name in required_methods:
                    self.assertTrue(callable(getattr(agent_type, method_name, None)))

    def test_public_persistence_accepts_each_real_engine_state(self):
        engine_types = (
            (QueryAgent, QueryState),
            (MediaAgent, MediaState),
            (InsightAgent, InsightState),
        )
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            for index, (agent_type, state_type) in enumerate(engine_types):
                with self.subTest(agent=agent_type.__module__):
                    output_dir = root / str(index)
                    agent = agent_type.__new__(agent_type)
                    agent.config = SimpleNamespace(
                        OUTPUT_DIR=str(output_dir), SAVE_INTERMEDIATE_STATES=False
                    )
                    agent.state = state_type(query="topic")

                    paths = persist_research_result(agent, "final")

                    self.assertEqual(paths["report"].read_text(encoding="utf-8"), "final")
                    self.assertTrue(paths["provenance"].is_file())

    def test_shared_runner_saves_before_publishing(self):
        events = []
        st = _Streamlit()

        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_dir = Path(temp_dir)
            config = SimpleNamespace(
                OUTPUT_DIR=str(output_dir), SAVE_INTERMEDIATE_STATES=False
            )

            def publish_after_save(*_args):
                self.assertEqual(len(list(output_dir.glob("*.md"))), 1)
                self.assertEqual(len(list(output_dir.glob("*.provenance.json"))), 1)
                bundle = _args[-1]
                self.assertEqual(bundle.meta["query"], "topic")
                self.assertEqual(bundle.meta["run_id"], "run-1")
                self.assertTrue(bundle.bundle_id)
                events.append("publish")
                return True

            with patch(
                "SingleEngineApp.research_runner.publish_runtime_result",
                side_effect=publish_after_save,
            ):
                result = run_streamlit_research(
                    st_module=st,
                    query="topic",
                    config=config,
                    run_id="run-1",
                    engine="query",
                    agent_factory=lambda supplied: _Agent(events, supplied),
                    display_results=lambda *_args: events.append("display"),
                    app_name="test",
                )

        self.assertIsNotNone(result)
        self.assertLess(events.index("report"), events.index("publish"))
        self.assertEqual(st.progress_bar.values[-1], 100)
        self.assertFalse(st.errors)

    def test_publish_failure_keeps_local_success_and_reports_terminal_state(self):
        events = []
        st = _Streamlit()

        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_dir = Path(temp_dir)
            config = SimpleNamespace(
                OUTPUT_DIR=str(output_dir), SAVE_INTERMEDIATE_STATES=False
            )
            with patch(
                "SingleEngineApp.research_runner.publish_runtime_result",
                side_effect=RuntimeError("offline"),
            ), patch(
                "SingleEngineApp.research_runner.publish_runtime_failure",
                side_effect=lambda *_args: events.append("failed-state"),
            ):
                result = run_streamlit_research(
                    st_module=st,
                    query="topic",
                    config=config,
                    run_id="run-1",
                    engine="query",
                    agent_factory=lambda supplied: _Agent(events, supplied),
                    display_results=lambda *_args: events.append("display"),
                    app_name="test",
                )

            self.assertEqual(len(list(output_dir.glob("*.md"))), 1)
            self.assertEqual(len(list(output_dir.glob("*.provenance.json"))), 1)

        self.assertIsNotNone(result)
        self.assertIn("display", events)
        self.assertIn("failed-state", events)
        self.assertTrue(st.warnings)
        self.assertFalse(st.errors)

    def test_display_failure_does_not_publish_late_engine_failure(self):
        events = []
        st = _Streamlit()
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config = SimpleNamespace(
                OUTPUT_DIR=temp_dir,
                SAVE_INTERMEDIATE_STATES=False,
            )
            with patch(
                "SingleEngineApp.research_runner.publish_runtime_result",
                return_value=True,
            ), patch(
                "SingleEngineApp.research_runner.publish_runtime_failure"
            ) as publish_failure:
                result = run_streamlit_research(
                    st_module=st,
                    query="topic",
                    config=config,
                    run_id="run-display",
                    engine="query",
                    agent_factory=lambda supplied: _Agent(events, supplied),
                    display_results=lambda *_args: (_ for _ in ()).throw(
                        RuntimeError("ui failed")
                    ),
                    app_name="test",
                )

        self.assertIsNotNone(result)
        publish_failure.assert_not_called()
        self.assertTrue(any("界面渲染失败" in value for value in st.warnings))
        self.assertFalse(st.errors)

    def test_zero_paragraph_report_does_not_divide_by_zero(self):
        events = []
        st = _Streamlit()

        class EmptyAgent(_Agent):
            def __init__(self, supplied):
                super().__init__(events, supplied)
                self.state.paragraphs = []

        with TemporaryDirectory(dir=Path.cwd()) as temp_dir, patch(
            "SingleEngineApp.research_runner.publish_runtime_result",
            return_value=True,
        ):
            result = run_streamlit_research(
                st_module=st,
                query="topic",
                config=SimpleNamespace(
                    OUTPUT_DIR=temp_dir,
                    SAVE_INTERMEDIATE_STATES=False,
                ),
                run_id="run-empty",
                engine="query",
                agent_factory=EmptyAgent,
                display_results=lambda *_args: None,
                app_name="test",
            )

        self.assertIsNotNone(result)
        self.assertEqual(st.progress_bar.values[-1], 100)

    def test_paragraph_forum_message_uses_only_its_valid_evidence_ids(self):
        events = []
        st = _Streamlit()

        class EvidenceAgent(_Agent):
            def _initial_search_and_summary(self, _index):
                super()._initial_search_and_summary(_index)
                paragraph = self.state.paragraphs[0]
                paragraph.research.latest_summary = "鹅腿阿姨在清华附近经营摊位。"
                self.state.provenance_bundle.add_records(
                    [
                        SourceRecord(
                            source_id="source-1",
                            agent="query_engine",
                            source_type="web",
                            url="https://example.com/source",
                        )
                    ],
                    [
                        EvidenceRecord(
                            evidence_id="evidence-1",
                            source_id="source-1",
                            agent="query_engine",
                            evidence_type="web",
                            snippet="鹅腿阿姨在清华附近经营摊位。",
                            scope={"subject": "one"},
                        ),
                        EvidenceRecord(
                            evidence_id="invalid-no-source",
                            source_id="missing",
                            agent="query_engine",
                            evidence_type="web",
                            snippet="不应引用。",
                            scope={"subject": "one"},
                        ),
                    ],
                )

        with TemporaryDirectory(dir=Path.cwd()) as temp_dir, patch(
            "SingleEngineApp.research_runner.publish_runtime_result",
            return_value=True,
        ), patch(
            "SingleEngineApp.research_runner.append_runtime_forum_message",
            return_value=True,
        ) as append_message:
            run_streamlit_research(
                st_module=st,
                query="topic",
                config=SimpleNamespace(
                    OUTPUT_DIR=temp_dir,
                    SAVE_INTERMEDIATE_STATES=False,
                ),
                run_id="run-forum",
                engine="query",
                agent_factory=lambda supplied: EvidenceAgent(events, supplied),
                display_results=lambda *_args: None,
                app_name="test",
            )

        append_message.assert_called_once_with(
            "run-forum",
            "query",
            "鹅腿阿姨在清华附近经营摊位。",
            ["evidence-1"],
        )


if __name__ == "__main__":
    unittest.main()
