"""Run the embedded project's offline suite without sharing its imports."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest


CRAWLER_ROOT = Path(__file__).resolve().parent / "MindSpider/DeepSentimentCrawling/MediaCrawler"
TEST_PATCH = Path(__file__).resolve().parent / "test_support/mediacrawler-offline-tests.patch"


def _prepare_test_overlay(project_root, overlay):
    """Apply test-only fixes to a temporary copy, leaving the gitlink intact.

    The patch retains MediaCrawler's source notices and license headers.  Its
    upstream tests live at https://github.com/NanmiCoder/MediaCrawler/tree/main/tests.
    """
    shutil.copytree(
        project_root / "tests", overlay / "tests",
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    shutil.copy2(project_root / "pyproject.toml", overlay / "pyproject.toml")
    env = os.environ.copy()
    # git apply can operate outside a repository; prevent finding the parent's
    # .git through the temporary directory and interpreting paths against it.
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_CEILING_DIRECTORIES"] = str(overlay.parent)
    for options in (["--check"], []):
        result = subprocess.run(
            ["git", "apply", *options, str(TEST_PATCH)], cwd=overlay,
            env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    # Delegate to the original conftest so its __file__-based project_root and
    # project_root_path fixture still refer to the real production modules.
    source_conftest = project_root / "tests/conftest.py"
    (overlay / "tests/conftest.py").write_text(
        "from runpy import run_path as _run_path\n"
        f"_fixtures = _run_path({str(source_conftest)!r})\n"
        "globals().update({k: v for k, v in _fixtures.items() if not k.startswith('__')})\n",
        encoding="utf-8",
    )
    return overlay / "tests", overlay / "pyproject.toml"


def _run_isolated_tests(project_root, basetemp, *, tests_path=None, config_path=None):
    env = os.environ.copy()
    # Parent options/import paths must not select tests or modules in the child.
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONIOENCODING"] = "utf-8"
    config_path = config_path or project_root / "pyproject.toml"
    tests_path = tests_path or project_root / "tests"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_path), "-q", "-ra",
         "-p", "no:cacheprovider", "-c", str(config_path),
         "--rootdir", str(config_path.parent), "--confcutdir", str(config_path.parent),
         "--basetemp", str(basetemp)],
        cwd=project_root, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180,
    )
    if result.returncode:
        pytest.fail(
            f"Embedded offline suite exited with {result.returncode}:\n"
            f"{result.stdout}\n{result.stderr}", pytrace=False,
        )
    print(result.stdout, end="")


def test_mediacrawler_offline_suite(tmp_path):
    tests_path, config_path = _prepare_test_overlay(CRAWLER_ROOT, tmp_path / "overlay")
    _run_isolated_tests(
        CRAWLER_ROOT, tmp_path / "crawler",
        tests_path=tests_path, config_path=config_path,
    )


def test_child_failure_fails_parent_pytest(tmp_path):
    """A failing embedded assertion must fail the enclosing pytest process."""
    child_root = tmp_path / "embedded"
    (child_root / "tests").mkdir(parents=True)
    (child_root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\n', encoding="utf-8"
    )
    (child_root / "tests/test_child.py").write_text(
        'def test_failure():\n    assert False, "CHILD_FAILURE_SENTINEL"\n',
        encoding="utf-8",
    )
    parent_root = tmp_path / "parent"
    parent_root.mkdir()
    (parent_root / "pytest.ini").write_text('[pytest]\n', encoding="utf-8")
    (parent_root / "test_bridge.py").write_text(
        "import runpy\n"
        f"bridge = runpy.run_path({str(Path(__file__).resolve())!r})\n"
        "def test_embedded_suite():\n"
        f"    bridge['_run_isolated_tests'](bridge['Path']({str(child_root)!r}), "
        f"bridge['Path']({str(tmp_path / 'child-temp')!r}))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-c", str(parent_root / "pytest.ini"), "--confcutdir", str(parent_root),
         "--basetemp", str(tmp_path / "parent-temp"), "test_bridge.py"],
        cwd=parent_root, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "CHILD_FAILURE_SENTINEL" in result.stdout, result.stdout + result.stderr
    assert "test_embedded_suite" in result.stdout
