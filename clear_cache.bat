@echo off
chcp 65001 > nul
title YouTube转文章工具 - 缓存管理

echo ============================================================
echo YouTube转文章工具 - 缓存管理
echo ============================================================
echo.

echo 请选择操作:
echo 1. 查看缓存统计
echo 2. 清理所有缓存
echo 3. 只清理视频缓存
echo 4. 只清理英文字幕缓存
echo 5. 只清理中文字幕缓存
echo 0. 退出
echo.

set /p choice=请输入选择 (0-5): 

if "%choice%"=="1" (
    echo.
    echo 正在查看缓存统计...
    py clear_cache.py --stats
    goto end
)

if "%choice%"=="2" (
    echo.
    echo 正在清理所有缓存...
    py clear_cache.py --type all
    goto end
)

if "%choice%"=="3" (
    echo.
    echo 正在清理视频缓存...
    py clear_cache.py --type video
    goto end
)

if "%choice%"=="4" (
    echo.
    echo 正在清理英文字幕缓存...
    py clear_cache.py --type subtitle_en
    goto end
)

if "%choice%"=="5" (
    echo.
    echo 正在清理中文字幕缓存...
    py clear_cache.py --type subtitle_zh
    goto end
)

if "%choice%"=="0" (
    echo 退出
    goto end
)

echo 无效选择，请重新运行脚本
:end
pause

