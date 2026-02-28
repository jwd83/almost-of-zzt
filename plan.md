# Remaining Porting Work: Pascal to Python ZZT Translation

## Context

The Python port is ~80-85% complete (3,750 lines vs 7,900 Pascal). Core gameplay, file I/O, 25 object behaviors, and the OOP interpreter are working, with 34 passing tests. The user wants to focus on **gameplay correctness** and also port the **board editor**. This plan identifies every remaining gap, organized into four phases.

---

## Phase 1: Gameplay Correctness

### 1.1 Fix RNDP direction bug (confirmed)
- **File**: `src/almost_of_zzt/oop.py:226-229`
- **Bug**: `RNDP` returns `(-dx, dy)` or `(dx, -dy)` which flips on the same axis. Pascal swaps params `(Dy,Dx)` in recursive call then negates one, producing **perpendicular** directions.
- **Fix**: Change to `(-dy, dx)` / `(dy, -dx)` (randomly CW or CCW)
- **Ref**: `ref/GAME/LANG.PAS:141-148`
- **Size**: Small. Add unit tests for all direction modifiers.

### 1.2 Add BOMBED message to `do_area`
- **File**: `src/almost_of_zzt/engine.py:690-697`
- **Gap**: When `code==1` (bomb blast), Pascal checks `Info[Kind].MsgScroll<>''` and sends `BOMBED` to programmable objects in the blast radius. Python skips this.
- **Fix**: Before the killable/zap check, find PROG objects in range and call `self.oop.lsend_msg(-obj_idx, "BOMBED", False)`
- **Ref**: `ref/GAME/OBJ.PAS:1244-1248`
- **Size**: Small

### 1.3 Implement input dialog functions
- **File**: `src/almost_of_zzt/engine.py` (new methods on `GameEngine`)
- **Gap**: Pascal has `InYN`, `InString`, `InNum`, `InChar`, `InChoice`, `InDir`, `InFancy` for interactive prompts. Only `_prompt_high_score_name()` exists. These are needed for quit confirm, secret commands, editor, and game settings.
- **Add**: `in_yn(prompt, default) -> bool`, `in_string(x, y, max_len) -> str|None`, `in_num(x, y, prompt, val) -> int`, `in_char(x, y, prompt, val) -> int`, `in_choice(y, prompt, choices, val) -> int`, `in_dir(y, prompt) -> (int,int)`, `in_fancy(prompt) -> str`
- **Ref**: `ref/GAME/MAIN.PAS:441-652`
- **Size**: Large (most effort in this phase). Unblocks 1.4, 1.5, and all of Phase 3.

### 1.4 Implement `AskQuitGame` and fix quit/death flow
- **File**: `src/almost_of_zzt/engine.py` (`upd_player` at line ~1473)
- **Gap**: Escape during gameplay immediately sets `exit_program=True`. Pascal shows Y/N confirm (or returns to monitor immediately if player is dead).
- **Fix**: Add `ask_quit_game()` using `in_yn()`. When dead, skip confirm. Return to monitor mode instead of exiting.
- **Ref**: `ref/GAME/OBJ.PAS:1268-1280`, `ref/GAME/MAIN.PAS:1678-1688`
- **Size**: Medium. Depends on 1.3.

### 1.5 Implement `SecretCmd` debug/cheat system
- **File**: `src/almost_of_zzt/engine.py` (monitor key handler at line ~419)
- **Gap**: `|` key in monitor is stubbed. Pascal accepts `+FLAG`/`-FLAG` to set/clear flags, then if DEBUG flag is active: health, ammo, keys, torches, time, gems, dark, zap cheats.
- **Ref**: `ref/GAME/MAIN.PAS:1446-1491`
- **Size**: Medium. Depends on 1.3 (`in_string`).

### 1.6 Implement `NewGame` state reset
- **File**: `src/almost_of_zzt/engine.py`
- **Gap**: No `new_game()` method to fully reset engine state. Needed for monitor P (play) command and editor N (new world).
- **Fix**: Add `new_game()` that resets world via `make_new_world()`, reinitializes info tables, resets counter/obj_num/standby/etc., enters monitor mode on room 0.
- **Ref**: `ref/GAME/MAIN.PAS:685-693, 323-359`
- **Size**: Small

### 1.7 Implement `PDrawBoard` progressive drawing effect
- **File**: `src/almost_of_zzt/engine.py`
- **Gap**: Room transitions should fill cells in random order (the distinctive ZZT "splotch" effect) before drawing the actual board.
- **Ref**: `ref/GAME/MAIN.PAS:99-118, 1383-1387`
- **Size**: Small

### 1.8 Implement player standby blink animation
- **File**: `src/almost_of_zzt/engine.py` (standby handling at line ~1982)
- **Gap**: During standby, Pascal blinks the player character on/off at ~250ms and shows "Pausing..." text. Python has no blink.
- **Ref**: `ref/GAME/MAIN.PAS:1611-1647`
- **Size**: Small

---

## Phase 2: Sound System

### 2.1 Create `sound.py` with `Music()` parser
- **New file**: `src/almost_of_zzt/sound.py`
- **Port**: `Music()` function - parses ZZT music notation (T/S/I/Q/H/W durations, A-G notes with #/! accidentals, +/- octave, X rests, 0-9 digit sounds, `.` dotted, `3` triplet) into binary note data.
- **Ref**: `ref/GAME/SOUNDU.PAS:224-289`
- **Size**: Medium

### 2.2 Implement note frequency table and digit sound effects
- **File**: `src/almost_of_zzt/sound.py`
- **Port**: `InitNoteTable()` (15 octaves x 12 notes, equal temperament from root=32Hz) and `InitDigits()` (10 special sound effects: click, bwoop, oscillator patterns, snare, kicks).
- **Ref**: `ref/GAME/SOUNDU.PAS:76-123`
- **Size**: Medium

### 2.3 Implement `SoundEngine` class with priority queue and pygame audio
- **File**: `src/almost_of_zzt/sound.py`
- **Port**: `SoundAdd()` (priority-based queue), `SoundStop()`, `TimerInt()` interrupt logic (note playback state machine). Use `pygame.mixer` to generate square wave tones.
- **Ref**: `ref/GAME/SOUNDU.PAS:46-74, 183-217`
- **Size**: Large. Depends on 2.1, 2.2.

### 2.4 Wire sound calls throughout engine and OOP
- **Files**: `src/almost_of_zzt/engine.py`, `src/almost_of_zzt/oop.py`
- **Port**: Add `self.sound.sound_add(priority, data)` calls to match every Pascal `SoundAdd` in touch/update handlers (key, ammo, gem, torch, door, bomb, bullet, energizer, push, scroll, shoot, passage, etc.), plus OOP `#PLAY` and `#THROWSTAR`.
- **Ref**: Every `SoundAdd` call in `ref/GAME/OBJ.PAS` and `ref/GAME/LANG.PAS`
- **Size**: Large (many call sites, each small). Depends on 2.3.

---

## Phase 3: Board Editor

### 3.1 Extend `InfoDef` with editor fields
- **File**: `src/almost_of_zzt/info.py`
- **Add**: `category`, `key_code`, `heading`, `msg_intel`, `msg_rate`, `msg_rate_h`, `msg_room`, `msg_dir`, `msg_scroll` fields to `InfoDef`. Create `init_info_edit()` that adds all editor metadata for every object type.
- **Ref**: `ref/GAME/OBJ.PAS:1478-1983`
- **Size**: Medium

### 3.2 Create `editor.py` module skeleton
- **New file**: `src/almost_of_zzt/editor.py`
- **Create**: `BoardEditor` class with state (cursor position, mode, current pattern/color, modification flag, defaults dict). Main `design_board()` entry point. Editor drawing (side panel, cursor blink).
- **Ref**: `ref/GAME/EDIT.PAS:1-67, 584-611`
- **Size**: Medium. Depends on 3.1.

### 3.3 Implement cursor movement and basic plot actions
- **File**: `src/almost_of_zzt/editor.py`
- **Port**: Arrow key movement, Space/plot, Tab/draw mode toggle, P/pattern cycle, C/color cycle, F4/text mode. `_plot_board(x,y)` using engine's board manipulation.
- **Ref**: `ref/GAME/EDIT.PAS:612-914`
- **Size**: Large

### 3.4 Implement F1/F2/F3 category menus (Item/Creature/Terrain placement)
- **File**: `src/almost_of_zzt/editor.py`
- **Port**: Display category items on side panel, wait for keycode match, place selected type with appropriate color/properties.
- **Ref**: `ref/GAME/EDIT.PAS:773-868`
- **Size**: Medium. Depends on 3.1, 3.3.

### 3.5 Implement `ModifyObj` property editor
- **File**: `src/almost_of_zzt/editor.py`
- **Port**: Show heading/description, prompt for each property based on msg_* fields (intelligence, character, rate, firing type, direction, room, OOP script).
- **Ref**: `ref/GAME/EDIT.PAS:386-496`
- **Size**: Large. Depends on 1.3 (input dialogs), 3.1.

### 3.6 Implement `EditScroll` (OOP script text editor)
- **File**: `src/almost_of_zzt/engine.py` (scroll system)
- **Port**: Cursor-based text editor within scroll overlay. Supports arrow keys, Enter (split line), Backspace (join/delete), Insert toggle, Delete, Ctrl-Y (delete line).
- **Ref**: `ref/GAME/SCROLLS.PAS:345-475`
- **Size**: Large

### 3.7 Implement board management (switch, add, clear, board info)
- **File**: `src/almost_of_zzt/editor.py`
- **Port**: B (switch board), I (board info dialog), Z (clear board), N (new world). `SetBoardInfo` edits title, can_shoot, is_dark, room links, re_enter, time_limit.
- **Ref**: `ref/GAME/EDIT.PAS:243-342, 729-764`
- **Size**: Medium. Depends on 1.3.

### 3.8 Implement editor Load/Save and paint-fill
- **File**: `src/almost_of_zzt/editor.py`
- **Port**: L (load world), S (save world), T (import/export .BRD), F (flood fill using BFS).
- **Ref**: `ref/GAME/EDIT.PAS:193-200, 555-582, 699-728`
- **Size**: Medium

### 3.9 Wire editor into main game loop
- **File**: `src/almost_of_zzt/engine.py` (monitor key handler)
- **Fix**: Replace `E` key stub with `BoardEditor(self).design_board()`. Reinitialize play info table and redraw on return.
- **Ref**: `ref/GAME/MAIN.PAS:1738-1744`
- **Size**: Small. Depends on all Phase 3 tasks.

---

## Phase 4: Polish

### 4.1 Implement `ViewDoc` and help file system
- **File**: `src/almost_of_zzt/engine.py`
- **Port**: `LoadScroll()` loads .HLP files from indexed binary help data or plain text. `ViewDoc()` shows in scroll viewer. Wire into A (About), H (Help) keys.
- **Ref**: `ref/GAME/SCROLLS.PAS:477-586`
- **Size**: Medium

### 4.2 Scroll open/close animations
- **File**: `src/almost_of_zzt/engine.py`
- **Port**: Smooth vertical expansion from center (OpenScroll) and collapse (CloseScroll) with frame delays.
- **Ref**: `ref/GAME/SCROLLS.PAS:105-136`
- **Size**: Medium

### 4.3 Config file persistence
- **File**: `src/almost_of_zzt/engine.py`
- **Port**: Save/load game speed and sound toggle to a config file.
- **Size**: Small

### 4.4 First-through logic
- **File**: `src/almost_of_zzt/engine.py`
- **Port**: On first launch, show About, load intro world if configured.
- **Ref**: `ref/GAME/MAIN.PAS:1578-1588`
- **Size**: Small. Depends on 4.1.

### 4.5 Extended smoke testing
- Add v3.2 world files to smoke tests, increase tick counts, test editor round-trips.
- **Size**: Medium

---

## Dependency Graph

```
Phase 1:  1.1, 1.2, 1.6, 1.7, 1.8 (independent)
          1.3 -> 1.4, 1.5

Phase 2:  2.1, 2.2 (independent) -> 2.3 -> 2.4

Phase 3:  3.1 -> 3.2 -> 3.3 -> 3.4
          1.3 + 3.1 -> 3.5
          3.6 (independent of editor, needs scroll system)
          1.3 + 3.2 -> 3.7, 3.8
          All -> 3.9

Phase 4:  All independent except 4.4 depends on 4.1
```

## Recommended execution order
1. 1.1 (RNDP bug), 1.2 (BOMBED), 1.6 (NewGame), 1.7 (PDrawBoard), 1.8 (standby blink)
2. 1.3 (input dialogs)
3. 1.4 (quit flow), 1.5 (secret cmd)
4. 2.1-2.4 (sound system)
5. 3.1-3.9 (editor)
6. 4.1-4.5 (polish)

## Estimated total new code: ~1,700-2,100 lines

## Verification
- Run `uv run pytest` after each task (34+ tests should keep passing)
- Add targeted unit tests for each fix (direction modifiers, BOMBED, input dialogs)
- Smoke test original .ZZT files: `uv run almost-of-zzt TOWN30.ZZT`
- Test editor by creating a small world, saving, reloading
- Test sound by playing a world with music/sound effects
