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
        生成中文Prompt文本（优化版）
        """
        title = video_info.get('title', '视频标题未知')
        duration = video_info.get('duration', 0)
        
        prompt = f"""# 视频转中文文章任务

## 源视频
- 标题: {title}
- 时长: {duration} 秒

## 任务目标
将下面的英文视频内容转换为专业的中文文章。

## 核心要求
1. **语言与格式**: 使用简体中文，Markdown格式
2. **内容优化**: 
   - 合并相关字幕，形成连贯段落（避免逐句翻译）
   - 筛选关键截图，删除重复或相似的图片
   - 每个段落配1-2张最具代表性的截图
3. **文章结构**: 
   - 清晰的标题和章节划分
   - 图文结合，截图前后添加说明文字

## 输出要求
生成完整的中文Markdown文章，包含：
- 文章标题和摘要
- 多个逻辑清晰的章节
- 精选的关键截图（使用相对路径引用）

**输出目录结构说明**：
生成的文章应放在项目的 `FinalOutput/` 目录中：
```
FinalOutput/
├── article_cn.md          (中文文章)
└── screenshots/           (用到的截图文件)
    ├── key_screenshot_01.png
    ├── key_screenshot_02.png
    └── ...
```

## 源内容（英文Markdown）
```markdown
{markdown_content}
```

---
请开始生成优化后的中文文章。
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
