"""Dump an annotated disassembly of the RPX .text section to a text file.

Annotations:
  * resolves lis/addi|ori|load|store pairs into absolute addresses (and the string there, if any)
  * resolves branch targets into symbol names (imports) where known

usage: uv run tools/disasm.py <Gambit.rpx> <out.asm>
"""
import re
import struct
import sys

from capstone import CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN, Cs

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from rpx import RPX  # noqa: E402

rpx = RPX(sys.argv[1])
out = open(sys.argv[2], "w", encoding="utf-8")

names = {}
for nm, val, size, info, sec in rpx.symbols():
    if nm and val:
        names.setdefault(val, nm)


def string_at(addr):
    s = rpx.section_at(addr)
    if not s or s.name not in (".rodata", ".data"):
        return None
    d = s.data[addr - s.addr: addr - s.addr + 80]
    m = re.match(rb"[\x20-\x7e]{3,}", d)
    if m and (len(m.group()) == len(d) or d[len(m.group())] == 0):
        return m.group().decode()
    return None


md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
md.skipdata = True
text = rpx.sections[2]
base = text.addr
data = text.data
hi = {}  # reg -> (value, addr set)
reg_re = re.compile(r"r(\d+)")

for insn in md.disasm(data, base):
    m, ops = insn.mnemonic, insn.op_str
    note = ""
    tgt_m = re.match(r"^(?:b|bl|ba|bla|b\w*)\s.*?0x([0-9a-f]+)$", f"{m} {ops}")
    if m.startswith("b") and tgt_m:
        t = int(tgt_m.group(1), 16)
        if t in names:
            note = names[t]
    parts = [p.strip() for p in ops.split(",")]
    if m == "lis" and len(parts) == 2:
        try:
            hi[parts[0]] = (int(parts[1], 0) & 0xFFFF) << 16
        except ValueError:
            pass
    elif m in ("addi", "ori", "addic") and len(parts) == 3 and parts[1] in hi:
        imm = int(parts[2], 0)
        v = hi[parts[1]] + (imm if m != "ori" else imm & 0xFFFF)
        v &= 0xFFFFFFFF
        note = f"=0x{v:08x}"
        s = string_at(v)
        if s:
            note += f' "{s}"'
        if parts[0] != parts[1]:
            pass
        hi.pop(parts[0], None)
    elif len(parts) == 2 and "(" in parts[1] and m[0] in "ls" and m not in ("lis",):
        mm = re.match(r"(-?0x[0-9a-f]+|-?\d+)\((r\d+)\)", parts[1])
        if mm and mm.group(2) in hi:
            v = (hi[mm.group(2)] + int(mm.group(1), 0)) & 0xFFFFFFFF
            note = f"@0x{v:08x}"
            if parts[0] == mm.group(2):
                hi.pop(parts[0], None)
    elif m not in ("lis",) and parts and parts[0] in hi and not m.startswith(("st", "cmp", "b", "mt")):
        hi.pop(parts[0], None)
    if m in ("blr", "bctr") or (m == "b"):
        hi.clear()
    raw = struct.unpack(">I", insn.bytes)[0] if len(insn.bytes) == 4 else 0
    out.write(f"{insn.address:08x}: {raw:08x}  {m:8} {ops}{('   ; ' + note) if note else ''}\n")
out.close()
