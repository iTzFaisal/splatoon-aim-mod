"""Tiny GDB remote-serial-protocol client for Cemu's GDB stub (--enable-gdbstub, port 1337)."""
import socket
import struct


class GDB:
    def __init__(self, host="127.0.0.1", port=1337, timeout=None):
        self.s = socket.create_connection((host, port))
        self.s.settimeout(timeout)
        self.buf = b""

    def _recv_packet(self, timeout=None):
        self.s.settimeout(timeout)
        while True:
            i = self.buf.find(b"$")
            if i >= 0:
                j = self.buf.find(b"#", i)
                if j >= 0 and len(self.buf) >= j + 3:
                    data = self.buf[i + 1:j]
                    self.buf = self.buf[j + 3:]
                    self.s.sendall(b"+")
                    return data.decode("latin1")
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk

    def cmd(self, data, wait=True, timeout=10):
        pkt = data.encode("latin1")
        cs = sum(pkt) & 0xFF
        self.s.sendall(b"$" + pkt + b"#" + f"{cs:02x}".encode())
        if wait:
            return self._recv_packet(timeout)

    def wait_stop(self, timeout=None):
        return self._recv_packet(timeout)

    def read(self, addr, n):
        out = b""
        while n > 0:
            k = min(n, 0x400)
            r = self.cmd(f"m{addr:x},{k:x}")
            if r.startswith("E") and len(r) == 3:
                raise IOError(f"read {addr:08x}: {r}")
            out += bytes.fromhex(r)
            addr += k
            n -= k
        return out

    def u32(self, a):
        return struct.unpack(">I", self.read(a, 4))[0]

    def f32(self, a):
        return struct.unpack(">f", self.read(a, 4))[0]

    def write(self, addr, data):
        return self.cmd(f"M{addr:x},{len(data):x}:{data.hex()}")

    def reg(self, n):
        return int(self.cmd(f"p{n:x}"), 16)

    def regs(self):
        r = self.cmd("g")
        return [int(r[i * 8:i * 8 + 8], 16) for i in range(32)]

    def pc(self):
        return self.reg(0x40)

    def lr(self):
        return self.reg(0x43)

    def bp(self, addr):
        return self.cmd(f"Z0,{addr:x},4")

    def unbp(self, addr):
        return self.cmd(f"z0,{addr:x},4")

    def cont(self):
        self.cmd("Hc-1")  # resume *all* threads (Cemu default resumes only one)
        self.cmd("c", wait=False)

    def interrupt(self):
        self.s.sendall(b"\x03")
