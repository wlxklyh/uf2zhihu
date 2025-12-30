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
import math
import shutil
import webbrowser
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
        
        # 动态计算默认max_workers
        cpu_count = os.cpu_count() or 4
        default_max_workers = max(4, math.ceil(cpu_count * 1.5))
        self.max_workers = self.config.get_int('step3_screenshots', 'max_workers', default_max_workers)
        
        self.batch_size = self.config.get_int('step3_screenshots', 'batch_size', 50)
        self.enable_deduplication = self.config.get_boolean('step3_screenshots', 'enable_deduplication', True)
        self.phash_threshold = self.config.get_int('step3_screenshots', 'phash_threshold', 10)
        self.delete_duplicate_files = self.config.get_boolean('step3_screenshots', 'delete_duplicate_files', False)
        self.generate_dedup_report = self.config.get_boolean('step3_screenshots', 'generate_dedup_report', True)
        self.auto_open_dedup_report = self.config.get_boolean('step3_screenshots', 'auto_open_dedup_report', True)
        
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
                '-loglevel', 'error',   # 只输出错误信息，减少日志开销
                '-ss', str(timestamp),  # 跳转到指定时间
                '-i', video_path,       # 输入视频
                '-vsync', '0',          # 禁用帧同步，加速单帧提取
                '-frames:v', '1',       # 只提取一帧
                '-q:v', str(100 - image_quality),  # 图片质量
                '-s', resolution,       # 分辨率
                '-threads', '1',        # 单线程，避免多实例线程竞争
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
    
    def _compute_single_phash(self, img_path: str) -> Optional[str]:
        """
        计算单张图片的pHash
        
        Args:
            img_path: 图片文件路径
            
        Returns:
            Optional[str]: pHash字符串，失败返回None
        """
        try:
            if os.path.exists(img_path):
                img = Image.open(img_path)
                hash_val = imagehash.phash(img)
                img.close()
                return str(hash_val)
            else:
                return None
        except Exception as e:
            return None
    
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
        
        self.logger.info(f"[去重] 开始计算pHash，共 {total_count} 个截图条目（并行处理）")
        
        # 1. 并行计算所有截图的pHash
        hashes = [None] * total_count
        completed_hash_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self._compute_single_phash, info['path']): i 
                for i, info in enumerate(screenshot_info)
            }
            
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    hash_str = future.result()
                    if hash_str:
                        hash_val = imagehash.hex_to_hash(hash_str)
                        screenshot_info[idx]['phash'] = hash_str
                        hashes[idx] = hash_val
                    else:
                        if os.path.exists(screenshot_info[idx]['path']):
                            self.logger.warning(f"[去重] 计算pHash失败 {screenshot_info[idx]['filename']}")
                        else:
                            self.logger.warning(f"[去重] 截图文件不存在: {screenshot_info[idx]['path']}")
                        hashes[idx] = None
                except Exception as e:
                    self.logger.warning(f"[去重] 计算pHash异常 {screenshot_info[idx]['filename']}: {str(e)}")
                    hashes[idx] = None
                
                completed_hash_count += 1
                if completed_hash_count % self.batch_size == 0:
                    self.logger.info(f"[去重] pHash计算进度: {completed_hash_count}/{total_count}")
        
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
        
        self.logger.success(f"[去重] 去重检测完成:")
        self.logger.info(f"  - 总截图数: {total_count}")
        self.logger.info(f"  - 重复截图: {duplicate_count} ({dedup_stats['duplicate_rate']:.1f}%)")
        self.logger.info(f"  - 唯一截图: {dedup_stats['unique_count']}")
        self.logger.info(f"  - 处理耗时: {dedup_elapsed:.2f}秒")
        
        # 生成去重报告（如果启用）
        if self.generate_dedup_report:
            self.logger.info("[报告] 开始生成去重可视化报告...")
            try:
                report_dir = os.path.join(os.path.dirname(screenshots_dir), 'deduplication_report')
                
                # 拷贝截图文件
                self.logger.info("[报告] 拷贝截图文件...")
                images_dir, copied_count = self._copy_screenshots_for_report(screenshot_info, os.path.dirname(screenshots_dir))
                self.logger.info(f"[报告] 已拷贝 {copied_count} 张截图")
                
                # 生成分组信息
                groups = self._generate_dedup_groups(screenshot_info)
                
                # 生成HTML报告
                html_path = self._generate_html_report(
                    screenshot_info, 
                    dedup_stats, 
                    groups, 
                    report_dir,
                    './images'
                )
                
                self.logger.success(f"[报告] HTML报告已生成: {html_path}")
                
                # 自动打开HTML（如果启用）
                if self.auto_open_dedup_report:
                    try:
                        webbrowser.open('file://' + os.path.abspath(html_path))
                        self.logger.info("[报告] 已在浏览器中打开报告")
                    except Exception as e:
                        self.logger.warning(f"[报告] 自动打开浏览器失败: {str(e)}")
                
                # 将报告信息添加到统计中
                dedup_stats['report_generated'] = True
                dedup_stats['report_path'] = html_path
                dedup_stats['images_copied'] = copied_count
                
            except Exception as e:
                self.logger.error(f"[报告] 生成报告失败: {str(e)}")
                self.logger.error(f"[报告] 错误详情: {traceback.format_exc()}")
                dedup_stats['report_generated'] = False
                dedup_stats['report_error'] = str(e)
        
        # 删除重复文件（在生成报告之后）
        if self.delete_duplicate_files:
            self.logger.info("[清理] 开始删除重复截图文件...")
            for info in screenshot_info:
                if info.get('is_duplicate', False):
                    try:
                        if os.path.exists(info['path']):
                            os.remove(info['path'])
                            deleted_files += 1
                    except Exception as e:
                        self.logger.warning(f"[清理] 删除文件失败 {info['filename']}: {str(e)}")
            
            self.logger.info(f"[清理] 已删除 {deleted_files} 个重复文件")
            dedup_stats['deleted_files'] = deleted_files
        
        return dedup_stats
    
    def _copy_screenshots_for_report(self, screenshot_info: List[Dict], output_dir: str) -> Tuple[str, int]:
        """
        拷贝截图文件到报告目录
        
        Args:
            screenshot_info: 截图信息列表
            output_dir: step3输出目录
            
        Returns:
            Tuple[str, int]: (图片目录路径, 成功拷贝的文件数)
        """
        # 创建报告目录结构
        report_dir = os.path.join(output_dir, 'deduplication_report')
        images_dir = os.path.join(report_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # 准备拷贝任务
        copy_tasks = []
        for info in screenshot_info:
            src_path = info['path']
            if os.path.exists(src_path):
                dst_path = os.path.join(images_dir, info['filename'])
                copy_tasks.append((src_path, dst_path))
        
        # 并行拷贝文件
        success_count = 0
        failed_count = 0
        
        def copy_single_file(src: str, dst: str) -> bool:
            try:
                shutil.copy2(src, dst)
                return True
            except Exception as e:
                return False
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(copy_single_file, src, dst): (src, dst) for src, dst in copy_tasks}
            
            for future in as_completed(futures):
                src, dst = futures[future]
                try:
                    if future.result():
                        success_count += 1
                    else:
                        failed_count += 1
                        self.logger.warning(f"[报告] 拷贝文件失败: {os.path.basename(src)}")
                except Exception as e:
                    failed_count += 1
                    self.logger.warning(f"[报告] 拷贝文件异常: {os.path.basename(src)}, {str(e)}")
        
        if failed_count > 0:
            self.logger.warning(f"[报告] 拷贝完成: 成功 {success_count}, 失败 {failed_count}")
        
        return images_dir, success_count
    
    def _generate_dedup_groups(self, screenshot_info: List[Dict]) -> Dict[int, List[int]]:
        """
        生成去重分组信息
        
        Args:
            screenshot_info: 截图信息列表
            
        Returns:
            Dict[int, List[int]]: 以根节点索引为key，成员索引列表为value
        """
        groups = {}
        
        for i, info in enumerate(screenshot_info):
            if info.get('is_duplicate', False):
                root_idx = info.get('duplicate_of_index')
            else:
                root_idx = i
            
            if root_idx not in groups:
                groups[root_idx] = []
            groups[root_idx].append(i)
        
        # 只保留有重复的组（成员数>1）
        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
        
        return duplicate_groups
    
    def _generate_html_report(self, screenshot_info: List[Dict], dedup_stats: Dict, 
                             groups: Dict[int, List[int]], report_dir: str, 
                             images_rel_path: str) -> str:
        """
        生成HTML可视化报告
        
        Args:
            screenshot_info: 截图信息列表
            dedup_stats: 去重统计信息
            groups: 重复组信息
            report_dir: 报告目录路径
            images_rel_path: 图片相对路径（相对于HTML文件）
            
        Returns:
            str: HTML文件路径
        """
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>截图去重分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .stat-card h3 {{
            color: #667eea;
            font-size: 2em;
            margin-bottom: 10px;
        }}
        
        .stat-card p {{
            color: #666;
            font-size: 0.9em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .screenshots-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .screenshot-card {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            border: 3px solid transparent;
        }}
        
        .screenshot-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }}
        
        .screenshot-card.unique {{
            border-color: #28a745;
        }}
        
        .screenshot-card.duplicate {{
            border-color: #ffc107;
        }}
        
        .screenshot-card img {{
            width: 100%;
            height: 150px;
            object-fit: cover;
            display: block;
        }}
        
        .screenshot-info {{
            padding: 15px;
        }}
        
        .screenshot-info .index {{
            font-size: 1.2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .screenshot-info .filename {{
            font-size: 0.85em;
            color: #666;
            margin-bottom: 10px;
            word-break: break-all;
        }}
        
        .screenshot-info .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        
        .status.unique {{
            background: #28a745;
            color: white;
        }}
        
        .status.duplicate {{
            background: #ffc107;
            color: #333;
        }}
        
        .screenshot-info .detail {{
            font-size: 0.85em;
            color: #666;
            margin: 3px 0;
        }}
        
        .screenshot-info .reference {{
            color: #667eea;
            font-weight: bold;
            cursor: pointer;
            text-decoration: underline;
        }}
        
        .groups-section {{
            margin-top: 30px;
        }}
        
        .group-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }}
        
        .group-card h3 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .group-members {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }}
        
        .member-tag {{
            background: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .member-tag.root {{
            background: #28a745;
            color: white;
            font-weight: bold;
        }}
        
        .legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        
        .legend-color.unique {{
            background: #28a745;
        }}
        
        .legend-color.duplicate {{
            background: #ffc107;
        }}
        
        footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>截图去重分析报告</h1>
            <p>相似度累积检测算法（方案C）</p>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <div class="summary">
            <div class="stat-card">
                <h3>{dedup_stats['total_screenshots']}</h3>
                <p>总截图数</p>
            </div>
            <div class="stat-card">
                <h3>{dedup_stats['unique_count']}</h3>
                <p>唯一截图 ({100 - dedup_stats['duplicate_rate']:.1f}%)</p>
            </div>
            <div class="stat-card">
                <h3>{dedup_stats['duplicate_count']}</h3>
                <p>重复截图 ({dedup_stats['duplicate_rate']:.1f}%)</p>
            </div>
            <div class="stat-card">
                <h3>{dedup_stats['threshold']}</h3>
                <p>汉明距离阈值</p>
            </div>
            <div class="stat-card">
                <h3>{len(groups)}</h3>
                <p>重复组数</p>
            </div>
            <div class="stat-card">
                <h3>{max([len(v) for v in groups.values()]) if groups else 0}</h3>
                <p>最大组大小</p>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>截图详情</h2>
                
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color unique"></div>
                        <span>唯一截图</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color duplicate"></div>
                        <span>重复截图</span>
                    </div>
                </div>
                
                <div class="screenshots-grid">
"""
        
        # 添加每张截图的卡片
        for i, info in enumerate(screenshot_info):
            card_class = "duplicate" if info.get('is_duplicate', False) else "unique"
            status_class = "duplicate" if info.get('is_duplicate', False) else "unique"
            status_text = "重复" if info.get('is_duplicate', False) else "唯一"
            
            # 使用相对路径
            img_path = f"{images_rel_path}/{info['filename']}"
            
            html_content += f"""
                    <div class="screenshot-card {card_class}" id="screenshot-{i}">
                        <img src="{img_path}" alt="{info['filename']}" loading="lazy">
                        <div class="screenshot-info">
                            <div class="index">#{i:03d}</div>
                            <div class="filename">{info['filename']}</div>
                            <div class="status {status_class}">{status_text}</div>
"""
            
            if info.get('is_duplicate', False):
                ref_idx = info.get('duplicate_of_index')
                html_content += f"""
                            <div class="detail">引用: <span class="reference" onclick="location.hash='screenshot-{ref_idx}'">#{ref_idx:03d}</span></div>
                            <div class="detail">汉明距离: {info.get('hamming_distance', 'N/A')}</div>
                            <div class="detail">与根节点距离: {info.get('hamming_distance_to_root', 'N/A')}</div>
"""
            else:
                phash_str = info.get('phash', 'N/A')
                phash_display = phash_str[:16] + '...' if phash_str and phash_str != 'N/A' else 'N/A'
                html_content += f"""
                            <div class="detail">pHash: {phash_display}</div>
"""
            
            html_content += """
                        </div>
                    </div>
"""
        
        html_content += """
                </div>
            </div>
            
            <div class="section groups-section">
                <h2>重复组分析</h2>
"""
        
        # 添加重复组信息
        if groups:
            for root_idx, members in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
                root_info = screenshot_info[root_idx]
                html_content += f"""
                <div class="group-card">
                    <h3>组 {root_idx + 1} - 根节点: #{root_idx:03d} ({root_info['filename']})</h3>
                    <p>成员数量: {len(members)}</p>
                    <div class="group-members">
"""
                for member_idx in members:
                    is_root = member_idx == root_idx
                    tag_class = "root" if is_root else ""
                    tag_text = f"#{member_idx:03d}" + (" (根)" if is_root else "")
                    html_content += f"""
                        <div class="member-tag {tag_class}" onclick="location.hash='screenshot-{member_idx}'">{tag_text}</div>
"""
                html_content += """
                    </div>
                </div>
"""
        else:
            html_content += """
                <p>没有发现重复组（所有截图都是唯一的）</p>
"""
        
        html_content += f"""
            </div>
        </div>
        
        <footer>
            <p>截图去重测试工具 | 处理时间: {dedup_stats['processing_time']:.2f}秒</p>
            <p>算法: 相似度累积检测（方案C）| 阈值: {dedup_stats['threshold']}</p>
        </footer>
    </div>
</body>
</html>
"""
        
        # 写入文件
        html_file = os.path.join(report_dir, 'report.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_file
    
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
