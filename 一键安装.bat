@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo    AI视频场景生成器 - Windows自动部署
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未检测到Python环境
    echo.
    choice /C YN /M "是否自动安装Python 3.11"
    if errorlevel 2 goto :manual_install
    if errorlevel 1 goto :install_python
) else (
    echo [信息] 检测到Python环境:
    python --version
    echo.
)

goto :check_dependencies

:install_python
echo.
echo [步骤1] 正在下载Python 3.11...
echo.

REM 下载Python安装包到临时目录
set PYTHON_INSTALLER=%TEMP%\python-3.11.7-amd64.exe
if not exist "%PYTHON_INSTALLER%" (
    powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe' -OutFile '%PYTHON_INSTALLER%'}"
)

echo [步骤2] 正在安装Python 3.11...
echo.
echo [提示] 请在弹出的安装窗口中勾选 "Add Python to PATH"
echo.
start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

echo.
echo [步骤3] Python安装完成，请重新运行此脚本
echo.
pause
exit /b 0

:check_dependencies
echo.
echo [步骤4] 检查并安装Python依赖包...
echo.

REM 升级pip
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

REM 安装requirements.txt中的依赖
if exist "requirements.txt" (
    echo [信息] 从requirements.txt安装依赖...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo [信息] 安装核心依赖...
    python -m pip install flask flask-cors dashscope requests Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
)

if %errorlevel% neq 0 (
    echo.
    echo [错误] 依赖安装失败，尝试使用官方源...
    python -m pip install -r requirements.txt
)

echo.
echo [成功] 所有依赖安装完成！
echo.

goto :create_shortcut

:create_shortcut
echo [步骤5] 创建桌面快捷方式...
echo.

REM 获取当前目录
set CURRENT_DIR=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\Desktop\AI视频生成器.lnk

REM 创建启动脚本
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%CURRENT_DIR%"
echo echo ========================================
echo echo    AI视频场景生成器
echo echo ========================================
echo echo.
echo echo [信息] 服务地址: http://127.0.0.1:5000
echo echo [提示] 按 Ctrl+C 停止服务
echo echo.
echo python web_app.py
echo pause
) > "%CURRENT_DIR%启动服务.bat"

echo.
echo [成功] 已创建启动脚本: 启动服务.bat
echo.

goto :start_service

:start_service
echo ========================================
echo    环境配置完成！
echo ========================================
echo.
echo [信息] 即将启动服务...
echo [信息] 浏览器将自动打开 http://127.0.0.1:5000
echo.
echo [提示] 首次使用请在网页中配置API Key
echo.
timeout /t 3 /nobreak >nul

REM 启动服务
cd /d "%CURRENT_DIR%"
python web_app.py

pause
exit /b 0

:manual_install
echo.
echo [信息] 请手动安装Python:
echo   1. 访问 https://www.python.org/downloads/
echo   2. 下载Python 3.9或更高版本
echo   3. 安装时勾选 "Add Python to PATH"
echo   4. 安装完成后重新运行此脚本
echo.
pause
exit /b 1
