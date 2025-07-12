#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket连接测试脚本
用于诊断网络对战连接问题
"""

import websocket
import json
import time
import threading

def test_connection():
    """测试WebSocket连接"""
    print("开始测试WebSocket连接...")
    
    try:
        # 创建连接
        print("正在连接到 ws://localhost:8765...")
        ws = websocket.create_connection(
            "ws://localhost:8765",
            timeout=10,
            ping_interval=10,
            ping_timeout=5
        )
        print("✓ 连接成功建立")
        
        # 发送加入房间消息
        join_msg = {
            "type": "join",
            "room": "test_room",
            "name": "测试玩家"
        }
        print(f"发送消息: {join_msg}")
        ws.send(json.dumps(join_msg))
        print("✓ 消息已发送")
        
        # 接收响应
        print("等待服务器响应...")
        response = ws.recv()
        print(f"收到响应: {response}")
        
        data = json.loads(response)
        if data.get("type") == "joined":
            print("✓ 成功加入房间")
            print(f"房间信息: {data}")
        elif data.get("type") == "error":
            print(f"✗ 加入失败: {data.get('msg')}")
        else:
            print(f"✗ 未知响应类型: {data.get('type')}")
        
        # 关闭连接
        ws.close()
        print("✓ 连接已关闭")
        
    except websocket.WebSocketException as e:
        print(f"✗ WebSocket异常: {e}")
    except ConnectionRefusedError:
        print("✗ 连接被拒绝: 服务器可能未运行")
    except Exception as e:
        print(f"✗ 其他错误: {e}")

def test_server_status():
    """测试服务器状态"""
    print("\n检查服务器状态...")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('localhost', 8765))
        sock.close()
        
        if result == 0:
            print("✓ 端口8765正在监听")
        else:
            print("✗ 端口8765未监听")
            
    except Exception as e:
        print(f"✗ 检查端口状态失败: {e}")

if __name__ == "__main__":
    print("=== WebSocket连接测试 ===")
    test_server_status()
    test_connection()
    print("\n测试完成") 