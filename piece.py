import enum

class PieceType(enum.Enum):
    ARMY = 1      # 军队（三角形）
    FARM = 2      # 农田（圆形）
    INDUSTRY = 3  # 工业（方形）
    TOWER = 4     # 王塔（特殊）

class Player(enum.Enum):
    WHITE = 1
    BLACK = 2

class Piece:
    def __init__(self, piece_type, player, x, y):
        self.type = piece_type
        self.player = player
        self.x = x
        self.y = y
        self.move_count = 0  # 用于军队移动计数 