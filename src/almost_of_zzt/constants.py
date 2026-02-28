"""Constants mirrored from ref/GAME/GLOB.PAS."""

from __future__ import annotations

from typing import Final

GAME_TITLE: Final[str] = "ZZT"
WORLD_EXT: Final[str] = ".ZZT"
SAVE_EXT: Final[str] = ".SAV"
HI_EXT: Final[str] = ".HI"

# Categories
C_ITEM: Final[int] = 1
C_CREATURE: Final[int] = 2
C_TERRAIN: Final[int] = 3

# Kinds
EMPTY: Final[int] = 0
BOUND: Final[int] = 1
SPECIAL: Final[int] = 2
MONITOR: Final[int] = 3
PLAYER: Final[int] = 4
AMMO: Final[int] = 5
TORCH: Final[int] = 6
GEM: Final[int] = 7
AKEY: Final[int] = 8
DOOR: Final[int] = 9
SCROLL: Final[int] = 10
PASSAGE: Final[int] = 11
DUPER: Final[int] = 12
BOMB: Final[int] = 13
ENERGIZER: Final[int] = 14
SBOMB: Final[int] = 15
CONVEYOR_CW: Final[int] = 16
CONVEYOR_CCW: Final[int] = 17
BULLET: Final[int] = 18
WATER: Final[int] = 19
BRUSH: Final[int] = 20
SOLID_WALL: Final[int] = 21
NORM_WALL: Final[int] = 22
BREAK_WALL: Final[int] = 23
BLOCK: Final[int] = 24
SLIDER_NS: Final[int] = 25
SLIDER_EW: Final[int] = 26
FAKE_WALL: Final[int] = 27
INVISO_WALL: Final[int] = 28
BLINK_WALL: Final[int] = 29
XPORTER: Final[int] = 30
LINE2: Final[int] = 31
RICOCHET: Final[int] = 32
HORIZ_WALL: Final[int] = 33
CHASER: Final[int] = 34
WANDERER: Final[int] = 35
PROG: Final[int] = 36
SLIME: Final[int] = 37
SHARK: Final[int] = 38
SHOOTER: Final[int] = 39
PUSHER: Final[int] = 40
ENEMY: Final[int] = 41
S_ENEMY: Final[int] = 42
VERT_WALL: Final[int] = 43
CENTI_H: Final[int] = 44
CENTI: Final[int] = 45
XXX1: Final[int] = 46
TEXT_COL: Final[int] = 47
NUM_TEXT_COLS: Final[int] = 6
NUM_CLASSES: Final[int] = TEXT_COL + NUM_TEXT_COLS

XS: Final[int] = 60
YS: Final[int] = 25
MAX_OBJS: Final[int] = 150
MAX_ROOMS: Final[int] = 100
NUM_FLAGS: Final[int] = 10
NUM_HI: Final[int] = 30
HEADER_LEN: Final[int] = 512

TORCH_XS: Final[int] = 8
TORCH_YS: Final[int] = 5
TORCH_SIZE: Final[int] = 50
TORCH_LIFE: Final[int] = 200
ENER_LIFE: Final[int] = 75

CLOCK_X: Final[tuple[int, ...]] = (-1, 0, 1, 1, 1, 0, -1, -1)
CLOCK_Y: Final[tuple[int, ...]] = (1, 1, 1, 0, -1, -1, -1, 0)
UDLR_X: Final[tuple[int, ...]] = (0, 0, -1, 1)
UDLR_Y: Final[tuple[int, ...]] = (-1, 1, 0, 0)

COLORS: Final[tuple[str, ...]] = (
    "",
    "Blue",
    "Green",
    "Cyan",
    "Red",
    "Purple",
    "Yellow",
    "White",
)

# VGA palette index -> RGB
EGA16: Final[tuple[tuple[int, int, int], ...]] = (
    (0x00, 0x00, 0x00),
    (0x00, 0x00, 0xAA),
    (0x00, 0xAA, 0x00),
    (0x00, 0xAA, 0xAA),
    (0xAA, 0x00, 0x00),
    (0xAA, 0x00, 0xAA),
    (0xAA, 0x55, 0x00),
    (0xAA, 0xAA, 0xAA),
    (0x55, 0x55, 0x55),
    (0x55, 0x55, 0xFF),
    (0x55, 0xFF, 0x55),
    (0x55, 0xFF, 0xFF),
    (0xFF, 0x55, 0x55),
    (0xFF, 0x55, 0xFF),
    (0xFF, 0xFF, 0x55),
    (0xFF, 0xFF, 0xFF),
)

CELL_W: Final[int] = 8
CELL_H: Final[int] = 14
SCREEN_W: Final[int] = 640
SCREEN_H: Final[int] = 360
BOARD_OFFSET_X: Final[int] = 0
BOARD_OFFSET_Y: Final[int] = 5

MONITOR_SIDE_START_COL: Final[int] = 60

VERSION_MARKER: Final[int] = -1
