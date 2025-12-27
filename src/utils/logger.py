"""
日志系统模块
"""
import logging
import os
from datetime import datetime
from typing import Optional
from colorama import init, Fore, Back, Style

# 初始化colorama
init()

class Logger:
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        # 创建日志目录
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 创建logger
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器
        logger.handlers.clear()
        
        # 创建文件处理器
        log_filename = f"{self.log_dir}/{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # 设置格式器
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def debug(self, message: str) -> None:
        """记录调试日志"""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """记录信息日志"""
        colored_message = f"{Fore.BLUE}[INFO] {message}{Style.RESET_ALL}"
        self.logger.info(message)
        # 直接打印带颜色的消息到控制台
        print(colored_message)
    
    def success(self, message: str) -> None:
        """记录成功日志"""
        colored_message = f"{Fore.GREEN}[SUCCESS] {message}{Style.RESET_ALL}"
        self.logger.info(f"SUCCESS: {message}")
        print(colored_message)
    
    def warning(self, message: str) -> None:
        """记录警告日志"""
        colored_message = f"{Fore.YELLOW}[WARNING] {message}{Style.RESET_ALL}"
        self.logger.warning(message)
        print(colored_message)
    
    def error(self, message: str, exc_info: bool = False) -> None:
        """记录错误日志"""
        colored_message = f"{Fore.RED}[ERROR] {message}{Style.RESET_ALL}"
        self.logger.error(message, exc_info=exc_info)
        print(colored_message)
    
    def critical(self, message: str) -> None:
        """记录严重错误日志"""
        colored_message = f"{Back.RED}{Fore.WHITE}[CRITICAL] {message}{Style.RESET_ALL}"
        self.logger.critical(message)
        print(colored_message)
    
    def progress(self, current: int, total: int, message: str = "") -> None:
        """记录进度信息"""
        try:
            percentage = (current / total) * 100 if total > 0 else 0
            progress_bar = self._create_progress_bar(percentage)
            progress_message = f"{progress_bar} {current}/{total} ({percentage:.1f}%) {message}"
            colored_message = f"{Fore.CYAN}{progress_message}{Style.RESET_ALL}"
            print(f"\r{colored_message}", end="", flush=True)
            
            if current >= total:
                print()  # 换行
        except UnicodeEncodeError:
            # 如果编码失败，使用简单的进度显示
            percentage = (current / total) * 100 if total > 0 else 0
            simple_message = f"Progress: {current}/{total} ({percentage:.1f}%) {message}"
            print(f"\r{simple_message}", end="", flush=True)
            if current >= total:
                print()
    
    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """创建进度条"""
        filled = int(width * percentage / 100)
        bar = "=" * filled + "-" * (width - filled)
        return f"[{bar}]"
    
    def step_start(self, step_num: int, step_name: str) -> None:
        """记录步骤开始"""
        message = f"开始执行步骤 {step_num}: {step_name}"
        colored_message = f"{Fore.MAGENTA}[STEP START] {message}{Style.RESET_ALL}"
        self.logger.info(message)
        print(f"\n{colored_message}")
        print("-" * 50)
    
    def step_complete(self, step_num: int, step_name: str) -> None:
        """记录步骤完成"""
        message = f"步骤 {step_num} 完成: {step_name}"
        colored_message = f"{Fore.GREEN}[STEP COMPLETE] {message}{Style.RESET_ALL}"
        self.logger.info(message)
        print(f"{colored_message}")
        print("-" * 50)
    
    def file_created(self, file_path: str) -> None:
        """记录文件创建"""
        message = f"文件已创建: {file_path}"
        colored_message = f"{Fore.GREEN}[FILE] {message}{Style.RESET_ALL}"
        self.logger.info(message)
        print(colored_message)
