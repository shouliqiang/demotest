#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI产品宣传生成器 - 主应用入口
整合视频生成和海报生成功能
"""

import sys
import os
import subprocess
import warnings


def auto_install_dependencies():
    """自动检查并安装缺失的依赖"""
    required = {
        'flask': 'flask>=2.0.0',
        'flask_cors': 'flask-cors>=4.0.0',
        'dashscope': 'dashscope>=1.14.0',
        'requests': 'requests>=2.31.0',
        'PIL': 'Pillow>=10.0.0',
    }

    missing = []
    for module_name, package_spec in required.items():
        try:
            if module_name == 'PIL':
                __import__('PIL')
            else:
                __import__(module_name)
        except ImportError:
            missing.append(package_spec)

    if missing:
        print("\n" + "=" * 50)
        print("⚠️  检测到缺少依赖包，正在自动安装...")
        print("=" * 50)

        for package in missing:
            print(f"安装: {package}")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package,
                "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
            ])

        print("\n✅ 依赖安装完成！")
        print("请重新运行程序\n")
        sys.exit(0)


auto_install_dependencies()

warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")



from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import dashscope
import base64
import os
import json
import uuid
from pathlib import Path
import logging
from datetime import datetime

from video_generator import VideoGenerator
from poster_module import PosterModule

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.absolute()

UPLOAD_FOLDER = BASE_DIR / 'uploads'
VIDEO_FOLDER = BASE_DIR / 'videos'
TEMPLATES_FOLDER = BASE_DIR / 'templates'
STATIC_FOLDER = BASE_DIR / 'static'
LOGS_FOLDER = BASE_DIR / 'logs'
CONFIG_FILE = BASE_DIR / 'config.json'

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['VIDEO_FOLDER'] = str(VIDEO_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024


def ensure_directories():
    """确保所有必要文件夹存在"""
    directories = [UPLOAD_FOLDER, VIDEO_FOLDER, TEMPLATES_FOLDER, STATIC_FOLDER, LOGS_FOLDER]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"📁 确保目录存在: {directory}")


ensure_directories()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_FOLDER / 'app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CORS(app)

config = {
    'dashscope_key': '',
    'gpt_image_key': '',
    'style': '高级感',
    'camera': '环绕旋转',
    'duration': 10
}

STYLE_LIGHTING = {
    "高级感": "冷色调光线，侧光勾勒轮廓，低饱和度，光影分明",
    "日系清新": "柔和自然光，明亮通透，高光柔和，低对比度",
    "电影质感": "电影色调，景深效果，胶片感，散景光斑",
    "赛博朋克": "霓虹灯光，蓝紫色调，科技感，城市夜景背景",
    "极简风格": "纯白背景，均匀布光，干净无杂物"
}

CAMERA_DESC = {
    "环绕旋转": "镜头围绕产品缓慢旋转一圈，360度全方位展示，速度均匀",
    "缓慢推镜": "开头中景展示全貌，镜头缓慢推近至产品特写，展现细节质感",
    "平稳横移": "镜头平稳横移，从左至右展现产品流线轮廓和设计语言",
    "特写拉远": "开头特写产品核心细节，缓慢拉远至全景，展现整体设计",
    "固定镜头": "固定机位，产品在画面中缓慢自转，背景保持静止",
    "跟随展示": "镜头平稳跟随产品移动轨迹，保持产品在画面中心",
    "升降镜头": "镜头从低角度缓缓升起至俯视角度，展现产品立体感"
}

video_generator = None
poster_module = None


def load_config():
    """从文件加载配置"""
    global config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config.update(saved)
                if config.get('dashscope_key'):
                    dashscope.api_key = config['dashscope_key']
            logger.info("配置加载成功")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")


def save_config_to_file():
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("配置保存成功")
    except Exception as e:
        logger.error(f"配置保存失败: {e}")


def initialize_modules():
    """初始化视频和海报生成模块"""
    global video_generator, poster_module
    video_generator = VideoGenerator(config, BASE_DIR)
    poster_module = PosterModule(config, BASE_DIR)
    logger.info("视频和海报生成模块初始化完成")


@app.route('/')
def index():
    """主页 - 返回前端界面"""
    logger.info("访问主页")
    return render_template('index.html')


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """配置管理端点"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'config': {
                'has_key': bool(config.get('dashscope_key')),
                'has_gpt_key': bool(config.get('gpt_image_key')),
                'dashscope_key': config.get('dashscope_key', ''),
                'gpt_image_key': config.get('gpt_image_key', ''),
                'style': config['style'],
                'camera': config['camera'],
                'duration': config['duration'],
                'styles': list(STYLE_LIGHTING.keys()),
                'cameras': list(CAMERA_DESC.keys())
            }
        })
    else:
        data = request.json
        if 'api_key' in data and data['api_key']:
            config['dashscope_key'] = data['api_key']
            dashscope.api_key = config['dashscope_key']
            logger.info("API Key已更新")

        if 'gpt_image_key' in data and data['gpt_image_key']:
            config['gpt_image_key'] = data['gpt_image_key']
            logger.info("GPT Image API Key已更新")

        if 'style' in data:
            config['style'] = data['style']
        if 'camera' in data:
            config['camera'] = data['camera']
        if 'duration' in data:
            config['duration'] = data['duration']

        save_config_to_file()
        return jsonify({'success': True, 'message': '配置已保存'})


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """图片上传端点"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'})

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'})

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png']:
        return jsonify({'success': False, 'error': '只支持JPG/PNG格式'})

    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_FOLDER / unique_filename

    file.save(str(filepath))
    logger.info(f"图片已保存: {filepath}")

    with open(filepath, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode()

    return jsonify({
        'success': True,
        'filepath': str(filepath),
        'image_base64': image_base64,
        'message': '上传成功'
    })


@app.route('/api/generate_prompt', methods=['POST'])
def generate_prompt():
    """生成场景描述端点（支持视频和海报两种模式）"""
    data = request.json
    image_path = data.get('image_path')
    user_desc = data.get('description', '')
    style = data.get('style', config['style'])
    camera = data.get('camera', config['camera'])
    duration = data.get('duration', config['duration'])
    mode = data.get('mode', 'video')

    if not image_path or not Path(image_path).exists():
        return jsonify({'success': False, 'error': '图片不存在'})

    if not config.get('dashscope_key'):
        return jsonify({'success': False, 'error': '请先配置API Key'})

    try:
        dashscope.api_key = config['dashscope_key']

        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()

        ext = Path(image_path).suffix.lower()
        mime_type = "image/jpeg" if ext in ['.jpg', '.jpeg'] else "image/png"

        if mode == 'poster':
            prompt = f"""你是专业AI海报设计提示词工程师，请根据产品图片生成高品质商业海报的设计提示词。

风格：{style}
光影：{STYLE_LIGHTING.get(style, '自然光')}

产品描述：{user_desc if user_desc else '请AI自主识别产品特征'}

要求：
1. 生成一段200-250字的海报设计提示词
2. 包含：主体构图、色彩搭配、文字排版建议、背景元素、氛围营造
3. 突出产品卖点，具有视觉冲击力
4. 适合商业宣传使用
5. 输出纯文本，不要序号和格式标记，直接输出可用于AI绘图的描述性文字。"""
        else:
            prompt = f"""你是专业AI视频提示词工程师，请根据产品图片生成高级感产品宣传短片提示词。

风格：{style}
运镜：{camera}
时长：{duration}秒
光影：{STYLE_LIGHTING.get(style, '自然光')}
运镜描述：{CAMERA_DESC.get(camera, '稳定镜头')}

产品描述：{user_desc if user_desc else '请AI自主识别产品特征'}

要求：生成250-300字的连贯视频提示词，包含：主体动作、光影效果、镜头语言、画质约束。
输出纯文本，不要序号和格式标记。"""

        from dashscope import MultiModalConversation
        messages = [{
            "role": "user",
            "content": [
                {"image": f"data:{mime_type};base64,{b64}"},
                {"text": prompt}
            ]
        }]

        mode_text = "海报设计" if mode == 'poster' else "视频场景"
        logger.info(f"调用通义千问生成{mode_text}提示词...")
        response = MultiModalConversation.call(model="qwen-vl-max", messages=messages)
        result_text = response.output.choices[0].message.content[0]["text"]

        return jsonify({'success': True, 'prompt': result_text})

    except Exception as e:
        logger.error(f"生成提示词失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate_video', methods=['POST'])
def generate_video():
    """生成视频端点（异步）"""
    data = request.json
    prompt = data.get('prompt')
    image_base64 = data.get('image_base64')
    duration = data.get('duration', config['duration'])

    if not config.get('dashscope_key'):
        return jsonify({'success': False, 'error': '请先配置API Key'})

    task_id = video_generator.generate_video_async(prompt, image_base64, duration)
    return jsonify({'success': True, 'task_id': task_id})


@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """查询视频任务状态"""
    result = video_generator.get_task_status(task_id)
    return jsonify(result)


@app.route('/api/generate_poster', methods=['POST'])
def generate_poster():
    """生成海报端点（异步）"""
    data = request.json
    prompt = data.get('prompt')
    image_urls = data.get('image_urls', [])

    try:
        task_id = poster_module.generate_poster_async(prompt, image_urls)
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/poster_task/<task_id>', methods=['GET'])
def get_poster_task_status(task_id):
    """查询海报任务状态"""
    result = poster_module.get_task_status(task_id)
    return jsonify(result)


@app.route('/api/download/<filename>')
def download_video(filename):
    """下载视频文件"""
    if '..' in filename or filename.startswith('/'):
        return jsonify({'success': False, 'error': '非法文件名'}), 400

    filepath = VIDEO_FOLDER / filename
    if not filepath.exists():
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    logger.info(f"下载视频: {filename}")
    return send_file(
        str(filepath),
        as_attachment=True,
        download_name=filename,
        mimetype='video/mp4'
    )


@app.route('/api/download_poster/<filename>')
def download_poster(filename):
    """下载海报文件"""
    if '..' in filename or filename.startswith('/'):
        return jsonify({'success': False, 'error': '非法文件名'}), 400

    POSTER_FOLDER = BASE_DIR / 'posters'
    filepath = POSTER_FOLDER / filename
    if not filepath.exists():
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    logger.info(f"下载海报: {filename}")
    return send_file(
        str(filepath),
        as_attachment=True,
        download_name=filename,
        mimetype='image/webp'
    )


def get_local_ip():
    """获取本机IP地址"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


if __name__ == '__main__':
    load_config()
    initialize_modules()

    local_ip = get_local_ip()
    port = 5000

    print("\n" + "=" * 60)
    print("🎬 AI产品宣传生成器 - Flask服务已启动")
    print("=" * 60)
    print(f"\n📍 本地访问: http://127.0.0.1:{port}")
    print(f"📍 局域网访问: http://{local_ip}:{port}")
    print("\n⚠️  按 Ctrl+C 停止服务\n")
    print("=" * 60 + "\n")

    import webbrowser
    webbrowser.open(f'http://127.0.0.1:{port}')

    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
