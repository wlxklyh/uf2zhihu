"""
视频URL平台识别器
用于识别视频来自哪个平台（YouTube、Bilibili等）
"""
from urllib.parse import urlparse
import re
from typing import Optional


class URLIdentifier:
    """视频URL平台识别器"""
    
    @staticmethod
    def identify_platform(url: str) -> str:
        """
        识别视频平台
        
        Args:
            url: 视频URL
            
        Returns:
            str: 'youtube' | 'bilibili' | 'unknown'
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # YouTube
            if 'youtube.com' in domain or 'youtu.be' in domain:
                return 'youtube'
            
            # Bilibili
            if 'bilibili.com' in domain or 'b23.tv' in domain:
                return 'bilibili'
            
            return 'unknown'
        except Exception:
            return 'unknown'
    
    @staticmethod
    def extract_bilibili_bvid(url: str) -> Optional[str]:
        """
        提取B站BVID
        
        Args:
            url: B站视频URL
            
        Returns:
            str: BVID (如: BV1C62PBeEha) 或 None
            
        Examples:
            >>> URLIdentifier.extract_bilibili_bvid("https://www.bilibili.com/video/BV1C62PBeEha/")
            'BV1C62PBeEha'
        """
        try:
            # 匹配 /video/BV... 格式
            match = re.search(r'/video/(BV[a-zA-Z0-9]+)', url)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    @staticmethod
    def extract_youtube_video_id(url: str) -> Optional[str]:
        """
        提取YouTube视频ID
        
        Args:
            url: YouTube视频URL
            
        Returns:
            str: 视频ID 或 None
            
        Examples:
            >>> URLIdentifier.extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            'dQw4w9WgXcQ'
        """
        try:
            # youtube.com 格式
            match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
            if match:
                return match.group(1)
            
            # youtu.be 格式
            match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
            if match:
                return match.group(1)
            
            return None
        except Exception:
            return None

