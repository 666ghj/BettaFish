"""
Flask接口模块
为甘特图生成功能提供RESTful API
"""

from flask import Blueprint, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
import logging

from .excel_parser import ExcelParser
from .gantt_generator import GanttGenerator

logger = logging.getLogger(__name__)

# 创建Blueprint
gantt_bp = Blueprint('gantt', __name__, url_prefix='/api/gantt')

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'outputs')
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@gantt_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    上传Excel文件并生成甘特图

    请求参数:
        - file: Excel文件
        - title: 图表标题（可选）
        - group_by: 分组方式 category/owner/none（可选，默认category）
        - show_progress: 是否显示进度 true/false（可选，默认true）
        - color_scheme: 颜色方案（可选，默认default）

    返回:
        JSON响应，包含任务摘要和图表URL
    """
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400

        file = request.files['file']

        # 检查文件名
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        # 检查文件类型
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件格式，请上传Excel文件(.xlsx或.xls)'}), 400

        # 生成唯一文件名
        filename = secure_filename(file.filename)
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{unique_id}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        # 保存文件
        file.save(file_path)
        logger.info(f"文件已保存: {file_path}")

        # 解析Excel文件
        parser = ExcelParser(file_path)
        tasks = parser.parse()
        summary = parser.get_summary()

        # 获取参数
        title = request.form.get('title', '项目时间轴甘特图')
        group_by = request.form.get('group_by', 'category')
        show_progress = request.form.get('show_progress', 'true').lower() == 'true'
        color_scheme = request.form.get('color_scheme', 'default')

        # 生成甘特图
        generator = GanttGenerator(tasks, color_scheme=color_scheme)
        fig = generator.generate(
            title=title,
            group_by=group_by,
            show_progress=show_progress
        )

        # 保存HTML文件
        output_filename = f"gantt_{timestamp}_{unique_id}.html"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        generator.save_html(output_path)

        # 返回结果
        return jsonify({
            'success': True,
            'message': '甘特图生成成功',
            'summary': summary,
            'file_id': f"{timestamp}_{unique_id}",
            'chart_url': f'/api/gantt/view/{timestamp}_{unique_id}',
            'download_url': f'/api/gantt/download/{timestamp}_{unique_id}'
        }), 200

    except ValueError as e:
        logger.error(f"数据验证错误: {str(e)}")
        return jsonify({'error': f'数据格式错误: {str(e)}'}), 400

    except Exception as e:
        logger.error(f"处理文件时发生错误: {str(e)}", exc_info=True)
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


@gantt_bp.route('/view/<file_id>', methods=['GET'])
def view_chart(file_id):
    """
    查看甘特图HTML

    参数:
        file_id: 文件ID

    返回:
        HTML文件
    """
    try:
        output_filename = f"gantt_{file_id}.html"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        if not os.path.exists(output_path):
            return jsonify({'error': '图表不存在或已过期'}), 404

        return send_file(output_path, mimetype='text/html')

    except Exception as e:
        logger.error(f"查看图表时发生错误: {str(e)}")
        return jsonify({'error': '查看失败'}), 500


@gantt_bp.route('/download/<file_id>', methods=['GET'])
def download_chart(file_id):
    """
    下载甘特图HTML文件

    参数:
        file_id: 文件ID

    返回:
        下载的HTML文件
    """
    try:
        output_filename = f"gantt_{file_id}.html"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        if not os.path.exists(output_path):
            return jsonify({'error': '图表不存在或已过期'}), 404

        return send_file(
            output_path,
            mimetype='text/html',
            as_attachment=True,
            download_name=f"gantt_chart_{file_id}.html"
        )

    except Exception as e:
        logger.error(f"下载图表时发生错误: {str(e)}")
        return jsonify({'error': '下载失败'}), 500


@gantt_bp.route('/list', methods=['GET'])
def list_charts():
    """
    列出所有已生成的甘特图

    返回:
        图表列表
    """
    try:
        charts = []
        for filename in os.listdir(OUTPUT_FOLDER):
            if filename.startswith('gantt_') and filename.endswith('.html'):
                file_path = os.path.join(OUTPUT_FOLDER, filename)
                file_id = filename.replace('gantt_', '').replace('.html', '')
                file_stat = os.stat(file_path)

                charts.append({
                    'file_id': file_id,
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': file_stat.st_size,
                    'view_url': f'/api/gantt/view/{file_id}',
                    'download_url': f'/api/gantt/download/{file_id}'
                })

        # 按创建时间倒序排序
        charts.sort(key=lambda x: x['created_at'], reverse=True)

        return jsonify({
            'success': True,
            'charts': charts,
            'total': len(charts)
        }), 200

    except Exception as e:
        logger.error(f"列出图表时发生错误: {str(e)}")
        return jsonify({'error': '获取列表失败'}), 500


@gantt_bp.route('/delete/<file_id>', methods=['DELETE'])
def delete_chart(file_id):
    """
    删除指定的甘特图

    参数:
        file_id: 文件ID

    返回:
        删除结果
    """
    try:
        output_filename = f"gantt_{file_id}.html"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        if not os.path.exists(output_path):
            return jsonify({'error': '图表不存在'}), 404

        # 删除输出文件
        os.remove(output_path)

        # 尝试删除对应的上传文件
        for filename in os.listdir(UPLOAD_FOLDER):
            if file_id in filename:
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                os.remove(upload_path)
                break

        logger.info(f"已删除图表: {file_id}")

        return jsonify({
            'success': True,
            'message': '删除成功'
        }), 200

    except Exception as e:
        logger.error(f"删除图表时发生错误: {str(e)}")
        return jsonify({'error': '删除失败'}), 500


@gantt_bp.route('/template', methods=['GET'])
def download_template():
    """
    下载Excel模板文件

    返回:
        模板文件
    """
    try:
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'gantt_template.xlsx')

        if not os.path.exists(template_path):
            return jsonify({'error': '模板文件不存在'}), 404

        return send_file(
            template_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='gantt_template.xlsx'
        )

    except Exception as e:
        logger.error(f"下载模板时发生错误: {str(e)}")
        return jsonify({'error': '下载模板失败'}), 500


def create_gantt_routes(app):
    """
    将甘特图路由注册到Flask应用

    Args:
        app: Flask应用实例
    """
    app.register_blueprint(gantt_bp)
    logger.info("甘特图路由已注册")


# 健康检查
@gantt_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'GanttEngine',
        'version': '1.0.0'
    }), 200
