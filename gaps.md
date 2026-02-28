# Gaps And Inferred Behavior

This file tracks behavior where the Python port currently differs from, or infers details beyond, the Pascal source.

## Implemented with inference

- Audio (`SoundAdd`, `SoundStop`, `Music`) is not implemented; runtime is silent.
- Monitor/menu command flow is now implemented for `Play` / `Restore` / `World` with scroll-based file pickers, but uses simplified prompts and no DOS-era metadata descriptions.
- High score flow (`LoadHi`/`ViewHi`/`NoteScore`) is implemented with Pascal-compatible `.HI` binary records, but name entry UI uses a simplified modern text prompt loop.
- Intro/help/document rendering is reduced to in-game status messages.
- Keyboard buffering and timing are approximated with Pygame key state/events.
- Monochrome/video mode and joystick/mouse control paths are not implemented.

## Known parity gaps

- ZZT-OOP interpreter now matches Pascal flow for `#SEND` self-offset jumps, `#TRY` inline fail-fallback commands, `#BIND` script rebinding, unknown bare-command error halts, and shared-script `#ZAP`/`#RESTORE` mutation on bound objects (including `LSeek` digit-boundary quirks). Remaining gaps are mostly parser tokenization/error minutiae and UI/sound side-effects from `LANG.PAS`.
- Blink wall, centipede, duplicator, and conveyor/transporter push+pusher edge-control flow now follow Pascal control flow more closely; remaining parity gaps are mostly in rare chain/overflow edge-cases and parser/UI differences.
- Dark-room redraw behavior is approximated by full-frame redraw, not Pascal incremental redraw.
- Bottom message lifecycle uses a simplified timer, not special object slot semantics.
- Save/load uses Pascal field layout and room compression but does not preserve raw pointer bytes meaningfully.
- `About`, board editor (`E`), and secret monitor command (`|`) are currently status-message stubs.
- Registered-copy and configuration file (`ZZT.CFG`) behavior is not implemented.
- Several editor-only and secret/debug command branches are omitted.

## Source omissions in `ref/GAME`

- Copyright-removed text blocks in `ZZTS.PAS` and `MAIN.PAS` were replaced with minimal neutral output.
