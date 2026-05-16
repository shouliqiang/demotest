#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
海报生成模块 - 整合海报生成和任务管理功能
支持异步任务处理、图像保存和状态查询
"""

import os
import time
import base64
import logging
import threading
import uuid
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class PosterAPI:
    """海报API调用类 - 负责与GPT Image-2 API交互"""

    def __init__(self, api_key=None, base_url="https://4sapi.com"):
        """
        初始化海报API

        Args:
            api_key: GPT Image-2 API密钥
            base_url: API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    def call_api(self, prompt, image_path=None):
        """
        调用GPT Image-2 API生成海报

        Args:
            prompt: 海报提示词
            image_path: 可选的参考图片路径

        Returns:
            dict: API响应结果
        """
        if not self.api_key:
            logger.error("API Key未配置")
            return {
                'success': False,
                'error': '请先配置API Key'
            }

        data = {
            'model': 'gpt-image-2',
            'prompt': prompt,

        }

        files = {}
        has_image = False

        if image_path and Path(image_path).exists():
            try:
                files['image'] = open(image_path, 'rb')
                has_image = True
                logger.info(f"已加载参考图片: {image_path}")
            except Exception as e:
                logger.warning(f"加载图片失败: {e}")

        try:
            if has_image:
                url = f"{self.base_url}/v1/images/edits"
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Accept': 'application/json'
                }

                logger.info(f"调用edits接口（带图）: {url}")
                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )
            else:
                url = f"{self.base_url}/v1/images/generations"
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                logger.info(f"调用generations接口（纯文本）: {url}")
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120
                )

            if 'image' in files:
                files['image'].close()

            logger.info(f"API响应状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                if 'data' in result and len(result['data']) > 0:
                    generated_images = []
                    for item in result['data']:
                        image_info = {'revised_prompt': item.get('revised_prompt', '')}

                        if 'b64_json' in item:
                            image_info['b64_json'] = item['b64_json']
                        elif 'url' in item:
                            image_info['url'] = item['url']

                        generated_images.append(image_info)

                    logger.info(f"成功生成{len(generated_images)}张图像")

                    return {
                        'success': True,
                        'images': generated_images,
                        'created': result.get('created', int(time.time())),
                        'usage': result.get('usage', {})
                    }
                else:
                    return {
                        'success': False,
                        'error': 'API返回数据格式错误'
                    }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}'

                logger.error(f"API错误: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.Timeout:
            logger.error("请求超时 (120秒)")
            return {
                'success': False,
                'error': '请求超时，请稍后重试'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"网络连接错误: {e}")
            return {
                'success': False,
                'error': '网络连接错误，请检查网络或API地址'
            }
        except Exception as e:
            logger.error(f"API调用异常: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'生成海报时出错: {str(e)}'
            }


class ImageSaver:
    """图像保存工具类"""

    @staticmethod
    def save_image(image_data, save_dir, filename=None, is_base64=True):
        """
        保存生成的图像

        Args:
            image_data: 图像数据（Base64字符串或URL）
            save_dir: 保存目录
            filename: 文件名（可选）
            is_base64: 是否为Base64格式

        Returns:
            str: 保存的文件路径，失败返回None
        """
        try:
            save_path = Path(save_dir)
            save_path.mkdir(parents=True, exist_ok=True)

            if not filename:
                ext = '.png' if is_base64 else '.webp'
                filename = f"poster_{uuid.uuid4().hex}{ext}"

            filepath = save_path / filename

            if is_base64:
                logger.info("正在解码Base64图像...")
                image_bytes = base64.b64decode(image_data)
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                logger.info(f"图像已保存 (Base64): {filepath}")
            else:
                logger.info(f"正在下载图像: {image_data[:50]}...")
                response = requests.get(image_data, stream=True, timeout=60)

                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"图像已保存 (URL): {filepath}")
                else:
                    logger.error(f"下载失败: HTTP {response.status_code}")
                    return None

            return str(filepath)

        except Exception as e:
            logger.error(f"保存图像失败: {e}", exc_info=True)
            return None


class PosterModule:
    """海报生成模块 - 整合API调用、任务管理和图像保存"""

    def __init__(self, config, base_dir):
        """
        初始化海报模块

        Args:
            config: 配置字典，包含gpt_image_key等
            base_dir: 基础目录路径
        """
        self.config = config
        self.base_dir = Path(base_dir)
        self.poster_folder = self.base_dir / 'posters'
        self.tasks = {}

        self.poster_folder.mkdir(parents=True, exist_ok=True)

        self.api = PosterAPI(
            api_key=config.get('gpt_image_key'),
            base_url=config.get('gpt_image_base_url', 'https://4sapi.com')
        )

        logger.info("海报模块初始化完成")

    def update_config(self, config):
        """更新配置"""
        self.config = config
        self.api = PosterAPI(
            api_key=config.get('gpt_image_key'),
            base_url=config.get('gpt_image_base_url', 'https://4sapi.com')
        )
        logger.info("海报模块配置已更新")

    def generate_poster_async(self, prompt, image_urls=None):
        """
        异步生成海报

        Args:
            prompt: 海报提示词
            image_urls: 参考图片路径列表

        Returns:
            str: 任务ID
        """
        if not self.config.get('gpt_image_key'):
            raise Exception('请先配置GPT Image API Key')

        if not prompt:
            raise Exception('请提供提示词')

        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'image_url': None,
            'error': None,
            'created_at': datetime.now().isoformat()
        }

        image_path = image_urls[0] if image_urls and len(image_urls) > 0 else None

        thread = threading.Thread(
            target=self._process_task,
            args=(task_id, prompt, image_path)
        )
        thread.daemon = True
        thread.start()

        logger.info(f"海报任务已创建: {task_id}")
        return task_id

    def get_task_status(self, task_id):
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            dict: 任务状态信息
        """
        if task_id not in self.tasks:
            return {'success': False, 'error': '任务不存在'}

        task = self.tasks[task_id]
        result = {
            'success': True,
            'status': task['status'],
            'progress': task.get('progress', 0)
        }

        if task['status'] == 'completed':
            result['image_url'] = task.get('image_url')
        elif task['status'] == 'failed':
            result['error'] = task.get('error')

        return result

    def _process_task(self, task_id, prompt, image_path):
        """后台处理海报生成任务"""
        try:
            self.tasks[task_id]['status'] = 'running'
            self.tasks[task_id]['progress'] = 10

            logger.info(f"[任务 {task_id}] 开始生成海报")
            logger.info(f"[任务 {task_id}] 提示词长度: {len(prompt)}")

            self.tasks[task_id]['progress'] = 30

            result = self.api.call_api(prompt, image_path)

            logger.info(f"[任务 {task_id}] API返回: success={result.get('success')}")

            self.tasks[task_id]['progress'] = 70

            if not result['success']:
                raise Exception(result['error'])

            if not result['images'] or len(result['images']) == 0:
                raise Exception("未获取到生成的图像")

            image_item = result['images'][0]

            self.tasks[task_id]['progress'] = 80
            logger.info(f"[任务 {task_id}] 正在保存图像...")

            if 'b64_json' in image_item:
                saved_path = ImageSaver.save_image(
                    image_data=image_item['b64_json'],
                    save_dir=str(self.poster_folder),
                    filename=f"poster_{task_id}.png",
                    is_base64=True
                )
            elif 'url' in image_item:
                saved_path = ImageSaver.save_image(
                    image_data=image_item['url'],
                    save_dir=str(self.poster_folder),
                    filename=f"poster_{task_id}.webp",
                    is_base64=False
                )
            else:
                raise Exception("未获取到图像数据")

            if saved_path:
                self.tasks[task_id]['status'] = 'completed'
                self.tasks[task_id]['progress'] = 100
                self.tasks[task_id]['image_url'] = f'/api/download_poster/{Path(saved_path).name}'

                logger.info(f"[任务 {task_id}] 海报生成成功: {saved_path}")

                if 'revised_prompt' in image_item:
                    logger.info(f"[任务 {task_id}] AI优化提示词: {image_item['revised_prompt'][:100]}...")
            else:
                raise Exception("保存海报图像失败")

        except Exception as e:
            logger.error(f"[任务 {task_id}] 失败: {e}", exc_info=True)
            self.tasks[task_id]['status'] = 'failed'
            self.tasks[task_id]['error'] = str(e)
            self.tasks[task_id]['progress'] = 0

    def cleanup_old_tasks(self, max_age_hours=24):
        """清理旧任务记录"""
        now = datetime.now()
        to_remove = []

        for task_id, task in self.tasks.items():
            created_at = datetime.fromisoformat(task['created_at'])
            if (now - created_at).total_seconds() > max_age_hours * 3600:
                to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]

        if to_remove:
            logger.info(f"清理了{len(to_remove)}个旧任务记录")


if __name__ == '__main__':
    print("海报模块测试")
    print("=" * 50)

    test_config = {
        'gpt_image_key': 'YOUR_API_KEY_HERE',
        'gpt_image_base_url': 'https://4sapi.com'
    }

    module = PosterModule(test_config, Path('.'))

    print("\n测试1: 纯文本生成海报")
    task_id = module.generate_poster_async(
        prompt="一个现代科技风格的产品海报，蓝色渐变背景，简洁大气",
        size="1024x1024"
    )
    print(f"任务ID: {task_id}")

    import time

    time.sleep(2)
    status = module.get_task_status(task_id)
    print(f"任务状态: {status}")
