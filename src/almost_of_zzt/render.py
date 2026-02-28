from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame

from . import constants as c


def attr_to_colors(attr: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    fg = c.EGA16[attr & 0x0F]
    bg = c.EGA16[(attr >> 4) & 0x0F]
    return fg, bg


def cp437_char(code: int) -> str:
    return bytes([code & 0xFF]).decode("cp437", errors="replace")


@dataclass
class Renderer:
    screen: pygame.Surface
    font: pygame.font.Font = field(init=False)
    glyph_cache: dict[tuple[int, int], pygame.Surface] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.font = self._load_font()

    def _load_font(self) -> pygame.font.Font:
        font_candidates = (
            "AcPlus_IBM_VGA_8x14.ttf",
            "AcPlus_IBM_EGA_8x8.ttf",
            "APL386.ttf",
        )
        base = Path(__file__).resolve().parent
        for name in font_candidates:
            font_path = base / name
            if not font_path.is_file():
                continue
            fitted = self._load_best_fit_font(font_path)
            if fitted is not None:
                return fitted
        return pygame.font.SysFont("Courier New", c.CELL_H, bold=True)

    def _load_best_fit_font(self, font_path: Path) -> pygame.font.Font | None:
        for size in range(32, 5, -1):
            font = pygame.font.Font(str(font_path), size)
            if self._font_fits_cell(font):
                return font
        return None

    def _font_fits_cell(self, font: pygame.font.Font) -> bool:
        for code in range(256):
            w, h = font.size(cp437_char(code))
            if w > c.CELL_W or h > c.CELL_H:
                return False
        return True

    def draw_glyph(self, col: int, row: int, code: int, attr: int) -> None:
        x = c.BOARD_OFFSET_X + col * c.CELL_W
        y = c.BOARD_OFFSET_Y + row * c.CELL_H
        fg, bg = attr_to_colors(attr)
        key = ((code & 0xFF), attr & 0xFF)
        surf = self.glyph_cache.get(key)
        if surf is None:
            surf = pygame.Surface((c.CELL_W, c.CELL_H))
            surf.fill(bg)
            glyph = self.font.render(cp437_char(code), False, fg)
            rect = glyph.get_rect(center=(c.CELL_W // 2, c.CELL_H // 2))
            surf.blit(glyph, rect)
            self.glyph_cache[key] = surf
        self.screen.blit(surf, (x, y))

    def clear(self) -> None:
        self.screen.fill((0, 0, 0))

    def draw_text(self, col: int, row: int, text: str, attr: int) -> None:
        for i, ch in enumerate(text):
            b = ch.encode("cp437", errors="replace")[0]
            self.draw_glyph(col + i, row, b, attr)
