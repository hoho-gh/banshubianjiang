import asyncio
import websockets
import json
import time
from datetime import datetime

async def monitor_server():
    """监控服务器状态"""
    uri = "ws://localhost:8765"
    
    print("=== 游戏服务器监控 ===")
    print(f"监控地址: {uri}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 服务器连接正常")
            
            # 测试基本功能
            print("\n🔍 测试房间功能...")
            
            # 测试1：创建房间
            await websocket.send(json.dumps({
                "type": "join",
                "room": "monitor_test",
                "name": "监控器"
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "joined":
                print("✅ 房间创建成功")
                print(f"   房间号: {data.get('room')}")
                print(f"   玩家数: {data.get('player')}")
            else:
                print(f"❌ 房间创建失败: {data.get('msg')}")
            
            # 测试2：选择执棋方
            await websocket.send(json.dumps({
                "type": "choose_side",
                "side": 2
            }))
            
            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(response)
                if data.get("type") == "player_update":
                    print("✅ 执棋方选择功能正常")
                else:
                    print(f"⚠️  执棋方选择响应: {data}")
            except asyncio.TimeoutError:
                print("⚠️  执棋方选择响应超时")
            
            # 测试3：游戏动作
            await websocket.send(json.dumps({
                "type": "game_action",
                "action": "test",
                "data": {"test": "data"}
            }))
            
            print("✅ 游戏动作发送成功")
            
            # 保持连接并监控
            print("\n📊 开始实时监控...")
            print("按 Ctrl+C 停止监控")
            
            start_time = time.time()
            message_count = 0
            
            while True:
                try:
                    # 发送心跳
                    await websocket.send(json.dumps({
                        "type": "ping",
                        "timestamp": time.time()
                    }))
                    
                    # 等待响应
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    message_count += 1
                    
                    current_time = time.time()
                    uptime = current_time - start_time
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"运行时间: {uptime:.1f}s, "
                          f"消息数: {message_count}, "
                          f"最新消息: {data.get('type', 'unknown')}")
                    
                    await asyncio.sleep(5)  # 每5秒检查一次
                    
                except asyncio.TimeoutError:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  心跳超时")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 监控错误: {e}")
                    break
                    
    except ConnectionRefusedError:
        print("❌ 无法连接到服务器，请确保服务器正在运行")
    except Exception as e:
        print(f"❌ 连接失败: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(monitor_server())
    except KeyboardInterrupt:
        print("\n\n🛑 监控已停止")
        print("服务器监控完成")
    except Exception as e:
        print(f"\n❌ 监控程序错误: {e}") 