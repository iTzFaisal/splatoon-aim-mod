"""Nintendo Wii U file formats: Yaz0, SARC, MSBT (big-endian, as used by Splatoon).

Library module; also a CLI:
    uv run python tools/nin.py list   <file.szs|.sarc>
    uv run python tools/nin.py unpack <file.szs|.sarc> <outdir>
"""
import struct
import sys
from pathlib import Path


# ---------------------------------------------------------------- Yaz0

def yaz0_decompress(data: bytes) -> bytes:
    assert data[:4] == b"Yaz0", "not Yaz0"
    size = struct.unpack_from(">I", data, 4)[0]
    out = bytearray(size)
    src, dst = 16, 0
    n = len(data)
    while dst < size and src < n:
        code = data[src]; src += 1
        for bit in range(7, -1, -1):
            if dst >= size:
                break
            if code >> bit & 1:
                out[dst] = data[src]; dst += 1; src += 1
            else:
                b1, b2 = data[src], data[src + 1]; src += 2
                dist = ((b1 & 0xF) << 8 | b2) + 1
                cnt = b1 >> 4
                if cnt == 0:
                    cnt = data[src] + 0x12; src += 1
                else:
                    cnt += 2
                s = dst - dist
                for i in range(cnt):
                    out[dst + i] = out[s + i]
                dst += cnt
    return bytes(out)


def yaz0_compress(data: bytes, align: int = 0, level: int = 1) -> bytes:
    """Yaz0 compression with a hash-chain LZ matcher (good enough, not optimal)."""
    out = bytearray(b"Yaz0" + struct.pack(">II", len(data), align) + b"\0" * 4)
    n = len(data)
    pos = 0
    heads: dict[bytes, list[int]] = {}
    max_chain = 16 * level

    def find(p):
        if p + 3 > n:
            return 0, 0
        key = data[p:p + 3]
        cands = heads.get(key)
        best_len, best_dist = 0, 0
        if cands:
            maxlen = min(0x111, n - p)
            for c in reversed(cands[-max_chain:]):
                d = p - c
                if d > 0x1000:
                    break
                l = 3
                while l < maxlen and data[c + l] == data[p + l]:
                    l += 1
                if l > best_len:
                    best_len, best_dist = l, d
                    if l == maxlen:
                        break
        return best_len, best_dist

    def add(p):
        if p + 3 <= n:
            heads.setdefault(data[p:p + 3], []).append(p)

    while pos < n:
        code_pos = len(out); out.append(0)
        code = 0
        for bit in range(7, -1, -1):
            if pos >= n:
                break
            l, d = find(pos)
            if l >= 3:
                d -= 1
                if l >= 0x12:
                    out += bytes([d >> 8, d & 0xFF, l - 0x12])
                else:
                    out += bytes([(l - 2) << 4 | d >> 8, d & 0xFF])
                for i in range(l):
                    add(pos + i)
                pos += l
            else:
                code |= 1 << bit
                out.append(data[pos]); add(pos); pos += 1
        out[code_pos] = code
    return bytes(out)


def load(path) -> bytes:
    data = Path(path).read_bytes()
    return yaz0_decompress(data) if data[:4] == b"Yaz0" else data


# ---------------------------------------------------------------- SARC

def sarc_hash(name: str, mult: int) -> int:
    h = 0
    for ch in name.encode("utf-8"):
        h = (h * mult + (ch if ch < 0x80 else ch - 0x100)) & 0xFFFFFFFF
    return h


class Sarc:
    def __init__(self, data: bytes):
        assert data[:4] == b"SARC", "not SARC"
        hdr_len, bom = struct.unpack_from(">HH", data, 4)
        assert bom == 0xFEFF, "only big-endian supported"
        _, data_off, self.version = struct.unpack_from(">IIH", data, 8)
        assert data[0x14:0x18] == b"SFAT"
        _, count, self.mult = struct.unpack_from(">HHI", data, 0x18)
        nodes = []
        for i in range(count):
            h, attr, s, e = struct.unpack_from(">IIII", data, 0x20 + i * 16)
            nodes.append((h, attr, s, e))
        sfnt = 0x20 + count * 16
        assert data[sfnt:sfnt + 4] == b"SFNT"
        names_base = sfnt + 8
        self.files: dict[str, bytes] = {}
        self.align: dict[str, int] = {}
        for h, attr, s, e in nodes:
            if attr & 0x01000000:
                off = names_base + (attr & 0xFFFF) * 4
                name = data[off:data.index(b"\0", off)].decode("utf-8")
            else:
                name = f"{h:08X}.bin"
            self.files[name] = data[data_off + s:data_off + e]
            a = 1
            while a < 0x2000 and (data_off + s) % (a * 2) == 0:
                a *= 2
            self.align[name] = a
        self.data_align = 1
        while self.data_align < 0x2000 and data_off % (self.data_align * 2) == 0:
            self.data_align *= 2

    def build(self) -> bytes:
        names = sorted(self.files, key=lambda nm: sarc_hash(nm, self.mult))
        sfnt = bytearray()
        name_offs = {}
        for nm in names:
            name_offs[nm] = len(sfnt) // 4
            sfnt += nm.encode("utf-8") + b"\0"
            sfnt += b"\0" * (-len(sfnt) % 4)
        hdr_size = 0x20 + 16 * len(names) + 8 + len(sfnt)
        base_align = max([self.data_align] + [self.align.get(nm, 4) for nm in names])
        data_off = hdr_size + (-hdr_size % base_align)
        body = bytearray()
        nodes = bytearray()
        for nm in names:
            a = self.align.get(nm, 4)
            body += b"\0" * (-(data_off + len(body)) % a)
            s = len(body)
            body += self.files[nm]
            nodes += struct.pack(">IIII", sarc_hash(nm, self.mult),
                                 0x01000000 | name_offs[nm], s, len(body))
        out = bytearray(b"SARC" + struct.pack(">HHIIHH", 0x14, 0xFEFF, 0, data_off, self.version, 0))
        out += b"SFAT" + struct.pack(">HHI", 0xC, len(names), self.mult) + nodes
        out += b"SFNT" + struct.pack(">HH", 8, 0) + sfnt
        out += b"\0" * (data_off - len(out))
        out += body
        struct.pack_into(">I", out, 8, len(out))
        return bytes(out)


# ---------------------------------------------------------------- MSBT

def _pad16(b: bytearray, fill=b"\xab"):
    b += fill * (-len(b) % 16)


class Msbt:
    """Parses LBL1 + TXT2; every other section is kept raw for round-tripping."""

    def __init__(self, data: bytes):
        assert data[:8] == b"MsgStdBn", "not MSBT"
        assert data[8:10] == b"\xfe\xff", "only big-endian supported"
        self.header = bytearray(data[:0x20])
        self.encoding = data[0xC]
        assert self.encoding == 1, "only UTF-16 MSBT supported"
        nsec = struct.unpack_from(">H", data, 0xE)[0]
        self.sections: list[list] = []  # [magic, raw bytes]
        p = 0x20
        for _ in range(nsec):
            magic = data[p:p + 4].decode()
            size = struct.unpack_from(">I", data, p + 4)[0]
            self.sections.append([magic, data[p + 16:p + 16 + size]])
            p += 16 + size
            p += -p % 16
        self.labels: dict[int, str] = {}
        sec = dict((m, d) for m, d in self.sections)
        if "LBL1" in sec:
            self._parse_lbl(sec["LBL1"])
        self.texts = self._parse_txt(sec["TXT2"])

    def _parse_lbl(self, d):
        slots = struct.unpack_from(">I", d, 0)[0]
        for i in range(slots):
            cnt, off = struct.unpack_from(">II", d, 4 + i * 8)
            for _ in range(cnt):
                ln = d[off]
                name = d[off + 1:off + 1 + ln].decode("utf-8")
                idx = struct.unpack_from(">I", d, off + 1 + ln)[0]
                self.labels[idx] = name
                off += 1 + ln + 4

    @staticmethod
    def _parse_txt(d) -> list[list]:
        """Each message -> list of tokens: str (text) or tuple (group, type, params bytes)."""
        cnt = struct.unpack_from(">I", d, 0)[0]
        offs = [struct.unpack_from(">I", d, 4 + i * 4)[0] for i in range(cnt)] + [len(d)]
        msgs = []
        for i in range(cnt):
            p, end = offs[i], offs[i + 1]
            toks, buf = [], []
            while p < end:
                c = struct.unpack_from(">H", d, p)[0]; p += 2
                if c == 0:
                    break
                if c == 0x0E:
                    g, t, ps = struct.unpack_from(">HHH", d, p); p += 6
                    if buf:
                        toks.append("".join(buf)); buf = []
                    toks.append(("tag", g, t, bytes(d[p:p + ps]))); p += ps
                elif c == 0x0F:
                    g, t = struct.unpack_from(">HH", d, p); p += 4
                    if buf:
                        toks.append("".join(buf)); buf = []
                    toks.append(("end", g, t, b""))
                else:
                    buf.append(chr(c))
            if buf:
                toks.append("".join(buf))
            msgs.append(toks)
        return msgs

    @staticmethod
    def _build_txt(msgs) -> bytes:
        body = bytearray()
        offs = []
        base = 4 + 4 * len(msgs)
        for toks in msgs:
            offs.append(base + len(body))
            for t in toks:
                if isinstance(t, str):
                    body += t.encode("utf-16-be")
                elif t[0] == "tag":
                    body += struct.pack(">HHHH", 0x0E, t[1], t[2], len(t[3])) + t[3]
                else:
                    body += struct.pack(">HHH", 0x0F, t[1], t[2])
            body += b"\0\0"
        return struct.pack(">I", len(msgs)) + b"".join(struct.pack(">I", o) for o in offs) + body

    def build(self) -> bytes:
        out = bytearray(self.header)
        for magic, raw in self.sections:
            if magic == "TXT2":
                raw = self._build_txt(self.texts)
            out += magic.encode() + struct.pack(">I", len(raw)) + b"\0" * 8 + raw
            _pad16(out)
        struct.pack_into(">I", out, 0x12, len(out))
        return bytes(out)

    def items(self):
        """Yield (label, tokens) in message index order."""
        for i, toks in enumerate(self.texts):
            yield self.labels.get(i, f"#{i}"), toks


# Text <-> token string encoding for translators: control tags become
# {g:t:hexparams} and closing tags {/g:t}. Literal braces are escaped as {{ }}.

def tokens_to_str(toks) -> str:
    out = []
    for t in toks:
        if isinstance(t, str):
            out.append(t.replace("{", "{{").replace("}", "}}"))
        elif t[0] == "tag":
            out.append("{%d:%d:%s}" % (t[1], t[2], t[3].hex()) if t[3] else "{%d:%d}" % (t[1], t[2]))
        else:
            out.append("{/%d:%d}" % (t[1], t[2]))
    return "".join(out)


def str_to_tokens(s: str):
    toks, buf, i = [], [], 0
    while i < len(s):
        c = s[i]
        if s.startswith("{{", i) or s.startswith("}}", i):
            buf.append(c); i += 2; continue
        if c == "{":
            j = s.index("}", i)
            body = s[i + 1:j]
            if buf:
                toks.append("".join(buf)); buf = []
            if body.startswith("/"):
                g, t = body[1:].split(":")
                toks.append(("end", int(g), int(t), b""))
            else:
                parts = body.split(":")
                params = bytes.fromhex(parts[2]) if len(parts) > 2 else b""
                toks.append(("tag", int(parts[0]), int(parts[1]), params))
            i = j + 1
            continue
        buf.append(c); i += 1
    if buf:
        toks.append("".join(buf))
    return toks


# ---------------------------------------------------------------- CLI

def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    cmd, path = argv[0], argv[1]
    sarc = Sarc(load(path))
    if cmd == "list":
        for nm, d in sarc.files.items():
            print(f"{len(d):9d}  align={sarc.align[nm]:#x}  {nm}")
    elif cmd == "unpack":
        out = Path(argv[2])
        for nm, d in sarc.files.items():
            p = out / nm
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(d)
        print(f"{len(sarc.files)} files -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
