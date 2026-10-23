# keep only triangles inside the assembled unit's bbox (drops exploded copies)
import struct
import sys
from pathlib import Path

src, dst, box = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3].split(",")]
b = Path(src).read_bytes()
n = struct.unpack("<I", b[80:84])[0]
out = []
for i in range(n):
    r = b[84 + 50 * i : 84 + 50 * i + 50]
    v = struct.unpack("<12f", r[:48])[3:]
    if all(box[2 * k] - 0.01 <= v[3 * j + k] <= box[2 * k + 1] + 0.01 for j in range(3) for k in range(3)):
        out.append(r)
Path(dst).write_bytes(b"\0" * 80 + struct.pack("<I", len(out)) + b"".join(out))
print(dst, len(out))
