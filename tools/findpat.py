"""Find 'lwz rA, OFF1(rB)' followed within N instructions by a load 'OFF2(rA)'.
usage: uv run tools/findpat.py work/text.asm 0x8c 6 [window]"""
import re
import sys

off1, off2 = int(sys.argv[2], 0), int(sys.argv[3], 0)
win = int(sys.argv[4]) if len(sys.argv) > 4 else 8
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
pat1 = re.compile(r"lwz\s+(r\d+), (-?0x[0-9a-f]+|\d+)\((r\d+)\)")
for i, ln in enumerate(lines):
    m = pat1.search(ln)
    if not m or int(m.group(2), 0) != off1:
        continue
    ra = m.group(1)
    for j in range(i + 1, min(i + 1 + win, len(lines))):
        l2 = lines[j]
        m2 = re.search(r"\s(l\w+)\s+(\w+), (-?0x[0-9a-f]+|\d+)\(" + ra + r"\)", l2)
        if m2 and int(m2.group(3), 0) == off2:
            print(ln)
            print(l2)
            print()
            break
        # register overwritten
        if re.search(r"\s\w+\s+" + ra + r",", l2) and not re.match(r".*\s(st|cmp)", l2):
            break
