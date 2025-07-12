#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试网络对战功能
"""

import os
import sys
import time
import socket
import subprocess
import threading

def check_port_available(port):
    """检查端口是否可用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def start_local_server(port=8765):
    """启动本地服务器"""
    try:
        # 检查端口是否被占用
        if not check_port_available(port):
            return False, f"端口 {port} 已被占用", None
        
        print(f"正在启动服务器，端口: {port}")
        
        # 启动服务器进程，不使用PIPE避免阻塞
        if os.name == 'nt':  # Windows
            server_process = subprocess.Popen(
                ['python', 'server.py'],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux/Mac
            server_process = subprocess.Popen(
                ['python', 'server.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # 等待服务器启动
        print("等待服务器启动...")
        time.sleep(3)
        
        # 检查服务器是否成功启动
        if server_process.poll() is None:  # 进程仍在运行
            # 再次检查端口是否被监听
            if not check_port_available(port):
                print("✅ 服务器启动成功")
                return True, f"本地服务器已启动 (端口: {port})", server_process
            else:
                print("❌ 服务器启动失败：端口未被监听")
                return False, "服务器启动失败：端口未被监听", None
        else:
            print("❌ 服务器启动失败：进程已退出")
            return False, "服务器启动失败：进程已退出", None
            
    except Exception as e:
        print(f"❌ 启动服务器时出错: {e}")
        return False, f"启动服务器时出错: {e}", None

def test_websocket_connection(addr):
    """测试WebSocket连接"""
    try:
        import websocket
        import json
        
        print(f"测试连接到: {addr}")
        
        # 创建WebSocket连接
        ws = websocket.create_connection(addr, timeout=10)
        print("✅ WebSocket连接成功")
        
        # 测试加入房间
        join_msg = {
            "type": "join",
            "room": "test_network",
            "name": "测试玩家"
        }
        
        ws.send(json.dumps(join_msg))
        response = ws.recv()
        data = json.loads(response)
        
        if data.get("type") == "joined":
            print("✅ 房间创建成功")
            print(f"   房间号: {data.get('room')}")
            print(f"   玩家数: {data.get('player')}")
            ws.close()
            return True
        else:
            print(f"❌ 房间创建失败: {data.get('msg')}")
            ws.close()
            return False
            
    except ImportError:
        print("❌ 缺少websocket-client模块")
        return False
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

def main():
    print("=== 网络对战功能测试 ===")
    print()
    
    # 检查依赖
    try:
        import websocket
        print("✅ websocket-client模块已安装")
    except ImportError:
        print("❌ 缺少websocket-client模块，请运行: pip install websocket-client")
        return
    
    # 检查端口状态
    print("1. 检查端口状态...")
    if check_port_available(8765):
        print("✅ 端口8765可用")
    else:
        print("❌ 端口8765被占用，请先关闭占用进程")
        return
    
    # 测试自动启动服务器
    print("\n2. 测试自动启动服务器...")
    success, msg, server_process = start_local_server(8765)
    
    if not success:
        print(f"❌ 自动启动失败: {msg}")
        return
    
    print(f"✅ {msg}")
    
    # 测试WebSocket连接
    print("\n3. 测试WebSocket连接...")
    if test_websocket_connection("ws://localhost:8765"):
        print("✅ 连接测试成功")
    else:
        print("❌ 连接测试失败")
    
    # 保持运行一段时间
    print("\n4. 服务器运行测试...")
    print("服务器将运行10秒，然后自动关闭")
    
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    
    # 关闭服务器
    print("\n5. 关闭服务器...")
    if server_process:
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
            print("✅ 服务器已关闭")
        except Exception as e:
            print(f"❌ 关闭服务器时出错: {e}")
            try:
                server_process.kill()
                print("✅ 强制关闭服务器")
            except Exception:
                print("❌ 无法关闭服务器")
    
    print("\n=== 测试完成 ===")
    print("\n现在您可以在游戏中测试网络对战功能：")
    print("1. 启动游戏: python main.py")
    print("2. 选择'网络对战'")
    print("3. 选择'创建房间'")
    print("4. 游戏会自动启动本地服务器")
    print("5. 其他玩家可以加入您的房间")

if __name__ == "__main__":
    main() 