import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "ReportEngine" / "utils"))

from json_parser import JSONParseError, RobustJSONParser


@pytest.fixture
def parser():
    return RobustJSONParser(enable_json_repair=False, enable_llm_repair=False)


def test_parses_normal_json_response(parser):
    assert parser.parse('{"status": "ok"}') == {"status": "ok"}


def test_prefers_json_markdown_fence(parser):
    response = """Model notes:
```
This is not JSON.
```
```json
{"status": "ok"}
```
"""

    assert parser.parse(response) == {"status": "ok"}


@pytest.mark.parametrize("response", ["not JSON", None, {"status": "ok"}])
def test_invalid_model_response_raises_contextual_error(parser, response):
    with pytest.raises(JSONParseError, match="模型响应"):
        parser.parse(response, context_name="模型响应")
