from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as c


@dataclass(slots=True)
class BoardCell:
    kind: int = c.EMPTY
    color: int = 0


@dataclass(slots=True)
class Obj:
    x: int = 0
    y: int = 0
    xd: int = 0
    yd: int = 0
    cycle: int = 0
    intel: int = 0
    rate: int = 0
    room: int = 0
    child: int = -1
    parent: int = -1
    under: BoardCell = field(default_factory=BoardCell)
    offset: int = 0
    inside: bytes = b""
    pad: bytes = b"\x00" * 8


@dataclass(slots=True)
class RoomInfo:
    can_shoot: int = 255
    is_dark: bool = False
    room_udlr: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    re_enter: bool = False
    bot_msg: str = ""
    start_x: int = c.XS // 2
    start_y: int = c.YS // 2
    time_limit: int = 0
    ypad: bytes = b"\x00" * 16


@dataclass(slots=True)
class Room:
    title: str = ""
    board: list[list[BoardCell]] = field(default_factory=list)
    objs: list[Obj] = field(default_factory=list)
    room_info: RoomInfo = field(default_factory=RoomInfo)

    @property
    def num_objs(self) -> int:
        return max(0, len(self.objs) - 1)


def make_empty_board() -> list[list[BoardCell]]:
    board = [[BoardCell() for _ in range(c.YS + 2)] for _ in range(c.XS + 2)]
    for x in range(c.XS + 2):
        board[x][0] = BoardCell(c.BOUND, 0)
        board[x][c.YS + 1] = BoardCell(c.BOUND, 0)
    for y in range(c.YS + 2):
        board[0][y] = BoardCell(c.BOUND, 0)
        board[c.XS + 1][y] = BoardCell(c.BOUND, 0)

    for x in range(1, c.XS + 1):
        board[x][1] = BoardCell(c.NORM_WALL, 0x0E)
        board[x][c.YS] = BoardCell(c.NORM_WALL, 0x0E)
    for y in range(1, c.YS + 1):
        board[1][y] = BoardCell(c.NORM_WALL, 0x0E)
        board[c.XS][y] = BoardCell(c.NORM_WALL, 0x0E)
    return board


@dataclass(slots=True)
class Inventory:
    ammo: int = 0
    gems: int = 0
    keys: list[bool] = field(default_factory=lambda: [False] * 7)
    strength: int = 100
    room: int = 0
    torches: int = 0
    torch_time: int = 0
    ener_time: int = 0
    inviso_time: int = 0
    score: int = 0
    orig_name: str = ""
    flags: list[str] = field(default_factory=lambda: [""] * c.NUM_FLAGS)
    room_time: int = 0
    last_sec: int = 0
    play_flag: bool = False
    wpad: bytes = b"\x00" * 14


@dataclass(slots=True)
class FirstFlags:
    got_ammo: bool = True
    no_ammo: bool = True
    cant_shoot_here: bool = True
    got_torch: bool = True
    no_torch: bool = True
    dont_need_torch: bool = True
    enter_dark: bool = True
    make_path: bool = True
    touch_fake: bool = True
    got_gem: bool = True
    touch_ener: bool = True


@dataclass(slots=True)
class GameWorld:
    num_rooms: int = 0
    rooms: list[Room] = field(default_factory=list)
    inv: Inventory = field(default_factory=Inventory)
    first: FirstFlags = field(default_factory=FirstFlags)
    game_name: str = ""


def make_default_room() -> Room:
    board = make_empty_board()
    px, py = c.XS // 2, c.YS // 2
    board[px][py] = BoardCell(c.PLAYER, 0x1F)
    player = Obj(x=px, y=py, cycle=1, under=BoardCell(c.EMPTY, 0))
    room = Room(title="Title screen", board=board, objs=[player], room_info=RoomInfo())
    room.room_info.start_x = px
    room.room_info.start_y = py
    return room


def make_new_world() -> GameWorld:
    room = make_default_room()
    world = GameWorld(num_rooms=0, rooms=[room])
    world.inv.room = 0
    return world
