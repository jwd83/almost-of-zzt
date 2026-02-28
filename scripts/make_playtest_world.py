from __future__ import annotations

from pathlib import Path

from almost_of_zzt import constants as c
from almost_of_zzt.model import BoardCell, GameWorld, Inventory, Obj, Room, make_default_room
from almost_of_zzt.world import save_world


def add_obj(
    room: Room,
    x: int,
    y: int,
    kind: int,
    color: int,
    *,
    cycle: int = 1,
    intel: int = 4,
    rate: int = 4,
    room_link: int = 0,
    xd: int = 0,
    yd: int = 0,
    inside: bytes = b"",
) -> int:
    under = room.board[x][y]
    obj = Obj(
        x=x,
        y=y,
        xd=xd,
        yd=yd,
        cycle=cycle,
        intel=intel,
        rate=rate,
        room=room_link,
        under=BoardCell(under.kind, under.color),
        inside=inside,
    )
    room.objs.append(obj)
    room.board[x][y] = BoardCell(kind, color)
    return len(room.objs) - 1


def main() -> None:
    room = make_default_room()
    room.title = "Playtest Arena"

    # Move player start to upper-left quadrant.
    player = room.objs[0]
    room.board[player.x][player.y] = BoardCell(c.EMPTY, 0)
    player.x = 5
    player.y = 5
    player.under = BoardCell(c.EMPTY, 0)
    room.board[player.x][player.y] = BoardCell(c.PLAYER, 0x1F)
    room.room_info.start_x = player.x
    room.room_info.start_y = player.y

    # Arena geometry.
    for x in range(8, 50):
        room.board[x][8] = BoardCell(c.BREAK_WALL, 0x0E)
    for y in range(9, 21):
        room.board[25][y] = BoardCell(c.NORM_WALL, 0x0E)
    for x in range(40, 54):
        for y in range(14, 22):
            room.board[x][y] = BoardCell(c.WATER, 0xF9)

    # Pickups and progression.
    add_obj(room, 7, 6, c.AMMO, 0x03)
    add_obj(room, 9, 6, c.GEM, 0x0D)
    add_obj(room, 11, 6, c.TORCH, 0x06)
    add_obj(room, 13, 6, c.AKEY, 0x09)  # Blue key
    add_obj(room, 17, 6, c.DOOR, 0x1F)  # Blue door

    scroll_text = b"@GUIDE\rWelcome to the playtest arena!\rPress Shift+Arrows to shoot.\r#END\r"
    add_obj(room, 6, 9, c.SCROLL, 0x0F, cycle=1, inside=scroll_text)

    # Monsters.
    add_obj(room, 32, 5, c.ENEMY, 0x0C, cycle=2, intel=5)
    add_obj(room, 36, 6, c.WANDERER, 0x0D, cycle=1, intel=5, rate=4)
    add_obj(room, 43, 6, c.CHASER, 0x06, cycle=3, intel=7)
    add_obj(room, 52, 10, c.SHOOTER, 0x0E, cycle=2, intel=6, rate=6)
    add_obj(room, 46, 17, c.SHARK, 0x07, cycle=3, intel=6)

    # Extra hazards.
    add_obj(room, 30, 14, c.BOMB, 0x0F, cycle=6, intel=0)
    add_obj(room, 28, 18, c.SLIME, 0x0A, cycle=3, rate=4)

    world = GameWorld(num_rooms=0, rooms=[room], inv=Inventory())
    world.inv.room = 0
    world.inv.orig_name = "PLAYTEST"
    world.game_name = "PLAYTEST"

    out = Path("playtest.ZZT")
    save_world(world, str(out))
    print(f"wrote {out.resolve()}")


if __name__ == "__main__":
    main()
