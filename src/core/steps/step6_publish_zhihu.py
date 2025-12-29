"""
步骤6：发布文章到知乎模块
实现知乎二维码登录和文章发布功能
"""
import os
import json
import re
import time
import base64
import hashlib
import uuid
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
        self.user_agent = config.get('step6_zhihu', 'user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.enable_draft_mode = config.get_boolean('step6_zhihu', 'enable_draft_mode', True)
        
        # 确保 cookie 文件目录存在
        cookie_dir = os.path.dirname(self.cookie_file)
        if cookie_dir and not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir, exist_ok=True)
        
        # 初始化 session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'DNT': '1',
            'Sec-GPC': '1',
            'Referer': 'https://www.zhihu.com/'
        })
        
        # 存储 cookies 字典
        self.cookies_dict = {}
        
        # 加载已保存的 cookie
        self._load_cookies()
    
    def _load_cookies(self) -> bool:
        """加载已保存的 cookie"""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    self.cookies_dict = json.load(f)
                    self.session.cookies.update(self.cookies_dict)
                    self.logger.info("已加载保存的 cookie")
                    return True
        except Exception as e:
            self.logger.warning(f"加载 cookie 失败: {str(e)}")
        return False
    
    def save_cookies(self, cookies: Dict = None) -> bool:
        """保存 cookie 到文件"""
        try:
            if cookies is None:
                # 合并 session cookies 和存储的 cookies
                session_cookies = self.session.cookies.get_dict()
                self.cookies_dict.update(session_cookies)
                cookies_dict = self.cookies_dict
            elif isinstance(cookies, dict):
                self.cookies_dict.update(cookies)
                cookies_dict = self.cookies_dict
            elif hasattr(cookies, 'get_dict'):
                new_cookies = cookies.get_dict()
                self.cookies_dict.update(new_cookies)
                cookies_dict = self.cookies_dict
            else:
                cookies_dict = self.session.cookies.get_dict()
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, ensure_ascii=False, indent=2)
            
            self.logger.success(f"Cookie 已保存到: {self.cookie_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存 cookie 失败: {str(e)}")
            return False
    
    def _build_cookie_header(self, cookie_keys: List[str] = None) -> str:
        """
        构建 Cookie 请求头
        
        Args:
            cookie_keys: 需要包含的 cookie 键列表，如果为 None 则包含所有
            
        Returns:
            str: Cookie 请求头字符串
        """
        if cookie_keys is None or len(cookie_keys) == 0:
            # 返回所有 cookies
            all_cookies = {**self.cookies_dict, **self.session.cookies.get_dict()}
            return '; '.join([f'{k}={v}' for k, v in all_cookies.items()])
        else:
            # 只返回指定的 cookies
            all_cookies = {**self.cookies_dict, **self.session.cookies.get_dict()}
            return '; '.join([f'{k}={v}' for k, v in all_cookies.items() if k in cookie_keys])
    
    def _get_cookies_from_response(self, response: requests.Response) -> Dict:
        """从响应头中提取 cookies"""
        cookies = {}
        set_cookie_headers = response.headers.get('Set-Cookie', '')
        if isinstance(set_cookie_headers, list):
            cookie_strings = set_cookie_headers
        elif isinstance(set_cookie_headers, str):
            cookie_strings = [set_cookie_headers]
        else:
            cookie_strings = []
        
        for cookie_str in cookie_strings:
            # 提取第一个分号之前的部分（key=value）
            key_value = cookie_str.split(';')[0].strip()
            if '=' in key_value:
                key, value = key_value.split('=', 1)
                cookies[key.strip()] = value.strip()
        
        # 同时从 session cookies 中获取
        session_cookies = self.session.cookies.get_dict()
        cookies.update(session_cookies)
        
        return cookies
    
    def _init_cookies(self) -> bool:
        """初始化 cookies（访问首页获取基础 cookies）"""
        try:
            self.logger.info("正在初始化 cookies...")
            response = self.session.get(
                "https://www.zhihu.com",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Priority': 'u=0, i'
                },
                timeout=10
            )
            cookies = self._get_cookies_from_response(response)
            self.cookies_dict.update(cookies)
            self.save_cookies()
            self.logger.info("初始化 cookies 成功")
            return True
        except Exception as e:
            self.logger.warning(f"初始化 cookies 失败: {str(e)}")
            return False
    
    def _signin_next(self) -> bool:
        """访问登录页面"""
        try:
            self.logger.info("正在访问登录页面...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC'])
            response = self.session.get(
                "https://www.zhihu.com/signin?next=%2F",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Priority': 'u=0, i',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            cookies = self._get_cookies_from_response(response)
            self.cookies_dict.update(cookies)
            self.save_cookies()
            return True
        except Exception as e:
            self.logger.warning(f"访问登录页面失败: {str(e)}")
            return False
    
    def _init_udid_cookies(self) -> bool:
        """获取 UDID cookies"""
        try:
            self.logger.info("正在获取 UDID cookies...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC'])
            xsrftoken = self.cookies_dict.get('_xsrf', '')
            
            response = self.session.post(
                "https://www.zhihu.com/udid",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Referer': 'https://www.zhihu.com/signin?next=%2F',
                    'x-xsrftoken': xsrftoken,
                    'x-zse-93': '101_3_3.0',
                    'Origin': 'https://www.zhihu.com',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'Priority': 'u=4',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            cookies = self._get_cookies_from_response(response)
            self.cookies_dict.update(cookies)
            self.save_cookies()
            self.logger.info("获取 UDID cookies 成功")
            return True
        except Exception as e:
            self.logger.warning(f"获取 UDID cookies 失败: {str(e)}")
            return False
    
    def _sc_profiler(self) -> bool:
        """调用 sc-profiler"""
        try:
            self.logger.info("正在调用 sc-profiler...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC'])
            
            response = self.session.post(
                "https://www.zhihu.com/sc-profiler",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Content-Type': 'application/json',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Referer': 'https://www.zhihu.com/signin?next=%2F',
                    'Origin': 'https://www.zhihu.com',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'Cookie': cookies_header
                },
                json=[[
                    "i",
                    "production.heifetz.desktop.v1.za_helper.init.count",
                    1,
                    1
                ]],
                timeout=10
            )
            return True
        except Exception as e:
            self.logger.warning(f"调用 sc-profiler 失败: {str(e)}")
            return False
    
    def _captcha_signin(self) -> bool:
        """获取验证码 session"""
        try:
            self.logger.info("正在获取验证码 session...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0'])
            
            response = self.session.get(
                "https://www.zhihu.com/api/v3/oauth/captcha/v2?type=captcha_sign_in",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Referer': 'https://www.zhihu.com/signin?next=%2F',
                    'x-requested-with': 'fetch',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Site': 'same-origin',
                    'Priority': 'u=4',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            cookies = self._get_cookies_from_response(response)
            self.cookies_dict.update(cookies)
            self.save_cookies()
            self.logger.info("获取验证码 session 成功")
            return True
        except Exception as e:
            self.logger.warning(f"获取验证码 session 失败: {str(e)}")
            return False
    
    def _login_link_builder(self, token: str) -> str:
        """构建二维码登录链接"""
        return f"https://www.zhihu.com/account/scan/login/{token}?/api/login/qrcode"
    
    def get_qrcode(self) -> Dict:
        """
        获取知乎登录二维码（完整流程）
        
        Returns:
            Dict: 包含 qrcode_token, qrcode_url, qrcode_image_base64
        """
        try:
            self.logger.info("正在获取知乎登录二维码...")
            
            # 执行初始化步骤
            self._init_cookies()
            self._signin_next()
            self._init_udid_cookies()
            self._sc_profiler()
            self._captcha_signin()
            
            # 获取二维码 token
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0'])
            response = self.session.post(
                "https://www.zhihu.com/api/v3/account/api/login/qrcode",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Referer': 'https://www.zhihu.com/signin?next=%2F',
                    'Origin': 'https://www.zhihu.com',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'Priority': 'u=4',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"获取二维码失败，状态码: {response.status_code}")
            
            data = response.json()
            qrcode_token = data.get('token', '')
            
            if not qrcode_token:
                raise Exception("未能获取二维码 token")
            
            # 构建二维码链接
            qrcode_link = self._login_link_builder(qrcode_token)
            
            # 生成二维码图片
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qrcode_link)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qrcode_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            self.logger.success(f"二维码获取成功，token: {qrcode_token[:20]}...")
            
            return {
                'success': True,
                'qrcode_token': qrcode_token,
                'qrcode_url': qrcode_link,
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
            Dict: 登录状态信息，可能包含 new_token（需要刷新二维码时）
        """
        try:
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2'])
            check_url = f"https://www.zhihu.com/api/v3/account/api/login/qrcode/{qrcode_token}/scan_info"
            
            response = self.session.get(
                check_url,
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Referer': 'https://www.zhihu.com/signin?next=%2F',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Site': 'same-origin',
                    'Priority': 'u=4',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'status': 'error',
                    'message': f'检查登录状态失败，状态码: {response.status_code}'
                }
            
            data = response.json()
            status = data.get('status', '')
            
            # status=1 表示已扫码
            if status == 1:
                # 检查是否有新的 token（需要刷新二维码）
                if 'new_token' in data and data['new_token']:
                    new_token = data['new_token'].get('Token', '')
                    if new_token:
                        return {
                            'success': True,
                            'status': 'refresh',
                            'message': '二维码已过期，需要刷新',
                            'new_token': new_token
                        }
                
                # 继续等待确认
                return {
                    'success': True,
                    'status': 'scan',
                    'message': '等待确认'
                }
            # status=5 表示二维码过期，需要刷新
            elif status == 5:
                new_token = data.get('new_token', {}).get('Token', '') if 'new_token' in data else ''
                return {
                    'success': True,
                    'status': 'refresh',
                    'message': '二维码已过期，需要刷新',
                    'new_token': new_token
                }
            # 登录成功（没有 status 字段，直接返回数据）
            elif 'status' not in data or status == '':
                # 登录成功，获取 cookies
                cookies = self._get_cookies_from_response(response)
                self.cookies_dict.update(cookies)
                self.save_cookies()
                
                # 执行登录后的步骤
                self._signin_zhihu()
                self._prod_token_refresh()
                user_info = self._get_user_info()
                
                return {
                    'success': True,
                    'status': 'login',
                    'message': '登录成功',
                    'cookies': cookies,
                    'user_info': user_info
                }
            else:
                return {
                    'success': True,
                    'status': str(status),
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
    
    def _signin_zhihu(self) -> bool:
        """登录后访问首页获取新 cookies"""
        try:
            self.logger.info("正在完成登录流程...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0'])
            
            response = self.session.get(
                "https://www.zhihu.com",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'referer': 'https://www.zhihu.com/signin?next=%2F',
                    'dnt': '1',
                    'sec-gpc': '1',
                    'upgrade-insecure-requests': '1',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'priority': 'u=0, i',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            cookies = self._get_cookies_from_response(response)
            self.cookies_dict.update(cookies)
            self.save_cookies()
            return True
        except Exception as e:
            self.logger.warning(f"完成登录流程失败: {str(e)}")
            return False
    
    def _prod_token_refresh(self) -> bool:
        """刷新生产 token"""
        try:
            self.logger.info("正在刷新生产 token...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0', 'q_c1'])
            
            response = self.session.post(
                "https://www.zhihu.com/api/account/prod/token/refresh",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'referer': 'https://www.zhihu.com/',
                    'x-requested-with': 'fetch',
                    'origin': 'https://www.zhihu.com',
                    'dnt': '1',
                    'sec-gpc': '1',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'priority': 'u=4',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            return True
        except Exception as e:
            self.logger.warning(f"刷新生产 token 失败: {str(e)}")
            return False
    
    def _get_user_info(self) -> Optional[Dict]:
        """获取用户信息"""
        try:
            self.logger.info("正在获取用户信息...")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'z_c0', 'q_c1'])
            
            response = self.session.get(
                "https://www.zhihu.com/api/v4/me?include=is_realname",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'referer': 'https://www.zhihu.com/',
                    'x-requested-with': 'fetch',
                    'x-zse-93': '101_3_3.0',
                    'Cookie': cookies_header
                },
                timeout=10
            )
            
            if response.status_code == 200:
                user_info = response.json()
                cookies = self._get_cookies_from_response(response)
                self.cookies_dict.update(cookies)
                self.save_cookies()
                self.logger.success(f"获取用户信息成功: {user_info.get('name', '未知用户')}")
                return user_info
            return None
        except Exception as e:
            self.logger.warning(f"获取用户信息失败: {str(e)}")
            return None
    
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
    
    def _calculate_image_hash(self, image_buffer: bytes) -> str:
        """计算图片的 MD5 hash"""
        return hashlib.md5(image_buffer).hexdigest()
    
    def _get_image_upload_token(self, img_hash: str) -> Optional[Dict]:
        """获取图片上传 token"""
        try:
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0'])
            
            response = self.session.post(
                "https://api.zhihu.com/images",
                headers={
                    'Content-Type': 'application/json',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'Cookie': cookies_header
                },
                json={
                    'image_hash': img_hash,
                    'source': 'article'
                },
                timeout=self.image_upload_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"获取图片上传 token 失败: {str(e)}")
            return None
    
    def _upload_image_to_oss(self, image_buffer: bytes, upload_token: Dict, img_hash: str, mime_type: str) -> bool:
        """上传图片到 OSS"""
        try:
            import hmac
            from datetime import datetime
            
            # upload_token 是直接从响应中获取的对象
            # 根据参考代码，字段名是 access_id, access_key, access_token
            access_id = upload_token.get('access_id', '')
            access_key = upload_token.get('access_key', '')
            security_token = upload_token.get('access_token', '')
            
            if not all([access_id, access_key, security_token]):
                self.logger.error(f"上传 token 信息不完整: access_id={bool(access_id)}, access_key={bool(access_key)}, security_token={bool(security_token)}")
                self.logger.error(f"Token 结构: {list(upload_token.keys())}")
                self.logger.error(f"Token 内容: {json.dumps(upload_token, ensure_ascii=False, indent=2)}")
                return False
            
            request_time = int(time.time() * 1000)
            utc_date = datetime.utcfromtimestamp(request_time / 1000).strftime('%a, %d %b %Y %H:%M:%S GMT')
            ua = "aliyun-sdk-js/6.8.0 Firefox 137.0 on OS X 10.15"
            
            # 构建签名字符串
            string_to_sign = f"PUT\n\n{mime_type}\n{utc_date}\nx-oss-date:{utc_date}\nx-oss-security-token:{security_token}\nx-oss-user-agent:{ua}\n/zhihu-pics/v2-{img_hash}"
            
            # 计算签名 (使用 access_key 作为 secret)
            signature = base64.b64encode(
                hmac.new(access_key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
            ).decode()
            
            # 上传到 OSS (使用 access_id 在 authorization header)
            response = self.session.put(
                f"https://zhihu-pics-upload.zhimg.com/v2-{img_hash}",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Content-Type': mime_type,
                    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'x-oss-date': utc_date,
                    'x-oss-user-agent': ua,
                    'x-oss-security-token': security_token,
                    'authorization': f'OSS {access_id}:{signature}'
                },
                data=image_buffer,
                timeout=self.image_upload_timeout
            )
            
            if response.status_code in [200, 204]:
                return True
            return False
        except Exception as e:
            self.logger.error(f"上传图片到 OSS 失败: {str(e)}")
            return False
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片到知乎图床（使用新的 API）
        
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
            
            # 读取图片文件
            with open(image_path, 'rb') as f:
                image_buffer = f.read()
            
            # 计算 hash
            img_hash = self._calculate_image_hash(image_buffer)
            
            # 获取文件扩展名和 MIME 类型
            ext = os.path.splitext(image_path)[1].lower().lstrip('.')
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            mime_type = mime_types.get(ext, 'image/png')
            
            # 获取上传 token
            upload_token_data = self._get_image_upload_token(img_hash)
            if not upload_token_data:
                self.logger.error("获取上传 token 失败")
                return None
            
            # 添加调试日志
            self.logger.info(f"上传token响应结构: {json.dumps(upload_token_data, ensure_ascii=False, indent=2)}")
            
            # 检查图片状态
            img_state = upload_token_data.get('upload_file', {}).get('state', 0)
            
            # state=2 表示需要上传
            if img_state == 2:
                upload_token = upload_token_data.get('upload_token')
                if not upload_token:
                    self.logger.error("未获取到上传 token")
                    self.logger.error(f"响应数据: {json.dumps(upload_token_data, ensure_ascii=False, indent=2)}")
                    return None
                if not self._upload_image_to_oss(image_buffer, upload_token, img_hash, mime_type):
                    self.logger.error("上传图片到 OSS 失败")
                    return None
            
            # 构建图片 URL
            image_url = f"https://picx.zhimg.com/v2-{img_hash}.{ext}"
            self.logger.success(f"图片上传成功: {image_url}")
            return image_url
                
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
    
    def create_draft(self, title: str) -> Optional[str]:
        """
        创建知乎草稿
        
        Args:
            title: 文章标题
            
        Returns:
            str: 草稿 ID，失败返回 None
        """
        try:
            if not self.is_logged_in():
                self.logger.error("未登录，请先登录")
                return None
            
            self.logger.info(f"正在创建草稿: {title}")
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0'])
            xsrftoken = self.cookies_dict.get('_xsrf', '')
            
            response = self.session.post(
                "https://zhuanlan.zhihu.com/api/articles/drafts",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Content-Type': 'application/json',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'referer': 'https://zhuanlan.zhihu.com/write',
                    'x-requested-with': 'fetch',
                    'x-xsrftoken': xsrftoken,
                    'origin': 'https://zhuanlan.zhihu.com',
                    'Cookie': cookies_header
                },
                json={
                    'title': title,
                    'delta_time': 0,
                    'can_reward': False
                },
                timeout=self.publish_timeout
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                article_id = data.get('id', '')
                if article_id:
                    self.logger.success(f"草稿创建成功: {article_id}")
                    return str(article_id)
            
            self.logger.error(f"创建草稿失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
        except Exception as e:
            self.logger.error(f"创建草稿异常: {str(e)}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    def update_draft(self, article_id: str, patch_body: Dict) -> bool:
        """
        更新草稿内容
        
        Args:
            article_id: 草稿 ID
            patch_body: 要更新的内容
            
        Returns:
            bool: 是否成功
        """
        try:
            cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0'])
            xsrftoken = self.cookies_dict.get('_xsrf', '')
            
            response = self.session.patch(
                f"https://zhuanlan.zhihu.com/api/articles/{article_id}/draft",
                headers={
                    'User-Agent': self.user_agent,
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Content-Type': 'application/json',
                    'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                    'referer': f'https://zhuanlan.zhihu.com/p/{article_id}/edit',
                    'x-requested-with': 'fetch',
                    'x-xsrftoken': xsrftoken,
                    'origin': 'https://zhuanlan.zhihu.com',
                    'Cookie': cookies_header
                },
                json=patch_body,
                timeout=self.publish_timeout
            )
            
            if response.status_code in [200, 204]:
                self.logger.success(f"草稿更新成功: {article_id}")
                return True
            
            self.logger.error(f"更新草稿失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
        except Exception as e:
            self.logger.error(f"更新草稿异常: {str(e)}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def publish_article(self, title: str, content: str, topics: List[str] = None, toc: bool = False) -> Dict:
        """
        发布文章到知乎（使用草稿 API）
        
        Args:
            title: 文章标题
            content: 文章内容（HTML 格式）
            topics: 话题列表
            toc: 是否启用目录
            
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
            
            # 使用草稿模式
            if self.enable_draft_mode:
                # 1. 创建草稿
                article_id = self.create_draft(title)
                if not article_id:
                    return {
                        'success': False,
                        'error': '创建草稿失败',
                        'message': '创建草稿失败'
                    }
                
                # 2. 更新草稿内容
                patch_body = {
                    'title': title,
                    'content': content,
                    'table_of_contents': toc,
                    'delta_time': 30,
                    'can_reward': False
                }
                
                if not self.update_draft(article_id, patch_body):
                    return {
                        'success': False,
                        'error': '更新草稿失败',
                        'message': '更新草稿失败'
                    }
                
                # 3. 发布草稿
                cookies_header = self._build_cookie_header(['_zap', '_xsrf', 'BEC', 'd_c0', 'captcha_session_v2', 'z_c0', 'q_c1'])
                xsrftoken = self.cookies_dict.get('_xsrf', '')
                trace_id = f"{int(time.time() * 1000)},{uuid.uuid4()}"
                
                response = self.session.post(
                    "https://www.zhihu.com/api/v4/content/publish",
                    headers={
                        'User-Agent': self.user_agent,
                        'Accept-Encoding': 'gzip, deflate, br, zstd',
                        'Content-Type': 'application/json',
                        'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                        'x-requested-with': 'fetch',
                        'x-xsrftoken': xsrftoken,
                        'Cookie': cookies_header
                    },
                    json={
                        'action': 'article',
                        'data': {
                            'publish': {'traceId': trace_id},
                            'extra_info': {
                                'publisher': 'pc',
                                'pc_business_params': json.dumps({
                                    'column': None,
                                    'commentPermission': 'anyone',
                                    'disclaimer_type': 0,
                                    'disclaimer_status': 0,
                                    'table_of_contents_enabled': toc,
                                    'commercial_report_info': {'commercial_types': []},
                                    'commercial_zhitask_bind_info': None,
                                    'canReward': False
                                }, ensure_ascii=False)
                            },
                            'draft': {
                                'disabled': 1,
                                'id': article_id,
                                'isPublished': False
                            },
                            'commentsPermission': {'comment_permission': 'anyone'},
                            'creationStatement': {
                                'disclaimer_type': 0,
                                'disclaimer_status': 0
                            },
                            'contentsTables': {'table_of_contents_enabled': toc},
                            'commercialReportInfo': {'isReport': 0},
                            'appreciate': {'can_reward': False, 'tagline': ''},
                            'hybridInfo': {}
                        }
                    },
                    timeout=self.publish_timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.logger.info(f"发布API响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    if data.get('message') == 'success':
                        result_data = json.loads(data.get('data', {}).get('result', '{}'))
                        article_url = f"https://zhuanlan.zhihu.com/p/{article_id}"
                        
                        self.logger.success(f"文章发布成功: {article_url}")
                        
                        return {
                            'success': True,
                            'article_id': article_id,
                            'article_url': article_url,
                            'message': '文章发布成功'
                        }
                    else:
                        error_msg = f"发布失败: {data.get('message', '未知错误')}"
                        error_detail = data.get('error', {})
                        if error_detail:
                            error_msg += f", 详情: {json.dumps(error_detail, ensure_ascii=False)}"
                        self.logger.error(error_msg)
                        self.logger.error(f"完整响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'message': error_msg
                        }
                else:
                    error_msg = f"发布失败，状态码: {response.status_code}, 响应: {response.text}"
                    self.logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'message': error_msg
                    }
            else:
                # 使用旧的直接发布方式（向后兼容）
                publish_url = "https://zhuanlan.zhihu.com/api/articles"
                publish_data = {
                    'title': title,
                    'content': content,
                    'summary': title[:100],
                    'can_comment': True,
                    'comment_permission': 'all',
                    'type': 'article'
                }
                
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






