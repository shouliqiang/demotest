#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
海报生成器 - 调用GPT Image-2 API生成海报图像
"""

import requests
import base64
import os
import json
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PosterGenerator:
    """海报生成器类，用于调用GPT Image-2 API生成海报"""

    def __init__(self, api_key=None, base_url="https://makerend.com"):
        """
        初始化海报生成器

        Args:
            api_key: GPT Image-2 API密钥
            base_url: API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'

    def generate_poster(self, prompt, image_urls=None, size="1024x1024", n=1):
        """
        生成海报图像（使用 4sapi.com API）

        Args:
            prompt: 所需图像的文本描述
            image_urls: 要编辑的图片路径列表（最多5张）
            size: 生成图像的尺寸，可选值：1024x1024、1536x1024（横版）、1024x1536（竖版）
            n: 要生成的图像数量

        Returns:
            dict: 包含生成结果的字典
        """
        if not self.api_key:
            logger.error("API Key未配置")
            return {
                'success': False,
                'error': '请先配置API Key'
            }

        # 准备请求数据
        data = {
            'model': 'gpt-image-2',
            'prompt': prompt,
            'quality': 'standard'
        }

        files = {}
        has_image = False

        # 如果提供了本地图片路径
        if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
            try:
                image_path = image_urls[0]
                if Path(image_path).exists():
                    files['image'] = open(image_path, 'rb')
                    has_image = True
                    logger.info(f"已加载图片: {image_path}")
                else:
                    logger.warning(f"图片文件不存在: {image_path}")
            except Exception as e:
                logger.warning(f"加载图片失败: {e}")

        try:
            if has_image:
                # 有图片时使用 multipart/form-data 调用 edits 接口
                url = f"{self.base_url}/v1/images/edits"
                logger.info(f"准备发送multipart/form-data请求到: {url}")
                logger.info(f"请求参数: model=gpt-image-2, quality=standard, prompt长度={len(prompt)}")

                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Accept': 'application/json'
                }

                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )
            else:
                # 没有图片时使用 JSON 格式调用 generations 接口
                url = f"{self.base_url}/v1/images/generations"
                logger.info(f"准备发送JSON请求到: {url} (无图片)")

                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=120
                )

            # 关闭文件
            if 'image' in files:
                files['image'].close()

            logger.info(f"收到响应: status_code={response.status_code}")

            # 检查响应状态码
            if response.status_code == 200:
                result = response.json()
                logger.info(f"API响应成功")

                # 解析返回结果
                if 'data' in result and len(result['data']) > 0:
                    generated_images = []
                    for item in result['data']:
                        if 'b64_json' in item:
                            generated_images.append({
                                'b64_json': item['b64_json'],
                                'revised_prompt': item.get('revised_prompt', '')
                            })
                        elif 'url' in item:
                            generated_images.append({
                                'url': item['url'],
                                'revised_prompt': item.get('revised_prompt', '')
                            })

                    logger.info(f"成功解析{len(generated_images)}个图像")

                    return {
                        'success': True,
                        'images': generated_images,
                        'created': result.get('created', int(time.time())),
                        'usage': result.get('usage', {})
                    }
                else:
                    logger.error(f"API返回数据格式错误: {result}")
                    return {
                        'success': False,
                        'error': 'API返回数据格式错误'
                    }
            else:
                logger.error(f"API返回错误状态码: {response.status_code}")
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                    logger.error(f"错误详情: {error_msg}")
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                    logger.error(f"错误响应内容: {response.text[:200]}")

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
            logger.error(f"生成海报时发生未知错误: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'生成海报时出错: {str(e)}'
            }

    def download_and_save_image(self, image_data, save_dir, filename=None, is_base64=True):
        """
        保存生成的图像（支持 Base64 和 URL 两种格式）

        Args:
            image_data: 图像数据（Base64字符串或URL）
            save_dir: 保存目录
            filename: 文件名（可选）
            is_base64: 是否为Base64格式（默认True）

        Returns:
            str: 保存的文件路径，失败返回None
        """
        try:
            import base64

            # 确保保存目录存在
            save_path = Path(save_dir)
            save_path.mkdir(parents=True, exist_ok=True)

            # 如果没有指定文件名，则生成唯一文件名
            if not filename:
                import uuid
                ext = '.png' if is_base64 else '.webp'
                filename = f"poster_{uuid.uuid4().hex}{ext}"

            filepath = save_path / filename

            if is_base64:
                # 解码 Base64 并保存
                logger.info(f"正在解码Base64图像数据...")
                image_bytes = base64.b64decode(image_data)
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                logger.info(f"图像已保存 (Base64): {filepath}")
            else:
                # 从 URL 下载图像
                logger.info(f"正在从URL下载图像: {image_data[:50]}...")
                response = requests.get(image_data, stream=True, timeout=60)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"图像已保存 (URL): {filepath}")
                else:
                    logger.error(f"下载图像失败: HTTP {response.status_code}")
                    return None

            return str(filepath)

        except Exception as e:
            logger.error(f"保存图像时出错: {e}", exc_info=True)
            return None

    def generate_from_local_images(self, prompt, local_image_paths, size="1024x1024", n=1):
        """
        从本地图片生成海报（需要先上传到图床或转换为base64）

        Args:
            prompt: 提示词
            local_image_paths: 本地图片路径列表
            size: 图像尺寸
            n: 生成数量

        Returns:
            dict: 生成结果
        """
        # 注意：GPT Image-2 API需要图片URL，而不是base64
        # 如果需要从本地图片生成，需要先上传到图床
        # 这里提供一个简单的实现思路

        if not local_image_paths:
            return {
                'success': False,
                'error': '请提供图片路径'
            }

        # 实际使用时，你需要将本地图片上传到图床服务
        # 或者使用支持base64的API
        return {
            'success': False,
            'error': 'GPT Image-2 API需要图片URL，请先将本地图片上传到图床服务'
        }


# 测试代码
if __name__ == '__main__':
    # 示例用法
    generator = PosterGenerator(api_key="YOUR_API_KEY")

    # 示例1：仅通过提示词生成海报
    result = generator.generate_poster(
        prompt="一个现代科技风格的产品海报，蓝色渐变背景，简洁大气",
        size="1024x1024",
        n=1
    )

    if result['success']:
        print("海报生成成功！")
        for img in result['images']:
            print(f"图像URL: {img['url']}")
    else:
        print(f"生成失败: {result['error']}")
