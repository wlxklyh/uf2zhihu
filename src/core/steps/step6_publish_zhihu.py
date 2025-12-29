"""
步骤6：发布文章到知乎模块
实现知乎二维码登录和文章发布功能
"""
import os
import json
import re
import time
import base64
import requests
import qrcode
from io import BytesIO
from typing import Dict, List, Optional
from datetime import datetime
import sys
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.utils.config import Config
from src.utils.logger import Logger


class ZhihuPublisher:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.cookie_file = config.get('step6_zhihu', 'cookie_file', './config/zhihu_cookies.json')
        self.qrcode_timeout = config.get_int('step6_zhihu', 'qrcode_timeout', 300)
        self.login_poll_interval = config.get_int('step6_zhihu', 'login_poll_interval', 2)
        self.image_upload_timeout = config.get_int('step6_zhihu', 'image_upload_timeout', 30)
        self.publish_timeout = config.get_int('step6_zhihu', 'publish_timeout', 60)
        
        # 确保 cookie 文件目录存在
        cookie_dir = os.path.dirname(self.cookie_file)
        if cookie_dir and not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir, exist_ok=True)
        
        # 初始化 session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.zhihu.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })
        
        # 加载已保存的 cookie
        self._load_cookies()
    
    def _load_cookies(self) -> bool:
        """加载已保存的 cookie"""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies_dict = json.load(f)
                    self.session.cookies.update(cookies_dict)
                    self.logger.info("已加载保存的 cookie")
                    return True
        except Exception as e:
            self.logger.warning(f"加载 cookie 失败: {str(e)}")
        return False
    
    def save_cookies(self, cookies: Dict) -> bool:
        """保存 cookie 到文件"""
        try:
            cookies_dict = {}
            if isinstance(cookies, dict):
                cookies_dict = cookies
            elif hasattr(cookies, 'get_dict'):
                cookies_dict = cookies.get_dict()
            else:
                # 从 session 中获取
                cookies_dict = self.session.cookies.get_dict()
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, ensure_ascii=False, indent=2)
            
            self.logger.success(f"Cookie 已保存到: {self.cookie_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存 cookie 失败: {str(e)}")
            return False
    
    def get_qrcode(self) -> Dict:
        """
        获取知乎登录二维码
        
        Returns:
            Dict: 包含 qrcode_token, qrcode_url, qrcode_image_base64
        """
        try:
            self.logger.info("正在获取知乎登录二维码...")
            
            # 获取二维码 token
            qrcode_url = "https://www.zhihu.com/api/v3/oauth/qr_code"
            params = {
                'client_id': 'c3cef7c66a1843f8b3a9e6a1e3160e20',
                'response_type': 'code',
                'scope': 'read,write'
            }
            
            response = self.session.get(qrcode_url, params=params, timeout=10)
            
            if response.status_code != 200:
                raise Exception(f"获取二维码失败，状态码: {response.status_code}")
            
            data = response.json()
            qrcode_token = data.get('token', '')
            qrcode_image_url = data.get('qrcode_url', '')
            
            if not qrcode_token:
                raise Exception("未能获取二维码 token")
            
            # 生成二维码图片
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qrcode_image_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qrcode_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            self.logger.success(f"二维码获取成功，token: {qrcode_token[:20]}...")
            
            return {
                'success': True,
                'qrcode_token': qrcode_token,
                'qrcode_url': qrcode_image_url,
                'qrcode_image_base64': f"data:image/png;base64,{qrcode_image_base64}",
                'message': '二维码获取成功'
            }
            
        except Exception as e:
            error_msg = f"获取二维码失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def check_login_status(self, qrcode_token: str) -> Dict:
        """
        检查登录状态
        
        Args:
            qrcode_token: 二维码 token
            
        Returns:
            Dict: 登录状态信息
        """
        try:
            check_url = f"https://www.zhihu.com/api/v3/oauth/qr_code/{qrcode_token}/scan_info"
            
            response = self.session.get(check_url, timeout=10)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'status': 'error',
                    'message': f'检查登录状态失败，状态码: {response.status_code}'
                }
            
            data = response.json()
            status = data.get('status', '')
            
            if status == 'login':
                # 登录成功，保存 cookie
                cookies = self.session.cookies.get_dict()
                self.save_cookies(cookies)
                
                return {
                    'success': True,
                    'status': 'login',
                    'message': '登录成功',
                    'cookies': cookies
                }
            elif status == 'scan':
                return {
                    'success': True,
                    'status': 'scan',
                    'message': '等待扫码'
                }
            elif status == 'cancel':
                return {
                    'success': False,
                    'status': 'cancel',
                    'message': '用户取消登录'
                }
            else:
                return {
                    'success': True,
                    'status': status,
                    'message': f'状态: {status}'
                }
                
        except Exception as e:
            error_msg = f"检查登录状态失败: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'status': 'error',
                'message': error_msg
            }
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            # 尝试访问需要登录的页面
            test_url = "https://www.zhihu.com/api/v4/me"
            response = self.session.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('id'):
                    self.logger.info("已登录状态验证成功")
                    return True
            
            return False
        except Exception as e:
            self.logger.warning(f"检查登录状态失败: {str(e)}")
            return False
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片到知乎图床
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            str: 图片 URL，失败返回 None
        """
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"图片文件不存在: {image_path}")
                return None
            
            self.logger.info(f"正在上传图片: {os.path.basename(image_path)}")
            
            # 知乎图片上传 API
            upload_url = "https://www.zhihu.com/api/v4/uploaded_images"
            
            with open(image_path, 'rb') as f:
                files = {
                    'image': (os.path.basename(image_path), f, 'image/png')
                }
                
                response = self.session.post(
                    upload_url,
                    files=files,
                    timeout=self.image_upload_timeout
                )
            
            if response.status_code == 200:
                data = response.json()
                image_url = data.get('url', '')
                if image_url:
                    self.logger.success(f"图片上传成功: {image_url}")
                    return image_url
                else:
                    self.logger.error(f"上传成功但未获取到图片 URL: {data}")
                    return None
            else:
                self.logger.error(f"图片上传失败，状态码: {response.status_code}, 响应: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"上传图片异常: {str(e)}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    def convert_markdown_to_zhihu(self, markdown_path: str, project_path: str) -> Dict:
        """
        将 Markdown 转换为知乎格式
        
        Args:
            markdown_path: Markdown 文件路径
            project_path: 项目路径（用于解析相对路径的图片）
            
        Returns:
            Dict: 转换后的内容和图片映射
        """
        try:
            if not os.path.exists(markdown_path):
                raise Exception(f"Markdown 文件不存在: {markdown_path}")
            
            self.logger.info(f"开始转换 Markdown: {os.path.basename(markdown_path)}")
            
            # 读取 Markdown 内容
            with open(markdown_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # 提取所有图片
            image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
            images = re.findall(image_pattern, markdown_content)
            
            # 上传图片并替换 URL
            image_map = {}  # 原路径 -> 新 URL
            zhihu_content = markdown_content
            
            for alt_text, image_path in images:
                # 处理相对路径
                if not os.path.isabs(image_path):
                    # 尝试多个可能的路径
                    possible_paths = [
                        os.path.join(project_path, image_path),
                        os.path.join(project_path, 'step3_screenshots', 'screenshots', os.path.basename(image_path)),
                        os.path.join(os.path.dirname(markdown_path), image_path)
                    ]
                    
                    actual_path = None
                    for path in possible_paths:
                        if os.path.exists(path):
                            actual_path = path
                            break
                else:
                    actual_path = image_path
                
                if actual_path and os.path.exists(actual_path):
                    # 上传图片
                    uploaded_url = self.upload_image(actual_path)
                    if uploaded_url:
                        image_map[image_path] = uploaded_url
                        # 替换 Markdown 中的图片链接
                        zhihu_content = zhihu_content.replace(
                            f'![{alt_text}]({image_path})',
                            f'<img src="{uploaded_url}" data-caption="{alt_text}" data-size="normal" data-watermark="watermark" data-original-src="{uploaded_url}" data-watermark-src="" data-private-watermark-src=""/>'
                        )
                    else:
                        self.logger.warning(f"图片上传失败，保留原路径: {image_path}")
                else:
                    self.logger.warning(f"图片文件不存在: {image_path}")
            
            # 转换标题格式（知乎限制）
            # # -> <h2>, ## -> <h3>, ### -> <strong>
            zhihu_content = re.sub(r'^# (.+)$', r'<h2>\1</h2>', zhihu_content, flags=re.MULTILINE)
            zhihu_content = re.sub(r'^## (.+)$', r'<h3>\1</h3>', zhihu_content, flags=re.MULTILINE)
            zhihu_content = re.sub(r'^### (.+)$', r'<strong>\1</strong><br>', zhihu_content, flags=re.MULTILINE)
            
            # 转换代码块
            code_block_pattern = r'```(\w+)?\n(.*?)```'
            def replace_code_block(match):
                lang = match.group(1) or ''
                code = match.group(2)
                return f'<pre><code class="language-{lang}">{code}</code></pre>'
            zhihu_content = re.sub(code_block_pattern, replace_code_block, zhihu_content, flags=re.DOTALL)
            
            # 转换行内代码
            zhihu_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', zhihu_content)
            
            # 转换粗体和斜体
            zhihu_content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', zhihu_content)
            zhihu_content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', zhihu_content)
            
            # 转换链接
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            zhihu_content = re.sub(link_pattern, r'<a href="\2">\1</a>', zhihu_content)
            
            # 转换段落（空行分隔）
            paragraphs = zhihu_content.split('\n\n')
            zhihu_content = '\n'.join([f'<p>{p.strip()}</p>' if p.strip() and not p.strip().startswith('<') else p for p in paragraphs])
            
            self.logger.success(f"Markdown 转换完成，上传了 {len(image_map)} 张图片")
            
            return {
                'success': True,
                'content': zhihu_content,
                'image_map': image_map,
                'original_length': len(markdown_content),
                'converted_length': len(zhihu_content),
                'images_uploaded': len(image_map)
            }
            
        except Exception as e:
            error_msg = f"Markdown 转换失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def publish_article(self, title: str, content: str, topics: List[str] = None) -> Dict:
        """
        发布文章到知乎
        
        Args:
            title: 文章标题
            content: 文章内容（HTML 格式）
            topics: 话题列表
            
        Returns:
            Dict: 发布结果
        """
        try:
            if not self.is_logged_in():
                return {
                    'success': False,
                    'error': '未登录，请先登录',
                    'message': '未登录，请先登录'
                }
            
            self.logger.info(f"正在发布文章: {title}")
            
            # 知乎发布文章 API
            publish_url = "https://zhuanlan.zhihu.com/api/articles"
            
            # 准备发布数据
            publish_data = {
                'title': title,
                'content': content,
                'summary': title[:100],  # 摘要
                'can_comment': True,
                'comment_permission': 'all',
                'type': 'article'
            }
            
            # 添加话题
            if topics:
                publish_data['topics'] = topics
            
            response = self.session.post(
                publish_url,
                json=publish_data,
                timeout=self.publish_timeout
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                article_id = data.get('id', '')
                article_url = data.get('url', f"https://zhuanlan.zhihu.com/p/{article_id}")
                
                self.logger.success(f"文章发布成功: {article_url}")
                
                return {
                    'success': True,
                    'article_id': article_id,
                    'article_url': article_url,
                    'message': '文章发布成功'
                }
            else:
                error_msg = f"发布失败，状态码: {response.status_code}, 响应: {response.text}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'message': error_msg
                }
                
        except Exception as e:
            error_msg = f"发布文章异常: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': error_msg
            }
    
    def list_finaloutput_files(self, project_path: str) -> List[Dict]:
        """
        列出 FinalOutput 目录下的 .md 文件
        
        Args:
            project_path: 项目路径
            
        Returns:
            List[Dict]: 文件信息列表
        """
        try:
            finaloutput_dir = os.path.join(project_path, 'FinalOutput')
            
            if not os.path.exists(finaloutput_dir):
                return []
            
            files = []
            for item in os.listdir(finaloutput_dir):
                item_path = os.path.join(finaloutput_dir, item)
                if os.path.isfile(item_path) and item.lower().endswith('.md'):
                    file_info = {
                        'name': item,
                        'path': item_path,
                        'size': os.path.getsize(item_path),
                        'modified_time': datetime.fromtimestamp(
                            os.path.getmtime(item_path)
                        ).isoformat()
                    }
                    files.append(file_info)
            
            # 按修改时间排序
            files.sort(key=lambda x: x['modified_time'], reverse=True)
            return files
            
        except Exception as e:
            self.logger.error(f"列出 FinalOutput 文件失败: {str(e)}")
            return []


def main():
    """测试函数"""
    try:
        config = Config()
        logger = Logger("step6_zhihu")
        
        publisher = ZhihuPublisher(config, logger)
        
        # 测试获取二维码
        result = publisher.get_qrcode()
        if result['success']:
            logger.info(f"二维码获取成功: {result['qrcode_token']}")
        else:
            logger.error(f"二维码获取失败: {result['error']}")
            
    except Exception as e:
        logger = Logger("step6_zhihu")
        logger.error(f"测试失败: {str(e)}")


if __name__ == "__main__":
    main()



