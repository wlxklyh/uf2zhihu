"""
步骤1：YouTube视频下载模块
参考成功的实现，使用subprocess调用yt-dlp命令行
"""
import subprocess
import os
import json
import shutil
from datetime import datetime
from typing import Dict, Optional, Callable
import sys
import traceback
import re
import time
import threading

# 尝试导入 yt_dlp Python API
try:
    import yt_dlp
    YT_DLP_API_AVAILABLE = True
except ImportError:
    YT_DLP_API_AVAILABLE = False

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.file_manager import FileManager
from src.utils.cache_manager import CacheManager

class YouTubeDownloader:
    def __init__(self, config: Config, logger: Logger, progress_callback: Optional[Callable] = None):
        self.config = config
        self.logger = logger
        self.output_dir = None
        self.cache_manager = CacheManager(config, logger)
        self.enable_cache = config.get_boolean('basic', 'enable_cache', True)
        self.progress_callback = progress_callback
        self.last_progress_time = None
        self.download_start_time = None
        
    def check_dependencies(self):
        """检查yt-dlp是否可用"""
        yt_dlp_available = False
        yt_dlp_command = None
        
        # 先尝试直接命令
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                yt_dlp_available = True
                yt_dlp_command = ['yt-dlp']
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            # 尝试使用python模块方式
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'yt_dlp', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    yt_dlp_available = True
                    yt_dlp_command = [sys.executable, '-m', 'yt_dlp']
            except Exception:
                pass
        
        return yt_dlp_available, yt_dlp_command
        
    def download_video(self, url: str, output_dir: str) -> Dict:
        """
        下载YouTube视频
        
        Args:
            url: YouTube视频URL
            output_dir: 输出目录
            
        Returns:
            Dict: 包含视频信息和文件路径的字典
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤1开始] YouTube视频下载")
        self.logger.info(f"视频URL: {url}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info("=" * 60)
        
        download_start_time = time.time()
        
        try:
            # 检查缓存
            self.logger.info("[检查] 检查视频缓存...")
            if self.enable_cache:
                self.logger.info("[成功] 缓存功能已启用")
                cached_result = self.cache_manager.get_cached_video(url)
                if cached_result:
                    self.logger.info("[成功] 找到缓存的视频！")
                    cached_video_path, cached_info = cached_result
                    
                    self.logger.info(f"[缓存] 缓存视频路径: {cached_video_path}")
                    self.logger.info(f"[缓存] 缓存视频标题: {cached_info.get('title', '未知')}")
                    
                    # 复制缓存文件到输出目录
                    output_filename = os.path.basename(cached_video_path)
                    output_video_path = os.path.join(output_dir, output_filename)
                    
                    if not os.path.exists(output_video_path):
                        self.logger.info(f"[复制] 正在复制缓存文件到输出目录...")
                        shutil.copy2(cached_video_path, output_video_path)
                        self.logger.success(f"[成功] 从缓存复制视频完成: {output_filename}")
                    else:
                        self.logger.info(f"[成功] 输出目录已存在该文件，跳过复制")
                    
                    # 更新文件路径
                    cached_info['file_path'] = output_video_path
                    cached_info['file_size'] = os.path.getsize(output_video_path)
                    
                    # 保存视频信息到JSON文件
                    info_file = os.path.join(output_dir, 'video_info.json')
                    with open(info_file, 'w', encoding='utf-8') as f:
                        json.dump(cached_info, f, ensure_ascii=False, indent=2)
                    
                    self.logger.file_created(info_file)
                    
                    elapsed_time = time.time() - download_start_time
                    self.logger.info("=" * 60)
                    self.logger.success(f"[步骤1完成] 使用缓存视频 (耗时: {elapsed_time:.2f}秒)")
                    self.logger.info("=" * 60)
                    
                    return {
                        'success': True,
                        'video_info': cached_info,
                        'video_file': output_video_path,
                        'info_file': info_file,
                        'message': f'使用缓存视频: {cached_info["title"]}',
                        'from_cache': True
                    }
                else:
                    self.logger.info("[信息] 未找到缓存，需要下载")
            else:
                self.logger.info("[信息] 缓存功能未启用")
                
            # 检查依赖
            self.logger.info("[检查] 检查yt-dlp依赖...")
            yt_dlp_available, yt_dlp_command = self.check_dependencies()
            if not yt_dlp_available:
                self.logger.error("[错误] yt-dlp不可用")
                raise Exception("yt-dlp不可用，请先安装: pip install yt-dlp")
            
            self.logger.success(f"[成功] yt-dlp可用: {' '.join(yt_dlp_command)}")
            
            # 设置输出目录
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
            self.logger.info(f"[目录] 输出目录已创建: {output_dir}")
            
            # 先获取视频信息
            self.logger.info("[获取] 正在获取视频信息...")
            video_info = self._get_video_info(url, yt_dlp_command)
            if not video_info:
                self.logger.error("[错误] 无法获取视频信息")
                raise Exception("无法获取视频信息")
            
            self.logger.info("[视频] 视频信息:")
            self.logger.info(f"  - 标题: {video_info['title']}")
            self.logger.info(f"  - 时长: {video_info['duration']} 秒 ({video_info['duration']//60}分{video_info['duration']%60}秒)")
            self.logger.info(f"  - 上传者: {video_info['uploader']}")
            self.logger.info(f"  - 视频ID: {video_info.get('video_id', '未知')}")
            self.logger.info(f"  - 可用格式: {video_info.get('formats_available', '未知')}")
            
            # 下载视频
            self.logger.info("[下载] 开始下载视频文件...")
            video_file = self._download_video_file(url, output_dir, yt_dlp_command)
            if not video_file:
                self.logger.error("[错误] 视频下载失败")
                raise Exception("视频下载失败")
            
            self.logger.success(f"[成功] 视频下载完成: {os.path.basename(video_file)}")
            
            # 验证下载的视频文件
            self.logger.info("[验证] 正在验证视频文件...")
            is_valid, validation_message = Validator.validate_video_file(video_file)
            if not is_valid:
                self.logger.error(f"[错误] 视频文件验证失败: {validation_message}")
                raise Exception(f"视频文件验证失败: {validation_message}")
            
            self.logger.success(f"[成功] 视频文件验证通过: {validation_message}")
            
            # 更新视频信息
            video_info['file_path'] = video_file
            video_info['file_size'] = os.path.getsize(video_file)
            
            file_size_mb = video_info['file_size'] / 1024 / 1024
            self.logger.info(f"[信息] 文件大小: {file_size_mb:.2f} MB")
            
            # 保存视频信息到JSON文件
            self.logger.info("[保存] 保存视频信息...")
            info_file = os.path.join(output_dir, 'video_info.json')
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)
            
            self.logger.file_created(info_file)
            
            # 缓存下载的视频
            if self.enable_cache:
                self.logger.info("[缓存] 正在缓存视频...")
                try:
                    self.cache_manager.cache_video(url, video_file, video_info)
                    self.logger.success("[成功] 视频已缓存")
                except Exception as cache_error:
                    self.logger.warning(f"[警告] 视频缓存失败: {str(cache_error)}")
            
            elapsed_time = time.time() - download_start_time
            self.logger.info("=" * 60)
            self.logger.success(f"[步骤1完成] 视频下载成功 (耗时: {elapsed_time:.2f}秒)")
            self.logger.info(f"[文件] 视频文件: {video_file}")
            self.logger.info(f"[文件] 信息文件: {info_file}")
            self.logger.info("=" * 60)
            
            return {
                'success': True,
                'video_info': video_info,
                'video_file': video_file,
                'info_file': info_file,
                'message': f'视频下载成功: {video_info["title"]}',
                'from_cache': False
            }
            
        except Exception as e:
            elapsed_time = time.time() - download_start_time
            error_msg = f"视频下载失败: {str(e)}"
            self.logger.error("=" * 60)
            self.logger.error(f"[步骤1失败] {error_msg} (耗时: {elapsed_time:.2f}秒)")
            self.logger.error(f"[错误] 详细错误信息:")
            self.logger.error(f"  - 错误类型: {type(e).__name__}")
            self.logger.error(f"  - 错误信息: {str(e)}")
            self.logger.error(f"[堆栈] 堆栈追踪:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.logger.error(f"  {line}")
            self.logger.error("=" * 60)
            
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def _get_video_info(self, url: str, yt_dlp_command: list) -> Optional[Dict]:
        """获取视频信息"""
        try:
            self.logger.info("正在获取视频信息...")
            
            # 构建命令获取视频信息
            cmd = yt_dlp_command + [
                '--dump-json',
                '--no-playlist',
                '--quiet',
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=60
            )
            
            if result.returncode != 0:
                self.logger.error(f"获取视频信息失败: {result.stderr}")
                return None
            
            # 解析JSON
            info = json.loads(result.stdout)
            
            # 提取关键信息
            video_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'description': info.get('description', '')[:500],  # 限制描述长度
                'url': url,
                'video_id': info.get('id', ''),
                'formats_available': len(info.get('formats', []))
            }
            
            return video_info
            
        except Exception as e:
            self.logger.error(f"获取视频信息异常: {str(e)}")
            return None
    
    def _download_video_file(self, url: str, output_dir: str, yt_dlp_command: list) -> Optional[str]:
        """
        下载视频文件（使用 yt-dlp Python API）
        
        Args:
            url: YouTube视频URL
            output_dir: 输出目录
            yt_dlp_command: yt-dlp命令（用于兼容性检查，实际使用API）
            
        Returns:
            str: 下载的视频文件路径，失败返回 None
        """
        try:
            self.logger.info("开始下载视频文件...")
            
            # 检查是否可以使用 Python API
            if not YT_DLP_API_AVAILABLE:
                self.logger.warning("yt-dlp Python API 不可用，回退到命令行方式")
                return self._download_video_file_legacy(url, output_dir, yt_dlp_command)
            
            # 获取配置
            quality = self.config.get('step1_download', 'quality', 'best')
            format_pref = self.config.get('step1_download', 'format', 'mp4')
            download_timeout = self.config.get_int('step1_download', 'download_timeout', 1200)
            
            # 使用简单的输出模板，避免特殊字符
            output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
            
            # 配置 yt-dlp 选项
            ydl_opts = {
                'format': f'best[ext={format_pref}]/best',
                'outtmpl': output_template,
                'no_warnings': True,
                'noprogress': False,
                'progress_hooks': [self._progress_hook],
                'quiet': False,
                'no_color': True,
            }
            
            # 初始化下载状态
            self.download_start_time = time.time()
            self.last_progress_time = time.time()
            self.download_completed = False
            self.download_error = None
            
            self.logger.info("[下载] 使用 yt-dlp Python API 开始下载...")
            self.logger.info(f"[状态] 进度回调状态: {'已设置' if self.progress_callback else '未设置'}")
            
            # 执行下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 启动超时监控线程
                timeout_thread = threading.Thread(
                    target=self._monitor_timeout,
                    args=(download_timeout,),
                    daemon=True
                )
                timeout_thread.start()
                
                try:
                    ydl.download([url])
                    self.download_completed = True
                except Exception as e:
                    self.download_error = str(e)
                    raise
            
            # 检查是否因超时而失败
            if self.download_error and 'timeout' in self.download_error.lower():
                self.logger.error(f"下载超时: {self.download_error}")
                return None
            
            # 查找下载的文件
            downloaded_files = self._find_downloaded_files(output_dir)
            if not downloaded_files:
                self.logger.error("未找到下载的视频文件")
                return None
            
            video_file = downloaded_files[0]
            self.logger.success(f"视频下载完成: {os.path.basename(video_file)}")
            
            return video_file
            
        except Exception as e:
            error_msg = f"下载异常: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    def _download_video_file_legacy(self, url: str, output_dir: str, yt_dlp_command: list) -> Optional[str]:
        """下载视频文件（命令行方式，作为回退方案）"""
        try:
            # 获取配置
            quality = self.config.get('step1_download', 'quality', 'best')
            format_pref = self.config.get('step1_download', 'format', 'mp4')
            download_timeout = self.config.get_int('step1_download', 'download_timeout', 1200)
            
            # 使用简单的输出模板，避免特殊字符
            output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
            
            # 构建下载命令
            cmd = yt_dlp_command + [
                '-f', f'best[ext={format_pref}]/best',
                '--no-playlist',
                '--output', output_template,
                '--no-warnings',
                url
            ]
            
            self.logger.info("执行下载命令...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=download_timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"下载失败: {result.stderr}")
                return None
            
            # 查找下载的文件
            downloaded_files = self._find_downloaded_files(output_dir)
            if not downloaded_files:
                self.logger.error("未找到下载的视频文件")
                return None
            
            video_file = downloaded_files[0]
            self.logger.success(f"视频下载完成: {os.path.basename(video_file)}")
            
            return video_file
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"下载超时（{download_timeout}秒）")
            return None
        except Exception as e:
            self.logger.error(f"下载异常: {str(e)}")
            return None
    
    def _progress_hook(self, d: Dict):
        """
        yt-dlp 进度回调函数
        
        Args:
            d: yt-dlp 提供的进度字典，包含以下关键字段：
                - status: 'downloading' | 'finished' | 'error'
                - downloaded_bytes: 已下载字节数
                - total_bytes: 总字节数（可能为 None）
                - total_bytes_estimate: 估计总字节数
                - speed: 下载速度（字节/秒）
                - eta: 预计剩余时间（秒）
                - elapsed: 已用时间（秒）
        """
        try:
            # 更新最后进度时间
            self.last_progress_time = time.time()
            
            status = d.get('status')
            
            if status == 'downloading':
                # 提取进度数据
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                # 计算百分比
                if total_bytes > 0:
                    percent = (downloaded_bytes / total_bytes) * 100
                else:
                    percent = 0
                
                # 格式化数据
                downloaded_mb = downloaded_bytes / 1024 / 1024
                total_mb = total_bytes / 1024 / 1024 if total_bytes > 0 else 0
                speed_mb = speed / 1024 / 1024 if speed else 0
                
                # 格式化 ETA
                if eta:
                    eta_minutes = int(eta // 60)
                    eta_seconds = int(eta % 60)
                    eta_str = f"{eta_minutes}m {eta_seconds}s" if eta_minutes > 0 else f"{eta_seconds}s"
                else:
                    eta_str = "--"
                
                # 构建进度数据
                progress_data = {
                    'percent': round(percent, 1),
                    'speed': f"{speed_mb:.2f} MB/s" if speed_mb > 0 else "-- MB/s",
                    'downloaded': f"{downloaded_mb:.1f} MB",
                    'total': f"{total_mb:.1f} MB" if total_mb > 0 else "-- MB",
                    'eta': eta_str
                }
                
                # 检查是否需要超时警告
                elapsed_time = time.time() - self.download_start_time
                download_timeout = self.config.get_int('step1_download', 'download_timeout', 1200)
                
                if elapsed_time > download_timeout * 0.75:  # 超过 75% 时间
                    remaining_time = download_timeout - elapsed_time
                    progress_data['timeout_warning'] = f"已下载 {int(elapsed_time/60)} 分钟，还剩 {int(remaining_time/60)} 分钟超时"
                
                # 调用进度回调
                if self.progress_callback:
                    try:
                        self.progress_callback(progress_data)
                        self.logger.info(f"[进度] 进度回调已发送: {percent:.1f}%")
                    except Exception as e:
                        self.logger.error(f"[错误] 进度回调失败: {str(e)}")
                else:
                    self.logger.warning("[警告] 进度回调未设置")
                
                # 记录日志（降低频率）
                progress_interval = self.config.get_int('step1_download', 'progress_update_interval', 2)
                if not hasattr(self, '_last_log_time') or time.time() - self._last_log_time >= progress_interval:
                    self.logger.info(f"[下载] 下载进度: {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB) @ {speed_mb:.2f} MB/s")
                    self._last_log_time = time.time()
                    
            elif status == 'finished':
                self.logger.success("视频下载完成，正在处理...")
                if self.progress_callback:
                    self.progress_callback({
                        'percent': 100.0,
                        'speed': '完成',
                        'downloaded': '完成',
                        'total': '完成',
                        'eta': '0s'
                    })
            elif status == 'error':
                self.logger.error(f"下载过程中出现错误")
                
        except Exception as e:
            self.logger.error(f"进度回调异常: {str(e)}")
    
    def _monitor_timeout(self, timeout_seconds: int):
        """
        监控下载超时
        
        Args:
            timeout_seconds: 超时时间（秒）
        """
        progress_timeout = self.config.get_int('step1_download', 'progress_timeout', 300)
        
        while not self.download_completed and not self.download_error:
            time.sleep(5)  # 每5秒检查一次
            
            current_time = time.time()
            
            # 检查总超时
            if current_time - self.download_start_time > timeout_seconds:
                self.download_error = f"下载总超时：{timeout_seconds}秒内未完成"
                self.logger.error(self.download_error)
                break
            
            # 检查无进度超时
            if current_time - self.last_progress_time > progress_timeout:
                self.download_error = f"下载无进度超时：{progress_timeout}秒无进度更新"
                self.logger.error(self.download_error)
                break
    
    def _check_timeout(self) -> bool:
        """
        检查是否超时
        
        Returns:
            bool: True 表示已超时，False 表示未超时
        """
        if not self.download_start_time or not self.last_progress_time:
            return False
        
        current_time = time.time()
        download_timeout = self.config.get_int('step1_download', 'download_timeout', 1200)
        progress_timeout = self.config.get_int('step1_download', 'progress_timeout', 300)
        
        # 检查总超时
        if current_time - self.download_start_time > download_timeout:
            return True
        
        # 检查无进度超时
        if current_time - self.last_progress_time > progress_timeout:
            return True
        
        return False
    
    def _find_downloaded_files(self, output_dir: str) -> list:
        """查找下载的文件"""
        video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv']
        downloaded_files = []
        
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in video_extensions:
                    downloaded_files.append(file_path)
        
        # 按文件大小排序，取最大的文件
        downloaded_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
        return downloaded_files

def main(url: str, output_dir: str) -> bool:
    """步骤1主函数"""
    try:
        config = Config()
        logger = Logger("step1_download")
        downloader = YouTubeDownloader(config, logger)
        
        logger.step_start(1, "YouTube视频下载")
        
        result = downloader.download_video(url, output_dir)
        
        if result['success']:
            logger.step_complete(1, "YouTube视频下载")
            logger.info("=" * 50)
            logger.info("步骤1完成，输出文件：")
            logger.info(f"- 视频文件: {result['video_file']}")
            logger.info(f"- 信息文件: {result['info_file']}")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤1失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step1_download")
        logger.error(f"步骤1执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python step1_download.py <YouTube_URL> <输出目录>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)