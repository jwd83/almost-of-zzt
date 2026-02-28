from __future__ import annotations

import copy
import random
from collections import deque
from dataclasses import dataclass

import pygame

from . import constants as c
from .info import InfoDef, init_info_play
from .model import BoardCell, Obj, Room, RoomInfo, make_default_room
from .oop import OOPRunner
from .render import Renderer
from .world import save_world


@dataclass(slots=True)
class ControlState:
    dx: int = 0
    dy: int = 0
    fire: bool = False
    key: str = "\x00"


class GameEngine:
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

        self.sound_enabled = True
        self.first_thru = True

        self.oop = OOPRunner(self)

        if not self.world.rooms:
            self.world.rooms = [make_default_room()]
            self.world.num_rooms = 0
            self.world.inv.room = 0

        if self.world.game_name == "" and self.world.num_rooms == 0:
            self._build_demo_world()

        self._ensure_player_board()

    @property
    def room(self) -> Room:
        return self.world.rooms[self.world.inv.room]

    @property
    def player(self) -> Obj:
        return self.room.objs[0]

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
        self.world.inv.room = 1
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
        self.room.board[p.x][p.y] = BoardCell(c.PLAYER, self.info[c.PLAYER].col)

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
                    p = self.player
                    self.room.board[p.x][p.y] = BoardCell(c.EMPTY, 0)
                    p.x = self.room.room_info.start_x
                    p.y = self.room.room_info.start_y
                    self.room.board[p.x][p.y] = BoardCell(c.PLAYER, self.info[c.PLAYER].col)
                    self.standby = True
            return

        if 0 < obj_idx < len(self.room.objs):
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
            return True
        return False

    def change_room(self, n: int) -> None:
        if not (0 <= n <= self.world.num_rooms):
            return
        self.world.inv.room = n

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
        self.note_enter_new_room()
        if self.world.inv.room == old_room:
            return

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

        new_x, new_y = x, y
        dest_x = -1
        dest_y = -1
        done = False
        past_x = True

        while not done:
            new_x += dx
            new_y += dy
            kind = self.room.board[new_x][new_y].kind
            if kind == c.BOUND:
                done = True
            elif past_x:
                past_x = False
                if not self.info[kind].go_thru:
                    self.push(new_x, new_y, dx, dy)
                if self.info[self.room.board[new_x][new_y].kind].go_thru:
                    done = True
                    dest_x, dest_y = new_x, new_y
                else:
                    dest_x = -1
            if kind == c.XPORTER:
                temp_idx = self.obj_at(new_x, new_y)
                if temp_idx >= 0:
                    t = self.room.objs[temp_idx]
                    if (t.xd, t.yd) == (-dx, -dy):
                        past_x = True

        if dest_x != -1:
            self.move_to(x - dx, y - dy, dest_x, dest_y)

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
        else:
            self.push(x, y, dir_xy[0], dir_xy[1])

    def touch_xporter(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.push_thru_xporter(x - dir_xy[0], y - dir_xy[1], dir_xy[0], dir_xy[1])
        dir_xy[0] = 0
        dir_xy[1] = 0

    def touch_energizer(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.EMPTY
        self.world.inv.ener_time = c.ENER_LIFE
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
        else:
            self.world.inv.keys[d - 1] = True
            self.room.board[x][y].kind = c.EMPTY
            self.put_bot_msg(200, f"You now have the {c.COLORS[d]} key.")

    def touch_ammo(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.ammo += 5
        self.room.board[x][y].kind = c.EMPTY
        if self.world.first.got_ammo:
            self.world.first.got_ammo = False
            self.put_bot_msg(200, "Ammunition - 5 shots per container.")

    def touch_gem(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.gems += 1
        self.world.inv.strength += 1
        self.world.inv.score += 10
        self.room.board[x][y].kind = c.EMPTY
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
        else:
            self.put_bot_msg(200, f"The {c.COLORS[d]} door is locked!")

    def touch_push(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.push(x, y, dir_xy[0], dir_xy[1])

    def touch_torch(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.world.inv.torches += 1
        self.room.board[x][y].kind = c.EMPTY
        if self.world.first.got_torch:
            self.put_bot_msg(200, "Torch - used for lighting in the underground.")
            self.world.first.got_torch = False

    def touch_inviso_wall(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.NORM_WALL
        self.put_bot_msg(100, "You are blocked by an invisible wall.")

    def touch_brush(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        self.room.board[x][y].kind = c.EMPTY
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
        self.put_bot_msg(100, "Your way is blocked by water.")

    def touch_slime(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        temp_color = self.room.board[x][y].color
        idx = self.obj_at(x, y)
        if idx >= 0:
            self.zap_obj(idx)
        self.room.board[x][y].kind = c.BREAK_WALL
        self.room.board[x][y].color = temp_color

    def touch_scroll(self, x: int, y: int, p: int, dir_xy: list[int]) -> None:
        idx = self.obj_at(x, y)
        if idx > 0:
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
        self.upd_enemy(n)

    def upd_centi(self, n: int) -> None:
        return

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
                first_ric = False
                continue

            if self.room.board[obj.x - obj.yd][obj.y - obj.xd].kind == c.RICOCHET and first_ric:
                old = obj.xd
                obj.xd = obj.yd
                obj.yd = old
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
                        temp_obj = self.obj_at(x + c.CLOCK_X[cidx], y + c.CLOCK_Y[cidx])
                        if temp_obj >= 0:
                            self.room.board[x1][y1].kind = c.EMPTY
                            self.move_obj(temp_obj, x1, y1)
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
                self.do_area(obj.x, obj.y, 1)
            elif obj.intel == 0:
                tx, ty = obj.x, obj.y
                self.kill_obj(n)
                self.do_area(tx, ty, 2)

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

        if self.room.board[dst_x][dst_y].kind != c.EMPTY:
            self.push(dst_x, dst_y, -obj.xd, -obj.yd)

        if self.room.board[dst_x][dst_y].kind == c.EMPTY:
            temp_obj = self.obj_at(src_x, src_y)
            if temp_obj > 0:
                if len(self.room.objs) - 1 < c.MAX_OBJS:
                    src_obj = self.room.objs[temp_obj]
                    idx = self.add_obj(dst_x, dst_y, self.room.board[src_x][src_y].kind, self.room.board[src_x][src_y].color, src_obj.cycle, src_obj)
                    if idx > 0:
                        self.room.objs[idx].inside = src_obj.inside
            elif temp_obj < 0:
                self.room.board[dst_x][dst_y] = copy.deepcopy(self.room.board[src_x][src_y])

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
            self.exit_program = True
        elif key == "S":
            save_world(self.world, "SAVED.SAV")
            self.put_bot_msg(100, "Saved to SAVED.SAV")
        elif key == "P":
            if self.world.inv.strength > 0:
                self.standby = True
        elif key == "B":
            self.sound_enabled = not self.sound_enabled
        elif key == "H":
            self.put_bot_msg(200, "Help docs: ref/HELP/GAME.HLP")

        if self.world.inv.torch_time > 0:
            self.world.inv.torch_time -= 1
            if self.world.inv.torch_time <= 0:
                self.do_area(p.x, p.y, 0)

        if self.world.inv.ener_time > 0:
            self.world.inv.ener_time -= 1
            if self.world.inv.ener_time <= 0:
                self.room.board[p.x][p.y].color = self.info[c.PLAYER].col

        if self.room.room_info.time_limit > 0 and self.world.inv.strength > 0:
            self.world.inv.room_time += 1
            if self.world.inv.room_time == (self.room.room_info.time_limit - 10):
                self.put_bot_msg(200, "Running out of time!")
            elif self.world.inv.room_time > self.room.room_info.time_limit:
                self.zap_obj(0)

    def upd_monitor(self, n: int) -> None:
        if self.control.key.upper() in {"W", "P", "A", "E", "S", "R", "H", "N", "\x1B", "Q", "|"}:
            self.done = True

    def upd_scroll(self, n: int) -> None:
        if n >= len(self.room.objs):
            return
        o = self.room.objs[n]
        self.room.board[o.x][o.y].color += 1
        if self.room.board[o.x][o.y].color > 0x0F:
            self.room.board[o.x][o.y].color = 0x09

    def upd_blink_wall(self, n: int) -> None:
        # Simplified blink wall: toggles one segment in front of emitter.
        if n >= len(self.room.objs):
            return
        o = self.room.objs[n]
        if o.room == 0:
            o.room = o.intel + 1
        if o.room > 1:
            o.room -= 1
            return

        tx, ty = o.x + o.xd, o.y + o.yd
        wall_kind = c.HORIZ_WALL if o.xd else c.VERT_WALL
        if self.room.board[tx][ty].kind == wall_kind and self.room.board[tx][ty].color == self.room.board[o.x][o.y].color:
            self.room.board[tx][ty].kind = c.EMPTY
        else:
            if self.room.board[tx][ty].kind == c.PLAYER:
                self.zap_obj(0)
            elif self.info[self.room.board[tx][ty].kind].killable:
                self.zap(tx, ty)
            if self.room.board[tx][ty].kind == c.EMPTY:
                self.room.board[tx][ty].kind = wall_kind
                self.room.board[tx][ty].color = self.room.board[o.x][o.y].color
        o.room = o.rate * 2 + 1

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
                if o.xd == 0:
                    return ord(h[o.yd * 2 + 3 + ((self.counter // max(1, o.cycle)) % 4)])
                return ord(v[o.xd * 2 + 3 + ((self.counter // max(1, o.cycle)) % 4)])
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
        renderer.draw_text(64, 22, "Pause", 0x1F)
        renderer.draw_text(61, 23, " Q ", 0x70)
        renderer.draw_text(64, 23, "Quit", 0x1F)

        msg = self.room.room_info.bot_msg
        if msg:
            text = f" {msg[:58]} "
            start = max(0, (c.XS - len(text)) // 2)
            renderer.draw_text(start, c.YS - 2, text, 0x1F)

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

        if dx == 0 and dy == 0 and self.move_queue:
            dx, dy, fire = self.move_queue.popleft()

        key = self.key_buffer.popleft() if self.key_buffer else "\x00"

        self.control.dx = dx
        self.control.dy = dy
        self.control.fire = fire
        self.control.key = key

    def _tick_game(self, now_ms: int) -> None:
        if self.standby:
            self._read_control()
            if self.control.key in {"\x1b", "q", "Q"}:
                self.exit_program = True
                return
            if self.control.dx or self.control.dy:
                dxy = [self.control.dx, self.control.dy]
                self.invoke_touch(self.player.x + dxy[0], self.player.y + dxy[1], 0, dxy)
                if (dxy[0] or dxy[1]) and self.info[self.room.board[self.player.x + dxy[0]][self.player.y + dxy[1]].kind].go_thru:
                    if self.room.board[self.player.x][self.player.y].kind == c.PLAYER:
                        self.move_obj(0, self.player.x + dxy[0], self.player.y + dxy[1])
                    self.standby = False
                    self.counter = self.random.randrange(100)
                    self.obj_num = self.room.num_objs + 1
                    self.cycle_last_ms = now_ms - self.game_cycle_ms
                    self.world.inv.play_flag = True
            return

        while self.obj_num <= self.room.num_objs:
            if self.obj_num < len(self.room.objs):
                obj = self.room.objs[self.obj_num]
                cyc = obj.cycle
                if cyc != 0 and (self.counter % cyc) == (self.obj_num % cyc):
                    self.invoke_update(self.obj_num)
            self.obj_num += 1

        steps = 0
        while now_ms - self.cycle_last_ms >= self.game_cycle_ms and steps < 3:
            self.cycle_last_ms += self.game_cycle_ms
            self.counter += 1
            if self.counter > 420:
                self.counter = 1
            self.obj_num = 0
            self._read_control()
            if self.bot_msg_ticks > 0:
                self.bot_msg_ticks -= 1
                if self.bot_msg_ticks <= 0:
                    self.room.room_info.bot_msg = ""
            steps += 1

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("almost-of-zzt")
        screen = pygame.display.set_mode((c.SCREEN_W, c.SCREEN_H))
        renderer = Renderer(screen)
        clock = pygame.time.Clock()

        self.note_enter_new_room()

        self.cycle_last_ms = pygame.time.get_ticks()

        while not self.exit_program:
            self._pump_events()
            now = pygame.time.get_ticks()
            self._tick_game(now)

            renderer.clear()
            self._draw_board(renderer)
            self._draw_panel(renderer)
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
