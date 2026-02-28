# Progress Report 3

Overall completion: ~80-85%. The OOP interpreter now handles several important Pascal-faithful behaviors, transporter/conveyor mechanics are more accurate, and smoke tests validate original world files tick without crashing.

## Changes since report 2

- **OOP `#SEND` self-jump** — Sending a message to a label within the same object now jumps to that label without executing intervening lines, matching Pascal's `NewLineF=false` offset behavior.
- **OOP `#BIND` implemented** — Objects can rebind their script to another named object's program. The bound object shares the same `inside` bytes, offset resets to 0, and execution continues from the new script immediately.
- **OOP `#TRY` inline fallback** — When `#TRY` movement is blocked, the rest of the line is now executed as a fallback command (Pascal's `goto GetCmd` path), instead of silently failing.
- **OOP shared-script `#ZAP`/`#RESTORE` mutation** — `#ZAP` and `#RESTORE` now propagate byte mutations to all objects sharing the same `inside` reference (via `#BIND` aliasing), matching Pascal's pointer-shared mutation semantics.
- **OOP unknown command error halt** — Bare unknown commands now set `offset = -1` (halting the object) and display `ERR: Bad command ...` in the bottom message, matching Pascal behavior. Only `TARGET:LABEL` messages are sent silently.
- **OOP `LSeek` digit boundary fix** — Label matching no longer treats digit characters as word continuations, so `#SEND TARGET1` correctly matches `:TARGET12` (Pascal treats digits as non-blocking boundaries).
- **Transporter source cell fix** — `touch_xporter` now correctly uses the transporter object's coordinates (not the player's) as the scan origin, and `move_to` pulls from the cell adjacent to the transporter rather than the player's old position, matching Pascal's `with` block semantics.
- **Conveyor rotation bookkeeping** — Clockwise/counter-clockwise conveyor rotation now preserves the source board cell across `move_obj` side effects, preventing tile corruption when objects are rotated around the conveyor.
- **Smoke tests on original worlds** — TOUR30, TOWN30, TIMMY30, and DEMO30 .ZZT files are loaded and ticked for 64 game steps each without crashing.

## Current status

### Solid (95-100%)

- **File I/O** — .ZZT/.SAV/.HI codec with full round-trip fidelity.
- **Object behaviors** — All 25 creature/element types implemented with update and touch handlers.
- **Player mechanics** — Movement, shooting, item pickup, inventory, death flow.
- **High scores** — Persistence, viewing, and score entry integrated into game flow.
- **Constants/data structures** — Faithfully mirrored from `GLOB.PAS`.

### Functional (75-90%)

- **Game loop and rendering (90%)** — Working well; dark room rendering uses full-frame redraw instead of Pascal's incremental approach.
- **ZZT-OOP interpreter (85%)** — Core language plus `#SEND` self-jumps, `#BIND`, `#TRY` fallback, shared-script mutation, and error halts. Remaining gaps are mostly parser tokenization minutiae and UI/sound side-effects from `LANG.PAS`.
- **Input handling (75%)** — Keyboard via Pygame with 8-move queue buffer and shift-modifiers. No joystick/mouse.
- **UI/Menus (70%)** — Monitor commands, scroll dialogs, file pickers all functional. Simplified prompts vs. DOS-era metadata.

### Not ported

- **Audio system** — `SOUNDU.PAS` (309 lines) has no equivalent. Runtime is silent.
- **Board editor** — `EDIT.PAS` (1,102 lines) not ported; runtime-only focus.
- **Config persistence** — `ZZT.CFG` and registered-copy behavior not implemented.
- **DOS-era specifics** — Monochrome mode, joystick, mouse, secret/debug commands.

## Code volume

~3,750 Python lines vs ~7,900 Pascal lines (47% ratio). The editor, audio, and DOS-specific I/O account for most of what's absent.

| Module | Lines | Role |
|---|---|---|
| engine.py | 2,044 | Core game loop, object updates, game state |
| oop.py | 741 | ZZT-OOP interpreter |
| world.py | 340 | .ZZT/.SAV/.HI codec |
| info.py | 284 | Object metadata and behavior tables |
| model.py | 134 | Data structures |
| constants.py | 128 | Game constants from `GLOB.PAS` |
| render.py | 50 | CP437 rendering with EGA colors |
| __main__.py | 29 | Entry point |

## Test coverage

34 tests across 3 files, all passing (0.40s):

- **test_world_codec.py** (2 tests) — .ZZT/.SAV round-trip, object data preservation.
- **test_oop_runner.py** (11 tests) — Flag operations, object targeting, PUT/CHANGE, BECOME, TAKE fallback, `#SEND` self-jump, unknown command error halt, `#BIND` script replacement, `#BIND` alias `#ZAP` propagation, `#TRY` inline fallback, `LSeek` digit boundary matching.
- **test_parity_tranche.py** (21 tests) — Scroll modals, centipede AI, blink walls, duplicators, monitor commands, high scores, player death flow, passage handling, transporter source cell, pusher-through-transporter, conveyor-rotated pusher, transporter display, movement queue, game tick processing, smoke test of 4 original world files.

New since report 2: 10 additional tests covering OOP interpreter behaviors (`#SEND`, `#BIND`, `#TRY`, error halt, label matching) and engine mechanics (transporter, pusher, conveyor, original world smoke tests).

## Key areas for further parity work

1. **Audio system** — Largest remaining gap. Would require a Pygame sound synthesis approach for PC speaker emulation.
2. **OOP interpreter edge cases** — Parser tokenization minutiae, `#CHAR`, `#THROWSTAR`, and any remaining offset corner cases from `LANG.PAS`.
3. **Dark-room incremental redraw** — Currently full-frame; original uses incremental approach for performance.
4. **Bottom message lifecycle** — Simplified timer vs. original object slot semantics.
5. **Broader smoke testing** — Extend world smoke tests to v3.2 files and deeper tick counts to surface remaining edge cases.
