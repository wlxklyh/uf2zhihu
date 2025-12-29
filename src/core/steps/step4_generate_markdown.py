"""
步骤4：生成Markdown文章模块
根据中文字幕和截图生成Markdown文章
"""
import os
import json
import pysrt
from datetime import datetime
from typing import Dict, List
from jinja2 import Template, FileSystemLoader, Environment
import sys
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator
from src.utils.file_manager import FileManager

class MarkdownGenerator:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.template = None
        
    def load_template(self) -> bool:
        """加载Markdown模板"""
        try:
            template_file = self.config.get('step4_markdown', 'template_file', 'templates/markdown_template.md')
            template_path = os.path.join('config', template_file)
            
            if not os.path.exists(template_path):
                raise Exception(f"模板文件不存在: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            self.template = Template(template_content)
            self.logger.success(f"模板加载成功: {template_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"模板加载失败: {str(e)}")
            return False
        
    def generate_markdown(self, srt_path: str, screenshots_dir: str, 
                         video_info_path: str, output_path: str) -> Dict:
        """
        生成英文Markdown文章（图文并茂）
        
        Args:
            srt_path: 英文字幕文件路径
            screenshots_dir: 截图目录路径
            video_info_path: 视频信息文件路径
            output_path: 输出Markdown文件路径
            
        Returns:
            Dict: 生成结果信息
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤4开始] 生成英文Markdown文章（图文并茂）")
        self.logger.info(f"字幕文件: {os.path.basename(srt_path)}")
        self.logger.info(f"截图目录: {screenshots_dir}")
        self.logger.info(f"输出文件: {output_path}")
        self.logger.info("=" * 60)
        
        markdown_start_time = datetime.now().timestamp()
        
        try:
            # 检查输入文件
            srt_path = os.path.abspath(srt_path)
            screenshots_dir = os.path.abspath(screenshots_dir)
            video_info_path = os.path.abspath(video_info_path)
            
            if not os.path.exists(srt_path):
                raise Exception(f"字幕文件不存在: {srt_path}")
            
            if not os.path.exists(screenshots_dir):
                raise Exception(f"截图目录不存在: {screenshots_dir}")
            
            if not os.path.exists(video_info_path):
                raise Exception(f"视频信息文件不存在: {video_info_path}")
            
            # 验证字幕文件
            srt_valid, srt_msg, srt_stats = Validator.validate_srt_file(srt_path)
            if not srt_valid:
                raise Exception(f"字幕文件验证失败: {srt_msg}")
            
            # 加载模板
            if not self.load_template():
                raise Exception("模板加载失败")
            
            # 读取视频信息
            self.logger.info("读取视频信息...")
            with open(video_info_path, 'r', encoding='utf-8') as f:
                video_info = json.load(f)
            
            # 读取字幕
            self.logger.info("读取字幕文件...")
            subs = pysrt.open(srt_path, encoding='utf-8')
            
            # 准备内容数据
            content_items = self._prepare_content_data(subs, screenshots_dir)
            
            # 准备模板数据
            template_data = {
                'title': video_info.get('title', 'YouTube视频文章'),
                'video_url': video_info.get('url', ''),
                'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'duration': self._format_duration(video_info.get('duration', 0)),
                'subtitle_count': len(subs),
                'screenshot_count': len(content_items) * len(self.config.get_float_list('step3_screenshots', 'time_offsets')),
                'content_items': content_items
            }
            
            self.logger.info(f"准备生成文章: {len(content_items)} 个内容块")
            
            # 生成Markdown内容
            markdown_content = self.template.render(**template_data)
            
            # 保存文章
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            self.logger.file_created(output_path)
            
            # 验证生成的文章
            md_valid, md_msg = Validator.validate_markdown_file(output_path)
            if not md_valid:
                self.logger.warning(f"Markdown文件验证警告: {md_msg}")
            else:
                self.logger.success(f"Markdown文件验证通过: {md_msg}")
            
            # 生成统计
            generation_stats = {
                'input_subtitles': len(subs),
                'content_blocks': len(content_items),
                'article_length': len(markdown_content),
                'article_lines': len(markdown_content.split('\n')),
                'has_images': '![' in markdown_content,
                'template_data': template_data
            }
            
            self.logger.info(f"文章生成完成: {generation_stats['article_length']} 字符")
            self.logger.info(f"内容块数: {generation_stats['content_blocks']}")
            
            return {
                'success': True,
                'markdown_file': output_path,
                'generation_stats': generation_stats,
                'message': f'Markdown文章生成成功: {generation_stats["content_blocks"]} 个内容块'
            }
            
        except Exception as e:
            error_msg = f"Markdown生成失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
        
    def _prepare_content_data(self, subs: pysrt.SubRipFile, screenshots_dir: str) -> List[Dict]:
        """准备内容数据（支持去重）"""
        content_items = []
        
        # 读取截图索引文件以获取去重信息
        index_file = os.path.join(os.path.dirname(screenshots_dir), 'screenshot_index.json')
        screenshot_index = {}
        
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    # 建立subtitle_index到截图信息的映射
                    for item in index_data:
                        screenshot_index[item['subtitle_index']] = item
            except Exception as e:
                self.logger.warning(f"读取截图索引失败: {str(e)}")
        
        for i, sub in enumerate(subs, 1):
            # 计算时间
            start_time = self._format_srt_time(sub.start)
            end_time = self._format_srt_time(sub.end)
            
            # 从索引中获取截图信息
            screenshot_info = screenshot_index.get(i, {})
            is_duplicate = screenshot_info.get('is_duplicate', False)
            
            if is_duplicate:
                # 使用引用的截图
                reference_filename = screenshot_info.get('reference_screenshot')
                duplicate_of_index = screenshot_info.get('duplicate_of_index')
                hamming_distance = screenshot_info.get('hamming_distance', 0)
                
                if reference_filename:
                    screenshot_filename = reference_filename
                    screenshot_path = os.path.join(screenshots_dir, reference_filename)
                else:
                    # 降级处理
                    screenshot_filename = f"{i:03d}_plus0.0s.png"
                    screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
            else:
                # 查找对应的截图（使用0s偏移的截图）
                possible_names = [
                    f"{i:03d}_0.0s.png",
                    f"{i:03d}_plus0.0s.png",
                    f"{i:03d}_0s.png"
                ]
                
                screenshot_filename = None
                screenshot_path = None
                
                for name in possible_names:
                    path = os.path.join(screenshots_dir, name)
                    if os.path.exists(path):
                        screenshot_filename = name
                        screenshot_path = path
                        break
                
                # 如果找不到，使用默认名称
                if not screenshot_filename:
                    screenshot_filename = f"{i:03d}_plus0.0s.png"
                    screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
            
            # 使用相对路径
            relative_screenshot_path = f"screenshots/{screenshot_filename}"
            
            content_item = {
                'index': i,
                'start_time': start_time,
                'end_time': end_time,
                'text': sub.text.strip(),
                'screenshot_path': relative_screenshot_path,
                'screenshot_exists': screenshot_path is not None and os.path.exists(screenshot_path),
                'is_duplicate': is_duplicate,
                'duplicate_of_index': screenshot_info.get('duplicate_of_index') if is_duplicate else None,
                'hamming_distance': screenshot_info.get('hamming_distance') if is_duplicate else None
            }
            
            content_items.append(content_item)
        
        return content_items
    
    def _format_srt_time(self, srt_time) -> str:
        """格式化SRT时间为可读格式"""
        return f"{srt_time.hours:02d}:{srt_time.minutes:02d}:{srt_time.seconds:02d}"
    
    def _format_duration(self, seconds: int) -> str:
        """格式化视频时长"""
        if seconds <= 0:
            return "未知"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}小时{minutes}分{secs}秒"
        elif minutes > 0:
            return f"{minutes}分{secs}秒"
        else:
            return f"{secs}秒"
        
    def validate_markdown(self, output_path: str) -> bool:
        """验证生成的Markdown文件"""
        return Validator.validate_markdown_file(output_path)[0]

def main(srt_path: str, screenshots_dir: str, video_info_path: str, output_path: str) -> bool:
    """步骤4主函数"""
    try:
        config = Config()
        logger = Logger("step4_markdown")
        generator = MarkdownGenerator(config, logger)
        
        logger.step_start(5, "Markdown文章生成")
        
        result = generator.generate_markdown(srt_path, screenshots_dir, video_info_path, output_path)
        
        if result['success']:
            logger.step_complete(5, "Markdown文章生成")
            logger.info("=" * 50)
            logger.info("步骤4完成，输出文件：")
            logger.info(f"- Markdown文件: {result['markdown_file']}")
            logger.info(f"- 内容块数: {result['generation_stats']['content_blocks']}")
            logger.info(f"- 文章长度: {result['generation_stats']['article_length']} 字符")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤4失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step4_markdown")
        logger.error(f"步骤4执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python step5_generate_markdown.py <字幕文件> <截图目录> <视频信息文件> <输出文件>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    sys.exit(0 if success else 1)
