"""
步骤1：Bilibili视频下载模块
使用Bilibili API下载视频
"""
import os
import json
import time
import shutil
import subprocess
import requests
from datetime import datetime
from typing import Dict, Optional, Callable
import sys
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.cache_manager import CacheManager
from src.utils.url_identifier import URLIdentifier
from src.core.steps.base_downloader import BaseVideoDownloader


class BilibiliDownloader(BaseVideoDownloader):
    """B站视频下载器"""
    
    def __init__(self, config: Config, logger: Logger, progress_callback: Optional[Callable] = None):
        super().__init__(config, logger, progress_callback)
        self.cache_manager = CacheManager(config, logger)
        self.enable_cache = config.get_boolean('basic', 'enable_cache', True)
        self.download_start_time = None
        
        # 创建session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        })
    
    def check_dependencies(self) -> tuple:
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, ['ffmpeg']
            return False, None
        except Exception:
            return False, None
    
    def download_video(self, url: str, output_dir: str) -> Dict:
        """
        下载Bilibili视频
        
        Args:
            url: Bilibili视频URL
            output_dir: 输出目录
            
        Returns:
            Dict: 包含视频信息和文件路径的字典
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤1开始] Bilibili视频下载")
        self.logger.info(f"视频URL: {url}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info("=" * 60)
        
        download_start_time = time.time()
        self.download_start_time = download_start_time
        
        try:
            # 提取BVID
            bvid = URLIdentifier.extract_bilibili_bvid(url)
            if not bvid:
                raise Exception(f"无法从URL提取BVID: {url}")
            
            self.logger.info(f"[提取] BVID: {bvid}")
            
            # 检查缓存
            self.logger.info("[检查] 检查视频缓存...")
            if self.enable_cache:
                self.logger.info("[成功] 缓存功能已启用")
                cached_result = self.cache_manager.get_cached_video(url)
                if cached_result:
                    self.logger.info("[成功] 找到缓存的视频！")
                    cached_video_path, cached_info = cached_result
                    
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
                    
                    # 保存视频信息
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
            
            # 检查依赖
            self.logger.info("[检查] 检查ffmpeg依赖...")
            ffmpeg_available, _ = self.check_dependencies()
            if not ffmpeg_available:
                self.logger.error("[错误] ffmpeg不可用")
                raise Exception("ffmpeg不可用，请先安装ffmpeg")
            
            self.logger.success(f"[成功] ffmpeg可用")
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            self.logger.info(f"[目录] 输出目录已创建: {output_dir}")
            
            # 获取视频信息
            self.logger.info("[获取] 正在获取视频信息...")
            video_info = self._get_video_info(bvid)
            if not video_info:
                raise Exception("无法获取视频信息")
            
            self.logger.info("[视频] 视频信息:")
            self.logger.info(f"  - 标题: {video_info['title']}")
            self.logger.info(f"  - 时长: {video_info['duration']} 秒 ({video_info['duration']//60}分{video_info['duration']%60}秒)")
            self.logger.info(f"  - UP主: {video_info['uploader']}")
            self.logger.info(f"  - CID: {video_info.get('cid', '未知')}")
            
            # 获取播放地址
            self.logger.info("[获取] 正在获取播放地址...")
            play_url_info = self._get_play_url(bvid, video_info['cid'])
            if not play_url_info:
                raise Exception("无法获取播放地址")
            
            video_url = play_url_info['video_url']
            audio_url = play_url_info['audio_url']
            
            self.logger.info(f"[地址] 视频流URL: {video_url[:80]}...")
            self.logger.info(f"[地址] 音频流URL: {audio_url[:80]}...")
            
            # 下载视频流
            self.logger.info("[下载] 开始下载视频流...")
            video_temp_path = os.path.join(output_dir, f"{bvid}_video.m4s")
            self._download_stream(video_url, video_temp_path, "video")
            self.logger.success(f"[成功] 视频流下载完成")
            
            # 下载音频流
            self.logger.info("[下载] 开始下载音频流...")
            audio_temp_path = os.path.join(output_dir, f"{bvid}_audio.m4s")
            self._download_stream(audio_url, audio_temp_path, "audio")
            self.logger.success(f"[成功] 音频流下载完成")
            
            # 合并视频和音频
            self.logger.info("[合并] 正在合并视频和音频...")
            output_video_path = os.path.join(output_dir, f"{bvid}.mp4")
            self._merge_video_audio(video_temp_path, audio_temp_path, output_video_path)
            self.logger.success(f"[成功] 视频合并完成")
            
            # 删除临时文件
            try:
                os.remove(video_temp_path)
                os.remove(audio_temp_path)
                self.logger.info("[清理] 临时文件已删除")
            except Exception as e:
                self.logger.warning(f"[警告] 删除临时文件失败: {str(e)}")
            
            # 验证视频文件
            self.logger.info("[验证] 正在验证视频文件...")
            is_valid, validation_message = Validator.validate_video_file(output_video_path)
            if not is_valid:
                self.logger.error(f"[错误] 视频文件验证失败: {validation_message}")
                raise Exception(f"视频文件验证失败: {validation_message}")
            
            self.logger.success(f"[成功] 视频文件验证通过: {validation_message}")
            
            # 更新视频信息
            video_info['file_path'] = output_video_path
            video_info['file_size'] = os.path.getsize(output_video_path)
            
            file_size_mb = video_info['file_size'] / 1024 / 1024
            self.logger.info(f"[信息] 文件大小: {file_size_mb:.2f} MB")
            
            # 保存视频信息
            self.logger.info("[保存] 保存视频信息...")
            info_file = os.path.join(output_dir, 'video_info.json')
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)
            
            self.logger.file_created(info_file)
            
            # 缓存下载的视频
            if self.enable_cache:
                self.logger.info("[缓存] 正在缓存视频...")
                try:
                    self.cache_manager.cache_video(url, output_video_path, video_info)
                    self.logger.success("[成功] 视频已缓存")
                except Exception as cache_error:
                    self.logger.warning(f"[警告] 视频缓存失败: {str(cache_error)}")
            
            elapsed_time = time.time() - download_start_time
            self.logger.info("=" * 60)
            self.logger.success(f"[步骤1完成] Bilibili视频下载成功 (耗时: {elapsed_time:.2f}秒)")
            self.logger.info(f"[文件] 视频文件: {output_video_path}")
            self.logger.info(f"[文件] 信息文件: {info_file}")
            self.logger.info("=" * 60)
            
            return {
                'success': True,
                'video_info': video_info,
                'video_file': output_video_path,
                'info_file': info_file,
                'message': f'Bilibili视频下载成功: {video_info["title"]}',
                'from_cache': False
            }
            
        except Exception as e:
            elapsed_time = time.time() - download_start_time
            error_msg = f"Bilibili视频下载失败: {str(e)}"
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
    
    def _get_video_info(self, bvid: str) -> Optional[Dict]:
        """获取视频信息"""
        try:
            url = "https://api.bilibili.com/x/web-interface/view"
            params = {"bvid": bvid}
            
            response = self.session.get(url, params=params, timeout=30)
            data = response.json()
            
            if data['code'] != 0:
                self.logger.error(f"API返回错误: {data}")
                return None
            
            info = data['data']
            
            video_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('owner', {}).get('name', 'Unknown'),
                'upload_date': info.get('pubdate', 0),
                'view_count': info.get('stat', {}).get('view', 0),
                'description': info.get('desc', '')[:500],
                'url': f"https://www.bilibili.com/video/{bvid}",
                'bvid': bvid,
                'aid': info.get('aid', 0),
                'cid': info.get('cid', 0),
                'pic': info.get('pic', '')
            }
            
            return video_info
            
        except Exception as e:
            self.logger.error(f"获取视频信息异常: {str(e)}")
            return None
    
    def _get_play_url(self, bvid: str, cid: int) -> Optional[Dict]:
        """获取播放地址（DASH格式）"""
        try:
            url = "https://api.bilibili.com/x/player/wbi/playurl"
            params = {
                'bvid': bvid,
                'cid': cid,
                'qn': 127,  # 最高质量
                'fnval': 4048  # DASH格式
            }
            
            response = self.session.get(url, params=params, timeout=30)
            data = response.json()
            
            if data['code'] != 0:
                self.logger.error(f"获取播放地址失败: {data}")
                return None
            
            dash = data['data']['dash']
            
            # 获取视频流（选择第一个，通常是最高质量）
            video_list = dash.get('video', [])
            if not video_list:
                self.logger.error("没有找到视频流")
                return None
            
            video_url = video_list[0]['base_url']
            
            # 获取音频流（优先无损，否则选择第一个）
            audio_list = dash.get('audio', [])
            if not audio_list:
                self.logger.error("没有找到音频流")
                return None
            
            audio_url = audio_list[0]['base_url']
            
            return {
                'video_url': video_url,
                'audio_url': audio_url,
                'quality': video_list[0].get('id', 0),
                'codec': video_list[0].get('codecs', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"获取播放地址异常: {str(e)}")
            return None
    
    def _download_stream(self, url: str, output_path: str, stream_type: str):
        """
        下载视频或音频流
        
        Args:
            url: 流URL
            output_path: 输出路径
            stream_type: 流类型 ('video' or 'audio')
        """
        try:
            # 发送进度更新
            if self.progress_callback:
                self.progress_callback({
                    'percent': 0,
                    'speed': '准备中',
                    'downloaded': '0 MB',
                    'total': '-- MB',
                    'eta': '--'
                })
            
            # 分片下载
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 计算进度
                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            elapsed_time = time.time() - start_time
                            
                            if elapsed_time > 0:
                                speed_mb = (downloaded_size / 1024 / 1024) / elapsed_time
                                remaining_size = total_size - downloaded_size
                                eta_seconds = remaining_size / (speed_mb * 1024 * 1024) if speed_mb > 0 else 0
                                
                                # 发送进度更新
                                if self.progress_callback:
                                    self.progress_callback({
                                        'percent': round(percent, 1),
                                        'speed': f"{speed_mb:.2f} MB/s",
                                        'downloaded': f"{downloaded_size / 1024 / 1024:.1f} MB",
                                        'total': f"{total_size / 1024 / 1024:.1f} MB",
                                        'eta': f"{int(eta_seconds)}s",
                                        'stream_type': stream_type
                                    })
            
            self.logger.info(f"[下载] {stream_type}流下载完成: {os.path.basename(output_path)}")
            
        except Exception as e:
            self.logger.error(f"下载{stream_type}流失败: {str(e)}")
            raise
    
    def _merge_video_audio(self, video_path: str, audio_path: str, output_path: str):
        """
        使用ffmpeg合并视频和音频
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c', 'copy',  # 直接复制流，不重新编码
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            
            if result.returncode != 0:
                self.logger.error(f"ffmpeg合并失败: {result.stderr}")
                raise Exception(f"ffmpeg合并失败: {result.stderr}")
            
            self.logger.info(f"[合并] 视频合并成功: {os.path.basename(output_path)}")
            
        except subprocess.TimeoutExpired:
            self.logger.error("ffmpeg合并超时")
            raise Exception("ffmpeg合并超时")
        except Exception as e:
            self.logger.error(f"合并视频音频异常: {str(e)}")
            raise

