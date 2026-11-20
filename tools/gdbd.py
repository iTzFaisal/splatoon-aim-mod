"""Persistent holder of the Cemu GDB connection. Executes python snippets sent to 127.0.0.1:1338.
Snippets see `g` (GDB instance) and `S` (dict for state between calls). Output = captured stdout.
usage: uv run tools/gdbd.py          (then: uv run tools/gdbc.py "<python code>")
"""
import contextlib
import io
import socket
import sys
import traceback

sys.path.insert(0, __file__.replace("\\", "/").rsplit("/", 1)[0])
from gdb import GDB  # noqa: E402

g = GDB()
print("stop:", g.cmd("?"), flush=True)
g.cont()
S = {}
srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 1338))
srv.listen(1)
while True:
    c, _ = srv.accept()
    data = b""
    while not data.endswith(b"\0"):
        chunk = c.recv(65536)
        if not chunk:
            break
        data += chunk
    code = data.rstrip(b"\0").decode()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            exec(code, {"g": g, "S": S, "__name__": "snippet"})
        except Exception:
            traceback.print_exc(file=out)
    c.sendall(out.getvalue().encode())
    c.close()
