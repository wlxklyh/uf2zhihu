#!/usr/bin/env python3
"""
完整流程测试脚本
测试从YouTube下载到文章生成的完整流程
"""
import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.append('.')

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.cache_manager import CacheManager

def test_complete_flow():
    """测试完整流程"""
    
    # 测试参数
    youtube_url = "https://www.youtube.com/watch?v=a7V3JKs1a5s&list=PLZlv_N0_O1gZy2nANAiZTd72TBvLyurkl&index=34"
    test_project = "complete_flow_test"
    
    # 创建测试目录
    test_dir = f"test_complete/{test_project}"
    os.makedirs(test_dir, exist_ok=True)
    
    step1_dir = os.path.join(test_dir, "step1")
    step2_dir = os.path.join(test_dir, "step2") 
    step3_dir = os.path.join(test_dir, "step3")
    step4_dir = os.path.join(test_dir, "step4")
    step5_dir = os.path.join(test_dir, "step5")
    step6_dir = os.path.join(test_dir, "step6")
    
    os.makedirs(step1_dir, exist_ok=True)
    os.makedirs(step2_dir, exist_ok=True)
    os.makedirs(step3_dir, exist_ok=True)
    os.makedirs(step4_dir, exist_ok=True)
    os.makedirs(step5_dir, exist_ok=True)
    os.makedirs(step6_dir, exist_ok=True)
    
    logger = Logger("complete_flow_test")
    
    print("=" * 60)
    print("YouTube转文章工具 - 完整流程测试")
    print("=" * 60)
    print(f"测试URL: {youtube_url}")
    print(f"输出目录: {test_dir}")
    print("=" * 60)
    
    # 导入步骤模块
    from src.core.steps.step1_download import main as step1_main
    from src.core.steps.step2_transcribe import main as step2_main
    from src.core.steps.step4_screenshots import main as step4_main
    from src.core.steps.step5_generate_markdown import main as step5_main
    from src.core.steps.step6_generate_prompt import main as step6_main
    
    # 步骤1: 下载视频
    print("\n[步骤1] 下载YouTube视频")
    print("-" * 40)
    success1 = step1_main(youtube_url, step1_dir)
    if not success1:
        print("❌ 步骤1失败")
        return False
    
    # 查找下载的视频文件
    video_file = None
    for file in os.listdir(step1_dir):
        if file.endswith('.mp4'):
            video_file = os.path.join(step1_dir, file)
            break
    
    if not video_file:
        print("❌ 未找到下载的视频文件")
        return False
    
    print(f"[成功] 步骤1成功: {os.path.basename(video_file)}")
    
    # 步骤2: 语音转录 (使用较小的测试 - 只转录前2分钟)
    print("\n[步骤2] 语音转录 (测试模式 - 前2分钟)")
    print("-" * 40)
    
    # 创建短视频用于快速测试
    short_video_path = os.path.join(step2_dir, "short_video.mp4")
    
    try:
        import subprocess
        # 使用ffmpeg提取前2分钟
        cmd = [
            'ffmpeg', '-i', video_file, '-t', '120', 
            '-c', 'copy', '-y', short_video_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        
        if result.returncode == 0:
            print("[成功] 创建测试视频成功 (前2分钟)")
            
            # 转录短视频
            success2 = step2_main(short_video_path, step2_dir)
            if success2:
                print("[成功] 步骤2成功")
                
                # 查找字幕文件
                srt_file = os.path.join(step2_dir, "english_subtitles.srt")
                if os.path.exists(srt_file):
                    # 步骤3已跳过 - 直接使用英文字幕进行截图提取
                    print("\n[步骤3] 已跳过翻译 (使用英文字幕)")
                    print("-" * 40)
                    
                    # 步骤4: 提取截图
                    print("\n[步骤4] 提取截图")
                    print("-" * 40)
                    
                    success4 = step4_main(short_video_path, srt_file, step4_dir)
                    if success4:
                        print("[成功] 步骤4成功")
                        
                        # 步骤5: 生成Markdown
                        print("\n[步骤5] 生成Markdown文章")
                        print("-" * 40)
                        
                        video_info_file = os.path.join(step1_dir, "video_info.json")
                        screenshots_dir = os.path.join(step4_dir, "screenshots")
                        markdown_file = os.path.join(step5_dir, "article.md")
                        
                        success5 = step5_main(srt_file, screenshots_dir, video_info_file, markdown_file)
                        if success5:
                            print("[成功] 步骤5成功")
                            
                            # 步骤6: 生成Prompt
                            print("\n[步骤6] 生成Prompt文件")
                            print("-" * 40)
                            
                            prompt_file = os.path.join(step6_dir, "optimization_prompt.txt")
                            
                            success6 = step6_main(markdown_file, video_info_file, prompt_file)
                            if success6:
                                print("[成功] 步骤6成功")
                                print("\n[完成] 完整流程测试成功!")
                                return True
    
    except Exception as e:
        print(f"[错误] 测试过程异常: {str(e)}")
        return False
    
    print("[错误] 完整流程测试失败")
    return False

if __name__ == "__main__":
    success = test_complete_flow()
    
    if success:
        print("\n" + "=" * 60)
        print("[完成] 所有步骤测试通过!")
        print("=" * 60)
        print("\n查看输出文件:")
        print("- test_complete/complete_flow_test/")
        
        # 显示缓存统计
        print("\n缓存统计:")
        os.system("py clear_cache.py --stats")
        
    else:
        print("\n" + "=" * 60)
        print("[失败] 测试失败，请检查日志")
        print("=" * 60)
    
    sys.exit(0 if success else 1)
