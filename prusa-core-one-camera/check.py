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


def interferences(bodies, keep, extra=()):
    """Overlapping pairs among `bodies` that `keep` accepts (touching faces don't count), after the `extra` commands.
    Exits if the kernel couldn't check every accepted pair, so an incomplete query can't pass as a clean fit."""
    script, res = os.path.join(TMP, "fit.json"), os.path.join(TMP, "fit.r.json")
    probe = {"command": "inspect.interference", "params": {"bodies": bodies, "budget_s": 900}}
    Path(script).write_text(json.dumps({"commands": cmds[: marks["render"]] + list(extra) + [probe]}))
    subprocess.run([SC, "run", script, "--results", "--json-out", res, "--quiet"], check=True, capture_output=True)
    r = json.loads(Path(res).read_text())[-1]
    if r.get("budget_exceeded") or r.get("truncated"):
        sys.exit(f"interference query incomplete (budget_exceeded/truncated): {bodies}")
    unchecked = [u for u in r["unchecked"] if keep(u["a"], u["b"] or "")]
    if unchecked:
        sys.exit(f"interference not checked: {unchecked}")
    return [(i["a"], i["b"], round(i["volume_mm3"], 2)) for i in r["interferences"] if keep(i["a"], i["b"])]


def joint_matches(a, b):
    """The dfr1154 cup meets the plate as the esp32cam cup does: rim outline (band just inside it solid, just outside
    empty) and the three pilots (empty bore, solid ring) agree in both."""
    ok = True
    z = cam.RIM_Z - 0.1
    for k in range(72):
        t = math.radians(5 * k + 2.5)
        # outer outline: hex across flats HEX_F, rounded corners; walk in from 40 mm to the first solid point of b
        r_out = next(
            (r / 20 for r in range(800, 400, -1) if b.inside((r / 20 * math.cos(t), r / 20 * math.sin(t), z))), 0
        )
        for dr, want in ((-0.3, True), (-1.8, True), (0.3, False)):
            p = ((r_out + dr) * math.cos(t), (r_out + dr) * math.sin(t), z)
            ok &= a.inside(p) == want and b.inside(p) == want
    for x, y in cam.JOINT:
        for zz in (26.2, 28.0, 29.8):
            ok &= not a.inside((x, y, zz)) and not b.inside((x, y, zz))
        # rings just inside and outside the Ø2.5 pilot, below the lead-in: a pilot moved 0.5 breaks one of them
        for k in range(8):
            t = math.radians(45 * k)
            for r, want in ((1.0, False), (1.5, True), (2.6, True)):
                p = (x + r * math.cos(t), y + r * math.sin(t), 27.5)
                ok &= a.inside(p) == want and b.inside(p) == want
    return true(ok, "dfr1154 cup joint matches the esp32cam cup (rim outline, pilots)")


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
# --- dfr1154: shell (DfrCup) and front plate (DfrBezel)
results += [
    cut("DfrCup", "dfr:shell", "dfr:hollow", "dfr1154 shell hollow"),
    true(dv("DfrCup", "dfr:hollow", "dfr:bosses") > 50, "dfr1154 plate-joint bosses"),
    cut("DfrCup", "dfr:bosses", "dfr:pilots", "dfr1154 plate-joint pilots"),
    true(dv("DfrCup", "dfr:pilots", "dfr:bezel_bosses") > 50, "dfr1154 front plate screw bosses"),
    cut("DfrCup", "dfr:bezel_bosses", "dfr:bezel_pilots", "dfr1154 front plate screw pilots"),
    cut("DfrCup", "dfr:bezel_pilots", "dfr:usb", "dfr1154 USB-C slot"),
    cut("DfrCup", "dfr:usb", "dfr:vents", "dfr1154 vents"),
    true(dv("DfrBezel", "dfr:bezel", "dfr:lip") > 50, "dfr1154 front plate lip"),
    true(dv("DfrBezel", "dfr:lip", "dfr:posts") > 50, "dfr1154 board posts"),
    cut("DfrBezel", "dfr:posts", "dfr:post_pilots", "dfr1154 post pilots"),
    cut("DfrBezel", "dfr:post_pilots", "dfr:module_hole", "dfr1154 camera module hole"),
    cut("DfrBezel", "dfr:module_hole", "dfr:ir", "dfr1154 IR windows"),
    true(dv("DfrBezel", "dfr:ir", "dfr:tubes") > 10, "dfr1154 light sensor and mic tubes"),
    cut("DfrBezel", "dfr:tubes", "dfr:windows", "dfr1154 light sensor window, mic hole"),
    cut("DfrBezel", "dfr:windows", "dfr:bezel_holes", "dfr1154 front plate screw holes"),
]
shell, bezel = Solid(ours("dfr1154-cup")), Solid(ours("dfr1154-front"))
results.append(joint_matches(shell, Solid(ours("esp32cam-cup"))))
zf, zi, zl, zp, zb = cam.z_front(), cam.z_inner(), cam.z_lens(), cam.z_pcb_front(), cam.z_pcb_back()


def open_column(solid, x, y, z0, z1, step=0.2):
    """Every point from z0 to z1 at (x, y) is outside the solid."""
    n = max(1, int((z1 - z0) / step))
    return all(not solid.inside((x, y, z0 + (z1 - z0) * i / n)) for i in range(n + 1))


def open_ray(solid, p, q, step=0.2):
    """Every point on the segment p→q is outside the solid."""
    n = max(1, int(math.dist(p, q) / step))
    return all(not solid.inside(tuple(p[k] + (q[k] - p[k]) * i / n for k in range(3))) for i in range(n + 1))


post_ok = True
for bx, by in cam.HOLES:
    x, y = cam.board_to_world(bx, by)
    zm = (zi + zp) / 2
    post_ok &= bezel.inside((x + 2.5, y, zm)) and bezel.inside((x - 2.5, y, zm))
    bottom = zp - cam.POST_PILOT_DEPTH
    post_ok &= open_column(bezel, x, y, bottom + 0.3, zp + 0.5) and bezel.inside((x, y, bottom - 0.3))
    post_ok &= bezel.inside((x, y, zf + 0.2))  # the pilot doesn't break through the face
results.append(true(post_ok, f"dfr1154 posts under the board holes, Ø2.5 × {cam.POST_PILOT_DEPTH:g} pilots"))

# camera: nothing of the front plate in the lens's view. Equidistant lens, the picture's edge at FOV_X across and
# FOV_Y along, so its boundary at azimuth psi is min(FOV_X/|cos psi|, FOV_Y/|sin psi|) off axis (80° at the corners)
lx, ly = cam.board_to_world(*cam.CAM)
fov_ok = open_column(bezel, lx, ly, zf - 1, zl)
for k in range(72):
    psi = math.radians(5 * k + 1)
    c, s = abs(math.cos(psi)), abs(math.sin(psi))
    theta = min(cam.FOV_X / c if c > 1e-6 else 90, cam.FOV_Y / s if s > 1e-6 else 90, 89.0)
    for frac in (0.0, 0.5, 1.0):  # aperture edge and middle
        r0 = cam.APERTURE_R * frac
        p = (lx + r0 * math.cos(psi), ly + r0 * math.sin(psi), zl)
        dz = zl - (zf - 0.5)
        reach = r0 + dz * math.tan(math.radians(theta))
        q = (lx + reach * math.cos(psi), ly + reach * math.sin(psi), zf - 0.5)
        fov_ok &= open_ray(bezel, p, q)
results.append(true(fov_ok, "dfr1154 nothing of the front plate in the 160° picture"))


# IR: how far off axis each LED's light gets out (outward, up, down) with nothing of the front plate, posts or tubes
# in the way, against IR_REACH; a wall stays between the module hole and each window
def ir_reach(x, y, top, dx, dy):
    """Widest angle (whole degrees) a ray from the LED at (x, y, top) clears the front plate along (dx, dy)."""
    h = top - (zf - 0.5)
    best = -1
    for ang in range(90):
        t = h * math.tan(math.radians(ang))
        if not open_ray(bezel, (x, y, top - 0.1), (x + dx * t, y + dy * t, zf - 0.5)):
            break
        best = ang
    return best


ir_ok, reached = True, []
hole = cam.CAM_BODY[0] / 2 + cam.CAM_CLEAR
for bx, by in cam.IR:
    x, y = cam.board_to_world(bx, by)
    top = zp - cam.FRONT_PART_H
    out = math.copysign(1, x)
    got = (ir_reach(x, y, top, out, 0), ir_reach(x, y, top, 0, 1), ir_reach(x, y, top, 0, -1))
    reached.append(got)
    ir_ok &= all(g >= want for g, want in zip(got, cam.IR_REACH))
    ir_ok &= bezel.inside((lx + out * (hole + cam.IR_WALL / 2), y, zf + cam.FRONT_T / 2))
results.append(
    true(
        ir_ok,
        "dfr1154 IR windows: beam out/up/down per LED vs IR_REACH, walled off from the camera module",
        f"{reached} want ≥ {cam.IR_REACH}",
    )
)


def tube_ok(c, size, through=True):
    """Window open through the front (if `through`) and a tube wall on all four sides from the front plate to just
    above the board."""
    x, y = cam.board_to_world(*c)
    hw, hh = size[0] / 2 + cam.WINDOW_CLEAR / 2, size[1] / 2 + cam.WINDOW_CLEAR / 2
    ok = open_column(bezel, x, y, zf - 1, zp - 0.4) if through else open_column(bezel, x, y, zi, zp - 0.4)
    zm = (zi + zp - cam.TUBE_GAP) / 2
    for px, py in ((x + hw + 0.4, y), (x - hw - 0.4, y), (x, y + hh + 0.4), (x, y - hh - 0.4)):
        ok &= bezel.inside((px, py, zm))
    return ok


results.append(true(tube_ok(cam.ALS, cam.ALS_SIZE), "dfr1154 light sensor window with tube"))
mx, my = cam.board_to_world(*cam.MIC)
mic_ok = tube_ok(cam.MIC, cam.MIC_SIZE, through=False) and open_column(bezel, mx, my, zf - 1, zi + 0.5)
mic_ok &= bezel.inside((mx + 1.2, my, zf + 0.8))  # a small hole, not a window
results.append(true(mic_ok, "dfr1154 mic hole with tube"))

# the two parts: front plate screws line up with the shell's pilots, the lip sits just inside the shell walls
join_ok = True
for x, y in cam.BEZEL_SCREWS:
    # rings around each screw axis: clear through the front plate's hole, the shell's pilot centred on it
    for k in range(8):
        cs, sn = math.cos(math.radians(45 * k)), math.sin(math.radians(45 * k))
        join_ok &= open_column(bezel, x + 1.4 * cs, y + 1.4 * sn, zf - 1, zf + cam.FRONT_T + 0.2)
        join_ok &= not shell.inside((x + 1.0 * cs, y + 1.0 * sn, zi + 3))
        join_ok &= shell.inside((x + 1.6 * cs, y + 1.6 * sn, zi + 3))
    join_ok &= open_column(shell, x, y, zi + 0.3, zi + cam.BEZEL_PILOT_DEPTH - 0.3)
inner = cam.HEX_F / 2 - cam.WALL
for phi in (0, 60, 120, 180, 240, 300):
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    zm = zi + cam.LIP_H / 2
    join_ok &= bezel.inside(((inner - cam.FIT - 0.3) * cp, (inner - cam.FIT - 0.3) * sp, zm))  # lip
    join_ok &= not bezel.inside(((inner - 0.05) * cp, (inner - 0.05) * sp, zm))  # fit gap
    join_ok &= shell.inside(((inner + 0.3) * cp, (inner + 0.3) * sp, zm))  # wall
results.append(true(join_ok, "dfr1154 front plate: screws into the shell's pilots, lip inside its walls"))

ux, _ = cam.board_to_world(cam.USB_X, cam.PCB)
uz = zb + cam.USB_Z
wall_y = (cam.HEX_F / 2 - cam.WALL / 2 - 0.5 * ux) / math.cos(math.radians(30))  # 60° wall's middle at x = ux
results.append(true(not shell.inside((ux, wall_y, uz)), "dfr1154 USB-C slot through the wall at the plug"))
w, pitch = cam.VENT
r_mid, z_mid = cam.HEX_F / 2 - cam.WALL / 2, (zb + cam.RIM_Z) / 2
vents_ok = True
for phi in (0, 120, 240):
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    for k in (-1, 0, 1):
        # across the slot along the wall: open inside its width, solid just past it
        for off, want in (
            (0, False),
            (w / 2 - 0.3, False),
            (-(w / 2 - 0.3), False),
            (w / 2 + 0.4, True),
            (-(w / 2 + 0.4), True),
        ):
            a = k * pitch + off
            vents_ok &= shell.inside((r_mid * cp - a * sp, r_mid * sp + a * cp, z_mid)) == want
    vents_ok &= shell.inside((r_mid * cp - 2 * pitch * sp, r_mid * sp + 2 * pitch * cp, z_mid))  # wall beyond them
results.append(true(vents_ok, "dfr1154 vents: three through each of the 0°, 120°, 240° walls"))

standins = sorted(cam.dfr_standins())
parts = {"DfrCup", "DfrBezel"}
found = interferences([*parts, *standins], lambda a, b: bool({a, b} & parts))
results.append(
    true(not found, "dfr1154 shell and front plate clear of each other, the board, parts and plug", f"{found}")
)
# insertion: the board and its parts (not the plug, plugged in after) leave through the shell's open end, each
# component's own outline swept from where it sits down past the front plate
sweeps, names = [], []
for name, boxes in cam.dfr_standins().items():
    if name == "DfrPlug":
        continue
    for x0, x1, y0, y1, _, z1 in boxes:
        names.append(f"Sweep{len(names)}")
        z0 = zf - 40
        sweeps.append(
            {
                "command": "solid.box",
                "params": {
                    "length": x1 - x0,
                    "width": y1 - y0,
                    "height": z1 - z0,
                    "corner": [x0, y0, z0],
                    "body_name": names[-1],
                },
            }
        )
found = interferences(["DfrCup", *names], lambda a, b: "DfrCup" in (a, b), sweeps)
results.append(true(not found, "dfr1154 board slides into the shell from its open end", f"{found}"))

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
