@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动局域网订阅服务（电视用 http://本机IP:8899/live.m3u 订阅）
python main.py serve
pause
