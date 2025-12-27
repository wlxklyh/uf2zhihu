"""
步骤1：YouTube视频下载模块
参考成功的实现，使用subprocess调用yt-dlp命令行
"""
import subprocess
import os
import json
import shutil
from datetime import datetime
from typing import Dict, Optional
import sys
import traceback
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.file_manager import FileManager
from src.utils.cache_manager import CacheManager

class YouTubeDownloader:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.output_dir = None
        self.cache_manager = CacheManager(config, logger)
        self.enable_cache = config.get_boolean('basic', 'enable_cache', True)
        
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
        self.logger.info(f"开始下载YouTube视频: {url}")
        
        try:
            # 检查缓存
            if self.enable_cache:
                cached_result = self.cache_manager.get_cached_video(url)
                if cached_result:
                    cached_video_path, cached_info = cached_result
                    
                    # 复制缓存文件到输出目录
                    output_filename = os.path.basename(cached_video_path)
                    output_video_path = os.path.join(output_dir, output_filename)
                    
                    if not os.path.exists(output_video_path):
                        shutil.copy2(cached_video_path, output_video_path)
                        self.logger.info(f"从缓存复制视频: {output_filename}")
                    
                    # 更新文件路径
                    cached_info['file_path'] = output_video_path
                    cached_info['file_size'] = os.path.getsize(output_video_path)
                    
                    # 保存视频信息到JSON文件
                    info_file = os.path.join(output_dir, 'video_info.json')
                    with open(info_file, 'w', encoding='utf-8') as f:
                        json.dump(cached_info, f, ensure_ascii=False, indent=2)
                    
                    self.logger.file_created(info_file)
                    
                    return {
                        'success': True,
                        'video_info': cached_info,
                        'video_file': output_video_path,
                        'info_file': info_file,
                        'message': f'使用缓存视频: {cached_info["title"]}',
                        'from_cache': True
                    }
            # 检查依赖
            yt_dlp_available, yt_dlp_command = self.check_dependencies()
            if not yt_dlp_available:
                raise Exception("yt-dlp不可用，请先安装: pip install yt-dlp")
            
            # 设置输出目录
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
            
            # 先获取视频信息
            video_info = self._get_video_info(url, yt_dlp_command)
            if not video_info:
                raise Exception("无法获取视频信息")
            
            self.logger.info(f"视频标题: {video_info['title']}")
            self.logger.info(f"视频时长: {video_info['duration']} 秒")
            self.logger.info(f"上传者: {video_info['uploader']}")
            
            # 下载视频
            video_file = self._download_video_file(url, output_dir, yt_dlp_command)
            if not video_file:
                raise Exception("视频下载失败")
            
            # 验证下载的视频文件
            is_valid, validation_message = Validator.validate_video_file(video_file)
            if not is_valid:
                raise Exception(f"视频文件验证失败: {validation_message}")
            
            self.logger.success("视频文件验证通过")
            
            # 更新视频信息
            video_info['file_path'] = video_file
            video_info['file_size'] = os.path.getsize(video_file)
            
            self.logger.info(f"文件大小: {video_info['file_size'] / 1024 / 1024:.1f} MB")
            
            # 保存视频信息到JSON文件
            info_file = os.path.join(output_dir, 'video_info.json')
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)
            
                self.logger.file_created(info_file)
                
                # 缓存下载的视频
                if self.enable_cache:
                    self.cache_manager.cache_video(url, video_file, video_info)
                
                return {
                    'success': True,
                    'video_info': video_info,
                    'video_file': video_file,
                    'info_file': info_file,
                    'message': f'视频下载成功: {video_info["title"]}',
                    'from_cache': False
                }
            
        except Exception as e:
            error_msg = f"视频下载失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
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
        """下载视频文件"""
        try:
            self.logger.info("开始下载视频文件...")
            
            # 获取配置
            quality = self.config.get('step1_download', 'quality', 'best')
            format_pref = self.config.get('step1_download', 'format', 'mp4')
            
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
                timeout=600  # 10分钟超时
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
            self.logger.error("下载超时")
            return None
        except Exception as e:
            self.logger.error(f"下载异常: {str(e)}")
            return None
    
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