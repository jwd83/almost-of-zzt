from __future__ import annotations

import random

from almost_of_zzt import constants as c
from almost_of_zzt.engine import GameEngine
from almost_of_zzt.model import Obj, make_new_world
from almost_of_zzt.sound import SoundEngine


def test_music_parser_matches_pascal_shape() -> None:
    s = SoundEngine(random.Random(1))
    seq = s.music("QC#D!X1")
    assert seq == bytes((0x31, 8, 0x31, 8, 0x00, 8, 0xF1, 8))


def test_sound_add_priority_and_append_semantics() -> None:
    s = SoundEngine(random.Random(2))

    s.add(4, bytes((0x30, 1)))
    assert s.notes == bytes((0x30, 1))
    assert s.note_priority == 4

    s.add(2, bytes((0x40, 1)))
    assert s.notes == bytes((0x30, 1))

    s.add(-1, bytes((0x20, 1)))
    assert s.notes == bytes((0x30, 1, 0x20, 1))
    assert s.note_priority == 4


def test_timer_progression_follows_sound_count() -> None:
    s = SoundEngine(random.Random(3))
    s.add(1, bytes((0x30, 1, 0x31, 1)))

    s.tick(0)
    s.tick(55)
    assert s.make_sound is True
    assert s.sound_ptr == 2

    s.tick(110)
    assert s.make_sound is True
    assert s.sound_ptr == 4

    s.tick(165)
    assert s.make_sound is False

    s.add(1, bytes((0x30, 1)))
    s.set_enabled(False)
    assert s.make_sound is False


def test_oop_play_queues_music_sequence() -> None:
    world = make_new_world()
    world.game_name = "TEST"
    world.inv.room = 0
    e = GameEngine(world)

    idx = e.add_obj(10, 10, c.PROG, 0x0F, 3, Obj(inside=b"@BOT\r#PLAY C\r#END\r"))
    e.oop.exec_obj(idx)

    assert e.sound.notes != b""
    assert e.sound.make_sound is True
