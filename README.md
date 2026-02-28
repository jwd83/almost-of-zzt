# almost-of-zzt

Pygame-ce runtime clone targeting the Pascal source in `ref/GAME`.

## Requirements

- Python 3.13+
- `uv`

## Run

```bash
uv sync
uv run almost-of-zzt
```

Load an existing world file:

```bash
uv run almost-of-zzt path/to/WORLD.ZZT
```

## Notes

- Display target is `640x360`.
- Original ZZT-style world/save binary formats are supported by `src/almost_of_zzt/world.py`.
- `S` saves to `SAVED.SAV` in the current working directory.
- Movement uses arrow keys (or keypad `8/2/4/6`), `Shift+direction` shoots.
- Scroll/dialog windows use arrows for navigation, `Enter` to continue/select, `Esc` to close.
- If no world is provided, a small playable demo room is generated.

## Layout

- `src/almost_of_zzt/constants.py`: IDs and timing constants from Pascal.
- `src/almost_of_zzt/model.py`: data structures for board/objects/world.
- `src/almost_of_zzt/world.py`: `.ZZT/.SAV` load/save codec (RLE + stat records).
- `src/almost_of_zzt/oop.py`: partial ZZT-OOP interpreter.
- `src/almost_of_zzt/engine.py`: game loop, object updates, touches, rendering orchestration.
- `src/almost_of_zzt/render.py`: CP437-style text rendering with EGA colors.
