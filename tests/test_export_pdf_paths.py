import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import export_pdf


def _install_filenames(monkeypatch, module=None):
    if module is None:
        path = Path(__file__).resolve().parents[1] / "ReportEngine" / "utils" / "filenames.py"
        spec = importlib.util.spec_from_file_location("ReportEngine.utils.filenames", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

    utils_pkg = ModuleType("ReportEngine.utils")
    utils_pkg.__path__ = []
    utils_pkg.filenames = module
    monkeypatch.setitem(sys.modules, "ReportEngine.utils", utils_pkg)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.filenames", module)
    return module


def _stub_pdf_renderer(monkeypatch, payload=b"%PDF-test", filenames_module=None):
    class FakeRenderer:
        def render_to_bytes(self, document_ir, optimize_layout):
            assert optimize_layout is True
            return payload

    report_engine = ModuleType("ReportEngine")
    report_engine.__path__ = []
    renderers = ModuleType("ReportEngine.renderers")
    renderers.__path__ = []
    pdf_renderer = ModuleType("ReportEngine.renderers.pdf_renderer")
    pdf_renderer.PDFRenderer = FakeRenderer
    monkeypatch.setitem(sys.modules, "ReportEngine", report_engine)
    monkeypatch.setitem(sys.modules, "ReportEngine.renderers", renderers)
    monkeypatch.setitem(sys.modules, "ReportEngine.renderers.pdf_renderer", pdf_renderer)
    _install_filenames(monkeypatch, filenames_module)


def test_project_root_is_derived_from_script_location():
    assert export_pdf.PROJECT_ROOT == Path(export_pdf.__file__).resolve().parent


def test_export_pdf_writes_to_project_reports_directory(monkeypatch, tmp_path):
    ir_path = tmp_path / "report.json"
    ir_path.write_text(json.dumps({"metadata": {"topic": "compatibility"}}), encoding="utf-8")
    _stub_pdf_renderer(monkeypatch)
    monkeypatch.setattr(export_pdf, "PROJECT_ROOT", tmp_path)

    result = export_pdf.export_pdf(ir_path)

    output_path = Path(result)
    assert output_path.parent == (tmp_path / "final_reports" / "pdf").resolve()
    assert output_path.read_bytes() == b"%PDF-test"
    assert output_path.name.startswith("report_compatibility_")
    assert output_path.suffix == ".pdf"


def test_export_pdf_sanitizes_traversal_topic(monkeypatch, tmp_path):
    ir_path = tmp_path / "report.json"
    ir_path.write_text(
        json.dumps({"metadata": {"topic": "../../tmp/pwned"}}),
        encoding="utf-8",
    )
    _stub_pdf_renderer(monkeypatch)
    monkeypatch.setattr(export_pdf, "PROJECT_ROOT", tmp_path)

    result = export_pdf.export_pdf(ir_path)

    output_path = Path(result).resolve()
    export_dir = (tmp_path / "final_reports" / "pdf").resolve()
    assert output_path.is_relative_to(export_dir)
    assert ".." not in output_path.name
    assert output_path.name.startswith("report_tmppwned_")
    assert not (tmp_path.parent / "pwned").exists()


def test_export_pdf_rejects_filename_that_escapes_output_dir(monkeypatch, tmp_path):
    ir_path = tmp_path / "report.json"
    ir_path.write_text(json.dumps({"metadata": {"topic": "ok"}}), encoding="utf-8")

    fake_filenames = ModuleType("ReportEngine.utils.filenames")
    fake_filenames.report_export_filename = lambda document_ir, extension: "../outside.pdf"
    _stub_pdf_renderer(monkeypatch, filenames_module=fake_filenames)
    monkeypatch.setattr(export_pdf, "PROJECT_ROOT", tmp_path)

    result = export_pdf.export_pdf(ir_path)

    assert result is None
    assert not (tmp_path / "outside.pdf").exists()
    assert not list((tmp_path / "final_reports" / "pdf").glob("*.pdf"))
