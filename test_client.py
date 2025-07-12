import asyncio
import websockets
import json
import sys

async def test_client():
    """测试客户端连接"""
    uri = "ws://localhost:8765"
    
    try:
        print(f"正在连接到服务器: {uri}")
        async with websockets.connect(uri) as websocket:
            print("连接成功！")
            
            # 测试加入房间
            join_message = {
                "type": "join",
                "room": "test123",
                "name": "测试玩家"
            }
            
            print(f"发送加入房间消息: {join_message}")
            await websocket.send(json.dumps(join_message))
            
            # 等待服务器响应
            response = await websocket.recv()
            data = json.loads(response)
            print(f"服务器响应: {data}")
            
            if data.get("type") == "joined":
                print("成功加入房间！")
                print(f"房间号: {data.get('room')}")
                print(f"玩家数量: {data.get('player')}")
                print(f"玩家列表: {data.get('names')}")
                print(f"房主执棋方: {data.get('side')}")
            else:
                print(f"加入房间失败: {data.get('msg')}")
            
            # 保持连接一段时间
            print("保持连接10秒...")
            await asyncio.sleep(10)
            
    except ConnectionRefusedError:
        print("连接被拒绝，请确保服务器正在运行")
    except Exception as e:
        print(f"连接失败: {e}")

if __name__ == "__main__":
    print("=== 游戏服务器测试客户端 ===")
    print("此客户端将测试与服务器的连接")
    print()
    
    try:
        asyncio.run(test_client())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试失败: {e}")
    
    print("测试完成") 