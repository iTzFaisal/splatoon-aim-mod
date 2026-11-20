"""Send held key presses to the Cemu window via PostMessage (no focus steal).

usage: uv run tools/keys.py <hwnd> SEQ...
  SEQ items:  KEY:seconds   hold key (e.g. A:0.1, T:1.5)   KEY may be a letter/digit or up/down/left/right
              K1+K2:seconds hold several keys together
              wait:seconds  sleep
"""
import ctypes
import sys
import time

user32 = ctypes.windll.user32
WM_KEYDOWN, WM_KEYUP = 0x100, 0x101
NAMED = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "enter": 0x0D, "esc": 0x1B}


def vk(k):
    return NAMED.get(k.lower(), ord(k.upper()) if len(k) == 1 else None)


def post(hwnd, code, down):
    scan = user32.MapVirtualKeyW(code, 0)
    lp = 1 | (scan << 16)
    if not down:
        lp |= (1 << 30) | (1 << 31)
    user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, code, lp)


hwnd = int(sys.argv[1], 0)
for item in sys.argv[2:]:
    key, _, dur = item.partition(":")
    dur = float(dur or 0.1)
    if key == "wait":
        time.sleep(dur)
        continue
    codes = [vk(k) for k in key.split("+")]
    end = time.time() + dur
    while True:  # repeat keydown like real auto-repeat so focus changes don't drop it
        for c in codes:
            post(hwnd, c, True)
        if time.time() >= end:
            break
        time.sleep(0.03)
    for c in codes:
        post(hwnd, c, False)
    time.sleep(0.05)
