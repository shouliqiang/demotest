
# -*- coding: utf-8 -*-
"""
视频生成模块 - 处理AI视频生成的所有功能
"""

import os
import time
import base64
import logging
import threading
import uuid
from pathlib import Path
from datetime import datetime
import requests
from dashscope import VideoSynthesis

logger = logging.getLogger(__name__)


class VideoGenerator:
    """视频生成器类"""

    def __init__(self, config, base_dir):
        """
        初始化视频生成器

        Args:
            config: 配置字典
            base_dir: 基础目录路径
        """
        self.config = config
        self.base_dir = Path(base_dir)
        self.video_folder = self.base_dir / 'videos'
        self.tasks = {}

        # 确保视频文件夹存在
        self.video_folder.mkdir(parents=True, exist_ok=True)

    def generate_video_async(self, prompt, image_base64, duration):
        """
        异步生成视频

        Args:
            prompt: 视频提示词
            image_base64: 图片base64编码
            duration: 视频时长

        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'video_url': None,
            'error': None,
            'created_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=self._process_video_task,
            args=(task_id, prompt, image_base64, duration)
        )
        thread.daemon = True
        thread.start()

        logger.info(f"视频任务已创建: {task_id}")
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
            result['video_url'] = task.get('video_url')
        elif task['status'] == 'failed':
            result['error'] = task.get('error')

        return result

    def _process_video_task(self, task_id, prompt, image_base64, duration):
        """后台处理视频生成任务"""
        try:
            self.tasks[task_id]['status'] = 'running'
            self.tasks[task_id]['progress'] = 10

            media = [{
                "type": "first_frame",
                "url": f"data:image/jpeg;base64,{image_base64}"
            }]

            import dashscope
            dashscope.api_key = self.config['dashscope_key']
            self.tasks[task_id]['progress'] = 20

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
            self.tasks[task_id]['progress'] = 30

            max_attempts = 60
            for attempt in range(max_attempts):
                time.sleep(5)
                poll_response = VideoSynthesis.fetch(remote_task_id)
                status = poll_response.output.task_status

                progress = min(30 + (attempt * 2), 90)
                self.tasks[task_id]['progress'] = progress

                if status == 'SUCCEEDED':
                    video_url = poll_response.output.video_url
                    self.tasks[task_id]['progress'] = 95

                    video_response = requests.get(video_url, stream=True)
                    filename = f"video_{task_id}.mp4"
                    filepath = self.video_folder / filename

                    with open(filepath, 'wb') as f:
                        for chunk in video_response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    self.tasks[task_id]['status'] = 'completed'
                    self.tasks[task_id]['progress'] = 100
                    self.tasks[task_id]['video_url'] = f'/api/download/{filename}'
                    logger.info(f"视频生成成功: {filename}")
                    return

                elif status == 'FAILED':
                    error_msg = getattr(poll_response.output, 'message', '未知错误')
                    raise Exception(error_msg)

            raise Exception("任务超时")

        except Exception as e:
            logger.error(f"视频任务失败 {task_id}: {e}")
            self.tasks[task_id]['status'] = 'failed'
            self.tasks[task_id]['error'] = str(e)
            self.tasks[task_id]['progress'] = 0
