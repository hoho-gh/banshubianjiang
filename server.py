import asyncio
import websockets
import json
import logging
from typing import Dict, List, Set, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameRoom:
    def __init__(self, room_id: str, host_name: str):
        self.room_id = room_id
        self.host_name = host_name
        self.players = []  # [{"name": str, "side": int, "ws": Any}]
        self.ready = {}    # {ws: bool}
        self.max_players = 2
        self.game_started = False
        self.host_side = 1  # 房主默认执白方
        # 新增：游戏状态
        self.game_state = None  # 游戏状态数据
        self.current_player = 1  # 当前轮到谁
        self.game_step = 0  # 当前阶段：0=行军, 1=建造, 2=拆除
        self.init_state = None  # 新增，初始地图和棋盘
        
    def add_player(self, name: str, websocket: Any):
        if len(self.players) >= self.max_players:
            return False, "房间已满"
        for player in self.players:
            if player["name"] == name:
                return False, "名字已存在"
        player_side = 1 if len(self.players) == 0 else 2
        player = {
            "name": name,
            "side": player_side,
            "ws": websocket
        }
        self.players.append(player)
        self.ready[websocket] = False
        return True, "加入成功"
    
    def remove_player(self, websocket: Any):
        for i, player in enumerate(self.players):
            if player["ws"] == websocket:
                self.players.pop(i)
                self.ready.pop(websocket, None)
                return player
        return None
    
    def get_player_names(self):
        return [p["name"] for p in self.players]
    
    def get_player_sides(self):
        return [p["side"] for p in self.players]
    
    def broadcast(self, message: str, exclude_ws: Any = None):
        """向房间内所有玩家广播消息"""
        for player in self.players:
            if player["ws"] != exclude_ws:
                try:
                    asyncio.create_task(player["ws"].send(message))
                except Exception as e:
                    logger.error(f"发送消息失败: {e}")
    
    def get_player_by_ws(self, websocket: Any):
        """根据websocket获取玩家信息"""
        for player in self.players:
            if player["ws"] == websocket:
                return player
        return None

class GameServer:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.websocket_to_room: Dict[Any, str] = {}
    
    async def handle_client(self, websocket: Any, path: str):
        """处理客户端连接"""
        room_id = None
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if websocket.remote_address else "unknown"
        logger.info(f"新客户端连接: {client_addr}")
        
        try:
            async for message in websocket:
                try:
                    logger.debug(f"收到来自 {client_addr} 的消息: {message}")
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "join":
                        await self.handle_join(websocket, data)
                    elif msg_type == "choose_side":
                        await self.handle_choose_side(websocket, data)
                    elif msg_type == "start_game":
                        await self.handle_start_game(websocket, data)
                    elif msg_type == "game_action":
                        await self.handle_game_action(websocket, data)
                    elif msg_type == "ready":
                        await self.handle_ready(websocket, data)
                    elif msg_type == "game_state_sync":
                        await self.handle_game_state_sync(websocket, data)
                    elif msg_type == "init_state_sync":
                        await self.handle_init_state_sync(websocket, data)
                    else:
                        logger.warning(f"未知消息类型: {msg_type} from {client_addr}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"无效的JSON消息 from {client_addr}: {e}")
                except Exception as e:
                    logger.error(f"处理消息时出错 from {client_addr}: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端连接关闭: {client_addr}")
        except Exception as e:
            logger.error(f"处理客户端时出错 {client_addr}: {e}")
        finally:
            await self.handle_disconnect(websocket)
    
    async def handle_join(self, websocket: Any, data: Dict[str, Any]):
        """处理加入房间请求"""
        room_id = data.get("room")
        name = data.get("name")
        
        logger.info(f"收到加入请求: room={room_id}, name={name}")
        
        if not room_id or not name:
            error_msg = "房间号和名字不能为空"
            logger.warning(f"无效的加入请求: {error_msg}")
            await websocket.send(json.dumps({
                "type": "error",
                "msg": error_msg
            }))
            return
        
        if room_id not in self.rooms:
            self.rooms[room_id] = GameRoom(room_id, name)
            logger.info(f"创建房间: {room_id}, 房主: {name}")
        
        room = self.rooms[room_id]
        success, msg = room.add_player(name, websocket)
        
        if success:
            self.websocket_to_room[websocket] = room_id
            
            response = {
                "type": "joined",
                "room": room_id,
                "player": len(room.players),
                "names": room.get_player_names(),
                "side": room.host_side
            }
            logger.info(f"发送加入成功消息: {response}")
            await websocket.send(json.dumps(response))
            
            broadcast_msg = {
                "type": "player_update",
                "names": room.get_player_names(),
                "side": room.host_side
            }
            logger.info(f"广播玩家更新: {broadcast_msg}")
            room.broadcast(json.dumps(broadcast_msg))
            
            logger.info(f"玩家 {name} 成功加入房间 {room_id}")
        else:
            logger.warning(f"玩家 {name} 加入房间 {room_id} 失败: {msg}")
            await websocket.send(json.dumps({
                "type": "error",
                "msg": msg
            }))
    
    async def handle_choose_side(self, websocket: Any, data: Dict[str, Any]):
        """处理房主选择执棋方"""
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        new_side = data.get("side")
        
        if room.players and room.players[0]["ws"] == websocket:
            if new_side is not None:
                room.host_side = int(new_side)
                if room.players:
                    room.players[0]["side"] = int(new_side)
                    room.players[1]["side"] = 3 - int(new_side) if len(room.players) > 1 else 1
                
                room.broadcast(json.dumps({
                    "type": "player_update",
                    "names": room.get_player_names(),
                    "side": room.host_side
                }))
    
    async def handle_ready(self, websocket: Any, data: Dict[str, Any]):
        """处理准备消息"""
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        room.ready[websocket] = True
        
        ready_status = [room.ready.get(p["ws"], False) for p in room.players]
        room.broadcast(json.dumps({
            "type": "ready_update",
            "ready": ready_status,
            "names": room.get_player_names()
        }))
        
        if len(room.players) == 2 and all(room.ready.get(p["ws"], False) for p in room.players):
            room.game_started = True
            room.current_player = 1  # 白方先手
            room.game_step = 0  # 从行军阶段开始
            
            # 广播游戏开始
            room.broadcast(json.dumps({
                "type": "start",
                "names": room.get_player_names(),
                "side": room.host_side,
                "current_player": room.current_player,
                "game_step": room.game_step
            }))
            
            logger.info(f"房间 {room_id} 游戏开始")
    
    async def handle_game_action(self, websocket: Any, data: Dict[str, Any]):
        """处理游戏动作（移动、建造、拆除等）"""
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        if not room.game_started:
            return
        
        player = room.get_player_by_ws(websocket)
        if not player:
            return
        
        # 检查是否是当前玩家的回合
        if player["side"] != room.current_player:
            await websocket.send(json.dumps({
                "type": "error",
                "msg": "不是你的回合"
            }))
            return
        
        action_type = data.get("action_type")
        action_data = data.get("action_data", {})
        
        # 广播游戏动作给其他玩家
        broadcast_msg = {
            "type": "game_action",
            "player_side": player["side"],
            "action_type": action_type,
            "action_data": action_data
        }
        
        room.broadcast(json.dumps(broadcast_msg), exclude_ws=websocket)
        
        # 处理特殊动作（如回合结束）
        if action_type == "end_turn":
            # 切换到下一个玩家或下一个阶段
            if room.game_step < 2:  # 0=行军, 1=建造, 2=拆除
                room.game_step += 1
            else:
                room.game_step = 0
                room.current_player = 3 - room.current_player  # 切换玩家
            
            # 广播回合更新
            room.broadcast(json.dumps({
                "type": "turn_update",
                "current_player": room.current_player,
                "game_step": room.game_step
            }))
        
        logger.info(f"房间 {room_id} 玩家 {player['name']} 执行动作: {action_type}")
    
    async def handle_game_state_sync(self, websocket: Any, data: Dict[str, Any]):
        """处理游戏状态同步"""
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        if not room.game_started:
            return
        
        # 更新房间的游戏状态
        room.game_state = data.get("game_state")
        
        # 广播给其他玩家
        room.broadcast(json.dumps({
            "type": "game_state_sync",
            "game_state": room.game_state
        }), exclude_ws=websocket)
    
    async def handle_start_game(self, websocket: Any, data: Dict[str, Any]):
        """处理开始游戏请求（保留兼容性）"""
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        
        if (room.players and room.players[0]["ws"] == websocket and 
            len(room.players) == 2):
            room.game_started = True
            
            room.broadcast(json.dumps({
                "type": "start",
                "names": room.get_player_names(),
                "side": room.host_side
            }))
            
            logger.info(f"房间 {room_id} 开始游戏")
    
    async def handle_init_state_sync(self, websocket: Any, data: dict):
        room_id = self.websocket_to_room.get(websocket)
        if not room_id or room_id not in self.rooms:
            return
        room = self.rooms[room_id]
        # 只允许房主同步
        if room.players and room.players[0]["ws"] == websocket:
            room.init_state = data.get("init_state")
            # 广播给所有玩家
            for p in room.players:
                try:
                    asyncio.create_task(p["ws"].send(json.dumps({
                        "type": "init_state_sync",
                        "init_state": room.init_state
                    })))
                except Exception as e:
                    logger.error(f"发送init_state_sync失败: {e}")
    
    async def handle_disconnect(self, websocket: Any):
        """处理客户端断开连接"""
        room_id = self.websocket_to_room.get(websocket)
        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            player = room.remove_player(websocket)
            
            if player:
                logger.info(f"玩家 {player['name']} 离开房间 {room_id}")
                
                if len(room.players) == 0:
                    del self.rooms[room_id]
                    logger.info(f"删除空房间: {room_id}")
                else:
                    room.broadcast(json.dumps({
                        "type": "player_left",
                        "name": player["name"]
                    }))
        
        if websocket in self.websocket_to_room:
            del self.websocket_to_room[websocket]

async def main():
    """启动服务器"""
    server = GameServer()
    
    # 启动WebSocket服务器
    host = "localhost"
    port = 8765
    
    logger.info(f"启动游戏服务器: ws://{host}:{port}")
    logger.info("服务器已启动，等待客户端连接...")
    logger.info("客户端可以使用以下地址连接:")
    logger.info(f"  - ws://{host}:{port}")
    logger.info(f"  - ws://127.0.0.1:{port}")
    
    # 使用正确的websockets处理函数
    async def handler(websocket):
        await server.handle_client(websocket, "")
    
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # 保持服务器运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}") 