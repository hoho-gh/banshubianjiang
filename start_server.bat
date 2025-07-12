@echo off
echo 启动游戏服务器...
echo.
echo 服务器地址: ws://localhost:8765
echo 其他玩家可以使用以下地址连接:
echo   - ws://localhost:8765
echo   - ws://127.0.0.1:8765
echo   - ws://[您的IP地址]:8765
echo.
echo 按 Ctrl+C 停止服务器
echo.
python server.py
pause 