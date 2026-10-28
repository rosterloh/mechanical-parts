# Verifies protective_stop_remote.py: volume each finishing step should change, the s3 variant against Polymath's
# STLs, and the p4 variant's fit.
# usage: python3 check.py
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import protective_stop_remote as remote

SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "vendor", "polymath-protective-stop")
TMP = tempfile.mkdtemp(prefix=f"{remote.NAME}-check-")
cmds, marks = remote.build(TMP)


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
        if ln < 1e-9:
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


# --- volumes: each pick must hit its edge
v = stage_bodies()


def dv(body, a, b):
    return v[b][body]["volume_mm3"] - v[a][body]["volume_mm3"]


results = []
results.append(true(dv("S3Base", "s3:base_layout", "s3:base_fillets") < -100, "s3 body bottom fillet"))
results.append(true(dv("S3pod", "s3:base_layout", "s3:base_fillets") < -10, "s3 pod bottom fillets"))
s3 = remote.VARIANTS["s3"]
post_h = s3["rim"] - s3["floor_top"]
n_post, n_so = len(s3["posts"]), len(s3["standoffs"])
so_h = s3["standoffs"][0][2] - s3["chan_floor"]  # all s3 standoffs are the same height
win_area = sum((y1 - y0) * (z1 - z0) for y0, y1, z0, z1 in s3["windows"].values())
results += [
    # two posts merge into the channel walls, so less than the full cylinders
    true(
        0.8 * n_post * math.pi * (s3["post_d"] / 2) ** 2 * post_h
        < dv("S3Base", "s3:channel", "s3:posts")
        < n_post * math.pi * (s3["post_d"] / 2) ** 2 * post_h,
        "s3 lid posts",
        f"({dv('S3Base', 's3:channel', 's3:posts'):.0f})",
    ),
    # the two posts by the pod have their holes break into the channel walls
    true(
        -n_post * math.pi * (s3["post_hole_d"] / 2) ** 2 * post_h
        <= dv("S3Base", "s3:posts", "s3:post_holes")
        < -0.95 * n_post * math.pi * (s3["post_hole_d"] / 2) ** 2 * post_h,
        "s3 insert holes in the lid posts",
        f"({dv('S3Base', 's3:posts', 's3:post_holes'):.0f})",
    ),
    close(
        dv("S3Base", "s3:post_holes", "s3:standoffs"),
        n_so * math.pi * (s3["standoffs"][0][3] / 2) ** 2 * so_h,
        1.0,
        "s3 board standoffs",
    ),
    close(
        dv("S3Base", "s3:standoffs", "s3:standoff_holes"),
        -n_so * math.pi * (s3["standoffs"][0][4] / 2) ** 2 * s3["standoff_hole_depth"],
        1.0,
        "s3 standoff insert holes",
    ),
    close(dv("S3Base", "s3:standoff_holes", "s3:windows"), -s3["chan_t"] * win_area, 1.0, "s3 port windows"),
    close(
        dv("S3Base", "s3:windows", "s3:small_holes"),
        -(
            2 * s3["chan_t"] * math.pi * 0.75**2
            + math.pi * 1**2 * (s3["chan_floor"] - s3["z_bot"])
            + math.pi * s3["wire_slot"][2] ** 2 / 2 * s3["chan_t"]
        ),
        0.3,
        "s3 cross hole, floor hole and end-wall slot",
    ),
    close(
        dv("S3Base", "s3:small_holes", "s3:wall_notches"),
        -2 * s3["chan_t"] * math.pi * (s3["wall_notch"][1] / 2) ** 2 / 2,
        0.2,
        "s3 wire notches in the channel side walls",
    ),
]


def area_in(inside, x0, x1, y0, y1, step=0.02):
    """Area of the region `inside(x, y)` within a box, on a grid."""
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    hits = sum(inside(x0 + (i + 0.5) * step, y0 + (j + 0.5) * step) for i in range(nx) for j in range(ny))
    return hits * step * step


lh = s3["lid_top"] - s3["lid_bot"]
lx0, lx1, ly0, ly1, lz0 = s3["lip"]
pr0, pr1, skin = s3["ring_pocket"]
ptop = s3["lid_top"] - skin
br0, bw, bh = s3["ring_bumps"]
bd, flat, key_w, key_y = s3["button_hole"]


def in_button_hole(x, y):
    in_round = x * x + y * y <= (bd / 2) ** 2 and abs(x) <= flat
    return in_round or (abs(x) <= key_w / 2 and 0 <= y <= key_y - remote.CY)


button_area = area_in(in_button_hole, -bd / 2, bd / 2, -bd / 2, key_y - remote.CY)
cb = s3["cb_depth"]
results += [
    true(dv("S3Lid", "s3:lid_layout", "s3:lid_fillet") < -50, "s3 lid top fillet"),
    close(dv("S3Lid", "s3:lid_fillet", "s3:lip"), (lx1 - lx0) * (ly1 - ly0) * (s3["lid_bot"] - lz0), 1.0, "s3 lid lip"),
    close(
        dv("S3Lid", "s3:lip", "s3:diffuser_hole"), -math.pi * (s3["diffuser_d"] / 2) ** 2 * lh, 2.0, "s3 diffuser hole"
    ),
    close(
        dv("S3Lid", "s3:diffuser_hole", "s3:lid_holes"),
        -len(s3["posts"]) * math.pi * ((s3["screw_d"] / 2) ** 2 * (lh - cb) + (s3["cb_d"] / 2) ** 2 * cb),
        1.0,
        "s3 counterbored lid screw holes",
    ),
    close(
        dv("S3Diffuser", "s3:diffuser_layout", "s3:ring_pocket"),
        -math.pi * (pr1**2 - pr0**2) * (ptop - s3["lid_bot"]),
        2.0,
        "s3 ring pocket",
    ),
    # blocks standing in for Polymath's curved bumps, so the volume is only a sign check
    true(dv("S3Diffuser", "s3:ring_pocket", "s3:ring_bumps") > 0.5 * 4 * (pr1 - br0) * bw * bh, "s3 ring snap bumps"),
    close(dv("S3Diffuser", "s3:ring_bumps", "s3:button_hole"), -button_area * lh, 1.0, "s3 FF01 button hole"),
]


# --- p4: its own features, its height, and the fit of board, stand-ins, button and ring
p4 = remote.VARIANTS["p4"]
xb, yb, zb = remote.p4_frame(p4)
lb, pins_top, sockets_top = remote.p4_height(p4)
print(f"     p4 lid underside {lb:.1f}: pins need {pins_top:.1f}, sockets {sockets_top:.1f}")
results += [
    close(p4["lid_bot"], max(pins_top, sockets_top), 1e-9, "p4 lid underside set by the higher of pins and sockets"),
    true(dv("P4Base", "p4:channel", "p4:posts") > 0, "p4 lid posts"),
    true(dv("P4Base", "p4:posts", "p4:post_holes") < 0, "p4 insert holes in the lid posts"),
    true(dv("P4Base", "p4:post_holes", "p4:standoffs") > 0, "p4 module and board posts"),
    close(
        dv("P4Base", "p4:standoffs", "p4:standoff_holes"),
        -sum(math.pi * (h / 2) ** 2 for *_, h in p4["standoffs"]) * p4["standoff_hole_depth"],
        1.0,
        "p4 post insert holes",
    ),
    close(
        dv("P4Base", "p4:standoff_holes", "p4:windows"),
        -p4["chan_t"] * sum((y1 - y0) * (z1 - z0) for y0, y1, z0, z1 in p4["windows"].values()),
        1.0,
        "p4 RJ45 window",
    ),
]
results.append(
    close(
        dv("P4Base", "p4:windows", "p4:board_stops"),
        sum((x1 - x0) * (y1 - y0) * (z1 - p4["floor_top"]) for x0, x1, y0, y1, _, z1 in p4["board_stops"]),
        1.0,
        "p4 board stop lugs",
    )
)
# sockets clear of the FF01's nut and terminals in plan (nut Ø22 + 1.3 half socket + 1)
keep_out = 11 + 1.3 + 1
nearest = min(
    math.hypot((b[0] + b[1]) / 2 - remote.CX, (b[2] + b[3]) / 2 - remote.CY)
    for b in remote.p4_standins(p4)["P4Sockets"]
)
results.append(close(max(nearest, keep_out), nearest, 0, f"p4 sockets ≥ {keep_out} from the button axis"))


# open (unclosed) bodies in Waveshare's STEP the kernel can't check; each is an 0201/0402 part on the board's face
OPEN_BODIES = ("USER_LIBRARY-RES_0603-0201_4", "3_1_A")


def interferences(extra, bodies, keep):
    """Overlapping pairs among `bodies` that `keep` accepts (touching faces don't count). Exits if the kernel
    couldn't check every accepted pair, so an incomplete query can't pass as a clean fit."""
    script, res = os.path.join(TMP, "fit.json"), os.path.join(TMP, "fit.r.json")
    probe = {"command": "inspect.interference", "params": {"bodies": bodies, "budget_s": 900}}
    Path(script).write_text(json.dumps({"commands": cmds + extra + [probe]}))
    subprocess.run([SC, "run", script, "--results", "--json-out", res, "--quiet"], check=True, capture_output=True)
    r = json.loads(Path(res).read_text())[-1]
    if r.get("budget_exceeded") or r.get("truncated"):
        sys.exit(f"interference query incomplete (budget_exceeded/truncated): {bodies}")
    unchecked = [u for u in r["unchecked"] if keep(u["a"], u["b"] or "")]
    known = [u for u in unchecked if any((u["b"] or "").startswith(n) or u["a"].startswith(n) for n in OPEN_BODIES)]
    if known:
        print(f"     not checked (open bodies in the vendor STEP): {[(u['a'], u['b'].split(' ')[0]) for u in known]}")
    if len(known) < len(unchecked):
        sys.exit(f"interference not checked: {[u for u in unchecked if u not in known]}")
    return [i for i in r["interferences"] if keep(i["a"], i["b"])]


def pairs(found):
    return [(i["a"], i["b"], round(i["volume_mm3"], 2)) for i in found]


case = {"P4Base", "P4Lid", "P4Diffuser"}
standins = set(remote.p4_standins(p4))
ff01 = {"FF01H", "FF01CBA", "ff01_seal", "FF01N", "FF01T2", "FF01IH"}

# --- the whole script once, so its exports land in TMP
Path(TMP, "all.json").write_text(json.dumps({"commands": cmds + [{"command": "inspect.measure", "params": {}}]}))
res = os.path.join(TMP, "all.r.json")
subprocess.run([SC, "run", os.path.join(TMP, "all.json"), "--results", "--json-out", res, "--quiet"], check=True)
final = {b["name"]: b["bbox"] for b in json.loads(Path(res).read_text())[-1]["bodies"]}
ring = {n for n in final if n.startswith("LED")}
board = {n for n in final if not n.startswith("S3")} - case - standins - ff01 - ring


def near(bb):
    """A board body that could touch the case, the button or the ring: by the floor, walls, end wall, posts or lid."""
    lo, hi = bb["min"], bb["max"]
    y0, y1 = p4["pod_y"]
    t = p4["chan_t"]
    by_post = any(
        lo[0] < x + 4 and hi[0] > x - 4 and lo[1] < y + 4 and hi[1] > y - 4 and lo[2] < top + 1
        for x, y, top, *_ in p4["standoffs"]
    )
    return (
        by_post
        or lo[2] < p4["chan_floor"] + 1
        or lo[0] < p4["pod_x0"] + t + 1
        or lo[1] < y0 + t + 1
        or hi[1] > y1 - t - 1
        or hi[2] > lb - remote.FF01_BELOW - 2
    )


board_near = sorted(n for n in board if near(final[n]))
print(f"     ({len(board_near)} of {len(board)} board bodies can reach the case, button or ring)")


def fit_pair(a, b):
    ab = {a, b}
    if ab & standins and ab & board:  # the module sits on the board, the sockets on its pins
        return False
    return bool(ab & case) or (bool(ab & (ff01 | ring)) and bool(ab & (board | standins)))


found = interferences([], sorted(case | standins | ff01 | ring) + board_near, fit_pair)
results.append(true(not found, "p4: no clash between case, board, stand-ins, button and ring", f"{pairs(found)}"))

# a plug, the size of the jack's mouth, pushed in from 10 mm outside
mx0, mx1, mz0, mz1 = remote.P4_RJ45_MOUTH
x_in = p4["pod_x0"] + p4["chan_t"]
plug = {
    "command": "solid.box",
    "params": {
        "length": 10 + p4["chan_t"],
        "width": mx1 - mx0,
        "height": mz1 - mz0,
        "corner": [x_in - 10 - p4["chan_t"], yb + mx0, zb - mz1],
        "body_name": "plug",
    },
}
found = interferences([plug], ["P4Base", "plug"], lambda a, b: True)
results.append(true(not found, "p4: an RJ45 plug reaches the jack through the window", f"{pairs(found)}"))

# unplugging pulls the jack outward: its face bears on the end wall around the window
pull = [
    {"command": "solid.move", "params": {"bodies": ["RJ45_HR911105A"], "translate": [0, -0.3, 0]}}
]  # local y = world x
found = interferences(pull, ["P4Base", "RJ45_HR911105A"], lambda a, b: True)
results.append(true(bool(found), "p4: the RJ45 bears on the end wall when a plug is pulled", f"{pairs(found)}"))

# plugging in pushes the board inward: its USB-C end must meet the stop lugs
# (a box for the PCB: the boolean against the STEP's PCB, holes and all, fails in the kernel)
push = [
    {
        "command": "solid.box",
        "params": {"length": 78, "width": 21, "height": 1.6, "corner": [xb + 0.5, yb, zb], "body_name": "pcb"},
    }
]
found = interferences(push, ["P4Base", "pcb"], lambda a, b: True)
results.append(true(bool(found), "p4: the board's end meets the stop lugs when a plug is pushed in", f"{pairs(found)}"))

# M1.6 screws from the pin side through board and module into the module posts' inserts
screws = []
for i, (x, y, top, *_) in enumerate(p4["standoffs"][:2]):
    z0 = top - p4["standoff_hole_depth"] + 0.5
    screws.append(
        {
            "command": "solid.cylinder",
            "params": {"diameter": 1.5, "height": zb + 1.6 - z0, "base": [x, y, z0], "body_name": f"screw{i}"},
        }
    )
names = [c["params"]["body_name"] for c in screws]
found = interferences(
    screws,
    names + sorted(case) + ["P4Module"] + sorted(set(board_near) | {"BOARD-893"}),
    lambda a, b: bool({a, b} & set(names)),
)
results.append(
    true(not found, "p4: module screws pass through board and module holes into the posts", f"{pairs(found)}")
)


def unmodelled(p):
    # Polymath's logo is embossed on the pod's side faces; not modelled (spec non-goal). Their standoffs' r2 feet
    # aren't either (see the generator)
    feet = p[2] < s3["chan_floor"] + 2.1 and any(math.hypot(p[0] - x, p[1] - y) < 4.1 for x, y, *_ in s3["standoffs"])
    return feet or (p[0] < 1 and (p[1] < -3.3 or p[1] > 22.4))


results.append(
    matches(
        "s3 base",
        stl(os.path.join(TMP, f"{remote.NAME}-s3-base.stl")),
        stl(os.path.join(REF, "base.stl")),
        unmodelled,
    )
)
results.append(
    matches("s3 lid", stl(os.path.join(TMP, f"{remote.NAME}-s3-lid.stl")), stl(os.path.join(REF, "lid-minus-led.stl")))
)
# the two-colour lid: lid and diffuser as separate, aligned objects in one 3MF, so the slicer can give each a filament
for key in remote.VARIANTS:
    with zipfile.ZipFile(os.path.join(TMP, f"{remote.NAME}-{key}-lid.3mf")) as z:
        model = z.read("3D/3dmodel.model").decode()
    objects = model.count("<object ")
    results.append(close(objects, 2, 0, f"{key} two-colour lid 3MF objects (lid, diffuser)"))

# informational: the snap bumps are blocks, Polymath's are curved (≈0.6 % of points miss); not chased further
INFO = True
matches("s3 diffuser", stl(os.path.join(TMP, f"{remote.NAME}-s3-diffuser.stl")), stl(os.path.join(REF, "led.stl")))
sys.exit(0 if all(results) else 1)
