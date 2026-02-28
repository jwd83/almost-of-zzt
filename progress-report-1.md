# Porting Parity Report

Overall completion: ~70-75%. The core gameplay loop works and can play original .ZZT world files.

## What's solid

- **File I/O (100%)** — .ZZT/.SAV codec is fully compatible with round-trip fidelity.
- **Object behaviors (85%)** — All 25 creature/element types implemented with update and touch handlers.
- **Player mechanics (95%)** — Movement, shooting, item pickup, inventory all working.
- **Game loop and rendering (90%)** — Functional; dark room rendering simplified vs. original's incremental approach.
- **Constants/data structures** — Faithfully mirrored from `GLOB.PAS`.

## Partially ported

- **ZZT-OOP interpreter (75%)** — Core language works (flags, messages, movement, PUT/CHANGE, IF/conditionals). Some parser edge cases and rare chain/overflow scenarios remain (see `gaps.md`).
- **UI/Menus (60%)** — Play/Load/Save work; scroll dialogs functional but simplified. No DOS-era metadata descriptions.
- **Input handling (70%)** — Keyboard via Pygame; no joystick/mouse.

## Not yet ported

- **Audio system (0%)** — `SOUNDU.PAS` (309 lines) has no Python equivalent. Runtime is silent.
- **Board editor** — `EDIT.PAS` (1,102 lines) not ported. This is a runtime-only focus.
- **High scores / config persistence** — Stubs only. `LoadHi`, `ViewHi`, `NoteScore`, and `ZZT.CFG` behavior are unimplemented.
- **DOS-era specifics** — Video mode selection and CRT optimizations replaced by Pygame. Monochrome mode not supported.
- **Secret/debug commands** — Editor entry (`E`), secret monitor command (`|`), and several editor-only branches omitted.

## Pascal unit to Python module mapping

| Pascal Unit | Lines | Python Equivalent | Status |
|---|---|---|---|
| GLOB.PAS (Constants) | 393 | constants.py (126 lines) | Complete |
| OBJ.PAS (Object behaviors) | 2,014 | engine.py (partial) | Substantial |
| LANG.PAS (OOP interpreter) | 882 | oop.py (696 lines) | Partial |
| MAIN.PAS (Game core) | 1,821 | engine.py (partial) | Partial |
| SCROLLS.PAS (UI rendering) | 601 | engine.py + render.py | Simplified |
| SOUNDU.PAS (Audio) | 309 | Not implemented | Missing |
| EDIT.PAS (Editor/Hi-scores) | 1,102 | Minimal stubs | Missing |
| GAMECTRL.PAS (Input) | 351 | Implicit in engine.py | Partial |
| FASTWR.PAS (Screen writes) | 120 | render.py + Pygame | Reimplemented |
| KEYBOARD.PAS (Kbd status) | 31 | Implicit in Pygame | Reimplemented |
| ZZTS.PAS (Main program) | 250 | \_\_main\_\_.py (29 lines) | Minimal |

## Code volume

~3,500 Python lines vs ~7,900 Pascal lines (44% ratio). The editor, audio, and DOS-specific I/O account for most of what's absent.

## Test coverage

322 lines across 3 test files:

- **test_world_codec.py** — .ZZT/.SAV file round-trip, object data preservation, inventory/room serialization.
- **test_parity_tranche.py** — Scroll modal interaction, OOP label/flag operations, centipede head-to-tail switching, blink wall expansion/retraction, movement blocking, IF/conditional branches.
- **test_oop_runner.py** — Flag operations, object targeting/naming, PUT/CHANGE, movement and directional logic.

Not yet tested: audio, editor, high scores, full creature AI edge cases, rare object interaction chains.

## Key areas for further parity work

1. OOP interpreter edge cases (documented in `gaps.md`).
2. Audio system if sound is desired.
3. Dark-room incremental redraw (currently full-frame).
4. Bottom message lifecycle (simplified timer vs. original object slot semantics).
5. Conveyor/transporter interaction edge cases.
