"""
视频下载器抽象基类
定义所有视频下载器的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable


class BaseVideoDownloader(ABC):
    """视频下载器抽象基类"""
    
    def __init__(self, config, logger, progress_callback: Optional[Callable] = None):
        """
        初始化下载器
        
        Args:
            config: 配置对象
            logger: 日志对象
            progress_callback: 进度回调函数
        """
        self.config = config
        self.logger = logger
        self.progress_callback = progress_callback
    
    @abstractmethod
    def download_video(self, url: str, output_dir: str) -> Dict:
        """
        下载视频
        
        Args:
            url: 视频URL
            output_dir: 输出目录
            
        Returns:
            Dict: {
                'success': bool,           # 是否成功
                'video_info': Dict,        # 视频信息
                'video_file': str,         # 视频文件路径
                'info_file': str,          # 信息文件路径
                'message': str,            # 消息
                'from_cache': bool         # 是否来自缓存
            }
        """
        pass
    
    @abstractmethod
    def check_dependencies(self) -> tuple:
        """
        检查依赖是否可用
        
        Returns:
            tuple: (bool, Optional[list]) - (是否可用, 命令列表)
        """
        pass

