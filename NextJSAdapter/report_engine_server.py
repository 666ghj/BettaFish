"""
Next.js 适配层 - ReportEngine Flask 接口
这是一个独立的 Flask 应用，专门为 Next.js 项目提供 ReportEngine API
端口: 8502
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 切换到项目根目录（重要：确保能找到 config.py）
os.chdir(str(project_root))
print(f"工作目录已切换到: {os.getcwd()}")

# 导入 ReportEngine
try:
    from ReportEngine.flask_interface import report_bp, initialize_report_engine
    REPORT_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"ReportEngine导入失败: {e}")
    REPORT_ENGINE_AVAILABLE = False

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 注册 ReportEngine Blueprint
if REPORT_ENGINE_AVAILABLE:
    app.register_blueprint(report_bp, url_prefix='/api/report')
    print("✓ ReportEngine Blueprint 已注册")
else:
    print("✗ ReportEngine 不可用")


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'success': True,
        'service': 'ReportEngine',
        'status': 'running',
        'initialized': REPORT_ENGINE_AVAILABLE
    })


if __name__ == '__main__':
    print("=" * 60)
    print("ReportEngine Flask 适配服务")
    print("=" * 60)
    
    if not REPORT_ENGINE_AVAILABLE:
        print("✗ ReportEngine 不可用")
        print("请检查 ReportEngine 模块是否正确安装")
        sys.exit(1)
    
    print("正在初始化 ReportEngine...")
    
    if initialize_report_engine():
        print("✓ ReportEngine 初始化成功")
        print(f"✓ 服务启动在端口 8502")
        print(f"✓ API 端点: http://localhost:8502/api/report/*")
        print("=" * 60)
        app.run(host='0.0.0.0', port=8502, debug=False)
    else:
        print("✗ ReportEngine 初始化失败")
        print("请检查配置和依赖")
        sys.exit(1)
