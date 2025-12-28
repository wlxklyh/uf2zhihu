#!/usr/bin/env python3
"""
YouTube转文章工具 - Web UI启动脚本
"""
import os
import sys
from src.web.app import create_app
from src.utils.config import Config
from src.utils.logger import Logger

def main():
    """启动Web应用"""
    # 初始化日志
    logger = Logger("web_startup")
    
    try:
        # 加载配置
        config = Config()
        if not config.validate_config():
            logger.error("配置文件验证失败，请检查 config/config.ini")
            return False
        
        # 创建Flask应用
        app = create_app()
        
        # 获取配置
        host = config.get('web', 'host', '0.0.0.0')
        port = config.get_int('web', 'port', 5000)
        debug = config.get_boolean('web', 'debug', True)
        
        print("=" * 60)
        print("YouTube转文章工具 Web界面")
        print("=" * 60)
        logger.info("正在启动Web服务...")
        logger.info(f"Web界面地址: http://localhost:{port}")
        logger.info(f"配置文件: config/config.ini")
        logger.info(f"输出目录: {config.get('basic', 'output_dir')}")
        logger.info(f"临时目录: {config.get('basic', 'temp_dir')}")
        print("=" * 60)
        print()
        logger.info("提示：")
        logger.info("- 在浏览器中打开上述地址开始使用")
        logger.info("- 按 Ctrl+C 停止服务")
        logger.info("- 所有项目文件将保存在 projects/ 目录中")
        print()
        
        # 启动Flask应用
        logger.success("Web服务启动成功！")
        app.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭服务...")
        return True
    except Exception as e:
        logger.error(f"启动失败: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
