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
        
        # 多语言字幕缓存目录映射
        self.subtitle_cache_dirs = {
            'en': os.path.join(self.cache_dir, 'subtitles_en'),
            'zh': os.path.join(self.cache_dir, 'subtitles_zh'),
            'ja': os.path.join(self.cache_dir, 'subtitles_ja'),
            'ko': os.path.join(self.cache_dir, 'subtitles_ko'),
            'fr': os.path.join(self.cache_dir, 'subtitles_fr'),
            'de': os.path.join(self.cache_dir, 'subtitles_de'),
            'es': os.path.join(self.cache_dir, 'subtitles_es')
        }
        
        # 确保缓存目录存在
        self._ensure_cache_directories()
    
    def _ensure_cache_directories(self):
        """确保缓存目录存在"""
        # 基础缓存目录
        base_dirs = [self.cache_dir, self.videos_cache]
        for cache_dir in base_dirs:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                self.logger.info(f"创建缓存目录: {cache_dir}")
    
    def _get_subtitle_cache_dir(self, language: str) -> str:
        """
        获取指定语言的字幕缓存目录
        
        Args:
            language: 语言代码 ('zh', 'en' 等)
            
        Returns:
            str: 字幕缓存目录路径
        """
        cache_dir = self.subtitle_cache_dirs.get(language)
        if not cache_dir:
            # 未知语言，使用通用目录
            cache_dir = os.path.join(self.cache_dir, f'subtitles_{language}')
            self.subtitle_cache_dirs[language] = cache_dir
        
        # 确保目录存在
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            self.logger.info(f"创建字幕缓存目录: {cache_dir}")
        
        return cache_dir
    
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
    
    def _get_cache_info_path(self, cache_type: str, cache_key: str, language: str = None) -> str:
        """
        获取缓存信息文件路径
        
        Args:
            cache_type: 缓存类型 ('video', 'subtitle_en', 'subtitle' 等)
            cache_key: 缓存键
            language: 语言代码（用于 subtitle 类型）
        """
        if cache_type == 'video':
            cache_base_dir = self.videos_cache
        elif cache_type == 'subtitle_en':
            cache_base_dir = self.subtitles_en_cache
        elif cache_type == 'subtitle' and language:
            cache_base_dir = self._get_subtitle_cache_dir(language)
        else:
            cache_base_dir = self.cache_dir
        
        return os.path.join(cache_base_dir, f"{cache_key}_info.json")
    
    def _save_cache_info(self, cache_type: str, cache_key: str, info: Dict, language: str = None):
        """
        保存缓存信息
        
        Args:
            cache_type: 缓存类型
            cache_key: 缓存键
            info: 缓存信息
            language: 语言代码（用于 subtitle 类型）
        """
        info_path = self._get_cache_info_path(cache_type, cache_key, language)
        info['cached_time'] = datetime.now().isoformat()
        info['cache_type'] = cache_type
        info['cache_key'] = cache_key
        if language:
            info['language'] = language
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    
    def _load_cache_info(self, cache_type: str, cache_key: str, language: str = None) -> Optional[Dict]:
        """
        加载缓存信息
        
        Args:
            cache_type: 缓存类型
            cache_key: 缓存键
            language: 语言代码（用于 subtitle 类型）
        """
        info_path = self._get_cache_info_path(cache_type, cache_key, language)
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
    
    # 英文字幕缓存相关方法（保留向后兼容）
    def get_cached_english_subtitles(self, youtube_url: str) -> Optional[Tuple[str, Dict]]:
        """获取缓存的英文字幕（向后兼容方法）"""
        return self.get_cached_subtitles(youtube_url, 'en')
    
    def cache_english_subtitles(self, youtube_url: str, srt_path: str, transcribe_info: Dict) -> str:
        """缓存英文字幕（向后兼容方法）"""
        return self.cache_subtitles(youtube_url, srt_path, transcribe_info, 'en')
    
    # 通用字幕缓存方法（支持多语言）
    def get_cached_subtitles(self, youtube_url: str, language: str) -> Optional[Tuple[str, Dict]]:
        """
        获取缓存的字幕（支持多语言）
        
        Args:
            youtube_url: 视频URL
            language: 语言代码 ('zh', 'en', 'ja' 等)
            
        Returns:
            Optional[Tuple[str, Dict]]: (字幕文件路径, 缓存信息) 或 None
        """
        cache_key = self._get_url_hash(youtube_url)
        cache_info = self._load_cache_info('subtitle', cache_key, language)
        
        if not cache_info:
            return None
        
        # 优先查找cache_path，然后查找file_path（向后兼容）
        srt_path = cache_info.get('cache_path') or cache_info.get('file_path')
        if not srt_path or not os.path.exists(srt_path):
            self.logger.info(f"缓存的{language}字幕不存在: {srt_path}")
            return None
        
        self.logger.success(f"找到缓存的{language}字幕: {os.path.basename(srt_path)}")
        return srt_path, cache_info
    
    def cache_subtitles(self, youtube_url: str, srt_path: str, transcribe_info: Dict, language: str) -> str:
        """
        缓存字幕（支持多语言）
        
        Args:
            youtube_url: 视频URL
            srt_path: 字幕文件路径
            transcribe_info: 转录信息
            language: 语言代码 ('zh', 'en', 'ja' 等)
            
        Returns:
            str: 缓存文件路径
        """
        cache_key = self._get_url_hash(youtube_url)
        cache_dir = self._get_subtitle_cache_dir(language)
        
        # 生成缓存文件名
        language_map = {'zh': 'chinese', 'en': 'english', 'ja': 'japanese', 'ko': 'korean'}
        lang_name = language_map.get(language, language)
        cache_filename = f"{cache_key}_{lang_name}.srt"
        cache_path = os.path.join(cache_dir, cache_filename)
        
        try:
            # 复制文件到缓存目录
            shutil.copy2(srt_path, cache_path)
            self.logger.success(f"{language}字幕已缓存: {cache_filename}")
            
            # 保存缓存信息
            cache_info = transcribe_info.copy()
            cache_info.update({
                'original_path': srt_path,
                'cache_path': cache_path,
                'cache_filename': cache_filename,
                'youtube_url': youtube_url,
                'language': language
            })
            
            self._save_cache_info('subtitle', cache_key, cache_info, language)
            
            return cache_path
            
        except Exception as e:
            self.logger.error(f"{language}字幕缓存失败: {str(e)}")
            return srt_path
    
    # 缓存管理方法
    def clear_cache(self, cache_type: str = None):
        """清理缓存"""
        if cache_type is None:
            # 清理所有缓存
            cache_dirs = [self.videos_cache] + list(self.subtitle_cache_dirs.values())
            cache_names = ['视频'] + [f'{lang}字幕' for lang in self.subtitle_cache_dirs.keys()]
        elif cache_type == 'video':
            cache_dirs = [self.videos_cache]
            cache_names = ['视频']
        elif cache_type == 'subtitle_en':
            cache_dirs = [self.subtitles_en_cache]
            cache_names = ['英文字幕']
        else:
            cache_dirs = []
            cache_names = []
        
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
        
        # 添加多语言字幕统计
        for lang, cache_dir in self.subtitle_cache_dirs.items():
            stats[f'subtitles_{lang}'] = {'count': 0, 'size': 0}
        
        # 统计视频缓存
        if os.path.exists(self.videos_cache):
            for file in os.listdir(self.videos_cache):
                file_path = os.path.join(self.videos_cache, file)
                if os.path.isfile(file_path):
                    stats['videos']['count'] += 1
                    stats['videos']['size'] += os.path.getsize(file_path)
        
        # 统计字幕缓存
        for lang, cache_dir in self.subtitle_cache_dirs.items():
            if os.path.exists(cache_dir):
                for file in os.listdir(cache_dir):
                    file_path = os.path.join(cache_dir, file)
                    if os.path.isfile(file_path):
                        stats[f'subtitles_{lang}']['count'] += 1
                        stats[f'subtitles_{lang}']['size'] += os.path.getsize(file_path)
        
        return stats
    
    def list_cached_items(self, cache_type: str) -> List[Dict]:
        """列出指定类型的缓存项"""
        if cache_type == 'video':
            cache_dir = self.videos_cache
        elif cache_type == 'subtitle_en':
            cache_dir = self.subtitles_en_cache
        elif cache_type.startswith('subtitle_'):
            # 提取语言代码
            lang = cache_type.replace('subtitle_', '')
            cache_dir = self.subtitle_cache_dirs.get(lang)
        else:
            cache_dir = None
        
        if not cache_dir or not os.path.exists(cache_dir):
            return []
        
        items = []
        for file in os.listdir(cache_dir):
            if file.endswith('_info.json'):
                cache_key = file.replace('_info.json', '')
                # 对于多语言字幕，需要传入语言参数
                if cache_type.startswith('subtitle_') and cache_type != 'subtitle_en':
                    lang = cache_type.replace('subtitle_', '')
                    cache_info = self._load_cache_info('subtitle', cache_key, lang)
                else:
                    cache_info = self._load_cache_info(cache_type, cache_key)
                if cache_info:
                    items.append(cache_info)
        
        # 按缓存时间排序
        items.sort(key=lambda x: x.get('cached_time', ''), reverse=True)
        return items
