#!/bin/bash

echo "========================================"
echo "   AI视频场景生成器 - 自动安装启动"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python3环境"
    echo ""
    echo "请安装Python 3.7或更高版本"
    echo "Ubuntu/Debian: sudo apt-get install python3"
    echo "macOS: brew install python3"
    echo ""
    exit 1
fi

echo "[信息] 检测到Python环境"
python3 --version
echo ""

# 运行环境配置脚本
echo "[信息] 开始配置环境并启动程序..."
echo ""

python3 setup.py

# 如果setup.py执行失败，等待用户按键
if [ $? -ne 0 ]; then
    echo ""
    read -p "按Enter键退出..."
fi
