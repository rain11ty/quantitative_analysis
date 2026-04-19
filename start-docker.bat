@echo off
chcp 65001 >nul
echo ============================================
echo   股票量化分析系统 - Docker 启动脚本
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 构建并启动所有服务...
docker compose -f docker-compose.dev.yml up -d --build
if %errorlevel% neq 0 (
    echo.
    echo ❌ 启动失败！请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo [2/3] 等待服务就绪...
timeout /t 3 /nobreak >nul

echo.
echo [3/3] 检查容器状态...
docker compose -f docker-compose.dev.yml ps

echo.
echo ============================================
echo   ✅ 启动完成！
echo   访问地址: http://localhost:5001
echo ============================================

echo.
echo 常用命令:
echo   查看日志:   docker logs stock-analysis-web
echo   停止服务:   stop-docker.bat
echo   重启服务:   双击本脚本即可
echo.

pause
