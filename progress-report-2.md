# Progress Report 2

Overall completion: ~75-80%. The runtime is playable with original .ZZT world files and now includes high score persistence, improved creature AI, and broader test coverage.

## Changes since report 1

- **High scores fully implemented** — `LoadHi`, `ViewHi`, and `NoteScore` are no longer stubs. Pascal-compatible `.HI` binary records (30 entries, 53 bytes each) persist between sessions. Player death triggers score entry and returns to the monitor.
- **Monitor menu complete** — Play, World, Restore, and High Scores commands all functional with scroll-based file pickers.
- **Centipede AI hardened** — Head-to-tail switching when stuck now works correctly. Non-unit direction values from child segments are handled without crashing.
- **Movement/input fixes** — Stale move queue entries are dropped when a direction key is held. Standby mode correctly moves the player off passage overlay cells.
- **Transporter display fix** — Dynamic character clamping handles non-unit direction values.
- **Crash fixes** — Several edge-case crashes resolved in creature update paths.
- **ZZT v3.2 world files added** — CAVES32, CITY32, DUNGEONS32, DEMO32, TOUR32, TOWN32 alongside existing v3.0 files.

## Current status

### Solid (95-100%)

- **File I/O** — .ZZT/.SAV/.HI codec with full round-trip fidelity.
- **Object behaviors** — All 25 creature/element types implemented with update and touch handlers.
- **Player mechanics** — Movement, shooting, item pickup, inventory, death flow.
- **High scores** — Persistence, viewing, and score entry integrated into game flow.
- **Constants/data structures** — Faithfully mirrored from `GLOB.PAS`.

### Functional (70-90%)

- **Game loop and rendering (90%)** — Working well; dark room rendering uses full-frame redraw instead of Pascal's incremental approach.
- **ZZT-OOP interpreter (75%)** — Core language works: flags, messages, movement, PUT/CHANGE/BECOME, IF/conditionals, interactive scroll dialogs with `!LABEL;text`. Parser edge cases and rare offset behavior remain.
- **Input handling (75%)** — Keyboard via Pygame with 8-move queue buffer and shift-modifiers. No joystick/mouse.
- **UI/Menus (70%)** — Monitor commands, scroll dialogs, file pickers all functional. Simplified prompts vs. DOS-era metadata.

### Not ported

- **Audio system** — `SOUNDU.PAS` (309 lines) has no equivalent. Runtime is silent.
- **Board editor** — `EDIT.PAS` (1,102 lines) not ported; runtime-only focus.
- **Config persistence** — `ZZT.CFG` and registered-copy behavior not implemented.
- **DOS-era specifics** — Monochrome mode, joystick, mouse, secret/debug commands.

## Code volume

~3,700 Python lines vs ~7,900 Pascal lines (47% ratio, up from 44%). The editor, audio, and DOS-specific I/O account for most of what's absent.

| Module | Lines | Role |
|---|---|---|
| engine.py | 2,036 | Core game loop, object updates, game state |
| oop.py | 696 | ZZT-OOP interpreter |
| world.py | 340 | .ZZT/.SAV/.HI codec |
| info.py | 284 | Object metadata and behavior tables |
| model.py | 134 | Data structures |
| constants.py | 128 | Game constants from `GLOB.PAS` |
| render.py | 50 | CP437 rendering with EGA colors |
| __main__.py | 29 | Entry point |

## Test coverage

24 tests across 3 files, all passing (0.25s):

- **test_world_codec.py** (2 tests) — .ZZT/.SAV round-trip, object data preservation.
- **test_oop_runner.py** (5 tests) — Flag operations, object targeting, PUT/CHANGE, BECOME, TAKE fallback.
- **test_parity_tranche.py** (17 tests) — Scroll modals, centipede AI, blink walls, duplicators, monitor commands (Play/World/Restore/High Scores), high score persistence, player death flow, passage handling, transporter display, movement queue, game tick processing.

New since report 1: 7 additional tests covering monitor commands, high scores, movement edge cases, and tick processing.

## Key areas for further parity work

1. **Audio system** — Largest remaining gap. Would require a Pygame sound synthesis approach for PC speaker emulation.
2. **OOP interpreter edge cases** — Parser error handling and rare offset behavior from `LANG.PAS`.
3. **Dark-room incremental redraw** — Currently full-frame; original uses incremental approach for performance.
4. **Bottom message lifecycle** — Simplified timer vs. original object slot semantics.
5. **Conveyor/transporter interaction edge cases** — Rare chain/overflow scenarios.
