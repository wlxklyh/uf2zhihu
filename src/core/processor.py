"""
主处理器 - 协调各个步骤的执行
"""
import os
import json
import threading
import time
import traceback
from datetime import datetime
from typing import Dict, Optional, Callable
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.file_manager import FileManager
from src.utils.cache_manager import CacheManager
from src.core.steps.step1_download import YouTubeDownloader
from src.core.steps.step2_transcribe import AudioTranscriber
from src.core.steps.step3_screenshots import VideoScreenshot
from src.core.steps.step4_generate_markdown import MarkdownGenerator
from src.core.steps.step5_generate_prompt import PromptGenerator
from src.core.steps.step6_publish_zhihu import ZhihuPublisher

class YouTubeToArticleProcessor:
    def __init__(self, config_path: str = "config/config.ini"):
        self.config = Config(config_path)
        self.logger = Logger("processor")
        self.file_manager = FileManager(self.config, self.logger)
        self.cache_manager = CacheManager(self.config, self.logger)
        self.current_project = None
        self.current_step = 1
        self.is_processing = False
        self.progress_callback = None
        self.step_complete_callback = None
        self.download_progress_callback = None
        self.transcribe_progress_callback = None
        self.zhihu_publisher = None  # 延迟初始化
        
    def set_callbacks(self, progress_callback: Callable = None, step_complete_callback: Callable = None, download_progress_callback: Callable = None, transcribe_progress_callback: Callable = None):
        """设置回调函数用于Web界面更新"""
        self.progress_callback = progress_callback
        self.step_complete_callback = step_complete_callback
        self.download_progress_callback = download_progress_callback
        self.transcribe_progress_callback = transcribe_progress_callback
    
    def start_async_process(self, youtube_url: str, project_name: str) -> Dict:
        """异步开始处理流程"""
        try:
            # 创建项目目录
            project_path = self.file_manager.create_project_directory(project_name)
            actual_project_name = os.path.basename(project_path)
            
            # 保存项目信息
            project_info = {
                'youtube_url': youtube_url,
                'project_name': project_name,
                'actual_project_name': actual_project_name,
                'created_time': datetime.now().isoformat(),
                'status': 'started',
                'current_step': 1
            }
            
            self.file_manager.update_project_summary(project_path, project_info)
            self.current_project = actual_project_name
            
            # 在后台线程中开始处理
            processing_thread = threading.Thread(
                target=self._process_video,
                args=(youtube_url, project_path),
                daemon=True
            )
            processing_thread.start()
            
            return {
                'success': True,
                'project_name': actual_project_name,
                'project_path': project_path,
                'message': '项目创建成功，开始处理'
            }
            
        except Exception as e:
            import traceback
            self.logger.error(f"启动处理失败: {str(e)}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'message': f'启动处理失败: {str(e)}'
            }
    
    def _process_video(self, youtube_url: str, project_path: str):
        """后台处理视频的主流程"""
        try:
            self.is_processing = True
            project_name = os.path.basename(project_path)
            
            self.logger.info(f"开始处理项目: {project_name}")
            self._send_progress_update(1, 0, "开始处理...")
            
            # 步骤1: 下载YouTube视频
            step1_result = self._execute_step1(youtube_url, project_path)
            if not step1_result:
                self._send_step_complete(1, False, "步骤1失败: YouTube视频下载")
                return
            
            self._send_step_complete(1, True, "步骤1完成: YouTube视频下载")
            
            # 更新项目状态
            self._update_project_status(project_path, 2, "step1_completed")
            
            # 获取视频文件路径
            step1_dir = self.file_manager.get_step_directory(project_path, 'step1_download')
            self.logger.info(f"查找视频文件，目录: {step1_dir}")
            
            video_files = [f for f in os.listdir(step1_dir) if f.endswith('.mp4')]
            if not video_files:
                self.logger.error(f"未找到视频文件，目录内容: {os.listdir(step1_dir)}")
                self._send_step_complete(2, False, "未找到视频文件")
                return
            
            video_file = os.path.join(step1_dir, video_files[0])
            self.logger.info(f"找到视频文件: {video_file}")
            
            # 步骤2: 语音转录
            success = self._execute_step2(video_file, project_path, youtube_url)
            if not success:
                self._send_step_complete(2, False, "步骤2失败: 语音转录")
                return
            
            self._send_step_complete(2, True, "步骤2完成: 语音转录")
            self._update_project_status(project_path, 3, "step2_completed")
            
            # 步骤3: 提取截图（优化版 - 并行处理，仅0s截图）
            success = self._execute_step3(video_file, project_path)
            if not success:
                self._send_step_complete(3, False, "步骤3失败: 提取截图")
                return
            
            self._send_step_complete(3, True, "步骤3完成: 提取截图（并行处理）")
            self._update_project_status(project_path, 4, "step3_completed")
            
            # 步骤4: 生成英文Markdown（图文并茂）
            success = self._execute_step4(project_path)
            if not success:
                self._send_step_complete(4, False, "步骤4失败: 生成英文Markdown")
                return
            
            self._send_step_complete(4, True, "步骤4完成: 生成英文Markdown")
            self._update_project_status(project_path, 5, "step4_completed")
            
            # 步骤5: 生成中文优化Prompt
            success = self._execute_step5(project_path)
            if not success:
                self._send_step_complete(5, False, "步骤5失败: 生成中文Prompt")
                return
            
            self._send_step_complete(5, True, "步骤5完成: 生成中文Prompt")
            self._update_project_status(project_path, 5, "completed")
            
            self.logger.success("所有步骤完成！")
            
        except Exception as e:
            self.logger.error(f"处理异常: {str(e)}")
            self._send_step_complete(self.current_step, False, f"处理异常: {str(e)}")
        finally:
            self.is_processing = False
    
    def _execute_step1(self, youtube_url: str, project_path: str) -> bool:
        """执行步骤1: YouTube视频下载"""
        try:
            self._send_progress_update(1, 10, "初始化下载器...")
            
            # 定义下载进度回调函数
            def download_progress_callback(progress_data: Dict):
                """下载进度回调"""
                self._send_download_progress(1, progress_data)
            
            # 创建下载器，传入进度回调
            downloader = YouTubeDownloader(self.config, self.logger, download_progress_callback)
            
            # 获取步骤1输出目录
            step1_dir = self.file_manager.get_step_directory(project_path, 'step1_download')
            
            self._send_progress_update(1, 20, "开始下载YouTube视频...")
            
            # 执行下载
            result = downloader.download_video(youtube_url, step1_dir)
            
            if result['success']:
                self._send_progress_update(1, 90, "下载完成，保存信息...")
                
                # 保存步骤信息
                step_info = {
                    'step': 1,
                    'status': 'completed',
                    'video_info': result['video_info'],
                    'output_files': {
                        'video_file': result['video_file'],
                        'info_file': result['info_file']
                    }
                }
                
                self.file_manager.save_step_info(project_path, 'step1_download', step_info)
                self.file_manager.save_step_log(project_path, 'step1_download', 
                                              f"下载成功: {result['message']}")
                
                self._send_progress_update(1, 100, "步骤1完成")
                return True
            else:
                self.file_manager.save_step_log(project_path, 'step1_download', 
                                              f"下载失败: {result['error']}")
                return False
                
        except Exception as e:
            self.logger.error(f"步骤1执行异常: {str(e)}")
            self.file_manager.save_step_log(project_path, 'step1_download', 
                                          f"执行异常: {str(e)}")
            return False
    
    def _send_progress_update(self, step: int, progress: int, message: str):
        """发送进度更新"""
        if self.progress_callback:
            self.progress_callback(self.current_project, step, progress, message)
        self.logger.info(f"[步骤{step}] {progress}% - {message}")
    
    def _send_download_progress(self, step: int, progress_data: Dict):
        """
        发送详细的下载进度更新
        
        Args:
            step: 步骤号
            progress_data: 进度数据字典
        """
        if self.download_progress_callback:
            self.download_progress_callback(self.current_project, step, progress_data)
    
    def _send_transcribe_progress(self, step: int, progress_data: Dict):
        """
        发送详细的转录进度更新
        
        Args:
            step: 步骤号
            progress_data: 进度数据字典
        """
        if self.transcribe_progress_callback:
            self.transcribe_progress_callback(self.current_project, step, progress_data)
    
    def _send_step_complete(self, step: int, success: bool, message: str):
        """发送步骤完成通知"""
        if self.step_complete_callback:
            self.step_complete_callback(self.current_project, step, success, message)
        
        if success:
            self.logger.success(f"[步骤{step}] {message}")
        else:
            self.logger.error(f"[步骤{step}] {message}")
    
    def _update_project_status(self, project_path: str, current_step: int, status: str):
        """更新项目状态"""
        try:
            summary = self.file_manager.get_project_summary(project_path)
            summary.update({
                'current_step': current_step,
                'status': status,
                'last_updated': datetime.now().isoformat()
            })
            self.file_manager.update_project_summary(project_path, summary)
        except Exception as e:
            self.logger.error(f"更新项目状态失败: {str(e)}")
    
    def get_step_status(self, project_name: str, step: int) -> Dict:
        """获取步骤状态"""
        try:
            project_path = os.path.join(self.config.get('basic', 'output_dir'), project_name)
            if not os.path.exists(project_path):
                return {'success': False, 'error': '项目不存在'}
            
            step_names = {
                1: 'step1_download',
                2: 'step2_transcribe', 
                3: 'step3_screenshots',
                4: 'step4_markdown',
                5: 'step5_prompt'
            }
            
            step_name = step_names.get(step)
            if not step_name:
                return {'success': False, 'error': '无效的步骤号'}
            
            step_files = self.file_manager.get_step_files(project_path, step_name)
            
            return {
                'success': True,
                'step': step,
                'step_name': step_name,
                'files': step_files
            }
            
        except Exception as e:
            self.logger.error(f"获取步骤状态失败: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _execute_step2(self, video_file: str, project_path: str, youtube_url: str) -> bool:
        """执行步骤2: 语音转录"""
        try:
            self.logger.info(f"步骤2开始，视频文件: {video_file}")
            self._send_progress_update(2, 10, "检查英文字幕缓存...")
            
            # 检查缓存
            if self.config.get_boolean('basic', 'enable_cache', True):
                self.logger.info("缓存已启用，检查英文字幕缓存...")
                cached_result = self.cache_manager.get_cached_english_subtitles(youtube_url)
                if cached_result:
                    self.logger.info("找到缓存的英文字幕，直接使用")
                    cached_srt_path, cached_info = cached_result
                    step2_dir = self.file_manager.get_step_directory(project_path, 'step2_transcribe')
                    output_srt = os.path.join(step2_dir, 'english_subtitles.srt')
                    
                    import shutil
                    shutil.copy2(cached_srt_path, output_srt)
                    
                    self._send_progress_update(2, 100, "使用缓存的英文字幕")
                    return True
                else:
                    self.logger.info("未找到缓存的英文字幕，需要进行转录")
            
            self._send_progress_update(2, 20, "初始化Whisper模型...")
            
            # 创建转录器
            self.logger.info("创建AudioTranscriber实例...")
            transcriber = AudioTranscriber(self.config, self.logger)
            
            # 定义转录进度回调函数
            def transcribe_progress_callback(progress_data: Dict):
                """转录进度回调"""
                self._send_transcribe_progress(2, progress_data)
            
            # 设置进度回调，使转录进度能实时更新到Web界面
            transcriber.progress_callback = transcribe_progress_callback
            self.logger.info("转录进度回调已设置")
            
            # 获取步骤2输出目录
            step2_dir = self.file_manager.get_step_directory(project_path, 'step2_transcribe')
            self.logger.info(f"输出目录: {step2_dir}")
            
            self._send_progress_update(2, 30, "开始语音转录...")
            
            # 执行转录
            self.logger.info("调用transcriber.transcribe_video()...")
            result = transcriber.transcribe_video(video_file, step2_dir, youtube_url)
            
            self.logger.info(f"转录结果: success={result.get('success', False)}")
            
            if result['success']:
                self._send_progress_update(2, 90, "转录完成，保存信息...")
                self.logger.info(f"转录成功，字幕文件: {result.get('srt_file')}")
                
                # 缓存英文字幕
                if self.config.get_boolean('basic', 'enable_cache', True):
                    self.logger.info("缓存英文字幕...")
                    self.cache_manager.cache_english_subtitles(youtube_url, result['srt_file'], result['transcribe_stats'])
                
                self._send_progress_update(2, 100, "步骤2完成")
                return True
            else:
                self.logger.error(f"转录失败: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"步骤2执行异常: {str(e)}")
            return False
    
    
    def _execute_step3(self, video_file: str, project_path: str) -> bool:
        """执行步骤3: 提取截图"""
        try:
            self._send_progress_update(3, 10, "初始化截图提取器...")
            
            # 创建截图提取器
            screenshot = VideoScreenshot(self.config, self.logger)
            
            # 获取英文字幕文件
            step2_dir = self.file_manager.get_step_directory(project_path, 'step2_transcribe')
            srt_file = os.path.join(step2_dir, 'english_subtitles.srt')
            
            # 获取步骤3输出目录
            step3_dir = self.file_manager.get_step_directory(project_path, 'step3_screenshots')
            
            self._send_progress_update(3, 20, "开始提取截图...")
            
            # 执行截图提取
            result = screenshot.extract_screenshots(video_file, srt_file, step3_dir)
            
            if result['success']:
                self._send_progress_update(3, 100, "步骤3完成")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"步骤3执行异常: {str(e)}")
            return False
    
    def _execute_step4(self, project_path: str) -> bool:
        """执行步骤4: 生成英文Markdown文章（图文并茂）"""
        try:
            self._send_progress_update(4, 10, "初始化Markdown生成器...")
            
            # 创建Markdown生成器
            generator = MarkdownGenerator(self.config, self.logger)
            
            # 获取输入文件路径（使用英文字幕，不使用中文）
            step2_dir = self.file_manager.get_step_directory(project_path, 'step2_transcribe')
            srt_file = os.path.join(step2_dir, 'english_subtitles.srt')
            
            step3_dir = self.file_manager.get_step_directory(project_path, 'step3_screenshots')
            screenshots_dir = os.path.join(step3_dir, 'screenshots')
            
            step1_dir = self.file_manager.get_step_directory(project_path, 'step1_download')
            video_info_file = os.path.join(step1_dir, 'video_info.json')
            
            # 获取步骤4输出目录
            step4_dir = self.file_manager.get_step_directory(project_path, 'step4_markdown')
            output_file = os.path.join(step4_dir, 'article.md')
            
            self._send_progress_update(4, 30, "开始生成英文Markdown文章（包含截图）...")
            
            # 执行生成
            result = generator.generate_markdown(srt_file, screenshots_dir, video_info_file, output_file)
            
            if result['success']:
                self._send_progress_update(4, 100, "步骤4完成: 生成英文Markdown")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"步骤4执行异常: {str(e)}")
            return False
    
    def _execute_step5(self, project_path: str) -> bool:
        """执行步骤5: 生成Prompt文件（支持多模板）"""
        try:
            self._send_progress_update(5, 10, "初始化Prompt生成器...")
            
            # 创建Prompt生成器
            generator = PromptGenerator(self.config, self.logger)
            
            # 获取输入文件路径
            step4_dir = self.file_manager.get_step_directory(project_path, 'step4_markdown')
            markdown_file = os.path.join(step4_dir, 'article.md')
            
            step1_dir = self.file_manager.get_step_directory(project_path, 'step1_download')
            video_info_file = os.path.join(step1_dir, 'video_info.json')
            
            # 获取步骤5输出目录（传递目录而不是文件路径）
            step5_dir = self.file_manager.get_step_directory(project_path, 'step5_prompt')
            
            self._send_progress_update(5, 30, "开始生成Prompt文件...")
            
            # 执行生成（传递目录路径）
            result = generator.generate_prompt(markdown_file, video_info_file, step5_dir)
            
            if result['success']:
                # 输出详细日志
                self.logger.info(f"成功生成 {result['total_generated']} 个Prompt文件")
                for prompt_file in result.get('prompt_files', []):
                    self.logger.info(f"  - {prompt_file['template']}: {os.path.basename(prompt_file['output_file'])}")
                
                self._send_progress_update(5, 100, f"步骤5完成 - 生成了{result['total_generated']}个文件")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"步骤5执行异常: {str(e)}")
            return False
    
    def _get_zhihu_publisher(self) -> ZhihuPublisher:
        """获取知乎发布器实例（延迟初始化）"""
        if self.zhihu_publisher is None:
            self.zhihu_publisher = ZhihuPublisher(self.config, self.logger)
        return self.zhihu_publisher
    
    def execute_step6_manual(self, project_name: str, action: str, **kwargs) -> Dict:
        """
        手动执行步骤6操作
        
        Args:
            project_name: 项目名称
            action: 操作类型 ('get_qrcode', 'check_login', 'publish', 'list_files')
            **kwargs: 其他参数
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 获取项目路径
            project_path = os.path.join(self.config.get('basic', 'output_dir'), project_name)
            if not os.path.exists(project_path):
                return {
                    'success': False,
                    'error': '项目不存在',
                    'message': f'项目不存在: {project_name}'
                }
            
            publisher = self._get_zhihu_publisher()
            
            if action == 'get_qrcode':
                # 获取二维码
                result = publisher.get_qrcode()
                return result
                
            elif action == 'check_login':
                # 检查登录状态
                qrcode_token = kwargs.get('qrcode_token', '')
                if not qrcode_token:
                    return {
                        'success': False,
                        'error': '缺少 qrcode_token 参数'
                    }
                result = publisher.check_login_status(qrcode_token)
                return result
                
            elif action == 'publish':
                # 发布文章
                markdown_file = kwargs.get('markdown_file', '')
                title = kwargs.get('title', '')
                topics = kwargs.get('topics', [])
                
                if not markdown_file:
                    return {
                        'success': False,
                        'error': '缺少 markdown_file 参数'
                    }
                
                if not title:
                    return {
                        'success': False,
                        'error': '缺少 title 参数'
                    }
                
                # 检查文件是否存在
                markdown_path = os.path.join(project_path, 'FinalOutput', markdown_file)
                if not os.path.exists(markdown_path):
                    return {
                        'success': False,
                        'error': f'Markdown 文件不存在: {markdown_file}'
                    }
                
                # 转换 Markdown
                convert_result = publisher.convert_markdown_to_zhihu(markdown_path, project_path)
                if not convert_result['success']:
                    return convert_result
                
                # 发布文章
                publish_result = publisher.publish_article(
                    title=title,
                    content=convert_result['content'],
                    topics=topics if topics else []
                )
                
                return publish_result
                
            elif action == 'list_files':
                # 列出 FinalOutput 下的文件
                files = publisher.list_finaloutput_files(project_path)
                return {
                    'success': True,
                    'files': files,
                    'count': len(files)
                }
                
            elif action == 'check_login_status':
                # 检查当前登录状态
                is_logged_in = publisher.is_logged_in()
                return {
                    'success': True,
                    'is_logged_in': is_logged_in,
                    'message': '已登录' if is_logged_in else '未登录'
                }
                
            else:
                return {
                    'success': False,
                    'error': f'未知的操作类型: {action}'
                }
                
        except Exception as e:
            error_msg = f"步骤6操作失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }