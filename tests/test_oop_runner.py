from __future__ import annotations

from almost_of_zzt import constants as c
from almost_of_zzt.engine import GameEngine
from almost_of_zzt.model import BoardCell, Obj, make_new_world


def _engine() -> GameEngine:
    world = make_new_world()
    world.game_name = "TEST"
    world.inv.room = 0
    return GameEngine(world)


def _add_prog(e: GameEngine, x: int, y: int, script: bytes) -> int:
    proto = Obj(inside=script)
    return e.add_obj(x, y, c.PROG, 0x0F, 3, proto)


def test_oop_set_flag_via_label_send() -> None:
    e = _engine()
    idx = _add_prog(e, 10, 10, b"@BOT\r:START\r#SET FLAG_A\r#END\r")
    assert idx == 1

    assert e.oop.lsend_msg(1, "START", ignore_lock=False) is True
    e.oop.exec_obj(1)

    assert e.oop.flag_num("FLAG_A") >= 0


def test_oop_if_blocked_then_move() -> None:
    e = _engine()
    e.room.board[6][5] = BoardCell(c.NORM_WALL, 0x0E)
    idx = _add_prog(e, 5, 5, b"#IF BLOCKED E THEN GO S\r")

    e.oop.exec_obj(idx)

    obj = e.room.objs[idx]
    assert (obj.x, obj.y) == (5, 6)


def test_oop_put_and_change_cells() -> None:
    e = _engine()
    idx = _add_prog(e, 8, 8, b"#PUT E AMMO\r#CHANGE AMMO GEM\r#END\r")

    e.oop.exec_obj(idx)

    assert e.room.board[9][8].kind == c.GEM


def test_oop_become_replaces_object() -> None:
    e = _engine()
    idx = _add_prog(e, 12, 12, b"#BECOME BREAKABLE\r")

    e.oop.exec_obj(idx)

    assert e.room.board[12][12].kind == c.BREAK_WALL
    assert e.obj_at(12, 12) == -1


def test_oop_take_fail_executes_fallback_command() -> None:
    e = _engine()
    idx = _add_prog(e, 14, 14, b"#TAKE GEMS 1 GIVE AMMO 5\r")

    e.oop.exec_obj(idx)

    assert e.world.inv.gems == 0
    assert e.world.inv.ammo == 5
