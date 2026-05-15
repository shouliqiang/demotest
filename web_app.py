#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import warnings


# ========== 自动检查和安装依赖 ==========
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


# 在导入其他模块前检查依赖
auto_install_dependencies()

# 屏蔽 urllib3 的 OpenSSL 警告
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

# 强制检查并处理 CentOS 7 上的 urllib3 版本问题
def _fix_urllib3_for_centos7():
    """在模块导入前强制处理 urllib3 兼容性问题"""
    try:
        import urllib3
        # 检查版本是否为 2.x
        if urllib3.__version__.startswith('2.'):
            print("⚠️  检测到 urllib3 版本过高 ({})，正在尝试修复...".format(urllib3.__version__))
            # 尝试动态卸载并重新加载低版本（高级技巧，备选）
            # 更可靠的方法是提示用户并退出
            print("❌ 请运行以下命令修复环境：")
            print("   pip3 uninstall urllib3 -y")
            print("   pip3 install 'urllib3<2.0'")

    except ImportError:
        # urllib3 未安装，忽略
        pass
    except Exception as e:
        print("⚠️  检查 urllib3 时出错: {}".format(e))

# 执行修复检查
_fix_urllib3_for_centos7()

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import dashscope
from dashscope import MultiModalConversation, VideoSynthesis
import base64
import os
import time
import json
import threading
import uuid
from pathlib import Path
import logging
from datetime import datetime

# ========== 1. 初始化Flask应用 ==========
app = Flask(__name__)

# ========== 2. 配置路径 ==========
BASE_DIR = Path(__file__).parent.absolute()

# 文件夹配置
UPLOAD_FOLDER = BASE_DIR / 'uploads'
VIDEO_FOLDER = BASE_DIR / 'videos'
TEMPLATES_FOLDER = BASE_DIR / 'templates'
STATIC_FOLDER = BASE_DIR / 'static'
LOGS_FOLDER = BASE_DIR / 'logs'
CONFIG_FILE = BASE_DIR / 'config.json'

# 应用到Flask配置
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['VIDEO_FOLDER'] = str(VIDEO_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB


# ========== 3. 创建必要文件夹 ==========
def ensure_directories():
    """确保所有必要文件夹存在"""
    directories = [UPLOAD_FOLDER, VIDEO_FOLDER, TEMPLATES_FOLDER, STATIC_FOLDER, LOGS_FOLDER]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"📁 确保目录存在: {directory}")


ensure_directories()

# ========== 4. 配置日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_FOLDER / 'app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== 5. 启用CORS ==========
CORS(app)  # 开发环境允许所有跨域

# ========== 6. 全局状态管理 ==========
# 配置存储
config = {
    'dashscope_key': '',
    'gpt_image_key': '',  # GPT Image-2 API密钥
    'style': '高级感',
    'camera': '环绕旋转',
    'duration': 10
}

# 任务存储（生产环境建议用Redis）
tasks = {}
poster_tasks = {}  # 海报任务存储
# 样式配置
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


# ========== 7. 辅助函数 ==========
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


# ========== 8. 路由定义 ==========

@app.route('/')
def index():
    """主页 - 返回前端界面"""
    logger.info("访问主页")
    return render_template('index.html')


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """配置管理端点"""
    if request.method == 'GET':
        # 返回当前配置（隐藏完整API Key）
        return jsonify({
            'success': True,
            'config': {
                'has_key': bool(config.get('dashscope_key')),
                'style': config['style'],
                'camera': config['camera'],
                'duration': config['duration'],
                'styles': list(STYLE_LIGHTING.keys()),
                'cameras': list(CAMERA_DESC.keys())
            }
        })
    else:
        # 保存配置
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

    # 检查文件类型
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png']:
        return jsonify({'success': False, 'error': '只支持JPG/PNG格式'})

    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_FOLDER / unique_filename

    # 保存文件
    file.save(str(filepath))
    logger.info(f"图片已保存: {filepath}")

    # 转换为Base64
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
    mode = data.get('mode', 'video')  # 新增：接收模式参数，默认video
    poster_size = data.get('poster_size', '1024x1024')  # 新增：海报尺寸

    if not image_path or not Path(image_path).exists():
        return jsonify({'success': False, 'error': '图片不存在'})

    if not config.get('dashscope_key'):
        return jsonify({'success': False, 'error': '请先配置API Key'})

    try:
        dashscope.api_key = config['dashscope_key']

        # 读取图片并转Base64
        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()

        ext = Path(image_path).suffix.lower()
        mime_type = "image/jpeg" if ext in ['.jpg', '.jpeg'] else "image/png"

        # 根据模式构建不同的提示词
        if mode == 'poster':
            # ====== 海报模式提示词 ======
            prompt = f"""你是专业AI海报设计提示词工程师，请根据产品图片生成高品质商业海报的设计提示词。

风格：{style}
尺寸：{poster_size}
光影：{STYLE_LIGHTING.get(style, '自然光')}

产品描述：{user_desc if user_desc else '请AI自主识别产品特征'}

要求：
1. 生成一段200-250字的海报设计提示词
2. 包含：主体构图、色彩搭配、文字排版建议、背景元素、氛围营造
3. 突出产品卖点，具有视觉冲击力
4. 适合商业宣传使用
5. 输出纯文本，不要序号和格式标记，直接输出可用于AI绘图的描述性文字。"""
        else:
            # ====== 视频模式提示词 ======
            prompt = f"""你是专业AI视频提示词工程师，请根据产品图片生成高级感产品宣传短片提示词。

风格：{style}
运镜：{camera}
时长：{duration}秒
光影：{STYLE_LIGHTING.get(style, '自然光')}
运镜描述：{CAMERA_DESC.get(camera, '稳定镜头')}

产品描述：{user_desc if user_desc else '请AI自主识别产品特征'}

要求：生成250-300字的连贯视频提示词，包含：主体动作、光影效果、镜头语言、画质约束。
输出纯文本，不要序号和格式标记。"""

        # 调用通义千问
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

    # 创建任务
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'pending',
        'progress': 0,
        'video_url': None,
        'error': None,
        'created_at': datetime.now().isoformat()
    }

    # 启动后台线程
    thread = threading.Thread(
        target=process_video_task,
        args=(task_id, prompt, image_base64, duration)
    )
    thread.daemon = True
    thread.start()

    logger.info(f"视频任务已创建: {task_id}")
    return jsonify({'success': True, 'task_id': task_id})


@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """查询任务状态"""
    if task_id not in tasks:
        return jsonify({'success': False, 'error': '任务不存在'})

    task = tasks[task_id]
    result = {
        'success': True,
        'status': task['status'],
        'progress': task.get('progress', 0)
    }

    if task['status'] == 'completed':
        result['video_url'] = task.get('video_url')
    elif task['status'] == 'failed':
        result['error'] = task.get('error')

    return jsonify(result)


@app.route('/api/download/<filename>')
def download_video(filename):
    """下载视频文件"""
    # 安全检查，防止路径遍历攻击
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


@app.route('/api/generate_poster', methods=['POST'])
def generate_poster():
    """生成海报端点（异步）"""
    data = request.json
    prompt = data.get('prompt')
    image_urls = data.get('image_urls', [])
    size = data.get('size', '1024x1024')

    if not config.get('gpt_image_key'):
        return jsonify({'success': False, 'error': '请先配置GPT Image API Key'})

    if not prompt:
        return jsonify({'success': False, 'error': '请提供提示词'})

    # 创建任务
    task_id = str(uuid.uuid4())
    poster_tasks[task_id] = {
        'status': 'pending',
        'progress': 0,
        'image_url': None,
        'error': None,
        'created_at': datetime.now().isoformat()
    }

    # 启动后台线程
    thread = threading.Thread(
        target=process_poster_task,
        args=(task_id, prompt, image_urls, size)
    )
    thread.daemon = True
    thread.start()

    logger.info(f"海报任务已创建: {task_id}")
    return jsonify({'success': True, 'task_id': task_id})


@app.route('/api/poster_task/<task_id>', methods=['GET'])
def get_poster_task_status(task_id):
    """查询海报任务状态"""
    if task_id not in poster_tasks:
        return jsonify({'success': False, 'error': '任务不存在'})

    task = poster_tasks[task_id]
    result = {
        'success': True,
        'status': task['status'],
        'progress': task.get('progress', 0)
    }

    if task['status'] == 'completed':
        result['image_url'] = task.get('image_url')
    elif task['status'] == 'failed':
        result['error'] = task.get('error')

    return jsonify(result)

# @app.route('/api/download/<filename>')
# def download_video(filename):
#     """下载视频文件"""
#     # 安全检查，防止路径遍历攻击
#     if '..' in filename or filename.startswith('/'):
#         return jsonify({'success': False, 'error': '非法文件名'}), 400
#
#     filepath = VIDEO_FOLDER / filename
#     if not filepath.exists():
#         return jsonify({'success': False, 'error': '文件不存在'}), 404
#
#     logger.info(f"下载视频: {filename}")
#     return send_file(
#         str(filepath),
#         as_attachment=True,
#         download_name=filename,
#         mimetype='video/mp4'
#     )


@app.route('/api/download_poster/<filename>')
def download_poster(filename):
    """下载海报文件"""
    # 安全检查，防止路径遍历攻击
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


# ========== 9. 后台任务处理函数 ==========
def process_video_task(task_id, prompt, image_base64, duration):
    """后台处理视频生成任务"""
    try:
        # 更新状态
        tasks[task_id]['status'] = 'running'
        tasks[task_id]['progress'] = 10

        # 准备媒体
        media = [{
            "type": "first_frame",
            "url": f"data:image/jpeg;base64,{image_base64}"
        }]

        # 提交任务
        dashscope.api_key = config['dashscope_key']
        tasks[task_id]['progress'] = 20

        logger.info(f"提交视频生成任务: {task_id}")
        response = VideoSynthesis.call(
            model="wan2.7-i2v",
            media=media,
            resolution="1080P",
            duration=duration,
            watermark=False,
            prompt=prompt,
        )

        if response.status_code != 200:
            raise Exception(f"API错误: {response.code} - {response.message}")

        remote_task_id = response.output.task_id
        tasks[task_id]['progress'] = 30

        # 轮询任务
        max_attempts = 60  # 最多5分钟
        for attempt in range(max_attempts):
            time.sleep(5)
            poll_response = VideoSynthesis.fetch(remote_task_id)
            status = poll_response.output.task_status

            # 更新进度
            progress = min(30 + (attempt * 2), 90)
            tasks[task_id]['progress'] = progress

            if status == 'SUCCEEDED':
                video_url = poll_response.output.video_url
                tasks[task_id]['progress'] = 95

                # 下载视频
                import requests
                video_response = requests.get(video_url, stream=True)
                filename = f"video_{task_id}.mp4"
                filepath = VIDEO_FOLDER / filename

                with open(filepath, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = 100
                tasks[task_id]['video_url'] = f'/api/download/{filename}'
                logger.info(f"视频生成成功: {filename}")
                return

            elif status == 'FAILED':
                error_msg = getattr(poll_response.output, 'message', '未知错误')
                raise Exception(error_msg)

        raise Exception("任务超时")

    except Exception as e:
        logger.error(f"视频任务失败 {task_id}: {e}")
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        tasks[task_id]['progress'] = 0


def process_poster_task(task_id, prompt, image_urls, size):
    """后台处理海报生成任务"""
    try:
        # 更新状态
        poster_tasks[task_id]['status'] = 'running'
        poster_tasks[task_id]['progress'] = 10

        logger.info(f"[海报任务 {task_id}] 开始处理")
        logger.info(f"[海报任务 {task_id}] 提示词: {prompt[:100]}...")
        logger.info(f"[海报任务 {task_id}] API Key配置: {'已配置' if config.get('gpt_image_key') else '未配置'}")

        # 导入海报生成器
        from poster_generator import PosterGenerator

        # 创建生成器实例
        generator = PosterGenerator(
            api_key=config['gpt_image_key'],
            base_url=config.get('gpt_image_base_url', 'https://4sapi.com')
        )

        poster_tasks[task_id]['progress'] = 30
        logger.info(f"[海报任务 {task_id}] 正在调用4sapi.com API...")

        # 调用API生成海报
        result = generator.generate_poster(
            prompt=prompt,
            image_urls=image_urls if image_urls else None,
            size=size,
            n=1
        )

        logger.info(
            f"[海报任务 {task_id}] API返回结果: success={result.get('success')}, error={result.get('error', 'None')}")

        poster_tasks[task_id]['progress'] = 70

        if result['success']:
            # 获取生成的图像
            if result['images'] and len(result['images']) > 0:
                image_item = result['images'][0]

                # 下载并保存图像
                POSTER_FOLDER = BASE_DIR / 'posters'
                POSTER_FOLDER.mkdir(parents=True, exist_ok=True)

                logger.info(f"[海报任务 {task_id}] 正在保存图像...")

                # 判断是 Base64 还是 URL
                if 'b64_json' in image_item:
                    saved_path = generator.download_and_save_image(
                        image_data=image_item['b64_json'],
                        save_dir=str(POSTER_FOLDER),
                        filename=f"poster_{task_id}.png",
                        is_base64=True
                    )
                elif 'url' in image_item:
                    saved_path = generator.download_and_save_image(
                        image_data=image_item['url'],
                        save_dir=str(POSTER_FOLDER),
                        filename=f"poster_{task_id}.webp",
                        is_base64=False
                    )
                else:
                    raise Exception("未获取到图像数据")

                if saved_path:
                    poster_tasks[task_id]['status'] = 'completed'
                    poster_tasks[task_id]['progress'] = 100
                    poster_tasks[task_id]['image_url'] = f'/api/download_poster/{Path(saved_path).name}'
                    logger.info(f"[海报任务 {task_id}] 海报生成成功: {saved_path}")

                    # 记录 AI 优化的提示词
                    if 'revised_prompt' in image_item:
                        logger.info(f"[海报任务 {task_id}] AI优化提示词: {image_item['revised_prompt'][:100]}...")
                else:
                    raise Exception("保存海报图像失败")
            else:
                raise Exception("未获取到生成的图像")
        else:
            raise Exception(result['error'])

    except Exception as e:
        logger.error(f"[海报任务 {task_id}] 任务失败: {e}", exc_info=True)
        poster_tasks[task_id]['status'] = 'failed'
        poster_tasks[task_id]['error'] = str(e)
        poster_tasks[task_id]['progress'] = 0


# ========== 10. 启动配置 ==========
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
    # 加载保存的配置
    load_config()

    # 获取本机IP
    local_ip = get_local_ip()
    port = 5000

    print("\n" + "=" * 60)
    print("🎬 AI视频场景生成器 - Flask服务已启动")
    print("=" * 60)
    print(f"\n📍 本地访问: http://127.0.0.1:{port}")
    print(f"📍 局域网访问: http://{local_ip}:{port}")
    print("\n⚠️  按 Ctrl+C 停止服务\n")
    print("=" * 60 + "\n")

    # 自动打开浏览器
    import webbrowser

    webbrowser.open(f'http://127.0.0.1:{port}')

    # 启动Flask服务
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=port,
        debug=False,  # 生产环境关闭debug
        threaded=True  # 启用多线程
    )
