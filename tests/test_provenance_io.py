from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from common.provenance.io import atomic_write_text


@pytest.mark.parametrize("failure_stage", ["write", "fsync"])
def test_atomic_write_cleans_temporary_file_when_persistence_fails(failure_stage):
    with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        root = Path(temp_dir)
        target = root / "report.md"
        target.write_text("previous report", encoding="utf-8")

        if failure_stage == "write":
            def failing_temp_file(**kwargs):
                temp_file = NamedTemporaryFile(**kwargs)
                temp_file.write = Mock(side_effect=OSError("controlled write failure"))
                return temp_file

            failure = patch(
                "common.provenance.io.tempfile.NamedTemporaryFile",
                side_effect=failing_temp_file,
            )
        else:
            failure = patch(
                "common.provenance.io.os.fsync",
                side_effect=OSError("controlled sync failure"),
            )

        with failure, pytest.raises(OSError, match="controlled"):
            atomic_write_text(target, "new report")

        assert target.read_text(encoding="utf-8") == "previous report"
        assert list(root.iterdir()) == [target]
