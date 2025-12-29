#!/usr/bin/env python3
"""测试下载功能"""
import os
import sys
import tempfile
import shutil

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from src.core.steps.step1_download import YouTubeDownloader
from src.utils.config import Config
from src.utils.logger import Logger

def test_download():
    """测试下载功能"""
    url = "https://www.youtube.com/watch?v=sZIOVNQfKxI"
    
    # 创建临时输出目录
    test_output_dir = os.path.join(tempfile.gettempdir(), "yt_test_download")
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)
    os.makedirs(test_output_dir)
    
    print("=" * 60)
    print("测试YouTube视频下载功能")
    print("=" * 60)
    print(f"视频URL: {url}")
    print(f"输出目录: {test_output_dir}")
    print("=" * 60)
    print()
    
    try:
        # 初始化
        config = Config()
        logger = Logger("test_download")
        downloader = YouTubeDownloader(config, logger)
        
        # 执行下载
        result = downloader.download_video(url, test_output_dir)
        
        print()
        print("=" * 60)
        if result['success']:
            print("[成功] 下载测试通过")
            print(f"视频文件: {result.get('video_file', 'N/A')}")
            print(f"文件大小: {result.get('video_info', {}).get('file_size', 0) / 1024 / 1024:.2f} MB")
            print(f"是否使用缓存: {result.get('from_cache', False)}")
        else:
            print("[失败] 下载测试失败")
            print(f"错误信息: {result.get('error', '未知错误')}")
        print("=" * 60)
        
        return result['success']
        
    except Exception as e:
        print(f"[异常] 测试过程中出现异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试目录（可选，保留用于检查）
        # if os.path.exists(test_output_dir):
        #     shutil.rmtree(test_output_dir)
        pass

if __name__ == "__main__":
    success = test_download()
    sys.exit(0 if success else 1)




