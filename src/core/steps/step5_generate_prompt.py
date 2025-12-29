"""
步骤5：生成LLM优化Prompt模块（优化版）
生成中文Prompt，要求将英文文章转换为图文并茂的中文文章
支持多模板生成，自动扫描 prompt_template_*.txt 文件
"""
import os
import json
from datetime import datetime
from typing import Dict, List
import sys
import traceback
import glob
import re

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator


class PromptGenerator:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/templates'))
    
    def _scan_template_files(self) -> List[Dict]:
        """
        扫描所有prompt模板文件
        
        Returns:
            list: 模板文件信息列表 [{'identifier': 'v1', 'path': '/path/to/file'}, ...]
        """
        templates = []
        pattern = os.path.join(self.templates_dir, 'prompt_template_*.txt')
        
        self.logger.info(f"扫描模板文件: {pattern}")
        
        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            # 使用正则提取标识符: prompt_template_xxx.txt -> xxx
            match = re.match(r'prompt_template_(.+?)\.txt$', filename)
            if match:
                identifier = match.group(1)
                templates.append({
                    'identifier': identifier,
                    'path': file_path,
                    'filename': filename
                })
                self.logger.info(f"  发现模板: {identifier} ({filename})")
        
        if not templates:
            self.logger.warning("未找到任何 prompt_template_*.txt 模板文件")
        else:
            self.logger.info(f"共找到 {len(templates)} 个模板文件")
        
        return templates
    
    def _read_common_prompt(self) -> str:
        """
        读取公共prompt内容
        
        Returns:
            str: 公共prompt内容，如果文件不存在返回空字符串
        """
        common_file = os.path.join(self.templates_dir, 'common_prompt.txt')
        
        if not os.path.exists(common_file):
            self.logger.warning(f"公共prompt文件不存在: {common_file}")
            return ""
        
        try:
            with open(common_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self.logger.info(f"已读取公共prompt内容 ({len(content)} 字符)")
            return content
        except Exception as e:
            self.logger.error(f"读取公共prompt文件失败: {str(e)}")
            return ""
    
    def _read_template_content(self, template_path: str) -> str:
        """
        读取模板文件内容
        
        Args:
            template_path: 模板文件路径
            
        Returns:
            str: 模板内容
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            self.logger.error(f"读取模板文件失败 {template_path}: {str(e)}")
            raise
    
    def _generate_prompt_from_template(self, common_content: str, template_content: str,
                                      markdown_content: str, video_info: Dict) -> str:
        """
        根据模板生成prompt内容
        
        Args:
            common_content: 公共prompt内容
            template_content: 模板特定内容
            markdown_content: Markdown文章内容
            video_info: 视频信息
            
        Returns:
            str: 完整的prompt内容
        """
        parts = []
        
        # 1. 公共部分（开头）
        if common_content:
            parts.append(common_content)
        
        # 2. 视频信息部分
        title = video_info.get('title', '视频标题未知')
        duration = video_info.get('duration', 0)
        
        video_info_section = f"""
## 源视频信息
- **标题**: {title}
- **时长**: {duration} 秒
- **内容**: 英文技术演讲/教程
"""
        parts.append(video_info_section)
        
        # 3. 模板特定部分
        if template_content:
            parts.append(template_content)
        
        # 4. Markdown内容部分
        markdown_section = f"""
## 源内容（英文Markdown）
```markdown
{markdown_content}
```
"""
        parts.append(markdown_section)
        
        # 5. 结尾提示
        parts.append("\n请开始生成中文文章：\n")
        
        # 拼接所有部分
        return "\n".join(parts)
        
    def generate_prompt(self, markdown_path: str, video_info_path: str, output_dir: str) -> Dict:
        """
        生成LLM优化Prompt（支持多模板）
        
        Args:
            markdown_path: 英文Markdown文章路径
            video_info_path: 视频信息文件路径
            output_dir: 输出目录路径
            
        Returns:
            Dict: 生成结果信息
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤5开始] 生成中文优化Prompt（多模板支持）")
        self.logger.info(f"Markdown文件: {os.path.basename(markdown_path)}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info("=" * 60)
        
        try:
            # 检查输入文件
            markdown_path = os.path.abspath(markdown_path)
            video_info_path = os.path.abspath(video_info_path)
            
            if not os.path.exists(markdown_path):
                raise Exception(f"Markdown文件不存在: {markdown_path}")
            
            if not os.path.exists(video_info_path):
                raise Exception(f"视频信息文件不存在: {video_info_path}")
            
            # 验证Markdown文件
            md_valid, md_msg = Validator.validate_markdown_file(markdown_path)
            if not md_valid:
                self.logger.warning(f"Markdown文件验证警告: {md_msg}")
            
            # 读取视频信息
            self.logger.info("读取视频信息...")
            with open(video_info_path, 'r', encoding='utf-8') as f:
                video_info = json.load(f)
            
            # 读取Markdown内容
            self.logger.info("读取Markdown文章...")
            with open(markdown_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # 扫描模板文件
            templates = self._scan_template_files()
            
            if not templates:
                # 如果没有找到模板，使用默认行为
                self.logger.warning("未找到模板文件，使用默认prompt生成")
                return self._generate_default_prompt(markdown_content, video_info, output_dir)
            
            # 读取公共prompt内容
            common_content = self._read_common_prompt()
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 遍历每个模板生成prompt
            prompt_files = []
            failed_templates = []
            
            for template in templates:
                try:
                    self.logger.info(f"处理模板: {template['identifier']}")
                    
                    # 读取模板内容
                    template_content = self._read_template_content(template['path'])
                    
                    # 生成完整prompt
                    prompt_content = self._generate_prompt_from_template(
                        common_content, template_content, markdown_content, video_info
                    )
                    
                    # 生成输出文件名
                    output_filename = f"optimization_prompt_{template['identifier']}.txt"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # 写入文件
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(prompt_content)
                    
                    self.logger.file_created(output_path)
                    
                    # 记录生成信息
                    prompt_files.append({
                        'template': template['identifier'],
                        'output_file': output_path,
                        'size': len(prompt_content)
                    })
                    
                    self.logger.info(f"  生成成功: {output_filename} ({len(prompt_content)} 字符)")
                    
                except Exception as e:
                    self.logger.error(f"  模板 {template['identifier']} 处理失败: {str(e)}")
                    failed_templates.append({
                        'template': template['identifier'],
                        'error': str(e)
                    })
            
            # 检查是否所有模板都失败了
            if not prompt_files:
                error_msg = "所有模板处理都失败了"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'failed_templates': failed_templates,
                    'message': error_msg
                }
            
            # 返回成功结果
            self.logger.info("=" * 60)
            self.logger.info(f"步骤5完成: 成功生成 {len(prompt_files)} 个Prompt文件")
            for pf in prompt_files:
                self.logger.info(f"  - {pf['template']}: {os.path.basename(pf['output_file'])}")
            if failed_templates:
                self.logger.warning(f"失败的模板数: {len(failed_templates)}")
            self.logger.info("=" * 60)
            
            return {
                'success': True,
                'prompt_files': prompt_files,
                'total_generated': len(prompt_files),
                'failed_templates': failed_templates,
                'message': f'成功生成{len(prompt_files)}个Prompt文件'
            }
            
        except Exception as e:
            error_msg = f"Prompt生成失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def _generate_default_prompt(self, markdown_content: str, video_info: Dict, output_dir: str) -> Dict:
        """
        生成默认prompt（当没有找到模板文件时使用）
        
        Args:
            markdown_content: Markdown内容
            video_info: 视频信息
            output_dir: 输出目录
            
        Returns:
            Dict: 生成结果
        """
        title = video_info.get('title', '视频标题未知')
        duration = video_info.get('duration', 0)
        
        prompt = f"""# 视频转文章 - 中文优化Prompt

## 任务说明
您的任务是将下面提供的英文视频内容转换为一篇专业的、结构清晰的中文文章。文章应该是**图文并茂**的形式，包含截图来说明关键内容。

## 源视频信息
- **标题**: {title}
- **时长**: {duration} 秒
- **内容**: 英文技术演讲/教程

## 要求
1. **语言**: 生成中文文章（简体中文）
2. **格式**: Markdown格式，包含以下结构：
   - 文章标题
   - 摘要/导言
   - 多个章节（按逻辑分组）
   - 每个关键点配有对应的截图
   - 总结和要点
3. **图文搭配**: 
   - 在适当位置插入截图（使用Markdown语法）
   - 在截图前后添加解释文字
   - 确保图文结合，提高可读性
4. **内容优化**:
   - 简化复杂的英文技术术语
   - 添加上下文和背景信息
   - 保持原视频的核心观点
   - 改进逻辑流程和过渡
5. **质量标准**:
   - 清晰的段落结构
   - 适当的标题层级
   - 中文表达自然流畅
   - 技术术语准确
6. **截图集成**:
   - 从提供的截图库中选择最相关的截图
   - 每张截图应该与周围文本相关联
   - 添加截图说明（中文）

## 源内容（英文Markdown）
```markdown
{markdown_content}
```

## 输出要求
1. **标题**: 用中文重新表述视频主题
2. **内容**: 完整的中文文章，包含章节标题、段落和截图
3. **截图引用**: 使用Markdown图片语法引用截图文件
4. **长度**: 根据内容确定，保证完整性
5. **风格**: 专业、学术、易懂的表达方式

## 注意事项
- 保持原视频的专业性和准确性
- 使用适当的中文表达方式
- 图片应该清晰且与内容匹配
- 避免过度翻译，确保内容自然
- 提高可读性和用户体验

请开始生成中文文章：
"""
        
        # 写入默认文件
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'optimization_prompt_default.txt')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        self.logger.file_created(output_path)
        
        return {
            'success': True,
            'prompt_files': [{
                'template': 'default',
                'output_file': output_path,
                'size': len(prompt)
            }],
            'total_generated': 1,
            'message': '使用默认prompt生成成功'
        }


def main(markdown_path: str, video_info_path: str, output_dir: str) -> bool:
    """步骤5主函数"""
    try:
        config = Config()
        logger = Logger("step5_prompt")
        
        generator = PromptGenerator(config, logger)
        
        logger.step_start(5, "生成中文优化Prompt（多模板）")
        
        result = generator.generate_prompt(markdown_path, video_info_path, output_dir)
        
        if result['success']:
            logger.step_complete(5, "生成中文优化Prompt")
            logger.info("=" * 50)
            logger.info(f"步骤5完成，生成了 {result['total_generated']} 个Prompt文件：")
            for pf in result['prompt_files']:
                logger.info(f"  - {pf['template']}: {os.path.basename(pf['output_file'])} ({pf['size']} 字符)")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤5失败: {result.get('error', '未知错误')}")
            return False
            
    except Exception as e:
        logger = Logger("step5_prompt")
        logger.error(f"步骤5执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python step5_generate_prompt.py <markdown_path> <video_info_path> <output_dir>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if success else 1)
