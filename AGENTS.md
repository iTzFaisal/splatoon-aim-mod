# AGENTS.md

Cemu graphic-pack code patch for Splatoon (Wii U) plus Python RE helpers. No build, tests, lint or CI exist.

## The mod (`graphicPacks/Splatoon_StickAim/`)
- `patches.txt` is the actual patch; `rules.txt` is metadata. Patches only apply when `moduleMatches` equals the Cemu checksum of `Gambit.rpx` (v272 = `0xF7A78809`). Addresses are v272-only; porting to another build needs that RPX and a new `[..._vNNN]` section.
- After changing the pack: bump `version` in `rules.txt`, and rebuild `Splatoon_StickAim.zip` (root, committed). The zip must contain the folder `Splatoon_StickAim/` with both files (Android install path depends on it). Keep the README "How it works" / compatibility table in sync with `patches.txt` comments.
- Verify in Cemu via `log.txt`: `Applying patch group 'Splatoon_StickAim_v272'`.

## Tools (`tools/`, Python via uv, only dep is capstone)
- Run as `uv run python tools/<script>.py ...`. Scripts are argv-based, no argparse; usage is in each docstring.
- `rpx.py <Gambit.rpx>` prints the Cemu module checksum + sections. `disasm.py <rpx> <out.asm>` writes annotated `.text` disassembly (conventionally `work/text.asm`), which `findpat.py` greps.
- Live debugging: start Cemu with `--enable-gdbstub` (port 1337), run `tools/gdbd.py` in the background (holds the connection, serves on 127.0.0.1:1338), then send Python snippets with `tools/gdbc.py "<code>"`. Snippets get `g` (GDB client, see `gdb.py`) and `S` (persistent dict). Only one GDB connection at a time — don't connect `gdb.py` directly while `gdbd` runs.
- `keys.py <hwnd> KEY:secs ...` posts key presses to the Cemu window without focus (Windows-only, ctypes).

## Local-only, gitignored (never commit)
- `Splatoon [AGMP01]/` — the user's game dump (EUR v272 loadiine; RPX at `code/Gambit.rpx`). Copyrighted; never add to git or the zip.
- `work/` — scratch: portable Cemu at `work/cemu_test/Cemu.exe`, gdbd snippets (`snap.py`, `hunt.py`, ...), screenshot/input scripts (`shot.sh`, `to_balloon.sh` read `PID WID` from `/tmp/cemuwin` and use `cua-driver`).
