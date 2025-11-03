"""
Next.js 适配层 - QueryEngine Flask 接口
这是一个独立的 Flask 应用，专门为 Next.js 项目提供 QueryEngine API
端口: 8503
"""

import os
import sys
import json
import threading
import time
import glob
from datetime import datetime
from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 切换到项目根目录（重要：确保能找到 config.py）
os.chdir(str(project_root))
print(f"工作目录已切换到: {os.getcwd()}")

# 导入 QueryEngine
try:
    from QueryEngine.agent import DeepSearchAgent
    from QueryEngine.utils.config import load_config
    QUERY_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"QueryEngine导入失败: {e}")
    QUERY_ENGINE_AVAILABLE = False

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 全局变量
query_agent = None
current_task = None
task_lock = threading.Lock()


class SearchTask:
    """搜索任务类"""
    
    def __init__(self, task_id: str, query: str, tool_name: str, kwargs: dict):
        self.task_id = task_id
        self.query = query
        self.tool_name = tool_name
        self.kwargs = kwargs
        self.status = "pending"  # pending, running, completed, error
        self.progress = 0
        self.result = None
        self.error_message = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.markdown_file = ""
        
    def update_status(self, status: str, progress: int = None, error_message: str = ""):
        """更新任务状态"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if error_message:
            self.error_message = error_message
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'task_id': self.task_id,
            'query': self.query,
            'tool_name': self.tool_name,
            'status': self.status,
            'progress': self.progress,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'has_result': bool(self.result),
            'markdown_file': self.markdown_file
        }


def initialize_query_engine():
    """初始化 QueryEngine"""
    global query_agent
    try:
        if not QUERY_ENGINE_AVAILABLE:
            print("QueryEngine 不可用")
            return False
        
        print(f"当前工作目录: {os.getcwd()}")
        print(f"检查配置文件...")
        
        # 检查配置文件是否存在
        config_exists = False
        for candidate in ("config.py", "config.env", ".env"):
            if os.path.exists(candidate):
                print(f"  ✓ 找到配置文件: {candidate}")
                config_exists = True
                break
        
        if not config_exists:
            print("  ✗ 未找到配置文件 (config.py, config.env, .env)")
            print("  请在 BettaFish 根目录创建 config.py")
            return False
        
        print("正在加载配置...")
        config = load_config()
        
        print("正在初始化 DeepSearchAgent...")
        query_agent = DeepSearchAgent(config)
        
        print("✓ QueryEngine 初始化成功")
        return True
        
    except FileNotFoundError as e:
        print(f"✗ 配置文件错误: {str(e)}")
        return False
    except ValueError as e:
        print(f"✗ 配置验证失败: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ QueryEngine 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_search_task(task: SearchTask):
    """在后台线程中运行搜索任务"""
    global current_task
    
    try:
        task.update_status("running", 5)
        print(f"开始深度搜索: query={task.query}, tool={task.tool_name}")
        
        # 调用完整的深度搜索流程（包括报告生成）
        # 这会自动执行：结构生成 -> 多轮搜索 -> 反思 -> 总结 -> 报告生成
        final_report = query_agent.research(task.query, save_report=True)
        
        task.update_status("running", 95)
        
        # 获取进度摘要
        progress_summary = query_agent.get_progress_summary()
        
        # 构建结果
        result = {
            'final_report': final_report,
            'total_paragraphs': progress_summary.get('total_paragraphs', 0),
            'completed_paragraphs': progress_summary.get('completed_paragraphs', 0),
            'total_search_queries': progress_summary.get('total_search_queries', 0),
            'query': task.query,
            'tool_name': task.tool_name
        }
        
        # 检查是否生成了 Markdown 文件
        output_dir = query_agent.config.output_dir
        if output_dir and os.path.exists(output_dir):
            # 查找最新的报告文件
            pattern = os.path.join(output_dir, "deep_search_report_*.md")
            files = glob.glob(pattern)
            if files:
                latest_file = max(files, key=os.path.getctime)
                task.markdown_file = latest_file
                result['markdown_file'] = latest_file
                print(f"✓ 报告已保存: {latest_file}")
        
        task.result = result
        task.update_status("completed", 100)
        print(f"深度搜索完成: task_id={task.task_id}")
        print(f"  - 段落数: {result['total_paragraphs']}")
        print(f"  - 搜索次数: {result['total_search_queries']}")
        print(f"  - 报告长度: {len(final_report)} 字符")
            
    except Exception as e:
        error_msg = str(e)
        print(f"搜索任务失败: {error_msg}")
        import traceback
        traceback.print_exc()
        task.update_status("error", 0, error_msg)
        # 只在出错时清理任务
        with task_lock:
            if current_task and current_task.task_id == task.task_id:
                current_task = None


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'success': True,
        'service': 'QueryEngine',
        'status': 'running',
        'initialized': query_agent is not None
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取 QueryEngine 状态"""
    try:
        return jsonify({
            'success': True,
            'initialized': query_agent is not None,
            'current_task': current_task.to_dict() if current_task else None,
            'service': 'QueryEngine',
            'port': 8503
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['POST'])
def start_search():
    """开始搜索任务"""
    global current_task
    
    try:
        # 检查是否有任务在运行
        with task_lock:
            if current_task and current_task.status == "running":
                return jsonify({
                    'success': False,
                    'error': '已有搜索任务在运行中',
                    'current_task': current_task.to_dict()
                }), 400
            
            # 如果有已完成的任务，清理它
            if current_task and current_task.status in ["completed", "error"]:
                current_task = None
        
        # 获取请求参数
        data = request.get_json() or {}
        query = data.get('query', '')
        tool_name = data.get('toolName', 'general_search')
        kwargs = data.get('kwargs', {})
        
        if not query:
            return jsonify({
                'success': False,
                'error': '缺少必要参数: query'
            }), 400
        
        # 检查 QueryEngine 是否初始化
        if not query_agent:
            return jsonify({
                'success': False,
                'error': 'QueryEngine 未初始化'
            }), 500
        
        # 创建新任务
        task_id = f"search_{int(time.time())}"
        task = SearchTask(task_id, query, tool_name, kwargs)
        
        with task_lock:
            current_task = task
        
        # 在后台线程中运行搜索
        thread = threading.Thread(
            target=run_search_task,
            args=(task,),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '搜索任务已启动',
            'task': task.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id: str):
    """获取搜索任务进度"""
    try:
        if not current_task or current_task.task_id != task_id:
            # 如果任务不存在，可能是已经完成并被清理了
            return jsonify({
                'success': True,
                'task': {
                    'task_id': task_id,
                    'status': 'completed',
                    'progress': 100,
                    'error_message': '',
                    'has_result': True
                }
            })
        
        return jsonify({
            'success': True,
            'task': current_task.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/result/<task_id>', methods=['GET'])
def get_result(task_id: str):
    """获取搜索结果"""
    try:
        if not current_task or current_task.task_id != task_id:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        if current_task.status != "completed":
            return jsonify({
                'success': False,
                'error': '搜索尚未完成',
                'task': current_task.to_dict()
            }), 400
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'result': current_task.result,
            'markdown_file': current_task.markdown_file
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("QueryEngine Flask 适配服务")
    print("=" * 60)
    print("正在初始化 QueryEngine...")
    
    if initialize_query_engine():
        print("✓ QueryEngine 初始化成功")
        print(f"✓ 服务启动在端口 8503")
        print(f"✓ API 端点: http://localhost:8503/api/*")
        print("=" * 60)
        app.run(host='0.0.0.0', port=8503, debug=False)
    else:
        print("✗ QueryEngine 初始化失败")
        print("请检查配置和依赖")
        sys.exit(1)
