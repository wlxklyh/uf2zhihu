"""
步骤2：语音转录模块
使用OpenAI Whisper将视频转录为英文字幕
"""
import whisper
import os
import json
import subprocess
from datetime import datetime
from typing import Dict, Optional
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
        
    def load_model(self) -> bool:
        """加载Whisper模型"""
        try:
            model_name = self.config.get('step2_transcribe', 'model', 'base')
            self.logger.info(f"正在加载Whisper模型: {model_name}")
            
            self.model = whisper.load_model(model_name)
            self.logger.success(f"Whisper模型加载成功: {model_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Whisper模型加载失败: {str(e)}")
            return False
        
    def transcribe_video(self, video_path: str, output_dir: str) -> Dict:
        """
        转录视频音频为英文字幕
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            
        Returns:
            Dict: 转录结果信息
        """
        self.logger.info(f"开始转录视频: {os.path.basename(video_path)}")
        
        try:
            # 标准化路径
            video_path = os.path.abspath(video_path)
            
            # 检查输入文件
            if not os.path.exists(video_path):
                # 尝试列出目录内容来调试
                video_dir = os.path.dirname(video_path)
                if os.path.exists(video_dir):
                    files = os.listdir(video_dir)
                    self.logger.info(f"目录 {video_dir} 中的文件: {files}")
                raise Exception(f"视频文件不存在: {video_path}")
            
            # 验证视频文件
            is_valid, validation_message = Validator.validate_video_file(video_path)
            if not is_valid:
                raise Exception(f"视频文件验证失败: {validation_message}")
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 加载Whisper模型
            if not self.load_model():
                raise Exception("Whisper模型加载失败")
            
            # 开始转录
            self.logger.info("开始语音转录，这可能需要几分钟...")
            
            # 获取配置
            language = self.config.get('step2_transcribe', 'language', 'en')
            
            # 执行转录
            result = self.model.transcribe(
                video_path,
                language=language,
                verbose=True,  # 显示详细进度
                word_timestamps=True  # 包含单词级时间戳
            )
            
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

def main(video_path: str, output_dir: str) -> bool:
    """步骤2主函数"""
    try:
        config = Config()
        logger = Logger("step2_transcribe")
        transcriber = AudioTranscriber(config, logger)
        
        logger.step_start(2, "语音转录")
        
        result = transcriber.transcribe_video(video_path, output_dir)
        
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
    if len(sys.argv) != 3:
        print("用法: python step2_transcribe.py <视频文件路径> <输出目录>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
