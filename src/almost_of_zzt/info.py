from __future__ import annotations

from dataclasses import dataclass

from . import constants as c


@dataclass(slots=True)
class InfoDef:
    ch: int = ord(" ")
    col: int = 0xFF
    killable: bool = False
    movable: bool = False
    show_in_dark: bool = False
    terrain: bool = False
    go_thru: bool = False
    print_dynamic: bool = False
    cycle: int = -1
    update: str = "upd_nothing"
    touch: str = "touch_nothing"
    score: int = 0
    descr: str = ""


def _make_table() -> list[InfoDef]:
    return [InfoDef() for _ in range(c.NUM_CLASSES + 1)]


def init_info_play() -> list[InfoDef]:
    info = _make_table()

    def seti(kind: int, **kwargs: object) -> None:
        entry = info[kind]
        for key, value in kwargs.items():
            setattr(entry, key, value)

    seti(c.EMPTY, ch=ord(" "), col=0x70, movable=True, go_thru=True, descr="Empty")
    seti(c.MONITOR, ch=ord(" "), col=0x07, cycle=1, update="upd_monitor", descr="Monitor")
    seti(
        c.WATER,
        ch=0xB0,
        col=0xF9,
        terrain=True,
        touch="touch_water",
        descr="Water",
    )
    seti(c.BRUSH, ch=0xB0, col=0x20, touch="touch_brush", descr="Forest")
    seti(
        c.PLAYER,
        ch=0x02,
        col=0x1F,
        killable=True,
        movable=True,
        show_in_dark=True,
        cycle=1,
        update="upd_player",
        descr="Player",
    )
    seti(
        c.ENEMY,
        ch=0xEA,
        col=0x0C,
        killable=True,
        movable=True,
        cycle=2,
        update="upd_enemy",
        touch="touch_enemy",
        score=1,
        descr="Lion",
    )
    seti(
        c.S_ENEMY,
        ch=0xE3,
        col=0x0B,
        killable=True,
        movable=True,
        cycle=2,
        update="upd_s_enemy",
        touch="touch_enemy",
        score=2,
        descr="Tiger",
    )
    seti(
        c.CENTI_H,
        ch=0xE9,
        killable=True,
        cycle=2,
        update="upd_centi_h",
        touch="touch_enemy",
        score=1,
        descr="Head",
    )
    seti(
        c.CENTI,
        ch=ord("O"),
        killable=True,
        cycle=2,
        update="upd_centi",
        touch="touch_enemy",
        score=3,
        descr="Segment",
    )
    seti(
        c.BULLET,
        ch=0xF8,
        col=0x0F,
        killable=True,
        cycle=1,
        update="upd_bullet",
        touch="touch_enemy",
        descr="Bullet",
    )
    seti(
        c.SBOMB,
        ch=ord("S"),
        col=0x0F,
        cycle=1,
        update="upd_sbomb",
        touch="touch_enemy",
        print_dynamic=True,
        descr="Star",
    )
    seti(c.AKEY, ch=0x0C, movable=True, touch="touch_key", descr="Key")
    seti(c.AMMO, ch=0x84, col=0x03, movable=True, touch="touch_ammo", descr="Ammo")
    seti(
        c.GEM,
        ch=0x04,
        movable=True,
        touch="touch_gem",
        killable=True,
        descr="Gem",
    )
    seti(
        c.PASSAGE,
        ch=0xF0,
        col=0xFE,
        cycle=0,
        show_in_dark=True,
        touch="touch_passage",
        descr="Passage",
    )
    seti(c.DOOR, ch=0x0A, col=0xFE, touch="touch_door", descr="Door")
    seti(
        c.SCROLL,
        ch=0xE8,
        col=0x0F,
        touch="touch_scroll",
        update="upd_scroll",
        movable=True,
        cycle=1,
        descr="Scroll",
    )
    seti(
        c.DUPER,
        ch=0xFA,
        col=0x0F,
        cycle=2,
        update="upd_duper",
        print_dynamic=True,
        descr="Duplicator",
    )
    seti(c.TORCH, ch=0x9D, col=0x06, show_in_dark=True, touch="touch_torch", descr="Torch")
    seti(
        c.SHOOTER,
        ch=0x18,
        cycle=2,
        update="upd_shooter",
        print_dynamic=True,
        descr="Spinning gun",
    )
    seti(
        c.WANDERER,
        ch=0x05,
        col=0x0D,
        killable=True,
        movable=True,
        cycle=1,
        update="upd_wanderer",
        touch="touch_enemy",
        score=2,
        descr="Ruffian",
    )
    seti(
        c.CHASER,
        ch=0x99,
        col=0x06,
        killable=True,
        movable=True,
        cycle=3,
        update="upd_chaser",
        touch="touch_enemy",
        score=1,
        descr="Bear",
    )
    seti(
        c.SLIME,
        ch=ord("*"),
        col=0xFF,
        cycle=3,
        update="upd_slime",
        touch="touch_slime",
        descr="Slime",
    )
    seti(c.SHARK, ch=ord("^"), col=0x07, cycle=3, update="upd_shark", descr="Shark")
    seti(
        c.CONVEYOR_CW,
        ch=ord("/"),
        cycle=3,
        print_dynamic=True,
        update="upd_conveyor_cw",
        descr="Clockwise",
    )
    seti(
        c.CONVEYOR_CCW,
        ch=ord("\\"),
        cycle=2,
        print_dynamic=True,
        update="upd_conveyor_ccw",
        descr="Counter",
    )

    seti(c.SOLID_WALL, ch=0xDB, descr="Solid")
    seti(c.NORM_WALL, ch=0xB2, descr="Normal")
    seti(c.LINE2, ch=0xCE, print_dynamic=True, descr="Line")
    seti(c.VERT_WALL, ch=0xBA)
    seti(c.HORIZ_WALL, ch=0xCD)
    seti(c.RICOCHET, ch=0x2A, col=0x0A, descr="Ricochet")
    seti(c.BREAK_WALL, ch=0xB1, killable=False, descr="Breakable")
    seti(c.BLOCK, ch=0xFE, movable=True, touch="touch_push", descr="Boulder")
    seti(c.SLIDER_NS, ch=0x12, touch="touch_push", descr="Slider (NS)")
    seti(c.SLIDER_EW, ch=0x1D, touch="touch_push", descr="Slider (EW)")

    seti(
        c.XPORTER,
        ch=0xC5,
        touch="touch_xporter",
        print_dynamic=True,
        cycle=2,
        update="upd_xporter",
        descr="Transporter",
    )
    seti(
        c.PUSHER,
        ch=0x10,
        col=0xFF,
        print_dynamic=True,
        cycle=4,
        update="upd_pusher",
        descr="Pusher",
    )
    seti(
        c.BOMB,
        ch=0x0B,
        print_dynamic=True,
        movable=True,
        cycle=6,
        update="upd_bomb",
        touch="touch_bomb",
        descr="Bomb",
    )
    seti(c.ENERGIZER, ch=0x7F, col=0x05, touch="touch_energizer", descr="Energizer")
    seti(
        c.BLINK_WALL,
        ch=0xCE,
        cycle=1,
        update="upd_blink_wall",
        print_dynamic=True,
        descr="Blink wall",
    )
    seti(c.FAKE_WALL, ch=0xB2, terrain=True, go_thru=True, touch="touch_fake_wall", descr="Fake")
    seti(c.INVISO_WALL, ch=ord(" "), touch="touch_inviso_wall", descr="Invisible")
    seti(
        c.PROG,
        ch=0x02,
        cycle=3,
        print_dynamic=True,
        update="upd_prog",
        touch="touch_prog",
        descr="Object",
    )
    seti(c.SPECIAL, update="upd_special")
    seti(c.BOUND, touch="touch_bound")

    return info
