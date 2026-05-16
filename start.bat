@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置标题
title AI视频场景生成器

:: 清屏
cls

echo.
echo ========================================
echo    AI视频场景生成器 - Windows启动脚本
echo ========================================
echo.
echo [信息] 正在检查Python环境...

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo [提示] 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 显示Python版本
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [成功] %PYTHON_VERSION%
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"
echo [信息] 工作目录: %CD%
echo.

:: 检查并安装依赖
echo [信息] 检查依赖包...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [警告] 检测到缺少依赖包，正在自动安装...
    echo.
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo [成功] 依赖安装完成
    echo.
) else (
    echo [成功] 依赖包检查通过
    echo.
)

:: 检查配置文件
if not exist "config.json" (
    echo [警告] 配置文件不存在，将使用默认配置
    echo [提示] 首次运行请在网页中配置API Key
    echo.
)

echo ========================================
echo    服务即将启动...
echo ========================================
echo.
echo [信息] 本地访问地址: http://127.0.0.1:5000
echo [信息] 浏览器将自动打开
echo.
echo [提示] 按 Ctrl+C 或关闭此窗口可停止服务
echo.
echo ========================================
echo.

:: 启动Flask应用
python main.py

:: 如果程序异常退出
echo.
echo [错误] 服务已停止
pause
