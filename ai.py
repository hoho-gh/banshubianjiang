import random
from piece import PieceType
from board import BOARD_SIZE

class AIPlayer:
    def __init__(self, difficulty='easy'):
        self.difficulty = difficulty

    def choose_move(self, board, player, move_limit):
        """选择军队移动"""
        moves = []
        armies = [p for p in board.get_player_pieces(player, PieceType.ARMY)]
        used = 0
        
        # 如果濒危状态，不能移动
        if board.danger[player]:
            return moves
        
        for _ in range(move_limit):
            best = None
            best_score = -9999
            
            for army in armies:
                # 检查单个军队移动步数限制
                if army.move_count >= 3:
                    continue
                    
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        tx, ty = army.x + dx, army.y + dy
                        if 0 <= tx < BOARD_SIZE and 0 <= ty < BOARD_SIZE:
                            if board.can_move_army(army.x, army.y, tx, ty, player, used, move_limit):
                                score = self.evaluate_move(board, player, army.x, army.y, tx, ty)
                                
                                if self.difficulty == 'easy':
                                    score = random.randint(0, 10)
                                elif self.difficulty == 'hard':
                                    # 高级策略：考虑位置价值
                                    score += self.evaluate_position_value(board, player, tx, ty)
                                
                                if score > best_score:
                                    best_score = score
                                    best = (army.x, army.y, tx, ty)
            
            if best:
                moves.append(best)
                used += 1
                # 临时移动棋子，防止重复
                for a in armies:
                    if a.x == best[0] and a.y == best[1]:
                        a.x, a.y = best[2], best[3]
                        a.move_count += 1
                        break
            else:
                break
        
        return moves

    def evaluate_move(self, board, player, sx, sy, tx, ty):
        """评估移动的价值"""
        score = 0
        target = board.get_piece(tx, ty)
        
        if target:
            if target.type == PieceType.TOWER and target.player.value != player:
                score = 10000  # 直接吃王塔
            elif target.type == PieceType.ARMY and target.player.value != player:
                score = 100  # 吃掉对方军队
        else:
            # 移动到空位置
            score = 1
            # 如果移动到势力范围内，加分
            if (tx, ty) in board.influence[player]:
                score += 10
        
        return score

    def evaluate_position_value(self, board, player, x, y):
        """评估位置价值"""
        score = 0
        
        # 靠近敌方王塔
        enemy_tower = [p for p in board.pieces if p.type == PieceType.TOWER and p.player.value != player]
        if enemy_tower:
            dist = abs(x - enemy_tower[0].x) + abs(y - enemy_tower[0].y)
            score -= dist * 2  # 距离越近分数越高
        
        # 保护己方建筑
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    piece = board.get_piece(nx, ny)
                    if piece and piece.player.value == player:
                        if piece.type == PieceType.FARM:
                            score += 5
                        elif piece.type == PieceType.INDUSTRY:
                            score += 8
                        elif piece.type == PieceType.TOWER:
                            score += 20
        
        return score

    def choose_build(self, board, player):
        """选择建造位置和类型"""
        builds = []
        
        # 检查濒危状态，优先补充建筑
        if board.danger[player]:
            builds = self.emergency_build(board, player)
        else:
            builds = self.strategic_build(board, player)
        
        return builds[:3]  # 最多建造3个

    def emergency_build(self, board, player):
        """濒危状态下的紧急建造"""
        builds = []
        farm = board.count_type(player, PieceType.FARM)
        ind = board.count_type(player, PieceType.INDUSTRY)
        army = board.count_type(player, PieceType.ARMY)
        
        # 优先建造农田
        if ind > (farm // 2):
            builds.extend(self.find_build_positions(board, player, 0, 2))
        
        # 然后建造工业
        if army > ind:
            builds.extend(self.find_build_positions(board, player, 1, 1))
        
        return builds

    def strategic_build(self, board, player):
        """战略建造"""
        builds = []
        
        # 优先建造农田
        builds.extend(self.find_build_positions(board, player, 0, 1))
        
        # 然后建造工业
        builds.extend(self.find_build_positions(board, player, 1, 1))
        
        # 最后建造军队
        builds.extend(self.find_build_positions(board, player, 2, 1))
        
        return builds

    def find_build_positions(self, board, player, build_type, count):
        """寻找建造位置"""
        positions = []
        
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if board.can_build(x, y, player, build_type):
                    score = self.evaluate_build_position(board, player, x, y, build_type)
                    positions.append((x, y, build_type, score))
        
        # 按分数排序
        positions.sort(key=lambda p: p[3], reverse=True)
        
        return [(x, y, build_type) for x, y, build_type, _ in positions[:count]]

    def evaluate_build_position(self, board, player, x, y, build_type):
        """评估建造位置的价值"""
        score = 0
        
        # 靠近己方王塔
        own_tower = [p for p in board.pieces if p.type == PieceType.TOWER and p.player.value == player]
        if own_tower:
            dist = abs(x - own_tower[0].x) + abs(y - own_tower[0].y)
            score += (10 - dist) * 2
        
        # 远离敌方王塔
        enemy_tower = [p for p in board.pieces if p.type == PieceType.TOWER and p.player.value != player]
        if enemy_tower:
            dist = abs(x - enemy_tower[0].x) + abs(y - enemy_tower[0].y)
            score += dist
        
        # 根据建筑类型调整分数
        if build_type == 0:  # 农田
            # 农田最好建在远离工业的地方
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                        piece = board.get_piece(nx, ny)
                        if piece and piece.type == PieceType.INDUSTRY:
                            score -= 20
        elif build_type == 1:  # 工业
            # 工业可以建在海洋上，靠近农田
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                        piece = board.get_piece(nx, ny)
                        if piece and piece.type == PieceType.FARM:
                            score += 10
        elif build_type == 2:  # 军队
            # 军队最好建在靠近敌方的地方
            enemy_tower = [p for p in board.pieces if p.type == PieceType.TOWER and p.player.value != player]
            if enemy_tower:
                dist = abs(x - enemy_tower[0].x) + abs(y - enemy_tower[0].y)
                score += (20 - dist) * 3
        
        return score

    def choose_remove(self, board, player):
        """选择拆除的棋子"""
        removes = []
        
        # 检查是否需要拆除以维持平衡
        farm = board.count_type(player, PieceType.FARM)
        ind = board.count_type(player, PieceType.INDUSTRY)
        army = board.count_type(player, PieceType.ARMY)
        
        # 如果工业过多，拆除工业
        if ind > (farm // 2):
            for p in board.get_player_pieces(player, PieceType.INDUSTRY):
                if board.can_remove(p.x, p.y, player):
                    removes.append((p.x, p.y))
                    break
        
        # 如果军队过多，拆除军队
        if army > (farm // 2) or army > ind:
            for p in board.get_player_pieces(player, PieceType.ARMY):
                if board.can_remove(p.x, p.y, player):
                    removes.append((p.x, p.y))
                    break
        
        # 如果没有紧急需要，拆除价值最低的棋子
        if not removes:
            pieces = []
            for p in board.get_player_pieces(player):
                if p.type != PieceType.TOWER and board.can_remove(p.x, p.y, player):
                    value = self.evaluate_piece_value(board, player, p)
                    pieces.append((p.x, p.y, value))
            
            # 按价值排序，拆除价值最低的
            pieces.sort(key=lambda p: p[2])
            removes = [(x, y) for x, y, _ in pieces[:2]]
        
        return removes

    def evaluate_piece_value(self, board, player, piece):
        """评估棋子的价值"""
        value = 0
        
        if piece.type == PieceType.FARM:
            value = 10
        elif piece.type == PieceType.INDUSTRY:
            value = 15
        elif piece.type == PieceType.ARMY:
            value = 20
            # 军队位置越靠近敌方王塔价值越高
            enemy_tower = [p for p in board.pieces if p.type == PieceType.TOWER and p.player.value != player]
            if enemy_tower:
                dist = abs(piece.x - enemy_tower[0].x) + abs(piece.y - enemy_tower[0].y)
                value += (20 - dist)
        
        return value 