from __future__ import annotations

import os
from pathlib import Path

import pygame

from almost_of_zzt import constants as c
from almost_of_zzt.engine import GameEngine
from almost_of_zzt.model import BoardCell, Obj, make_default_room, make_new_world
from almost_of_zzt.render import Renderer


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _engine() -> GameEngine:
    world = make_new_world()
    world.game_name = "TEST"
    world.inv.room = 0
    return GameEngine(world)


def _set_player(e: GameEngine, x: int, y: int) -> None:
    p = e.player
    e.room.board[p.x][p.y] = BoardCell(c.EMPTY, 0)
    p.x = x
    p.y = y
    p.under = BoardCell(c.EMPTY, 0)
    e.room.board[x][y] = BoardCell(c.PLAYER, 0x1F)


def test_scroll_modal_returns_hyper_command() -> None:
    pygame.init()
    screen = pygame.display.set_mode((c.SCREEN_W, c.SCREEN_H))
    e = _engine()
    e._screen = screen
    e._renderer = Renderer(screen)
    e._clock = pygame.time.Clock()

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
    cmd = e.show_scroll(["!HELLO;Say hello", "Plain"], "Dialog", obj_flag=True)

    assert cmd == "HELLO"


def test_oop_multiline_scroll_command_dispatches_label() -> None:
    e = _engine()

    script = b"@BOT\rHello there\r!WAVE;Wave\r:WAVE\r#SET WAVED\r#END\r"
    idx = e.add_obj(10, 10, c.PROG, 0x0F, 3, Obj(inside=script))

    # Keep this test non-interactive.
    e.show_scroll = lambda lines, title, obj_flag=True: "WAVE"  # type: ignore[method-assign]

    e.oop.exec_obj(idx, "Interaction")

    assert e.oop.flag_num("WAVED") >= 0


def test_centi_head_switches_to_tail_when_stuck() -> None:
    e = _engine()

    head = e.add_obj(20, 10, c.CENTI_H, 0x0F, 2)
    seg = e.add_obj(19, 10, c.CENTI, 0x0F, 2)

    e.room.objs[head].xd = 1
    e.room.objs[head].yd = 0
    e.room.objs[head].child = seg
    e.room.objs[head].parent = -1

    e.room.objs[seg].parent = head
    e.room.objs[seg].child = -1
    e.room.objs[seg].xd = 1
    e.room.objs[seg].yd = 0

    e.room.board[21][10] = BoardCell(c.NORM_WALL, 0x0E)
    e.room.board[20][9] = BoardCell(c.NORM_WALL, 0x0E)
    e.room.board[20][11] = BoardCell(c.NORM_WALL, 0x0E)

    e.upd_centi_h(head)

    assert e.room.board[20][10].kind == c.CENTI
    assert e.room.board[e.room.objs[seg].x][e.room.objs[seg].y].kind == c.CENTI_H


def test_blink_wall_retracts_existing_wall_segment() -> None:
    e = _engine()

    idx = e.add_obj(30, 10, c.BLINK_WALL, 0x0A, 1)
    o = e.room.objs[idx]
    o.xd = 1
    o.yd = 0
    o.rate = 2
    o.intel = 0
    o.room = 1

    e.room.board[31][10] = BoardCell(c.HORIZ_WALL, 0x0A)
    e.room.board[32][10] = BoardCell(c.HORIZ_WALL, 0x0A)

    e.upd_blink_wall(idx)

    assert e.room.board[31][10].kind == c.EMPTY
    assert e.room.board[32][10].kind == c.EMPTY
    assert e.room.objs[idx].room == 5


def test_duper_touches_source_when_player_is_behind() -> None:
    e = _engine()
    _set_player(e, 9, 10)

    e.add_obj(11, 10, c.AMMO, 0x03, 1)
    idx = e.add_obj(10, 10, c.DUPER, 0x0F, 2)
    o = e.room.objs[idx]
    o.xd = 1
    o.yd = 0
    o.rate = 4
    o.intel = 5

    ammo_before = e.world.inv.ammo
    e.upd_duper(idx)

    assert e.world.inv.ammo == ammo_before + 5
    assert e.room.board[11][10].kind == c.EMPTY


def test_monitor_play_switches_to_entry_room() -> None:
    world = make_new_world()
    world.game_name = "TEST"
    world.rooms[0].board[world.rooms[0].objs[0].x][world.rooms[0].objs[0].y] = BoardCell(c.MONITOR, 0x07)
    world.rooms.append(make_default_room())
    world.num_rooms = 1
    world.inv.room = 0

    e = GameEngine(world)
    e.entry_room = 1
    e._handle_monitor_key("P")

    assert e.play_mode == c.PLAYER
    assert e.world.inv.room == 1
    assert e.standby is True
    assert e.room.board[e.player.x][e.player.y].kind == c.PLAYER


def test_monitor_world_command_loads_and_stays_in_menu() -> None:
    e = _engine()
    e._set_play_mode(c.MONITOR)
    e.standby = False

    picked = Path("WORLD.ZZT")
    e._select_game_file = lambda ext, title: picked  # type: ignore[method-assign]
    e._load_world_from_path = lambda path: path == picked  # type: ignore[method-assign]

    e._handle_monitor_key("W")

    assert e.play_mode == c.MONITOR
    assert e.standby is False


def test_monitor_restore_command_starts_play_mode() -> None:
    e = _engine()
    e._set_play_mode(c.MONITOR)
    e.standby = False

    picked = Path("SAVE.SAV")
    e._select_game_file = lambda ext, title: picked  # type: ignore[method-assign]
    e._load_world_from_path = lambda path: path == picked  # type: ignore[method-assign]

    e._handle_monitor_key("R")

    assert e.play_mode == c.PLAYER
    assert e.standby is True


def test_standby_moves_off_passage_overlay_cell() -> None:
    e = _engine()
    _set_player(e, 10, 10)
    e.play_mode = c.PLAYER
    e.standby = True
    e.room.board[10][10] = BoardCell(c.PASSAGE, 0x0E)
    e.room.board[11][10] = BoardCell(c.EMPTY, 0)
    e.control.dx = 1
    e.control.dy = 0
    e.control.key = "\x00"
    e._read_control = lambda: None  # type: ignore[method-assign]

    e._tick_game(100)

    assert (e.player.x, e.player.y) == (11, 10)
    assert e.room.board[10][10].kind == c.PASSAGE
    assert e.room.board[11][10].kind == c.PLAYER
    assert e.standby is False


def test_touch_bound_moves_player_into_adjacent_room_entry() -> None:
    world = make_new_world()
    world.game_name = "TEST"
    world.rooms.append(make_default_room())
    world.num_rooms = 1
    world.inv.room = 0
    world.rooms[0].room_info.room_udlr[3] = 1
    world.rooms[1].board[1][10] = BoardCell(c.EMPTY, 0)

    e = GameEngine(world)
    _set_player(e, c.XS, 10)
    dxy = [1, 0]

    e.touch_bound(c.XS + 1, 10, 0, dxy)

    assert e.world.inv.room == 1
    assert (e.player.x, e.player.y) == (1, 10)
    assert dxy == [0, 0]


def test_xporter_dynamic_char_clamps_non_unit_direction_values() -> None:
    e = _engine()
    idx = e.add_obj(20, 10, c.XPORTER, 0x0F, 1)
    o = e.room.objs[idx]
    o.xd = 9
    o.yd = -7
    e.counter = 3

    ch = e._dynamic_char(20, 10, c.XPORTER)

    assert ch == ord("|")


def test_centi_head_handles_non_unit_child_deltas_without_crash() -> None:
    e = _engine()
    head = e.add_obj(2, 2, c.CENTI_H, 0x0F, 2)
    child = e.add_obj(1, 2, c.CENTI, 0x0F, 2)

    e.room.objs[head].xd = 1
    e.room.objs[head].yd = 0
    e.room.objs[head].child = child
    e.room.objs[head].parent = -1

    e.room.objs[child].parent = head
    e.room.objs[child].child = -1
    e.room.objs[child].xd = 99
    e.room.objs[child].yd = -99

    e.upd_centi_h(head)

    assert 0 <= e.room.objs[head].x <= c.XS + 1
    assert 0 <= e.room.objs[head].y <= c.YS + 1
