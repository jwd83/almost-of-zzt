from __future__ import annotations

import copy
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from . import constants as c
from .info import init_info_edit, init_info_play
from .model import BoardCell, Obj, make_default_room
from .world import save_world

if TYPE_CHECKING:
    from .engine import GameEngine


class BoardEditor:
    def __init__(self, engine: "GameEngine") -> None:
        self.engine = engine
        self.cursor_x = max(1, min(c.XS, self.engine.player.x))
        self.cursor_y = max(1, min(c.YS, self.engine.player.y))
        self.draw_mode = False
        self.modified = False
        self.running = False
        self.pattern_kind = c.EMPTY
        self.pattern_color = 0x0F
        self._clock = self.engine._clock or pygame.time.Clock()
        self._default_obj: dict[int, Obj] = {}

    def _is_stat_kind(self, kind: int) -> bool:
        if kind in (c.PLAYER, c.MONITOR, c.EMPTY, c.BOUND, c.SPECIAL):
            return False
        if self.engine.info[kind].update != "upd_nothing":
            return True
        return kind in (c.PROG, c.SCROLL, c.PASSAGE, c.BOMB, c.DUPER)

    def _default_cycle(self, kind: int) -> int:
        cyc = self.engine.info[kind].cycle
        return 1 if cyc <= 0 else cyc

    def _ensure_pattern_color(self) -> None:
        base = self.engine.info[self.pattern_kind].col
        if base < 0xF0:
            self.pattern_color = base

    def _clear_stat_at(self, x: int, y: int) -> None:
        idx = self.engine.obj_at(x, y)
        if idx > 0:
            self.engine.kill_obj(idx)

    def _plot_board(self, x: int, y: int, kind: int | None = None, color: int | None = None) -> None:
        if not (1 <= x <= c.XS and 1 <= y <= c.YS):
            return
        kind = self.pattern_kind if kind is None else kind
        color = self.pattern_color if color is None else color

        if kind == c.PLAYER:
            old_x, old_y = self.engine.player.x, self.engine.player.y
            self.engine.room.board[old_x][old_y] = copy.deepcopy(self.engine.player.under)
            self.engine.player.x = x
            self.engine.player.y = y
            self.engine.player.under = copy.deepcopy(self.engine.room.board[x][y])
            self.engine.room.board[x][y] = BoardCell(c.PLAYER, self.engine.info[c.PLAYER].col)
            self.cursor_x, self.cursor_y = x, y
            self.modified = True
            return

        if self.engine.obj_at(x, y) == 0:
            return

        self._clear_stat_at(x, y)
        if self._is_stat_kind(kind):
            idx = self.engine.add_obj(x, y, kind, color, self._default_cycle(kind))
            if idx >= 0 and kind in self._default_obj:
                proto = self._default_obj[kind]
                obj = self.engine.room.objs[idx]
                obj.xd = proto.xd
                obj.yd = proto.yd
                obj.intel = proto.intel
                obj.rate = proto.rate
                obj.room = proto.room
                if proto.inside:
                    obj.inside = proto.inside
                    obj.offset = 0
        else:
            self.engine.room.board[x][y] = BoardCell(kind, color)
        self.modified = True

    def _flood_fill(self, x: int, y: int) -> None:
        if not (1 <= x <= c.XS and 1 <= y <= c.YS):
            return
        src = self.engine.room.board[x][y]
        if (src.kind, src.color) == (self.pattern_kind, self.pattern_color):
            return

        q: deque[tuple[int, int]] = deque([(x, y)])
        seen: set[tuple[int, int]] = set()
        while q:
            cx, cy = q.popleft()
            if (cx, cy) in seen:
                continue
            seen.add((cx, cy))
            cell = self.engine.room.board[cx][cy]
            if (cell.kind, cell.color) != (src.kind, src.color):
                continue
            if self.engine.obj_at(cx, cy) == 0:
                continue
            self._plot_board(cx, cy)
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 1 <= nx <= c.XS and 1 <= ny <= c.YS:
                    q.append((nx, ny))

    def _select_by_category(self, category: int, title: str) -> None:
        lines: list[str] = []
        for kind in range(c.NUM_CLASSES + 1):
            if self.engine.info[kind].category != category:
                continue
            if kind in (c.BOUND, c.SPECIAL):
                continue
            descr = self.engine.info[kind].descr or f"Kind {kind}"
            lines.append(f"!K{kind};{descr}")
        if not lines:
            return
        selection = self.engine.show_scroll(lines, title, obj_flag=True)
        if selection and selection.startswith("K"):
            try:
                self.pattern_kind = int(selection[1:])
                self._ensure_pattern_color()
            except ValueError:
                return

    def _modify_obj(self, x: int, y: int) -> None:
        idx = self.engine.obj_at(x, y)
        if idx <= 0:
            return
        obj = self.engine.room.objs[idx]
        kind = self.engine.room.board[x][y].kind
        info = self.engine.info[kind]

        if kind == c.PROG:
            obj.intel = self.engine.in_char(1, 24, "Object character:", obj.intel or 2)
        elif info.msg_intel:
            obj.intel = self.engine.in_num(1, 24, info.msg_intel + ":", obj.intel)

        if info.msg_rate or info.msg_rate_h:
            label = info.msg_rate or info.msg_rate_h
            obj.rate = self.engine.in_num(1, 24, label + ":", obj.rate)
        if info.msg_room:
            obj.room = self.engine.in_num(1, 24, info.msg_room + ":", obj.room)
        if info.msg_dir:
            obj.xd, obj.yd = self.engine.in_dir(24, info.msg_dir + ":")
        if info.msg_scroll:
            updated = self.engine.edit_scroll(obj.inside, title=f"Edit {info.msg_scroll}")
            if updated is not None:
                obj.inside = updated
                obj.offset = 0
        self._default_obj[kind] = copy.deepcopy(obj)
        self.modified = True

    def _set_board_info(self) -> None:
        room = self.engine.room
        title = self.engine.in_string(1, 24, 50, "Board title:", room.title)
        if title is not None:
            room.title = title
            self.modified = True
        room.room_info.can_shoot = self.engine.in_num(1, 24, "Shots allowed:", room.room_info.can_shoot)
        room.room_info.time_limit = self.engine.in_num(1, 24, "Time limit:", room.room_info.time_limit)
        room.room_info.is_dark = self.engine.in_yn("Dark room?", room.room_info.is_dark)
        self.modified = True

    def _switch_board(self) -> None:
        cur = self.engine.world.inv.room
        nxt = self.engine.in_num(1, 24, "Board number:", cur)
        if 0 <= nxt <= self.engine.world.num_rooms:
            self.engine.change_room(nxt)
            self.cursor_x = max(1, min(c.XS, self.engine.player.x))
            self.cursor_y = max(1, min(c.YS, self.engine.player.y))

    def _clear_board(self) -> None:
        if not self.engine.in_yn("Clear this board?", False):
            return
        idx = self.engine.world.inv.room
        new_room = make_default_room()
        new_room.title = self.engine.room.title
        self.engine.world.rooms[idx] = new_room
        self.engine.change_room(idx)
        self.cursor_x = self.engine.player.x
        self.cursor_y = self.engine.player.y
        self.modified = True

    def _save_world(self) -> None:
        out_path: Path
        if self.engine._world_file is not None:
            out_path = self.engine._world_file
        else:
            name = self.engine.in_string(1, 24, 64, "Save world as:", "EDIT.ZZT")
            if not name:
                return
            out_path = Path(name)
            self.engine._world_file = out_path
        save_world(self.engine.world, str(out_path))
        self.engine.put_bot_msg(120, f"Saved {out_path.name}")
        self.modified = False

    def _load_world(self) -> None:
        picked = self.engine._select_game_file(c.WORLD_EXT, "Load world")
        if picked and self.engine._load_world_from_path(picked):
            self.cursor_x = max(1, min(c.XS, self.engine.player.x))
            self.cursor_y = max(1, min(c.YS, self.engine.player.y))
            self.modified = False

    def _draw(self) -> None:
        renderer = self.engine._renderer
        if renderer is None:
            return
        renderer.clear()
        self.engine._draw_board(renderer)
        self.engine._draw_panel(renderer)

        cursor_cell = self.engine.room.board[self.cursor_x][self.cursor_y]
        ch = self.engine._dynamic_char(self.cursor_x, self.cursor_y, cursor_cell.kind) if self.engine.info[cursor_cell.kind].print_dynamic else self.engine.info[cursor_cell.kind].ch
        renderer.draw_glyph(self.cursor_x - 1, self.cursor_y - 1, ch, 0x70)

        mode = "DRAW" if self.draw_mode else "MOVE"
        desc = self.engine.info[self.pattern_kind].descr or str(self.pattern_kind)
        status = f"E {mode} ({self.cursor_x:02},{self.cursor_y:02})  {desc} {self.pattern_color:02X}"
        renderer.draw_text(0, c.YS - 1, status[:60].ljust(60), 0x1F)

        renderer.draw_text(61, 4, "Editor keys", 0x1B)
        renderer.draw_text(61, 5, "Arrows Move", 0x1E)
        renderer.draw_text(61, 6, "Space Plot", 0x1E)
        renderer.draw_text(61, 7, "Tab Draw", 0x1E)
        renderer.draw_text(61, 8, "F Fill", 0x1E)
        renderer.draw_text(61, 9, "M Modify", 0x1E)
        renderer.draw_text(61, 10, "F1/2/3 Menu", 0x1E)
        renderer.draw_text(61, 11, "I Board info", 0x1E)
        renderer.draw_text(61, 12, "B Board #", 0x1E)
        renderer.draw_text(61, 13, "L Load", 0x1E)
        renderer.draw_text(61, 14, "S Save", 0x1E)
        renderer.draw_text(61, 15, "Z Clear", 0x1E)
        renderer.draw_text(61, 16, "N New world", 0x1E)
        renderer.draw_text(61, 17, "Esc Exit", 0x1E)

    def _move_cursor(self, dx: int, dy: int) -> None:
        nx = max(1, min(c.XS, self.cursor_x + dx))
        ny = max(1, min(c.YS, self.cursor_y + dy))
        self.cursor_x = nx
        self.cursor_y = ny
        if self.draw_mode:
            self._plot_board(nx, ny)

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key == pygame.K_ESCAPE or key == pygame.K_q:
            if self.modified and not self.engine.in_yn("Discard editor changes?", False):
                return
            self.running = False
            return
        if key in (pygame.K_UP, pygame.K_KP8):
            self._move_cursor(0, -1)
            return
        if key in (pygame.K_DOWN, pygame.K_KP2):
            self._move_cursor(0, 1)
            return
        if key in (pygame.K_LEFT, pygame.K_KP4):
            self._move_cursor(-1, 0)
            return
        if key in (pygame.K_RIGHT, pygame.K_KP6):
            self._move_cursor(1, 0)
            return
        if key == pygame.K_SPACE:
            self._plot_board(self.cursor_x, self.cursor_y)
            return
        if key == pygame.K_TAB:
            self.draw_mode = not self.draw_mode
            return
        if key == pygame.K_p:
            self.pattern_kind = (self.pattern_kind + 1) % (c.NUM_CLASSES + 1)
            if self.pattern_kind in (c.BOUND, c.SPECIAL):
                self.pattern_kind = c.EMPTY
            self._ensure_pattern_color()
            return
        if key == pygame.K_c:
            low = self.pattern_color & 0x0F
            low = 1 if low >= 15 else low + 1
            self.pattern_color = (self.pattern_color & 0xF0) | low
            return
        if key == pygame.K_f:
            self._flood_fill(self.cursor_x, self.cursor_y)
            return
        if key in (pygame.K_RETURN, pygame.K_m):
            self._modify_obj(self.cursor_x, self.cursor_y)
            return
        if key == pygame.K_F1:
            self._select_by_category(c.C_ITEM, "Items")
            return
        if key == pygame.K_F2:
            self._select_by_category(c.C_CREATURE, "Creatures")
            return
        if key == pygame.K_F3:
            self._select_by_category(c.C_TERRAIN, "Terrain")
            return
        if key == pygame.K_i:
            self._set_board_info()
            return
        if key == pygame.K_b:
            self._switch_board()
            return
        if key == pygame.K_z:
            self._clear_board()
            return
        if key == pygame.K_n:
            if self.engine.in_yn("Create new world?", False):
                self.engine.new_game()
                self.cursor_x = self.engine.player.x
                self.cursor_y = self.engine.player.y
                self.modified = False
            return
        if key == pygame.K_s:
            self._save_world()
            return
        if key == pygame.K_l:
            self._load_world()
            return

    def design_board(self) -> None:
        self.engine.info = init_info_edit()
        self.engine._set_play_mode(c.MONITOR)
        self.engine.standby = False
        self.running = True

        if self.engine._renderer is None or self.engine._screen is None:
            self.running = False

        while self.running and not self.engine.exit_program:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.exit_program = True
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event)
            self._draw()
            pygame.display.flip()
            self._clock.tick(30)

        self.engine.info = init_info_play()
        self.engine._set_play_mode(c.MONITOR)
        self.engine.standby = False
        self.engine.room.board[self.engine.player.x][self.engine.player.y] = BoardCell(c.MONITOR, self.engine.info[c.MONITOR].col)
        self.engine.key_buffer.clear()
        self.engine.move_queue.clear()
