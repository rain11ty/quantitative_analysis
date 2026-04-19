@echo off
chcp 65001 >nul
echo ============================================
echo   股票量化分析系统 - Docker 停止脚本
echo ============================================
echo.

cd /d "%~dp0"

echo 正在停止所有服务...
docker compose -f docker-compose.dev.yml down

echo.
echo ============================================
echo   ✅ 所有服务已停止
echo ============================================
echo.

pause
