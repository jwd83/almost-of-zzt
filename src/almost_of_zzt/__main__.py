from __future__ import annotations

import argparse
from pathlib import Path

from .engine import GameEngine
from .world import bootstrap_world


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pygame-ce ZZT runtime clone")
    p.add_argument("world", nargs="?", help="Path to .ZZT/.SAV world to load")
    return p


def main() -> None:
    args = build_parser().parse_args()
    world_path = None
    if args.world:
        path = Path(args.world)
        if path.exists():
            world_path = str(path)
    world = bootstrap_world(world_path)
    engine = GameEngine(world)
    engine.run()


if __name__ == "__main__":
    main()
