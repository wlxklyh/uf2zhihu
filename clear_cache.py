#!/usr/bin/env python3
"""
缓存清理脚本
"""
import os
import sys
import argparse

# 添加项目根目录到Python路径
sys.path.append('.')

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.cache_manager import CacheManager

def main():
    parser = argparse.ArgumentParser(description='清理缓存文件')
    parser.add_argument('--type', choices=['video', 'subtitle_en', 'subtitle_zh', 'all'], 
                       default='all', help='缓存类型')
    parser.add_argument('--stats', action='store_true', help='显示缓存统计')
    
    args = parser.parse_args()
    
    # 初始化
    config = Config()
    logger = Logger("cache_manager")
    cache_manager = CacheManager(config, logger)
    
    if args.stats:
        # 显示缓存统计
        stats = cache_manager.get_cache_stats()
        
        print("=" * 50)
        print("缓存统计信息")
        print("=" * 50)
        
        total_size = 0
        total_count = 0
        
        for cache_type, data in stats.items():
            size_mb = data['size'] / 1024 / 1024
            total_size += data['size']
            total_count += data['count']
            
            type_name = {
                'videos': '视频文件',
                'subtitles_en': '英文字幕',
                'subtitles_zh': '中文字幕'
            }.get(cache_type, cache_type)
            
            print(f"{type_name}: {data['count']} 个文件, {size_mb:.1f} MB")
        
        total_size_mb = total_size / 1024 / 1024
        print("-" * 30)
        print(f"总计: {total_count} 个文件, {total_size_mb:.1f} MB")
        print("=" * 50)
        
        # 列出缓存项
        for cache_type in ['video', 'subtitle_en', 'subtitle_zh']:
            items = cache_manager.list_cached_items(cache_type)
            if items:
                type_name = {
                    'video': '视频',
                    'subtitle_en': '英文字幕', 
                    'subtitle_zh': '中文字幕'
                }.get(cache_type, cache_type)
                
                print(f"\n{type_name}缓存项:")
                for item in items[:5]:  # 只显示前5个
                    title = item.get('title', 'Unknown')[:50]
                    cached_time = item.get('cached_time', '')[:19]
                    print(f"  - {title}... ({cached_time})")
                
                if len(items) > 5:
                    print(f"  ... 还有 {len(items) - 5} 个项目")
    
    else:
        # 清理缓存
        cache_type = None if args.type == 'all' else args.type
        
        print("=" * 50)
        print("清理缓存")
        print("=" * 50)
        
        if cache_type:
            type_name = {
                'video': '视频',
                'subtitle_en': '英文字幕',
                'subtitle_zh': '中文字幕'
            }.get(cache_type, cache_type)
            print(f"清理 {type_name} 缓存...")
        else:
            print("清理所有缓存...")
        
        cache_manager.clear_cache(cache_type)
        
        print("缓存清理完成!")
        print("=" * 50)

if __name__ == "__main__":
    main()
