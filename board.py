import pygame
import random
import math
from piece import Piece, PieceType, Player

BOARD_SIZE = 14
LAND = 0
WATER = 1
MOUNTAIN = 2

class Board:
    def __init__(self):
        self.grid = self.generate_map()
        self.pieces = []
        self.init_pieces()
        self.winner = None
        self.danger = {1: False, 2: False}  # 濒危状态
        
        # 初始化区域变量
        self.national_scope = {1: set(), 2: set()}
        self.influence = {1: set(), 2: set()}
        self.built_areas = set()
        self.forbidden_areas = set()
        self.pollution_areas = set()
        self.farmland_areas = {1: set(), 2: set()}
        self.development_areas = {1: set(), 2: set()}
        self.preparation_areas = {1: set(), 2: set()}
        
        self.update_all_status()

    def generate_map(self):
        """生成14x14地图：112块海洋，56格陆地，28格山脉"""
        # 初始化所有为海洋
        grid = [[WATER for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        all_positions = [(x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE)]
        # 先选56块陆地
        land_candidates = random.sample(all_positions, 56)
        for x, y in land_candidates:
            grid[y][x] = LAND
        # 再从这56块陆地中选28块变为山脉
        mountain_positions = random.sample(land_candidates, 28)
        for x, y in mountain_positions:
            grid[y][x] = MOUNTAIN
        return grid

    def find_tower_positions(self):
        """找到周围八格至少两块陆地的陆地，计算曼哈顿距离最大的两个作为王塔位置"""
        for _ in range(10):  # 最多尝试10次
            candidates = []
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if self.grid[y][x] == LAND:
                        # 计算周围八格陆地数量
                        land_count = 0
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                if dx == 0 and dy == 0:
                                    continue
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and self.grid[ny][nx] == LAND:
                                    land_count += 1
                        if land_count >= 2:
                            candidates.append((x, y))
            if len(candidates) >= 2:
                # 找到曼哈顿距离最大的两个位置
                max_distance = 0
                best_pair = None
                for i in range(len(candidates)):
                    for j in range(i + 1, len(candidates)):
                        x1, y1 = candidates[i]
                        x2, y2 = candidates[j]
                        distance = abs(x1 - x2) + abs(y1 - y2)
                        if distance > max_distance:
                            max_distance = distance
                            best_pair = (candidates[i], candidates[j])
                if best_pair:
                    return best_pair
            # 如果没找到，重新生成地图
            self.grid = self.generate_map()
        # 最后兜底
        return ((0, 0), (BOARD_SIZE-1, BOARD_SIZE-1))

    def init_pieces(self):
        """初始化王塔位置"""
        self.pieces = []
        tower_positions = self.find_tower_positions()
        
        # 白王塔
        white_x, white_y = tower_positions[0]
        self.pieces.append(Piece(PieceType.TOWER, Player.WHITE, white_x, white_y))
        
        # 黑王塔
        black_x, black_y = tower_positions[1]
        self.pieces.append(Piece(PieceType.TOWER, Player.BLACK, black_x, black_y))

    def get_piece(self, x, y):
        for p in self.pieces:
            if p.x == x and p.y == y:
                return p
        return None

    def get_player_pieces(self, player, ptype=None):
        return [p for p in self.pieces if p.player.value == player and (ptype is None or p.type == ptype)]

    def count_type(self, player, ptype):
        return len(self.get_player_pieces(player, ptype))

    def can_move_army(self, sx, sy, tx, ty, player, move_used, move_limit):
        """检查军队是否可以移动"""
        if self.danger[player]:
            return False
        
        piece = self.get_piece(sx, sy)
        if not piece or piece.type != PieceType.ARMY or piece.player.value != player:
            return False
        
        # 检查是否是八格移动（上下左右斜对角）
        if abs(tx-sx) > 1 or abs(ty-sy) > 1:
            return False
        
        # 检查目标位置
        target = self.get_piece(tx, ty)
        if target:
            if target.player.value == player:
                return False
            if target.type == PieceType.TOWER:
                self.winner = player
                return True
            if target.type == PieceType.ARMY:
                return True  # 吃掉对方军队
            return False
        
        # 检查地形（不能移动到禁区）
        if self.grid[ty][tx] == MOUNTAIN:
            return False
        
        # 检查是否在已建区（除了敌方建筑）
        if target and target.player.value == player:
            return False
        
        # 规则4：检查单个军队移动步数限制
        if piece.move_count >= 3:
            return False
        
        # 规则4：检查总移动步数限制
        if move_used >= move_limit:
            return False
        
        return True

    def move_piece(self, sx, sy, tx, ty):
        """移动棋子"""
        piece = self.get_piece(sx, sy)
        if piece:
            target = self.get_piece(tx, ty)
            if target and target.type in (PieceType.ARMY, PieceType.TOWER) and target.player != piece.player:
                self.pieces.remove(target)
            piece.x = tx
            piece.y = ty
            piece.move_count += 1
            
            # 规则2：移动军队后处理势力范围冲突
            self.resolve_influence_conflict()
        self.update_all_status()

    def can_build(self, x, y, player, build_type):
        """检查是否可以建造"""
        if self.get_piece(x, y) is not None:
            return False
        
        # 检查地形限制
        if build_type == 0:  # 农田
            if self.grid[y][x] != LAND:
                return False
            # 检查是否在耕地区
            if (x, y) not in self.farmland_areas[player]:
                return False
        elif build_type == 1:  # 工业
            if self.grid[y][x] not in (LAND, WATER):
                return False
            # 检查是否在开发区
            if (x, y) not in self.development_areas[player]:
                return False
        elif build_type == 2:  # 军队
            if self.grid[y][x] != LAND:
                return False
            # 检查是否在备战区
            if (x, y) not in self.preparation_areas[player]:
                return False
        
        # 检查数量限制
        farm = self.count_type(player, PieceType.FARM)
        ind = self.count_type(player, PieceType.INDUSTRY)
        army = self.count_type(player, PieceType.ARMY)
        
        if build_type == 1 and ind + 1 > (farm // 2):
            return False
        if build_type == 2 and (army + 1 > (farm // 2) or army + 1 > ind):
            return False
        
        return True

    def build_piece(self, x, y, player, build_type):
        """建造棋子"""
        if build_type == 0:
            self.pieces.append(Piece(PieceType.FARM, Player(player), x, y))
        elif build_type == 1:
            self.pieces.append(Piece(PieceType.INDUSTRY, Player(player), x, y))
            # 规则1：工业建造后摧毁上下左右四个格子的农田
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    p = self.get_piece(nx, ny)
                    if p and p.type == PieceType.FARM:
                        self.pieces.remove(p)
        elif build_type == 2:
            self.pieces.append(Piece(PieceType.ARMY, Player(player), x, y))
        
        self.update_all_status()

    def can_remove(self, x, y, player):
        """检查是否可以拆除"""
        piece = self.get_piece(x, y)
        if piece and piece.player.value == player and piece.type != PieceType.TOWER:
            return True
        return False

    def remove_piece(self, x, y):
        """拆除棋子"""
        self.pieces = [p for p in self.pieces if not (p.x == x and p.y == y)]
        self.update_all_status()

    def get_move_limit(self, player):
        """计算军队移动总数：工业数-军队数+1"""
        ind = self.count_type(player, PieceType.INDUSTRY)
        army = self.count_type(player, PieceType.ARMY)
        return max(0, ind - army + 1)

    def reset_move_count(self, player):
        """重置军队移动计数"""
        for p in self.get_player_pieces(player, PieceType.ARMY):
            p.move_count = 0

    def update_all_status(self):
        """更新所有状态"""
        # 检查濒危状态
        for player in [1, 2]:
            farm = self.count_type(player, PieceType.FARM)
            ind = self.count_type(player, PieceType.INDUSTRY)
            army = self.count_type(player, PieceType.ARMY)
            danger = False
            # 规则3：工业数量小于等于二分之一农田数，军队数小于等于工业数
            if ind > (farm // 2) or army > (farm // 2) or army > ind:
                danger = True
            # 规则4：当行动点为负数时也处于濒危状态
            if ind - army + 1 < 0:
                danger = True
            self.danger[player] = danger
        
        # 计算各种区域
        self.calc_all_areas()
        
        # 解决势力范围冲突
        self.resolve_influence_conflict()

    def calc_all_areas(self):
        """计算所有区域"""
        # 计算已建区（所有建筑位置）
        self.built_areas = set()
        for p in self.pieces:
            self.built_areas.add((p.x, p.y))
        
        # 计算国家范围（所有己方建筑周围八格的并集）
        self.national_scope = {1: set(), 2: set()}
        for player in [1, 2]:
            for p in self.get_player_pieces(player):
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = p.x + dx, p.y + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                            self.national_scope[player].add((nx, ny))
        
        # 计算势力范围（所有己方军队周围八格的并集）
        self.influence = {1: set(), 2: set()}
        for player in [1, 2]:
            for p in self.get_player_pieces(player, PieceType.ARMY):
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = p.x + dx, p.y + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                            self.influence[player].add((nx, ny))
        
        # 计算禁区（所有山脉格）
        self.forbidden_areas = set()
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self.grid[y][x] == MOUNTAIN:
                    self.forbidden_areas.add((x, y))
        
        # 计算污染区（所有工业上下左右四格减去已建区）
        self.pollution_areas = set()
        for p in self.pieces:
            if p.type == PieceType.INDUSTRY:
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nx, ny = p.x + dx, p.y + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                        if (nx, ny) not in self.built_areas:
                            self.pollution_areas.add((nx, ny))
        
        # 计算耕地区（陆地与己方国家范围并集减去已建区减去污染区减去对方势力范围）
        self.farmland_areas = {1: set(), 2: set()}
        for player in [1, 2]:
            other_player = 3 - player
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if (self.grid[y][x] == LAND and 
                        (x, y) in self.national_scope[player] and
                        (x, y) not in self.built_areas and
                        (x, y) not in self.pollution_areas and
                        (x, y) not in self.influence[other_player]):
                        self.farmland_areas[player].add((x, y))
        
        # 计算开发区（己方国家范围减去禁区减去已建区减去对方势力范围）
        self.development_areas = {1: set(), 2: set()}
        for player in [1, 2]:
            other_player = 3 - player
            for x, y in self.national_scope[player]:
                if ((x, y) not in self.forbidden_areas and
                    (x, y) not in self.built_areas and
                    (x, y) not in self.influence[other_player]):
                    self.development_areas[player].add((x, y))
        
        # 计算备战区（陆地与己方国家范围并集减去已建区）
        self.preparation_areas = {1: set(), 2: set()}
        for player in [1, 2]:
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if (self.grid[y][x] == LAND and
                        (x, y) in self.national_scope[player] and
                        (x, y) not in self.built_areas):
                        self.preparation_areas[player].add((x, y))
    
    def calc_influence(self):
        """计算势力范围（所有军队为中心3x3范围）"""
        inf = {1: set(), 2: set()}
        for player in [1, 2]:
            for p in self.get_player_pieces(player, PieceType.ARMY):
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = p.x + dx, p.y + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                            inf[player].add((nx, ny))
        return inf

    def resolve_influence_conflict(self):
        """解决势力范围冲突：规则2的实现"""
        # 重新计算势力范围
        self.influence = self.calc_influence()
        
        # 检查每个农田和工业
        to_remove = []
        to_change_owner = []
        
        for p in self.pieces:
            if p.type in (PieceType.FARM, PieceType.INDUSTRY):
                pos = (p.x, p.y)
                in_white_influence = pos in self.influence[1]
                in_black_influence = pos in self.influence[2]
                
                if in_white_influence and in_black_influence:
                    # 同时出现在双方势力范围，消失
                    to_remove.append(p)
                elif in_white_influence and not in_black_influence and p.player.value == 2:
                    # 只出现在白方势力范围，归白方
                    to_change_owner.append((p, 1))
                elif in_black_influence and not in_white_influence and p.player.value == 1:
                    # 只出现在黑方势力范围，归黑方
                    to_change_owner.append((p, 2))
        
        # 执行变更
        for p in to_remove:
            self.pieces.remove(p)
        
        for p, new_player in to_change_owner:
            p.player = Player(new_player)

    def draw(self, screen, width, height, selected=None, mode=0, current_player=1, offset_x=40, offset_y=40, board_pixel=None):
        """绘制游戏板，支持自定义偏移和区域大小"""
        if board_pixel is None:
            board_pixel = min(width, height-100) - 40*2
        tile_size = board_pixel // BOARD_SIZE
        # 势力范围高亮
        for player in [1, 2]:
            color = (255, 220, 220, 80) if player == 1 else (180, 200, 255, 80)
            for (x, y) in self.influence[player]:
                rect = pygame.Rect(offset_x + x*tile_size, offset_y + y*tile_size, tile_size, tile_size)
                s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                s.fill(color)
                screen.blit(s, rect.topleft)
        # 地形
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                rect = pygame.Rect(offset_x + x*tile_size, offset_y + y*tile_size, tile_size, tile_size)
                if self.grid[y][x] == LAND:
                    color = (180, 220, 180)
                elif self.grid[y][x] == WATER:
                    color = (120, 180, 220)
                else:
                    color = (150, 150, 150)
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, (80, 80, 80), rect, 1)
                if selected and (x, y) == selected:
                    pygame.draw.rect(screen, (255, 180, 60), rect, 4)
        # 棋子
        for piece in self.pieces:
            px = offset_x + piece.x*tile_size + tile_size//2
            py = offset_y + piece.y*tile_size + tile_size//2
            if piece.type == PieceType.ARMY:
                points = [
                    (px, py-int(tile_size*0.3)), 
                    (px-int(tile_size*0.25), py+int(tile_size*0.2)), 
                    (px+int(tile_size*0.25), py+int(tile_size*0.2))
                ]
                color = (220, 60, 60) if piece.player == Player.WHITE else (60, 60, 220)
                pygame.draw.polygon(screen, color, points)
            elif piece.type == PieceType.FARM:
                color = (200, 220, 80) if piece.player == Player.WHITE else (80, 200, 120)
                pygame.draw.circle(screen, color, (px, py), int(tile_size*0.27))
            elif piece.type == PieceType.INDUSTRY:
                color = (180, 180, 180) if piece.player == Player.WHITE else (220, 140, 60)
                pygame.draw.rect(screen, color, (px-int(tile_size*0.27), py-int(tile_size*0.27), int(tile_size*0.54), int(tile_size*0.54)))
            elif piece.type == PieceType.TOWER:
                color = (255, 255, 255) if piece.player == Player.WHITE else (0, 0, 0)
                pygame.draw.rect(screen, color, (px-int(tile_size*0.2), py-int(tile_size*0.2), int(tile_size*0.4), int(tile_size*0.4)))
                pygame.draw.rect(screen, (120, 60, 0), (px-int(tile_size*0.13), py-int(tile_size*0.13), int(tile_size*0.26), int(tile_size*0.26))) 