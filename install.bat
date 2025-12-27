@echo off
chcp 65001 > nul
title YouTube转文章工具 - 安装依赖

echo ============================================================
echo YouTube转文章工具 - 依赖安装脚本
echo ============================================================
echo.

:: 检查Python
echo [1/4] 检查Python环境...
py --version
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 升级pip
echo.
echo [2/4] 升级pip...
py -m pip install --upgrade pip

:: 安装依赖
echo.
echo [3/4] 安装依赖包...
py -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [错误] 依赖包安装失败
    pause
    exit /b 1
)

:: 创建目录
echo.
echo [4/4] 创建必要目录...
if not exist "projects" mkdir projects && echo 创建目录: projects
if not exist "temp" mkdir temp && echo 创建目录: temp
if not exist "logs" mkdir logs && echo 创建目录: logs

echo.
echo ============================================================
echo [成功] 安装完成！
echo.
echo 使用方法：
echo   双击 start.bat 启动完整版
echo   双击 quick_start.bat 快速启动
echo.
echo 或者在命令行中运行：
echo   py run_web.py
echo ============================================================
pause
