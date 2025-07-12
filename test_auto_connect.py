#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试自动启动服务器和连接功能
"""

import os
import sys
import time
import socket
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

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
            "room": "test_auto",
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

def simulate_game_dialog():
    """模拟游戏中的对话框"""
    root = tk.Tk()
    root.withdraw()
    
    print("=== 模拟游戏中的网络对战对话框 ===")
    
    # 显示网络对战说明
    result = messagebox.askyesno("网络对战", 
        "网络对战功能支持自动启动本地服务器。\n\n"
        "创建房间时将自动启动本地服务器，其他玩家可以加入。\n\n"
        "是否继续？")
    
    if not result:
        print("用户取消")
        return
    
    # 选择模式
    mode = simpledialog.askstring("网络对战", "请选择: 输入1创建房间，输入2加入房间", initialvalue="1")
    if not mode:
        print("用户取消")
        return
    
    mode = mode.strip()
    if mode == '1':
        is_create = True
    elif mode == '2':
        is_create = False
    else:
        messagebox.showerror("错误", "请输入1或2")
        return
    
    # 创建房间时自动启动本地服务器
    if is_create:
        print("选择创建房间，尝试自动启动服务器...")
        success, msg, server_process = start_local_server(8765)
        
        if success:
            messagebox.showinfo("服务器启动", f"{msg}\n\n其他玩家可以使用以下地址连接:\nws://localhost:8765\nws://127.0.0.1:8765")
            addr = "ws://localhost:8765"
            print("✅ 自动启动服务器成功")
        else:
            # 如果自动启动失败，询问是否手动输入地址
            retry = messagebox.askyesno("服务器启动失败", 
                f"{msg}\n\n是否手动输入服务器地址？")
            if not retry:
                return
            addr = simpledialog.askstring("网络对战", "服务器地址 (如 ws://localhost:8765)", initialvalue="ws://localhost:8765")
    else:
        addr = simpledialog.askstring("网络对战", "服务器地址 (如 ws://localhost:8765)", initialvalue="ws://localhost:8765")
    
    if not addr:
        print("用户取消")
        return
    
    room = simpledialog.askstring("网络对战", "房间号 (任意英文/数字)", initialvalue="room1")
    if not room:
        print("用户取消")
        return
    
    name = simpledialog.askstring("网络对战", "昵称", initialvalue="玩家")
    if not name:
        print("用户取消")
        return
    
    print(f"连接信息: {addr}, 房间: {room}, 昵称: {name}")
    
    # 测试连接
    print("\n=== 测试WebSocket连接 ===")
    if test_websocket_connection(addr):
        print("✅ 连接测试成功")
        messagebox.showinfo("连接成功", "WebSocket连接测试成功！")
    else:
        print("❌ 连接测试失败")
        messagebox.showerror("连接失败", "WebSocket连接测试失败，请检查服务器状态。")

def main():
    print("=== 自动启动服务器和连接测试 ===")
    print()
    
    # 检查依赖
    try:
        import websocket
        print("✅ websocket-client模块已安装")
    except ImportError:
        print("❌ 缺少websocket-client模块，请运行: pip install websocket-client")
        return
    
    # 模拟游戏对话框
    simulate_game_dialog()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main() 