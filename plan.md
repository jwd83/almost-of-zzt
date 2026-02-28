# Plan: Remaining Work

## Current state

Playing ZZT worlds is feature-complete. All 27 ZZT-OOP commands, all 25 element types, sound, save/restore, high scores, and the full game loop are implemented and tested (49 tests passing). The editor can modify existing worlds but cannot create multi-board worlds from scratch.

## Editor showstoppers

These two gaps block world creation from scratch:

### 1. Add new boards

`_switch_board` navigates boards 0..`num_rooms` but there is no way to allocate a new board. In the original ZZT editor, entering a board number one past the last would create it. Needs:
- Accept `num_rooms + 1` in the board switcher
- Append a fresh `make_default_room()` to `world.rooms`
- Increment `world.num_rooms`
- ~15 lines in `editor.py`

### 2. Board exit links (room_udlr)

`room_info.room_udlr[0..3]` (Up/Down/Left/Right board connections) are never exposed in the editor. Without them, boards can only connect via passages. Needs:
- Add 4 integer prompts (board number for each direction) to `_set_board_info`
- ~20 lines in `editor.py`

## Editor quality-of-life

These are not blockers but would make the editor practical for real world-building:

### 3. World Info editing

No way to set world name, `orig_name`, or starting board number. Add a `W` key handler with 2-3 string/int prompts. ~15 lines.

### 4. Re-enter flag and start position in Board Info

`re_enter` (player re-enters from start position on zap) and `start_x`/`start_y` are not editable. Add to `_set_board_info`. ~10 lines.

### 5. Background color picker

`C` key only cycles foreground (bits 0-3). Add a second key (e.g., Shift+C) to cycle the background nibble (bits 4-7). ~10 lines.

### 6. Eye-dropper

Sample the element kind and color at the cursor into the current pattern. One key binding, ~5 lines.

## Cosmetic/low-priority

### 7. Help/About scroll rendering

`H` and `A` keys show a one-line status message instead of rendering the `.HLP` files as scrolls. Low value — almost no one reads these.

### 8. Dark-room incremental redraw

Currently full-frame redraw. Visually identical, just not the exact Pascal algorithm. No gameplay impact.

### 9. Bottom message lifecycle

Simplified timer vs. Pascal's object-slot semantics. Barely noticeable difference.

### 10. .BRD import/export

Standalone board file support. Niche compatibility feature.

## Suggested order

Items 1-2 are the minimum to unblock world creation (~35 lines total). Items 3-6 round out the editor into something usable (~40 more lines). Items 7-10 are optional polish.
