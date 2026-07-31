@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Bilibili 收藏集卡片 ID 工具

bili-garb-id-spider.exe

echo.
echo 程序已经退出，按任意键关闭窗口。
pause >nul
