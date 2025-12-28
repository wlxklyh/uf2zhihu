"""
步骤2：语音转录模块
使用OpenAI Whisper将视频转录为英文字幕
"""
import whisper
import os
import json
import subprocess
import threading
import time
import shutil
from datetime import datetime
from typing import Dict, Optional, Callable
import sys
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.file_manager import FileManager
from src.utils.cache_manager import CacheManager

class AudioTranscriber:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.model = None
        self.cache_manager = CacheManager(config, logger)
        self.enable_cache = config.get_boolean('basic', 'enable_cache', True)
        
        # 进度监控相关属性
        self.monitor_thread = None
        self.stop_monitor = None
        self.start_time = None
        self.video_duration = None
        self.progress_callback = None
        self.timeout_occurred = False  # 超时标志
    
    def _calculate_estimated_progress(self) -> Dict:
        """
        计算预估的转录进度
        
        Returns:
            Dict: 包含进度信息的字典
        """
        if not self.start_time or not self.video_duration:
            return {
                'progress': 0,
                'elapsed_time': 0,
                'estimated_remaining': 0,
                'estimated_total': 0
            }
        
        elapsed_time = time.time() - self.start_time
        
        # 从配置获取转录速度系数
        speed_factor = float(self.config.get('step2_transcribe', 'transcribe_speed_factor', '0.15'))
        
        # 计算预估总时间（秒）
        estimated_total_time = self.video_duration * speed_factor
        
        # 计算进度百分比，最多显示95%（避免显示100%但还未完成）
        if estimated_total_time > 0:
            progress = min(95, int((elapsed_time / estimated_total_time) * 100))
        else:
            progress = 0
        
        # 计算预估剩余时间
        estimated_remaining = max(0, estimated_total_time - elapsed_time)
        
        return {
            'progress': progress,
            'elapsed_time': elapsed_time,
            'estimated_remaining': estimated_remaining,
            'estimated_total': estimated_total_time
        }
    
    def _build_detailed_progress(self, progress_info: Dict) -> Dict:
        """
        构建详细的进度数据（类似下载进度的格式）
        
        Args:
            progress_info: 进度信息字典
            
        Returns:
            Dict: 详细进度数据，包含百分比、速度、时间等信息
        """
        # 计算转录速度（相对于实时播放）
        if progress_info['elapsed_time'] > 0 and self.video_duration > 0:
            # 计算已处理的视频时长（基于进度百分比）
            processed_duration = (progress_info['progress'] / 100.0) * self.video_duration
            # 转录速度 = 已处理时长 / 已用时间
            transcribe_speed = processed_duration / progress_info['elapsed_time']
        else:
            transcribe_speed = 0
        
        # 格式化时间
        def format_time(seconds):
            if seconds < 60:
                return f"{int(seconds)}秒"
            elif seconds < 3600:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}分{secs}秒"
            else:
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{hours}小时{minutes}分"
        
        # 格式化视频时长
        def format_duration(seconds):
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        
        # 计算已处理和总时长
        processed_duration = (progress_info['progress'] / 100.0) * self.video_duration
        
        return {
            'percent': round(progress_info['progress'], 1),
            'speed': f"{transcribe_speed:.2f}x" if transcribe_speed > 0 else "--",
            'elapsed': format_time(progress_info['elapsed_time']),
            'eta': format_time(progress_info['estimated_remaining']),
            'processed': format_duration(processed_duration),
            'total': format_duration(self.video_duration),
            'model': self.config.get('step2_transcribe', 'model', 'base'),
            'language': self.config.get('step2_transcribe', 'language', 'en')
        }
    
    def _progress_monitor_loop(self) -> None:
        """
        进度监控线程的主循环
        定期输出转录进度信息和心跳日志
        """
        heartbeat_interval = int(self.config.get('step2_transcribe', 'progress_heartbeat_interval', '30'))
        timeout_factor = float(self.config.get('step2_transcribe', 'transcribe_timeout_factor', '10'))
        timeout_seconds = self.video_duration * timeout_factor if self.video_duration else 3600
        
        # 进度更新间隔（秒）- 用于详细进度回调
        progress_update_interval = 5  # 每5秒更新一次详细进度
        last_detailed_update = time.time()
        
        while not self.stop_monitor.is_set():
            try:
                current_time = time.time()
                
                # 计算当前进度
                progress_info = self._calculate_estimated_progress()
                
                elapsed_minutes = progress_info['elapsed_time'] / 60
                remaining_minutes = progress_info['estimated_remaining'] / 60
                
                # 每隔心跳间隔输出日志
                should_log = (current_time - last_detailed_update) >= heartbeat_interval
                
                if should_log:
                    # 输出心跳日志
                    self.logger.info(
                        f"转录进行中: {progress_info['progress']}% | "
                        f"已用时: {elapsed_minutes:.1f}分钟 | "
                        f"预计还需: {remaining_minutes:.1f}分钟"
                    )
                
                # 定期发送详细进度更新到Web界面
                if (current_time - last_detailed_update) >= progress_update_interval:
                    if self.progress_callback:
                        # 构建详细进度数据（类似下载进度的格式）
                        detailed_progress = self._build_detailed_progress(progress_info)
                        # 发送详细进度
                        self.progress_callback(detailed_progress)
                    
                    last_detailed_update = current_time
                
                # 检查是否超时
                if progress_info['elapsed_time'] > timeout_seconds:
                    error_msg = (
                        f"转录超时！已运行{elapsed_minutes:.1f}分钟，"
                        f"超过限制{timeout_seconds/60:.1f}分钟"
                    )
                    self.logger.error(error_msg)
                    self.timeout_occurred = True  # 设置超时标志
                    self.logger.error("建议：考虑使用更快的模型或对长视频进行预处理")
                    break
                
            except Exception as e:
                self.logger.error(f"监控线程异常: {str(e)}")
            
            # 等待更短的间隔时间以便更频繁地更新进度
            self.stop_monitor.wait(min(progress_update_interval, heartbeat_interval))
    
    def _start_progress_monitor(self, video_duration: float, progress_callback: Optional[Callable] = None) -> None:
        """
        启动进度监控线程
        
        Args:
            video_duration: 视频时长（秒）
            progress_callback: 进度回调函数
        """
        self.video_duration = video_duration
        self.progress_callback = progress_callback
        self.start_time = time.time()
        self.stop_monitor = threading.Event()
        
        # 创建并启动监控线程
        self.monitor_thread = threading.Thread(
            target=self._progress_monitor_loop,
            daemon=True,
            name="TranscribeProgressMonitor"
        )
        self.monitor_thread.start()
        
        self.logger.info(f"进度监控已启动，视频时长: {video_duration:.1f}秒")
    
    def _stop_progress_monitor(self) -> None:
        """
        停止进度监控线程
        """
        if self.stop_monitor and self.monitor_thread:
            self.stop_monitor.set()  # 发送停止信号
            self.monitor_thread.join(timeout=5)  # 等待线程结束，最多5秒
            
            if self.monitor_thread.is_alive():
                self.logger.warning("监控线程未能正常终止")
            else:
                self.logger.info("进度监控已停止")
            
            # 清理
            self.monitor_thread = None
            self.stop_monitor = None
        
    def load_model(self) -> bool:
        """加载Whisper模型"""
        try:
            model_name = self.config.get('step2_transcribe', 'model', 'base')
            use_fp16 = self.config.get_boolean('step2_transcribe', 'use_fp16', False)
            precision_mode = 'FP16' if use_fp16 else 'FP32'
            
            self.logger.info(f"正在加载Whisper模型: {model_name} (精度: {precision_mode})")
            self.logger.info("正在初始化模型，请稍候...")
            
            self.model = whisper.load_model(model_name)
            
            self.logger.success(f"Whisper模型加载成功: {model_name} (精度: {precision_mode})")
            self.logger.info(f"模型已就绪，准备开始转录")
            return True
            
        except Exception as e:
            self.logger.error(f"Whisper模型加载失败: {str(e)}")
            return False
        
    def transcribe_video(self, video_path: str, output_dir: str, youtube_url: Optional[str] = None) -> Dict:
        """
        转录视频音频为英文字幕
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            youtube_url: YouTube视频URL（可选，用于缓存功能）
            
        Returns:
            Dict: 转录结果信息
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤2开始] 语音转录")
        self.logger.info(f"视频文件: {os.path.basename(video_path)}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info("=" * 60)
        
        transcribe_start_time = time.time()
        
        try:
            # 标准化路径
            self.logger.info("[准备] 正在标准化文件路径...")
            video_path = os.path.abspath(video_path)
            self.logger.info(f"视频文件路径: {video_path}")
            
            # 检查输入文件
            if not os.path.exists(video_path):
                # 尝试列出目录内容来调试
                video_dir = os.path.dirname(video_path)
                if os.path.exists(video_dir):
                    files = os.listdir(video_dir)
                    self.logger.info(f"目录 {video_dir} 中的文件: {files}")
                raise Exception(f"视频文件不存在: {video_path}")
            
            self.logger.info("视频文件存在，开始验证...")
            
            # 验证视频文件
            is_valid, validation_message = Validator.validate_video_file(video_path)
            if not is_valid:
                raise Exception(f"视频文件验证失败: {validation_message}")
            
            self.logger.info(f"视频文件验证通过: {validation_message}")
            
            # 检查缓存（如果提供了youtube_url且启用了缓存）
            if youtube_url and self.enable_cache:
                self.logger.info("检查英文字幕缓存...")
                cached_result = self.cache_manager.get_cached_english_subtitles(youtube_url)
                if cached_result:
                    cached_srt_path, cached_info = cached_result
                    self.logger.success("找到缓存的英文字幕，直接使用")
                    
                    # 创建输出目录
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 复制缓存文件到输出目录
                    output_srt = os.path.join(output_dir, 'english_subtitles.srt')
                    shutil.copy2(cached_srt_path, output_srt)
                    self.logger.info(f"从缓存复制字幕: {os.path.basename(output_srt)}")
                    
                    # 同时复制原始转录结果（如果存在）
                    cached_dir = os.path.dirname(cached_srt_path)
                    cache_key = self.cache_manager._get_url_hash(youtube_url)
                    cached_raw_result = os.path.join(cached_dir, f"{cache_key}_raw_result.json")
                    output_raw_result = os.path.join(output_dir, 'transcribe_raw_result.json')
                    if os.path.exists(cached_raw_result):
                        shutil.copy2(cached_raw_result, output_raw_result)
                        self.logger.info(f"从缓存复制原始结果: {os.path.basename(output_raw_result)}")
                    
                    return {
                        'success': True,
                        'srt_file': output_srt,
                        'raw_result_file': output_raw_result,
                        'transcribe_stats': cached_info,
                        'message': f'使用缓存字幕: {cached_info.get("subtitle_count", 0)} 条字幕',
                        'from_cache': True
                    }
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 加载Whisper模型
            self.logger.info("准备加载Whisper模型...")
            if not self.load_model():
                raise Exception("Whisper模型加载失败")
            
            # 获取视频时长
            self.logger.info("正在获取视频时长...")
            video_duration = Validator.get_video_duration(video_path)
            if video_duration > 0:
                self.logger.info(f"视频时长: {video_duration:.1f}秒 ({video_duration/60:.1f}分钟)")
            else:
                self.logger.warning("无法获取视频时长，将不显示进度预估")
            
            # 开始转录
            self.logger.info("开始语音转录，这可能需要几分钟...")
            
            # 启动进度监控线程（如果获取到视频时长）
            if video_duration > 0:
                self._start_progress_monitor(video_duration, self.progress_callback)
            
            try:
                # 获取配置
                language = self.config.get('step2_transcribe', 'language', 'en')
                use_fp16 = self.config.get_boolean('step2_transcribe', 'use_fp16', False)
                precision_mode = 'FP16' if use_fp16 else 'FP32'
                
                # 执行转录
                self.logger.info(f"开始执行 Whisper 转录，语言: {language}, 精度: {precision_mode}")
                try:
                    result = self.model.transcribe(
                        video_path,
                        language=language,
                        verbose=False,  # 避免输出阻塞
                        word_timestamps=True,  # 包含单词级时间戳
                        fp16=use_fp16
                    )
                    self.logger.info("Whisper 转录完成")
                except Exception as transcribe_error:
                    self.logger.error(f"Whisper 转录过程异常: {str(transcribe_error)}")
                    raise Exception(f"语音转录失败: {str(transcribe_error)}")
            finally:
                # 确保停止监控线程
                if video_duration > 0:
                    self._stop_progress_monitor()
                
                # 检查是否发生超时
                if self.timeout_occurred:
                    self.timeout_occurred = False  # 重置标志
                    raise Exception("语音转录超时，请尝试使用更快的模型或更短的视频")
            
            # 保存SRT格式字幕
            srt_path = os.path.join(output_dir, 'english_subtitles.srt')
            self._save_srt(result, srt_path)
            
            # 保存原始转录结果
            raw_result_path = os.path.join(output_dir, 'transcribe_raw_result.json')
            with open(raw_result_path, 'w', encoding='utf-8') as f:
                # 转换为可序列化的格式
                serializable_result = {
                    'text': result['text'],
                    'language': result['language'],
                    'segments': []
                }
                
                for segment in result['segments']:
                    serializable_segment = {
                        'id': segment['id'],
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': segment['text'],
                        'words': []
                    }
                    
                    if 'words' in segment:
                        for word in segment['words']:
                            serializable_word = {
                                'word': word['word'],
                                'start': word['start'],
                                'end': word['end'],
                                'probability': word.get('probability', 0.0)
                            }
                            serializable_segment['words'].append(serializable_word)
                    
                    serializable_result['segments'].append(serializable_segment)
                
                json.dump(serializable_result, f, ensure_ascii=False, indent=2)
            
            # 验证生成的字幕文件
            is_valid, validation_message, stats = Validator.validate_srt_file(srt_path)
            if not is_valid:
                self.logger.warning(f"字幕文件验证警告: {validation_message}")
            else:
                self.logger.success(f"字幕文件验证通过: {validation_message}")
            
            # 统计信息
            transcribe_stats = {
                'subtitle_count': len(result['segments']),
                'total_duration': result['segments'][-1]['end'] if result['segments'] else 0,
                'language_detected': result['language'],
                'average_confidence': self._calculate_average_confidence(result),
                'file_stats': stats
            }
            
            self.logger.info(f"转录完成: {transcribe_stats['subtitle_count']} 条字幕")
            self.logger.info(f"检测语言: {transcribe_stats['language_detected']}")
            self.logger.info(f"平均置信度: {transcribe_stats['average_confidence']:.2f}")
            
            # 缓存转录结果（如果提供了youtube_url且启用了缓存）
            if youtube_url and self.enable_cache:
                self.logger.info("保存转录结果到缓存...")
                try:
                    self.cache_manager.cache_english_subtitles(youtube_url, srt_path, transcribe_stats)
                    
                    # 同时缓存原始转录结果
                    cache_key = self.cache_manager._get_url_hash(youtube_url)
                    cache_raw_result_path = os.path.join(
                        self.cache_manager.subtitles_en_cache,
                        f"{cache_key}_raw_result.json"
                    )
                    shutil.copy2(raw_result_path, cache_raw_result_path)
                    self.logger.success("转录结果已缓存")
                except Exception as e:
                    self.logger.warning(f"缓存保存失败（不影响转录结果）: {str(e)}")
            
            return {
                'success': True,
                'srt_file': srt_path,
                'raw_result_file': raw_result_path,
                'transcribe_stats': transcribe_stats,
                'message': f'语音转录成功: {transcribe_stats["subtitle_count"]} 条字幕'
            }
            
        except Exception as e:
            error_msg = f"语音转录失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def _save_srt(self, result: Dict, output_path: str) -> None:
        """保存为SRT格式"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(result['segments'], 1):
                start_time = self._format_timestamp(segment['start'])
                end_time = self._format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        self.logger.file_created(output_path)
    
    def _format_timestamp(self, seconds: float) -> str:
        """将秒数转换为SRT时间戳格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def _calculate_average_confidence(self, result: Dict) -> float:
        """计算平均置信度"""
        if 'segments' not in result:
            return 0.0
        
        total_confidence = 0.0
        total_words = 0
        
        for segment in result['segments']:
            if 'words' in segment:
                for word in segment['words']:
                    if 'probability' in word:
                        total_confidence += word['probability']
                        total_words += 1
        
        return total_confidence / total_words if total_words > 0 else 0.0
    
    def validate_transcription(self, srt_path: str) -> bool:
        """验证转录结果"""
        return Validator.validate_srt_file(srt_path)[0]

def main(video_path: str, output_dir: str, youtube_url: Optional[str] = None) -> bool:
    """步骤2主函数"""
    try:
        config = Config()
        logger = Logger("step2_transcribe")
        transcriber = AudioTranscriber(config, logger)
        
        logger.step_start(2, "语音转录")
        
        result = transcriber.transcribe_video(video_path, output_dir, youtube_url)
        
        if result['success']:
            logger.step_complete(2, "语音转录")
            logger.info("=" * 50)
            logger.info("步骤2完成，输出文件：")
            logger.info(f"- 英文字幕文件: {result['srt_file']}")
            logger.info(f"- 原始转录结果: {result['raw_result_file']}")
            logger.info(f"- 字幕条数: {result['transcribe_stats']['subtitle_count']}")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤2失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step2_transcribe")
        logger.error(f"步骤2执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python step2_transcribe.py <视频文件路径> <输出目录> [YouTube URL]")
        print("  YouTube URL (可选): 用于启用缓存功能")
        sys.exit(1)
    
    youtube_url = sys.argv[3] if len(sys.argv) > 3 else None
    success = main(sys.argv[1], sys.argv[2], youtube_url)
    sys.exit(0 if success else 1)
