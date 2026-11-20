# Splatoon – Stick Aim (No Motion Controls)

A Cemu graphic pack (code patch) that makes Splatoon playable **without any motion/gyro input**.
The right stick controls the camera and aim on both axes (left/right and up/down), from the very
first tutorial onward.

## Why it's needed

Splatoon has an in-game *Motion Controls: Off* option, but it's only reachable **after** the
opening tutorial. The tutorial forces gyro aiming. Without a gyro the camera points at the floor
and the game blocks you with *"Face forward and slowly tilt the GamePad upward."*

This patch forces the game's own "motion controls off" mode everywhere, so:

- the tutorial no longer asks you to tilt the GamePad, and the camera stays level
- right stick ↑/↓ aims up and down, right stick ←/→ turns
- your save's motion setting is ignored while the pack is enabled (turn the pack off to get gyro back)
- use the in-game **Camera sensitivity** slider (Options, after the tutorial) to tune stick speed

## Compatibility

| Game build | Cemu module checksum | Status |
|---|---|---|
| v272 (2.12.0) – EUR / USA / JPN | `0xF7A78809` | ✅ tested on Cemu 2.6 (Windows) |
| v288 (2.12.1) | `0x659C782E` | ❌ not supported (code layout differs; needs that RPX to port) |
| older updates | – | ❌ not supported |

Cemu applies the patch only when the checksum matches, so it can't affect any other build.
Graphic-pack patches are applied by Cemu's shared core, so the same pack works on Cemu Android.

## Install

### Android (Cemu fork by SSimco)
1. Copy the `Splatoon_StickAim` folder (unzip `Splatoon_StickAim.zip`) into
   `/storage/emulated/0/Android/data/info.cemu.cemu/files/graphicPacks/`
   so you get `.../graphicPacks/Splatoon_StickAim/rules.txt`.
   The downloaded community packs sit next to it in `graphicPacks/downloadedGraphicPacks/`.
   On Android 11+ the `Android/data` folder is hidden from most file managers. Use a PC over USB,
   or a file manager that can open it (e.g. the system "Files" app or MiXplorer/Shizuku).
2. Open Cemu → Graphic packs → Splatoon → Mods → **Stick Aim (No Motion Controls)** → enable.
3. Start the game.

### Windows
1. Copy `graphicPacks/Splatoon_StickAim` into `<Cemu folder>/graphicPacks/`
   (`File → Open Cemu folder` in Cemu shows where that is).
2. Right-click Splatoon → *Edit graphic packs* → Splatoon → Mods → tick **Stick Aim (No Motion Controls)**.
3. Check `log.txt` for `Applying patch group 'Splatoon_StickAim_v272'`.

## Tutorial notes

- In the first step ("Shoot the balloons!") the game locks the player's input and expects gyro
  aiming. The patch lets the right stick aim there (left-stick movement stays locked, as intended).
- If you aim too far down, the tutorial shows *"Face forward and slowly tilt the GamePad upward"*.
  Push the right stick **up** and the hint goes away.

## How it works

The game asks one function whether the GamePad gyro should drive the camera:

```
bool Ctrl::isGyroEnabled(this)        // 0x02036DE8 (v272)
    return (this->mode == 0 || this->force) && this->options->EnableGyro;
```

`options` is the save data's `CtrlOption_*` block (`+0` CameraSpeed, `+4` ReverseUD, `+5` ReverseLR,
`+6` EnableGyro). The player camera (`0x0265E7EC`) switches to stick-only mode when this returns
false. That's the same path the in-game option uses. The patch replaces the function body with
`li r3, 0 / blr`.

The player's camera-stick routine (`0x02635254`) reads the right stick, but first checks
`isInputLocked` (`0x02634F48`, bit `0x40` of `player+0x54`) and zeroes the stick input when it's set.
The tutorial's balloon step sets that lock, because the gyro path ignores it. The patch replaces that call at
`0x02635284` with `li r3, 0`, so the stick works wherever the gyro would have.

## Repository layout

- `graphicPacks/Splatoon_StickAim/` – the mod (`rules.txt`, `patches.txt`)
- `tools/rpx.py` – RPX unpacker + Cemu module-checksum calculator
- `tools/disasm.py` – annotated PPC disassembly of `.text` (string/address cross-refs)
- `tools/findpat.py`, `tools/relocs.py` – small RE helpers
- `tools/keys.py` – posts held key presses to the Cemu window (used for automated testing)

`tools/` runs with `uv run python tools/<script>.py ...`. Game files are not included.
