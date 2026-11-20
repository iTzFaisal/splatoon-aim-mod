"""List .rela.text relocations that reference named symbols matching a regex.
usage: uv run tools/relocs.py <rpx> <regex>"""
import re, struct, sys
sys.path.insert(0, __file__.replace("\\", "/").rsplit("/", 1)[0])
from rpx import RPX
r = RPX(sys.argv[1])
symtab = [s for s in r.sections if s.type == 2][0]
strtab = r.sections[symtab.link].data
syms = []
for o in range(0, len(symtab.data), 16):
    name, value, size, info, other, shndx = struct.unpack_from(">IIIBBH", symtab.data, o)
    syms.append(strtab[name:strtab.index(b"\0", name)].decode("latin1"))
for s in r.sections:
    if s.type != 4 or s.name != ".rela.text":
        continue
    for o in range(0, len(s.data), 12):
        off, info, add = struct.unpack_from(">IIi", s.data, o)
        nm = syms[info >> 8]
        if re.search(sys.argv[2], nm):
            print(f"{off:08x} type={info & 0xff} {nm}")
