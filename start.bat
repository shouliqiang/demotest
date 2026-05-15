@echo off
chcp 65001 >nul
title AI视频场景生成器

echo ========================================
echo    AI视频场景生成器
echo ========================================
echo.

echo [信息] 启动Flask服务...
echo [信息] 服务启动后会自动打开浏览器
echo [信息] 如果浏览器未自动打开，请访问 http://127.0.0.1:5000
echo.
echo [提示] 按 Ctrl+C 停止服务
echo.

python web_app.py

pause
