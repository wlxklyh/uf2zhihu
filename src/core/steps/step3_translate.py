"""
步骤3：翻译字幕模块
将英文字幕翻译为中文字幕
"""
from translatepy import Translator
import pysrt
import time
import os
import json
from datetime import datetime
from typing import List, Dict
import sys
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.file_manager import FileManager

class SubtitleTranslator:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.translator = None
        
    def init_translator(self) -> bool:
        """初始化翻译器"""
        try:
            self.translator = Translator()
            self.logger.success("翻译器初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"翻译器初始化失败: {str(e)}")
            return False
        
    def translate_srt(self, input_srt: str, output_srt: str) -> Dict:
        """
        翻译SRT字幕文件
        
        Args:
            input_srt: 输入的英文字幕文件
            output_srt: 输出的中文字幕文件
            
        Returns:
            Dict: 翻译结果统计
        """
        self.logger.info(f"开始翻译字幕: {os.path.basename(input_srt)}")
        
        try:
            # 检查输入文件
            input_srt = os.path.abspath(input_srt)
            if not os.path.exists(input_srt):
                raise Exception(f"字幕文件不存在: {input_srt}")
            
            # 验证输入字幕文件
            is_valid, validation_message, stats = Validator.validate_srt_file(input_srt)
            if not is_valid:
                raise Exception(f"输入字幕文件无效: {validation_message}")
            
            self.logger.info(f"输入字幕验证通过: {stats['subtitle_count']} 条字幕")
            
            # 初始化翻译器
            if not self.init_translator():
                raise Exception("翻译器初始化失败")
            
            # 创建输出目录
            os.makedirs(os.path.dirname(output_srt), exist_ok=True)
            
            # 读取字幕文件
            self.logger.info("正在读取字幕文件...")
            subs = pysrt.open(input_srt, encoding='utf-8')
            
            # 获取配置
            target_language = self.config.get('step3_translate', 'target_language', 'zh-CN')
            batch_size = self.config.get_int('step3_translate', 'batch_size', 10)
            
            self.logger.info(f"开始翻译到 {target_language}，批量大小: {batch_size}")
            
            # 统计信息
            total_subs = len(subs)
            translated_count = 0
            failed_count = 0
            
            # 批量翻译
            for i in range(0, total_subs, batch_size):
                batch_end = min(i + batch_size, total_subs)
                batch_subs = subs[i:batch_end]
                
                self.logger.info(f"翻译批次 {i//batch_size + 1}: {i+1}-{batch_end}/{total_subs}")
                
                # 翻译当前批次
                batch_success = self._translate_batch(batch_subs, target_language)
                translated_count += batch_success
                failed_count += (len(batch_subs) - batch_success)
                
                # 显示进度
                progress = (batch_end / total_subs) * 100
                self.logger.progress(batch_end, total_subs, f"翻译进度")
                
                # 避免API限制，稍微延迟
                if batch_end < total_subs:
                    time.sleep(0.5)
            
            # 保存翻译后的字幕
            self.logger.info("保存翻译后的字幕...")
            subs.save(output_srt, encoding='utf-8')
            self.logger.file_created(output_srt)
            
            # 验证输出文件
            is_valid, validation_message, output_stats = Validator.validate_srt_file(output_srt)
            if not is_valid:
                self.logger.warning(f"输出字幕验证警告: {validation_message}")
            else:
                self.logger.success(f"输出字幕验证通过: {validation_message}")
            
            # 翻译统计
            translation_stats = {
                'total_subtitles': total_subs,
                'translated_successfully': translated_count,
                'translation_failed': failed_count,
                'success_rate': (translated_count / total_subs * 100) if total_subs > 0 else 0,
                'target_language': target_language,
                'input_stats': stats,
                'output_stats': output_stats
            }
            
            self.logger.info(f"翻译完成: {translated_count}/{total_subs} 成功")
            self.logger.info(f"成功率: {translation_stats['success_rate']:.1f}%")
            
            return {
                'success': True,
                'srt_file': output_srt,
                'translation_stats': translation_stats,
                'message': f'翻译成功: {translated_count}/{total_subs} 条字幕'
            }
            
        except Exception as e:
            error_msg = f"字幕翻译失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
        
    def _translate_batch(self, batch_subs: List, target_language: str) -> int:
        """批量翻译文本"""
        success_count = 0
        
        for sub in batch_subs:
            try:
                original_text = sub.text.strip()
                if not original_text:
                    continue
                
                # 执行翻译
                translated = self.translator.translate(original_text, target_language)
                
                if hasattr(translated, 'result'):
                    sub.text = translated.result
                else:
                    sub.text = str(translated)
                
                success_count += 1
                
            except Exception as e:
                self.logger.warning(f"翻译失败: {original_text[:50]}... - {str(e)}")
                # 翻译失败时保留原文
                continue
        
        return success_count
        
    def validate_translation(self, original_srt: str, translated_srt: str) -> bool:
        """验证翻译结果"""
        try:
            # 验证两个文件都有效
            orig_valid, _, orig_stats = Validator.validate_srt_file(original_srt)
            trans_valid, _, trans_stats = Validator.validate_srt_file(translated_srt)
            
            if not orig_valid or not trans_valid:
                return False
            
            # 检查字幕条数是否一致
            if orig_stats['subtitle_count'] != trans_stats['subtitle_count']:
                self.logger.warning("原文和译文的字幕条数不一致")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"翻译验证失败: {str(e)}")
            return False

def main(input_srt: str, output_dir: str) -> bool:
    """步骤3主函数"""
    try:
        config = Config()
        logger = Logger("step3_translate")
        translator = SubtitleTranslator(config, logger)
        
        logger.step_start(3, "字幕翻译")
        
        # 设置输出文件路径
        output_srt = os.path.join(output_dir, 'chinese_subtitles.srt')
        
        result = translator.translate_srt(input_srt, output_srt)
        
        if result['success']:
            logger.step_complete(3, "字幕翻译")
            logger.info("=" * 50)
            logger.info("步骤3完成，输出文件：")
            logger.info(f"- 中文字幕文件: {result['srt_file']}")
            logger.info(f"- 翻译统计: {result['translation_stats']['translated_successfully']}/{result['translation_stats']['total_subtitles']}")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤3失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step3_translate")
        logger.error(f"步骤3执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python step3_translate.py <英文字幕文件路径> <输出目录>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
