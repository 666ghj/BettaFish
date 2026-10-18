"""Execute the report SSE handler so retry states cannot masquerade as success."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_chapter_retry_events_show_retry_and_discard_interrupted_delta():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed to execute the browser event handler")
    template = Path(__file__).resolve().parents[1] / "templates/index.html"
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const text = fs.readFileSync(process.argv[1], 'utf8');
const start = text.indexOf('function handleReportStreamEvent(');
const end = text.indexOf('function formatStreamChunk(', start);
const lines = [];
const context = {
  appendReportStreamLine: (...args) => lines.push(args),
  formatStreamChunk: text => text,
};
vm.createContext(context);
vm.runInContext(text.slice(start, end), context);
context.handleReportStreamEvent('chapter_status', {payload: {
  chapterId: 'S2', title: '第二章', status: 'retrying', attempt: 1, max_attempts: 2,
}});
assert.match(lines[0][0], /重试/);
assert.equal(lines[0][1], 'warn');
context.handleReportStreamEvent('chapter_status', {payload: {
  chapterId: 'S2', title: '第二章', status: 'error',
}});
assert.match(lines[1][0], /失败/);
assert.equal(lines[1][1], 'error');
context.handleReportStreamEvent('chapter_status', {payload: {
  chapterId: 'S1', title: '第一章', status: 'completed',
}});
assert.match(lines[2][0], /已完成/);
assert.equal(lines[2][1], 'success');
context.handleReportStreamEvent('chapter_chunk', {payload: {
  chapterId: 'S2', reset: true, delta: 'discard interrupted output',
}});
assert.equal(lines.length, 3);
console.log('chapter retry events verified');
"""
    result = subprocess.run(
        [node, "-e", script, str(template)], capture_output=True, text=True,
        encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
