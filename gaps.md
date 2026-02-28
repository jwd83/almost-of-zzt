# Gaps And Inferred Behavior

This file tracks behavior where the Python port currently differs from, or infers details beyond, the Pascal source.

## Implemented with inference

- Audio (`SoundAdd`, `SoundStop`, `Music`) is not implemented; runtime is silent.
- Menu/monitor/editor flows from Pascal are reduced to direct gameplay entry.
- Intro/help/document rendering is reduced to in-game status messages.
- Keyboard buffering and timing are approximated with Pygame key state/events.
- Monochrome/video mode and joystick/mouse control paths are not implemented.

## Known parity gaps

- ZZT-OOP interpreter is partial; many commands and edge cases are missing or simplified.
- Blink wall, centipede, duplicator, conveyor, and transporter interactions are implemented but not fully cycle-accurate.
- Dark-room redraw behavior is approximated by full-frame redraw, not Pascal incremental redraw.
- Bottom message lifecycle uses a simplified timer, not special object slot semantics.
- Save/load uses Pascal field layout and room compression but does not preserve raw pointer bytes meaningfully.
- High score handling (`LoadHi`, `ViewHi`, `NoteScore`) is not implemented.
- Registered-copy and configuration file (`ZZT.CFG`) behavior is not implemented.
- Several editor-only and secret/debug command branches are omitted.

## Source omissions in `ref/GAME`

- Copyright-removed text blocks in `ZZTS.PAS` and `MAIN.PAS` were replaced with minimal neutral output.
