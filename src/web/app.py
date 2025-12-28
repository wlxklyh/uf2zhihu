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
from ..utils.cache_manager import CacheManager
from ..core.processor import YouTubeToArticleProcessor

# 全局变量存储应用实例
socketio = None
config = None
logger = None
file_manager = None
cache_manager = None
processor = None

def create_app() -> Flask:
    """创建Flask应用"""
    global socketio, config, logger, file_manager, cache_manager, processor
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'youtube-to-article-secret-key-2024'
    
    # 初始化SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # 初始化工具类
    config = Config()
    logger = Logger("web_app")
    file_manager = FileManager(config, logger)
    cache_manager = CacheManager(config, logger)
    processor = YouTubeToArticleProcessor()
    
    # 设置处理器回调
    processor.set_callbacks(
        progress_callback=send_progress_update,
        step_complete_callback=send_step_complete,
        download_progress_callback=send_download_progress,
        transcribe_progress_callback=send_transcribe_progress
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
                         'step3_screenshots', 'step4_markdown', 'step5_prompt']
            
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
            import traceback
            logger.error(f"开始处理失败: {str(e)}")
            logger.error(f"详细错误堆栈:\n{traceback.format_exc()}")
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
    
    @app.route('/api/cache/stats')
    def api_cache_stats():
        """获取缓存统计信息API"""
        try:
            stats = cache_manager.get_cache_stats()
            
            # 格式化大小为可读格式
            def format_size(bytes_size):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_size < 1024.0:
                        return f"{bytes_size:.2f} {unit}"
                    bytes_size /= 1024.0
                return f"{bytes_size:.2f} TB"
            
            return jsonify({
                'success': True,
                'stats': {
                    'videos': {
                        'count': stats['videos']['count'],
                        'size': stats['videos']['size'],
                        'size_formatted': format_size(stats['videos']['size'])
                    },
                    'subtitles_en': {
                        'count': stats['subtitles_en']['count'],
                        'size': stats['subtitles_en']['size'],
                        'size_formatted': format_size(stats['subtitles_en']['size'])
                    },
                    'total_size': stats['videos']['size'] + stats['subtitles_en']['size'],
                    'total_size_formatted': format_size(stats['videos']['size'] + stats['subtitles_en']['size'])
                }
            })
        except Exception as e:
            logger.error(f"获取缓存统计失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/cache/list/<cache_type>')
    def api_cache_list(cache_type: str):
        """列出指定类型的缓存项API"""
        try:
            if cache_type not in ['video', 'subtitle_en']:
                return jsonify({
                    'success': False,
                    'error': '无效的缓存类型'
                }), 400
            
            items = cache_manager.list_cached_items(cache_type)
            
            return jsonify({
                'success': True,
                'cache_type': cache_type,
                'items': items
            })
        except Exception as e:
            logger.error(f"列出缓存失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/cache/clear', methods=['POST'])
    def api_cache_clear():
        """清理缓存API"""
        try:
            data = request.json or {}
            cache_type = data.get('cache_type')  # None表示清理全部
            
            if cache_type and cache_type not in ['video', 'subtitle_en']:
                return jsonify({
                    'success': False,
                    'error': '无效的缓存类型'
                }), 400
            
            cache_manager.clear_cache(cache_type)
            
            cache_name = {
                'video': '视频',
                'subtitle_en': '字幕',
                None: '所有'
            }.get(cache_type, cache_type)
            
            logger.info(f"已清理{cache_name}缓存")
            
            return jsonify({
                'success': True,
                'message': f'已成功清理{cache_name}缓存'
            })
        except Exception as e:
            logger.error(f"清理缓存失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/logs/export/<project_name>')
    def api_logs_export(project_name: str):
        """导出项目日志API"""
        try:
            # 获取日志文件路径
            log_dir = config.get('basic', 'log_dir', './logs')
            
            # 尝试找到最新的日志文件
            today = datetime.now().strftime('%Y%m%d')
            log_file = os.path.join(log_dir, f'processor_{today}.log')
            
            if not os.path.exists(log_file):
                return jsonify({
                    'success': False,
                    'error': '日志文件不存在'
                }), 404
            
            return send_file(log_file, 
                           as_attachment=True, 
                           download_name=f'{project_name}_log_{today}.txt',
                           mimetype='text/plain')
        except Exception as e:
            logger.error(f"导出日志失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/process/retry_step', methods=['POST'])
    def api_retry_step():
        """重试指定步骤API"""
        try:
            data = request.json
            project_name = data.get('project_name')
            step = data.get('step')
            
            if not project_name or not step:
                return jsonify({
                    'success': False,
                    'error': '缺少必要参数'
                }), 400
            
            # TODO: 实现从指定步骤重新开始的逻辑
            # 这需要在processor中添加相应的方法
            
            return jsonify({
                'success': False,
                'error': '此功能正在开发中'
            }), 501
        except Exception as e:
            logger.error(f"重试步骤失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
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

def send_download_progress(project_name: str, step: int, progress_data: Dict):
    """
    发送详细的下载进度（供处理模块调用）
    
    Args:
        project_name: 项目名称
        step: 步骤号
        progress_data: 详细进度数据
    """
    if socketio:
        logger.info(f"[下载] 发送下载进度: 项目={project_name}, 步骤={step}, 进度={progress_data.get('percent', 0)}%")
        socketio.emit('download_progress', {
            'project_name': project_name,
            'step': step,
            'progress_data': progress_data,
            'timestamp': datetime.now().isoformat()
        })
    else:
        logger.warning("[警告] SocketIO未初始化，无法发送下载进度")

def send_transcribe_progress(project_name: str, step: int, progress_data: Dict):
    """
    发送详细的转录进度（供处理模块调用）
    
    Args:
        project_name: 项目名称
        step: 步骤号
        progress_data: 详细进度数据
    """
    if socketio:
        logger.info(f"[转录] 发送转录进度: 项目={project_name}, 步骤={step}, 进度={progress_data.get('percent', 0)}%")
        socketio.emit('transcribe_progress', {
            'project_name': project_name,
            'step': step,
            'progress_data': progress_data,
            'timestamp': datetime.now().isoformat()
        })
    else:
        logger.warning("[警告] SocketIO未初始化，无法发送转录进度")

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
