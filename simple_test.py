#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单测试自动启动服务器功能
"""

import os
import sys
import time
import socket
import subprocess

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
            print(f"❌ 端口 {port} 已被占用")
            return False, f"端口 {port} 已被占用", None
        
        print(f"✅ 端口 {port} 可用")
        print(f"正在启动服务器...")
        
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

def main():
    print("=== 简单自动启动服务器测试 ===")
    print()
    
    # 测试启动服务器
    success, msg, server_process = start_local_server(8765)
    
    if success:
        print(f"✅ {msg}")
        print("服务器正在运行，按 Ctrl+C 停止测试")
        
        try:
            # 保持运行一段时间
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n用户中断测试")
        
        # 关闭服务器
        print("正在关闭服务器...")
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
    else:
        print(f"❌ 启动失败: {msg}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main() 