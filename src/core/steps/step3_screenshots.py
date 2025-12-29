"""
步骤3：视频截图提取模块（优化版）
根据字幕时间戳提取视频截图
支持并行处理、断点续传、进度保存、智能去重
"""
import subprocess
import os
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import pysrt

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator


class VideoScreenshot:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.time_offsets = self._parse_time_offsets()
        self.max_workers = self.config.get_int('step3_screenshots', 'max_workers', 4)
        self.batch_size = self.config.get_int('step3_screenshots', 'batch_size', 50)
        self.enable_deduplication = self.config.get_boolean('step3_screenshots', 'enable_deduplication', True)
        self.phash_threshold = self.config.get_int('step3_screenshots', 'phash_threshold', 10)
        self.delete_duplicate_files = self.config.get_boolean('step3_screenshots', 'delete_duplicate_files', False)
        
    def check_ffmpeg(self) -> bool:
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.success("ffmpeg可用")
                return True
            else:
                self.logger.error("ffmpeg不可用")
                return False
        except FileNotFoundError:
            self.logger.error("ffmpeg未安装，请安装ffmpeg")
            return False
        except Exception as e:
            self.logger.error(f"检查ffmpeg失败: {str(e)}")
            return False
    
    def _load_progress(self, progress_file: str) -> Dict:
        """加载进度信息"""
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_progress(self, progress_file: str, progress: Dict):
        """保存进度信息"""
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def extract_screenshots(self, video_path: str, srt_path: str, output_dir: str) -> Dict:
        """
        根据字幕时间戳提取视频截图（并行处理版本）
        
        Args:
            video_path: 视频文件路径
            srt_path: 字幕文件路径
            output_dir: 输出目录
            
        Returns:
            Dict: 截图提取结果
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤3开始] 视频截图提取（并行处理）")
        self.logger.info(f"视频文件: {os.path.basename(video_path)}")
        self.logger.info(f"字幕文件: {os.path.basename(srt_path)}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info("=" * 60)
        
        screenshot_start_time = time.time()
        
        try:
            # 标准化路径
            video_path = os.path.abspath(video_path)
            srt_path = os.path.abspath(srt_path)
            progress_file = os.path.join(output_dir, 'screenshot_progress.json')
            
            # 检查输入文件
            if not os.path.exists(video_path):
                raise Exception(f"视频文件不存在: {video_path}")
            
            if not os.path.exists(srt_path):
                raise Exception(f"字幕文件不存在: {srt_path}")
            
            # 验证文件
            self.logger.info("[验证] 验证输入文件...")
            video_valid, video_msg = Validator.validate_video_file(video_path)
            if not video_valid:
                self.logger.error(f"[错误] 视频文件验证失败: {video_msg}")
                raise Exception(f"视频文件验证失败: {video_msg}")
            self.logger.success(f"[成功] 视频文件验证通过: {video_msg}")
            
            srt_valid, srt_msg, srt_stats = Validator.validate_srt_file(srt_path)
            if not srt_valid:
                self.logger.error(f"[错误] 字幕文件验证失败: {srt_msg}")
                raise Exception(f"字幕文件验证失败: {srt_msg}")
            self.logger.success(f"[成功] 字幕文件验证通过")
            self.logger.info(f"[统计] 字幕统计: {srt_stats}")
            
            # 检查ffmpeg
            self.logger.info("[检查] 检查ffmpeg依赖...")
            if not self.check_ffmpeg():
                self.logger.error("[错误] ffmpeg不可用")
                raise Exception("ffmpeg不可用，无法提取截图")
            
            # 创建输出目录
            screenshots_dir = os.path.join(output_dir, 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)
            self.logger.info(f"[目录] 截图输出目录: {screenshots_dir}")
            
            # 读取字幕文件
            self.logger.info("[读取] 正在读取字幕文件...")
            subs = pysrt.open(srt_path, encoding='utf-8')
            
            self.logger.info("[配置] 处理配置:")
            self.logger.info(f"  - 字幕条数: {len(subs)}")
            self.logger.info(f"  - 时间偏移: {self.time_offsets}")
            self.logger.info(f"  - 并行线程: {self.max_workers}")
            self.logger.info(f"  - 批次大小: {self.batch_size}")
            
            # 加载进度
            progress = self._load_progress(progress_file)
            completed_count = progress.get('completed_count', 0)
            
            if completed_count > 0:
                self.logger.info(f"断点续传: 已完成 {completed_count} 个字幕")
            
            # 准备任务列表
            tasks = []
            for i, sub in enumerate(subs, 1):
                if i <= completed_count:
                    continue  # 跳过已完成的
                
                start_seconds = (sub.start.hours * 3600 + 
                               sub.start.minutes * 60 + 
                               sub.start.seconds + 
                               sub.start.milliseconds / 1000.0)
                
                for offset in self.time_offsets:
                    timestamp = max(0, start_seconds + offset)
                    offset_str = f"{offset:+.1f}s".replace('+', 'plus').replace('-', 'minus')
                    screenshot_filename = f"{i:03d}_{offset_str}.png"
                    screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
                    
                    subtitle_info = {
                        'subtitle_index': i,
                        'start_time': start_seconds,
                        'text': sub.text.strip(),
                        'offset': offset,
                        'timestamp': timestamp,
                        'filename': screenshot_filename,
                        'path': screenshot_path
                    }
                    
                    tasks.append((i, subtitle_info))
            
            # 并行处理截图
            total_tasks = len(tasks)
            completed_tasks = 0
            failed_tasks = 0
            screenshot_info = progress.get('screenshot_info', [])
            
            self.logger.info(f"待处理任务: {total_tasks}")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_task = {
                    executor.submit(self._extract_single_screenshot, 
                                  video_path, 
                                  task[1]['timestamp'], 
                                  task[1]['path']): task 
                    for task in tasks
                }
                
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    subtitle_idx, subtitle_data = task
                    
                    try:
                        success = future.result()
                        if success:
                            screenshot_info.append(subtitle_data)
                        else:
                            failed_tasks += 1
                        
                        completed_tasks += 1
                        completed_count += 1
                        
                        # 每50个任务保存一次进度
                        if completed_tasks % self.batch_size == 0:
                            progress['completed_count'] = completed_count
                            progress['screenshot_info'] = screenshot_info
                            self._save_progress(progress_file, progress)
                            self.logger.info(f"进度保存: {completed_count}/{len(subs)} 字幕")
                        
                        if completed_tasks % 10 == 0:
                            self.logger.info(f"已处理: {completed_count}/{len(subs)}")
                            
                    except Exception as e:
                        self.logger.warning(f"处理字幕 {subtitle_idx} 失败: {str(e)}")
                        failed_tasks += 1
                        completed_tasks += 1
            
            # 去重处理（在保存索引文件之前）
            dedup_stats = None
            if self.enable_deduplication:
                if IMAGEHASH_AVAILABLE:
                    self.logger.info("[去重] 开始截图去重处理...")
                    dedup_stats = self._deduplicate_screenshots(screenshots_dir, screenshot_info)
                    self.logger.info(f"[去重] 去重完成")
                else:
                    self.logger.warning("[去重] imagehash库未安装，跳过去重")
            
            # 保存最终截图索引文件
            index_file = os.path.join(output_dir, 'screenshot_index.json')
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(screenshot_info, f, ensure_ascii=False, indent=2)
            
            self.logger.file_created(index_file)
            
            # 验证截图结果
            screenshot_count = len([f for f in os.listdir(screenshots_dir) 
                                  if f.lower().endswith('.png')])
            
            elapsed_time = time.time() - screenshot_start_time
            
            self.logger.info("=" * 60)
            self.logger.success(f"[完成] 截图提取完成:")
            self.logger.info(f"  - 成功截图: {len(screenshot_info)}/{total_tasks}")
            self.logger.info(f"  - 失败任务: {failed_tasks}")
            self.logger.info(f"  - 实际文件: {screenshot_count} 个")
            self.logger.info(f"  - 总耗时: {elapsed_time:.2f}秒")
            self.logger.info(f"  - 平均速度: {len(screenshot_info)/elapsed_time:.2f} 截图/秒")
            
            # 删除进度文件（表示已完成）
            if os.path.exists(progress_file):
                os.remove(progress_file)
                self.logger.info("[清理] 已清理进度文件")
            
            # 统计信息
            extraction_stats = {
                'total_subtitles': len(subs),
                'total_screenshots_expected': len(tasks),
                'screenshots_extracted': len(screenshot_info),
                'screenshots_failed': failed_tasks,
                'success_rate': (len(screenshot_info) / len(tasks) * 100) if len(tasks) > 0 else 0,
                'time_offsets': self.time_offsets,
                'max_workers': self.max_workers,
                'batch_size': self.batch_size,
                'deduplication_enabled': self.enable_deduplication,
                'deduplication_stats': dedup_stats if dedup_stats else None
            }
            
            return {
                'success': True,
                'screenshots_dir': screenshots_dir,
                'index_file': index_file,
                'extraction_stats': extraction_stats,
                'message': f'截图提取成功: {len(screenshot_info)}/{len(tasks)}'
            }
            
        except Exception as e:
            elapsed_time = time.time() - screenshot_start_time
            error_msg = f"截图提取失败: {str(e)}"
            
            self.logger.error("=" * 60)
            self.logger.error(f"[步骤3失败] {error_msg} (耗时: {elapsed_time:.2f}秒)")
            self.logger.error(f"[错误] 错误详情:")
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
    
    def _extract_single_screenshot(self, video_path: str, timestamp: float, output_path: str) -> bool:
        """提取单张截图"""
        try:
            # 检查是否已存在
            if os.path.exists(output_path):
                return True
            
            # 获取配置
            image_quality = self.config.get_int('step3_screenshots', 'image_quality', 95)
            resolution = self.config.get('step3_screenshots', 'resolution', '1280x720')
            
            # 构建ffmpeg命令
            cmd = [
                'ffmpeg',
                '-ss', str(timestamp),  # 跳转到指定时间
                '-i', video_path,       # 输入视频
                '-frames:v', '1',       # 只提取一帧
                '-q:v', str(100 - image_quality),  # 图片质量
                '-s', resolution,       # 分辨率
                '-y',                   # 覆盖输出文件
                output_path
            ]
            
            # 执行ffmpeg命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30  # 30秒超时
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                return False
                
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            return False
    
    def _parse_time_offsets(self) -> List[float]:
        """解析时间偏移配置"""
        try:
            offsets_str = self.config.get('step3_screenshots', 'time_offsets', '0.0')
            if ',' in offsets_str:
                offsets = [float(x.strip()) for x in offsets_str.split(',')]
            else:
                offsets = [float(offsets_str)]
            return offsets
        except Exception:
            return [0.0]
    
    def _deduplicate_screenshots(self, screenshots_dir: str, screenshot_info: List[Dict]) -> Dict:
        """
        对提取的截图进行去重处理（相似度累积检测）
        
        Args:
            screenshots_dir: 截图目录
            screenshot_info: 截图信息列表
            
        Returns:
            Dict: 去重统计信息
        """
        dedup_start_time = time.time()
        
        # 统计信息
        total_count = len(screenshot_info)
        duplicate_count = 0
        deleted_files = 0
        
        self.logger.info(f"[去重] 开始计算pHash，共 {total_count} 个截图条目")
        
        # 1. 计算所有截图的pHash
        hashes = []
        for i, info in enumerate(screenshot_info):
            try:
                img_path = info['path']
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    hash_val = imagehash.phash(img)
                    info['phash'] = str(hash_val)
                    hashes.append(hash_val)
                    img.close()
                else:
                    self.logger.warning(f"[去重] 截图文件不存在: {img_path}")
                    hashes.append(None)
            except Exception as e:
                self.logger.warning(f"[去重] 计算pHash失败 {info['filename']}: {str(e)}")
                hashes.append(None)
            
            if (i + 1) % self.batch_size == 0:
                self.logger.info(f"[去重] pHash计算进度: {i + 1}/{total_count}")
        
        self.logger.info(f"[去重] pHash计算完成，开始去重检测（阈值={self.phash_threshold}）")
        
        # 2. 标记第一张为原始
        if len(screenshot_info) > 0:
            screenshot_info[0]['is_duplicate'] = False
            screenshot_info[0]['duplicate_of_index'] = None
            screenshot_info[0]['reference_screenshot'] = None
        
        # 3. 遍历其余截图，进行相似度累积检测
        for i in range(1, len(screenshot_info)):
            if hashes[i] is None:
                screenshot_info[i]['is_duplicate'] = False
                continue
            
            current_hash = hashes[i]
            prev_idx = i - 1
            
            # 跳过前一张如果它的hash无效
            while prev_idx >= 0 and hashes[prev_idx] is None:
                prev_idx -= 1
            
            if prev_idx < 0:
                screenshot_info[i]['is_duplicate'] = False
                continue
            
            prev_hash = hashes[prev_idx]
            distance_to_prev = current_hash - prev_hash
            
            if distance_to_prev <= self.phash_threshold:
                # 找到前一张的根节点
                root_idx = self._find_root_index(screenshot_info, prev_idx)
                root_hash = hashes[root_idx]
                
                # 检查与根节点的距离
                distance_to_root = current_hash - root_hash
                
                if distance_to_root <= self.phash_threshold:
                    # 标记为重复，引用根节点
                    screenshot_info[i]['is_duplicate'] = True
                    screenshot_info[i]['duplicate_of_index'] = root_idx
                    screenshot_info[i]['hamming_distance'] = int(distance_to_prev)
                    screenshot_info[i]['hamming_distance_to_root'] = int(distance_to_root)
                    screenshot_info[i]['reference_screenshot'] = screenshot_info[root_idx]['filename']
                    duplicate_count += 1
                    
                    # 可选：删除重复的截图文件
                    if self.delete_duplicate_files:
                        try:
                            if os.path.exists(screenshot_info[i]['path']):
                                os.remove(screenshot_info[i]['path'])
                                deleted_files += 1
                        except Exception as e:
                            self.logger.warning(f"[去重] 删除重复文件失败: {str(e)}")
                else:
                    # 与根节点差异太大，作为新原始
                    screenshot_info[i]['is_duplicate'] = False
                    screenshot_info[i]['duplicate_of_index'] = None
                    screenshot_info[i]['reference_screenshot'] = None
            else:
                # 与前一张不相似，作为新原始
                screenshot_info[i]['is_duplicate'] = False
                screenshot_info[i]['duplicate_of_index'] = None
                screenshot_info[i]['reference_screenshot'] = None
            
            if (i + 1) % self.batch_size == 0:
                self.logger.info(f"[去重] 去重进度: {i + 1}/{total_count}, 已发现重复: {duplicate_count}")
        
        dedup_elapsed = time.time() - dedup_start_time
        
        # 统计结果
        dedup_stats = {
            'total_screenshots': total_count,
            'duplicate_count': duplicate_count,
            'unique_count': total_count - duplicate_count,
            'duplicate_rate': (duplicate_count / total_count * 100) if total_count > 0 else 0,
            'deleted_files': deleted_files,
            'threshold': self.phash_threshold,
            'processing_time': dedup_elapsed
        }
        
        self.logger.success(f"[去重] 去重完成:")
        self.logger.info(f"  - 总截图数: {total_count}")
        self.logger.info(f"  - 重复截图: {duplicate_count} ({dedup_stats['duplicate_rate']:.1f}%)")
        self.logger.info(f"  - 唯一截图: {dedup_stats['unique_count']}")
        if self.delete_duplicate_files:
            self.logger.info(f"  - 删除文件: {deleted_files}")
        self.logger.info(f"  - 处理耗时: {dedup_elapsed:.2f}秒")
        
        return dedup_stats
    
    def _find_root_index(self, screenshot_info: List[Dict], index: int) -> int:
        """
        查找引用链的根节点索引
        
        Args:
            screenshot_info: 截图信息列表
            index: 当前索引
            
        Returns:
            int: 根节点索引
        """
        visited = set()
        while screenshot_info[index].get('is_duplicate', False):
            if index in visited:
                self.logger.warning(f"[去重] 检测到循环引用: {index}")
                break
            visited.add(index)
            next_idx = screenshot_info[index].get('duplicate_of_index')
            if next_idx is None or next_idx >= len(screenshot_info):
                break
            index = next_idx
        return index


def main(video_path: str, srt_path: str, output_dir: str) -> bool:
    """步骤4主函数"""
    try:
        config = Config()
        logger = Logger("step3_screenshots")
        screenshot = VideoScreenshot(config, logger)
        
        logger.step_start(4, "视频截图提取（并行处理）")
        
        result = screenshot.extract_screenshots(video_path, srt_path, output_dir)
        
        if result['success']:
            logger.step_complete(4, "视频截图提取")
            logger.info("=" * 50)
            logger.info("步骤4完成，输出文件：")
            logger.info(f"- 截图目录: {result['screenshots_dir']}")
            logger.info(f"- 索引文件: {result['index_file']}")
            logger.info(f"- 提取统计: {result['extraction_stats']['screenshots_extracted']}/{result['extraction_stats']['total_screenshots_expected']}")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤4失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step3_screenshots")
        logger.error(f"步骤4执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python step3_screenshots.py <video_path> <srt_path> <output_dir>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if success else 1)
