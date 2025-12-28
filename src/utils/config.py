"""
配置管理模块
"""
import configparser
import os
from typing import Dict, Any, List

class Config:
    def __init__(self, config_path: str = "config/config.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        self.config.read(self.config_path, encoding='utf-8')
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """获取配置值"""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """获取整数类型的配置值"""
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """获取浮点数类型的配置值"""
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_boolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """获取布尔类型的配置值"""
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_list(self, section: str, key: str, separator: str = ',') -> List[str]:
        """获取列表类型的配置值"""
        value = self.get(section, key, "")
        if not value:
            return []
        return [item.strip() for item in value.split(separator)]
    
    def get_float_list(self, section: str, key: str, separator: str = ',') -> List[float]:
        """获取浮点数列表类型的配置值"""
        str_list = self.get_list(section, key, separator)
        try:
            return [float(item) for item in str_list]
        except ValueError:
            return []
    
    def validate_config(self) -> bool:
        """验证配置文件完整性"""
        required_sections = ['basic', 'step1_download', 'step2_transcribe', 
                           'step3_screenshots', 
                           'step4_markdown', 'step5_prompt', 'web']
        
        for section in required_sections:
            if not self.config.has_section(section):
                print(f"缺少配置节: {section}")
                return False
        
        return True
    
    def get_all_sections(self) -> List[str]:
        """获取所有配置节"""
        return self.config.sections()
    
    def get_section_items(self, section: str) -> Dict[str, str]:
        """获取指定节的所有配置项"""
        if not self.config.has_section(section):
            return {}
        return dict(self.config.items(section))
