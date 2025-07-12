import os
import pygame
from board import Board, BOARD_SIZE
from ai import AIPlayer
from piece import PieceType
import threading
import tkinter as tk
from tkinter import simpledialog
import subprocess
import time
import socket

# 中文字体加载工具
def get_chinese_font(size):
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc"
    ]
    for path in font_paths:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont("SimHei", size)

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
        time.sleep(3)
        
        # 检查服务器是否成功启动
        if server_process.poll() is None:  # 进程仍在运行
            # 再次检查端口是否被监听
            if not check_port_available(port):
                return True, f"本地服务器已启动 (端口: {port})", server_process
            else:
                # 进程在运行但端口未被监听，可能启动失败
                return False, "服务器启动失败：端口未被监听", None
        else:
            return False, "服务器启动失败：进程已退出", None
            
    except Exception as e:
        return False, f"启动服务器时出错: {e}", None

MODE_NAMES = ['行军', '建造', '拆除']
BUILD_NAMES = ['农田', '工业', '军队']

TOP_TEXT_HEIGHT = 40
BOTTOM_TEXT_HEIGHT = 100
MARGIN = 10

# 1. Game类增加网络对战相关状态
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.running = True
        self.width, self.height = self.screen.get_size()
        self.reset_btn_rect = pygame.Rect(0, 0, 120, 40)
        self.update_reset_btn_pos()
        self.show_start_menu = True
        self.player_side = 1  # 1=白, 2=黑
        self.ai_side = 2
        self.ai_difficulty = 'easy'
        self.ai = AIPlayer(self.ai_difficulty)
        self.game_mode = 'ai'  # 'ai' or 'pvp' or 'net'
        self.net_addr = ''
        self.net_room = ''
        self.net_name = ''
        self.net_waiting = False  # 网络对战等待对手
        self.net_ws = None  # websocket连接
        self.net_error = ''  # 网络错误提示
        self.net_wait_anim = 0  # 等待动画帧
        self.net_players = [None, None]  # [房主, 加入者]，dict: {'name':..., 'side':...}
        self.net_is_host = False  # 是否房主
        self.esc_down_time = None  # 记录ESC按下时间
        self.server_process = None  # 本地服务器进程
        # 字体缓存
        self.font_title = get_chinese_font(36)
        self.font_btn = get_chinese_font(24)
        self.font_hint = get_chinese_font(20)
        self.font_mid = get_chinese_font(32)
        self.font_small = get_chinese_font(18)
        self.font_ui = get_chinese_font(18)
        self.font_res = get_chinese_font(16)
        self.font_ctrl = get_chinese_font(14)
        self.font_net_btn = get_chinese_font(22)
        self.font_net_err = get_chinese_font(24)
        self.font_net_esc = get_chinese_font(20)
        self.last_side_click_time = 0  # 房主选边按钮防抖
        self.net_ready = [False, False]  # 记录双方准备状态
        # 新增：网络对战游戏状态
        self.net_current_player = 1  # 当前轮到谁
        self.net_game_step = 0  # 当前阶段
        self.net_is_my_turn = False  # 是否是我的回合
        self.net_last_action_time = 0  # 上次动作时间，防重复
        self.init_game()

    def cleanup(self):
        """清理资源，关闭服务器等"""
        # 关闭网络连接
        if self.net_ws:
            try:
                self.net_ws.close()
            except Exception:
                pass
        
        # 关闭本地服务器进程
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except Exception:
                try:
                    self.server_process.kill()
                except Exception:
                    pass

    def init_game(self):
        self.board = Board()
        self.selected = None
        self.current_player = 1  # 白先
        self.step = 0  # 0=行军, 1=建造, 2=拆除
        self.move_used = 0
        self.move_limit = self.board.get_move_limit(self.current_player)
        self.game_over = False
        self.winner = None
        self.board.reset_move_count(1)
        self.board.reset_move_count(2)
        
        # 高亮相关
        self.highlight_tower_influence = False  # 是否高亮王塔势力范围
        self.highlight_armies = False  # 是否高亮所有军队
        self.highlight_army_moves = False  # 是否高亮军队移动范围
        self.highlighted_army = None  # 高亮的军队位置
        
        # 建造相关 - 新规则：最多建两个相同的建筑，若要建三个则必须不同
        self.build_list = []  # [(x, y, build_type)]
        self.build_counts = {0: 0, 1: 0, 2: 0}  # 各类型建筑计数
        self.build_popup = None  # (x, y) 弹窗选择建筑类型
        self.build_preview = None  # (x, y, build_type)
        
        # 区域高亮
        self.highlight_farmland = False  # 高亮耕地区
        self.highlight_development = False  # 高亮开发区
        self.highlight_preparation = False  # 高亮备战区

    def update_reset_btn_pos(self):
        self.reset_btn_rect.x = self.width - 160
        self.reset_btn_rect.y = 20

    def run(self):
        import time
        clock = pygame.time.Clock()
        self.winner_btn_rect = None
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.VIDEORESIZE:
                        self.width, self.height = event.w, event.h
                        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                        self.update_reset_btn_pos()
                    if self.show_start_menu:
                        self.handle_start_menu_event(event)
                    elif self.game_mode == 'net' and self.net_waiting:
                        # 等待界面允许按ESC返回主菜单
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            self.show_start_menu = True
                            self.net_waiting = False
                            self.net_error = ''
                            self.cleanup()  # 新增，确保服务器进程关闭
                        # 如果网络连接失败，提供快速切换选项
                        elif event.type == pygame.KEYDOWN and self.net_error and "连接" in self.net_error:
                            if event.key == pygame.K_1:
                                # 切换到人机对战
                                self.game_mode = 'ai'
                                self.show_start_menu = False
                                self.ai = AIPlayer(self.ai_difficulty)
                                self.init_game()
                            elif event.key == pygame.K_2:
                                # 切换到双人对战
                                self.game_mode = 'pvp'
                                self.show_start_menu = False
                                self.init_game()
                    else:
                        # 游戏进行中或游戏结束时的键盘事件处理
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            if self.esc_down_time is None:
                                self.esc_down_time = time.time()
                        elif event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
                            self.esc_down_time = None
                        
                        # 处理游戏事件（包括键盘和鼠标）
                        self.handle_game_event(event)
                        
                        # 游戏结束时的鼠标点击处理
                        if self.game_over and self.winner_btn_rect and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            if self.winner_btn_rect.collidepoint(event.pos):
                                self.init_game()
                                self.game_over = False
                                self.winner = None
                                self.winner_btn_rect = None
                # 检查ESC长按（对局中）
                if not self.show_start_menu and not (self.game_mode == 'net' and self.net_waiting):
                    if self.esc_down_time is not None:
                        if time.time() - self.esc_down_time > 1.0:
                            self.show_start_menu = True
                            self.esc_down_time = None
                            # 网络对战时断开连接
                            if self.game_mode == 'net' and self.net_ws:
                                try:
                                    self.net_ws.close()
                                except Exception:
                                    pass
                            self.init_game()
                self.screen.fill((220, 220, 220))
                if self.show_start_menu:
                    self.draw_start_menu()
                elif self.game_mode == 'net' and self.net_waiting:
                    self.draw_net_waiting()
                    self.net_wait_anim = (self.net_wait_anim + 1) % 60
                else:
                    # 动态计算地图区域
                    board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
                    tile_size = board_pixel // BOARD_SIZE
                    offset_x = (self.width - board_pixel) // 2
                    offset_y = TOP_TEXT_HEIGHT + MARGIN
                    self.board.draw(self.screen, self.width, self.height, self.selected, self.step, self.current_player, offset_x, offset_y, board_pixel)
                    self.draw_ui()
                    if self.board.winner:
                        self.game_over = True
                        self.winner = self.board.winner
                        self.draw_winner()
                    # 仅AI模式下才自动AI回合
                    if self.game_mode == 'ai' and self.current_player == self.ai_side and not self.game_over and not self.show_start_menu:
                        self.ai_turn()
                pygame.display.flip()
                clock.tick(30)
        finally:
            self.cleanup()  # 退出时自动清理

    def handle_start_menu_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            # 网络对战按钮
            if 200 < x < 400 and 120 < y < 180:
                self.game_mode = 'net'
                return
            # 模式选择
            if 200 < x < 400 and 180 < y < 240:
                self.game_mode = 'ai'
            elif 420 < x < 620 and 180 < y < 240:
                self.game_mode = 'pvp'
            # 玩家方选择
            if 200 < x < 400 and 300 < y < 360:
                self.player_side = 1
                self.ai_side = 2
            elif 420 < x < 620 and 300 < y < 360:
                self.player_side = 2
                self.ai_side = 1
            # AI难度选择
            if 200 < x < 320 and 400 < y < 460:
                self.ai_difficulty = 'easy'
            elif 340 < x < 460 and 400 < y < 460:
                self.ai_difficulty = 'normal'
            elif 480 < x < 600 and 400 < y < 460:
                self.ai_difficulty = 'hard'
            # 开始游戏
            if hasattr(self, 'start_btn_rect') and self.start_btn_rect.collidepoint(x, y):
                if self.game_mode == 'net':
                    self.get_net_info_dialog()
                else:
                    self.ai = AIPlayer(self.ai_difficulty)
                    self.init_game()
                    self.show_start_menu = False

    def handle_game_event(self, event):
        if event.type == pygame.KEYDOWN:
            print(f"键盘事件: {event.key}")  # 调试信息
            if event.key == pygame.K_ESCAPE:
                self.show_start_menu = True
                self.cleanup()
            elif event.key == pygame.K_r:
                if self.game_mode == 'ai':
                    self.init_game()
            elif event.key == pygame.K_1:
                self.highlight_tower_influence = not self.highlight_tower_influence
                print(f"高亮王塔势力范围: {self.highlight_tower_influence}")  # 调试信息
            elif event.key == pygame.K_2:
                self.highlight_armies = not self.highlight_armies
                print(f"高亮所有军队: {self.highlight_armies}")  # 调试信息
            elif event.key == pygame.K_3:
                self.highlight_army_moves = not self.highlight_army_moves
                print(f"高亮军队移动范围: {self.highlight_army_moves}")  # 调试信息
            elif event.key == pygame.K_4:
                self.highlight_farmland = not self.highlight_farmland
                print(f"高亮耕地区: {self.highlight_farmland}")  # 调试信息
            elif event.key == pygame.K_5:
                self.highlight_development = not self.highlight_development
                print(f"高亮开发区: {self.highlight_development}")  # 调试信息
            elif event.key == pygame.K_6:
                self.highlight_preparation = not self.highlight_preparation
                print(f"高亮备战区: {self.highlight_preparation}")  # 调试信息
            elif event.key == pygame.K_SPACE:
                # 网络对战中的回合结束
                if self.game_mode == 'net' and self.net_is_my_turn:
                    self.send_game_action("end_turn")
            elif event.key == pygame.K_f:
                # 跳过当前阶段（允许未完成目标）
                if self.step == 0:  # 行军阶段
                    # 网络对战发送跳过阶段消息
                    if self.game_mode == 'net' and self.net_is_my_turn:
                        self.send_game_action("skip_phase", {
                            "from_step": 0,
                            "to_step": 1
                        })
                    
                    self.step = 1
                    self.move_used = 0
                    self.build_counts = {0: 0, 1: 0, 2: 0}
                    print(f"→ 跳过行军阶段，进入建造阶段")
                elif self.step == 1:  # 建造阶段
                    # 网络对战发送跳过阶段消息
                    if self.game_mode == 'net' and self.net_is_my_turn:
                        self.send_game_action("skip_phase", {
                            "from_step": 1,
                            "to_step": 2
                        })
                    
                    self.step = 2
                    print(f"→ 跳过建造阶段，进入拆除阶段")
                elif self.step == 2:  # 拆除阶段
                    # 网络对战发送回合结束消息
                    if self.game_mode == 'net' and self.net_is_my_turn:
                        self.send_game_action("end_turn")
                    
                    self.next_turn()
                    print("→ 回合结束，进入下一回合")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                pos = pygame.mouse.get_pos()
                self.handle_mouse(pos)

    def handle_mouse(self, pos):
        print(f"鼠标点击: {pos}, 游戏模式: {self.game_mode}, 网络回合: {self.net_is_my_turn if self.game_mode == 'net' else 'N/A'}")
        
        # 检查是否点击了重置按钮
        if self.reset_btn_rect.collidepoint(pos):
            if self.game_mode == 'ai':
                self.init_game()
            elif self.game_mode == 'net':
                # 网络对战投降
                self.game_over = True
                self.winner = 3 - self.current_player
                self.winner_btn_rect = None
            return
        
        # 网络对战检查是否是我的回合
        if self.game_mode == 'net' and not self.net_is_my_turn:
            print(f"鼠标操作被拒绝: 不是我的回合")
            return
        
        # 动态计算地图坐标，与绘制时保持一致
        board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
        tile_size = board_pixel // BOARD_SIZE
        offset_x = (self.width - board_pixel) // 2
        offset_y = TOP_TEXT_HEIGHT + MARGIN
        
        x = (pos[0] - offset_x) // tile_size
        y = (pos[1] - offset_y) // tile_size
        
        if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
            piece = self.board.get_piece(x, y)
            
            if self.step == 0:  # 行军
                self.handle_move_phase(x, y, piece)
            elif self.step == 1:  # 建造
                self.handle_build_phase(x, y, piece)
            elif self.step == 2:  # 拆除
                self.handle_remove_phase(x, y, piece)

    def handle_move_phase(self, x, y, piece):
        if self.game_mode == 'net' and not self.net_is_my_turn:
            return
        
        if self.selected:
            old_x, old_y = self.selected
            if self.board.can_move_army(old_x, old_y, x, y, self.current_player, self.move_used, self.move_limit):
                # 发送移动动作
                if self.game_mode == 'net':
                    self.send_game_action("move", {
                        "from": [old_x, old_y],
                        "to": [x, y]
                    })
                
                self.board.move_piece(old_x, old_y, x, y)
                self.selected = None
                self.move_used += 1
                
                # 检查濒危状态
                if self.board.danger[self.current_player]:
                    print(f"玩家{self.current_player}处于濒危状态！")
            else:
                self.selected = (x, y) if piece and piece.player.value == self.current_player else None
        else:
            self.selected = (x, y) if piece and piece.player.value == self.current_player else None

    def handle_build_phase(self, x, y, piece):
        if self.game_mode == 'net' and not self.net_is_my_turn:
            return
        
        if self.build_popup:
            popup_x, popup_y = self.build_popup
            # 检查是否点击了弹窗按钮 - 使用动态计算的坐标
            board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
            tile_size = board_pixel // BOARD_SIZE
            offset_x = (self.width - board_pixel) // 2
            offset_y = TOP_TEXT_HEIGHT + MARGIN
            
            # 计算弹窗位置（与绘制时保持一致）
            popup_screen_x = offset_x + popup_x * tile_size
            popup_screen_y = offset_y + popup_y * tile_size
            
            # 确保弹窗不超出屏幕边界
            popup_width = 200
            popup_height = 120
            if popup_screen_x + popup_width > self.width:
                popup_screen_x = self.width - popup_width - 10
            if popup_screen_y + popup_height > self.height - BOTTOM_TEXT_HEIGHT:
                popup_screen_y = self.height - BOTTOM_TEXT_HEIGHT - popup_height - 10
            
            popup_rect = pygame.Rect(popup_screen_x, popup_screen_y, popup_width, popup_height)
            if popup_rect.collidepoint(pygame.mouse.get_pos()):
                # 处理弹窗点击 - 使用动态计算的坐标
                mouse_x, mouse_y = pygame.mouse.get_pos()
                button_y = mouse_y - popup_screen_y
                
                # 计算按钮区域
                button_width = 50
                button_height = 30
                button_spacing = 10
                total_width = 3 * button_width + 2 * button_spacing
                start_x = popup_screen_x + (popup_width - total_width) // 2
                button_start_y = popup_screen_y + 50
                
                # 检查点击了哪个按钮
                if button_start_y <= mouse_y <= button_start_y + button_height:
                    for i in range(3):
                        button_x = start_x + i * (button_width + button_spacing)
                        if button_x <= mouse_x <= button_x + button_width:
                            build_type = i
                            break
                    else:
                        self.build_popup = None
                        return
                else:
                    self.build_popup = None
                    return
                
                if self.can_build_type(build_type):
                    # 发送建造动作
                    if self.game_mode == 'net':
                        self.send_game_action("build", {
                            "x": popup_x,
                            "y": popup_y,
                            "build_type": build_type
                        })
                    
                    self.board.build_piece(popup_x, popup_y, self.current_player, build_type)
                    self.build_counts[build_type] += 1
                else:
                    self.show_cannot_build_message()
                
                self.build_popup = None
            else:
                self.build_popup = None
        else:
            if piece and piece.side == self.current_player:
                # 检查是否可以建造
                can_build = False
                for build_type in range(3):
                    if self.can_build_type(build_type) and self.board.can_build(x, y, build_type, self.current_player):
                        can_build = True
                        break
                
                if can_build:
                    self.build_popup = (x, y)

    def handle_remove_phase(self, x, y, piece):
        if self.game_mode == 'net' and not self.net_is_my_turn:
            return
        
        if piece and piece.player.value == self.current_player:
            # 发送拆除动作
            if self.game_mode == 'net':
                self.send_game_action("remove", {
                    "x": x,
                    "y": y
                })
            
            self.board.remove_piece(x, y)

    def can_build_type(self, build_type):
        """检查是否可以建造指定类型的建筑"""
        # 规则：最多建两个相同的建筑，若要建三个则必须不同
        if self.build_counts[build_type] >= 2:
            return False
        
        # 检查总数限制
        total_builds = sum(self.build_counts.values())
        if total_builds >= 3:
            return False
        
        # 如果要建第三个，必须与前两个不同
        if total_builds == 2 and self.build_counts[build_type] > 0:
            return False
        
        return True

    def show_cannot_build_message(self):
        # 这里可以添加一个临时的提示消息
        pass

    def next_turn(self):
        """进入下一回合"""
        self.current_player = 3 - self.current_player  # 切换玩家
        self.step = 0
        self.move_used = 0
        self.move_limit = self.board.get_move_limit(self.current_player)
        self.board.reset_move_count(self.current_player)
        self.selected = None
        self.highlight_tower_influence = False
        self.highlight_armies = False
        self.highlight_army_moves = False
        self.highlighted_army = None
        # 重置区域高亮
        self.highlight_farmland = False
        self.highlight_development = False
        self.highlight_preparation = False
        # 重置建造相关状态
        self.build_list = []
        self.build_counts = {0: 0, 1: 0, 2: 0}
        self.build_preview = None
        self.build_popup = None

    def ai_turn(self):
        """AI回合"""
        pygame.time.wait(400)
        
        # 行军阶段
        if self.step == 0:
            self.move_limit = self.board.get_move_limit(self.ai_side)
            self.board.reset_move_count(self.ai_side)
            moves = self.ai.choose_move(self.board, self.ai_side, self.move_limit)
            for sx, sy, tx, ty in moves:
                self.board.move_piece(sx, sy, tx, ty)
            self.step = 1
        
        # 建造阶段
        elif self.step == 1:
            builds = self.ai.choose_build(self.board, self.ai_side)
            for x, y, build_type in builds:
                if self.board.can_build(x, y, self.ai_side, build_type):
                    self.board.build_piece(x, y, self.ai_side, build_type)
            self.step = 2
        
        # 拆除阶段
        elif self.step == 2:
            removes = self.ai.choose_remove(self.board, self.ai_side)
            for x, y in removes:
                if self.board.can_remove(x, y, self.ai_side):
                    self.board.remove_piece(x, y)
            self.next_turn()

    def finish_build_phase(self):
        """完成建造阶段"""
        self.build_list = []
        self.build_counts = {0: 0, 1: 0, 2: 0}
        self.build_preview = None
        self.build_popup = None
        self.step = 2

    def draw_build_popup(self):
        """绘制建造选择弹窗"""
        if not self.build_popup:
            return
        
        popup_x, popup_y = self.build_popup
        
        # 动态计算弹窗位置，避免与地图重叠
        board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
        tile_size = board_pixel // BOARD_SIZE
        offset_x = (self.width - board_pixel) // 2
        offset_y = TOP_TEXT_HEIGHT + MARGIN
        
        # 计算弹窗位置（在地块旁边）
        popup_screen_x = offset_x + popup_x * tile_size
        popup_screen_y = offset_y + popup_y * tile_size
        
        # 确保弹窗不超出屏幕边界
        popup_width = 200
        popup_height = 120
        if popup_screen_x + popup_width > self.width:
            popup_screen_x = self.width - popup_width - 10
        if popup_screen_y + popup_height > self.height - BOTTOM_TEXT_HEIGHT:
            popup_screen_y = self.height - BOTTOM_TEXT_HEIGHT - popup_height - 10
        
        # 绘制弹窗背景
        popup_rect = pygame.Rect(popup_screen_x, popup_screen_y, popup_width, popup_height)
        pygame.draw.rect(self.screen, (240, 240, 240), popup_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), popup_rect, 2)
        
        # 绘制标题
        font = get_chinese_font(20)
        title = font.render("选择建筑类型", True, (0, 0, 0))
        self.screen.blit(title, (popup_screen_x + 10, popup_screen_y + 10))
        
        # 绘制建筑类型按钮
        build_names = ["农田", "工业", "军队"]
        button_width = 50
        button_height = 30
        button_spacing = 10
        total_width = len(build_names) * button_width + (len(build_names) - 1) * button_spacing
        start_x = popup_screen_x + (popup_width - total_width) // 2
        
        for i in range(3):
            button_x = start_x + i * (button_width + button_spacing)
            button_y = popup_screen_y + 50
            rect = pygame.Rect(button_x, button_y, button_width, button_height)
            
            color = (200, 220, 80) if i == 0 else (180, 180, 180) if i == 1 else (220, 60, 60)
            pygame.draw.rect(self.screen, color, rect)
            if not self.can_build_type(i):
                pygame.draw.rect(self.screen, (120, 120, 120), rect, 3)
            pygame.draw.rect(self.screen, (100, 100, 100), rect, 1)
            
            text = font.render(build_names[i], True, (0, 0, 0))
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

    def draw_build_preview(self, offset_x, offset_y, tile_size):
        """绘制建造预览"""
        if not self.build_preview or self.step != 1:
            return
        
        x, y, build_type = self.build_preview
        px = offset_x + x*tile_size + tile_size//2
        py = offset_y + y*tile_size + tile_size//2
        
        # 闪烁效果
        t = pygame.time.get_ticks() // 300 % 2
        if t == 0:
            if build_type == 0:  # 农田
                color = (200, 220, 80)
                pygame.draw.circle(self.screen, color, (px, py), int(tile_size*0.27))
            elif build_type == 1:  # 工业
                color = (180, 180, 180)
                pygame.draw.rect(self.screen, color, (px-int(tile_size*0.27), py-int(tile_size*0.27), 
                                                   int(tile_size*0.54), int(tile_size*0.54)))
            elif build_type == 2:  # 军队
                points = [
                    (px, py-int(tile_size*0.3)), 
                    (px-int(tile_size*0.25), py+int(tile_size*0.2)), 
                    (px+int(tile_size*0.25), py+int(tile_size*0.2))
                ]
                color = (220, 60, 60)
                pygame.draw.polygon(self.screen, color, points)

    def draw_building_hint(self):
        """绘制建造提示"""
        if self.step == 1:
            font = get_chinese_font(16)
            hint = f'建造阶段: 最多建两个相同的建筑，若要建三个则必须不同'
            text = font.render(hint, True, (60, 120, 200))
            self.screen.blit(text, (20, self.height - BOTTOM_TEXT_HEIGHT - 25))
            
            # 显示已建造的建筑
            build_names = ["农田", "工业", "军队"]
            built_info = []
            for i in range(3):
                if self.build_counts[i] > 0:
                    built_info.append(f"{build_names[i]}:{self.build_counts[i]}")
            
            if built_info:
                text2 = font.render(f'已建: {" ".join(built_info)}', True, (80, 80, 180))
                self.screen.blit(text2, (200, self.height - BOTTOM_TEXT_HEIGHT - 25))
            
            text3 = font.render(f'总数: {sum(self.build_counts.values())}/3', True, (80, 80, 180))
            self.screen.blit(text3, (400, self.height - BOTTOM_TEXT_HEIGHT - 25))

    def draw_highlights(self, offset_x, offset_y, tile_size):
        """绘制高亮效果"""
        
        # 高亮耕地区（农田建造时）
        if self.highlight_farmland:
            for x, y in self.board.farmland_areas[self.current_player]:
                rect = pygame.Rect(offset_x + x*tile_size, offset_y + y*tile_size, tile_size, tile_size)
                s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                s.fill((200, 220, 80, 100))  # 农田色高亮
                self.screen.blit(s, rect.topleft)
        
        # 高亮开发区（工业建造时）
        if self.highlight_development:
            for x, y in self.board.development_areas[self.current_player]:
                rect = pygame.Rect(offset_x + x*tile_size, offset_y + y*tile_size, tile_size, tile_size)
                s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                s.fill((180, 180, 180, 100))  # 工业色高亮
                self.screen.blit(s, rect.topleft)
        
        # 高亮备战区（军队建造时）
        if self.highlight_preparation:
            for x, y in self.board.preparation_areas[self.current_player]:
                rect = pygame.Rect(offset_x + x*tile_size, offset_y + y*tile_size, tile_size, tile_size)
                s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                s.fill((220, 60, 60, 100))  # 军队色高亮
                self.screen.blit(s, rect.topleft)
        
        # 高亮王塔势力范围
        if self.highlight_tower_influence:
            for piece in self.board.pieces:
                if piece.type == PieceType.TOWER and piece.player.value == self.current_player:
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = piece.x + dx, piece.y + dy
                            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                                rect = pygame.Rect(offset_x + nx*tile_size, offset_y + ny*tile_size, tile_size, tile_size)
                                s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                                s.fill((255, 255, 0, 100))  # 黄色高亮
                                self.screen.blit(s, rect.topleft)
        
        # 高亮所有军队
        if self.highlight_armies:
            for piece in self.board.pieces:
                if piece.type == PieceType.ARMY and piece.player.value == self.current_player:
                    rect = pygame.Rect(offset_x + piece.x*tile_size, offset_y + piece.y*tile_size, tile_size, tile_size)
                    pygame.draw.rect(self.screen, (255, 255, 0), rect, 3)
        
        # 高亮军队移动范围（即时区）
        if self.highlight_army_moves and self.highlighted_army:
            x, y = self.highlighted_army
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                        if self.board.can_move_army(x, y, nx, ny, self.current_player, self.move_used, self.move_limit):
                            rect = pygame.Rect(offset_x + nx*tile_size, offset_y + ny*tile_size, tile_size, tile_size)
                            s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                            s.fill((0, 255, 0, 100))  # 绿色高亮
                            self.screen.blit(s, rect.topleft)

    def draw_ui(self):
        # 绘制顶部信息
        font = self.font_mid
        if self.game_mode == 'net':
            # 网络对战状态
            turn_text = f"当前玩家: {'白方' if self.current_player == 1 else '黑方'}"
            step_text = f"阶段: {MODE_NAMES[self.step]}"
            my_turn_text = "（你的回合）" if self.net_is_my_turn else "（对方回合）"
            full_text = f"{turn_text} - {step_text} {my_turn_text}"
        else:
            # 本地游戏状态
            full_text = f"当前玩家: {'白方' if self.current_player == 1 else '黑方'} - 阶段: {MODE_NAMES[self.step]}"
        
        text = font.render(full_text, True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        
        # 绘制资源信息
        self.draw_resources(10, 50)
        
        # 绘制控制提示 - 移到屏幕底部，避免与地图重叠
        self.draw_controls(10, self.height - BOTTOM_TEXT_HEIGHT + 10)
        
        # 绘制重置按钮
        self.draw_reset_btn()
        
        # 绘制危险提示
        self.draw_danger_hint()
        
        # 绘制建造提示
        if self.step == 1:
            self.draw_building_hint()
        
        # 绘制建造弹窗
        if self.build_popup:
            self.draw_build_popup()
        
        # 绘制建造预览 - 使用动态计算的坐标
        if self.build_preview:
            board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
            tile_size = board_pixel // BOARD_SIZE
            offset_x = (self.width - board_pixel) // 2
            offset_y = TOP_TEXT_HEIGHT + MARGIN
            self.draw_build_preview(offset_x, offset_y, tile_size)
        
        # 绘制高亮 - 使用动态计算的坐标
        board_pixel = min(self.width, self.height - TOP_TEXT_HEIGHT - BOTTOM_TEXT_HEIGHT) - 2*MARGIN
        tile_size = board_pixel // BOARD_SIZE
        offset_x = (self.width - board_pixel) // 2
        offset_y = TOP_TEXT_HEIGHT + MARGIN
        self.draw_highlights(offset_x, offset_y, tile_size)
        
        # 绘制胜利界面
        if self.game_over:
            self.draw_winner()

    def draw_resources(self, x, y):
        font = self.font_res
        for player in [1, 2]:
            farm = self.board.count_type(player, PieceType.FARM)
            ind = self.board.count_type(player, PieceType.INDUSTRY)
            army = self.board.count_type(player, PieceType.ARMY)
            player_name = "白方" if player == 1 else "黑方"
            color = (255, 255, 255) if player == 1 else (0, 0, 0)
            danger_text = " (濒危)" if self.board.danger[player] else ""
            text = f"{player_name}{danger_text}: 农田{farm} 工业{ind} 军队{army}"
            text_surface = font.render(text, True, color)
            self.screen.blit(text_surface, (x, y + (player-1)*20))

    def draw_controls(self, x, y):
        font = self.font_ctrl
        controls = [
            "操作提示:",
            "T - 高亮王塔势力范围",
            "A - 高亮所有军队", 
            "F - 完成当前阶段",
            "左键 - 选择/操作",
            "右键 - 取消选择"
        ]
        col_num = 2
        per_col = (len(controls) + 1) // 2
        x2 = self.width // 2 + 20
        for i, control in enumerate(controls):
            col = i // per_col
            row = i % per_col
            draw_x = x if col == 0 else x2
            draw_y = y + row * 18
            text_surface = font.render(control, True, (0, 0, 0))
            self.screen.blit(text_surface, (draw_x, draw_y))

    def draw_reset_btn(self):
        """绘制重置/投降按钮"""
        if self.show_start_menu or self.game_over or (self.game_mode == 'net' and self.net_waiting):
            return
        if self.game_mode == 'ai':
            # 只在人机对战显示“重新开始”
            pygame.draw.rect(self.screen, (200, 200, 200), self.reset_btn_rect)
            pygame.draw.rect(self.screen, (100, 100, 100), self.reset_btn_rect, 2)
            font = get_chinese_font(24)
            text = font.render("重新开始", True, (0, 0, 0))
            text_rect = text.get_rect(center=self.reset_btn_rect.center)
            self.screen.blit(text, text_rect)
        else:
            # 其他模式显示“投降”
            pygame.draw.rect(self.screen, (255, 180, 180), self.reset_btn_rect)
            pygame.draw.rect(self.screen, (180, 60, 60), self.reset_btn_rect, 2)
            font = get_chinese_font(24)
            text = font.render("投降", True, (180, 60, 60))
            text_rect = text.get_rect(center=self.reset_btn_rect.center)
            self.screen.blit(text, text_rect)

    def draw_danger_hint(self):
        """绘制濒危提示"""
        font = get_chinese_font(24)
        
        # 计算当前玩家的状态
        farm = self.board.count_type(self.current_player, PieceType.FARM)
        ind = self.board.count_type(self.current_player, PieceType.INDUSTRY)
        army = self.board.count_type(self.current_player, PieceType.ARMY)
        move_limit = self.board.get_move_limit(self.current_player)
        
        # 显示具体的濒危原因
        reasons = []
        if ind > (farm // 2):
            reasons.append(f"工业数({ind}) > 农田数/2({farm//2})")
        if army > (farm // 2):
            reasons.append(f"军队数({army}) > 农田数/2({farm//2})")
        if army > ind:
            reasons.append(f"军队数({army}) > 工业数({ind})")
        if move_limit == 0 and ind - army + 1 < 0:
            reasons.append(f"行动点不足(工业{ind}-军队{army}+1={ind-army+1})")
        
        if reasons:
            text = font.render("濒危状态！", True, (255, 0, 0))
            text_rect = text.get_rect(center=(self.width//2, 30))
            self.screen.blit(text, text_rect)
            
            # 显示具体原因
            font_small = get_chinese_font(16)
            for i, reason in enumerate(reasons):
                text = font_small.render(reason, True, (255, 0, 0))
                text_rect = text.get_rect(center=(self.width//2, 55 + i*20))
                self.screen.blit(text, text_rect)

    def draw_winner(self):
        """绘制获胜画面"""
        font = get_chinese_font(48)
        winner_name = "白方" if self.winner == 1 else "黑方"
        text = font.render(f"{winner_name}获胜！", True, (255, 215, 0))
        text_rect = text.get_rect(center=(self.width//2, self.height//2))
        self.screen.blit(text, text_rect)
        
        # 重新开始按钮
        self.winner_btn_rect = pygame.Rect(self.width//2 - 60, self.height//2 + 50, 120, 40)
        pygame.draw.rect(self.screen, (200, 200, 200), self.winner_btn_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), self.winner_btn_rect, 2)
        font = get_chinese_font(24)
        text = font.render("重新开始", True, (0, 0, 0))
        text_rect = text.get_rect(center=self.winner_btn_rect.center)
        self.screen.blit(text, text_rect)

    def draw_start_menu(self):
        font = self.font_title
        title = font.render("半数边疆", True, (0, 0, 0))
        title_rect = title.get_rect(center=(self.width//2, 60))
        self.screen.blit(title, title_rect)

        # 网络对战按钮（最顶部）
        font_btn = self.font_btn
        net_rect = pygame.Rect(200, 120, 200, 60)
        pygame.draw.rect(self.screen, (255, 255, 200), net_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), net_rect, 2)
        text = font_btn.render("网络对战", True, (0, 0, 0))
        text_rect = text.get_rect(center=net_rect.center)
        self.screen.blit(text, text_rect)

        # 其余原有内容
        # 模式选择
        mode_ai_rect = pygame.Rect(200, 200, 200, 60)
        mode_pvp_rect = pygame.Rect(420, 200, 200, 60)
        pygame.draw.rect(self.screen, (220, 220, 255), mode_ai_rect)
        pygame.draw.rect(self.screen, (220, 255, 220), mode_pvp_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), mode_ai_rect, 2)
        pygame.draw.rect(self.screen, (0, 0, 0), mode_pvp_rect, 2)
        text = font_btn.render("人机对战", True, (0, 0, 0))
        text_rect = text.get_rect(center=mode_ai_rect.center)
        self.screen.blit(text, text_rect)
        text = font_btn.render("双人对战", True, (0, 0, 0))
        text_rect = text.get_rect(center=mode_pvp_rect.center)
        self.screen.blit(text, text_rect)
        # 高亮当前模式
        if self.game_mode == 'ai':
            pygame.draw.rect(self.screen, (60, 200, 255), mode_ai_rect, 5)
        elif self.game_mode == 'net':
            pygame.draw.rect(self.screen, (60, 200, 255), net_rect, 5)
        else:
            pygame.draw.rect(self.screen, (60, 200, 255), mode_pvp_rect, 5)
        # 玩家方选择
        text = font_btn.render("选择玩家方:", True, (0, 0, 0))
        self.screen.blit(text, (200, 280))
        white_rect = pygame.Rect(200, 330, 200, 60)
        pygame.draw.rect(self.screen, (255, 255, 255), white_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), white_rect, 2)
        text = font_btn.render("白方", True, (0, 0, 0))
        text_rect = text.get_rect(center=white_rect.center)
        self.screen.blit(text, text_rect)
        if self.player_side == 1:
            pygame.draw.rect(self.screen, (255, 180, 60), white_rect, 5)
        black_rect = pygame.Rect(420, 330, 200, 60)
        pygame.draw.rect(self.screen, (0, 0, 0), black_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), black_rect, 2)
        text = font_btn.render("黑方", True, (255, 255, 255))
        text_rect = text.get_rect(center=black_rect.center)
        self.screen.blit(text, text_rect)
        if self.player_side == 2:
            pygame.draw.rect(self.screen, (255, 180, 60), black_rect, 5)
        # AI难度选择（仅AI模式下显示）
        if self.game_mode == 'ai':
            text = font_btn.render("AI难度:", True, (0, 0, 0))
            self.screen.blit(text, (200, 410))
            difficulties = [("简单", 200), ("普通", 340), ("困难", 480)]
            diff_rects = []
            for idx, (name, x) in enumerate(difficulties):
                diff_rect = pygame.Rect(x, 430, 120, 60)
                diff_rects.append(diff_rect)
                pygame.draw.rect(self.screen, (200, 200, 200), diff_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), diff_rect, 2)
                text = font_btn.render(name, True, (0, 0, 0))
                text_rect = text.get_rect(center=diff_rect.center)
                self.screen.blit(text, text_rect)
            color_map = {"easy":0, "normal":1, "hard":2}
            if self.ai_difficulty in color_map:
                idx = color_map[self.ai_difficulty]
                pygame.draw.rect(self.screen, (60, 200, 255), diff_rects[idx], 5)
        # 开始游戏按钮
        start_rect = pygame.Rect(300, 540, 200, 60)
        pygame.draw.rect(self.screen, (0, 255, 0), start_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), start_rect, 2)
        text = font_btn.render("开始游戏", True, (0, 0, 0))
        text_rect = text.get_rect(center=start_rect.center)
        self.screen.blit(text, text_rect)
        self.start_btn_rect = start_rect  # 用于点击检测

    def get_net_info_dialog(self):
        # 用tkinter弹窗选择创建/加入房间，并输入服务器地址、房间号、昵称
        def ask():
            root = tk.Tk()
            root.withdraw()
            # 先弹出选择
            import tkinter.messagebox as messagebox
            import tkinter.simpledialog as simpledialog
            
            # 显示网络对战说明
            result = messagebox.askyesno("网络对战", 
                "网络对战功能支持自动启动本地服务器。\n\n"
                "创建房间时将自动启动本地服务器，其他玩家可以加入。\n\n"
                "是否继续？")
            
            if not result:
                return
            
            mode = simpledialog.askstring("网络对战", "请选择: 输入1创建房间，输入2加入房间", initialvalue="1")
            if not mode:
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
                # 尝试启动本地服务器
                success, msg, server_process = start_local_server(8765)
                if success:
                    messagebox.showinfo("服务器启动", f"{msg}\n\n其他玩家可以使用以下地址连接:\nws://localhost:8765\nws://127.0.0.1:8765")
                    addr = "ws://localhost:8765"
                    self.server_process = server_process # 保存进程对象
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
                return
            room = simpledialog.askstring("网络对战", "房间号 (任意英文/数字)", initialvalue="room1")
            if not room:
                return
            name = simpledialog.askstring("网络对战", "昵称", initialvalue="玩家")
            if not name:
                return
            self.net_addr = addr
            self.net_room = room
            self.net_name = name
            self.game_mode = 'net'
            self.show_start_menu = False
            self.net_waiting = True
            self.net_error = ''
            self.net_wait_anim = 0
            self.net_players = [None, None]
            self.net_is_host = False
            threading.Thread(target=self.net_connect_thread, daemon=True).start()
        ask()

    def export_init_state(self):
        """导出初始地图和棋盘状态"""
        return {
            "grid": self.board.grid,
            "pieces": [
                {"type": p.type.value, "player": p.player.value, "x": p.x, "y": p.y}
                for p in self.board.pieces
            ]
        }
    def import_init_state(self, state):
        """导入初始地图和棋盘状态"""
        if not state:
            return
        self.board.grid = state.get("grid", self.board.grid)
        self.board.pieces = []
        from piece import Piece, PieceType, Player
        for p in state.get("pieces", []):
            self.board.pieces.append(Piece(PieceType(p["type"]), Player(p["player"]), p["x"], p["y"]))
        self.board.update_all_status()

    def net_connect_thread(self):
        import websocket
        import json
        import time
        try:
            ws = websocket.create_connection(
                self.net_addr, 
                timeout=30,
                ping_interval=10,
                ping_timeout=5
            )
            self.net_ws = ws
            join_msg = json.dumps({"type": "join", "room": self.net_room, "name": self.net_name})
            ws.send(join_msg)
            ws.settimeout(5)
            while True:
                try:
                    msg = ws.recv()
                    if not msg:
                        continue
                    data = json.loads(msg)
                    print(f"收到服务器消息: {data}")
                    if data.get("type") == "joined":
                        player_idx = data.get("player", 1) - 1
                        self.net_is_host = (player_idx == 0)
                        names = data.get("names", [self.net_name, ""])
                        side = data.get("side", 1)
                        self.net_players = [
                            {"name": names[0] if len(names)>0 else "", "side": side},
                            {"name": names[1] if len(names)>1 else "", "side": 3-side}
                        ]
                        self.net_ready = [False, False]
                    elif data.get("type") == "player_update":
                        names = data.get("names", [self.net_name, ""])
                        side = data.get("side", 1)
                        self.net_players = [
                            {"name": names[0] if len(names)>0 else "", "side": side},
                            {"name": names[1] if len(names)>1 else "", "side": 3-side}
                        ]
                    elif data.get("type") == "ready_update":
                        self.net_ready = data.get("ready", [False, False])
                    elif data.get("type") == "start":
                        names = data.get("names", [self.net_name, ""])
                        side = data.get("side", 1)
                        self.net_players = [
                            {"name": names[0] if len(names)>0 else "", "side": side},
                            {"name": names[1] if len(names)>1 else "", "side": 3-side}
                        ]
                        if self.net_is_host:
                            self.player_side = side
                        else:
                            self.player_side = 3 - side
                        self.net_waiting = False
                        # 初始化网络对战状态
                        self.net_current_player = data.get("current_player", 1)
                        self.net_game_step = data.get("game_step", 0)
                        self.current_player = self.net_current_player
                        self.step = self.net_game_step
                        
                        # 正确设置回合状态
                        if self.net_is_host:
                            self.player_side = side
                        else:
                            self.player_side = 3 - side
                        
                        self.net_is_my_turn = (self.player_side == self.net_current_player)
                        print(f"网络对战初始化: 玩家方={self.player_side}, 当前玩家={self.net_current_player}, 我的回合={self.net_is_my_turn}")
                        # 重置游戏状态
                        self.selected = None
                        self.move_used = 0
                        self.move_limit = self.board.get_move_limit(self.current_player)
                        self.build_list = []
                        self.build_counts = {0: 0, 1: 0, 2: 0}
                        self.build_popup = None
                        self.build_preview = None
                        self.game_over = False
                        self.winner = None
                        # 确保游戏状态正确初始化
                        self.board.reset_move_count(1)
                        self.board.reset_move_count(2)
                        self.board.update_all_status()
                        # 不要break，继续监听消息
                        continue
                    elif data.get("type") == "turn_update":
                        self.net_current_player = data.get("current_player", 1)
                        self.net_game_step = data.get("game_step", 0)
                        self.net_is_my_turn = (self.player_side == self.net_current_player)
                        self.current_player = self.net_current_player
                        self.step = self.net_game_step
                    elif data.get("type") == "game_action":
                        # 处理对方动作
                        self.handle_remote_action(data)
                    elif data.get("type") == "game_state_sync":
                        # 同步游戏状态
                        self.sync_game_state(data.get("game_state", {}))
                    elif data.get("type") == "error":
                        self.net_error = data.get("msg", "加入房间失败")
                        self.net_waiting = True
                        try:
                            ws.close()
                        except Exception:
                            pass
                        break
                    elif data.get("type") == "init_state_sync":
                        self.import_init_state(data.get("init_state"))
                except websocket.WebSocketTimeoutException:
                    continue
                except websocket.WebSocketConnectionClosedException:
                    self.net_error = "连接已断开"
                    self.net_waiting = True
                    break
        except websocket.WebSocketException as e:
            self.net_error = f"WebSocket连接失败: {e}"
            self.net_waiting = True
            print(f"WebSocket异常: {e}")
        except ConnectionRefusedError:
            self.net_error = "连接被拒绝: 服务器可能未运行或地址错误"
            self.net_waiting = True
            print("连接被拒绝")
        except Exception as e:
            self.net_error = f"连接失败: {e}" if not self.net_error else self.net_error
            self.net_waiting = True
            print(f"其他异常: {e}")
        finally:
            try:
                if self.net_ws:
                    self.net_ws.close()
            except Exception:
                pass

    def handle_remote_action(self, data):
        """处理远程玩家的动作"""
        action_type = data.get("action_type")
        action_data = data.get("action_data", {})
        player_side = data.get("player_side")
        
        print(f"处理远程动作: {action_type} from player {player_side}")
        
        if action_type == "move":
            # 处理移动动作
            from_pos = action_data.get("from")
            to_pos = action_data.get("to")
            if from_pos and to_pos:
                self.board.move_piece(from_pos[0], from_pos[1], to_pos[0], to_pos[1])
        elif action_type == "build":
            # 处理建造动作
            x, y = action_data.get("x"), action_data.get("y")
            build_type = action_data.get("build_type")
            if x is not None and y is not None and build_type is not None:
                self.board.build_piece(x, y, player_side, build_type)
        elif action_type == "remove":
            # 处理拆除动作
            x, y = action_data.get("x"), action_data.get("y")
            if x is not None and y is not None:
                self.board.remove_piece(x, y)
        elif action_type == "skip_phase":
            # 处理跳过阶段动作
            from_step = action_data.get("from_step")
            to_step = action_data.get("to_step")
            if from_step is not None and to_step is not None:
                self.step = to_step
                if from_step == 0:  # 从行军阶段跳过
                    self.move_used = 0
                    self.build_counts = {0: 0, 1: 0, 2: 0}
                    print(f"→ 对方跳过行军阶段，进入建造阶段")
                elif from_step == 1:  # 从建造阶段跳过
                    print(f"→ 对方跳过建造阶段，进入拆除阶段")
        elif action_type == "end_turn":
            # 回合结束，状态已在turn_update中更新
            pass

    def sync_game_state(self, game_state):
        """同步游戏状态"""
        if not game_state:
            return
        
        # 同步棋盘状态
        board_state = game_state.get("board")
        if board_state:
            # 这里可以根据需要同步具体的棋盘数据
            pass
        
        # 同步游戏进度
        self.current_player = game_state.get("current_player", self.current_player)
        self.step = game_state.get("step", self.step)
        self.move_used = game_state.get("move_used", self.move_used)

    def send_game_action(self, action_type, action_data=None):
        """发送游戏动作到服务器"""
        print(f"尝试发送游戏动作: {action_type}")
        print(f"网络状态: ws={self.net_ws is not None}, mode={self.game_mode}, my_turn={self.net_is_my_turn}")
        
        if not self.net_ws or self.game_mode != 'net':
            print(f"发送失败: WebSocket或游戏模式问题")
            return
        
        if not self.net_is_my_turn:
            print(f"发送失败: 不是我的回合")
            return
        
        # 防重复发送
        import time
        now = time.time()
        if now - self.net_last_action_time < 0.1:  # 100ms防抖
            print(f"发送失败: 防抖限制")
            return
        self.net_last_action_time = now
        
        try:
            import json
            message = {
                "type": "game_action",
                "action_type": action_type,
                "action_data": action_data or {}
            }
            self.net_ws.send(json.dumps(message))
            print(f"✓ 成功发送游戏动作: {action_type}")
        except Exception as e:
            print(f"✗ 发送游戏动作失败: {e}")

    def draw_net_waiting(self):
        font = self.font_mid
        
        # 错误提示优先显示
        if self.net_error:
            font2 = self.font_net_err
            err = font2.render(self.net_error, True, (200, 0, 0))
            err_rect = err.get_rect(center=(self.width//2, 80))
            self.screen.blit(err, err_rect)
            
            # 提供返回主菜单的提示
            font3 = self.font_net_esc
            back_text = "按ESC返回主菜单"
            back = font3.render(back_text, True, (100, 100, 100))
            back_rect = back.get_rect(center=(self.width//2, 120))
            self.screen.blit(back, back_rect)
            
            # 提供快速切换建议
            if "连接" in self.net_error:
                font4 = get_chinese_font(16)
                suggest_text = "快速切换：按1键切换到人机对战，按2键切换到双人对战"
                suggest = font4.render(suggest_text, True, (80, 80, 80))
                suggest_rect = suggest.get_rect(center=(self.width//2, 150))
                self.screen.blit(suggest, suggest_rect)
            else:
                # 提供建议
                font4 = get_chinese_font(16)
                suggest_text = "建议：选择人机对战或双人对战模式进行游戏"
                suggest = font4.render(suggest_text, True, (80, 80, 80))
                suggest_rect = suggest.get_rect(center=(self.width//2, 150))
                self.screen.blit(suggest, suggest_rect)
            return
        
        # 正常等待状态
        dots = '.' * ((self.net_wait_anim // 20) % 4)
        text = font.render(f"等待另一位玩家加入{dots}", True, (0, 0, 0))
        rect = text.get_rect(center=(self.width//2, 80))
        self.screen.blit(text, rect)
        
        # 玩家信息
        font2 = self.font_btn
        y0 = 160
        for idx, p in enumerate(self.net_players):
            if p:
                side_str = "白方" if p["side"] == 1 else "黑方"
                label = "房主" if idx == 0 else "玩家2"
                name = p["name"]
                ready_str = "（已准备）" if self.net_ready[idx] else "（未准备）"
                info = f"{label}: {name}（{side_str}）{ready_str}"
                t = font2.render(info, True, (0,0,0))
                self.screen.blit(t, (self.width//2-160, y0+idx*40))
        
        # 房主选边按钮
        if self.net_is_host:
            btn_font = self.font_net_btn
            btn_rect = pygame.Rect(self.width//2-60, y0+90, 120, 40)
            side = 1
            if self.net_players[0] is not None:
                side = self.net_players[0]["side"]
            btn_text = "执黑方" if side == 1 else "执白方"
            pygame.draw.rect(self.screen, (200,220,255), btn_rect)
            pygame.draw.rect(self.screen, (0,0,0), btn_rect, 2)
            t = btn_font.render(btn_text, True, (0,0,0))
            self.screen.blit(t, t.get_rect(center=btn_rect.center))
            # 鼠标点击切换执棋方（防抖）
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            import time
            now = time.time()
            if mouse[0] and btn_rect.collidepoint(mx, my):
                if now - self.last_side_click_time > 0.25:
                    new_side = 2 if side == 1 else 1
                    if self.net_players[0] is not None:
                        self.net_players[0]["side"] = new_side
                    # 发送choose_side消息
                    try:
                        if self.net_ws:
                            import json
                            self.net_ws.send(json.dumps({"type": "choose_side", "side": new_side}))
                    except Exception:
                        pass
                    self.last_side_click_time = now
        
        # 准备按钮
        my_idx = 0 if self.net_is_host else 1
        if not self.net_ready[my_idx]:
            ready_btn_rect = pygame.Rect(self.width//2-60, y0+150, 120, 40)
            pygame.draw.rect(self.screen, (180,255,180), ready_btn_rect)
            pygame.draw.rect(self.screen, (0,0,0), ready_btn_rect, 2)
            t = self.font_net_btn.render("准备", True, (0,0,0))
            self.screen.blit(t, t.get_rect(center=ready_btn_rect.center))
            mouse = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse[0] and ready_btn_rect.collidepoint(mx, my):
                if self.net_ws:
                    import json
                    if self.net_is_host:
                        # 房主先同步初始状态
                        self.net_ws.send(json.dumps({
                            "type": "init_state_sync",
                            "init_state": self.export_init_state()
                        }))
                    self.net_ws.send(json.dumps({"type": "ready"}))
        
        # ESC返回提示
        font2 = self.font_net_esc
        esc = font2.render("按ESC返回主菜单", True, (100, 100, 100))
        esc_rect = esc.get_rect(center=(self.width//2, self.height-60))
        self.screen.blit(esc, esc_rect) 