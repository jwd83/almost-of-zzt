from __future__ import annotations

import math
import random
from array import array

import pygame

TIMER_INTERVAL_MS = 55


def _seq(*values: int) -> bytes:
    return bytes(values)


SFX_OOP_ERROR = _seq(0x50, 10)
SFX_OOP_SHOOT = _seq(0x30, 1, 0x26, 1)
SFX_PLAYER_SHOOT = _seq(0x40, 1, 0x30, 1, 0x20, 1)
SFX_SHOT_HIT = _seq(0x10, 1)
SFX_BULLET_RICOCHET = _seq(0xF9, 1)
SFX_BOMB_ARM = _seq(0x30, 1, 0x35, 1, 0x40, 1, 0x45, 1, 0x50, 1)
SFX_BOMB_TICK_EVEN = _seq(0xF8, 1)
SFX_BOMB_TICK_ODD = _seq(0xF5, 1)
SFX_BOMB_DETONATE = _seq(0x60, 1, 0x50, 1, 0x40, 1, 0x30, 1, 0x20, 1, 0x10, 1)
SFX_XPORT = _seq(0x30, 1, 0x42, 1, 0x34, 1, 0x46, 1, 0x38, 1, 0x4A, 1, 0x40, 1, 0x52, 1)
SFX_ENERGIZER = _seq(
    *(
        [0x20, 3, 0x23, 3, 0x24, 3, 0x25, 3, 0x35, 3, 0x25, 3, 0x23, 3, 0x20, 3]
        * 7
    )
)
SFX_SLIME_TOUCH = _seq(0x20, 1, 0x23, 1)
SFX_DUPER_OK = _seq(0x30, 2, 0x32, 2, 0x34, 2, 0x35, 2, 0x37, 2)
SFX_DUPER_FAIL = _seq(0x18, 1, 0x16, 1)
SFX_KEY_ALREADY = _seq(0x30, 2, 0x20, 2)
SFX_KEY_GET = _seq(
    0x40,
    1,
    0x44,
    1,
    0x47,
    1,
    0x40,
    1,
    0x44,
    1,
    0x47,
    1,
    0x40,
    1,
    0x44,
    1,
    0x47,
    1,
    0x50,
    2,
)
SFX_AMMO_GET = _seq(0x30, 1, 0x31, 1, 0x32, 1)
SFX_GEM_GET = _seq(0x40, 1, 0x37, 1, 0x34, 1, 0x30, 1)
SFX_DOOR_OPEN = _seq(0x30, 1, 0x37, 1, 0x3B, 1, 0x30, 1, 0x37, 1, 0x3B, 1, 0x40, 4)
SFX_DOOR_LOCKED = _seq(0x17, 1, 0x10, 1)
SFX_PUSH = _seq(0x15, 1)
SFX_TORCH_GET = _seq(0x30, 1, 0x39, 1, 0x34, 2)
SFX_INVISO = _seq(0x12, 1, 0x10, 1)
SFX_BRUSH = _seq(0x39, 1)
SFX_WATER_BLOCK = _seq(0x40, 1, 0x50, 1)
SFX_PLAYER_REENTER = _seq(0x20, 1, 0x23, 1, 0x27, 1, 0x30, 1, 0x10, 1)
SFX_PLAYER_HURT = _seq(0x10, 1, 0x20, 1, 0x13, 1, 0x23, 1)
SFX_PLAYER_DIE = _seq(
    0x20,
    3,
    0x23,
    3,
    0x27,
    3,
    0x30,
    3,
    0x27,
    3,
    0x2A,
    3,
    0x32,
    3,
    0x37,
    3,
    0x35,
    3,
    0x38,
    3,
    0x40,
    3,
    0x45,
    3,
    0x10,
    10,
)
SFX_ZAP_BULLET = _seq(0x20, 1)
SFX_ZAP_ENEMY = _seq(0x40, 1, 0x10, 1, 0x50, 1, 0x30, 1)
SFX_PASSAGE = _seq(
    0x30,
    1,
    0x34,
    1,
    0x37,
    1,
    0x31,
    1,
    0x35,
    1,
    0x38,
    1,
    0x32,
    1,
    0x36,
    1,
    0x39,
    1,
    0x33,
    1,
    0x37,
    1,
    0x3A,
    1,
    0x34,
    1,
    0x38,
    1,
    0x40,
    1,
)
SFX_TORCH_OUT = _seq(0x30, 1, 0x20, 1, 0x10, 1)
SFX_ENERGIZER_WARN = _seq(0x20, 3, 0x1A, 3, 0x17, 3, 0x16, 3, 0x15, 3, 0x13, 3, 0x10, 3)
SFX_TIMELIMIT_WARN = _seq(0x40, 6, 0x45, 6, 0x40, 6, 0x35, 6, 0x40, 6, 0x45, 6, 0x40, 10)
SFX_SECRET_CMD = _seq(0x27, 4)


class _NullSpeaker:
    def play_note(self, freq: int) -> None:
        del freq

    def play_digit(self, digit: int, data: list[int]) -> None:
        del digit, data

    def stop(self) -> None:
        return

    def shutdown(self) -> None:
        return


class _PygameSpeaker:
    def __init__(self, sample_rate: int, digits: list[list[int]]) -> None:
        self.sample_rate = sample_rate
        self.amplitude = 9000
        self._tone_cache: dict[int, pygame.mixer.Sound] = {}
        self._digit_cache: dict[int, pygame.mixer.Sound] = {}
        self._digits = digits
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=sample_rate, size=-16, channels=1, buffer=512)
        self._channel = pygame.mixer.find_channel(True) or pygame.mixer.Channel(0)

    def _make_square_wave(self, freq: int) -> pygame.mixer.Sound:
        period = max(8, int(self.sample_rate / max(1, freq)))
        half = period // 2
        data = array("h")
        for i in range(period):
            data.append(self.amplitude if i < half else -self.amplitude)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _make_digit_sound(self, data: list[int]) -> pygame.mixer.Sound:
        frames_per_ms = max(1, self.sample_rate // 1000)
        out = array("h")
        count = max(0, min(data[0], len(data) - 1))
        for i in range(1, count + 1):
            freq = max(1, data[i])
            half = max(1, int(self.sample_rate / (2 * freq)))
            cycle = half * 2
            for j in range(frames_per_ms):
                out.append(self.amplitude if (j % cycle) < half else -self.amplitude)
        if not out:
            out.append(0)
        return pygame.mixer.Sound(buffer=out.tobytes())

    def play_note(self, freq: int) -> None:
        if freq <= 0:
            self.stop()
            return
        tone = self._tone_cache.get(freq)
        if tone is None:
            tone = self._make_square_wave(freq)
            self._tone_cache[freq] = tone
        self._channel.play(tone, loops=-1)

    def play_digit(self, digit: int, data: list[int]) -> None:
        clip = self._digit_cache.get(digit)
        if clip is None:
            clip = self._make_digit_sound(data)
            self._digit_cache[digit] = clip
        self._channel.play(clip)

    def stop(self) -> None:
        self._channel.stop()

    def shutdown(self) -> None:
        self.stop()


class SoundEngine:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self.sound_f = True
        self.sound_off = False
        self.note_priority = -1
        self.sound_speed = 1
        self.sound_count = 0
        self.notes = b""
        self.sound_ptr = 0
        self.make_sound = False
        self._last_tick_ms: int | None = None
        self._note_table = self._init_note_table()
        self._digits = self._init_digits()
        self._speaker: _NullSpeaker | _PygameSpeaker = _NullSpeaker()

    def bind_pygame(self) -> None:
        try:
            self._speaker = _PygameSpeaker(44100, self._digits)
        except pygame.error:
            self._speaker = _NullSpeaker()

    def set_enabled(self, enabled: bool) -> None:
        self.sound_f = enabled
        if not enabled:
            self.make_sound = False
            self._speaker.stop()

    def set_off(self, off: bool) -> None:
        self.sound_off = off
        if off:
            self.stop()

    def stop(self) -> None:
        self.notes = b""
        self.make_sound = False
        self.sound_ptr = 0
        self.sound_count = 0
        self._speaker.stop()

    def shutdown(self) -> None:
        self.stop()
        self._speaker.shutdown()

    def add(self, priority: int, seq: bytes) -> None:
        if self.sound_off or not seq:
            return
        if (not self.make_sound) or ((priority >= self.note_priority) and (self.note_priority != -1)) or priority == -1:
            if (priority >= 0) or (not self.make_sound):
                self.note_priority = priority
                self.notes = bytes(seq)
                self.sound_ptr = 0
                self.sound_count = 1
            else:
                self.notes = self.notes[self.sound_ptr :]
                self.sound_ptr = 0
                if (len(self.notes) + len(seq)) < 255:
                    self.notes += bytes(seq)
            self.make_sound = True

    def music(self, spec: str) -> bytes:
        result: list[int] = []
        octave = 3
        duration = 1
        i = 0
        while i < len(spec):
            ch = spec[i].upper()
            i += 1
            if ch == "T":
                duration = 1
            elif ch == "S":
                duration = 2
            elif ch == "I":
                duration = 4
            elif ch == "Q":
                duration = 8
            elif ch == "H":
                duration = 16
            elif ch == "W":
                duration = 32
            elif ch == ".":
                duration = (duration * 3) // 2
            elif ch == "3":
                duration = duration // 3
            elif ch == "+":
                if octave < 6:
                    octave += 1
            elif ch == "-":
                if octave > 1:
                    octave -= 1
            elif ch in "ABCDEFG":
                base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[ch]
                if i < len(spec):
                    nxt = spec[i].upper()
                    if nxt == "!":
                        base -= 1
                        i += 1
                    elif nxt == "#":
                        base += 1
                        i += 1
                result.append((octave * 0x10 + base) & 0xFF)
                result.append(duration & 0xFF)
            elif ch == "X":
                result.append(0)
                result.append(duration & 0xFF)
            elif "0" <= ch <= "9":
                result.append(0xF0 + ord(ch) - ord("0"))
                result.append(duration & 0xFF)
        return bytes(result)

    def tick(self, now_ms: int) -> None:
        if self._last_tick_ms is None:
            self._last_tick_ms = now_ms
            return
        if now_ms < self._last_tick_ms:
            self._last_tick_ms = now_ms
            return
        while now_ms - self._last_tick_ms >= TIMER_INTERVAL_MS:
            self._last_tick_ms += TIMER_INTERVAL_MS
            self._timer_step()

    def _timer_step(self) -> None:
        if not self.sound_f:
            self.make_sound = False
            self._speaker.stop()
            return

        if not self.make_sound:
            return

        self.sound_count -= 1
        if self.sound_count > 0:
            return

        self._speaker.stop()
        if self.sound_ptr >= len(self.notes):
            self.make_sound = False
            return

        note = self.notes[self.sound_ptr]
        if note == 0:
            self._speaker.stop()
        elif note < 0xF0:
            self._speaker.play_note(self._note_table[note])
        else:
            digit = note - 0xF0
            if 0 <= digit <= 9:
                self._speaker.play_digit(digit, self._digits[digit])

        self.sound_ptr += 1
        if self.sound_ptr >= len(self.notes):
            self.make_sound = False
            return

        self.sound_count = max(0, self.sound_speed * self.notes[self.sound_ptr])
        self.sound_ptr += 1

    def _init_note_table(self) -> list[int]:
        note_table = [0] * 256
        root = 32.0
        ln2 = math.log(2.0)
        step = math.exp(ln2 / 12.0)
        for octave in range(1, 16):
            current = root * math.exp(ln2 * octave)
            for note in range(12):
                note_table[octave * 0x10 + note] = int(current)
                current *= step
        return note_table

    def _init_digits(self) -> list[list[int]]:
        digits = [[0] * 17 for _ in range(10)]
        digits[0][0] = 1
        digits[0][1] = 3200
        for d in range(1, 10):
            digits[d][0] = 14

        for c in range(1, 15):
            digits[1][c] = c * 100 + 1000
        for c in range(1, 17):
            digits[2][c] = 1600 + 1600 * (c % 2) + 1600 * (c % 4)
        for c in range(1, 15):
            digits[4][c] = self._rng.randrange(5000) + 500
        for c in range(1, 9):
            digits[5][c * 2 - 1] = 1600
            digits[5][c * 2] = self._rng.randrange(1600) + 800
        for c in range(1, 15):
            digits[6][c] = 880 + 880 * (c % 2) + 440 * (c % 3)
        for c in range(1, 15):
            digits[7][c] = 700 - 12 * c
        for c in range(1, 15):
            digits[8][c] = 1200 + c * 20 - self._rng.randrange(c * 40)
        for c in range(1, 15):
            digits[9][c] = self._rng.randrange(440) + 220
        return digits
