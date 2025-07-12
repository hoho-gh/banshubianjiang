@echo off
title 游戏启动器
color 0A

echo ========================================
echo           游戏启动器
echo ========================================
echo.
echo 请选择要启动的服务：
echo.
echo 1. 启动服务器
echo 2. 启动游戏客户端
echo 3. 测试服务器连接
echo 4. 监控服务器状态
echo 5. 启动服务器 + 游戏客户端
echo 6. 退出
echo.
echo ========================================

:menu
set /p choice=请输入选择 (1-6): 

if "%choice%"=="1" goto start_server
if "%choice%"=="2" goto start_client
if "%choice%"=="3" goto test_server
if "%choice%"=="4" goto monitor_server
if "%choice%"=="5" goto start_both
if "%choice%"=="6" goto exit
echo 无效选择，请重新输入
goto menu

:start_server
echo.
echo 正在启动服务器...
echo 服务器地址: ws://localhost:8765
echo 按 Ctrl+C 停止服务器
echo.
python server.py
goto menu

:start_client
echo.
echo 正在启动游戏客户端...
python main.py
goto menu

:test_server
echo.
echo 正在测试服务器连接...
python test_client.py
echo.
pause
goto menu

:monitor_server
echo.
echo 正在启动服务器监控...
echo 按 Ctrl+C 停止监控
echo.
python server_monitor.py
goto menu

:start_both
echo.
echo 正在启动服务器和游戏客户端...
echo.
echo 启动服务器...
start "游戏服务器" cmd /k "python server.py"
timeout /t 3 /nobreak >nul
echo.
echo 启动游戏客户端...
start "游戏客户端" cmd /k "python main.py"
echo.
echo 服务器和客户端已启动！
echo 服务器窗口: 游戏服务器
echo 客户端窗口: 游戏客户端
echo.
pause
goto menu

:exit
echo.
echo 感谢使用游戏启动器！
echo.
pause
exit 