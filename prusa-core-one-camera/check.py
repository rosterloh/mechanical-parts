# Verifies prusa_core_one_camera.py: volume each cut should change, the esp32cam parts against the Printables STLs
# (kept out of git, read from $PRUSA_CAM_REF), and the dfr1154 cup's joint and fit.
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

import prusa_core_one_camera as cam

SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix=f"{cam.NAME}-check-")
cmds, marks = cam.build(TMP)


def stage_bodies():
    """Bodies after every stage, from one run of the script with a measure probe at each stage's end."""
    script, res = os.path.join(TMP, "stages.json"), os.path.join(TMP, "stages.r.json")
    at = {}
    for s, i in marks.items():
        at.setdefault(i, []).append(s)  # stages with nothing between them end at the same command
    probed, where = [], {}
    for i in range(len(cmds) + 1):
        if i in at:
            for s in at[i]:
                where[s] = len(probed)
            probed.append({"command": "inspect.measure", "params": {}})
        if i < len(cmds):
            probed.append(cmds[i])
    Path(script).write_text(json.dumps({"commands": probed}))
    subprocess.run([SC, "run", script, "--results", "--json-out", res, "--quiet"], check=True, capture_output=True)
    r = json.loads(Path(res).read_text())
    return {s: {b["name"]: b for b in r[k]["bodies"]} for s, k in where.items()}


INFO = False  # set while running checks that are reported but not required


def close(got, want, tol, what):
    ok = abs(got - want) <= tol
    print(f"{'ok  ' if ok else 'info' if INFO else 'FAIL'} {what}: got {got:.2f}, want {want:.2f} ±{tol:.2f}")
    return ok


def true(cond, what, detail=""):
    print(f"{'ok  ' if cond else 'info' if INFO else 'FAIL'} {what} {detail}")
    return cond


def stl(path):
    b = Path(path).read_bytes()
    n = struct.unpack("<I", b[80:84])[0]
    return [[struct.unpack("<3f", b[96 + 50 * i + 12 * j : 108 + 50 * i + 12 * j]) for j in range(3)] for i in range(n)]


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


def samples(tris, depth, spacing=1.5):
    """Points over every triangle (about one per spacing² mm²) moved `depth` along the outward normal."""
    out = []
    for p, q, r in tris:
        u, v = [q[k] - p[k] for k in range(3)], [r[k] - p[k] for k in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = math.sqrt(sum(c * c for c in n))
        if ln < 0.02:  # < 0.01 mm²: export slivers where faces meet, their normals are float noise
            continue
        k = max(1, int(math.sqrt(ln / 2) / spacing))
        for i in range(k):
            for j in range(k - i):
                a, b = (i + 1 / 3) / k, (j + 1 / 3) / k
                out.append(tuple(p[m] + a * u[m] + b * v[m] + depth * n[m] / ln for m in range(3)))
    return out


def mesh_volume(tris):
    return (
        sum(
            p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0])
            for p, q, r in tris
        )
        / 6
    )


def match(ours, ref, tol, skip=lambda p: False):
    """Surface points of `ours` stepped `tol` in and out must fall on the same side of `ref` as of `ours`: (misses,
    total). Against `ours` rather than a fixed side, since near a concave corner a step out lands in the other face."""
    own, solid = Solid(ours), Solid(ref)
    pts = [p for p in samples(ours, -tol) + samples(ours, tol) if not skip(p)]
    misses = [p for p in pts if solid.inside(p) != own.inside(p)]
    return misses, len(pts)


def bbox(tris):
    pts = [p for t in tris for p in t]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def matches(name, ours, ref, skip=lambda p: False):
    """bbox ±0.2, volume ±1 %, and the two-way surface match at 0.5 (≤0.5 % misses for facet chords)."""
    ok = True
    (lo, hi), (rlo, rhi) = bbox(ours), bbox(ref)
    for i in range(3):
        ok &= close(lo[i], rlo[i], 0.2, f"{name} bbox min {'xyz'[i]}")
        ok &= close(hi[i], rhi[i], 0.2, f"{name} bbox max {'xyz'[i]}")
    rv = mesh_volume(ref)
    ok &= close(mesh_volume(ours), rv, 0.01 * rv, f"{name} volume")
    for a, b, way in ((ours, ref, "ours in ref"), (ref, ours, "ref in ours")):
        misses, n = match(a, b, 0.5, skip)
        frac = len(misses) / n
        cells = {}
        for p in misses:
            c = tuple(int(p[i] // 5) * 5 for i in range(3))
            cells[c] = cells.get(c, 0) + 1
        worst = sorted(cells.items(), key=lambda kv: -kv[1])[:6]
        where = ", ".join(f"{n}@{list(c)}" for c, n in worst)  # 5 mm cells by lower corner, most misses first
        ok &= true(frac <= 0.005, f"{name} surface match ({way})", f"({len(misses)}/{n} = {frac:.2%}) {where}")
    return ok


REF = os.environ.get("PRUSA_CAM_REF", os.path.expanduser("~/Downloads/3D"))


def ref(name):
    path = os.path.join(REF, name)
    if not os.path.isfile(path):
        print(f"SKIP {name}: set PRUSA_CAM_REF")
        return None
    return stl(path)


def ours(part):
    return stl(os.path.join(TMP, f"{cam.NAME}-{part}.stl"))


v = stage_bodies()


def dv(body, a, b):
    return v[b][body]["volume_mm3"] - v[a][body]["volume_mm3"]


def cut(body, a, b, what):
    """A cut or chamfer that leaves the volume unchanged has missed its edge."""
    return true(dv(body, a, b) < -1, what, f"({dv(body, a, b):.1f} mm³)")


results = [
    cut("Plate", "e32:plate", "e32:plate_chamfer", "plate top chamfer"),
    cut("Leg", "e32:leg", "e32:magnet", "magnet pocket"),
    cut("Leg", "e32:magnet", "e32:bore", "screwdriver bore"),
    cut("Plate", "e32:plate_legs", "e32:plate_holes", "plate screw holes"),
    cut("E32Cup", "e32:cup_shell", "e32:cup_corners", "cup corner rounds"),
    cut("E32Cup", "e32:cup_corners", "e32:cup_hollow", "cup hollow"),
    cut("CupPost0", "e32:posts", "e32:post_chamfers", "post chamfers"),
    cut("E32Cup", "e32:cup_inside", "e32:post_pilots", "post pilot holes"),
    cut("E32Cup", "e32:post_pilots", "e32:lens", "lens recess and hole"),
    cut("E32Cup", "e32:lens", "e32:flash", "flash hole"),
    cut("E32Cup", "e32:bosses", "e32:cup_pilots", "cup pilot holes"),
    cut("E32Cup", "e32:cup_pilots", "e32:cable", "cable slot"),
    cut("E32Cup", "e32:cable", "e32:vents", "vents"),
    cut("Bracket", "e32:bracket", "e32:bracket_convex", "bracket outer bend rounds"),
    true(dv("Bracket", "e32:bracket_convex", "e32:bracket_rounds") > 1, "bracket inner bend rounds"),
    cut("Bracket", "e32:bracket_rounds", "e32:bracket_chamfers", "bracket end chamfers"),
    cut("Bracket", "e32:bracket_chamfers", "e32:bracket_holes", "bracket holes"),
]
r = ref("prusacoreone_kamera_oben_v3.stl")
if r:
    results.append(matches("plate", ours("plate"), r))
r = ref("prusacoreone_kamera_unten_v3.stl")
if r:
    results.append(matches("esp32cam cup", ours("esp32cam-cup"), r))
r = ref("prusacoreone_kamera_bugel.stl")
if r:
    results.append(matches("bracket", ours("bracket"), r))

sys.exit(0 if all(results) else 1)
