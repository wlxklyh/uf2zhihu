"""
验证工具模块
"""
import os
import json
from typing import Dict, List, Optional, Tuple
import pysrt
from PIL import Image
import subprocess

class Validator:
    @staticmethod
    def validate_video_file(file_path: str) -> Tuple[bool, str]:
        """验证视频文件"""
        if not os.path.exists(file_path):
            return False, f"视频文件不存在: {file_path}"
        
        if not file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            return False, f"不支持的视频格式: {file_path}"
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "视频文件为空"
        
        if file_size < 1024:  # 小于1KB可能有问题
            return False, f"视频文件过小: {file_size} bytes"
        
        # 使用ffprobe检查视频信息
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False, f"无法读取视频信息: {result.stderr}"
            
            info = json.loads(result.stdout)
            
            # 检查是否有视频流
            has_video = any(stream.get('codec_type') == 'video' 
                          for stream in info.get('streams', []))
            if not has_video:
                return False, "文件中没有视频流"
            
            # 检查时长
            duration = float(info.get('format', {}).get('duration', 0))
            if duration <= 0:
                return False, "视频时长无效"
            
            return True, f"视频文件有效 (时长: {duration:.1f}秒)"
            
        except subprocess.TimeoutExpired:
            return False, "视频文件检查超时"
        except json.JSONDecodeError:
            return False, "无法解析视频信息"
        except Exception as e:
            return False, f"视频验证失败: {str(e)}"
    
    @staticmethod
    def validate_srt_file(file_path: str) -> Tuple[bool, str, Dict]:
        """验证SRT字幕文件"""
        if not os.path.exists(file_path):
            return False, f"字幕文件不存在: {file_path}", {}
        
        try:
            subs = pysrt.open(file_path, encoding='utf-8')
            
            if len(subs) == 0:
                return False, "字幕文件为空", {}
            
            # 统计信息
            stats = {
                'subtitle_count': len(subs),
                'total_duration': 0,
                'average_duration': 0,
                'min_duration': float('inf'),
                'max_duration': 0,
                'empty_subtitles': 0,
                'overlapping_subtitles': 0
            }
            
            durations = []
            prev_end = None
            
            for i, sub in enumerate(subs):
                # 检查文本内容
                if not sub.text.strip():
                    stats['empty_subtitles'] += 1
                
                # 计算时长 - 修复SubRipTime对象的方法调用
                try:
                    # SubRipTime对象转换为秒数
                    start_seconds = sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds + sub.start.milliseconds / 1000
                    end_seconds = sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds + sub.end.milliseconds / 1000
                    duration = end_seconds - start_seconds
                except Exception:
                    duration = 0
                durations.append(duration)
                
                stats['min_duration'] = min(stats['min_duration'], duration)
                stats['max_duration'] = max(stats['max_duration'], duration)
                
                # 检查重叠 - 修复时间比较
                try:
                    if prev_end:
                        # 将SubRipTime转换为总秒数进行比较
                        current_start_seconds = sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds + sub.start.milliseconds / 1000
                        prev_end_seconds = prev_end.hours * 3600 + prev_end.minutes * 60 + prev_end.seconds + prev_end.milliseconds / 1000
                        if current_start_seconds < prev_end_seconds:
                            stats['overlapping_subtitles'] += 1
                except Exception:
                    pass
                
                prev_end = sub.end
            
            if durations:
                stats['total_duration'] = sum(durations)
                stats['average_duration'] = stats['total_duration'] / len(durations)
                stats['min_duration'] = stats['min_duration'] if stats['min_duration'] != float('inf') else 0
            
            # 验证结果
            issues = []
            if stats['empty_subtitles'] > 0:
                issues.append(f"发现 {stats['empty_subtitles']} 个空字幕")
            
            if stats['overlapping_subtitles'] > 0:
                issues.append(f"发现 {stats['overlapping_subtitles']} 个重叠字幕")
            
            if stats['average_duration'] < 1:
                issues.append("平均字幕时长过短")
            
            if stats['average_duration'] > 10:
                issues.append("平均字幕时长过长")
            
            success_message = f"字幕文件有效 ({stats['subtitle_count']} 条字幕"
            if issues:
                success_message += f", 发现问题: {'; '.join(issues)}"
            success_message += ")"
            
            return True, success_message, stats
            
        except Exception as e:
            return False, f"字幕文件验证失败: {str(e)}", {}
    
    @staticmethod
    def validate_screenshots(directory: str, expected_count: int) -> Tuple[bool, str]:
        """验证截图文件"""
        if not os.path.exists(directory):
            return False, f"截图目录不存在: {directory}"
        
        image_files = []
        for file in os.listdir(directory):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(file)
        
        if len(image_files) == 0:
            return False, "截图目录中没有图片文件"
        
        # 验证每个图片文件
        invalid_images = []
        total_size = 0
        
        for img_file in image_files:
            img_path = os.path.join(directory, img_file)
            try:
                with Image.open(img_path) as img:
                    # 检查图片尺寸
                    if img.size[0] < 100 or img.size[1] < 100:
                        invalid_images.append(f"{img_file}: 尺寸过小 {img.size}")
                    
                    # 累计文件大小
                    total_size += os.path.getsize(img_path)
                    
            except Exception as e:
                invalid_images.append(f"{img_file}: 无法打开 ({str(e)})")
        
        # 生成验证报告
        report_parts = [f"找到 {len(image_files)} 个图片文件"]
        
        if expected_count > 0:
            if len(image_files) < expected_count:
                report_parts.append(f"预期 {expected_count} 个，实际 {len(image_files)} 个")
            elif len(image_files) > expected_count:
                report_parts.append(f"预期 {expected_count} 个，实际 {len(image_files)} 个 (多余)")
        
        if invalid_images:
            report_parts.append(f"发现 {len(invalid_images)} 个问题图片")
            for invalid in invalid_images[:3]:  # 只显示前3个问题
                report_parts.append(f"  - {invalid}")
            if len(invalid_images) > 3:
                report_parts.append(f"  - ... 还有 {len(invalid_images) - 3} 个问题")
        
        report_parts.append(f"总大小: {total_size / 1024 / 1024:.1f} MB")
        
        success = len(invalid_images) == 0
        message = "; ".join(report_parts)
        
        return success, message
    
    @staticmethod
    def validate_markdown_file(file_path: str) -> Tuple[bool, str]:
        """验证Markdown文件"""
        if not os.path.exists(file_path):
            return False, f"Markdown文件不存在: {file_path}"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return False, "Markdown文件为空"
            
            # 基本统计
            lines = content.split('\n')
            word_count = len(content.split())
            char_count = len(content)
            
            # 检查Markdown元素
            has_headers = any(line.startswith('#') for line in lines)
            has_images = '![' in content and '](' in content
            has_links = '[' in content and '](' in content and not has_images
            
            stats = {
                'line_count': len(lines),
                'word_count': word_count,
                'char_count': char_count,
                'has_headers': has_headers,
                'has_images': has_images,
                'has_links': has_links
            }
            
            # 验证结果
            issues = []
            if word_count < 10:
                issues.append("内容过少")
            
            if not has_headers:
                issues.append("缺少标题")
            
            success_message = f"Markdown文件有效 ({word_count} 词, {len(lines)} 行"
            if issues:
                success_message += f", 问题: {'; '.join(issues)}"
            success_message += ")"
            
            return True, success_message
            
        except Exception as e:
            return False, f"Markdown文件验证失败: {str(e)}"
    
    @staticmethod
    def validate_json_file(file_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """验证JSON文件"""
        if not os.path.exists(file_path):
            return False, f"JSON文件不存在: {file_path}", None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return True, f"JSON文件有效 ({len(str(data))} 字符)", data
            
        except json.JSONDecodeError as e:
            return False, f"JSON格式错误: {str(e)}", None
        except Exception as e:
            return False, f"JSON文件验证失败: {str(e)}", None
