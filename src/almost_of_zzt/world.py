from __future__ import annotations

import io
import struct
from dataclasses import replace

from . import constants as c
from .model import BoardCell, GameWorld, Inventory, Obj, Room, RoomInfo, make_new_world


_INT16 = struct.Struct("<h")
_UINT16 = struct.Struct("<H")
_OBJ_HEAD = struct.Struct("<BBhhhBBBhhBBIhh8s")


def _read_short_string(data: memoryview, ofs: int, max_len: int) -> tuple[str, int]:
    length = data[ofs]
    ofs += 1
    raw = bytes(data[ofs : ofs + min(length, max_len)])
    ofs += max_len
    return raw.decode("cp437", errors="replace"), ofs


def _write_short_string(value: str, max_len: int) -> bytes:
    enc = value.encode("cp437", errors="replace")[:max_len]
    return bytes([len(enc)]) + enc.ljust(max_len, b"\x00")


def _parse_inventory(data: memoryview, ofs: int) -> tuple[Inventory, int]:
    inv = Inventory()
    inv.ammo, inv.gems = struct.unpack_from("<hh", data, ofs)
    ofs += 4
    inv.keys = [bool(data[ofs + i]) for i in range(7)]
    ofs += 7
    (
        inv.strength,
        inv.room,
        inv.torches,
        inv.torch_time,
        inv.ener_time,
        inv.inviso_time,
        inv.score,
    ) = struct.unpack_from("<hhhhhhh", data, ofs)
    ofs += 14
    inv.orig_name, ofs = _read_short_string(data, ofs, 20)
    flags: list[str] = []
    for _ in range(c.NUM_FLAGS):
        flag, ofs = _read_short_string(data, ofs, 20)
        flags.append(flag)
    inv.flags = flags
    inv.room_time, inv.last_sec = struct.unpack_from("<hH", data, ofs)
    ofs += 4
    inv.play_flag = bool(data[ofs])
    ofs += 1
    inv.wpad = bytes(data[ofs : ofs + 14])
    ofs += 14
    return inv, ofs


def _pack_inventory(inv: Inventory) -> bytes:
    b = bytearray()
    b.extend(struct.pack("<hh", inv.ammo, inv.gems))
    b.extend(bytes(int(v) for v in inv.keys[:7]).ljust(7, b"\x00"))
    b.extend(
        struct.pack(
            "<hhhhhhh",
            inv.strength,
            inv.room,
            inv.torches,
            inv.torch_time,
            inv.ener_time,
            inv.inviso_time,
            inv.score,
        )
    )
    b.extend(_write_short_string(inv.orig_name, 20))
    for idx in range(c.NUM_FLAGS):
        b.extend(_write_short_string(inv.flags[idx] if idx < len(inv.flags) else "", 20))
    b.extend(struct.pack("<hH", inv.room_time, inv.last_sec & 0xFFFF))
    b.append(1 if inv.play_flag else 0)
    b.extend(inv.wpad[:14].ljust(14, b"\x00"))
    return bytes(b)


def _parse_room_info(data: memoryview, ofs: int) -> tuple[RoomInfo, int]:
    info = RoomInfo()
    info.can_shoot = data[ofs]
    info.is_dark = bool(data[ofs + 1])
    info.room_udlr = [data[ofs + 2 + i] for i in range(4)]
    info.re_enter = bool(data[ofs + 6])
    ofs += 7
    info.bot_msg, ofs = _read_short_string(data, ofs, c.XS - 2)
    info.start_x = data[ofs]
    info.start_y = data[ofs + 1]
    info.time_limit = _INT16.unpack_from(data, ofs + 2)[0]
    ofs += 4
    info.ypad = bytes(data[ofs : ofs + 16])
    ofs += 16
    return info, ofs


def _pack_room_info(info: RoomInfo) -> bytes:
    b = bytearray()
    b.append(info.can_shoot & 0xFF)
    b.append(1 if info.is_dark else 0)
    b.extend(bytes((info.room_udlr + [0, 0, 0, 0])[:4]))
    b.append(1 if info.re_enter else 0)
    b.extend(_write_short_string(info.bot_msg, c.XS - 2))
    b.append(info.start_x & 0xFF)
    b.append(info.start_y & 0xFF)
    b.extend(_INT16.pack(info.time_limit))
    b.extend(info.ypad[:16].ljust(16, b"\x00"))
    return bytes(b)


def _decode_room(blob: bytes) -> Room:
    data = memoryview(blob)
    ofs = 0
    title, ofs = _read_short_string(data, ofs, 50)

    board = [[BoardCell() for _ in range(c.YS + 2)] for _ in range(c.XS + 2)]
    for x in range(c.XS + 2):
        board[x][0] = BoardCell(c.BOUND, 0)
        board[x][c.YS + 1] = BoardCell(c.BOUND, 0)
    for y in range(c.YS + 2):
        board[0][y] = BoardCell(c.BOUND, 0)
        board[c.XS + 1][y] = BoardCell(c.BOUND, 0)

    x, y = 1, 1
    rle_len = 0
    rle_kind = c.EMPTY
    rle_color = 0
    while y <= c.YS:
        if rle_len <= 0:
            if ofs + 3 > len(data):
                raise ValueError("Room RLE decode overflow")
            rle_len = data[ofs]
            rle_kind = data[ofs + 1]
            rle_color = data[ofs + 2]
            ofs += 3
        board[x][y] = BoardCell(rle_kind, rle_color)
        x += 1
        if x > c.XS:
            x = 1
            y += 1
        rle_len -= 1

    room_info, ofs = _parse_room_info(data, ofs)
    num_objs = _INT16.unpack_from(data, ofs)[0]
    ofs += 2

    objs: list[Obj] = []
    for idx in range(num_objs + 1):
        if ofs + _OBJ_HEAD.size > len(data):
            raise ValueError("Object table decode overflow")
        (
            ox,
            oy,
            xd,
            yd,
            cycle,
            intel,
            rate,
            room,
            child,
            parent,
            under_kind,
            under_color,
            _inside_ptr,
            offset,
            inside_len,
            pad,
        ) = _OBJ_HEAD.unpack_from(data, ofs)
        ofs += _OBJ_HEAD.size

        inside = b""
        if inside_len > 0:
            end = ofs + inside_len
            if end > len(data):
                raise ValueError("Object inside decode overflow")
            inside = bytes(data[ofs:end])
            ofs = end
        elif inside_len < 0:
            ref_idx = -inside_len
            if 0 <= ref_idx < len(objs):
                inside = objs[ref_idx].inside

        obj = Obj(
            x=ox,
            y=oy,
            xd=xd,
            yd=yd,
            cycle=cycle,
            intel=intel,
            rate=rate,
            room=room,
            child=child,
            parent=parent,
            under=BoardCell(under_kind, under_color),
            offset=offset,
            inside=inside,
            pad=pad,
        )
        objs.append(obj)

    if not objs:
        raise ValueError("Room does not contain player object")

    return Room(title=title, board=board, objs=objs, room_info=room_info)


def _encode_room(room: Room) -> bytes:
    out = bytearray()
    out.extend(_write_short_string(room.title, 50))

    x, y = 1, 1
    run_len = 1
    run_cell = replace(room.board[x][y])
    while True:
        x += 1
        if x > c.XS:
            x = 1
            y += 1
        cell = room.board[x][y] if y <= c.YS else BoardCell(c.BOUND, 0)
        if (
            y <= c.YS
            and cell.kind == run_cell.kind
            and cell.color == run_cell.color
            and run_len < 255
        ):
            run_len += 1
        else:
            out.append(run_len)
            out.append(run_cell.kind & 0xFF)
            out.append(run_cell.color & 0xFF)
            run_cell = replace(cell)
            run_len = 1
        if y > c.YS:
            break

    out.extend(_pack_room_info(room.room_info))
    out.extend(_INT16.pack(room.num_objs))

    inside_alias: dict[int, int] = {}
    for idx, obj in enumerate(room.objs):
        inside_len = len(obj.inside)
        inside_key = id(obj.inside) if inside_len > 0 else 0
        inside_ref = 0
        if inside_len > 0 and inside_key in inside_alias:
            inside_ref = -inside_alias[inside_key]
            inside_len = inside_ref
        elif inside_len > 0:
            inside_alias[inside_key] = idx

        out.extend(
            _OBJ_HEAD.pack(
                obj.x & 0xFF,
                obj.y & 0xFF,
                obj.xd,
                obj.yd,
                obj.cycle,
                obj.intel & 0xFF,
                obj.rate & 0xFF,
                obj.room & 0xFF,
                obj.child,
                obj.parent,
                obj.under.kind & 0xFF,
                obj.under.color & 0xFF,
                0,
                obj.offset,
                inside_len,
                obj.pad[:8].ljust(8, b"\x00"),
            )
        )
        if inside_len > 0:
            out.extend(obj.inside)

    return bytes(out)


def load_world(path: str) -> GameWorld:
    data = memoryview(open(path, "rb").read())
    if len(data) < c.HEADER_LEN:
        raise ValueError("World file is too short")

    ofs = 0
    first = _INT16.unpack_from(data, ofs)[0]
    ofs += 2

    if first < 0:
        if first != c.VERSION_MARKER:
            raise ValueError("Unsupported world version marker")
        num_rooms = _INT16.unpack_from(data, ofs)[0]
        ofs += 2
    else:
        num_rooms = first

    inv, _ = _parse_inventory(data, ofs)

    cursor = c.HEADER_LEN
    rooms: list[Room] = []
    for _ in range(num_rooms + 1):
        if cursor + 2 > len(data):
            raise ValueError("Unexpected EOF while reading room size")
        room_size = _INT16.unpack_from(data, cursor)[0]
        cursor += 2
        if room_size < 0 or cursor + room_size > len(data):
            raise ValueError("Invalid room size")
        blob = bytes(data[cursor : cursor + room_size])
        cursor += room_size
        rooms.append(_decode_room(blob))

    world = GameWorld(num_rooms=num_rooms, rooms=rooms, inv=inv)
    world.game_name = path
    return world


def save_world(world: GameWorld, path: str) -> None:
    header = bytearray(c.HEADER_LEN)
    struct.pack_into("<h", header, 0, c.VERSION_MARKER)
    struct.pack_into("<h", header, 2, world.num_rooms)
    inv_blob = _pack_inventory(world.inv)
    max_copy = min(len(inv_blob), c.HEADER_LEN - 4)
    header[4 : 4 + max_copy] = inv_blob[:max_copy]

    out = io.BytesIO()
    out.write(header)
    for idx in range(world.num_rooms + 1):
        blob = _encode_room(world.rooms[idx])
        out.write(_INT16.pack(len(blob)))
        out.write(blob)

    with open(path, "wb") as f:
        f.write(out.getvalue())


def bootstrap_world(path: str | None = None) -> GameWorld:
    if path:
        return load_world(path)
    return make_new_world()
