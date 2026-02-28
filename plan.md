# Finish Plan: Gameplay Correctness + Editor Core

## Scope for this cycle

Implemented in this pass:

1. Gameplay parity fixes from Phase 1:
- RNDP perpendicular direction fix
- BOMBED message dispatch in bomb blast area
- Input dialog APIs (`in_yn`, `in_string`, `in_num`, `in_char`, `in_choice`, `in_dir`, `in_fancy`)
- Quit confirmation flow (`ask_quit_game`) for play/standby
- Secret command system (`secret_cmd`) with flag toggles + DEBUG-gated cheats
- New game reset (`new_game`)
- Progressive board transition draw (`pdraw_board`)
- Standby blink + "Pausing..." panel behavior

2. Editor core:
- `InfoDef` editor metadata + `init_info_edit()`
- New `editor.py` with `BoardEditor.design_board()`
- Plot/draw/flood-fill editing operations
- Category pickers (`F1/F2/F3`)
- Object/property modification flow
- Board/world operations (switch, clear, board info, load, save, new world)
- Monitor `E` integration

3. Script editing:
- `edit_scroll` editor with cursor movement, insert toggle, split/join, delete, Ctrl+Y line delete, save/cancel

4. Test expansion:
- Added finish-plan tests for gameplay parity, secret commands, editor behavior, script editor key handling, monitor editor entry, save/reload, and extended smoke ticks.

## Acceptance status

- `uv run python -m pytest -q`: passing
- Current suite size: **45 passing tests**
- No additional dependencies added

## Deferred follow-up

Still intentionally deferred:

1. Audio system (`sound.py`, parser/synth, and call-site wiring)
2. Full DOS-era polish features in the old Phase 4 list
3. `.BRD` import/export compatibility path
