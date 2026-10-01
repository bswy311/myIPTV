@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   IPTV 直播源自动检测
echo ============================================
python main.py run
echo.
echo 完成后可用 PotPlayer 打开 output\live.m3u 验证
pause
