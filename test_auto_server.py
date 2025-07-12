#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试自动启动服务器功能
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
        
        # 启动服务器进程
        server_process = subprocess.Popen(
            ['python', 'server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        # 等待服务器启动
        print("等待服务器启动...")
        time.sleep(3)
        
        # 检查服务器是否成功启动
        if server_process.poll() is None:  # 进程仍在运行
            print("✅ 服务器启动成功")
            return True, f"本地服务器已启动 (端口: {port})", server_process
        else:
            print("❌ 服务器启动失败")
            return False, "服务器启动失败", None
            
    except Exception as e:
        print(f"❌ 启动服务器时出错: {e}")
        return False, f"启动服务器时出错: {e}", None

def test_server_connection(port=8765):
    """测试服务器连接"""
    try:
        import websockets
        import asyncio
        import json
        
        async def test_connect():
            uri = f"ws://localhost:{port}"
            print(f"测试连接到: {uri}")
            
            try:
                async with websockets.connect(uri, timeout=5) as websocket:
                    print("✅ 连接成功")
                    
                    # 测试加入房间
                    join_msg = {
                        "type": "join",
                        "room": "test_auto",
                        "name": "测试玩家"
                    }
                    
                    await websocket.send(json.dumps(join_msg))
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if data.get("type") == "joined":
                        print("✅ 房间创建成功")
                        print(f"   房间号: {data.get('room')}")
                        print(f"   玩家数: {data.get('player')}")
                    else:
                        print(f"❌ 房间创建失败: {data.get('msg')}")
                        
            except Exception as e:
                print(f"❌ 连接测试失败: {e}")
        
        asyncio.run(test_connect())
        
    except ImportError:
        print("❌ 缺少websockets模块，无法测试连接")
    except Exception as e:
        print(f"❌ 测试连接时出错: {e}")

def main():
    print("=== 自动启动服务器测试 ===")
    print()
    
    # 测试1: 检查端口
    print("1. 检查端口状态...")
    if check_port_available(8765):
        print("✅ 端口8765可用")
    else:
        print("❌ 端口8765被占用")
        return
    
    # 测试2: 启动服务器
    print("\n2. 启动本地服务器...")
    success, msg, server_process = start_local_server(8765)
    
    if not success:
        print(f"❌ 启动失败: {msg}")
        return
    
    print(f"✅ {msg}")
    
    # 测试3: 测试连接
    print("\n3. 测试服务器连接...")
    test_server_connection(8765)
    
    # 测试4: 保持运行一段时间
    print("\n4. 服务器运行测试...")
    print("服务器将运行10秒，然后自动关闭")
    
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    
    # 测试5: 关闭服务器
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

if __name__ == "__main__":
    main() 