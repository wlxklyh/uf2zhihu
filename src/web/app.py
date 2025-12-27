"""
Flask Web应用主文件
"""
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_socketio import SocketIO, emit
import os
import json
import threading
from datetime import datetime
from typing import Dict, Optional

from ..utils.config import Config
from ..utils.logger import Logger
from ..utils.file_manager import FileManager
from ..core.processor import YouTubeToArticleProcessor

# 全局变量存储应用实例
socketio = None
config = None
logger = None
file_manager = None
processor = None

def create_app() -> Flask:
    """创建Flask应用"""
    global socketio, config, logger, file_manager, processor
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'youtube-to-article-secret-key-2024'
    
    # 初始化SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # 初始化工具类
    config = Config()
    logger = Logger("web_app")
    file_manager = FileManager(config, logger)
    processor = YouTubeToArticleProcessor()
    
    # 设置处理器回调
    processor.set_callbacks(
        progress_callback=send_progress_update,
        step_complete_callback=send_step_complete
    )
    
    # 注册路由
    register_routes(app)
    register_socketio_events()
    
    return app

def register_routes(app: Flask):
    """注册路由"""
    
    @app.route('/')
    def index():
        """主页"""
        try:
            # 获取历史项目
            projects = file_manager.list_projects()
            return render_template('index.html', projects=projects[:10])  # 只显示最近10个项目
        except Exception as e:
            logger.error(f"加载主页失败: {str(e)}")
            return render_template('index.html', projects=[])
    
    @app.route('/process')
    def process_page():
        """处理页面"""
        project_name = request.args.get('project', '')
        youtube_url = request.args.get('url', '')
        return render_template('process.html', project_name=project_name, youtube_url=youtube_url)
    
    @app.route('/results/<project_name>')
    def results_page(project_name: str):
        """结果展示页面"""
        try:
            project_path = os.path.join(config.get('basic', 'output_dir'), project_name)
            if not os.path.exists(project_path):
                abort(404, "项目不存在")
            
            # 获取项目信息
            project_summary = file_manager.get_project_summary(project_path)
            
            # 获取各个步骤的文件
            steps_data = {}
            step_names = ['step1_download', 'step2_transcribe', 
                         'step4_screenshots', 'step5_markdown', 'step6_prompt']
            
            for step_name in step_names:
                steps_data[step_name] = file_manager.get_step_files(project_path, step_name)
            
            return render_template('results.html', 
                                 project_name=project_name,
                                 project_summary=project_summary,
                                 steps_data=steps_data)
        except Exception as e:
            logger.error(f"加载结果页面失败: {str(e)}")
            abort(500, f"加载结果页面失败: {str(e)}")
    
    @app.route('/api/projects')
    def api_projects():
        """获取项目列表API"""
        try:
            projects = file_manager.list_projects()
            return jsonify({
                'success': True,
                'projects': projects
            })
        except Exception as e:
            logger.error(f"获取项目列表失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/start_process', methods=['POST'])
    def api_start_process():
        """开始处理API"""
        try:
            data = request.json
            youtube_url = data.get('youtube_url', '').strip()
            project_name = data.get('project_name', '').strip()
            
            # 验证输入
            if not youtube_url:
                return jsonify({
                    'success': False,
                    'error': 'YouTube URL不能为空'
                }), 400
            
            if not youtube_url.startswith(('https://www.youtube.com/', 'https://youtu.be/')):
                return jsonify({
                    'success': False,
                    'error': 'YouTube URL格式不正确'
                }), 400
            
            # 生成项目名称
            if not project_name:
                project_name = f"youtube_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 使用处理器启动异步处理
            result = processor.start_async_process(youtube_url, project_name)
            
            if not result['success']:
                return jsonify(result), 500
            
            actual_project_name = result['project_name']
            logger.info(f"开始处理项目: {actual_project_name}")
            
            return jsonify({
                'success': True,
                'project_name': actual_project_name,
                'project_path': result['project_path'],
                'message': result['message']
            })
            
        except Exception as e:
            logger.error(f"开始处理失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/step_status/<project_name>/<int:step>')
    def api_step_status(project_name: str, step: int):
        """获取步骤状态API"""
        try:
            result = processor.get_step_status(project_name, step)
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 404 if 'not exist' in result.get('error', '') else 500
            
        except Exception as e:
            logger.error(f"获取步骤状态失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/file_preview/<project_name>/<step_name>/<path:filename>')
    def api_file_preview(project_name: str, step_name: str, filename: str):
        """文件预览API"""
        try:
            project_path = os.path.join(config.get('basic', 'output_dir'), project_name)
            if not os.path.exists(project_path):
                return jsonify({
                    'success': False,
                    'error': '项目不存在'
                }), 404
            
            file_path = os.path.join(project_path, step_name, filename)
            if not os.path.exists(file_path):
                return jsonify({
                    'success': False,
                    'error': '文件不存在'
                }), 404
            
            # 获取文件预览内容
            preview_content = file_manager.get_file_content_preview(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            
            return jsonify({
                'success': True,
                'filename': filename,
                'file_type': file_ext,
                'content': preview_content,
                'file_size': os.path.getsize(file_path)
            })
            
        except Exception as e:
            logger.error(f"文件预览失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/download/<project_name>/<step_name>/<path:filename>')
    def api_download_file(project_name: str, step_name: str, filename: str):
        """文件下载API"""
        try:
            project_path = os.path.join(config.get('basic', 'output_dir'), project_name)
            if not os.path.exists(project_path):
                abort(404, "项目不存在")
            
            file_path = os.path.join(project_path, step_name, filename)
            if not os.path.exists(file_path):
                abort(404, "文件不存在")
            
            return send_file(file_path, as_attachment=True, download_name=filename)
            
        except Exception as e:
            logger.error(f"文件下载失败: {str(e)}")
            abort(500, f"文件下载失败: {str(e)}")
    
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        return render_template('error.html', 
                             error_code=404,
                             error_message="页面不存在"), 404
    
    @app.errorhandler(500)
    def server_error(error):
        """500错误处理"""
        return render_template('error.html',
                             error_code=500,
                             error_message="服务器内部错误"), 500

def send_progress_update(project_name: str, step: int, progress: int, message: str):
    """发送进度更新（供处理模块调用）"""
    if socketio:
        socketio.emit('progress_update', {
            'project_name': project_name,
            'step': step,
            'progress': progress,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

def send_step_complete(project_name: str, step: int, success: bool, message: str):
    """发送步骤完成通知（供处理模块调用）"""
    if socketio:
        socketio.emit('step_complete', {
            'project_name': project_name,
            'step': step,
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

def register_socketio_events():
    """注册SocketIO事件"""
    
    @socketio.on('connect')
    def handle_connect():
        """客户端连接"""
        logger.info("客户端已连接")
        emit('connected', {'message': '连接成功'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接"""
        logger.info("客户端已断开连接")
    
    @socketio.on('join_project')
    def handle_join_project(data):
        """加入项目房间"""
        project_name = data.get('project_name')
        if project_name:
            # 加入房间以接收该项目的更新
            # room = f"project_{project_name}"
            # join_room(room)
            logger.info(f"客户端加入项目: {project_name}")
            emit('joined_project', {'project_name': project_name})

# 导出函数供其他模块使用
def get_socketio():
    """获取SocketIO实例"""
    return socketio

def get_file_manager():
    """获取文件管理器实例"""
    return file_manager
