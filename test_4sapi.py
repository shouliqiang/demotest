#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
4sapi.com API 测试脚本
测试 GPT Image 模型的图像编辑功能
"""

import requests
import os
from pathlib import Path


def test_image_edit_with_upload():
    """
    测试场景1：上传图片 + 提示词编辑
    """
    print("\n" + "=" * 60)
    print(" 测试1：图片编辑（上传图片 + 提示词）")
    print("=" * 60)

    # API 配置
    url = "https://4sapi.com/v1/images/edits"
    api_key = os.environ.get("GPT_IMAGE_KEY", "")
    if not api_key:
        print("⚠️  未设置环境变量 GPT_IMAGE_KEY")
        return

    # 准备上传的图片（替换为你的图片路径）
    image_path = "D:/CTF/pythonProject/zijie/demo/R-C.jpg"

    if not Path(image_path).exists():
        print(f"⚠️  图片不存在: {image_path}")
        print("提示：请先准备一张测试图片")
        return

    # 准备请求数据（multipart/form-data）
    files = {
        'image[]': open(image_path, 'rb')
    }

    data = {
        'model': 'gpt-image-2',  # 或 dall-e-2
        'prompt': '针对该图片所示的耳机，生成一张商品海报，用于宣传',
        'quality': 'standard'
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }

    try:
        print(f"📤 正在发送请求...")
        print(f"   URL: {url}")
        print(f"   模型: {data['model']}")
        print(f"   提示词: {data['prompt']}")
        print(f"   质量: {data['quality']}")
        print()

        # 发送请求
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=120
        )

        print(f" 收到响应:")
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 请求成功！")
            print(f"   响应数据: {result}")

            # 保存生成的图片
            if 'data' in result and len(result['data']) > 0:
                for i, item in enumerate(result['data']):
                    if 'b64_json' in item:
                        # 解码 Base64 并保存图片
                        import base64
                        image_data = base64.b64decode(item['b64_json'])

                        # 保存路径
                        output_dir = Path("D:/CTF/pythonProject/zijie/demotest/generated_posters")
                        output_dir.mkdir(parents=True, exist_ok=True)

                        output_path = output_dir / f"cyberpunk_swordsman_{i + 1}.png"
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        print(f"\n✅ 图片 {i + 1} 已保存: {output_path}")
                        print(f"   AI优化提示词: {item.get('revised_prompt', 'N/A')}")

                    elif 'url' in item:
                        print(f"\n  图片 {i + 1} URL: {item['url']}")


    except requests.exceptions.Timeout:
        print("❌ 请求超时（120秒）")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 网络连接错误: {e}")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        # 关闭文件
        if 'image[]' in files:
            files['image[]'].close()


def test_image_generation_only():
    """
    测试场景2：仅用提示词生成（不上传图片）
    """
    print("\n" + "=" * 60)
    print(" 测试2：纯提示词生成（不上传图片）")
    print("=" * 60)

    # API 配置
    url = "https://4sapi.com/v1/images/generations"  # 注意：生成接口可能不同
    api_key = os.environ.get("GPT_IMAGE_KEY", "")
    if not api_key:
        print("⚠️  未设置环境变量 GPT_IMAGE_KEY")
        return

    data = {
        'model': 'dall-e-2',
        'prompt': '中国传统水墨画风格的剑客竹林练剑海报，一位身穿白色长袍的武林高手在翠绿竹林中挥剑练习，剑光划出优雅的弧线，8K高清',
        'quality': 'hd'
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }

    try:
        print(f" 正在发送请求...")
        print(f"   URL: {url}")
        print(f"   模型: {data['model']}")
        print(f"   提示词: {data['prompt'][:50]}...")
        print()

        # 注意：如果这个平台不支持纯生成，可能需要用 edits 接口
        response = requests.post(
            url,
            headers=headers,
            json=data,  # JSON 格式
            timeout=120
        )

        print(f" 收到响应:")
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 请求成功！")
            print(f"   响应数据: {result}")
        else:
            print(f"   ❌ 请求失败")
            print(f"   错误信息: {response.text}")

    except Exception as e:
        print(f"❌ 发生错误: {e}")


def test_connection():
    """
    测试网络连接
    """
    print("\n" + "=" * 60)
    print(" 测试0：网络连接测试")
    print("=" * 60)

    try:
        print("正在测试 4sapi.com 连通性...")
        response = requests.get("https://4sapi.com", timeout=10)
        print(f"✅ 网站可访问，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 无法访问 4sapi.com: {e}")


if __name__ == '__main__':
    print("\n🚀 开始测试 4sapi.com API")

    # 先测试网络连通性
    test_connection()

    # 测试图片编辑
    test_image_edit_with_upload()

    # 测试纯提示词生成（可选）
    # test_image_generation_only()

    print("\n" + "=" * 60)
    print(" 测试完成！")
    print("=" * 60 + "\n")
