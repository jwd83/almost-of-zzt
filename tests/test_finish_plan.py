from __future__ import annotations

import os
from pathlib import Path

import pygame

from almost_of_zzt import constants as c
from almost_of_zzt.editor import BoardEditor
from almost_of_zzt.engine import EditScrollState, GameEngine
from almost_of_zzt.info import init_info_edit
from almost_of_zzt.model import BoardCell, Obj, make_default_room, make_new_world
from almost_of_zzt.world import load_world


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _engine() -> GameEngine:
    world = make_new_world()
    world.game_name = "TEST"
    world.inv.room = 0
    return GameEngine(world)


def _add_prog(e: GameEngine, x: int, y: int, script: bytes) -> int:
    proto = Obj(inside=script)
    return e.add_obj(x, y, c.PROG, 0x0F, 3, proto)


def test_rndp_is_perpendicular_to_base_direction() -> None:
    e = _engine()
    idx = _add_prog(e, 10, 10, b"@BOT\r#END\r")

    e.random.randrange = lambda _: 0  # type: ignore[method-assign]
    d0, _ = e.oop._note_dir(idx, ["RNDP", "N"], 0)
    e.random.randrange = lambda _: 1  # type: ignore[method-assign]
    d1, _ = e.oop._note_dir(idx, ["RNDP", "N"], 0)

    assert d0 == (1, 0)
    assert d1 == (-1, 0)


def test_do_area_sends_bombed_message_to_programmable_objects() -> None:
    e = _engine()
    idx = _add_prog(e, 10, 10, b"@BOT\r:BOMBED\r#SET HIT\r#END\r")

    e.do_area(10, 10, 1)
    e.oop.exec_obj(idx)

    assert e.oop.flag_num("HIT") >= 0


def test_quit_flow_confirms_and_returns_to_monitor() -> None:
    world = make_new_world()
    world.rooms.append(make_default_room())
    world.num_rooms = 1
    world.inv.room = 1
    e = GameEngine(world)
    e._set_play_mode(c.PLAYER)
    e.standby = False
    e.in_yn = lambda prompt, default=False: True  # type: ignore[method-assign]

    e.control.key = "Q"
    e.upd_player(0)

    assert e.play_mode == c.MONITOR
    assert e.world.inv.room == 0
    assert e.standby is False


def test_dead_quit_skips_confirm_prompt() -> None:
    e = _engine()
    e._set_play_mode(c.PLAYER)
    e.world.inv.strength = 0
    e.in_yn = lambda prompt, default=False: (_ for _ in ()).throw(RuntimeError("should not ask"))  # type: ignore[method-assign]

    assert e.ask_quit_game() is True
    assert e.play_mode == c.MONITOR


def test_secret_cmd_sets_flags_and_gates_debug_cheats() -> None:
    e = _engine()

    e.in_string = lambda x, y, max_len, prompt="Input:", initial="": "+FLAGX"  # type: ignore[method-assign]
    e.secret_cmd()
    assert e.oop.flag_num("FLAGX") >= 0

    e.in_string = lambda x, y, max_len, prompt="Input:", initial="": "-FLAGX"  # type: ignore[method-assign]
    e.secret_cmd()
    assert e.oop.flag_num("FLAGX") == -1

    e.world.inv.ammo = 0
    e.in_string = lambda x, y, max_len, prompt="Input:", initial="": "AMMO 55"  # type: ignore[method-assign]
    e.secret_cmd()
    assert e.world.inv.ammo == 0

    e.oop.set_flag("DEBUG")
    e.secret_cmd()
    assert e.world.inv.ammo == 55


def test_editor_plot_and_fill_preserve_board_object_rules() -> None:
    e = _engine()
    ed = BoardEditor(e)
    e.info = init_info_edit()

    ed.pattern_kind = c.BREAK_WALL
    ed.pattern_color = 0x0E
    ed._plot_board(10, 10)
    assert e.room.board[10][10].kind == c.BREAK_WALL
    assert e.obj_at(10, 10) == -1

    ed.pattern_kind = c.PUSHER
    ed.pattern_color = 0x0F
    ed._plot_board(11, 10)
    assert e.room.board[11][10].kind == c.PUSHER
    assert e.obj_at(11, 10) > 0

    e.room.board[20][20] = BoardCell(c.BREAK_WALL, 0x0E)
    e.room.board[21][20] = BoardCell(c.BREAK_WALL, 0x0E)
    ed.pattern_kind = c.GEM
    ed.pattern_color = 0x0D
    ed._flood_fill(20, 20)
    assert e.room.board[20][20].kind == c.GEM
    assert e.room.board[21][20].kind == c.GEM


def test_modify_obj_updates_fields_and_script() -> None:
    e = _engine()
    e.info = init_info_edit()
    idx = _add_prog(e, 10, 10, b"@BOT\r#END\r")
    ed = BoardEditor(e)

    e.in_char = lambda x, y, prompt, val: 65  # type: ignore[method-assign]
    e.in_num = lambda x, y, prompt, val: 5  # type: ignore[method-assign]
    e.edit_scroll = lambda initial, title="Edit text": b"@BOT\r#SET OK\r#END\r"  # type: ignore[method-assign]

    ed._modify_obj(10, 10)

    obj = e.room.objs[idx]
    assert obj.intel == 65
    assert obj.rate == 5
    assert b"SET OK" in obj.inside


def test_edit_scroll_key_behaviors() -> None:
    e = _engine()
    state = EditScrollState(lines=["AB", "CD"], cur_x=2, cur_y=0)

    e._edit_scroll_apply_key(state, pygame.K_RETURN)
    assert state.lines == ["AB", "", "CD"]
    assert (state.cur_x, state.cur_y) == (0, 1)

    e._edit_scroll_apply_key(state, pygame.K_BACKSPACE)
    assert state.lines == ["AB", "CD"]
    assert (state.cur_x, state.cur_y) == (2, 0)

    e._edit_scroll_apply_key(state, pygame.K_DELETE)
    assert state.lines == ["ABCD"]

    state.cur_x = 0
    state.cur_y = 0
    e._edit_scroll_apply_key(state, pygame.K_y, mod=pygame.KMOD_CTRL)
    assert state.lines == [""]


def test_monitor_e_key_enters_editor(monkeypatch) -> None:
    e = _engine()
    calls: list[str] = []

    def fake_design_board(self: BoardEditor) -> None:
        calls.append("edit")

    monkeypatch.setattr("almost_of_zzt.editor.BoardEditor.design_board", fake_design_board)
    e._handle_monitor_key("E")
    assert calls == ["edit"]


def test_monitor_f_key_toggles_fullscreen() -> None:
    e = _engine()
    messages: list[str] = []

    def fake_toggle() -> bool:
        e._fullscreen = not e._fullscreen
        return True

    e._toggle_fullscreen = fake_toggle  # type: ignore[method-assign]
    e.put_bot_msg = lambda duration, msg: messages.append(msg)  # type: ignore[method-assign]

    e._handle_monitor_key("F")
    e._handle_monitor_key("f")

    assert messages == ["Fullscreen mode", "Windowed mode"]


def test_editor_save_and_world_reload_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    e = _engine()
    e.info = init_info_edit()
    ed = BoardEditor(e)
    ed.pattern_kind = c.GEM
    ed.pattern_color = 0x0D
    ed._plot_board(9, 9)
    e.in_string = lambda x, y, max_len, prompt="Input:", initial="": "ROUNDTRIP.ZZT"  # type: ignore[method-assign]

    ed._save_world()

    loaded = load_world("ROUNDTRIP.ZZT")
    assert loaded.rooms[0].board[9][9].kind == c.GEM


def test_smoke_all_reference_worlds_tick_256_steps_without_crash() -> None:
    for world_name in (
        "TOUR30.ZZT",
        "TOWN30.ZZT",
        "TIMMY30.ZZT",
        "DEMO30.ZZT",
        "TOUR32.ZZT",
        "TOWN32.ZZT",
        "DEMO32.ZZT",
        "CAVES32.ZZT",
    ):
        world = load_world(world_name)
        e = GameEngine(world)

        if not (0 <= e.world.inv.room <= e.world.num_rooms):
            e.world.inv.room = 0
        e.change_room(e.world.inv.room)
        e._set_play_mode(c.PLAYER)
        e.play_mode = c.PLAYER
        e.standby = False
        e.world.inv.strength = max(1, e.world.inv.strength)
        e._read_control = lambda: None  # type: ignore[method-assign]
        e.cycle_last_ms = 0
        e.counter = 1

        for step in range(256):
            e._tick_game((step + 1) * e.game_cycle_ms)
