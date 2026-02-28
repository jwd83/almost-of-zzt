from __future__ import annotations

import copy
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pygame

from . import constants as c
from .info import InfoDef, init_info_play
from .model import BoardCell, Obj, Room, RoomInfo, make_default_room, make_new_world
from .oop import OOPRunner
from .render import Renderer
from . import sound as snd
from .world import load_world, save_world


@dataclass(slots=True)
class ControlState:
    dx: int = 0
    dy: int = 0
    fire: bool = False
    key: str = "\x00"


@dataclass(slots=True)
class ScrollEntry:
    raw: str
    text: str
    kind: str
    command: str | None = None


@dataclass(slots=True)
class EditScrollState:
    lines: list[str]
    cur_x: int = 0
    cur_y: int = 0
    insert_mode: bool = True
    done: bool = False
    cancelled: bool = False


class GameEngine:
    TARGET_RENDER_FPS = 60
    MAX_MOVE_QUEUE = 8
    MAX_TICK_CATCHUP = 8

    def __init__(self, world) -> None:
        self.constants = c
        self.random = random.Random()
        self.world = world
        self.info: list[InfoDef] = init_info_play()

        self.speed = 4
        self.game_cycle_ms = self.speed * 20
        self.counter = self.random.randrange(1, 100)
        self.obj_num = 0
        self.cycle_last_ms = 0

        self.standby = True
        self.done = False
        self.exit_program = False

        self.control = ControlState()
        self.key_buffer: deque[str] = deque()
        self.move_queue: deque[tuple[int, int, bool]] = deque()
        self.bot_msg_ticks = 0
        self._screen: pygame.Surface | None = None
        self._renderer: Renderer | None = None
        self._clock: pygame.time.Clock | None = None

        self.sound_enabled = True
        self.sound = snd.SoundEngine(self.random)
        self.sound.set_enabled(self.sound_enabled)
        self.first_thru = True
        self.play_mode = c.PLAYER
        self._standby_blink_visible = True
        self._standby_blink_last_ms = 0
        self.entry_room = 0
        self._world_file: Path | None = None
        self._world_origin_file: Path | None = None
        self._hi_scores: list[tuple[str, int]] = [("", -1) for _ in range(c.NUM_HI)]
        self._death_score_noted = False

        self.oop = OOPRunner(self)

        if not self.world.rooms:
            self.world.rooms = [make_default_room()]
            self.world.num_rooms = 0
            self.world.inv.room = 0

        if self.world.game_name == "" and self.world.num_rooms == 0:
            self._build_demo_world()

        self._ensure_player_board()
        self._init_menu_state()
        self._load_hi_scores()

    @property
    def room(self) -> Room:
        return self.world.rooms[self.world.inv.room]

    @property
    def player(self) -> Obj:
        return self.room.objs[0]

    def sound_add(self, priority: int, seq: bytes) -> None:
        self.sound.add(priority, seq)

    def sound_music(self, spec: str) -> bytes:
        return self.sound.music(spec)

    def sound_stop(self) -> None:
        self.sound.stop()

    def _service_sound(self, now_ms: int | None = None) -> None:
        if now_ms is None:
            if not pygame.get_init():
                return
            now_ms = pygame.time.get_ticks()
        self.sound.tick(now_ms)

    def _ui_wait(self, clock: pygame.time.Clock, fps: int = 30) -> None:
        self._service_sound()
        clock.tick(fps)

    def _build_demo_world(self) -> None:
        title = make_default_room()
        title.title = "Title screen"
        title.board[title.objs[0].x][title.objs[0].y] = BoardCell(c.MONITOR, 0x07)

        demo = make_default_room()
        demo.title = "Playable demo"
        demo.room_info.start_x = demo.objs[0].x
        demo.room_info.start_y = demo.objs[0].y

        for x in range(8, 24):
            demo.board[x][7] = BoardCell(c.BREAK_WALL, 0x0E)

        self.world.rooms = [title, demo]
        self.world.num_rooms = 1
        self.world.inv.room = 0
        self.world.inv.orig_name = "DEMO"

        self._add_obj_to_room(demo, 10, 10, c.AMMO, 0x03, self.info[c.AMMO].cycle)
        self._add_obj_to_room(demo, 12, 10, c.GEM, 0x0D, self.info[c.GEM].cycle)
        self._add_obj_to_room(demo, 14, 10, c.TORCH, 0x06, self.info[c.TORCH].cycle)
        self._add_obj_to_room(demo, 16, 10, c.AKEY, 0x09, self.info[c.AKEY].cycle)
        self._add_obj_to_room(demo, 18, 10, c.DOOR, 0x1F, self.info[c.DOOR].cycle)
        self._add_obj_to_room(demo, 30, 13, c.ENEMY, 0x0C, 2)
        self._add_obj_to_room(demo, 35, 13, c.WANDERER, 0x0D, 1)
        self._add_obj_to_room(demo, 50, 13, c.SHOOTER, 0x0E, 2)

    def _ensure_player_board(self) -> None:
        p = self.player
        if self.room.board[p.x][p.y].kind != c.MONITOR:
            self.room.board[p.x][p.y] = BoardCell(c.PLAYER, self.info[c.PLAYER].col)

    def _init_menu_state(self) -> None:
        self.entry_room = self.world.inv.room
        if (
            self.world.inv.orig_name == "DEMO"
            and self.world.game_name == ""
            and self.world.num_rooms >= 1
            and self.world.inv.room == 0
        ):
            self.entry_room = 1

        if self.world.game_name:
            path = Path(self.world.game_name)
            if path.exists():
                self._world_file = path
                if path.suffix.upper() == c.WORLD_EXT:
                    self._world_origin_file = path
        if self._world_origin_file is None and self.world.inv.orig_name:
            world_path = Path(f"{self.world.inv.orig_name}{c.WORLD_EXT}")
            if world_path.exists():
                self._world_origin_file = world_path

        if self.room.board[self.player.x][self.player.y].kind == c.MONITOR:
            self.play_mode = c.MONITOR
            self.standby = False
        else:
            self.play_mode = c.PLAYER
            self.standby = True
        self._set_play_mode(self.play_mode)

    def _set_play_mode(self, mode: int) -> None:
        self.play_mode = mode
        p = self.player
        self.room.board[p.x][p.y] = BoardCell(mode, self.info[mode].col)

    def _select_game_file(self, ext: str, title: str) -> Path | None:
        files = sorted(Path.cwd().glob(f"*{ext}"), key=lambda p: p.name.lower())
        if not files:
            self.put_bot_msg(120, f"No {ext} files found.")
            return None

        lines: list[str] = []
        cmd_map: dict[str, Path] = {}
        for idx, path in enumerate(files):
            cmd = f"F{idx}"
            cmd_map[cmd] = path
            lines.append(f"!{cmd};{path.name}")
        lines.append("Exit")

        selection = self.show_scroll(lines, title, obj_flag=True)
        if not selection:
            return None
        return cmd_map.get(selection)

    def _load_world_from_path(self, path: Path) -> bool:
        try:
            loaded = load_world(str(path))
        except Exception:
            self.put_bot_msg(200, f"Could not load {path.name}")
            return False

        self.world = loaded
        self._world_file = path
        if path.suffix.upper() == c.WORLD_EXT:
            self._world_origin_file = path
            if not self.world.inv.orig_name:
                self.world.inv.orig_name = path.stem.upper()
        elif self.world.inv.orig_name:
            origin = Path(f"{self.world.inv.orig_name}{c.WORLD_EXT}")
            if origin.exists():
                self._world_origin_file = origin

        if self.world.num_rooms < 0:
            self.world.num_rooms = 0
        if not (0 <= self.world.inv.room <= self.world.num_rooms):
            self.world.inv.room = 0
        self.entry_room = self.world.inv.room
        self.key_buffer.clear()
        self.move_queue.clear()
        self.bot_msg_ticks = 0
        self._death_score_noted = False
        self._load_hi_scores()
        return True

    def _start_play(self, reload_original: bool) -> None:
        if reload_original and self._world_origin_file and self._world_origin_file.exists():
            if not self._load_world_from_path(self._world_origin_file):
                return

        if not (0 <= self.entry_room <= self.world.num_rooms):
            self.entry_room = self.world.inv.room
        self.change_room(self.entry_room)
        self._set_play_mode(c.PLAYER)
        self.note_enter_new_room()
        self.standby = True
        self._standby_blink_visible = True
        self._standby_blink_last_ms = 0
        self.counter = self.random.randrange(100)
        self.obj_num = self.room.num_objs + 1
        self._death_score_noted = False

    def _hi_scores_path(self) -> Path | None:
        name = self.world.inv.orig_name.strip()
        if not name:
            return None
        if self._world_origin_file is not None:
            return self._world_origin_file.parent / f"{name}{c.HI_EXT}"
        if self._world_file is not None:
            return self._world_file.parent / f"{name}{c.HI_EXT}"
        return Path.cwd() / f"{name}{c.HI_EXT}"

    def _load_hi_scores(self) -> None:
        self._hi_scores = [("", -1) for _ in range(c.NUM_HI)]
        path = self._hi_scores_path()
        if path is None:
            return

        try:
            raw = path.read_bytes()
        except OSError:
            return

        entry_size = 53
        total_size = entry_size * c.NUM_HI
        if len(raw) < total_size:
            return

        loaded: list[tuple[str, int]] = []
        for idx in range(c.NUM_HI):
            ofs = idx * entry_size
            name_len = min(raw[ofs], 50)
            name = raw[ofs + 1 : ofs + 1 + name_len].decode("cp437", errors="replace")
            score = int.from_bytes(raw[ofs + 51 : ofs + 53], byteorder="little", signed=True)
            loaded.append((name, score))
        self._hi_scores = loaded

    def _save_hi_scores(self) -> None:
        path = self._hi_scores_path()
        if path is None:
            return

        payload = bytearray()
        for idx in range(c.NUM_HI):
            name, score = self._hi_scores[idx] if idx < len(self._hi_scores) else ("", -1)
            enc = name.encode("cp437", errors="replace")[:50]
            payload.append(len(enc))
            payload.extend(enc.ljust(50, b"\x00"))
            payload.extend(int(score).to_bytes(2, byteorder="little", signed=True))

        try:
            path.write_bytes(bytes(payload))
        except OSError:
            self.put_bot_msg(200, f"Could not save {path.name}")

    def _set_view_hi_lines(self) -> list[str]:
        lines = ["Score  Name", "-----  ----------------------------------"]
        for name, score in self._hi_scores:
            if name:
                lines.append(f"{score:>5}  {name}")
        return lines

    def _view_hi(self, n: int) -> None:
        del n  # Maintained for parity with Pascal signature.
        lines = self._set_view_hi_lines()
        if len(lines) <= 2:
            return

        title_name = self.world.inv.orig_name if self.world.inv.orig_name else "Untitled"
        self.show_scroll(lines, f"High scores for {title_name}", obj_flag=False)

    def _prompt_high_score_name(self, prompt: str) -> str:
        if self._renderer is None or self._screen is None:
            return ""

        clock = self._clock or pygame.time.Clock()
        name = ""
        max_name_len = 50
        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    return ""
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return name
                if event.key == pygame.K_ESCAPE:
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return ""
                if event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n\t":
                    if len(name) < max_name_len:
                        name += event.unicode

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._renderer.draw_text(1, c.YS - 2, (" " + prompt)[: c.XS], 0x1F)
            shown = name if len(name) <= c.XS - 3 else name[-(c.XS - 3) :]
            self._renderer.draw_text(1, c.YS - 1, ("> " + shown + "_")[: c.XS], 0x1E)
            pygame.display.flip()
            self._ui_wait(clock)

        return ""

    def _input_line(self, prompt: str, initial: str = "", max_len: int = 50) -> str | None:
        if self._renderer is None or self._screen is None:
            return initial

        clock = self._clock or pygame.time.Clock()
        value = initial[:max_len]
        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    return None
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return value
                if event.key == pygame.K_ESCAPE:
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return None
                if event.key == pygame.K_BACKSPACE:
                    value = value[:-1]
                elif event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n\t":
                    if len(value) < max_len:
                        value += event.unicode

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._renderer.draw_text(1, c.YS - 2, (" " + prompt)[: c.XS], 0x1F)
            shown = value if len(value) <= c.XS - 3 else value[-(c.XS - 3) :]
            self._renderer.draw_text(1, c.YS - 1, ("> " + shown + "_")[: c.XS], 0x1E)
            pygame.display.flip()
            self._ui_wait(clock)
        return None

    def in_yn(self, prompt: str, default: bool = False) -> bool:
        if self._renderer is None or self._screen is None:
            return default

        clock = self._clock or pygame.time.Clock()
        cur = 0 if default else 1
        options = ("Yes", "No")
        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    return default
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    cur = max(0, cur - 1)
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    cur = min(1, cur + 1)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return cur == 0
                elif event.key == pygame.K_ESCAPE:
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return default

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._renderer.draw_text(2, c.YS - 2, prompt[: c.XS - 2], 0x1F)
            yes_attr = 0x1C if cur == 0 else 0x1E
            no_attr = 0x1C if cur == 1 else 0x1E
            self._renderer.draw_text(2, c.YS - 1, " Yes ", yes_attr)
            self._renderer.draw_text(8, c.YS - 1, " No ", no_attr)
            pygame.display.flip()
            self._ui_wait(clock)
        return default

    def in_string(self, x: int, y: int, max_len: int, prompt: str = "Input:", initial: str = "") -> str | None:
        del x, y
        return self._input_line(prompt, initial=initial, max_len=max_len)

    def in_num(self, x: int, y: int, prompt: str, val: int) -> int:
        text = self.in_string(x, y, 10, prompt, str(val))
        if text is None:
            return val
        try:
            return int(text.strip())
        except ValueError:
            return val

    def in_char(self, x: int, y: int, prompt: str, val: int) -> int:
        parsed = self.in_num(x, y, prompt, val)
        return max(1, min(255, parsed))

    def in_choice(self, y: int, prompt: str, choices: list[str], val: int = 0) -> int:
        del y
        if not choices:
            return 0
        if self._renderer is None or self._screen is None:
            return max(0, min(len(choices) - 1, val))

        clock = self._clock or pygame.time.Clock()
        cur = max(0, min(len(choices) - 1, val))
        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    return cur
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_UP, pygame.K_LEFT):
                    cur = (cur - 1) % len(choices)
                elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                    cur = (cur + 1) % len(choices)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return cur
                elif event.key == pygame.K_ESCAPE:
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return val

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._renderer.draw_text(2, c.YS - 2, prompt[: c.XS - 2], 0x1F)
            rendered = "  ".join(f"[{cname}]" if i == cur else cname for i, cname in enumerate(choices))
            self._renderer.draw_text(2, c.YS - 1, rendered[: c.XS - 2], 0x1E)
            pygame.display.flip()
            self._ui_wait(clock)
        return cur

    def in_dir(self, y: int, prompt: str) -> tuple[int, int]:
        del y
        if self._renderer is None or self._screen is None:
            return (0, -1)

        clock = self._clock or pygame.time.Clock()
        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    return (0, -1)
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_UP, pygame.K_KP8):
                    return (0, -1)
                if event.key in (pygame.K_DOWN, pygame.K_KP2):
                    return (0, 1)
                if event.key in (pygame.K_LEFT, pygame.K_KP4):
                    return (-1, 0)
                if event.key in (pygame.K_RIGHT, pygame.K_KP6):
                    return (1, 0)
                if event.key == pygame.K_ESCAPE:
                    return (0, -1)

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._renderer.draw_text(2, c.YS - 2, prompt[: c.XS - 2], 0x1F)
            self._renderer.draw_text(2, c.YS - 1, "Use an arrow key", 0x1E)
            pygame.display.flip()
            self._ui_wait(clock)
        return (0, -1)

    def in_fancy(self, prompt: str) -> str:
        text = self.in_string(1, c.YS - 1, 50, prompt, "")
        return text if text is not None else ""

    def _note_score(self, score: int) -> None:
        rank = 1
        while rank <= c.NUM_HI and score < self._hi_scores[rank - 1][1]:
            rank += 1
        if rank > c.NUM_HI or score <= 0:
            return

        for idx in range(c.NUM_HI - 1, rank - 1, -1):
            self._hi_scores[idx] = self._hi_scores[idx - 1]
        self._hi_scores[rank - 1] = ("-- You! --", score)

        title_name = self.world.inv.orig_name if self.world.inv.orig_name else "Untitled"
        self.show_scroll(
            self._set_view_hi_lines(),
            f"New high score for {title_name}",
            obj_flag=False,
        )

        name = self._prompt_high_score_name("Congratulations!  Enter your name:")
        self._hi_scores[rank - 1] = (name[:50], score)
        self._save_hi_scores()

    def _handle_player_death(self) -> None:
        if self.play_mode != c.PLAYER or self._death_score_noted:
            return
        self._death_score_noted = True
        self.sound_stop()

        self._load_hi_scores()
        self._note_score(self.world.inv.score)

        dead_room = self.world.inv.room
        if 0 <= 0 <= self.world.num_rooms:
            self.change_room(0)
        self.entry_room = dead_room
        self._set_play_mode(c.MONITOR)
        self.standby = False
        self.key_buffer.clear()
        self.move_queue.clear()
        self.control = ControlState()
        self.obj_num = self.room.num_objs + 1

    def ask_quit_game(self) -> bool:
        if self.world.inv.strength <= 0:
            self._handle_player_death()
            return True
        if not self.in_yn("Quit current game?", default=False):
            return False
        self.sound_stop()
        self.entry_room = self.world.inv.room
        if 0 <= 0 <= self.world.num_rooms:
            self.change_room(0)
        self._set_play_mode(c.MONITOR)
        self.standby = False
        self.key_buffer.clear()
        self.move_queue.clear()
        self.control = ControlState()
        return True

    def secret_cmd(self) -> None:
        text = self.in_string(1, c.YS - 1, 60, "Secret command:", "")
        if not text:
            return

        cmd = text.strip()
        if not cmd:
            return
        self.sound_add(10, snd.SFX_SECRET_CMD)

        ucmd = cmd.upper()
        if ucmd.startswith("+") and len(ucmd) > 1:
            self.oop.set_flag(ucmd[1:])
            self.put_bot_msg(120, f"Flag set: {ucmd[1:]}")
            return
        if ucmd.startswith("-") and len(ucmd) > 1:
            self.oop.clear_flag(ucmd[1:])
            self.put_bot_msg(120, f"Flag cleared: {ucmd[1:]}")
            return

        if self.oop.flag_num("DEBUG") < 0:
            self.put_bot_msg(120, "Set DEBUG flag first.")
            return

        parts = ucmd.split()
        head = parts[0]
        arg = parts[1] if len(parts) > 1 else ""
        if head == "HEALTH":
            self.world.inv.strength = int(arg) if arg.lstrip("-").isdigit() else 100
        elif head == "AMMO":
            self.world.inv.ammo = int(arg) if arg.lstrip("-").isdigit() else 100
        elif head == "GEMS":
            self.world.inv.gems = int(arg) if arg.lstrip("-").isdigit() else 100
        elif head == "TORCHES":
            self.world.inv.torches = int(arg) if arg.lstrip("-").isdigit() else 20
        elif head == "TIME":
            self.world.inv.room_time = int(arg) if arg.lstrip("-").isdigit() else 0
        elif head == "DARK":
            self.room.room_info.is_dark = not self.room.room_info.is_dark
        elif head == "ZAP":
            for idx in range(self.room.num_objs, 0, -1):
                if idx < len(self.room.objs) and self.info[self.room.board[self.room.objs[idx].x][self.room.objs[idx].y].kind].killable:
                    self.kill_obj(idx)
        elif head == "KEY":
            if arg.isdigit():
                key_idx = int(arg) - 1
                if 0 <= key_idx < 7:
                    self.world.inv.keys[key_idx] = True
        elif head == "NOKEY":
            if arg.isdigit():
                key_idx = int(arg) - 1
                if 0 <= key_idx < 7:
                    self.world.inv.keys[key_idx] = False
        else:
            self.put_bot_msg(120, "Unknown secret command.")
            return
        self.put_bot_msg(120, "Secret command applied.")

    def new_game(self) -> None:
        self.world = make_new_world()
        self.info = init_info_play()
        self.entry_room = 0
        self.counter = self.random.randrange(1, 100)
        self.obj_num = 0
        self.standby = False
        self._death_score_noted = False
        self._set_play_mode(c.MONITOR)
        self.room.board[self.player.x][self.player.y] = BoardCell(c.MONITOR, self.info[c.MONITOR].col)

    def pdraw_board(self) -> None:
        if self._renderer is None or self._screen is None:
            return
        cells = [(x, y) for y in range(1, c.YS + 1) for x in range(1, c.XS + 1)]
        self.random.shuffle(cells)
        for idx, (x, y) in enumerate(cells):
            self._renderer.draw_glyph(x - 1, y - 1, 0xB1, 0x08 + (idx % 7))
            if (idx % 120) == 0:
                self._service_sound()
                pygame.display.flip()
        self._renderer.clear()
        self._draw_board(self._renderer)
        self._draw_panel(self._renderer)
        pygame.display.flip()

    def _handle_monitor_key(self, key: str) -> None:
        key_u = key.upper()
        if not key_u or key_u == "\x00":
            return

        if key_u == "W":
            picked = self._select_game_file(c.WORLD_EXT, "ZZT Worlds")
            if picked and self._load_world_from_path(picked):
                self.entry_room = self.world.inv.room
                self._set_play_mode(c.MONITOR)
                self.standby = False
                self.put_bot_msg(120, f"Loaded {picked.name}")
            return

        if key_u == "R":
            picked = self._select_game_file(c.SAVE_EXT, "Saved Games")
            if picked and self._load_world_from_path(picked):
                self.entry_room = self.world.inv.room
                self._start_play(reload_original=False)
            return

        if key_u == "P":
            self._start_play(reload_original=self.world.inv.play_flag)
            return

        if key_u == "H":
            self._load_hi_scores()
            self._view_hi(1)
            return

        if key_u == "A":
            self.put_bot_msg(180, "About/help docs: ref/HELP/ABOUT.HLP")
            return

        if key_u == "S":
            self.speed = 1 if self.speed >= 9 else self.speed + 1
            self.game_cycle_ms = self.speed * 20
            self.put_bot_msg(120, f"Game speed: {self.speed}")
            return

        if key_u == "E":
            from .editor import BoardEditor

            editor = BoardEditor(self)
            editor.design_board()
            return

        if key_u == "|":
            self.secret_cmd()
            return

        if key_u in {"N"}:
            self.new_game()
            return

        if key_u in {"\x1B", "Q"}:
            self.exit_program = True

    def _standby_step_player(self, dx: int, dy: int) -> None:
        src_x, src_y = self.player.x, self.player.y
        dst_x = src_x + dx
        dst_y = src_y + dy
        self.player.x = dst_x
        self.player.y = dst_y
        self.player.under = copy.deepcopy(self.room.board[dst_x][dst_y])
        self.room.board[dst_x][dst_y] = BoardCell(c.PLAYER, self.info[c.PLAYER].col)
        if self.world.inv.torch_time > 0:
            self.do_area(dst_x, dst_y, 0)
            self.do_area(src_x, src_y, 0)

    def _add_obj_to_room(self, room: Room, x: int, y: int, kind: int, color: int, cycle: int) -> int:
        if len(room.objs) - 1 >= c.MAX_OBJS:
            return -1
        proto = Obj()
        obj = copy.deepcopy(proto)
        obj.x = x
        obj.y = y
        obj.cycle = cycle
        obj.under = copy.deepcopy(room.board[x][y])
        room.objs.append(obj)

        if self.info[room.board[x][y].kind].terrain:
            room.board[x][y].color = (color & 0x0F) + (room.board[x][y].color & 0x70)
        else:
            room.board[x][y].color = color
        room.board[x][y].kind = kind
        return len(room.objs) - 1

    def obj_at(self, x: int, y: int) -> int:
        for idx, obj in enumerate(self.room.objs):
            if obj.x == x and obj.y == y:
                return idx
        return -1

    def add_obj(self, x: int, y: int, kind: int, color: int, cycle: int, prototype: Obj | None = None) -> int:
        if len(self.room.objs) - 1 >= c.MAX_OBJS:
            return -1
        if prototype is None:
            prototype = Obj()
        obj = copy.deepcopy(prototype)
        obj.x = x
        obj.y = y
        obj.cycle = cycle
        obj.under = copy.deepcopy(self.room.board[x][y]) if y > 0 else BoardCell(c.EMPTY, 0)
        obj.offset = 0
        self.room.objs.append(obj)

        if y > 0:
            if self.info[self.room.board[x][y].kind].terrain:
                self.room.board[x][y].color = (color & 0x0F) + (self.room.board[x][y].color & 0x70)
            else:
                self.room.board[x][y].color = color
            self.room.board[x][y].kind = kind
        return len(self.room.objs) - 1

    def kill_obj(self, n: int) -> None:
        if n <= 0 or n >= len(self.room.objs):
            return

        obj = self.room.objs[n]
        if obj.y > 0:
            self.room.board[obj.x][obj.y] = copy.deepcopy(obj.under)

        for i in range(1, len(self.room.objs)):
            if self.room.objs[i].child >= n:
                self.room.objs[i].child = -1 if self.room.objs[i].child == n else self.room.objs[i].child - 1
            if self.room.objs[i].parent >= n:
                self.room.objs[i].parent = -1 if self.room.objs[i].parent == n else self.room.objs[i].parent - 1

        del self.room.objs[n]
        if n < self.obj_num:
            self.obj_num -= 1

    def move_obj(self, n: int, x: int, y: int) -> None:
        if n < 0 or n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        old_x, old_y = obj.x, obj.y

        old_under = copy.deepcopy(obj.under)
        obj.under = copy.deepcopy(self.room.board[x][y])

        src_kind = self.room.board[old_x][old_y].kind
        src_color = self.room.board[old_x][old_y].color
        dst_kind = self.room.board[x][y].kind
        dst_color = self.room.board[x][y].color

        if src_kind == c.PLAYER:
            self.room.board[x][y].color = src_color
        elif dst_kind == c.EMPTY:
            self.room.board[x][y].color = src_color & 0x0F
        else:
            self.room.board[x][y].color = (src_color & 0x0F) + (dst_color & 0x70)
        self.room.board[x][y].kind = src_kind

        self.room.board[old_x][old_y] = old_under
        obj.x, obj.y = x, y

    def move_to(self, x1: int, y1: int, x2: int, y2: int) -> None:
        obj_idx = self.obj_at(x1, y1)
        if obj_idx >= 0:
            self.move_obj(obj_idx, x2, y2)
        else:
            self.room.board[x2][y2] = copy.deepcopy(self.room.board[x1][y1])
            self.room.board[x1][y1] = BoardCell(c.EMPTY, 0)

    def free_cell(self, x: int, y: int) -> bool:
        idx = self.obj_at(x, y)
        if idx > 0:
            self.kill_obj(idx)
            return True
        if idx < 0:
            if not self.info[self.room.board[x][y].kind].terrain:
                self.room.board[x][y].kind = c.EMPTY
            return True
        return False

    def _in_board(self, x: int, y: int) -> bool:
        return 0 <= x <= c.XS + 1 and 0 <= y <= c.YS + 1

    def signf(self, val: int) -> int:
        return 1 if val > 0 else -1 if val < 0 else 0

    def distf(self, a: int, b: int) -> int:
        return abs(a - b)

    def pick_random_dir(self) -> tuple[int, int]:
        dx = self.random.randrange(3) - 1
        if dx == 0:
            return (0, self.random.randrange(2) * 2 - 1)
        return (dx, 0)

    def seek_player(self, x: int, y: int) -> tuple[int, int]:
        dx = 0
        dy = 0
        if self.random.randrange(2) < 1 or self.player.y == y:
            dx = self.signf(self.player.x - x)
        if dx == 0:
            dy = self.signf(self.player.y - y)
        if self.world.inv.ener_time > 0:
            dx, dy = -dx, -dy
        return dx, dy

    def put_bot_msg(self, duration: int, msg: str) -> None:
        self.room.room_info.bot_msg = msg
        self.bot_msg_ticks = max(0, duration // (self.game_cycle_ms // 10 + 1))

    def print_stats(self) -> None:
        # HUD is redrawn every frame from inventory values.
        pass

    def zap_obj(self, obj_idx: int) -> None:
        if obj_idx == 0:
            if self.world.inv.strength > 0:
                self.world.inv.strength -= 10
                if self.world.inv.strength < 0:
                    self.world.inv.strength = 0
                self.put_bot_msg(100, "Ouch!")
                if self.world.inv.strength > 0 and self.room.room_info.re_enter:
                    self.sound_add(4, snd.SFX_PLAYER_REENTER)
                    p = self.player
                    self.room.board[p.x][p.y] = BoardCell(c.EMPTY, 0)
                    p.x = self.room.room_info.start_x
                    p.y = self.room.room_info.start_y
                    self.room.board[p.x][p.y] = BoardCell(c.PLAYER, self.info[c.PLAYER].col)
                    self.standby = True
                if self.world.inv.strength > 0:
                    self.sound_add(4, snd.SFX_PLAYER_HURT)
                else:
                    self.sound_add(5, snd.SFX_PLAYER_DIE)
            return

        if 0 < obj_idx < len(self.room.objs):
            obj = self.room.objs[obj_idx]
            kind = self.room.board[obj.x][obj.y].kind
            if kind == c.BULLET:
                self.sound_add(3, snd.SFX_ZAP_BULLET)
            elif kind != c.PROG:
                self.sound_add(3, snd.SFX_ZAP_ENEMY)
            self.kill_obj(obj_idx)

    def zap(self, x: int, y: int) -> None:
        obj_idx = self.obj_at(x, y)
        if obj_idx >= 0:
            self.zap_obj(obj_idx)
        else:
            self.room.board[x][y] = BoardCell(c.EMPTY, 0)

    def zap_with(self, obj_idx: int, x: int, y: int) -> None:
        if obj_idx == 0 and self.world.inv.ener_time > 0:
            self.world.inv.score += self.info[self.room.board[x][y].kind].score
        else:
            self.zap_obj(obj_idx)
        if obj_idx > 0 and obj_idx <= self.obj_num:
            self.obj_num -= 1
        if self.room.board[x][y].kind == c.PLAYER and self.world.inv.ener_time > 0:
            self.world.inv.score += self.info[self.room.board[self.room.objs[obj_idx].x][self.room.objs[obj_idx].y].kind].score
        else:
            self.zap(x, y)
            self.sound_add(2, snd.SFX_SHOT_HIT)

    def try_fire(self, kind: int, x: int, y: int, dx: int, dy: int, who: int) -> bool:
        target = self.room.board[x + dx][y + dy]
        tkind = target.kind
        if self.info[tkind].go_thru or tkind == c.WATER:
            new_idx = self.add_obj(x + dx, y + dy, kind, self.info[kind].col, 1)
            if new_idx > 0:
                shot = self.room.objs[new_idx]
                shot.intel = who
                shot.xd = dx
                shot.yd = dy
                shot.rate = 100
                return True
            return False

        if tkind == c.BREAK_WALL or (
            self.info[tkind].killable and bool(who) == (tkind == c.PLAYER) and self.world.inv.ener_time <= 0
        ):
            self.zap(x + dx, y + dy)
            self.sound_add(2, snd.SFX_SHOT_HIT)
            return True
        return False

    def change_room(self, n: int) -> None:
        if not (0 <= n <= self.world.num_rooms):
            return
        if n == self.world.inv.room:
            return
        self.world.inv.room = n
        self.pdraw_board()

    def enter_passage(self, x: int, y: int) -> None:
        idx = self.obj_at(x, y)
        if idx < 0:
            return
        passage_color = self.room.board[x][y].color
        old_room = self.world.inv.room
        self.change_room(self.room.objs[idx].room)

        dest_x = 0
        dest_y = 0
        for tx in range(1, c.XS + 1):
            for ty in range(1, c.YS + 1):
                if (
                    self.room.board[tx][ty].kind == c.PASSAGE
                    and self.room.board[tx][ty].color == passage_color
                ):
                    dest_x, dest_y = tx, ty

        self.room.board[self.player.x][self.player.y] = BoardCell(c.EMPTY, 0)
        if dest_x:
            self.player.x = dest_x
            self.player.y = dest_y

        self.standby = True
        self.sound_add(4, snd.SFX_PASSAGE)
        self.note_enter_new_room()
        if self.world.inv.room != old_room:
            self.counter = self.random.randrange(100)

    def note_enter_new_room(self) -> None:
        self.room.room_info.start_x = self.player.x
        self.room.room_info.start_y = self.player.y
        if self.room.room_info.is_dark and self.world.first.enter_dark:
            self.put_bot_msg(200, "Room is dark - you need to light a torch!")
            self.world.first.enter_dark = False
        self.world.inv.room_time = 0

    def do_area(self, xc: int, yc: int, code: int) -> None:
        for tx in range(xc - c.TORCH_XS - 1, xc + c.TORCH_XS + 2):
            if not (1 <= tx <= c.XS):
                continue
            for ty in range(yc - c.TORCH_YS - 1, yc + c.TORCH_YS + 2):
                if not (1 <= ty <= c.YS):
                    continue
                dist_ok = (tx - xc) ** 2 + 2 * (ty - yc) ** 2 < c.TORCH_SIZE
                if code > 0 and dist_ok:
                    kind = self.room.board[tx][ty].kind
                    if code == 1:
                        obj_idx = self.obj_at(tx, ty)
                        if obj_idx > 0 and kind == c.PROG:
                            self.oop.lsend_msg(-obj_idx, "BOMBED", False)
                        if self.info[kind].killable or kind == c.SBOMB:
                            self.zap(tx, ty)
                        if kind in (c.EMPTY, c.BREAK_WALL):
                            self.room.board[tx][ty].kind = c.BREAK_WALL
                            self.room.board[tx][ty].color = self.random.randrange(7) + 9
                    else:
                        if kind == c.BREAK_WALL:
                            self.room.board[tx][ty].kind = c.EMPTY

    def push_thru_xporter(self, x: int, y: int, dx: int, dy: int) -> None:
        idx = self.obj_at(x + dx, y + dy)
        if idx < 0:
            return
        port = self.room.objs[idx]
        if (dx, dy) != (port.xd, port.yd):
            return

        # Pascal uses the transporter object's coordinates via a `with` block.
        new_x, new_y = port.x, port.y
        src_x, src_y = port.x - dx, port.y - dy
        dest_x = -1
        dest_y = -1
        done = False
        past_x = True

        while not done:
            new_x += dx
            new_y += dy
            if self.room.board[new_x][new_y].kind == c.BOUND:
                done = True
            elif past_x:
                past_x = False
                if not self.info[self.room.board[new_x][new_y].kind].go_thru:
                    self.push(new_x, new_y, dx, dy)
                if self.info[self.room.board[new_x][new_y].kind].go_thru:
                    done = True
                    dest_x, dest_y = new_x, new_y
                else:
                    dest_x = -1
            if self.room.board[new_x][new_y].kind == c.XPORTER:
                temp_idx = self.obj_at(new_x, new_y)
                if temp_idx >= 0:
                    t = self.room.objs[temp_idx]
                    if (t.xd, t.yd) == (-dx, -dy):
                        past_x = True

        if dest_x != -1:
            self.move_to(src_x, src_y, dest_x, dest_y)
            self.sound_add(3, snd.SFX_XPORT)

    def push(self, x: int, y: int, dx: int, dy: int) -> None:
        kind = self.room.board[x][y].kind
        if not (
            (kind == c.SLIDER_NS and dx == 0)
            or (kind == c.SLIDER_EW and dy == 0)
            or self.info[kind].movable
        ):
            return

        if self.room.board[x + dx][y + dy].kind == c.XPORTER:
            self.push_thru_xporter(x, y, dx, dy)
        elif self.room.board[x + dx][y + dy].kind != c.EMPTY:
            self.push(x + dx, y + dy, dx, dy)

        target_kind = self.room.board[x + dx][y + dy].kind
        if (not self.info[target_kind].go_thru) and self.info[target_kind].killable and target_kind != c.PLAYER:
            self.zap(x + dx, y + dy)

        if self.info[self.room.board[x + dx][y + dy].kind].go_thru:
            self.move_to(x, y, x + dx, y + dy)

    def invoke_touch(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        touch_name = self.info[self.room.board[x][y].kind].touch
        method = getattr(self, touch_name, self.touch_nothing)
        method(x, y, p, dir_xy)

    def invoke_update(self, obj_idx: int) -> None:
        if obj_idx >= len(self.room.objs):
            return
        obj = self.room.objs[obj_idx]
        if obj.x <= 0 or obj.y <= 0 or obj.x > c.XS or obj.y > c.YS:
            return
        kind = self.room.board[obj.x][obj.y].kind
        update_name = self.info[kind].update
        method = getattr(self, update_name, self.upd_nothing)
        method(obj_idx)

    # Touch handlers
    def touch_nothing(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        return

    def touch_enemy(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.zap_with(p, x, y)

    def touch_bomb(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        idx = self.obj_at(x, y)
        if idx < 0:
            return
        obj = self.room.objs[idx]
        if obj.intel == 0:
            obj.intel = 9
            self.put_bot_msg(200, "Bomb activated!")
            self.sound_add(4, snd.SFX_BOMB_ARM)
        else:
            self.push(x, y, dir_xy[0], dir_xy[1])

    def touch_xporter(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.push_thru_xporter(x - dir_xy[0], y - dir_xy[1], dir_xy[0], dir_xy[1])
        dir_xy[0] = 0
        dir_xy[1] = 0

    def touch_energizer(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.EMPTY
        self.world.inv.ener_time = c.ENER_LIFE
        self.sound_add(9, snd.SFX_ENERGIZER)
        if self.world.first.touch_ener:
            self.put_bot_msg(200, "Energizer - You are invincible")
            self.world.first.touch_ener = False
        self.oop.lsend_msg(0, "ALL:ENERGIZE", ignore_lock=False)

    def touch_prog(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        idx = self.obj_at(x, y)
        if idx > 0:
            self.oop.lsend_msg(-idx, "TOUCH", ignore_lock=False)

    def touch_key(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        d = self.room.board[x][y].color % 8
        d = min(max(d, 1), 7)
        if self.world.inv.keys[d - 1]:
            self.put_bot_msg(200, f"You already have a {c.COLORS[d]} key!")
            self.sound_add(2, snd.SFX_KEY_ALREADY)
        else:
            self.world.inv.keys[d - 1] = True
            self.room.board[x][y].kind = c.EMPTY
            self.put_bot_msg(200, f"You now have the {c.COLORS[d]} key.")
            self.sound_add(2, snd.SFX_KEY_GET)

    def touch_ammo(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.ammo += 5
        self.room.board[x][y].kind = c.EMPTY
        self.sound_add(2, snd.SFX_AMMO_GET)
        if self.world.first.got_ammo:
            self.world.first.got_ammo = False
            self.put_bot_msg(200, "Ammunition - 5 shots per container.")

    def touch_gem(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.gems += 1
        self.world.inv.strength += 1
        self.world.inv.score += 10
        self.room.board[x][y].kind = c.EMPTY
        self.sound_add(2, snd.SFX_GEM_GET)
        if self.world.first.got_gem:
            self.world.first.got_gem = False
            self.put_bot_msg(200, "Gems give you Health!")

    def touch_passage(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.enter_passage(x, y)
        dir_xy[0] = 0
        dir_xy[1] = 0

    def touch_door(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        d = (self.room.board[x][y].color // 0x10) % 8
        d = min(max(d, 1), 7)
        if self.world.inv.keys[d - 1]:
            self.room.board[x][y].kind = c.EMPTY
            self.world.inv.keys[d - 1] = False
            self.put_bot_msg(200, f"The {c.COLORS[d]} door is now open.")
            self.sound_add(3, snd.SFX_DOOR_OPEN)
        else:
            self.put_bot_msg(200, f"The {c.COLORS[d]} door is locked!")
            self.sound_add(3, snd.SFX_DOOR_LOCKED)

    def touch_push(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.push(x, y, dir_xy[0], dir_xy[1])
        self.sound_add(2, snd.SFX_PUSH)

    def touch_torch(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.torches += 1
        self.room.board[x][y].kind = c.EMPTY
        self.sound_add(3, snd.SFX_TORCH_GET)
        if self.world.first.got_torch:
            self.put_bot_msg(200, "Torch - used for lighting in the underground.")
            self.world.first.got_torch = False

    def touch_inviso_wall(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.NORM_WALL
        self.sound_add(3, snd.SFX_INVISO)
        self.put_bot_msg(100, "You are blocked by an invisible wall.")

    def touch_brush(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.EMPTY
        self.sound_add(3, snd.SFX_BRUSH)
        if self.world.first.make_path:
            self.world.first.make_path = False
            self.put_bot_msg(200, "A path is cleared through the forest.")

    def touch_fake_wall(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        if self.world.first.touch_fake:
            self.world.first.touch_fake = False
            self.put_bot_msg(150, "A fake wall - secret passage!")

    def touch_bound(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        new_x = self.player.x
        new_y = self.player.y
        room_dir = 3
        dx, dy = dir_xy
        if dy == -1:
            room_dir = 0
            new_y = c.YS
        elif dy == 1:
            room_dir = 1
            new_y = 1
        elif dx == -1:
            room_dir = 2
            new_x = c.XS
        else:
            room_dir = 3
            new_x = 1

        target_room = self.room.room_info.room_udlr[room_dir]
        if target_room == 0:
            return

        old_room = self.world.inv.room
        self.change_room(target_room)
        if self.room.board[new_x][new_y].kind != c.PLAYER:
            dxy = [dx, dy]
            self.invoke_touch(new_x, new_y, p, dxy)

        if self.info[self.room.board[new_x][new_y].kind].go_thru or self.room.board[new_x][new_y].kind == c.PLAYER:
            if self.room.board[new_x][new_y].kind != c.PLAYER:
                self.move_obj(0, new_x, new_y)
            dir_xy[0] = 0
            dir_xy[1] = 0
            self.note_enter_new_room()
        else:
            self.change_room(old_room)

    def touch_water(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.sound_add(3, snd.SFX_WATER_BLOCK)
        self.put_bot_msg(100, "Your way is blocked by water.")

    def touch_slime(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        temp_color = self.room.board[x][y].color
        idx = self.obj_at(x, y)
        if idx >= 0:
            self.zap_obj(idx)
        self.room.board[x][y].kind = c.BREAK_WALL
        self.room.board[x][y].color = temp_color
        self.sound_add(2, snd.SFX_SLIME_TOUCH)

    def touch_scroll(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        idx = self.obj_at(x, y)
        if idx > 0:
            self.sound_add(2, self.sound_music("c-c+d-d+e-e+f-f+g-g"))
            self.room.objs[idx].offset = 0
            self.oop.exec_obj(idx, "Scroll")
        idx2 = self.obj_at(x, y)
        if idx2 > 0:
            self.kill_obj(idx2)

    # Update handlers
    def upd_nothing(self, n: int) -> None:
        return

    def upd_special(self, n: int) -> None:
        return

    def upd_enemy(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if self.random.randrange(10) > obj.intel:
            dx, dy = self.pick_random_dir()
        else:
            dx, dy = self.seek_player(obj.x, obj.y)
        kind = self.room.board[obj.x + dx][obj.y + dy].kind
        if self.info[kind].go_thru:
            self.move_obj(n, obj.x + dx, obj.y + dy)
        elif kind == c.PLAYER:
            self.zap_with(n, obj.x + dx, obj.y + dy)

    def upd_s_enemy(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        fire_kind = c.SBOMB if obj.rate >= 0x80 else c.BULLET
        if self.random.randrange(10) * 3 <= (obj.rate % 0x80):
            flag = False
            if self.distf(obj.x, self.player.x) <= 2:
                flag = self.try_fire(fire_kind, obj.x, obj.y, 0, self.signf(self.player.y - obj.y), 1)
            if not flag and self.distf(obj.y, self.player.y) <= 2:
                self.try_fire(fire_kind, obj.x, obj.y, self.signf(self.player.x - obj.x), 0, 1)
        self.upd_enemy(n)

    def upd_wanderer(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.xd == 0 and obj.yd == 0:
            if self.random.randrange(17) >= (8 + obj.rate):
                if self.random.randrange(9) <= obj.intel:
                    obj.xd, obj.yd = self.seek_player(obj.x, obj.y)
                else:
                    obj.xd, obj.yd = self.pick_random_dir()
        else:
            if (obj.y == self.player.y or obj.x == self.player.x) and self.random.randrange(9) <= obj.intel:
                obj.xd, obj.yd = self.seek_player(obj.x, obj.y)
            kind = self.room.board[obj.x + obj.xd][obj.y + obj.yd].kind
            if kind == c.PLAYER:
                self.zap_with(n, obj.x + obj.xd, obj.y + obj.yd)
            elif self.info[kind].go_thru:
                self.move_obj(n, obj.x + obj.xd, obj.y + obj.yd)
                if self.random.randrange(17) >= (8 + obj.rate):
                    obj.xd = 0
                    obj.yd = 0
            else:
                obj.xd = 0
                obj.yd = 0

    def upd_chaser(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.x != self.player.x and self.distf(obj.y, self.player.y) <= (8 - obj.intel):
            dx, dy = self.signf(self.player.x - obj.x), 0
        elif self.distf(obj.x, self.player.x) <= (8 - obj.intel):
            dx, dy = 0, self.signf(self.player.y - obj.y)
        else:
            dx = dy = 0
        kind = self.room.board[obj.x + dx][obj.y + dy].kind
        if self.info[kind].go_thru:
            self.move_obj(n, obj.x + dx, obj.y + dy)
        elif kind in (c.PLAYER, c.BREAK_WALL):
            self.zap_with(n, obj.x + dx, obj.y + dy)

    def upd_centi_h(self, n: int) -> None:
        if n >= len(self.room.objs):
            return

        obj = self.room.objs[n]
        player = self.player
        obj.xd = self.signf(obj.xd)
        obj.yd = self.signf(obj.yd)

        def settle_stopped_head() -> None:
            self.room.board[obj.x][obj.y].kind = c.CENTI
            obj.parent = -1
            cur = n
            while self.room.objs[cur].child > 0:
                temp = self.room.objs[cur].child
                self.room.objs[cur].child = self.room.objs[cur].parent
                self.room.objs[cur].parent = temp
                cur = temp
            self.room.objs[cur].child = self.room.objs[cur].parent
            tail = self.room.objs[cur]
            if self._in_board(tail.x, tail.y):
                self.room.board[tail.x][tail.y].kind = c.CENTI_H

        def can_step(dx: int, dy: int) -> bool:
            tx = obj.x + dx
            ty = obj.y + dy
            if not self._in_board(tx, ty):
                return False
            kind = self.room.board[tx][ty].kind
            return self.info[kind].go_thru or kind == c.PLAYER

        if obj.x == player.x and self.random.randrange(10) < obj.intel:
            obj.yd = self.signf(player.y - obj.y)
            obj.xd = 0
        elif obj.y == player.y and self.random.randrange(10) < obj.intel:
            obj.xd = self.signf(player.x - obj.x)
            obj.yd = 0
        elif (self.random.randrange(10) * 4 < obj.rate) or (obj.xd == 0 and obj.yd == 0):
            obj.xd, obj.yd = self.pick_random_dir()

        if not can_step(obj.xd, obj.yd):
            old_dx, old_dy = obj.xd, obj.yd
            temp = obj.yd * (self.random.randrange(2) * 2 - 1)
            obj.yd = obj.xd * (self.random.randrange(2) * 2 - 1)
            obj.xd = temp
            if not can_step(obj.xd, obj.yd):
                obj.xd = -obj.xd
                obj.yd = -obj.yd
                if not can_step(obj.xd, obj.yd):
                    if can_step(-old_dx, -old_dy):
                        obj.xd = -old_dx
                        obj.yd = -old_dy
                    else:
                        obj.xd = 0
                        obj.yd = 0

        if obj.xd == 0 and obj.yd == 0:
            settle_stopped_head()
            return

        target_x = obj.x + obj.xd
        target_y = obj.y + obj.yd
        if not self._in_board(target_x, target_y):
            obj.xd = 0
            obj.yd = 0
            settle_stopped_head()
            return
        if self.room.board[target_x][target_y].kind == c.PLAYER:
            if obj.child > 0 and obj.child < len(self.room.objs):
                child = self.room.objs[obj.child]
                if self._in_board(child.x, child.y):
                    self.room.board[child.x][child.y].kind = c.CENTI_H
                child.xd = obj.xd
                child.yd = obj.yd
            self.zap_with(n, target_x, target_y)
            return

        self.move_obj(n, target_x, target_y)

        cur = n
        while cur != -1 and cur < len(self.room.objs):
            cur_obj = self.room.objs[cur]
            dx = self.signf(cur_obj.xd)
            dy = self.signf(cur_obj.yd)
            temp_x = cur_obj.x - dx
            temp_y = cur_obj.y - dy

            if cur_obj.child < 0:
                for cx, cy in ((temp_x - dx, temp_y - dy), (temp_x - dy, temp_y - dx), (temp_x + dy, temp_y + dx)):
                    if not self._in_board(cx, cy):
                        continue
                    if self.room.board[cx][cy].kind != c.CENTI:
                        continue
                    candidate = self.obj_at(cx, cy)
                    if candidate >= 0 and self.room.objs[candidate].parent < 0:
                        cur_obj.child = candidate
                        break

            if cur_obj.child > 0 and cur_obj.child < len(self.room.objs):
                child = self.room.objs[cur_obj.child]
                child.parent = cur
                child.intel = cur_obj.intel
                child.rate = cur_obj.rate
                child.xd = self.signf(temp_x - child.x)
                child.yd = self.signf(temp_y - child.y)
                if self._in_board(temp_x, temp_y):
                    self.move_obj(cur_obj.child, temp_x, temp_y)

            cur = cur_obj.child

    def upd_centi(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.parent < 0:
            if obj.parent < -1:
                self.room.board[obj.x][obj.y].kind = c.CENTI_H
            else:
                obj.parent -= 1

    def upd_bullet(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        first_ric = True

        while True:
            tx = obj.x + obj.xd
            ty = obj.y + obj.yd
            temp_kind = self.room.board[tx][ty].kind

            if self.info[temp_kind].go_thru or temp_kind == c.WATER:
                self.move_obj(n, tx, ty)
                return

            if temp_kind == c.RICOCHET and first_ric:
                obj.xd = -obj.xd
                obj.yd = -obj.yd
                self.sound_add(1, snd.SFX_BULLET_RICOCHET)
                first_ric = False
                continue

            if temp_kind == c.BREAK_WALL or (
                self.info[temp_kind].killable and (temp_kind == c.PLAYER or obj.intel == 0)
            ):
                if self.info[temp_kind].score:
                    self.world.inv.score += self.info[temp_kind].score
                self.zap_with(n, tx, ty)
                return

            if self.room.board[obj.x + obj.yd][obj.y + obj.xd].kind == c.RICOCHET and first_ric:
                old = obj.xd
                obj.xd = -obj.yd
                obj.yd = -old
                self.sound_add(1, snd.SFX_BULLET_RICOCHET)
                first_ric = False
                continue

            if self.room.board[obj.x - obj.yd][obj.y - obj.xd].kind == c.RICOCHET and first_ric:
                old = obj.xd
                obj.xd = obj.yd
                obj.yd = old
                self.sound_add(1, snd.SFX_BULLET_RICOCHET)
                first_ric = False
                continue

            self.kill_obj(n)
            if temp_kind in (c.PROG, c.SCROLL):
                temp_obj = self.obj_at(tx, ty)
                if temp_obj > 0:
                    self.oop.lsend_msg(-temp_obj, "SHOT", ignore_lock=False)
            return

    def revolve(self, x: int, y: int, dirc: int) -> None:
        start = 0 if dirc == 1 else 7
        end = 8 if dirc == 1 else -1

        temp_cells: dict[int, BoardCell] = {}
        can_move = True

        cidx = start
        while cidx != end:
            cell = copy.deepcopy(self.room.board[x + c.CLOCK_X[cidx]][y + c.CLOCK_Y[cidx]])
            temp_cells[cidx] = cell
            if cell.kind == c.EMPTY:
                can_move = True
            elif not self.info[cell.kind].movable:
                can_move = False
            cidx += dirc

        cidx = start
        while cidx != end:
            cell = temp_cells[cidx]
            if can_move:
                if self.info[cell.kind].movable:
                    x1 = x + c.CLOCK_X[(cidx - dirc + 8) % 8]
                    y1 = y + c.CLOCK_Y[(cidx - dirc + 8) % 8]
                    if self.info[cell.kind].cycle > -1:
                        src_x = x + c.CLOCK_X[cidx]
                        src_y = y + c.CLOCK_Y[cidx]
                        temp_obj = self.obj_at(src_x, src_y)
                        if temp_obj >= 0:
                            # Preserve Pascal MoveObj side-effects by restoring the
                            # source board cell after rotation bookkeeping.
                            cell_before = copy.deepcopy(self.room.board[src_x][src_y])
                            self.room.board[src_x][src_y] = copy.deepcopy(temp_cells[cidx])
                            self.room.board[x1][y1].kind = c.EMPTY
                            self.move_obj(temp_obj, x1, y1)
                            self.room.board[src_x][src_y] = cell_before
                    else:
                        self.room.board[x1][y1] = copy.deepcopy(cell)

                    next_cell = temp_cells[(cidx + dirc + 8) % 8]
                    if not self.info[next_cell.kind].movable:
                        self.room.board[x + c.CLOCK_X[cidx]][y + c.CLOCK_Y[cidx]].kind = c.EMPTY
                else:
                    can_move = False
            elif cell.kind == c.EMPTY:
                can_move = True
            elif not self.info[cell.kind].movable:
                can_move = False

            cidx += dirc

    def upd_shooter(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        fire_kind = c.SBOMB if obj.rate >= 0x80 else c.BULLET
        if self.random.randrange(9) < (obj.rate % 0x80):
            if self.random.randrange(9) <= obj.intel:
                flag = False
                if self.distf(obj.x, self.player.x) <= 2:
                    flag = self.try_fire(fire_kind, obj.x, obj.y, 0, self.signf(self.player.y - obj.y), 1)
                if not flag and self.distf(obj.y, self.player.y) <= 2:
                    self.try_fire(fire_kind, obj.x, obj.y, self.signf(self.player.x - obj.x), 0, 1)
            else:
                dx, dy = self.pick_random_dir()
                self.try_fire(fire_kind, obj.x, obj.y, dx, dy, 1)

    def upd_conveyor_cw(self, n: int) -> None:
        if n < len(self.room.objs):
            obj = self.room.objs[n]
            self.revolve(obj.x, obj.y, 1)

    def upd_conveyor_ccw(self, n: int) -> None:
        if n < len(self.room.objs):
            obj = self.room.objs[n]
            self.revolve(obj.x, obj.y, -1)

    def upd_bomb(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.intel > 0:
            obj.intel -= 1
            if obj.intel == 1:
                self.sound_add(1, snd.SFX_BOMB_DETONATE)
                self.do_area(obj.x, obj.y, 1)
            elif obj.intel == 0:
                tx, ty = obj.x, obj.y
                self.kill_obj(n)
                self.do_area(tx, ty, 2)
            elif (obj.intel % 2) == 0:
                self.sound_add(1, snd.SFX_BOMB_TICK_EVEN)
            else:
                self.sound_add(1, snd.SFX_BOMB_TICK_ODD)

    def upd_xporter(self, n: int) -> None:
        return

    def upd_sbomb(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        obj.rate -= 1
        if obj.rate <= 0:
            self.kill_obj(n)
            return
        if obj.rate % 2 == 0:
            obj.xd, obj.yd = self.seek_player(obj.x, obj.y)
            kind = self.room.board[obj.x + obj.xd][obj.y + obj.yd].kind
            if kind in (c.PLAYER, c.BREAK_WALL):
                self.zap_with(n, obj.x + obj.xd, obj.y + obj.yd)
            else:
                if not self.info[kind].go_thru:
                    self.push(obj.x + obj.xd, obj.y + obj.yd, obj.xd, obj.yd)
                nkind = self.room.board[obj.x + obj.xd][obj.y + obj.yd].kind
                if self.info[nkind].go_thru or nkind == c.WATER:
                    self.move_obj(n, obj.x + obj.xd, obj.y + obj.yd)

    def upd_slime(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.intel < obj.rate:
            obj.intel += 1
            return

        slime_color = self.room.board[obj.x][obj.y].color
        obj.intel = 0
        tx, ty = obj.x, obj.y
        num = 0
        for i in range(4):
            nx = tx + c.UDLR_X[i]
            ny = ty + c.UDLR_Y[i]
            if self.info[self.room.board[nx][ny].kind].go_thru:
                if num == 0:
                    self.move_obj(n, nx, ny)
                    self.room.board[tx][ty].color = slime_color
                    self.room.board[tx][ty].kind = c.BREAK_WALL
                else:
                    idx = self.add_obj(nx, ny, c.SLIME, slime_color, self.info[c.SLIME].cycle)
                    if idx > 0:
                        self.room.objs[idx].rate = obj.rate
                num += 1

        if num == 0:
            self.kill_obj(n)
            self.room.board[tx][ty].kind = c.BREAK_WALL
            self.room.board[tx][ty].color = slime_color

    def upd_shark(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if self.random.randrange(10) > obj.intel:
            dx, dy = self.pick_random_dir()
        else:
            dx, dy = self.seek_player(obj.x, obj.y)
        kind = self.room.board[obj.x + dx][obj.y + dy].kind
        if kind == c.WATER:
            self.move_obj(n, obj.x + dx, obj.y + dy)
        elif kind == c.PLAYER:
            self.zap_with(n, obj.x + dx, obj.y + dy)

    def upd_prog(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.offset >= 0:
            self.oop.exec_obj(n, "Interaction")
        if obj.xd or obj.yd:
            kind = self.room.board[obj.x + obj.xd][obj.y + obj.yd].kind
            if self.info[kind].go_thru:
                self.move_obj(n, obj.x + obj.xd, obj.y + obj.yd)
            else:
                self.oop.lsend_msg(-n, "THUD", ignore_lock=False)

    def upd_duper(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        if obj.intel <= 4:
            obj.intel += 1
            return

        obj.intel = 0
        src_x = obj.x + obj.xd
        src_y = obj.y + obj.yd
        dst_x = obj.x - obj.xd
        dst_y = obj.y - obj.yd

        if self.room.board[dst_x][dst_y].kind == c.PLAYER:
            dxy = [self.control.dx, self.control.dy]
            self.invoke_touch(src_x, src_y, 0, dxy)
        else:
            if self.room.board[dst_x][dst_y].kind != c.EMPTY:
                self.push(dst_x, dst_y, -obj.xd, -obj.yd)

            if self.room.board[dst_x][dst_y].kind == c.EMPTY:
                temp_obj = self.obj_at(src_x, src_y)
                if temp_obj > 0:
                    if len(self.room.objs) - 1 < (c.MAX_OBJS + 24):
                        src_obj = self.room.objs[temp_obj]
                        self.add_obj(
                            dst_x,
                            dst_y,
                            self.room.board[src_x][src_y].kind,
                            self.room.board[src_x][src_y].color,
                            src_obj.cycle,
                            src_obj,
                        )
                elif temp_obj != 0:
                    self.room.board[dst_x][dst_y] = copy.deepcopy(self.room.board[src_x][src_y])
                self.sound_add(3, snd.SFX_DUPER_OK)
            else:
                self.sound_add(3, snd.SFX_DUPER_FAIL)

        obj.cycle = (9 - obj.rate) * 3

    def upd_pusher(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        obj = self.room.objs[n]
        tx, ty = obj.x, obj.y
        if not self.info[self.room.board[obj.x + obj.xd][obj.y + obj.yd].kind].go_thru:
            self.push(obj.x + obj.xd, obj.y + obj.yd, obj.xd, obj.yd)

        n2 = self.obj_at(tx, ty)
        if n2 < 0:
            return
        obj2 = self.room.objs[n2]
        if self.info[self.room.board[obj2.x + obj2.xd][obj2.y + obj2.yd].kind].go_thru:
            self.move_obj(n2, obj2.x + obj2.xd, obj2.y + obj2.yd)
            self.sound_add(2, snd.SFX_PUSH)
            if self.room.board[obj2.x - obj2.xd * 2][obj2.y - obj2.yd * 2].kind == c.PUSHER:
                temp_obj = self.obj_at(obj2.x - obj2.xd * 2, obj2.y - obj2.yd * 2)
                if temp_obj >= 0:
                    o = self.room.objs[temp_obj]
                    if (o.xd, o.yd) == (obj2.xd, obj2.yd):
                        self.upd_pusher(temp_obj)

    def upd_player(self, n: int) -> None:
        p = self.player

        if self.world.inv.ener_time > 0:
            self.info[c.PLAYER].ch = 0x01 if self.info[c.PLAYER].ch == 0x02 else 0x02
            if self.counter % 2:
                self.room.board[p.x][p.y].color = 0x0F
            else:
                self.room.board[p.x][p.y].color = 0x0F + 0x10 * ((self.counter % 7) + 1)
        elif self.room.board[p.x][p.y].color != 0x1F or self.info[c.PLAYER].ch != 0x02:
            self.room.board[p.x][p.y].color = 0x1F
            self.info[c.PLAYER].ch = 0x02

        if self.world.inv.strength <= 0:
            self.control.dx = 0
            self.control.dy = 0
            self.control.fire = False
            self.game_cycle_ms = 9999

        if self.control.fire:
            if self.control.dx or self.control.dy:
                if self.room.room_info.can_shoot == 0:
                    if self.world.first.cant_shoot_here:
                        self.put_bot_msg(200, "Can't shoot in this place!")
                        self.world.first.cant_shoot_here = False
                elif self.world.inv.ammo == 0:
                    if self.world.first.no_ammo:
                        self.put_bot_msg(200, "You don't have any ammo!")
                        self.world.first.no_ammo = False
                else:
                    d = 0
                    for i in range(len(self.room.objs)):
                        o = self.room.objs[i]
                        if self.room.board[o.x][o.y].kind == c.BULLET and o.intel == 0:
                            d += 1
                    if d < self.room.room_info.can_shoot and self.try_fire(c.BULLET, p.x, p.y, self.control.dx, self.control.dy, 0):
                        self.world.inv.ammo -= 1
                        self.sound_add(2, snd.SFX_PLAYER_SHOOT)
                        self.control.dx = 0
                        self.control.dy = 0
        elif self.control.dx or self.control.dy:
            dxy = [self.control.dx, self.control.dy]
            self.invoke_touch(p.x + dxy[0], p.y + dxy[1], 0, dxy)
            if dxy[0] or dxy[1]:
                if self.info[self.room.board[p.x + dxy[0]][p.y + dxy[1]].kind].go_thru:
                    self.move_obj(0, p.x + dxy[0], p.y + dxy[1])

        key = self.control.key.upper()
        if key == "T" and self.world.inv.torch_time <= 0:
            if self.world.inv.torches > 0:
                if self.room.room_info.is_dark:
                    self.world.inv.torches -= 1
                    self.world.inv.torch_time = c.TORCH_LIFE
                    self.do_area(p.x, p.y, 0)
                elif self.world.first.dont_need_torch:
                    self.put_bot_msg(200, "Don't need torch - room is not dark!")
                    self.world.first.dont_need_torch = False
            elif self.world.first.no_torch:
                self.put_bot_msg(200, "You don't have any torches!")
                self.world.first.no_torch = False
        elif key in {"\x1B", "Q"}:
            self.ask_quit_game()
        elif key == "S":
            save_world(self.world, "SAVED.SAV")
            self.put_bot_msg(100, "Saved to SAVED.SAV")
        elif key == "P":
            if self.world.inv.strength > 0:
                self.standby = True
        elif key == "B":
            self.sound_enabled = not self.sound_enabled
            self.sound.set_enabled(self.sound_enabled)
            self.sound_stop()
        elif key == "H":
            self.put_bot_msg(200, "Help docs: ref/HELP/GAME.HLP")

        if self.world.inv.torch_time > 0:
            self.world.inv.torch_time -= 1
            if self.world.inv.torch_time <= 0:
                self.do_area(p.x, p.y, 0)
                self.sound_add(3, snd.SFX_TORCH_OUT)

        if self.world.inv.ener_time > 0:
            self.world.inv.ener_time -= 1
            if self.world.inv.ener_time == 10:
                self.sound_add(9, snd.SFX_ENERGIZER_WARN)
            elif self.world.inv.ener_time <= 0:
                self.room.board[p.x][p.y].color = self.info[c.PLAYER].col

        if self.room.room_info.time_limit > 0 and self.world.inv.strength > 0:
            self.world.inv.room_time += 1
            if self.world.inv.room_time == (self.room.room_info.time_limit - 10):
                self.put_bot_msg(200, "Running out of time!")
                self.sound_add(3, snd.SFX_TIMELIMIT_WARN)
            elif self.world.inv.room_time > self.room.room_info.time_limit:
                self.zap_obj(0)

    def upd_monitor(self, n: int) -> None:
        self._handle_monitor_key(self.control.key)

    def upd_scroll(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        o = self.room.objs[n]
        self.room.board[o.x][o.y].color += 1
        if self.room.board[o.x][o.y].color > 0x0F:
            self.room.board[o.x][o.y].color = 0x09

    def upd_blink_wall(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        o = self.room.objs[n]
        if o.room == 0:
            o.room = o.intel + 1
        if o.room == 1:
            temp_x = o.x + o.xd
            temp_y = o.y + o.yd
            wall_kind = c.HORIZ_WALL if o.xd != 0 else c.VERT_WALL

            while (
                self.room.board[temp_x][temp_y].kind == wall_kind
                and self.room.board[temp_x][temp_y].color == self.room.board[o.x][o.y].color
            ):
                self.room.board[temp_x][temp_y].kind = c.EMPTY
                temp_x += o.xd
                temp_y += o.yd
                o.room = o.rate * 2 + 1

            if temp_x == o.x + o.xd and temp_y == o.y + o.yd:
                done = False
                limit = (c.XS + c.YS) * 2
                while not done and limit > 0:
                    limit -= 1
                    kind = self.room.board[temp_x][temp_y].kind
                    if kind != c.EMPTY and self.info[kind].killable:
                        self.zap(temp_x, temp_y)

                    if self.room.board[temp_x][temp_y].kind == c.PLAYER:
                        player_idx = self.obj_at(temp_x, temp_y)
                        if player_idx >= 0:
                            if o.xd != 0:
                                if self.room.board[temp_x][temp_y - 1].kind == c.EMPTY:
                                    self.move_obj(player_idx, temp_x, temp_y - 1)
                                elif self.room.board[temp_x][temp_y + 1].kind == c.EMPTY:
                                    self.move_obj(player_idx, temp_x, temp_y + 1)
                            else:
                                if self.room.board[temp_x + 1][temp_y].kind == c.EMPTY:
                                    self.move_obj(player_idx, temp_x + 1, temp_y)
                                elif self.room.board[temp_x - 1][temp_y].kind == c.EMPTY:
                                    # Intentionally mirrors the original Pascal behavior.
                                    self.move_obj(player_idx, temp_x + 1, temp_y)

                        if self.room.board[temp_x][temp_y].kind == c.PLAYER:
                            while self.world.inv.strength > 0:
                                self.zap_obj(0)
                            done = True

                    if self.room.board[temp_x][temp_y].kind == c.EMPTY:
                        self.room.board[temp_x][temp_y].kind = wall_kind
                        self.room.board[temp_x][temp_y].color = self.room.board[o.x][o.y].color
                    else:
                        done = True

                    temp_x += o.xd
                    temp_y += o.yd

                o.room = o.rate * 2 + 1
        else:
            o.room -= 1

    def _dynamic_char(self, x: int, y: int, kind: int) -> int:
        if kind == c.SHOOTER:
            phase = self.counter % 8
            if phase in (0, 1):
                return 0x18
            if phase in (2, 3):
                return 0x1A
            if phase in (4, 5):
                return 0x19
            return 0x1B
        if kind == c.LINE2:
            a = 1
            k = 1
            for i in range(4):
                nk = self.room.board[x + c.UDLR_X[i]][y + c.UDLR_Y[i]].kind
                if nk in (c.LINE2, c.BOUND):
                    a += k
                k *= 2
            line2 = [0xF9, 0xD0, 0xD2, 0xBA, 0xB5, 0xBC, 0xBB, 0xB9, 0xC6, 0xC8, 0xC9, 0xCC, 0xCD, 0xCA, 0xCB, 0xCE]
            return line2[max(1, min(16, a)) - 1]
        if kind == c.CONVEYOR_CW:
            phase = (self.counter // max(1, self.info[c.CONVEYOR_CW].cycle)) % 4
            return (0xB3, ord("/"), 0xC4, ord("\\"))[phase]
        if kind == c.CONVEYOR_CCW:
            phase = (self.counter // max(1, self.info[c.CONVEYOR_CCW].cycle)) % 4
            return (ord("\\"), 0xC4, ord("/"), 0xB3)[phase]
        if kind == c.BOMB:
            idx = self.obj_at(x, y)
            if idx >= 0:
                intel = self.room.objs[idx].intel
                return 0x0B if intel <= 1 else ord(str(min(9, intel)))
            return 0x0B
        if kind == c.XPORTER:
            idx = self.obj_at(x, y)
            if idx >= 0:
                o = self.room.objs[idx]
                h = "^~^-v_v-"
                v = "(<(|)>)|"
                xd = self.signf(o.xd)
                yd = self.signf(o.yd)
                phase = (self.counter // max(1, o.cycle)) % 4
                if o.xd == 0:
                    return ord(h[yd * 2 + 3 + phase - 1])
                return ord(v[xd * 2 + 3 + phase - 1])
            return 0xC5
        if kind == c.SBOMB:
            seq = (0xB3, ord("/"), 0xC4, ord("\\"))
            self.room.board[x][y].color += 1
            if self.room.board[x][y].color > 0x0F:
                self.room.board[x][y].color = 0x09
            return seq[self.counter % 4]
        if kind == c.DUPER:
            idx = self.obj_at(x, y)
            if idx >= 0:
                return {1: 0xFA, 2: 0xF9, 3: 0xF8, 4: ord("o"), 5: ord("O")}.get(self.room.objs[idx].intel, 0xFA)
            return 0xFA
        if kind == c.PROG:
            idx = self.obj_at(x, y)
            if idx >= 0:
                return self.room.objs[idx].intel & 0xFF
            return 0x02
        if kind == c.PUSHER:
            idx = self.obj_at(x, y)
            if idx >= 0:
                o = self.room.objs[idx]
                if o.xd == 1:
                    return 0x10
                if o.xd == -1:
                    return 0x11
                if o.yd == -1:
                    return 0x1E
                return 0x1F
            return 0x10
        if kind == c.BLINK_WALL:
            return 0xCE
        return self.info[kind].ch

    def _cell_visible(self, x: int, y: int) -> bool:
        cell = self.room.board[x][y]
        if not self.room.room_info.is_dark:
            return True
        if self.info[cell.kind].show_in_dark:
            return True
        if self.world.inv.torch_time > 0:
            p = self.player
            if (p.x - x) ** 2 + 2 * (p.y - y) ** 2 < c.TORCH_SIZE:
                return True
        return False

    def _draw_board(self, renderer: Renderer) -> None:
        for y in range(1, c.YS + 1):
            for x in range(1, c.XS + 1):
                cell = self.room.board[x][y]
                kind = cell.kind
                if not self._cell_visible(x, y):
                    renderer.draw_glyph(x - 1, y - 1, 0xB0, 0x07)
                    continue

                if (
                    kind == c.PLAYER
                    and self.play_mode == c.PLAYER
                    and self.standby
                    and not self._standby_blink_visible
                ):
                    renderer.draw_glyph(x - 1, y - 1, ord(" "), 0x0F)
                    continue

                if kind == c.EMPTY:
                    renderer.draw_glyph(x - 1, y - 1, ord(" "), 0x0F)
                elif kind < c.TEXT_COL:
                    ch = self._dynamic_char(x, y, kind) if self.info[kind].print_dynamic else self.info[kind].ch
                    renderer.draw_glyph(x - 1, y - 1, ch, cell.color)
                else:
                    if kind == c.TEXT_COL + c.NUM_TEXT_COLS:
                        renderer.draw_glyph(x - 1, y - 1, cell.color, 0x0F)
                    else:
                        attr = ((kind - c.TEXT_COL + 1) << 4) + 0x0F
                        renderer.draw_glyph(x - 1, y - 1, cell.color, attr)

    def _draw_panel(self, renderer: Renderer) -> None:
        panel_x = 61
        renderer.draw_text(panel_x, 0, "- - - - -", 0x1F)
        renderer.draw_text(panel_x + 1, 1, "ZZT", 0x70)
        renderer.draw_text(panel_x, 2, "- - - - -", 0x1F)

        inv = self.world.inv
        if self.play_mode == c.MONITOR:
            world_name = inv.orig_name if inv.orig_name else "Untitled"
            renderer.draw_text(61, 5, "Pick a command:", 0x1B)
            renderer.draw_text(61, 7, " W ", 0x30)
            renderer.draw_text(64, 7, "World:", 0x1E)
            renderer.draw_text(68, 8, world_name[:11], 0x1F)
            renderer.draw_text(61, 11, " P ", 0x70)
            renderer.draw_text(64, 11, "Play", 0x1F)
            renderer.draw_text(61, 12, " R ", 0x30)
            renderer.draw_text(64, 12, "Restore game", 0x1E)
            renderer.draw_text(61, 13, " Q ", 0x70)
            renderer.draw_text(64, 13, "Quit", 0x1E)
            renderer.draw_text(61, 16, " A ", 0x30)
            renderer.draw_text(64, 16, "About ZZT!", 0x1F)
            renderer.draw_text(61, 17, " H ", 0x70)
            renderer.draw_text(64, 17, "High Scores", 0x1E)
            renderer.draw_text(61, 21, " S ", 0x70)
            renderer.draw_text(64, 21, f"Game speed: {self.speed}", 0x1F)

            msg = self.room.room_info.bot_msg
            if msg:
                text = f" {msg[:58]} "
                start = max(0, (c.XS - len(text)) // 2)
                renderer.draw_text(start, c.YS - 2, text, 0x1F)
            return

        renderer.draw_text(panel_x + 1, 7, "Health:", 0x1E)
        renderer.draw_text(panel_x + 1, 8, "Ammo:", 0x1E)
        renderer.draw_text(panel_x + 1, 9, "Torches:", 0x1E)
        renderer.draw_text(panel_x + 1, 10, "Gems:", 0x1E)
        renderer.draw_text(panel_x + 1, 11, "Score:", 0x1E)
        renderer.draw_text(panel_x + 1, 12, "Keys:", 0x1E)

        renderer.draw_text(72, 7, f"{inv.strength:>4}", 0x1E)
        renderer.draw_text(72, 8, f"{inv.ammo:>4}", 0x1E)
        renderer.draw_text(72, 9, f"{inv.torches:>4}", 0x1E)
        renderer.draw_text(72, 10, f"{inv.gems:>4}", 0x1E)
        renderer.draw_text(72, 11, f"{inv.score:>4}", 0x1E)

        for i in range(7):
            if inv.keys[i]:
                renderer.draw_glyph(71 + i, 12, self.info[c.AKEY].ch, 0x18 + (i + 1))
            else:
                renderer.draw_glyph(71 + i, 12, ord(" "), 0x1F)

        renderer.draw_text(61, 14, " T ", 0x70)
        renderer.draw_text(64, 14, "Torch", 0x1F)
        renderer.draw_text(61, 15, " B ", 0x30)
        renderer.draw_text(64, 15, "Be quiet" if self.sound_enabled else "Be noisy", 0x1F)
        renderer.draw_text(61, 21, " S ", 0x70)
        renderer.draw_text(64, 21, "Save game", 0x1F)
        renderer.draw_text(61, 22, " P ", 0x30)
        renderer.draw_text(64, 22, "Pausing..." if self.standby else "Pause", 0x1F)
        renderer.draw_text(61, 23, " Q ", 0x70)
        renderer.draw_text(64, 23, "Quit", 0x1F)

        msg = self.room.room_info.bot_msg
        if msg:
            text = f" {msg[:58]} "
            start = max(0, (c.XS - len(text)) // 2)
            renderer.draw_text(start, c.YS - 2, text, 0x1F)

    def _parse_scroll_entries(self, lines: list[str]) -> list[ScrollEntry]:
        entries: list[ScrollEntry] = []
        for raw in lines:
            if not raw:
                entries.append(ScrollEntry(raw="", text="", kind="text"))
                continue
            if raw[0] == "!":
                rest = raw[1:]
                if ";" in rest:
                    cmd, text = rest.split(";", 1)
                else:
                    cmd, text = rest, rest
                entries.append(ScrollEntry(raw=raw, text=text, kind="hyper", command=cmd.strip()))
            elif raw[0] == ":":
                rest = raw[1:]
                if ";" in rest:
                    _, text = rest.split(";", 1)
                else:
                    text = ""
                entries.append(ScrollEntry(raw=raw, text=text, kind="label"))
            elif raw[0] == "$":
                entries.append(ScrollEntry(raw=raw, text=raw[1:], kind="heading"))
            else:
                entries.append(ScrollEntry(raw=raw, text=raw, kind="text"))
        return entries

    def _draw_scroll_overlay(
        self,
        renderer: Renderer,
        title: str,
        entries: list[ScrollEntry],
        cur: int,
        obj_flag: bool,
    ) -> None:
        x0, y0 = 5, 3
        w, h = 52, 18
        visible = h - 4
        top_idx = max(0, min(cur - visible // 2, max(0, len(entries) - visible)))

        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                renderer.draw_glyph(x, y, ord(" "), 0x1E)

        for x in range(x0 + 1, x0 + w - 1):
            renderer.draw_glyph(x, y0, 0xCD, 0x0F)
            renderer.draw_glyph(x, y0 + h - 1, 0xCD, 0x0F)
        for y in range(y0 + 1, y0 + h - 1):
            renderer.draw_glyph(x0, y, 0xBA, 0x0F)
            renderer.draw_glyph(x0 + w - 1, y, 0xBA, 0x0F)
        renderer.draw_glyph(x0, y0, 0xC9, 0x0F)
        renderer.draw_glyph(x0 + w - 1, y0, 0xBB, 0x0F)
        renderer.draw_glyph(x0, y0 + h - 1, 0xC8, 0x0F)
        renderer.draw_glyph(x0 + w - 1, y0 + h - 1, 0xBC, 0x0F)

        title_text = title[: w - 4]
        title_x = x0 + max(1, (w - len(title_text)) // 2)
        renderer.draw_text(title_x, y0 + 1, title_text, 0x1E)

        for row in range(visible):
            idx = top_idx + row
            if idx >= len(entries):
                break
            entry = entries[idx]
            y = y0 + 2 + row
            base_attr = 0x1E
            if entry.kind in {"hyper", "label", "heading"}:
                base_attr = 0x1F
            if idx == cur:
                base_attr = 0x1C

            if entry.kind == "heading":
                text = entry.text[: w - 4].center(w - 4)
            elif entry.kind == "hyper":
                text = "  " + entry.text
            else:
                text = entry.text
            text = text[: w - 4]
            renderer.draw_text(x0 + 2, y, text.ljust(w - 4), base_attr)
            if entry.kind == "hyper":
                renderer.draw_glyph(x0 + 2, y, 0x10, base_attr)

        hint = "Enter selects" if obj_flag else "Enter continues"
        renderer.draw_text(x0 + 2, y0 + h - 2, f"{hint}  Esc closes"[: w - 4], 0x1A)

    def show_scroll(self, lines: list[str], title: str, obj_flag: bool = True) -> str | None:
        entries = self._parse_scroll_entries(lines)
        if not entries:
            return None

        if self._renderer is None or self._screen is None:
            for entry in entries:
                if entry.text.strip():
                    self.put_bot_msg(200, entry.text[:58])
                    break
            return None

        cur = 0
        for i, entry in enumerate(entries):
            if entry.kind != "label":
                cur = i
                break

        clock = self._clock or pygame.time.Clock()
        result: str | None = None

        while not self.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    break
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_ESCAPE,):
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return None
                if event.key in (pygame.K_UP, pygame.K_KP8):
                    cur = max(0, cur - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_KP2):
                    cur = min(len(entries) - 1, cur + 1)
                elif event.key == pygame.K_PAGEUP:
                    cur = max(0, cur - 12)
                elif event.key == pygame.K_PAGEDOWN:
                    cur = min(len(entries) - 1, cur + 12)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    entry = entries[cur]
                    if entry.kind == "hyper" and entry.command:
                        if obj_flag:
                            result = entry.command
                            self.key_buffer.clear()
                            self.move_queue.clear()
                            return result
                    self.key_buffer.clear()
                    self.move_queue.clear()
                    return result

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._draw_scroll_overlay(self._renderer, title, entries, cur, obj_flag)
            pygame.display.flip()
            self._ui_wait(clock)

        self.key_buffer.clear()
        self.move_queue.clear()
        return result

    def _decode_scroll_lines(self, initial: bytes | str) -> list[str]:
        if isinstance(initial, bytes):
            text = initial.decode("cp437", errors="replace")
        else:
            text = initial
        lines = text.replace("\n", "\r").split("\r")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        return lines if lines else [""]

    def _encode_scroll_lines(self, lines: list[str]) -> bytes:
        safe = [line[:250] for line in lines]
        return ("\r".join(safe) + "\r").encode("cp437", errors="replace")

    def _edit_scroll_apply_key(self, state: EditScrollState, key: int, unicode: str = "", mod: int = 0) -> None:
        if not state.lines:
            state.lines = [""]
        max_lines = 255
        max_len = 250

        if key == pygame.K_ESCAPE:
            state.cancelled = True
            state.done = True
            return
        if key in (pygame.K_F2,) or (key == pygame.K_s and (mod & pygame.KMOD_CTRL)):
            state.done = True
            return
        if key == pygame.K_INSERT:
            state.insert_mode = not state.insert_mode
            return

        line = state.lines[state.cur_y]
        if key == pygame.K_UP:
            state.cur_y = max(0, state.cur_y - 1)
            state.cur_x = min(state.cur_x, len(state.lines[state.cur_y]))
            return
        if key == pygame.K_DOWN:
            state.cur_y = min(len(state.lines) - 1, state.cur_y + 1)
            state.cur_x = min(state.cur_x, len(state.lines[state.cur_y]))
            return
        if key == pygame.K_LEFT:
            if state.cur_x > 0:
                state.cur_x -= 1
            elif state.cur_y > 0:
                state.cur_y -= 1
                state.cur_x = len(state.lines[state.cur_y])
            return
        if key == pygame.K_RIGHT:
            if state.cur_x < len(line):
                state.cur_x += 1
            elif state.cur_y < len(state.lines) - 1:
                state.cur_y += 1
                state.cur_x = 0
            return
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            left = line[: state.cur_x]
            right = line[state.cur_x :]
            state.lines[state.cur_y] = left
            if len(state.lines) < max_lines:
                state.lines.insert(state.cur_y + 1, right)
                state.cur_y += 1
                state.cur_x = 0
            return
        if key == pygame.K_BACKSPACE:
            if state.cur_x > 0:
                state.lines[state.cur_y] = line[: state.cur_x - 1] + line[state.cur_x :]
                state.cur_x -= 1
            elif state.cur_y > 0:
                prev = state.lines[state.cur_y - 1]
                state.cur_x = len(prev)
                state.lines[state.cur_y - 1] = (prev + line)[:max_len]
                del state.lines[state.cur_y]
                state.cur_y -= 1
            return
        if key == pygame.K_DELETE:
            if state.cur_x < len(line):
                state.lines[state.cur_y] = line[: state.cur_x] + line[state.cur_x + 1 :]
            elif state.cur_y < len(state.lines) - 1:
                state.lines[state.cur_y] = (line + state.lines[state.cur_y + 1])[:max_len]
                del state.lines[state.cur_y + 1]
            return
        if key == pygame.K_y and (mod & pygame.KMOD_CTRL):
            if len(state.lines) > 1:
                del state.lines[state.cur_y]
                state.cur_y = min(state.cur_y, len(state.lines) - 1)
            else:
                state.lines[0] = ""
                state.cur_y = 0
            state.cur_x = min(state.cur_x, len(state.lines[state.cur_y]))
            return

        if unicode and unicode.isprintable() and unicode not in "\r\n\t":
            if len(line) >= max_len and state.insert_mode:
                return
            if state.insert_mode:
                line = line[: state.cur_x] + unicode + line[state.cur_x :]
            else:
                if state.cur_x < len(line):
                    line = line[: state.cur_x] + unicode + line[state.cur_x + 1 :]
                else:
                    line = line + unicode
            state.lines[state.cur_y] = line[:max_len]
            state.cur_x = min(max_len, state.cur_x + 1)

    def _draw_edit_scroll_overlay(self, renderer: Renderer, title: str, state: EditScrollState) -> None:
        x0, y0 = 4, 2
        w, h = 54, 20
        body_w = w - 4
        visible = h - 5
        top = max(0, min(state.cur_y - visible // 2, max(0, len(state.lines) - visible)))

        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                renderer.draw_glyph(x, y, ord(" "), 0x1E)
        for x in range(x0 + 1, x0 + w - 1):
            renderer.draw_glyph(x, y0, 0xCD, 0x0F)
            renderer.draw_glyph(x, y0 + h - 1, 0xCD, 0x0F)
        for y in range(y0 + 1, y0 + h - 1):
            renderer.draw_glyph(x0, y, 0xBA, 0x0F)
            renderer.draw_glyph(x0 + w - 1, y, 0xBA, 0x0F)
        renderer.draw_glyph(x0, y0, 0xC9, 0x0F)
        renderer.draw_glyph(x0 + w - 1, y0, 0xBB, 0x0F)
        renderer.draw_glyph(x0, y0 + h - 1, 0xC8, 0x0F)
        renderer.draw_glyph(x0 + w - 1, y0 + h - 1, 0xBC, 0x0F)

        renderer.draw_text(x0 + 2, y0 + 1, title[: body_w], 0x1F)
        mode = "INS" if state.insert_mode else "OVR"
        renderer.draw_text(x0 + w - 8, y0 + 1, mode, 0x1A)

        for row in range(visible):
            idx = top + row
            if idx >= len(state.lines):
                break
            attr = 0x1C if idx == state.cur_y else 0x1E
            text = state.lines[idx][:body_w]
            renderer.draw_text(x0 + 2, y0 + 2 + row, text.ljust(body_w), attr)

        cy = y0 + 2 + (state.cur_y - top)
        cx = x0 + 2 + min(state.cur_x, body_w - 1)
        if y0 + 2 <= cy < y0 + h - 2:
            cursor_ch = ord(state.lines[state.cur_y][state.cur_x]) if state.cur_x < len(state.lines[state.cur_y]) else ord("_")
            renderer.draw_glyph(cx, cy, cursor_ch, 0x70)

        help_text = "F2/Ctrl+S save  Esc cancel  Ctrl+Y del line"
        renderer.draw_text(x0 + 2, y0 + h - 2, help_text[:body_w], 0x1A)

    def edit_scroll(self, initial: bytes | str, title: str = "Edit text") -> bytes | None:
        state = EditScrollState(lines=self._decode_scroll_lines(initial))
        if self._renderer is None or self._screen is None:
            return self._encode_scroll_lines(state.lines)

        clock = self._clock or pygame.time.Clock()
        while not self.exit_program and not state.done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.exit_program = True
                    state.cancelled = True
                    state.done = True
                    break
                if event.type == pygame.KEYDOWN:
                    self._edit_scroll_apply_key(state, event.key, event.unicode, event.mod)

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            self._draw_edit_scroll_overlay(self._renderer, title, state)
            pygame.display.flip()
            self._ui_wait(clock)

        self.key_buffer.clear()
        self.move_queue.clear()
        if state.cancelled:
            return None
        return self._encode_scroll_lines(state.lines)

    def _pump_events(self) -> None:
        key_to_dir: dict[int, tuple[int, int]] = {
            pygame.K_UP: (0, -1),
            pygame.K_KP8: (0, -1),
            pygame.K_DOWN: (0, 1),
            pygame.K_KP2: (0, 1),
            pygame.K_LEFT: (-1, 0),
            pygame.K_KP4: (-1, 0),
            pygame.K_RIGHT: (1, 0),
            pygame.K_KP6: (1, 0),
        }

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_program = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.key_buffer.append("\x1b")
                elif event.key in key_to_dir:
                    dx, dy = key_to_dir[event.key]
                    fire = bool(event.mod & pygame.KMOD_SHIFT)
                    if len(self.move_queue) >= self.MAX_MOVE_QUEUE:
                        self.move_queue.popleft()
                    self.move_queue.append((dx, dy, fire))
                elif event.unicode:
                    self.key_buffer.append(event.unicode)

    def _read_control(self) -> None:
        pressed = pygame.key.get_pressed()

        dx, dy = 0, 0
        if pressed[pygame.K_UP] or pressed[pygame.K_KP8]:
            dy = -1
        elif pressed[pygame.K_DOWN] or pressed[pygame.K_KP2]:
            dy = 1
        elif pressed[pygame.K_LEFT] or pressed[pygame.K_KP4]:
            dx = -1
        elif pressed[pygame.K_RIGHT] or pressed[pygame.K_KP6]:
            dx = 1

        mods = pygame.key.get_mods()
        fire = bool(mods & pygame.KMOD_SHIFT) and (dx != 0 or dy != 0)

        if dx != 0 or dy != 0:
            # Continuous key state wins; clear queued keydown bursts to avoid stale "ghost" moves.
            self.move_queue.clear()
        elif self.move_queue:
            dx, dy, fire = self.move_queue.popleft()

        key = self.key_buffer.popleft() if self.key_buffer else "\x00"

        self.control.dx = dx
        self.control.dy = dy
        self.control.fire = fire
        self.control.key = key

    def _update_active_objects(self) -> None:
        self.obj_num = 0
        while self.obj_num <= self.room.num_objs:
            if self.obj_num < len(self.room.objs):
                obj = self.room.objs[self.obj_num]
                cyc = obj.cycle
                if cyc != 0 and (self.counter % cyc) == (self.obj_num % cyc):
                    self.invoke_update(self.obj_num)
            self.obj_num += 1

    def _tick_game(self, now_ms: int) -> None:
        self._service_sound(now_ms)
        if self.play_mode == c.PLAYER and self.world.inv.strength <= 0:
            self._handle_player_death()
            return

        if self.play_mode == c.MONITOR:
            self._read_control()
            self._handle_monitor_key(self.control.key)
            if self.bot_msg_ticks > 0:
                self.bot_msg_ticks -= 1
                if self.bot_msg_ticks <= 0:
                    self.room.room_info.bot_msg = ""
            return

        if self.standby:
            if now_ms - self._standby_blink_last_ms >= 250:
                self._standby_blink_last_ms = now_ms
                self._standby_blink_visible = not self._standby_blink_visible
            self._read_control()
            if self.control.key in {"\x1b", "q", "Q"}:
                self.ask_quit_game()
                return
            if self.control.dx or self.control.dy:
                dxy = [self.control.dx, self.control.dy]
                self.invoke_touch(self.player.x + dxy[0], self.player.y + dxy[1], 0, dxy)
                if (dxy[0] or dxy[1]) and self.info[self.room.board[self.player.x + dxy[0]][self.player.y + dxy[1]].kind].go_thru:
                    if self.room.board[self.player.x][self.player.y].kind == c.PLAYER:
                        self.move_obj(0, self.player.x + dxy[0], self.player.y + dxy[1])
                    else:
                        self._standby_step_player(dxy[0], dxy[1])
                    self.standby = False
                    self.counter = self.random.randrange(100)
                    self.obj_num = self.room.num_objs + 1
                    self.cycle_last_ms = now_ms - self.game_cycle_ms
                    self.world.inv.play_flag = True
                    self._standby_blink_visible = True
            return

        self._standby_blink_visible = True

        max_lag_ms = self.game_cycle_ms * self.MAX_TICK_CATCHUP
        if now_ms - self.cycle_last_ms > max_lag_ms:
            self.cycle_last_ms = now_ms - max_lag_ms

        while now_ms - self.cycle_last_ms >= self.game_cycle_ms:
            self.cycle_last_ms += self.game_cycle_ms
            self._read_control()
            self._update_active_objects()
            if self.bot_msg_ticks > 0:
                self.bot_msg_ticks -= 1
                if self.bot_msg_ticks <= 0:
                    self.room.room_info.bot_msg = ""
            self.counter += 1
            if self.counter > 420:
                self.counter = 1

    def run(self) -> None:
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        self.sound.bind_pygame()
        self.sound.set_enabled(self.sound_enabled)
        pygame.display.set_caption("almost-of-zzt")
        self._screen = pygame.display.set_mode((c.SCREEN_W, c.SCREEN_H))
        self._renderer = Renderer(self._screen)
        self._clock = pygame.time.Clock()

        if self.play_mode == c.PLAYER:
            self.note_enter_new_room()

        self.cycle_last_ms = pygame.time.get_ticks()

        while not self.exit_program:
            self._pump_events()
            now = pygame.time.get_ticks()
            self._tick_game(now)

            self._renderer.clear()
            self._draw_board(self._renderer)
            self._draw_panel(self._renderer)
            pygame.display.flip()
            self._clock.tick(self.TARGET_RENDER_FPS)

        self.sound.shutdown()
        pygame.quit()
        self._screen = None
        self._renderer = None
        self._clock = None
