"""
视频下载器工厂类
根据URL自动选择对应平台的下载器
"""
from typing import Optional, Callable
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.url_identifier import URLIdentifier
from src.core.steps.base_downloader import BaseVideoDownloader
from src.core.steps.step1_download import YouTubeDownloader
from src.core.steps.step1_bilibili_download import BilibiliDownloader


class VideoDownloaderFactory:
    """视频下载器工厂类"""
    
    @staticmethod
    def create_downloader(
        url: str,
        config: Config,
        logger: Logger,
        progress_callback: Optional[Callable] = None
    ) -> BaseVideoDownloader:
        """
        根据URL创建对应的下载器
        
        Args:
            url: 视频URL
            config: 配置对象
            logger: 日志对象
            progress_callback: 进度回调函数
            
        Returns:
            BaseVideoDownloader: 对应平台的下载器实例
            
        Raises:
            ValueError: 不支持的视频平台
        """
        platform = URLIdentifier.identify_platform(url)
        
        if platform == 'youtube':
            logger.info(f"[识别] 检测到YouTube视频")
            return YouTubeDownloader(config, logger, progress_callback)
        
        elif platform == 'bilibili':
            logger.info(f"[识别] 检测到Bilibili视频")
            return BilibiliDownloader(config, logger, progress_callback)
        
        else:
            raise ValueError(f"不支持的视频平台: {url}")
    
    @staticmethod
    def get_supported_platforms() -> list:
        """
        获取支持的平台列表
        
        Returns:
            list: 支持的平台名称列表
        """
        return ['youtube', 'bilibili']

