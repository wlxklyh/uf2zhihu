"""
缓存管理模块
管理视频、字幕等文件的缓存
"""
import os
import json
import hashlib
import shutil
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from .config import Config
from .logger import Logger

class CacheManager:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.cache_dir = config.get('basic', 'cache_dir', './cache')
        self.videos_cache = os.path.join(self.cache_dir, 'videos')
        self.subtitles_en_cache = os.path.join(self.cache_dir, 'subtitles_en')
        
        # 确保缓存目录存在
        self._ensure_cache_directories()
    
    def _ensure_cache_directories(self):
        """确保缓存目录存在"""
        for cache_dir in [self.cache_dir, self.videos_cache, 
                         self.subtitles_en_cache]:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                self.logger.info(f"创建缓存目录: {cache_dir}")
    
    def _get_url_hash(self, url: str) -> str:
        """生成URL的哈希值作为缓存键"""
        # 清理URL，移除播放列表参数，只保留视频ID
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
        else:
            # 如果无法提取视频ID，使用完整URL的哈希
            video_id = hashlib.md5(url.encode()).hexdigest()
        
        return video_id
    
    def _get_cache_info_path(self, cache_type: str, cache_key: str) -> str:
        """获取缓存信息文件路径"""
        cache_base_dir = {
            'video': self.videos_cache,
            'subtitle_en': self.subtitles_en_cache
        }.get(cache_type, self.cache_dir)
        
        return os.path.join(cache_base_dir, f"{cache_key}_info.json")
    
    def _save_cache_info(self, cache_type: str, cache_key: str, info: Dict):
        """保存缓存信息"""
        info_path = self._get_cache_info_path(cache_type, cache_key)
        info['cached_time'] = datetime.now().isoformat()
        info['cache_type'] = cache_type
        info['cache_key'] = cache_key
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    
    def _load_cache_info(self, cache_type: str, cache_key: str) -> Optional[Dict]:
        """加载缓存信息"""
        info_path = self._get_cache_info_path(cache_type, cache_key)
        if not os.path.exists(info_path):
            return None
        
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"读取缓存信息失败: {str(e)}")
            return None
    
    # 视频缓存相关方法
    def get_cached_video(self, youtube_url: str) -> Optional[Tuple[str, Dict]]:
        """获取缓存的视频文件"""
        cache_key = self._get_url_hash(youtube_url)
        cache_info = self._load_cache_info('video', cache_key)
        
        if not cache_info:
            return None
        
        # 优先查找cache_path，然后查找file_path（向后兼容）
        video_path = cache_info.get('cache_path') or cache_info.get('file_path')
        if not video_path or not os.path.exists(video_path):
            self.logger.info(f"缓存的视频文件不存在: {video_path}")
            return None
        
        self.logger.success(f"找到缓存视频: {os.path.basename(video_path)}")
        return video_path, cache_info
    
    def cache_video(self, youtube_url: str, video_path: str, video_info: Dict) -> str:
        """缓存视频文件"""
        cache_key = self._get_url_hash(youtube_url)
        
        # 生成缓存文件名
        original_filename = os.path.basename(video_path)
        cache_filename = f"{cache_key}_{original_filename}"
        cache_path = os.path.join(self.videos_cache, cache_filename)
        
        try:
            # 复制文件到缓存目录
            shutil.copy2(video_path, cache_path)
            self.logger.success(f"视频已缓存: {cache_filename}")
            
            # 保存缓存信息
            cache_info = video_info.copy()
            cache_info.update({
                'original_path': video_path,
                'cache_path': cache_path,
                'cache_filename': cache_filename,
                'youtube_url': youtube_url
            })
            
            self._save_cache_info('video', cache_key, cache_info)
            
            return cache_path
            
        except Exception as e:
            self.logger.error(f"视频缓存失败: {str(e)}")
            return video_path
    
    # 英文字幕缓存相关方法
    def get_cached_english_subtitles(self, youtube_url: str) -> Optional[Tuple[str, Dict]]:
        """获取缓存的英文字幕"""
        cache_key = self._get_url_hash(youtube_url)
        cache_info = self._load_cache_info('subtitle_en', cache_key)
        
        if not cache_info:
            return None
        
        # 优先查找cache_path，然后查找file_path（向后兼容）
        srt_path = cache_info.get('cache_path') or cache_info.get('file_path')
        if not srt_path or not os.path.exists(srt_path):
            self.logger.info(f"缓存的英文字幕不存在: {srt_path}")
            return None
        
        self.logger.success(f"找到缓存英文字幕: {os.path.basename(srt_path)}")
        return srt_path, cache_info
    
    def cache_english_subtitles(self, youtube_url: str, srt_path: str, transcribe_info: Dict) -> str:
        """缓存英文字幕"""
        cache_key = self._get_url_hash(youtube_url)
        
        # 生成缓存文件名
        cache_filename = f"{cache_key}_english.srt"
        cache_path = os.path.join(self.subtitles_en_cache, cache_filename)
        
        try:
            # 复制文件到缓存目录
            shutil.copy2(srt_path, cache_path)
            self.logger.success(f"英文字幕已缓存: {cache_filename}")
            
            # 保存缓存信息
            cache_info = transcribe_info.copy()
            cache_info.update({
                'original_path': srt_path,
                'cache_path': cache_path,
                'cache_filename': cache_filename,
                'youtube_url': youtube_url
            })
            
            self._save_cache_info('subtitle_en', cache_key, cache_info)
            
            return cache_path
            
        except Exception as e:
            self.logger.error(f"英文字幕缓存失败: {str(e)}")
            return srt_path
    
    # 缓存管理方法
    def clear_cache(self, cache_type: str = None):
        """清理缓存"""
        if cache_type is None:
            # 清理所有缓存
            cache_dirs = [self.videos_cache, self.subtitles_en_cache]
            cache_names = ['视频', '英文字幕']
        else:
            cache_dirs = {
                'video': [self.videos_cache],
                'subtitle_en': [self.subtitles_en_cache]
            }.get(cache_type, [])
            cache_names = [cache_type]
        
        for cache_dir, cache_name in zip(cache_dirs, cache_names):
            try:
                if os.path.exists(cache_dir):
                    for file in os.listdir(cache_dir):
                        file_path = os.path.join(cache_dir, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    self.logger.info(f"已清理{cache_name}缓存")
            except Exception as e:
                self.logger.error(f"清理{cache_name}缓存失败: {str(e)}")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        stats = {
            'videos': {'count': 0, 'size': 0},
            'subtitles_en': {'count': 0, 'size': 0}
        }
        
        cache_dirs = {
            'videos': self.videos_cache,
            'subtitles_en': self.subtitles_en_cache
        }
        
        for cache_type, cache_dir in cache_dirs.items():
            if os.path.exists(cache_dir):
                for file in os.listdir(cache_dir):
                    file_path = os.path.join(cache_dir, file)
                    if os.path.isfile(file_path):
                        stats[cache_type]['count'] += 1
                        stats[cache_type]['size'] += os.path.getsize(file_path)
        
        return stats
    
    def list_cached_items(self, cache_type: str) -> List[Dict]:
        """列出指定类型的缓存项"""
        cache_dir = {
            'video': self.videos_cache,
            'subtitle_en': self.subtitles_en_cache
        }.get(cache_type)
        
        if not cache_dir or not os.path.exists(cache_dir):
            return []
        
        items = []
        for file in os.listdir(cache_dir):
            if file.endswith('_info.json'):
                cache_key = file.replace('_info.json', '')
                cache_info = self._load_cache_info(cache_type, cache_key)
                if cache_info:
                    items.append(cache_info)
        
        # 按缓存时间排序
        items.sort(key=lambda x: x.get('cached_time', ''), reverse=True)
        return items
