from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    def _find_label(self, obj_idx: int, label: str) -> int:
        needle = ("\r:" + label.upper()).encode("cp437")
        buf = b"\r" + self.engine.room.objs[obj_idx].inside.upper()
        pos = buf.find(needle)
        if pos < 0:
            return -1
        return pos

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
                ofs = self._find_label(dest, label)
                if ofs < 0:
                    continue
            obj.offset = ofs
            changed_sender = changed_sender or (dest == sender)
        return changed_sender

    def _note_dir(self, obj_idx: int, token: str) -> tuple[int, int] | None:
        obj = self.engine.room.objs[obj_idx]
        t = token.upper()
        if t in {"N", "NORTH"}:
            return (0, -1)
        if t in {"S", "SOUTH"}:
            return (0, 1)
        if t in {"E", "EAST"}:
            return (1, 0)
        if t in {"W", "WEST"}:
            return (-1, 0)
        if t in {"I", "IDLE"}:
            return (0, 0)
        if t == "SEEK":
            return self.engine.seek_player(obj.x, obj.y)
        if t == "FLOW":
            return (obj.xd, obj.yd)
        if t == "RND":
            return self.engine.pick_random_dir()
        if t == "RNDNS":
            return (0, -1 if self.engine.random.randrange(2) == 0 else 1)
        if t == "RNDNE":
            return (0, -1) if self.engine.random.randrange(2) == 0 else (1, 0)
        return None

    def exec_obj(self, obj_idx: int, title: str = "Interaction") -> None:
        room = self.engine.room
        if not (0 <= obj_idx <= room.num_objs):
            return
        obj = room.objs[obj_idx]
        if obj.offset < 0:
            return
        buf = obj.inside
        if not buf:
            return

        ofs = obj.offset
        lines_seen = 0
        while 0 <= ofs < len(buf) and lines_seen < 32:
            next_cr = buf.find(b"\r", ofs)
            if next_cr < 0:
                line_b = buf[ofs:]
                ofs = len(buf)
            else:
                line_b = buf[ofs:next_cr]
                ofs = next_cr + 1
            line = line_b.decode("cp437", errors="replace").strip()
            lines_seen += 1

            if not line:
                continue
            if line.startswith(":"):
                continue
            if line.startswith("'"):
                continue
            if line.startswith("@"):
                continue

            if line.startswith("#"):
                cmdline = line[1:].strip()
                parts = cmdline.split()
                if not parts:
                    continue
                cmd = parts[0].upper()
                args = parts[1:]

                if cmd == "GO" and args:
                    dirv = self._note_dir(obj_idx, args[0])
                    if dirv is not None:
                        dx, dy = dirv
                        tx, ty = obj.x + dx, obj.y + dy
                        if not self.engine.info[self.engine.room.board[tx][ty].kind].go_thru:
                            self.engine.push(tx, ty, dx, dy)
                        if self.engine.info[self.engine.room.board[tx][ty].kind].go_thru:
                            self.engine.move_obj(obj_idx, tx, ty)
                            obj = room.objs[obj_idx]
                            obj.offset = ofs
                            return
                elif cmd == "TRY" and args:
                    dirv = self._note_dir(obj_idx, args[0])
                    if dirv is not None:
                        dx, dy = dirv
                        tx, ty = obj.x + dx, obj.y + dy
                        if not self.engine.info[self.engine.room.board[tx][ty].kind].go_thru:
                            self.engine.push(tx, ty, dx, dy)
                        if self.engine.info[self.engine.room.board[tx][ty].kind].go_thru:
                            self.engine.move_obj(obj_idx, tx, ty)
                            obj = room.objs[obj_idx]
                            obj.offset = ofs
                            return
                elif cmd == "WALK" and args:
                    dirv = self._note_dir(obj_idx, args[0])
                    if dirv is not None:
                        obj.xd, obj.yd = dirv
                elif cmd == "SET" and args:
                    self.set_flag(args[0])
                elif cmd == "CLEAR" and args:
                    self.clear_flag(args[0])
                elif cmd == "SEND" and args:
                    self.lsend_msg(obj_idx, args[0], ignore_lock=False)
                elif cmd == "SHOOT" and args:
                    dirv = self._note_dir(obj_idx, args[0])
                    if dirv is not None:
                        self.engine.try_fire(self.engine.constants.BULLET, obj.x, obj.y, dirv[0], dirv[1], 1)
                        obj.offset = ofs
                        return
                elif cmd == "THROWSTAR" and args:
                    dirv = self._note_dir(obj_idx, args[0])
                    if dirv is not None:
                        self.engine.try_fire(self.engine.constants.SBOMB, obj.x, obj.y, dirv[0], dirv[1], 1)
                        obj.offset = ofs
                        return
                elif cmd == "IF" and len(args) >= 3 and args[1].upper() == "THEN":
                    cond = args[0].upper()
                    ok = self.flag_num(cond) >= 0
                    if ok:
                        fake = "#" + " ".join(args[2:])
                        line = fake
                        cmdline = line[1:]
                        parts = cmdline.split()
                        cmd = parts[0].upper() if parts else ""
                        args = parts[1:]
                        continue
                elif cmd == "LOCK":
                    obj.rate = 1
                elif cmd == "UNLOCK":
                    obj.rate = 0
                elif cmd == "END":
                    obj.offset = -1
                    return
                elif cmd == "RESTART":
                    ofs = 0
                    continue
                elif cmd == "DIE":
                    self.engine.zap_obj(obj_idx)
                    return
                elif cmd == "ENDGAME":
                    self.engine.world.inv.strength = 0
                else:
                    self.lsend_msg(obj_idx, cmd, ignore_lock=False)
            else:
                self.engine.put_bot_msg(200, line)
                obj.offset = ofs
                return

        obj.offset = -1 if ofs >= len(buf) else ofs
