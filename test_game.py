#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
势域争霸游戏测试脚本
用于验证游戏的核心功能是否正常工作
"""

import pygame
from board import Board, BOARD_SIZE
from piece import PieceType, Player

def test_board_generation():
    """测试地图生成功能"""
    print("测试地图生成...")
    board = Board()
    
    # 检查地图大小
    assert len(board.grid) == BOARD_SIZE, f"地图高度应该是{BOARD_SIZE}"
    assert len(board.grid[0]) == BOARD_SIZE, f"地图宽度应该是{BOARD_SIZE}"
    
    # 检查地形分布
    water_count = sum(1 for row in board.grid for cell in row if cell == 1)
    land_count = sum(1 for row in board.grid for cell in row if cell == 0)
    mountain_count = sum(1 for row in board.grid for cell in row if cell == 2)
    
    print(f"海洋数量: {water_count} (期望: 112)")
    print(f"陆地数量: {land_count} (期望: 56)")
    print(f"山脉数量: {mountain_count} (期望: 28)")
    
    # 检查王塔位置
    towers = [p for p in board.pieces if p.type == PieceType.TOWER]
    assert len(towers) == 2, "应该有2个王塔"
    
    white_tower = [p for p in towers if p.player == Player.WHITE][0]
    black_tower = [p for p in towers if p.player == Player.BLACK][0]
    
    print(f"白王塔位置: ({white_tower.x}, {white_tower.y})")
    print(f"黑王塔位置: ({black_tower.x}, {black_tower.y})")
    
    # 检查王塔周围陆地数量
    for tower in towers:
        land_neighbors = 0
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = tower.x + dx, tower.y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board.grid[ny][nx] == 0:  # 陆地
                    land_neighbors += 1
        assert land_neighbors >= 2, f"王塔周围应该有至少2块陆地，实际有{land_neighbors}块"
    
    print("✓ 地图生成测试通过")

def test_piece_operations():
    """测试棋子操作功能"""
    print("\n测试棋子操作...")
    board = Board()
    
    # 测试建造农田
    farm_x, farm_y = 5, 5
    if board.can_build(farm_x, farm_y, 1, 0):  # 白方建造农田
        board.build_piece(farm_x, farm_y, 1, 0)
        piece = board.get_piece(farm_x, farm_y)
        assert piece is not None, "农田应该被成功建造"
        assert piece.type == PieceType.FARM, "建造的应该是农田"
        assert piece.player == Player.WHITE, "农田应该属于白方"
        print("✓ 农田建造测试通过")
    
    # 测试建造工业
    industry_x, industry_y = 6, 6
    if board.can_build(industry_x, industry_y, 1, 1):  # 白方建造工业
        board.build_piece(industry_x, industry_y, 1, 1)
        piece = board.get_piece(industry_x, industry_y)
        assert piece is not None, "工业应该被成功建造"
        assert piece.type == PieceType.INDUSTRY, "建造的应该是工业"
        print("✓ 工业建造测试通过")
    
    # 测试建造军队
    army_x, army_y = 7, 7
    army_piece = None
    if board.can_build(army_x, army_y, 1, 2):  # 白方建造军队
        board.build_piece(army_x, army_y, 1, 2)
        army_piece = board.get_piece(army_x, army_y)
        assert army_piece is not None, "军队应该被成功建造"
        assert army_piece.type == PieceType.ARMY, "建造的应该是军队"
        print("✓ 军队建造测试通过")
    
    # 测试移动军队
    if army_piece and army_piece.type == PieceType.ARMY:
        old_x, old_y = army_piece.x, army_piece.y
        new_x, new_y = old_x + 1, old_y
        if board.can_move_army(old_x, old_y, new_x, new_y, 1, 0, 10):
            board.move_piece(old_x, old_y, new_x, new_y)
            assert board.get_piece(old_x, old_y) is None, "原位置应该为空"
            assert board.get_piece(new_x, new_y) is not None, "新位置应该有军队"
            print("✓ 军队移动测试通过")
        else:
            print("⚠ 军队移动测试跳过（无法移动）")
    else:
        print("⚠ 军队移动测试跳过（无法建造军队）")

def test_game_rules():
    """测试游戏规则"""
    print("\n测试游戏规则...")
    board = Board()
    
    # 测试移动点数计算
    # 初始状态：0工业，0军队
    move_limit = board.get_move_limit(1)
    assert move_limit == 1, f"初始移动点数应该是1，实际是{move_limit}"
    print("✓ 移动点数计算测试通过")
    
    # 测试濒危状态
    # 建造1个工业，0个农田 -> 濒危
    if board.can_build(5, 5, 1, 1):
        board.build_piece(5, 5, 1, 1)
        board.update_all_status()
        assert board.danger[1] == True, "工业数量超过农田一半应该进入濒危状态"
        print("✓ 濒危状态测试通过")
    
    # 测试势力范围
    # 建造军队后检查势力范围
    if board.can_build(6, 6, 1, 2):
        board.build_piece(6, 6, 1, 2)
        board.update_all_status()
        assert len(board.influence[1]) > 0, "应该有势力范围"
        print("✓ 势力范围测试通过")

def test_ai_functions():
    """测试AI功能"""
    print("\n测试AI功能...")
    from ai import AIPlayer
    
    board = Board()
    ai = AIPlayer('easy')
    
    # 测试AI移动选择
    moves = ai.choose_move(board, 1, 1)
    assert isinstance(moves, list), "AI应该返回移动列表"
    print("✓ AI移动选择测试通过")
    
    # 测试AI建造选择
    builds = ai.choose_build(board, 1)
    assert isinstance(builds, list), "AI应该返回建造列表"
    print("✓ AI建造选择测试通过")
    
    # 测试AI拆除选择
    removes = ai.choose_remove(board, 1)
    assert isinstance(removes, list), "AI应该返回拆除列表"
    print("✓ AI拆除选择测试通过")

def main():
    """运行所有测试"""
    print("开始测试势域争霸游戏...")
    print("=" * 50)
    
    try:
        test_board_generation()
        test_piece_operations()
        test_game_rules()
        test_ai_functions()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试通过！游戏功能正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 