from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import constants as c
from .model import BoardCell

if TYPE_CHECKING:
    from .engine import GameEngine


@dataclass(slots=True)
class OOPRunner:
    engine: "GameEngine"

    def flag_num(self, word: str) -> int:
        word_u = word.upper()
        for idx, flag in enumerate(self.engine.world.inv.flags):
            if flag.upper() == word_u and flag:
                return idx
        return -1

    def set_flag(self, word: str) -> None:
        if self.flag_num(word) >= 0:
            return
        for idx, flag in enumerate(self.engine.world.inv.flags):
            if not flag:
                self.engine.world.inv.flags[idx] = word.upper()
                return

    def clear_flag(self, word: str) -> None:
        idx = self.flag_num(word)
        if idx >= 0:
            self.engine.world.inv.flags[idx] = ""

    def _object_name(self, obj_idx: int) -> str:
        obj = self.engine.room.objs[obj_idx]
        if not obj.inside:
            return ""
        first = obj.inside.split(b"\r", 1)[0].decode("cp437", errors="replace").strip()
        if first.startswith("@"):
            return first[1:].strip().upper()
        return ""

    def _iter_targets(self, sender: int, target: str) -> list[int]:
        target_u = target.upper()
        room = self.engine.room

        if target_u in {"", "SELF"}:
            return [sender] if sender > 0 else []
        if target_u == "ALL":
            return [i for i in range(1, room.num_objs + 1)]
        if target_u == "OTHERS":
            return [i for i in range(1, room.num_objs + 1) if i != sender]

        found: list[int] = []
        for i in range(1, room.num_objs + 1):
            if self._object_name(i) == target_u:
                found.append(i)
        return found

    def _find_label(self, obj_idx: int, label: str, before: str = ":") -> int:
        data = self.engine.room.objs[obj_idx].inside
        if not data:
            return -1

        pat = ("\r" + before + label.upper()).encode("cp437")
        up = data.upper()
        pos = 0
        while True:
            idx = up.find(pat, pos)
            if idx < 0:
                return -1
            end = idx + len(pat)
            next_b = up[end : end + 1]
            if not next_b:
                return idx
            ch = next_b[0]
            # Match Pascal LSeek boundary behavior: letters and underscore
            # continue words; digits do not block a match.
            is_word = (ord("A") <= ch <= ord("Z")) or ch == ord("_")
            if not is_word:
                return idx
            pos = idx + 1

    def lsend_msg(self, sender: int, msg: str, ignore_lock: bool = False) -> bool:
        extern = sender < 0
        sender = abs(sender)

        if ":" in msg:
            dest_name, label = msg.split(":", 1)
        else:
            dest_name, label = "SELF", msg

        changed_sender = False
        for dest in self._iter_targets(sender, dest_name):
            obj = self.engine.room.objs[dest]
            if obj.rate != 0 and not ignore_lock and not (dest == sender and not extern):
                continue

            if label.upper() == "RESTART":
                ofs = 0
            else:
                ofs = self._find_label(dest, label, before=":")
                if ofs < 0:
                    continue

            obj.offset = ofs
            changed_sender = changed_sender or (dest == sender)

        return changed_sender

    def _xupcase(self, value: str) -> str:
        return "".join(ch.upper() for ch in value if ch.isalnum())

    def _parse_kind(self, tokens: list[str], start: int) -> tuple[BoardCell | None, int]:
        if start >= len(tokens):
            return None, start

        idx = start
        color = 0
        tok = tokens[idx].upper()

        for ci in range(1, 8):
            if tok == c.COLORS[ci].upper():
                color = ci + 8
                idx += 1
                if idx >= len(tokens):
                    return None, idx
                tok = tokens[idx].upper()
                break

        for kind in range(c.NUM_CLASSES + 1):
            if tok == self._xupcase(self.engine.info[kind].descr):
                return BoardCell(kind, color), idx + 1
        return None, idx + 1

    def _real_color(self, cell: BoardCell) -> int:
        info = self.engine.info[cell.kind]
        if info.col < 0xF0:
            return info.col & 0x07
        if info.col == 0xFE:
            return ((cell.color >> 4) & 0x0F) + 8
        return cell.color & 0x0F

    def _locate_kind(self, start_x: int, start_y: int, target: BoardCell) -> tuple[int, int] | None:
        x, y = start_x, start_y
        while True:
            x += 1
            if x > c.XS:
                x = 1
                y += 1
                if y > c.YS:
                    return None
            cell = self.engine.room.board[x][y]
            if cell.kind == target.kind and (target.color == 0 or self._real_color(cell) == target.color):
                return x, y

    def _change_cell(self, x: int, y: int, target: BoardCell) -> None:
        room = self.engine.room
        if room.board[x][y].kind == c.PLAYER:
            return

        tinfo = self.engine.info[target.kind]
        temp_color = target.color

        if tinfo.col < 0xF0:
            temp_color = tinfo.col
        else:
            if temp_color == 0:
                temp_color = room.board[x][y].color
            if temp_color == 0:
                temp_color = 0x0F
            if tinfo.col == 0xFE:
                temp_color = (temp_color - 8) * 0x10 + 0x0F

        if room.board[x][y].kind == target.kind:
            room.board[x][y].color = temp_color
            return

        self.engine.zap(x, y)
        if tinfo.cycle >= 0:
            self.engine.add_obj(x, y, target.kind, temp_color, tinfo.cycle)
        else:
            room.board[x][y].kind = target.kind
            room.board[x][y].color = temp_color

    def _note_dir(self, obj_idx: int, tokens: list[str], idx: int) -> tuple[tuple[int, int] | None, int]:
        if idx >= len(tokens):
            return None, idx

        obj = self.engine.room.objs[obj_idx]
        tok = tokens[idx].upper()

        if tok in {"N", "NORTH"}:
            return (0, -1), idx + 1
        if tok in {"S", "SOUTH"}:
            return (0, 1), idx + 1
        if tok in {"E", "EAST"}:
            return (1, 0), idx + 1
        if tok in {"W", "WEST"}:
            return (-1, 0), idx + 1
        if tok in {"I", "IDLE"}:
            return (0, 0), idx + 1
        if tok == "SEEK":
            return self.engine.seek_player(obj.x, obj.y), idx + 1
        if tok == "FLOW":
            return (obj.xd, obj.yd), idx + 1
        if tok == "RND":
            return self.engine.pick_random_dir(), idx + 1
        if tok == "RNDNS":
            return (0, -1 if self.engine.random.randrange(2) == 0 else 1), idx + 1
        if tok == "RNDNE":
            return ((0, -1) if self.engine.random.randrange(2) == 0 else (1, 0)), idx + 1

        if tok in {"CW", "CCW", "RNDP", "OPP"}:
            base, j = self._note_dir(obj_idx, tokens, idx + 1)
            if base is None:
                return None, j
            dx, dy = base
            if tok == "CW":
                return (-dy, dx), j
            if tok == "CCW":
                return (dy, -dx), j
            if tok == "RNDP":
                if self.engine.random.randrange(2) == 0:
                    return (-dx, dy), j
                return (dx, -dy), j
            return (-dx, -dy), j

        return None, idx + 1

    def _eval_condition(self, obj_idx: int, tokens: list[str], idx: int) -> tuple[bool, int]:
        room = self.engine.room
        obj = room.objs[obj_idx]

        if idx >= len(tokens):
            return False, idx

        tok = tokens[idx].upper()

        if tok == "NOT":
            res, j = self._eval_condition(obj_idx, tokens, idx + 1)
            return (not res), j

        if tok in {"ALLIGNED", "ALIGNED"}:
            return (obj.x == room.objs[0].x or obj.y == room.objs[0].y), idx + 1

        if tok == "CONTACT":
            return ((obj.x - room.objs[0].x) ** 2 + (obj.y - room.objs[0].y) ** 2) == 1, idx + 1

        if tok == "BLOCKED":
            d, j = self._note_dir(obj_idx, tokens, idx + 1)
            if d is None:
                return False, j
            dx, dy = d
            return (not self.engine.info[room.board[obj.x + dx][obj.y + dy].kind].go_thru), j

        if tok == "ENERGIZED":
            return self.engine.world.inv.ener_time > 0, idx + 1

        if tok == "ANY":
            target, j = self._parse_kind(tokens, idx + 1)
            if target is None:
                return False, j
            found = self._locate_kind(0, 1, target) is not None
            return found, j

        return self.flag_num(tok) >= 0, idx + 1

    def _set_oop_char(self, obj_idx: int, code: int) -> None:
        obj = self.engine.room.objs[obj_idx]
        obj.intel = code

    def _apply_take_or_give(self, tokens: list[str], idx: int, take: bool) -> tuple[bool, int]:
        if idx >= len(tokens):
            return False, idx

        item = tokens[idx].upper()
        idx += 1
        if idx >= len(tokens):
            return False, idx

        try:
            amount = int(tokens[idx])
        except ValueError:
            return False, idx + 1
        idx += 1

        if amount <= 0:
            return True, idx

        if take:
            amount = -amount

        inv = self.engine.world.inv

        if item == "HEALTH":
            current = inv.strength
            setter = lambda v: setattr(inv, "strength", v)
        elif item == "AMMO":
            current = inv.ammo
            setter = lambda v: setattr(inv, "ammo", v)
        elif item == "GEMS":
            current = inv.gems
            setter = lambda v: setattr(inv, "gems", v)
        elif item == "TORCHES":
            current = inv.torches
            setter = lambda v: setattr(inv, "torches", v)
        elif item == "SCORE":
            current = inv.score
            setter = lambda v: setattr(inv, "score", v)
        elif item == "TIME":
            current = inv.room_time
            setter = lambda v: setattr(inv, "room_time", v)
        else:
            return True, idx

        if current + amount < 0:
            return False, idx

        setter(current + amount)
        return True, idx

    def _zap_label(self, sender: int, msg: str) -> None:
        room = self.engine.room
        dest_obj = 0
        while True:
            target = None
            for candidate in self._iter_targets(sender, msg.split(":", 1)[0] if ":" in msg else "SELF"):
                if candidate > dest_obj:
                    target = candidate
                    break
            if target is None:
                return
            dest_obj = target

            label = msg.split(":", 1)[1] if ":" in msg else msg
            ofs = self._find_label(dest_obj, label, before=":")
            if ofs < 0:
                continue
            old_inside = room.objs[dest_obj].inside
            data = bytearray(old_inside)
            if ofs + 1 < len(data):
                data[ofs + 1] = ord("'")
                new_inside = bytes(data)
                for obj in room.objs:
                    if obj.inside is old_inside:
                        obj.inside = new_inside

    def _restore_label(self, sender: int, msg: str) -> None:
        room = self.engine.room
        label = msg.split(":", 1)[1] if ":" in msg else msg
        for dest_obj in self._iter_targets(sender, msg.split(":", 1)[0] if ":" in msg else "SELF"):
            while True:
                ofs = self._find_label(dest_obj, label, before="'")
                if ofs < 0:
                    break
                old_inside = room.objs[dest_obj].inside
                data = bytearray(old_inside)
                if ofs + 1 < len(data):
                    data[ofs + 1] = ord(":")
                    new_inside = bytes(data)
                    for obj in room.objs:
                        if obj.inside is old_inside:
                            obj.inside = new_inside
                else:
                    break

    def _exec_command(
        self,
        obj_idx: int,
        tokens: list[str],
        idx: int,
    ) -> tuple[bool, bool, bool, int, bool, BoardCell | None]:
        """Run one command.

        Returns tuple:
        (poll, redo, halt, next_idx, die_flag, die_cell).
        next_idx is -1 for commands that changed the sender offset and
        should continue from that offset (Pascal NewLineF=false behavior).
        """
        room = self.engine.room
        obj = room.objs[obj_idx]

        if idx >= len(tokens):
            return False, False, False, idx, False, None

        cmd = tokens[idx].upper()
        idx += 1

        if cmd == "THEN":
            if idx >= len(tokens):
                return False, False, False, idx, False, None
            cmd = tokens[idx].upper()
            idx += 1

        if cmd == "GO":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is None:
                return False, False, True, j, False, None
            idx = j
            dx, dy = d
            tx, ty = obj.x + dx, obj.y + dy
            if not self.engine.info[room.board[tx][ty].kind].go_thru:
                self.engine.push(tx, ty, dx, dy)
            if self.engine.info[room.board[tx][ty].kind].go_thru:
                self.engine.move_obj(obj_idx, tx, ty)
                return True, False, False, idx, False, None
            return False, True, False, idx, False, None

        if cmd == "TRY":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is None:
                return False, False, True, j, False, None
            idx = j
            dx, dy = d
            tx, ty = obj.x + dx, obj.y + dy
            if not self.engine.info[room.board[tx][ty].kind].go_thru:
                self.engine.push(tx, ty, dx, dy)
            if self.engine.info[room.board[tx][ty].kind].go_thru:
                self.engine.move_obj(obj_idx, tx, ty)
                return True, False, False, idx, False, None
            # Pascal uses `goto GetCmd` here to run same-line fallback command.
            return self._exec_command(obj_idx, tokens, idx)

        if cmd == "WALK":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is not None:
                obj.xd, obj.yd = d
            return False, False, False, j, False, None

        if cmd == "SET":
            if idx < len(tokens):
                self.set_flag(tokens[idx])
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "CLEAR":
            if idx < len(tokens):
                self.clear_flag(tokens[idx])
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "IF":
            ok, j = self._eval_condition(obj_idx, tokens, idx)
            idx = j
            if ok:
                return self._exec_command(obj_idx, tokens, idx)
            return False, False, False, idx, False, None

        if cmd == "SHOOT":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is not None:
                self.engine.try_fire(c.BULLET, obj.x, obj.y, d[0], d[1], 1)
            return True, False, False, j, False, None

        if cmd == "THROWSTAR":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is not None:
                self.engine.try_fire(c.SBOMB, obj.x, obj.y, d[0], d[1], 1)
            return True, False, False, j, False, None

        if cmd in {"GIVE", "TAKE"}:
            ok, j = self._apply_take_or_give(tokens, idx, take=(cmd == "TAKE"))
            if ok:
                return False, False, False, j, False, None
            return self._exec_command(obj_idx, tokens, j)

        if cmd == "END":
            room.objs[obj_idx].offset = -1
            return False, False, True, idx, False, None

        if cmd == "ENDGAME":
            self.engine.world.inv.strength = 0
            return False, False, False, idx, False, None

        if cmd == "IDLE":
            return True, False, False, idx, False, None

        if cmd == "RESTART":
            room.objs[obj_idx].offset = 0
            return False, False, True, idx, False, None

        if cmd == "ZAP":
            if idx < len(tokens):
                self._zap_label(obj_idx, tokens[idx])
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "RESTORE":
            if idx < len(tokens):
                self._restore_label(obj_idx, tokens[idx])
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "LOCK":
            room.objs[obj_idx].rate = 1
            return False, False, False, idx, False, None

        if cmd == "UNLOCK":
            room.objs[obj_idx].rate = 0
            return False, False, False, idx, False, None

        if cmd == "SEND":
            if idx < len(tokens):
                changed_sender = self.lsend_msg(obj_idx, tokens[idx], ignore_lock=False)
                idx += 1
                if changed_sender:
                    return False, False, False, -1, False, None
            return False, False, False, idx, False, None

        if cmd == "BIND":
            if idx < len(tokens):
                target = tokens[idx]
                idx += 1
                dest = None
                for candidate in self._iter_targets(obj_idx, target):
                    dest = candidate
                    break
                if dest is not None:
                    room.objs[obj_idx].inside = room.objs[dest].inside
                    room.objs[obj_idx].offset = 0
                    return False, False, False, -1, False, None
            return False, False, False, idx, False, None

        if cmd == "BECOME":
            target, j = self._parse_kind(tokens, idx)
            if target is None:
                return False, False, True, j, False, None
            return False, False, False, j, True, target

        if cmd == "PUT":
            d, j = self._note_dir(obj_idx, tokens, idx)
            if d is None:
                return False, False, True, j, False, None
            idx = j
            target, j = self._parse_kind(tokens, idx)
            if target is None:
                return False, False, True, j, False, None
            idx = j
            dx, dy = d
            if dx == 0 and dy == 0:
                return False, False, True, idx, False, None
            tx, ty = obj.x + dx, obj.y + dy
            if 1 <= tx <= c.XS and 1 <= ty <= c.YS:
                if not self.engine.info[room.board[tx][ty].kind].go_thru:
                    self.engine.push(tx, ty, dx, dy)
                self._change_cell(tx, ty, target)
            return False, False, False, idx, False, None

        if cmd == "CHANGE":
            src, j = self._parse_kind(tokens, idx)
            if src is None:
                return False, False, True, j, False, None
            idx = j
            dst, j = self._parse_kind(tokens, idx)
            if dst is None:
                return False, False, True, j, False, None
            idx = j

            if dst.color == 0 and self.engine.info[dst.kind].col < 0xF0:
                dst.color = self.engine.info[dst.kind].col

            x, y = 0, 1
            while True:
                found = self._locate_kind(x, y, src)
                if found is None:
                    break
                x, y = found
                self._change_cell(x, y, BoardCell(dst.kind, dst.color))
            return False, False, False, idx, False, None

        if cmd == "PLAY":
            return False, False, False, len(tokens), False, None

        if cmd == "CYCLE":
            if idx < len(tokens):
                try:
                    val = int(tokens[idx])
                    if val > 0:
                        room.objs[obj_idx].cycle = val
                except ValueError:
                    pass
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "CHAR":
            if idx < len(tokens):
                try:
                    val = int(tokens[idx])
                    if 0 < val <= 255:
                        self._set_oop_char(obj_idx, val)
                except ValueError:
                    pass
                idx += 1
            return False, False, False, idx, False, None

        if cmd == "DIE":
            return False, False, False, idx, True, BoardCell(c.EMPTY, 0x0F)

        changed_sender = self.lsend_msg(obj_idx, cmd, ignore_lock=False)
        if changed_sender:
            return False, False, False, -1, False, None
        if ":" not in cmd:
            room.objs[obj_idx].offset = -1
            self.engine.put_bot_msg(200, f"ERR: Bad command {cmd}")
            return False, False, True, idx, False, None
        return False, False, False, idx, False, None

    def exec_obj(self, obj_idx: int, title: str = "Interaction") -> None:
        room = self.engine.room
        if not (0 <= obj_idx <= room.num_objs):
            return

        obj = room.objs[obj_idx]
        if obj.offset < 0:
            return

        if not obj.inside:
            return

        ofs = obj.offset
        cmds_exec = 0
        text_lines: list[str] = []

        while cmds_exec <= 32:
            buf = room.objs[obj_idx].inside
            if not (0 <= ofs < len(buf)):
                break

            start_ofs = ofs
            next_cr = buf.find(b"\r", ofs)
            if next_cr < 0:
                line_b = buf[ofs:]
                ofs = len(buf)
            else:
                line_b = buf[ofs:next_cr]
                ofs = next_cr + 1

            raw = line_b.decode("cp437", errors="replace")
            stripped = raw.strip()
            if not stripped:
                if text_lines:
                    text_lines.append("")
                continue

            if stripped.startswith(":"):
                continue
            if stripped.startswith("'"):
                continue
            if stripped.startswith("@"):
                continue

            if stripped.startswith("/") or stripped.startswith("?"):
                redo = stripped.startswith("/")
                parts = stripped[1:].strip().split()
                d, _ = self._note_dir(obj_idx, parts, 0)
                if d is None:
                    room.objs[obj_idx].offset = ofs
                    return
                dx, dy = d
                if dx != 0 or dy != 0:
                    tx, ty = room.objs[obj_idx].x + dx, room.objs[obj_idx].y + dy
                    if not self.engine.info[room.board[tx][ty].kind].go_thru:
                        self.engine.push(tx, ty, dx, dy)
                    if self.engine.info[room.board[tx][ty].kind].go_thru:
                        self.engine.move_obj(obj_idx, tx, ty)
                        room.objs[obj_idx].offset = ofs
                        return
                if redo:
                    room.objs[obj_idx].offset = start_ofs
                else:
                    room.objs[obj_idx].offset = ofs
                return

            if stripped.startswith("#"):
                cmds_exec += 1
                tokens = stripped[1:].strip().split()
                if not tokens:
                    continue

                poll, redo, halt, next_idx, die_flag, die_cell = self._exec_command(obj_idx, tokens, 0)

                if die_flag and die_cell is not None:
                    ox, oy = room.objs[obj_idx].x, room.objs[obj_idx].y
                    self.engine.zap_obj(obj_idx)
                    self._change_cell(ox, oy, die_cell)
                    return

                if halt:
                    if room.objs[obj_idx].offset < 0:
                        ofs = len(buf)
                    elif room.objs[obj_idx].offset == 0:
                        ofs = 0
                    else:
                        room.objs[obj_idx].offset = ofs
                    break

                if redo:
                    room.objs[obj_idx].offset = start_ofs
                    return

                if poll:
                    room.objs[obj_idx].offset = ofs
                    return

                if next_idx == -1:
                    ofs = room.objs[obj_idx].offset
                    continue

                room.objs[obj_idx].offset = ofs
                continue

            text_lines.append(raw)

        buf = room.objs[obj_idx].inside
        if ofs >= len(buf):
            room.objs[obj_idx].offset = -1
        else:
            room.objs[obj_idx].offset = ofs

        if text_lines:
            if len(text_lines) == 1:
                self.engine.put_bot_msg(200, text_lines[0][:58])
                return

            dialog_title = title or "Interaction"
            if buf.startswith(b"@"):
                first_cr = buf.find(b"\r")
                if first_cr < 0:
                    first_cr = len(buf)
                name = buf[1:first_cr].decode("cp437", errors="replace").strip()
                if name:
                    dialog_title = name

            cmd = self.engine.show_scroll(text_lines, dialog_title, obj_flag=True)
            if cmd:
                if self.lsend_msg(obj_idx, cmd, ignore_lock=False):
                    self.exec_obj(obj_idx, dialog_title)
