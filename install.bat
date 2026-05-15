@echo off
chcp 65001 >nul
title AI视频场景生成器 - 自动安装启动

echo ========================================
echo    AI视频场景生成器 - 自动安装启动
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python环境
    echo.
    echo 请先安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [信息] 检测到Python环境
python --version
echo.

REM 运行环境配置脚本
echo [信息] 开始配置环境并启动程序...
echo.

python setup.py

pause
