"""
步骤5：生成LLM优化Prompt模块（优化版）
生成中文Prompt，要求将英文文章转换为图文并茂的中文文章
"""
import os
import json
from datetime import datetime
from typing import Dict
import sys
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.validator import Validator


class PromptGenerator:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        
    def generate_prompt(self, markdown_path: str, video_info_path: str, output_path: str) -> Dict:
        """
        生成LLM优化Prompt（中文版本）
        
        Args:
            markdown_path: 英文Markdown文章路径
            video_info_path: 视频信息文件路径
            output_path: 输出Prompt文件路径
            
        Returns:
            Dict: 生成结果信息
        """
        self.logger.info("=" * 60)
        self.logger.info(f"[步骤5开始] 生成中文优化Prompt")
        self.logger.info(f"Markdown文件: {os.path.basename(markdown_path)}")
        self.logger.info(f"输出文件: {output_path}")
        self.logger.info("=" * 60)
        
        prompt_start_time = datetime.now().timestamp()
        
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
            
            # 生成中文Prompt
            prompt_content = self._generate_chinese_prompt(markdown_content, video_info)
            
            # 写入Prompt文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            
            self.logger.file_created(output_path)
            
            # 统计信息
            prompt_stats = {
                'prompt_length': len(prompt_content),
                'video_title': video_info.get('title', 'Unknown'),
                'video_duration': video_info.get('duration', 0),
                'generated_time': datetime.now().isoformat(),
                'output_file': output_path
            }
            
            return {
                'success': True,
                'prompt_file': output_path,
                'prompt_stats': prompt_stats,
                'message': '中文Prompt生成成功'
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
    
    def _generate_chinese_prompt(self, markdown_content: str, video_info: Dict) -> str:
        """
        生成中文Prompt文本（考虑截图去重）
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

## 重要说明：截图智能去重处理
源内容中的截图已经过智能去重处理（基于感知哈希算法）：
- **去重原理**: 使用pHash算法计算图片相似度，汉明距离≤10的截图被视为重复
- **去重策略**: 相邻时间段如果画面相似，会自动复用第一张截图（根节点）
- **累积检测**: 防止连续小变化累积成大变化，确保引用的截图与当前内容确实相似
- **实际情况**: 演讲类视频通常有80-90%的截图是重复的（演讲者静止讲话）

### 对您的影响
1. **多个段落共享截图**: 连续的多个文本段落可能引用同一张截图
2. **内容合并机会**: 这些共享截图的段落通常属于同一个主题或场景
3. **优化建议**: 
   - 将使用相同截图的段落合并为一个逻辑章节
   - 在章节开头放置截图，后面跟随所有相关内容
   - 避免重复引用同一张截图

## 要求
1. **语言**: 生成中文文章（简体中文）
2. **格式**: Markdown格式，包含以下结构：
   - 文章标题
   - 摘要/导言
   - 多个章节（**按截图分组，合并相同截图的内容**）
   - 每个关键点配有对应的截图
   - 总结和要点
3. **图文搭配**: 
   - 在适当位置插入截图（使用Markdown语法）
   - 在截图前后添加解释文字
   - 确保图文结合，提高可读性
   - **智能处理重复截图**: 如果源内容中多个段落使用同一截图，将这些段落整合为一个章节
4. **内容优化**:
   - 简化复杂的英文技术术语
   - 添加上下文和背景信息
   - 保持原视频的核心观点
   - 改进逻辑流程和过渡
   - **合并冗余内容**: 将引用相同截图的相关内容合并，避免重复
5. **质量标准**:
   - 清晰的段落结构
   - 适当的标题层级
   - 中文表达自然流畅
   - 技术术语准确
6. **截图集成**:
   - 从提供的截图库中选择最相关的截图
   - 每张截图应该与周围文本相关联
   - 添加截图说明（中文）
   - **避免截图冗余**: 同一张截图在文章中只出现一次

## 源内容（英文Markdown）
```markdown
{markdown_content}
```

## 输出要求
1. **标题**: 用中文重新表述视频主题
2. **内容**: 完整的中文文章，包含章节标题、段落和截图
3. **截图引用**: 使用Markdown图片语法引用截图文件
4. **长度**: 根据内容确定，保证完整性，但要避免因截图重复导致的内容冗余
5. **风格**: 专业、学术、易懂的表达方式
6. **结构优化**: 将使用相同截图的内容段落合理组织，形成连贯的章节

## 注意事项
- 保持原视频的专业性和准确性
- 使用适当的中文表达方式
- 图片应该清晰且与内容匹配
- 避免过度翻译，确保内容自然
- 提高可读性和用户体验
- **特别注意**: 源内容中的截图重复是正常的技术处理，请在生成文章时智能合并相关内容，创建更精炼、结构更清晰的文章

请开始生成中文文章：
"""
        
        return prompt


def main(markdown_path: str, video_info_path: str, output_path: str) -> bool:
    """步骤5主函数"""
    try:
        config = Config()
        logger = Logger("step5_prompt")
        
        generator = PromptGenerator(config, logger)
        
        logger.step_start(6, "生成中文优化Prompt")
        
        result = generator.generate_prompt(markdown_path, video_info_path, output_path)
        
        if result['success']:
            logger.step_complete(6, "生成中文优化Prompt")
            logger.info("=" * 50)
            logger.info("步骤5完成，输出文件：")
            logger.info(f"- Prompt文件: {result['prompt_file']}")
            logger.info(f"- 文件大小: {result['prompt_stats']['prompt_length']} 字符")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"步骤5失败: {result['error']}")
            return False
            
    except Exception as e:
        logger = Logger("step5_prompt")
        logger.error(f"步骤5执行异常: {str(e)}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python step6_generate_prompt.py <markdown_path> <video_info_path> <output_path>")
        sys.exit(1)
    
    success = main(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if success else 1)
