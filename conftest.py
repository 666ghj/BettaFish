"""Keep default pytest artifacts inside the writable project workspace."""

import os
from pathlib import Path


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(
            Path(__file__).resolve().parent / "logs" / f"pytest-{os.getpid()}"
        )
