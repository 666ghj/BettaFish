"""
Report Engine Flask接口。

该模块为前端/CLI提供统一HTTP/SSE入口，负责：
1. 初始化 ReportAgent 并串联后台线程；
2. 管理任务排队、进度查询、流式推送与日志下载；
3. 提供模板列表、输入文件检查等周边能力。
"""

import os
import json
import threading
import time
from collections import deque, defaultdict
from datetime import datetime
from queue import Queue, Empty
from flask import Blueprint, request, jsonify, Response, send_file, stream_with_context
from typing import Dict, Any, List, Optional
from loguru import logger
from .agent import ReportAgent, create_agent
from .utils.config import settings


# 创建Blueprint
report_bp = Blueprint('report_engine', __name__)

# 全局变量
report_agent = None
current_task = None
task_lock = threading.Lock()

# ====== 流式推送与任务历史管理 ======
# 通过有界deque缓存最近的事件，方便SSE断线后快速补发
MAX_TASK_HISTORY = 5
STREAM_HEARTBEAT_INTERVAL = 15  # 心跳间隔秒
stream_lock = threading.Lock()
stream_subscribers = defaultdict(list)
tasks_registry: Dict[str, 'ReportTask'] = {}


def _register_stream(task_id: str) -> Queue:
    """
    为指定任务注册一个事件队列，供SSE监听器消费。

    返回的 Queue 会存入 `stream_subscribers`，SSE 生成器将不断读取。

    参数:
        task_id: 需要监听的任务ID。

    返回:
        Queue: 线程安全的事件队列。
    """
    queue = Queue()
    with stream_lock:
        stream_subscribers[task_id].append(queue)
    return queue


def _unregister_stream(task_id: str, queue: Queue):
    """
    安全移除事件队列，避免内存泄漏。

    需要在finally中调用，保证异常情况下资源也能释放。

    参数:
        task_id: 任务ID。
        queue: 之前注册的事件队列。
    """
    with stream_lock:
        listeners = stream_subscribers.get(task_id, [])
        if queue in listeners:
            listeners.remove(queue)
        if not listeners and task_id in stream_subscribers:
            stream_subscribers.pop(task_id, None)


def _broadcast_event(task_id: str, event: Dict[str, Any]):
    """
    将事件推送给所有监听者，失败时做好异常捕获。

    采用浅拷贝监听列表，防止并发移除导致遍历异常。

    参数:
        task_id: 待推送的任务ID。
        event: 结构化事件payload。
    """
    with stream_lock:
        listeners = list(stream_subscribers.get(task_id, []))
    for queue in listeners:
        try:
            queue.put(event, timeout=0.1)
        except Exception:
            logger.exception("推送流式事件失败，跳过当前监听队列")


def _prune_task_history_locked():
    """
    在task_lock持有期间调用，清理过多的历史任务。

    仅保留最近 `MAX_TASK_HISTORY` 个任务，避免长时间运行占用过多内存。

    说明:
        该函数假设调用方已获取 `task_lock`，否则存在竞态风险。
    """
    if len(tasks_registry) <= MAX_TASK_HISTORY:
        return
    # 按创建时间排序，移除最旧的任务
    sorted_tasks = sorted(tasks_registry.values(), key=lambda t: t.created_at)
    for task in sorted_tasks[:-MAX_TASK_HISTORY]:
        tasks_registry.pop(task.task_id, None)


def _get_task(task_id: str) -> Optional['ReportTask']:
    """
    统一的任务查找方法，优先返回当前任务。

    避免重复写锁逻辑，便于多个API共享。

    参数:
        task_id: 任务ID。

    返回:
        ReportTask | None: 命中时返回任务实例，否则为None。
    """
    with task_lock:
        if current_task and current_task.task_id == task_id:
            return current_task
        return tasks_registry.get(task_id)


def _format_sse(event: Dict[str, Any]) -> str:
    """
    按SSE协议格式化消息。

    输出形如 `id:/event:/data:` 的三段文本，供浏览器端直接消费。

    参数:
        event: 事件payload，至少包含 id/type。

    返回:
        str: SSE协议要求的字符串。
    """
    payload = json.dumps(event, ensure_ascii=False)
    event_id = event.get('id', 0)
    event_type = event.get('type', 'message')
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


def initialize_report_engine():
    """
    初始化Report Engine。

    单例化 ReportAgent，方便 API 启动后直接接收任务。

    返回:
        bool: 初始化成功返回True，异常时返回False。
    """
    global report_agent
    try:
        report_agent = create_agent()
        logger.info("Report Engine初始化成功")
        return True
    except Exception as e:
        logger.exception(f"Report Engine初始化失败: {str(e)}")
        return False


class ReportTask:
    """
    报告生成任务。

    该对象串联运行状态、进度、事件历史及最终文件路径，
    既供后台线程更新，也供HTTP接口读取。
    """

    def __init__(self, query: str, task_id: str, custom_template: str = ""):
        """
        初始化任务对象，记录查询词、自定义模板与运行期元数据。

        Args:
            query: 最终需要生成的报告主题
            task_id: 任务唯一ID，通常由时间戳构造
            custom_template: 可选的自定义Markdown模板
        """
        self.task_id = task_id
        self.query = query
        self.custom_template = custom_template
        self.status = "pending"  # pending, running, completed, error
        self.progress = 0
        self.result = None
        self.error_message = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.html_content = ""
        self.report_file_path = ""
        self.report_file_relative_path = ""
        self.report_file_name = ""
        self.state_file_path = ""
        self.state_file_relative_path = ""
        # ====== 流式事件缓存与并发保护 ======
        # 使用deque保存最近的事件，结合锁保证多线程下的安全访问
        self.event_history: deque = deque(maxlen=1000)
        self._event_lock = threading.Lock()
        self.last_event_id = 0

    def update_status(self, status: str, progress: int = None, error_message: str = ""):
        """
        更新任务状态并广播事件。

        会自动刷新 `updated_at`、错误信息，并触发 `status` 类型的 SSE。

        参数:
            status: 任务阶段（pending/running/completed/error/cancelled）。
            progress: 可选的进度百分比。
            error_message: 出错时的人类可读说明。
        """
        self.status = status
        if progress is not None:
            self.progress = progress
        if error_message:
            self.error_message = error_message
        self.updated_at = datetime.now()
        # 推送状态变更事件，方便前端实时刷新
        self.publish_event(
            'status',
            {
                'status': self.status,
                'progress': self.progress,
                'error_message': self.error_message,
                'hint': error_message or '',
                'task': self.to_dict(),
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，方便直接返回给JSON API。"""
        return {
            'task_id': self.task_id,
            'query': self.query,
            'status': self.status,
            'progress': self.progress,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'has_result': bool(self.html_content),
            'report_file_ready': bool(self.report_file_path),
            'report_file_name': self.report_file_name,
            'report_file_path': self.report_file_relative_path or self.report_file_path,
            'state_file_ready': bool(self.state_file_path),
            'state_file_path': self.state_file_relative_path or self.state_file_path
        }

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        将任意事件放入缓存并广播，所有新增逻辑均配套中文说明。

        参数:
            event_type: SSE中的event名称。
            payload: 实际业务数据。
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        event: Dict[str, Any] = {
            'id': 0,
            'type': event_type,
            'task_id': self.task_id,
            'timestamp': timestamp,
            'payload': payload,
        }
        with self._event_lock:
            self.last_event_id += 1
            event['id'] = self.last_event_id
            self.event_history.append(event)
        _broadcast_event(self.task_id, event)

    def history_since(self, last_event_id: Optional[int]) -> List[Dict[str, Any]]:
        """
        根据Last-Event-ID补发历史事件，确保断线重连无遗漏。

        参数:
            last_event_id: SSE客户端记录的最后一个事件ID。

        返回:
            list[dict]: 从 last_event_id 之后的事件列表。
        """
        with self._event_lock:
            if last_event_id is None:
                return list(self.event_history)
            return [evt for evt in self.event_history if evt['id'] > last_event_id]


def check_engines_ready() -> Dict[str, Any]:
    """
    检查三个子引擎是否都有新文件。

    调用 ReportAgent 的基准检测逻辑，并附带论坛日志存在性，
    是 /status、/generate 的前置校验。
    """
    directories = {
        'insight': 'insight_engine_streamlit_reports',
        'media': 'media_engine_streamlit_reports',
        'query': 'query_engine_streamlit_reports'
    }

    forum_log_path = 'logs/forum.log'

    if not report_agent:
        return {
            'ready': False,
            'error': 'Report Engine未初始化'
        }

    return report_agent.check_input_files(
        directories['insight'],
        directories['media'],
        directories['query'],
        forum_log_path
    )


def run_report_generation(task: ReportTask, query: str, custom_template: str = ""):
    """
    在后台线程中运行报告生成。

    包括：检查输入→加载文档→调用ReportAgent→持久化输出→
    推送阶段性事件。出现错误会自动推送并写状态。

    参数:
        task: 本次任务对象，内部持有事件队列。
        query: 报告主题。
        custom_template: 可选的自定义模板字符串。
    """
    global current_task

    try:
        # 在局部闭包内封装推送逻辑，便于传递给ReportAgent
        def stream_handler(event_type: str, payload: Dict[str, Any]):
            """所有阶段事件都通过同一个接口分发，保证日志一致。"""
            task.publish_event(event_type, payload)

        task.update_status("running", 10)
        task.publish_event('stage', {'message': '任务已启动，正在检查输入文件', 'stage': 'prepare'})

        # 检查输入文件
        check_result = check_engines_ready()
        if not check_result['ready']:
            task.update_status("error", 0, f"输入文件未准备就绪: {check_result.get('missing_files', [])}")
            return

        task.publish_event('stage', {
            'message': '输入文件检查通过，准备载入内容',
            'stage': 'io_ready',
            'files': check_result.get('latest_files', {})
        })

        task.update_status("running", 30)

        # 加载输入文件
        content = report_agent.load_input_files(check_result['latest_files'])
        task.publish_event('stage', {'message': '源数据加载完成，启动生成流程', 'stage': 'data_loaded'})

        task.update_status("running", 50)

        # 生成报告（附带兜底重试，缓解瞬时网络抖动）
        for attempt in range(1, 3):
            try:
                task.publish_event('stage', {
                    'message': f'正在调用ReportAgent生成报告（第{attempt}次尝试）',
                    'stage': 'agent_running',
                    'attempt': attempt
                })
                generation_result = report_agent.generate_report(
                    query=query,
                    reports=content['reports'],
                    forum_logs=content['forum_logs'],
                    custom_template=custom_template,
                    save_report=True,
                    stream_handler=stream_handler
                )
                break
            except Exception as err:
                # 将错误即时推送至前端，方便观察重试策略
                task.publish_event('warning', {
                    'message': f'ReportAgent执行失败: {str(err)}',
                    'stage': 'agent_running',
                    'attempt': attempt
                })
                if attempt == 2:
                    raise
                # 简单的指数退避，防止频繁触发限流（单位秒）
                backoff = min(5 * attempt, 15)
                task.publish_event('stage', {
                    'message': f'{backoff} 秒后重试生成任务',
                    'stage': 'retry_wait',
                    'wait_seconds': backoff
                })
                time.sleep(backoff)

        if isinstance(generation_result, dict):
            html_report = generation_result.get('html_content', '')
        else:
            html_report = generation_result

        task.update_status("running", 90)
        task.publish_event('stage', {'message': '报告生成完毕，准备持久化', 'stage': 'persist'})

        # 保存结果
        task.html_content = html_report
        if isinstance(generation_result, dict):
            task.report_file_path = generation_result.get('report_filepath', '')
            task.report_file_relative_path = generation_result.get('report_relative_path', '')
            task.report_file_name = generation_result.get('report_filename', '')
            task.state_file_path = generation_result.get('state_filepath', '')
            task.state_file_relative_path = generation_result.get('state_relative_path', '')
        task.publish_event('html_ready', {
            'message': 'HTML渲染完成，可刷新预览',
            'report_file': task.report_file_relative_path or task.report_file_path,
            'state_file': task.state_file_relative_path or task.state_file_path,
            'task': task.to_dict(),
        })
        task.update_status("completed", 100)
        task.publish_event('completed', {
            'message': '任务完成',
            'duration_seconds': (task.updated_at - task.created_at).total_seconds(),
            'report_file': task.report_file_relative_path or task.report_file_path,
            'task': task.to_dict(),
        })

    except Exception as e:
        logger.exception(f"报告生成过程中发生错误: {str(e)}")
        task.update_status("error", 0, str(e))
        task.publish_event('error', {
            'message': str(e),
            'stage': 'failed',
            'task': task.to_dict(),
        })
        # 只在出错时清理任务
        with task_lock:
            if current_task and current_task.task_id == task.task_id:
                current_task = None


@report_bp.route('/status', methods=['GET'])
def get_status():
    """
    获取Report Engine状态，包括引擎就绪情况与当前任务信息。

    返回:
        Response: JSON结构包含initialized/engines_ready/当前任务等。
    """
    try:
        engines_status = check_engines_ready()

        return jsonify({
            'success': True,
            'initialized': report_agent is not None,
            'engines_ready': engines_status['ready'],
            'files_found': engines_status.get('files_found', []),
            'missing_files': engines_status.get('missing_files', []),
            'current_task': current_task.to_dict() if current_task else None
        })
    except Exception as e:
        logger.exception(f"获取Report Engine状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    开始生成报告。

    负责排队、创建后台线程、清空日志并返回SSE地址。

    请求体:
        query: 报告主题（可选）。
        custom_template: 自定义模板字符串（可选）。

    返回:
        Response: JSON，包含 task_id 与 SSE stream url。
    """
    global current_task

    try:
        # 检查是否有任务在运行
        with task_lock:
            if current_task and current_task.status == "running":
                return jsonify({
                    'success': False,
                    'error': '已有报告生成任务在运行中',
                    'current_task': current_task.to_dict()
                }), 400

            # 如果有已完成的任务，清理它
            if current_task and current_task.status in ["completed", "error"]:
                current_task = None

        # 获取请求参数
        data = request.get_json() or {}
        query = data.get('query', '智能舆情分析报告')
        custom_template = data.get('custom_template', '')

        # 清空日志文件
        clear_report_log()

        # 检查Report Engine是否初始化
        if not report_agent:
            return jsonify({
                'success': False,
                'error': 'Report Engine未初始化'
            }), 500

        # 检查输入文件是否准备就绪
        engines_status = check_engines_ready()
        if not engines_status['ready']:
            return jsonify({
                'success': False,
                'error': '输入文件未准备就绪',
                'missing_files': engines_status.get('missing_files', [])
            }), 400

        # 创建新任务
        task_id = f"report_{int(time.time())}"
        task = ReportTask(query, task_id, custom_template)

        with task_lock:
            current_task = task
            tasks_registry[task_id] = task
            _prune_task_history_locked()

        # 通过主动推送pending事件告知前端任务已经排队
        task.publish_event(
            'status',
            {
                'status': task.status,
                'progress': task.progress,
                'message': '任务已排队，等待资源空闲',
                'task': task.to_dict(),
            }
        )

        # 在后台线程中运行报告生成
        thread = threading.Thread(
            target=run_report_generation,
            args=(task, query, custom_template),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '报告生成已启动',
            'task': task.to_dict(),
            'stream_url': f"/api/report/stream/{task_id}"
        })

    except Exception as e:
        logger.exception(f"开始生成报告失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id: str):
    """
    获取报告生成进度，若任务被清理则返回一个完成态兜底。

    参数:
        task_id: 任务唯一标识。

    返回:
        Response: JSON包含任务当前状态。
    """
    try:
        task = _get_task(task_id)
        if not task:
            # 如果任务不存在，可能是历史记录已被清理，回传一个完成态兜底
            return jsonify({
                'success': True,
                'task': {
                    'task_id': task_id,
                    'status': 'completed',
                    'progress': 100,
                    'error_message': '',
                    'has_result': True,
                    'report_file_ready': False,
                    'report_file_name': '',
                    'report_file_path': '',
                    'state_file_ready': False,
                    'state_file_path': ''
                }
            })

        return jsonify({
            'success': True,
            'task': task.to_dict()
        })

    except Exception as e:
        logger.exception(f"获取报告生成进度失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/stream/<task_id>', methods=['GET'])
def stream_task(task_id: str):
    """
    基于SSE的实时推送接口。

    - 自动补发Last-Event-ID之后的历史事件；
    - 周期性发送心跳以防代理中断；
    - 任务结束后自动注销监听。

    参数:
        task_id: 任务唯一标识。

    返回:
        Response: `text/event-stream` 类型响应。
    """
    task = _get_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    last_event_header = request.headers.get('Last-Event-ID')
    try:
        last_event_id = int(last_event_header) if last_event_header else None
    except ValueError:
        last_event_id = None

    def event_generator():
        queue = _register_stream(task_id)
        try:
            # 断线重连场景下，先补发历史事件，保证界面状态一致
            history = task.history_since(last_event_id)
            for event in history:
                yield _format_sse(event)

            finished = task.status in ("completed", "error", "cancelled")
            while True:
                if finished:
                    break
                try:
                    event = queue.get(timeout=STREAM_HEARTBEAT_INTERVAL)
                    yield _format_sse(event)
                    if event.get('type') in ("completed", "error"):
                        finished = True
                except Empty:
                    heartbeat = {
                        'id': f"hb-{int(time.time() * 1000)}",
                        'type': 'heartbeat',
                        'task_id': task_id,
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'payload': {'status': task.status}
                    }
                    yield _format_sse(heartbeat)
                    finished = task.status in ("completed", "error", "cancelled")
        finally:
            _unregister_stream(task_id, queue)

    response = Response(
        stream_with_context(event_generator()),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@report_bp.route('/result/<task_id>', methods=['GET'])
def get_result(task_id: str):
    """
    获取报告生成结果。

    参数:
        task_id: 任务ID。

    返回:
        Response: JSON，包含HTML预览与文件路径。
    """
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404

        if task.status != "completed":
            return jsonify({
                'success': False,
                'error': '报告尚未完成',
                'task': task.to_dict()
            }), 400

        return Response(
            task.html_content,
            mimetype='text/html'
        )

    except Exception as e:
        logger.exception(f"获取报告生成结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/result/<task_id>/json', methods=['GET'])
def get_result_json(task_id: str):
    """获取报告生成结果（JSON格式）"""
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404

        if task.status != "completed":
            return jsonify({
                'success': False,
                'error': '报告尚未完成',
                'task': task.to_dict()
            }), 400

        return jsonify({
            'success': True,
            'task': task.to_dict(),
            'html_content': task.html_content
        })

    except Exception as e:
        logger.exception(f"获取报告生成结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/download/<task_id>', methods=['GET'])
def download_report(task_id: str):
    """
    下载已生成的报告HTML文件。

    参数:
        task_id: 任务ID。

    返回:
        Response: HTML文件的附件下载响应。
    """
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404

        if task.status != "completed" or not task.report_file_path:
            return jsonify({
                'success': False,
                'error': '报告尚未完成或尚未保存'
            }), 400

        if not os.path.exists(task.report_file_path):
            return jsonify({
                'success': False,
                'error': '报告文件不存在或已被删除'
            }), 404

        download_name = task.report_file_name or os.path.basename(task.report_file_path)
        return send_file(
            task.report_file_path,
            mimetype='text/html',
            as_attachment=True,
            download_name=download_name
        )

    except Exception as e:
        logger.exception(f"下载报告失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id: str):
    """
    取消报告生成任务。

    参数:
        task_id: 需要被取消的任务ID。

    返回:
        Response: JSON，包含取消结果或错误信息。
    """
    global current_task

    try:
        with task_lock:
            if current_task and current_task.task_id == task_id:
                if current_task.status == "running":
                    current_task.update_status("cancelled", 0, "用户取消任务")
                    current_task.publish_event('cancelled', {
                        'message': '任务被用户主动终止',
                        'task': current_task.to_dict(),
                    })
                current_task = None
            task = tasks_registry.get(task_id)
            if task and task.status == 'running':
                task.update_status("cancelled", task.progress, "用户取消任务")
                task.publish_event('cancelled', {
                    'message': '任务被用户主动终止',
                    'task': task.to_dict(),
                })

                return jsonify({
                    'success': True,
                    'message': '任务已取消'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '任务不存在或无法取消'
                }), 404

    except Exception as e:
        logger.exception(f"取消报告生成任务失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/templates', methods=['GET'])
def get_templates():
    """
    获取可用模板列表，便于前端展示可选Markdown骨架。

    返回:
        Response: JSON，列出模板名称/描述/大小。
    """
    try:
        if not report_agent:
            return jsonify({
                'success': False,
                'error': 'Report Engine未初始化'
            }), 500

        template_dir = settings.TEMPLATE_DIR
        templates = []

        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('.md'):
                    template_path = os.path.join(template_dir, filename)
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        templates.append({
                            'name': filename.replace('.md', ''),
                            'filename': filename,
                            'description': content.split('\n')[0] if content else '无描述',
                            'size': len(content)
                        })
                    except Exception as e:
                        logger.exception(f"读取模板失败 {filename}: {str(e)}")

        return jsonify({
            'success': True,
            'templates': templates,
            'template_dir': template_dir
        })

    except Exception as e:
        logger.exception(f"获取可用模板列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# 错误处理
@report_bp.errorhandler(404)
def not_found(error):
    """404兜底处理：保证接口统一返回JSON结构"""
    logger.exception(f"API端点不存在: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'API端点不存在'
    }), 404


@report_bp.errorhandler(500)
def internal_error(error):
    """500兜底处理：捕获未被主动捕获的异常"""
    logger.exception(f"服务器内部错误: {str(error)}")
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500


def clear_report_log():
    """
    清空report.log文件，方便新任务只查看本次运行日志。

    返回:
        None
    """
    try:
        log_file = settings.LOG_FILE
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('')
        logger.info(f"已清空日志文件: {log_file}")
    except Exception as e:
        logger.exception(f"清空日志文件失败: {str(e)}")


@report_bp.route('/log', methods=['GET'])
def get_report_log():
    """
    获取report.log内容，并按行去除空白返回。

    返回:
        Response: JSON，包含最新日志行数组。
    """
    try:
        log_file = settings.LOG_FILE
        
        if not os.path.exists(log_file):
            return jsonify({
                'success': True,
                'log_lines': []
            })
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 清理行尾的换行符
        log_lines = [line.rstrip('\n\r') for line in lines if line.strip()]
        
        return jsonify({
            'success': True,
            'log_lines': log_lines
        })
        
    except Exception as e:
        logger.exception(f"读取日志失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'读取日志失败: {str(e)}'
        }), 500


@report_bp.route('/log/clear', methods=['POST'])
def clear_log():
    """
    手动清空日志，提供REST入口供前端一键重置。

    返回:
        Response: JSON，标记是否清理成功。
    """
    try:
        clear_report_log()
        return jsonify({
            'success': True,
            'message': '日志已清空'
        })
    except Exception as e:
        logger.exception(f"清空日志失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'清空日志失败: {str(e)}'
        }), 500
