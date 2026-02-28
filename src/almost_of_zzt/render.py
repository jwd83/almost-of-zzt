from __future__ import annotations

from dataclasses import dataclass, field

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
        self.font = pygame.font.SysFont("Courier New", 14, bold=True)

    def draw_glyph(self, col: int, row: int, code: int, attr: int) -> None:
        x = c.BOARD_OFFSET_X + col * c.CELL_W
        y = c.BOARD_OFFSET_Y + row * c.CELL_H
        fg, bg = attr_to_colors(attr)
        key = ((code & 0xFF), attr & 0xFF)
        surf = self.glyph_cache.get(key)
        if surf is None:
            surf = pygame.Surface((c.CELL_W, c.CELL_H))
            surf.fill(bg)
            glyph = self.font.render(cp437_char(code), True, fg)
            rect = glyph.get_rect(center=(c.CELL_W // 2, c.CELL_H // 2 + 1))
            surf.blit(glyph, rect)
            self.glyph_cache[key] = surf
        self.screen.blit(surf, (x, y))

    def clear(self) -> None:
        self.screen.fill((0, 0, 0))

    def draw_text(self, col: int, row: int, text: str, attr: int) -> None:
        for i, ch in enumerate(text):
            b = ch.encode("cp437", errors="replace")[0]
            self.draw_glyph(col + i, row, b, attr)
