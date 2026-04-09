# main.py
# 新应用入口，替代原 app.py
# TODO(C组): 将原 app.py 中的配置管理路由、健康检查等逻辑迁移至此
# 引擎调度部分替换为 agno Team 调用

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from loguru import logger
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'agno-mirofish-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@socketio.on('start_analysis')
def handle_start_analysis(data):
    """
    接收前端的分析请求，启动 agno Team 分析流程，流式推送进度。
    TODO(C组): 替换下方 mock 为真实的 agno Team 调用
    """
    topic = data.get('topic', '').strip()
    if not topic:
        emit('error', {'message': '请输入分析主题'})
        return

    logger.info(f"收到分析请求: {topic}")
    emit('analysis_started', {'topic': topic})

    # TODO(C组): 替换为真实 agno Team 流式调用
    # from agno_team.opinion_team import create_opinion_team
    # team = create_opinion_team()
    # for chunk in team.run(f"请对以下主题进行全面的舆情分析：{topic}", stream=True):
    #     socketio.emit('analysis_progress', {
    #         'agent': getattr(chunk, 'agent_name', 'system'),
    #         'content': chunk.content,
    #     })

    # Mock（开发阶段占位）
    emit('analysis_progress', {'agent': 'system', 'content': f'[Mock] 正在分析主题：{topic}'})
    emit('analysis_complete', {'message': '分析完成（Mock）'})


@socketio.on('forum_subscribe')
def handle_forum_subscribe():
    """
    前端订阅论坛主持人发言。
    TODO(C组): 接入 ForumAgent 的实时发言推送
    """
    emit('forum_message', {'speaker': 'host', 'content': '[Mock] 主持人发言占位'})


if __name__ == '__main__':
    from config import settings
    logger.info(f"启动服务: http://{settings.HOST}:{settings.PORT}")
    socketio.run(app, host=settings.HOST, port=settings.PORT, debug=False)
