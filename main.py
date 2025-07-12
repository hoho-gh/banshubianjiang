import pygame
from game import Game
import sys
import subprocess
import os

# 自动检查并安装requirements.txt依赖，兼容无pkg_resources环境
for _ in range(2):
    try:
        import pkg_resources
        req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
        with open(req_file, 'r', encoding='utf-8') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        pkgs = [r.split('==')[0].split('>=')[0].strip() for r in requirements]
        installed = {pkg.key for pkg in pkg_resources.working_set}
        missing = [r for r in requirements if (r.split('==')[0].split('>=')[0].strip().replace('_', '-').lower() not in installed)]
        if missing:
            print('检测到缺失依赖，正在自动安装:', missing)
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
        break
    except ImportError:
        print('未检测到pkg_resources，正在安装setuptools...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'setuptools'])
    except Exception as e:
        print('依赖检查/安装失败:', e)
        break

def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
    pygame.display.set_caption("半数边疆")
    game = Game(screen)
    game.run()
    pygame.quit()

if __name__ == '__main__':
    main() 