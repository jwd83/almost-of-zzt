from __future__ import annotations

from pathlib import Path

from almost_of_zzt import constants as c
from almost_of_zzt.model import Obj, make_new_world
from almost_of_zzt.world import load_world, save_world


def test_roundtrip_default_world(tmp_path: Path) -> None:
    world = make_new_world()
    out = tmp_path / "roundtrip.zzt"
    save_world(world, str(out))

    loaded = load_world(str(out))
    assert loaded.num_rooms == world.num_rooms
    assert loaded.inv.strength == 100
    assert loaded.rooms[0].title == "Title screen"
    assert loaded.rooms[0].board[c.XS // 2][c.YS // 2].kind == c.PLAYER


def test_roundtrip_object_inside_data(tmp_path: Path) -> None:
    world = make_new_world()
    room = world.rooms[0]

    prototype = Obj()
    prototype.inside = b"@TEST\r:START\r#END\r"
    idx = len(room.objs)
    prototype.under = room.board[10][10]
    room.objs.append(prototype)
    room.objs[idx].x = 10
    room.objs[idx].y = 10
    room.objs[idx].cycle = 1
    room.board[10][10].kind = c.PROG
    room.board[10][10].color = 0x0F

    out = tmp_path / "inside.zzt"
    save_world(world, str(out))
    loaded = load_world(str(out))

    assert loaded.rooms[0].num_objs == 1
    assert loaded.rooms[0].objs[1].inside == b"@TEST\r:START\r#END\r"
