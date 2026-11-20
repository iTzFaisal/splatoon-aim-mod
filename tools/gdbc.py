"""Send a python snippet (argument or stdin) to gdbd.py and print the result."""
import socket
import sys

code = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
s = socket.create_connection(("127.0.0.1", 1338))
s.sendall(code.encode() + b"\0")
out = b""
while True:
    d = s.recv(65536)
    if not d:
        break
    out += d
print(out.decode(), end="")
