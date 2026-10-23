# Verifies poe_rs485_3030_mount.py: volume each finishing step should change, clearance to both units, and that they are held.
# usage: python3 check.py
import json
import math
import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import poe_rs485_3030_mount as mount

SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix=f"{mount.NAME}-check-")
cmds, marks = mount.build(TMP)


def bracket_after(stage):
    script, res = os.path.join(TMP, f"{stage}.json"), os.path.join(TMP, f"{stage}.r.json")
    Path(script).write_text(json.dumps({"commands": cmds[: marks[stage]]}))
    subprocess.run([SC, "eval", script, "--json-out", res], check=True, capture_output=True)
    return next(b for b in json.loads(Path(res).read_text())["bodies"] if b["name"] == "Bracket")


def stl(path, place=lambda p: p):
    b = Path(path).read_bytes()
    n = struct.unpack("<I", b[80:84])[0]
    return [
        [place(struct.unpack("<3f", b[96 + 50 * i + 12 * j : 108 + 50 * i + 12 * j])) for j in range(3)]
        for i in range(n)
    ]


class Solid:
    """Point-in-solid by vertical ray parity over an xy grid of triangles."""

    def __init__(self, tris, cell=2.0):
        self.cell, self.grid = cell, {}
        for t in tris:
            xs, ys = [p[0] for p in t], [p[1] for p in t]
            for i in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
                for j in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
                    self.grid.setdefault((i, j), []).append(t)

    def inside(self, p):
        px, py, pz = p[0] + 1.3e-5, p[1] + 0.7e-5, p[2]  # off-axis, so the ray misses shared edges
        n = 0
        for (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) in self.grid.get((int(px // self.cell), int(py // self.cell)), ()):
            d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(d) < 1e-12:
                continue
            a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / d
            b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / d
            if a >= 0 and b >= 0 and a + b <= 1 and a * z1 + b * z2 + (1 - a - b) * z3 > pz:
                n += 1
        return n % 2 == 1


def samples(tris, depth=0.05):
    """Triangle centroids moved `depth` into the unit, so touching surfaces don't count as a clash."""
    out = []
    for p, q, r in tris:
        u, v = [q[k] - p[k] for k in range(3)], [r[k] - p[k] for k in range(3)]
        nx, ny, nz = u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln < 1e-9:
            continue
        out.append(tuple((p[k] + q[k] + r[k]) / 3 - depth * (nx, ny, nz)[k] / ln for k in range(3)))
    return out


def clashes(solid, pts, shift=(0, 0, 0)):
    return [p for p in pts if solid.inside((p[0] + shift[0], p[1] + shift[1], p[2] + shift[2]))]


def close(got, want, tol, what):
    ok = abs(got - want) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {what}: got {got:.2f}, want {want:.2f} ±{tol:.2f}")
    return ok


def true(cond, what, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {what} {detail}")
    return cond


# --- volumes: each pick must hit its edge
v = {s: bracket_after(s) for s in marks}
vol = {s: b["volume_mm3"] for s, b in v.items()}
bb = v["holes"]["bbox"]
k = 1 - math.pi / 4
P = mount.PLATE_PERIMETER
ridge_r = mount.RIDGE_D / 2
results = [
    close(bb["max"][0], 63.3, 1e-6, "nothing past the RJ45/USB-C face (x max)"),
    close(bb["max"][2], mount.POE["top"] + mount.HOOK_H, 1e-6, "tab top (z max)"),
    close(
        vol["ridge_tip"] - vol["layout"],
        -(mount.RIDGE_CHAMFER**2) / 2 * 2 * math.pi * (ridge_r - mount.RIDGE_CHAMFER / 3) * 2,
        0.3,
        "peg ridge lead-ins",
    ),
    close(
        vol["peg_slot"] - vol["ridge_tip"],
        -2 * mount.PEG_SLOT_W * (mount.PEG_D * (mount.RIDGE_Z0 - mount.PEG_SLOT_Z0) + mount.RIDGE_D * mount.RIDGE_H),
        3.0,
        "peg slots",
    ),
    close(
        vol["tab_fillet"] - vol["peg_slot"],
        4 * k * mount.TAB_W * (mount.TAB_ROOT_R**2 + mount.TAB_ROOT_R_IN**2),
        0.2,
        "tab-root fillets, both faces",
    ),
    close(
        vol["corners"] - vol["tab_fillet"],
        -2 * k * mount.CORNER_R**2 * mount.PLATE - 2 * k * mount.CORNER_R_RJ45**2 * (mount.PLATE + mount.WALL_H),
        0.5,
        "plate corners",
    ),
    close(
        vol["bottom_chamfer"] - vol["corners"], -(mount.BOTTOM_CHAMFER**2) / 2 * P, 0.02 * 0.125 * P, "bottom chamfer"
    ),
    close(vol["holes"] - vol["bottom_chamfer"], -2 * math.pi * 3.3**2 * mount.PLATE, 2.0, "M6 holes"),
]

# --- geometry against the unit meshes (SolidCraft skips mesh bodies in interference)
Path(TMP, "full.json").write_text(json.dumps({"commands": cmds}))
subprocess.run([SC, "run", os.path.join(TMP, "full.json"), "--quiet"], check=True, capture_output=True)
bracket = Solid(stl(os.path.join(TMP, f"{mount.NAME}.stl")))
poe_t = stl(os.path.join(HERE, "units/poe.stl"), mount.place_poe)
rs_t = stl(os.path.join(HERE, "units/rs485.stl"), mount.place_rs485)
poe, rs = samples(poe_t), samples(rs_t)

c = clashes(bracket, poe) + clashes(bracket, rs)
results.append(
    true(
        not c,
        "no bracket material inside either unit",
        f"({len(c)} points, e.g. {[tuple(round(x, 2) for x in p) for p in c[:3]]})",
    )
)
c = clashes(bracket, poe, (1.0, 0, 0))
results.append(true(len(c) > 0, "PoE pulled 1 mm toward the RJ45 is stopped", f"({len(c)} points)"))
c = clashes(bracket, poe, (-1.0, 0, 0))
results.append(true(len(c) > 0, "PoE pushed 1 mm the other way is stopped", f"({len(c)} points)"))
c = [p for p in clashes(bracket, rs, (0, 0, -0.3)) if p[0] < -70]
results.append(true(len(c) > 0, "RS485 far end (x < -70) rests on the bracket", f"({len(c)} points)"))
# peg ridge: free inside the top counterbore, with a lip of the bore under it to catch on
for x, y in mount.lego():
    pts = [p for t in rs_t for p in t] + [tuple(sum(q[k] for q in t) / 3 for k in range(3)) for t in rs_t]
    near = [(math.hypot(p[0] - x, p[1] - y), p[2]) for p in pts if math.hypot(p[0] - x, p[1] - y) < 3.4]
    in_cb = [r for r, z in near if mount.RIDGE_Z0 < z < mount.RIDGE_Z0 + mount.RIDGE_H]
    lip = [r for r, z in near if mount.RIDGE_Z0 - 0.4 < z < mount.RIDGE_Z0 - 0.05]
    results.append(
        true(
            in_cb and min(in_cb) > ridge_r and lip and min(lip) < ridge_r - 0.1,
            f"peg at ({x:.1f}, {y:.1f}) catches under the counterbore lip",
            f"(counterbore r {min(in_cb) if in_cb else None}, lip r {min(lip) if lip else None}, ridge r {ridge_r})",
        )
    )
sys.exit(0 if all(results) else 1)
