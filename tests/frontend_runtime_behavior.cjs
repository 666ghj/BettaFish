// Execute the page's real request/event handlers with deterministic network order.
// The DOM and network edges are in-memory; no server or external CDN is used.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const template = fs.readFileSync(path.join(__dirname, '../templates/index.html'), 'utf8');
const section = (start, end) => {
    const offset = template.indexOf(start);
    const limit = template.indexOf(end, offset + start.length);
    assert.ok(offset >= 0 && limit > offset, `Missing page section: ${start}`);
    return template.slice(offset, limit);
};
const production = [
    section('let searchSubmissionSequence = 0;', '// 切换应用'),
    section('let reportTaskId = null;', '// 加载报告界面'),
    section('function loadReportInterface(', 'function downloadReport('),
    section('function renderTaskStatus(', '// 【修复】启动Report Engine日志实时刷新'),
    section('function stopProgressPolling(', '// ====== Report Engine SSE流式辅助函数'),
    section('function openReportStream(', '// 清洗流式chunk'),
    section('function viewReport(', '// 更新引擎状态显示'),
    section('function checkReportLockStatus(', '// 【重构】刷新Report'),
    section('function resetReportLogsForNewTask(', '// 【调试】测试日志管理器'),
];

function environment() {
    const requests = [], timers = [], intervals = [], sources = [], notices = [];
    class Element {
        constructor() { this.style = {}; this.dataset = {}; this.children = []; this.disabled = false; this.value = ''; this.textContent = ''; }
        set innerHTML(value) { this.html = value; this.children = []; }
        get innerHTML() { return this.html || ''; }
        appendChild(child) { this.children.push(child); }
        querySelector(selector) { return selector === 'iframe' ? this.children.find(child => child.isIframe) || null : null; }
        addEventListener() {}
    }
    const nodes = Object.fromEntries([
        'searchInput', 'searchButton', 'reportPreview', 'reportContent', 'taskProgressArea',
        'generateReportButton', 'downloadReportButton', 'downloadPdfButton', 'downloadMdButton', 'status-report',
    ].map(id => [id, new Element()]));
    nodes.searchInput.value = 'Topic A';
    const locked = new Set();
    const reportButton = {classList: {contains: value => locked.has(value), add: value => locked.add(value), remove: value => locked.delete(value)}};
    class EventSource {
        static CLOSED = 2;
        constructor(url) { this.url = url; this.listeners = {}; this.readyState = 1; this.closed = false; sources.push(this); }
        addEventListener(name, listener) { this.listeners[name] = listener; }
        emit(name, payload) { if (!this.closed) this.deliverQueued(name, payload); }
        deliverQueued(name, payload) { this.listeners[name]?.({type: name, data: JSON.stringify(payload)}); }
        close() { this.closed = true; this.readyState = 2; }
    }
    const context = {
        console: {log() {}, warn() {}, error() {}}, URL, EventSource,
        window: {EventSource, location: {hostname: '127.0.0.1'}},
        document: {
            getElementById: id => nodes[id] || null,
            querySelector: () => reportButton,
            createElement(tag) {
                const element = new Element();
                if (tag === 'iframe') {
                    element.isIframe = true;
                    element.contentDocument = {
                        open() {}, close() {}, write(text) { element.written = text; },
                        body: {style: {}}, documentElement: {style: {}},
                        createElement: () => new Element(), head: new Element(),
                    };
                }
                return element;
            },
        },
        sessionStorage: {getItem: () => 'run-A', setItem() {}, removeItem() {}},
        currentApp: 'report', autoGenerateTriggered: false, lastCompletedReportTask: null,
        reportLogStreaming: false, reportStreamConnected: false, customTemplate: '',
        reportLogLineCount: 0, lastLineCount: {report: 0},
        appStatus: {query: 'running'}, APP_PORTS: {query: 8653}, preloadedIframes: {query: {src: 'about:blank'}},
        lazyLoadIframe() { throw Error('Unexpected iframe creation'); },
        reportLogManager: {isRunning: false, stop() { this.isRunning = false; }, start() { this.isRunning = true; }, reset() {}, refresh() {}},
        showMessage: (...values) => notices.push(values),
        clearConsoleLayer() {}, resetReportStreamOutput() {}, appendReportStreamLine() {}, appendConsoleTextLine() {},
        updateReportStreamStatus() {}, updateEngineStatusDisplay() {},
        clearStreamHeartbeat() {}, startStreamHeartbeat() {}, refreshConnectionStatus() {},
        formatStreamChunk: value => value,
        setTimeout(callback, ms) { const timer = {callback, ms, cleared: false}; timers.push(timer); return timer; },
        clearTimeout(timer) { if (timer) timer.cleared = true; },
        setInterval(callback, ms) { const timer = {callback, ms, cleared: false}; intervals.push(timer); return timer; },
        clearInterval(timer) { if (timer) timer.cleared = true; },
        fetch(url, options) { return new Promise((resolve, reject) => requests.push({url, options, resolve, reject})); },
    };
    vm.createContext(context);
    for (const source of production) vm.runInContext(source, context);
    const run = code => vm.runInContext(code, context);
    const flush = async () => { for (let index = 0; index < 12; ++index) await Promise.resolve(); };
    const respond = (request, value) => request.resolve({ok: true, json: async () => value, text: async () => value});
    const task = (id, runId = 'run-A', status = 'running') => ({
        task_id: id, run_id: runId, status, query: runId === 'run-A' ? 'Topic A' : 'Topic B',
        progress: status === 'completed' ? 100 : 25, has_result: status === 'completed',
        report_file_ready: status === 'completed', ir_file_ready: status === 'completed',
        created_at: '2026-10-18T00:00:00', updated_at: '2026-10-18T00:00:01',
    });
    const switchRun = async () => {
        nodes.searchInput.value = 'Topic B';
        const pending = context.performSearch();
        respond(requests.at(-1), {success: true, run_id: 'run-B'});
        await pending;
    };
    const startB = async () => {
        context.generateReport();
        respond(requests.at(-1), {success: true, task_id: 'task-B', task: task('task-B', 'run-B')});
        await flush();
    };
    return {context, nodes, requests, sources, timers, intervals, notices, locked, run, flush, respond, task, switchRun, startB};
}

const scenarios = {
    async search_is_single_flight() {
        const e = environment();
        const first = e.context.performSearch();
        const duplicate = e.context.performSearch();
        assert.equal(e.requests.length, 1);
        e.respond(e.requests[0], {success: true, run_id: 'run-A-new'});
        await Promise.all([first, duplicate]);
        assert.equal(e.run('provenanceRunId'), 'run-A-new');
        assert.equal(new URL(e.context.preloadedIframes.query.src).searchParams.get('run_id'), 'run-A-new');
        assert.equal(e.nodes.searchButton.disabled, false);
    },
    async switching_search_releases_old_ui() {
        const e = environment();
        e.run("reportTaskId = 'task-A'"); e.context.openReportStream('task-A');
        e.context.updateDownloadButtonState(e.task('old-complete', 'run-A', 'completed'));
        await e.switchRun();
        assert.equal(e.sources[0].closed, true, 'New search retained the old SSE connection');
        assert.equal(e.run('reportTaskId'), null);
        assert.equal(e.nodes.downloadReportButton.disabled, true);
        assert.equal(e.nodes.downloadReportButton.dataset.taskId, '');
        assert.equal(e.context.lastCompletedReportTask, null);
    },
    async old_generate_success_cannot_claim_new_run() {
        const e = environment(); e.context.generateReport(); const old = e.requests[0];
        await e.switchRun();
        e.respond(old, {success: true, task_id: 'task-A', task: e.task('task-A')}); await e.flush();
        assert.equal(e.run('reportTaskId'), null, 'Old generate response claimed the new search');
        assert.equal(e.sources.length, 0);
        assert.equal(e.nodes.generateReportButton.disabled, false);
    },
    async old_generate_error_cannot_clear_new_task() {
        const e = environment(); e.context.generateReport(); const old = e.requests[0];
        await e.switchRun(); await e.startB();
        old.reject(new Error('old request disconnected')); await e.flush();
        assert.equal(e.run('reportTaskId'), 'task-B');
        assert.equal(e.sources.at(-1).closed, false);
        assert.equal(e.nodes.generateReportButton.disabled, true);
    },
    async old_progress_cannot_replace_new_report() {
        const e = environment(); e.run("reportTaskId = 'task-A'"); e.context.startProgressPolling('task-A');
        const old = e.requests[0]; await e.switchRun(); await e.startB();
        e.respond(old, {success: true, task: e.task('task-A', 'run-A', 'completed')}); await e.flush();
        assert.equal(e.run('reportTaskId'), 'task-B');
        assert.equal(e.nodes.downloadReportButton.dataset.taskId || '', '');
        assert.equal(e.requests.some(request => request.url === '/api/report/result/task-A'), false);
    },
    async old_sse_cannot_close_or_replace_new_task() {
        const e = environment(); e.run("reportTaskId = 'task-A'"); e.context.openReportStream('task-A');
        const oldSource = e.sources[0]; await e.switchRun(); await e.startB();
        oldSource.deliverQueued('status', {task_id: 'task-A', payload: {task: e.task('task-A')}});
        oldSource.deliverQueued('completed', {task_id: 'task-A', payload: {task: e.task('task-A', 'run-A', 'completed')}});
        oldSource.onerror();
        assert.equal(e.run('reportTaskId'), 'task-B');
        assert.equal(e.sources.at(-1).closed, false);
        assert.equal(e.requests.some(request => request.url === '/api/report/result/task-A'), false);
    },
    async old_status_cannot_unlock_or_render_new_run() {
        const e = environment(); e.context.checkReportLockStatus(); const readyA = e.requests[0];
        e.context.loadReportInterface(); const interfaceA = e.requests[1];
        await e.switchRun(); e.locked.add('locked');
        e.respond(readyA, {success: true, engines_ready: true, initialized: true, current_task: null});
        e.respond(interfaceA, {success: true, engines_ready: true, initialized: true, current_task: e.task('task-A')});
        await e.flush();
        assert.equal(e.locked.has('locked'), true);
        assert.equal(e.run('reportTaskId'), null);
        assert.equal(e.timers.some(timer => timer.ms === 1000 && !timer.cleared), false);
        assert.equal(e.sources.length, 0);
    },
    async old_preview_cannot_overwrite_new_search() {
        const e = environment(); e.context.viewReport('task-A'); const old = e.requests[0];
        await e.switchRun(); const waiting = e.nodes.reportPreview.innerHTML;
        e.respond(old, '<html>old report A</html>'); await e.flush();
        assert.equal(e.nodes.reportPreview.innerHTML, waiting);
        assert.equal(e.nodes.reportPreview.children.length, 0);
        // A deliberate historical preview after the switch remains supported.
        e.context.viewReport('history-report'); e.respond(e.requests.at(-1), '<html>chosen history</html>'); await e.flush();
        assert.equal(e.nodes.reportPreview.children[0].written, '<html>chosen history</html>');
    },
    async old_preview_error_cannot_overwrite_current_preview() {
        const e = environment(); e.context.viewReport('task-A'); const old = e.requests[0];
        await e.switchRun(); e.context.viewReport('task-B');
        e.respond(e.requests.at(-1), '<html>new B report</html>'); await e.flush();
        old.reject(new Error('old report failed')); await e.flush();
        assert.equal(e.nodes.reportPreview.children[0]?.written, '<html>new B report</html>');
    },
    async completed_stream_timer_cannot_close_next_task() {
        const e = environment(); e.run("reportTaskId = 'task-A'"); e.context.openReportStream('task-A');
        e.sources[0].emit('completed', {task_id: 'task-A', payload: {task: e.task('task-A', 'run-A', 'completed')}});
        const closeA = e.timers.find(timer => timer.ms === 500); assert.ok(closeA);
        await e.switchRun(); await e.startB(); closeA.callback();
        assert.equal(e.sources.at(-1).closed, false, 'Old completion timer closed the next task SSE');
        assert.equal(e.run('reportTaskId'), 'task-B');
    },
    async same_run_current_events_complete_report() {
        const e = environment(); await e.switchRun(); await e.startB();
        e.sources[0].emit('completed', {task_id: 'task-B', payload: {task: e.task('task-B', 'run-B', 'completed')}});
        const preview = e.requests.find(request => request.url === '/api/report/result/task-B'); assert.ok(preview);
        e.respond(preview, '<html>current report B</html>'); await e.flush();
        assert.equal(e.nodes.reportPreview.children[0].written, '<html>current report B</html>');
        assert.equal(e.nodes.downloadReportButton.dataset.taskId, 'task-B');
        assert.equal(e.nodes.generateReportButton.disabled, false);
    },
    async delayed_auto_generate_cannot_follow_new_search() {
        const e = environment(); e.context.checkReportLockStatus();
        e.respond(e.requests[0], {success: true, initialized: true, engines_ready: true, current_task: null}); await e.flush();
        const generateA = e.timers.find(timer => timer.ms === 1000); assert.ok(generateA);
        await e.switchRun(); generateA.callback();
        assert.equal(e.requests.filter(request => request.url === '/api/report/generate').length, 0);
    },
    async generate_is_single_flight() {
        const e = environment();
        e.context.generateReport(); e.context.generateReport();
        assert.equal(e.requests.filter(request => request.url === '/api/report/generate').length, 1);
    },
    async same_run_latest_preview_wins() {
        const e = environment();
        e.context.viewReport('history-A'); const first = e.requests[0];
        e.context.viewReport('history-B'); const second = e.requests[1];
        e.respond(second, '<html>selected B</html>'); await e.flush();
        e.respond(first, '<html>previous A</html>'); await e.flush();
        assert.equal(e.nodes.reportPreview.children[0].written, '<html>selected B</html>');
    },
    async foreign_worker_does_not_claim_current_run() {
        const e = environment(); e.context.loadReportInterface();
        e.respond(e.requests[0], {success: true, initialized: true, engines_ready: true, current_task: null, worker_busy: true});
        await e.flush();
        assert.equal(e.run('reportTaskId'), null);
        assert.equal(e.sources.length, 0);
        assert.equal(e.nodes.generateReportButton.disabled, true);
        e.context.checkReportLockStatus();
        e.respond(e.requests.at(-1), {success: true, initialized: true, engines_ready: true, current_task: null, worker_busy: true});
        await e.flush();
        assert.equal(e.timers.some(timer => timer.ms === 1000 && !timer.cleared), false);
    },
    async worker_occupied_before_auto_timer_prevents_generate() {
        const e = environment(); e.context.checkReportLockStatus();
        e.respond(e.requests[0], {success: true, engines_ready: true, current_task: null, worker_busy: false}); await e.flush();
        const delayed = e.timers.find(timer => timer.ms === 1000); assert.ok(delayed);
        e.context.checkReportLockStatus();
        e.respond(e.requests.at(-1), {success: true, engines_ready: true, current_task: null, worker_busy: true}); await e.flush();
        delayed.callback();
        assert.equal(e.requests.filter(request => request.url === '/api/report/generate').length, 0);
    },
    async current_run_status_can_recover_own_task() {
        const e = environment(); e.context.loadReportInterface();
        e.respond(e.requests[0], {success: true, initialized: true, engines_ready: true, current_task: e.task('task-A'), worker_busy: true});
        await e.flush();
        assert.equal(e.run('reportTaskId'), 'task-A');
        assert.equal(e.sources.length, 1);
        e.sources[0].emit('status', {task_id: 'task-A', run_id: 'run-A', payload: {task: e.task('task-A')}});
        assert.equal(e.sources[0].closed, false, 'Real log reset unexpectedly closed the current stream');
    },
    async foreign_task_event_on_current_stream_is_ignored() {
        const e = environment(); await e.switchRun(); await e.startB();
        const source = e.sources[0];
        source.emit('completed', {task_id: 'task-A', run_id: 'run-A', payload: {task: e.task('task-A', 'run-A', 'completed')}});
        assert.equal(e.run('reportTaskId'), 'task-B');
        assert.equal(e.nodes.downloadReportButton.dataset.taskId || '', '');
        assert.equal(e.requests.some(request => request.url === '/api/report/result/task-A'), false);
        assert.equal(source.closed, false);
    },
};

const requested = process.argv[2];
assert.ok(scenarios[requested], `Unknown scenario ${requested}`);
scenarios[requested]().then(() => console.log(`${requested}: passed`)).catch(error => {
    console.error(error); process.exitCode = 1;
});
