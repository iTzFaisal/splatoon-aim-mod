"""Minimal RPX/RPL reader: decompresses sections, computes Cemu's patch module checksum,
and exposes symbols / imports / memory reads for reverse engineering.

usage: uv run tools/rpx.py <Gambit.rpx>
"""
import struct
import sys
import zlib

SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_NOBITS = 8
SHT_RPL_EXPORTS = 0x80000001
SHT_RPL_IMPORTS = 0x80000002
SHT_RPL_CRCS = 0x80000003
SHT_RPL_FILEINFO = 0x80000004
SHF_RPL_COMPRESSED = 0x08000000


class Section:
    pass


class RPX:
    def __init__(self, path):
        self.raw = open(path, "rb").read()
        r = self.raw
        assert r[:4] == b"\x7fELF"
        (self.shoff,) = struct.unpack_from(">I", r, 0x20)
        self.shentsize, self.shnum, self.shstrndx = struct.unpack_from(">HHH", r, 0x2E)
        self.sections = []
        for i in range(self.shnum):
            o = self.shoff + i * self.shentsize
            s = Section()
            (s.name_off, s.type, s.flags, s.addr, s.offset, s.size, s.link, s.info,
             s.addralign, s.entsize) = struct.unpack_from(">10I", r, o)
            s.index = i
            if s.type == SHT_NOBITS or s.offset == 0:
                s.data = b"" if s.type != SHT_NOBITS else None
                s.raw_size = s.size
            elif s.flags & SHF_RPL_COMPRESSED:
                (dsize,) = struct.unpack_from(">I", r, s.offset)
                s.data = zlib.decompress(r[s.offset + 4: s.offset + s.size])
                assert len(s.data) == dsize
                s.raw_size = dsize
            else:
                s.data = r[s.offset: s.offset + s.size]
                s.raw_size = s.size
            self.sections.append(s)
        shstr = self.sections[self.shstrndx].data
        for s in self.sections:
            s.name = shstr[s.name_off: shstr.index(b"\0", s.name_off)].decode() if shstr else ""

    def cemu_checksum(self):
        symidx = -1
        stridx = -1
        for i, s in enumerate(self.sections):
            if s.type == SHT_SYMTAB:
                symidx = i
            if s.type == SHT_STRTAB and i != self.shstrndx and stridx == -1:
                stridx = i
        crc = zlib.crc32(b"\x7fRPX")
        for v in (len(self.sections), symidx, stridx, self.shstrndx):
            crc = zlib.crc32(struct.pack("<i", v), crc)
        for s in self.sections:
            for v in (s.name_off, s.type, s.flags, s.addr, s.raw_size, s.addralign):
                crc = zlib.crc32(struct.pack("<I", v), crc)
            if s.data:
                crc = zlib.crc32(s.data, crc)
        return crc & 0xFFFFFFFF

    def section_at(self, addr):
        for s in self.sections:
            if s.data and s.addr and s.addr <= addr < s.addr + len(s.data):
                return s
        return None

    def read(self, addr, n):
        s = self.section_at(addr)
        o = addr - s.addr
        return s.data[o:o + n]

    def u32(self, addr):
        return struct.unpack(">I", self.read(addr, 4))[0]

    def apply_data_relocs(self):
        """Apply R_PPC_ADDR32 relocations to .rodata/.data so vtables and pointer tables resolve."""
        symtab = [s for s in self.sections if s.type == SHT_SYMTAB][0]
        vals = [struct.unpack_from(">I", symtab.data, o + 4)[0] for o in range(0, len(symtab.data), 16)]
        for rs in self.sections:
            if rs.type != 4 or rs.name not in (".rela.rodata", ".rela.data"):
                continue
            tgt = self.sections[rs.info]
            buf = bytearray(tgt.data)
            for o in range(0, len(rs.data), 12):
                off, info, add = struct.unpack_from(">IIi", rs.data, o)
                if info & 0xFF == 1:  # R_PPC_ADDR32
                    struct.pack_into(">I", buf, off - tgt.addr, (vals[info >> 8] + add) & 0xFFFFFFFF)
            tgt.data = bytes(buf)

    def symbols(self):
        """yield (name, value, size, info, section_name)"""
        for s in self.sections:
            if s.type != SHT_SYMTAB:
                continue
            strtab = self.sections[s.link].data
            for o in range(0, len(s.data), 16):
                name, value, size, info, other, shndx = struct.unpack_from(">IIIBBH", s.data, o)
                nm = strtab[name: strtab.index(b"\0", name)].decode("latin1")
                sec = self.sections[shndx].name if shndx < len(self.sections) else ""
                yield nm, value, size, info, sec


if __name__ == "__main__":
    rpx = RPX(sys.argv[1])
    print(f"cemu module checksum: 0x{rpx.cemu_checksum():08X}")
    for s in rpx.sections:
        print(f"{s.index:3} {s.name:24} type={s.type:08x} addr={s.addr:08x} size={s.raw_size:08x} flags={s.flags:08x}")
    syms = list(rpx.symbols())
    print("symbols:", len(syms))
