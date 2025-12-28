@echo off
chcp 65001 > nul
title YouTube转文章工具

echo ============================================================
echo YouTube转文章工具 启动脚本
echo ============================================================
echo.

:: 检查Python是否安装
echo "[检查] 检查Python环境..."
py --version > nul 2>&1
if %errorlevel% neq 0 (
    echo "[错误] 未找到Python，请先安装Python 3.8+"
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 显示Python版本
for /f "tokens=2" %%i in ('py --version 2^>^&1') do echo [信息] Python版本: %%i

:: 检查依赖是否安装
echo "[检查] 检查依赖包..."
py -c "import flask" > nul 2>&1
if %errorlevel% neq 0 (
    echo "[警告] 依赖包未安装，正在安装..."
    echo "[安装] 安装依赖包，请稍候..."
    py -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo "[错误] 依赖包安装失败，请检查网络连接"
        pause
        exit /b 1
    )
    echo "[成功] 依赖包安装完成"
)

:: 检查配置文件
echo "[检查] 检查配置文件..."
if not exist "config\config.ini" (
    echo "[错误] 配置文件不存在: config\config.ini"
    pause
    exit /b 1
)

:: 创建必要目录
echo "[准备] 创建输出目录..."
if not exist "projects" mkdir projects
if not exist "temp" mkdir temp
if not exist "logs" mkdir logs

echo.
echo "[启动] 正在启动Web服务..."
echo "[提示] Web界面将在浏览器中打开"
echo "[提示] 按 Ctrl+C 可以停止服务"
echo "[提示] 关闭此窗口也会停止服务"
echo.
echo ============================================================

:: 启动Web应用
py run_web.py

:: 如果出现错误
if %errorlevel% neq 0 (
    echo.
    echo "[错误] Web服务启动失败"
    echo "[建议] 请检查错误信息或联系技术支持"
    pause
)

