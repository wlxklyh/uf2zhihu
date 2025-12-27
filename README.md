# YouTube转文章工具

一个将YouTube视频转换为带截图的中文文章的工具，支持Web界面操作。

## 功能特色

- 🎥 **视频下载**: 高质量下载YouTube视频
- 🎤 **语音转录**: AI自动生成英文字幕
- 📸 **精准截图**: 按时间点提取关键截图
- 📝 **文章生成**: 生成图文并茂的Markdown文章
- 🤖 **AI优化**: 生成LLM优化提示文件

## 快速开始

### 方法一：使用批处理文件（推荐）

1. **首次使用 - 安装依赖**
   ```
   双击 install.bat
   ```

2. **启动应用**
   ```
   双击 start.bat      # 完整版启动（推荐）
   或
   双击 quick_start.bat # 快速启动
   ```

3. **使用工具**
   - 浏览器会自动打开 http://localhost:5000
   - 输入YouTube视频链接
   - 点击"开始处理"
   - 等待处理完成

### 方法二：命令行启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动Web界面
python run_web.py
```

## 系统要求

- Windows 10/11
- Python 3.8+
- 网络连接（用于下载视频和翻译）
- 约2GB可用磁盘空间

## 处理流程

1. **步骤1**: 下载YouTube视频 → `projects/[项目名]/step1_download/`
2. **步骤2**: 语音转录为英文字幕 → `projects/[项目名]/step2_transcribe/`
3. **步骤3**: 提取视频截图 → `projects/[项目名]/step4_screenshots/`
4. **步骤4**: 生成Markdown文章 → `projects/[项目名]/step5_markdown/`
5. **步骤5**: 生成优化提示 → `projects/[项目名]/step6_prompt/`

## 文件结构

```
youtube_to_article/
├── start.bat              # 完整启动脚本
├── quick_start.bat         # 快速启动脚本
├── install.bat            # 依赖安装脚本
├── run_web.py             # Web应用启动器
├── config/
│   ├── config.ini         # 主配置文件
│   └── templates/         # 模板文件
├── projects/              # 项目输出目录
├── src/                   # 源代码
├── logs/                  # 日志文件
└── temp/                  # 临时文件
```

## 配置说明

编辑 `config/config.ini` 可以修改：

- 截图时间偏移: `time_offsets = -0.2,0.0,0.2`
- 翻译服务: `translation_service = translatepy`
- Whisper模型: `model = base`
- 输出目录: `output_dir = ./projects`

## 常见问题

**Q: 启动失败怎么办？**
A: 
1. 确保已安装Python 3.8+
2. 运行 `install.bat` 安装依赖
3. 检查网络连接

**Q: 处理很慢怎么办？**
A: 
- 处理时间取决于视频长度
- Whisper转录需要较长时间
- 可以在配置中选择更快的模型

**Q: 如何查看处理结果？**
A: 
- 每个步骤都有独立的输出目录
- 在Web界面中可以预览文件
- 最终文章在 `step5_markdown/article.md`

**Q: 支持哪些YouTube链接格式？**
A: 
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`

## 技术栈

- **后端**: Python, Flask, SocketIO
- **前端**: Bootstrap, JavaScript
- **AI**: OpenAI Whisper, TranslatePy
- **视频处理**: yt-dlp, FFmpeg

## 注意事项

- 请遵守YouTube的使用条款
- 仅用于个人学习和研究目的
- 处理大文件时请确保有足够的磁盘空间
- 首次运行Whisper会下载模型文件

## 更新日志

### v1.0.0
- 初始版本发布
- 支持完整的视频转文章流程
- Web界面操作
- 批处理文件启动

---

如有问题或建议，请联系技术支持。
