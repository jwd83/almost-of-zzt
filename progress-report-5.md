# Progress Report 5

Overall completion: ~93%. The audio system — previously the largest unported unit — is now implemented with full priority-queue semantics and square-wave synthesis via Pygame mixer. All 49 tests pass.

## Changes since report 4

- **Sound engine** — New `sound.py` (401 lines) porting `SOUNDU.PAS`. Implements `SoundEngine` with Pascal-faithful priority queue, 55 ms timer tick model, 12-tone note table, MML-style music parser (for `#PLAY`), digit-based sound effects (0-9 with randomized formula tables), and square-wave synthesis through Pygame mixer. Includes a `_NullSpeaker` fallback for headless/test contexts and a `_PygameSpeaker` backend with tone and digit caching.
- **35+ SFX constants** — All game sound effects transcribed as byte sequences matching the Pascal originals: player (shoot, hurt, die, re-enter), items (key get/already, ammo, gem, torch get/out, door open/locked), elements (push, bomb arm/tick/detonate, energizer/warn, passage, transporter), creatures (bullet ricochet, zap bullet/enemy, shot hit, slime touch), and misc (water block, invisible wall, brush, scroll touch, duplicator ok/fail, pusher, secret command, time limit warning).
- **Engine SFX wiring** — `sound_add`, `sound_music`, `sound_stop`, and `_service_sound` methods on `GameEngine` hook ~30 gameplay events to their corresponding SFX sequences. Energizer warning now fires at `ener_time == 10`, matching Pascal.
- **OOP sound integration** — `#PLAY` command parses the music spec string and queues the resulting byte sequence. `#SHOOT` plays `SFX_OOP_SHOOT` on successful fire. Unknown command error halt plays `SFX_OOP_ERROR`.
- **Sound servicing in UI loops** — New `_ui_wait` method replaces bare `clock.tick(30)` calls in scroll viewer, script editor, and all input dialogs, ensuring sound ticks are processed during blocking UI.
- **Lifecycle management** — `pygame.mixer.pre_init()` before `pygame.init()`, `bind_pygame()` after initialization, `shutdown()` on exit. `B` key toggle now propagates to the sound engine and stops playback.
- **gaps.md updated** — Audio entry changed from "not implemented; runtime is silent" to "implemented with approximated timbre." OOP gap description updated to remove sound side-effects from remaining gaps.

## Coverage: Pascal source vs Python port

Total Pascal source: **7,874 lines** across 11 units.
Total Python source: **5,142 lines** across 11 modules (65% line ratio).

| Pascal Unit | Lines | Python Module | Lines | Coverage |
|---|---|---|---|---|
| GLOB.PAS | 393 | constants.py | 128 | Complete |
| OBJ.PAS | 2,014 | engine.py (partial) | — | ~95% — all 25 element types, update + touch handlers |
| LANG.PAS | 882 | oop.py | 747 | ~92% — core language + #SEND/#BIND/#TRY/error halts + #PLAY music; remaining gaps are parser tokenization minutiae |
| MAIN.PAS | 1,821 | engine.py (partial) | — | ~92% — game loop, state management, quit flow, secret commands, standby, SFX calls; dark-room incremental redraw and bottom message lifecycle simplified |
| SCROLLS.PAS | 601 | engine.py (partial) | — | ~85% — scroll dialogs, file pickers, input prompts all functional; simplified vs DOS-era metadata |
| EDIT.PAS | 1,102 | editor.py | 354 | ~75% — board editor, script editor, category pickers, object modification; some editor-only element paths and polish deferred |
| GAMECTRL.PAS | 351 | engine.py (implicit) | — | ~80% — keyboard input with 8-move queue buffer and shift-modifiers; no joystick/mouse |
| FASTWR.PAS | 120 | render.py | 50 | Complete (reimplemented via Pygame) |
| KEYBOARD.PAS | 31 | (implicit in Pygame) | — | Complete (reimplemented) |
| SOUNDU.PAS | 309 | sound.py | 401 | ~95% — priority queue, note table, music parser, timer model, square-wave synthesis; PC speaker timbre approximated |
| ZZTS.PAS | 250 | \_\_main\_\_.py | 29 | ~60% — entry point and monitor flow; no config persistence or registered-copy behavior |

Combined engine.py is 2,605 lines, covering parts of OBJ.PAS, MAIN.PAS, SCROLLS.PAS, and GAMECTRL.PAS.

### Weighted coverage estimate

Excluding DOS-only paths (monochrome, joystick, config file):

- **Ported scope**: ~7,500 of 7,874 Pascal lines are in scope
- **Estimated behavioral coverage**: ~93% of in-scope functionality is implemented
- **Tested behavioral coverage**: 49 tests verify gameplay, OOP interpreter, editor, codec, sound system, and original-world smoke runs

## Test suite

**49 tests** across 5 files, all passing (0.61s):

| Test file | Tests | Lines | Focus |
|---|---|---|---|
| test_world_codec.py | 2 | 42 | .ZZT/.SAV round-trip fidelity |
| test_oop_runner.py | 11 | 130 | OOP interpreter: flags, targeting, PUT/CHANGE, BECOME, TAKE, #SEND, #BIND, #TRY, error halt, label matching |
| test_parity_tranche.py | 21 | 447 | Scroll modals, creature AI, blink walls, duplicators, monitor commands, high scores, player death, passages, transporters, pushers, conveyors, movement queue, game ticks, original-world smoke tests |
| test_finish_plan.py | 11 | 222 | RNDP, BOMBED dispatch, quit flow, secret commands, editor plot/fill, object modification, script editor keys, monitor editor entry, save/reload round-trip, 256-step smoke on all reference worlds |
| test_sound_system.py | 4 | 63 | Music parser shape, priority/append semantics, timer tick progression, OOP #PLAY integration |

New since report 4: 4 tests in `test_sound_system.py` covering the sound engine and its OOP integration.

## Code volume

| Module | Lines | Role |
|---|---|---|
| engine.py | 2,605 | Core game loop, object updates, game state, input, UI, SFX wiring |
| oop.py | 747 | ZZT-OOP interpreter |
| sound.py | 401 | Sound engine — priority queue, synthesis, music parser |
| editor.py | 354 | Board editor and script editor |
| info.py | 353 | Object metadata and behavior tables |
| world.py | 340 | .ZZT/.SAV/.HI codec |
| model.py | 134 | Data structures |
| constants.py | 128 | Game constants from GLOB.PAS |
| render.py | 50 | CP437 rendering with EGA colors |
| \_\_main\_\_.py | 29 | Entry point |
| **Total** | **5,142** | |

## Still deferred

1. **Config persistence** — `ZZT.CFG` and registered-copy behavior.
2. **DOS-era specifics** — Monochrome mode, joystick, mouse.
3. **.BRD import/export** — Compatibility path for standalone board files.
4. **Editor polish** — Some editor-only element paths and category edge cases.
5. **Dark-room incremental redraw** — Currently full-frame; original uses incremental approach.
