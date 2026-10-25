# Verifies rebot_psu_covers.py: volume each feature step should change, the Fusion revision it was ported from,
# and the fit on Mean Well's PSU model.
# usage: python3 check.py
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import rebot_psu_covers as p

SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")
TMP = tempfile.mkdtemp(prefix=f"{p.NAME}-check-")
cmds, marks = p.build(TMP)
OURS = ["AcCap", "DcCap", "Cover", "CoverDc"]


def bodies_after(n):
    script, res = os.path.join(TMP, f"{n}.json"), os.path.join(TMP, f"{n}.r.json")
    Path(script).write_text(json.dumps({"commands": cmds[:n]}))
    subprocess.run([SC, "eval", script, "--json-out", res], check=True, capture_output=True)
    return {b["name"]: b for b in json.loads(Path(res).read_text())["bodies"]}


def close(got, want, tol, what):
    ok = abs(got - want) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {what}: got {got:.2f}, want {want:.2f} ±{tol:.2f}")
    return ok


def true(cond, what, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {what} {detail}")
    return cond


# --- volumes: each cut must hit material
v = {s: bodies_after(n) for s, n in marks.items()}
final = bodies_after(len(cmds))


def dv(body, a, b):
    return v[b][body]["volume_mm3"] - v[a][body]["volume_mm3"]


r, R, h = p.BORE_D / 2, p.HEAD_D / 2, (p.HEAD_D - p.BORE_D) / 2  # 90° countersink: depth = radius step
frustum = math.pi * h / 3 * (R * R + R * r + r * r) - math.pi * r * r * h
side_hole = math.pi * r * r * p.MOUNT_THICKNESS + frustum
vents = 3 * p.WALL * 40 * (2 * len(p.SIDE_VENTS) + len(p.ROOF_VENTS))
iec = (
    p.WALL * (p.IEC_BODY_W + 2 * p.IEC_FIT) * (p.IEC_BODY_H + 2 * p.IEC_FIT)
    + 2 * math.pi * (p.IEC_SCREW_D / 2) ** 2 * p.WALL
    + len(p.AC_VENTS) * 46 * 3 * p.WALL
)
cover_holes = 2 * (math.pi * r * r * p.SLIDE_THICKNESS + frustum)
results = []
for k, cap in (("ac", "AcCap"), ("dc", "DcCap")):
    results += [
        close(dv(cap, f"{k}_layout", f"{k}_holes"), -4 * side_hole, 2.0, f"{cap} side M4 countersinks"),
        close(dv(cap, f"{k}_holes", f"{k}_vents"), -vents, 1.0, f"{cap} side and roof vents"),
    ]
results.append(close(dv("AcCap", "ac_vents", "iec"), -iec, 1.0, "IEC opening, bolt holes and front vents"))
x0, x1, y0, y1, z0, z1 = p.XT60_WINDOW
bare = len(p.DC_PORT_OFFSETS) * p.WALL * (y1 - y0) * (z1 - z0)  # windows cut through the plain wall
patches = dv("DcCap", "dc_vents", "xt60") + len(p.DC_VENTS) * 94 * 3 * p.WALL + bare
results.append(
    true(patches > 1000, "XT60 patches joined: Seeed's panel and bosses fill the windows", f"({patches:.2f})")
)
cover0 = (p.OVERLAP + p.CAP_DEPTH - p.WALL - 0.3) * 2 * (p.IW - p.SLIDE_SIDE_GAP) * p.SLIDE_THICKNESS
results.append(close(v["cover"]["Cover"]["volume_mm3"], cover0 - cover_holes, 2.0, "cover underside M4 countersinks"))

# --- regression: Fusion "RebotFit" revision 4 exports (inspect.compare found them identical within 0.002 mm)
for body, want in (("AcCap", 96009.4), ("DcCap", 97350.6), ("Cover", 43961.3)):
    stage = {"AcCap": "iec", "DcCap": "xt60", "Cover": "cover"}[body]  # before the print tuning
    results.append(close(v[stage][body]["volume_mm3"], want, 0.5, f"{body} volume matches Fusion revision 4"))

# --- print tuning
yo, zb, zt = p.IW + p.WALL, p.BASE_Z, p.ROOF + p.WALL
foot = p.FOOT**2 / 2  # chamfer section
front = 2 * (2 * (yo - p.CORNER_R) + (zt - zb - 2 * p.CORNER_R)) + 2 * math.pi * p.CORNER_R  # bed-face perimeter
iec_edges = 2 * (p.IEC_BODY_W + p.IEC_BODY_H + 4 * p.IEC_FIT)
for k, cap, before, extra in (("ac", "AcCap", "iec", iec_edges), ("dc", "DcCap", "xt60", 0)):
    corners = -4 * (1 - math.pi / 4) * p.CORNER_R**2 * (p.CAP_DEPTH + p.OVERLAP)
    results += [
        close(dv(cap, before, f"{k}_corners"), corners, 0.5, f"{cap} r{p.CORNER_R:g} long edges"),
        true(
            -15 < dv(cap, f"{k}_corners", f"{k}_leadin") < -8,
            f"{cap} rail and lip lead-ins",
            f"({dv(cap, f'{k}_corners', f'{k}_leadin'):.2f})",
        ),
        close(dv(cap, f"{k}_leadin", f"{k}_foot"), -foot * (front + extra), 1.0, f"{cap} elephant's foot chamfer"),
    ]
cover_edges = 2 * (p.OVERLAP + p.CAP_DEPTH - p.WALL - 0.3 + 2 * (p.IW - p.SLIDE_SIDE_GAP))
results.append(close(dv("Cover", "cover", "cover_foot"), -foot * cover_edges, 0.5, "cover elephant's foot chamfer"))
for part, body, height in (
    ("ac-cap", "AcCap", p.CAP_DEPTH + p.OVERLAP),
    ("dc-cap", "DcCap", p.CAP_DEPTH + p.OVERLAP),
    ("cover", "Cover", 4.0),
):
    b = v[f"print_{part}"][f"{body}Print"]["bbox"]
    results.append(close(b["min"][2], 0, 1e-6, f"{part} STL on the bed"))
    results.append(close(b["max"][2], height, 1e-6, f"{part} STL print height"))
    results.append(true(f"{body}Print" not in final, f"{part} print copy removed after export"))

bb = final["DcCap"]["bbox"]
results.append(close(bb["max"][0], p.PSU_LENGTH + p.CAP_DEPTH, 1e-6, "DC cap turned onto the DC end"))


# --- fit on the Mean Well model
def interferences(extra, bodies, mine=OURS):
    script, res = os.path.join(TMP, "fit.json"), os.path.join(TMP, "fit.r.json")
    probe = {"command": "inspect.interference", "params": {"bodies": bodies}}
    Path(script).write_text(json.dumps({"commands": cmds + extra + [probe]}))
    subprocess.run([SC, "run", script, "--results", "--json-out", res, "--quiet"], check=True, capture_output=True)
    out = json.loads(Path(res).read_text())[-1]
    # the PSU model's own screws and rivets defeat the kernel against its chassis; only ours must be checked
    unchecked = [u for u in out["unchecked"] if {u["a"], u["b"]} & set(mine)]
    if unchecked:
        sys.exit(f"interference not checked: {unchecked}")
    return out["interferences"]


def pairs(found):
    return [(i["a"], i["b"], round(i["volume_mm3"], 2)) for i in found]


# 表面1 ("surface 1") is the model's open fan sheet, which reaches outside the chassis; not a solid
psu = [n for n in final if n not in OURS and n != "表面1"]
found = [i for i in interferences([], OURS + psu) if {i["a"], i["b"]} & set(OURS)]
results.append(true(not found, "no clash between caps, covers and the PSU model", f"{pairs(found)}"))

# pins through every cap and cover hole, 3 mm into the chassis, must drop into its M4 holes, not hit sheet metal
# (square: a round pin coaxial with a modelled hole makes the kernel's intersect fail; its 2.8 diagonal fits the model's Ø3.1 holes)
S = 2.0
pins = []  # (centre, size)
for x in (p.MOUNT_INSET, p.PSU_LENGTH - p.MOUNT_INSET):
    for s in (-1, 1):
        y0, y1 = p.PSU_WIDTH / 2 - 3, p.IW + p.MOUNT_THICKNESS
        for z in p.MOUNT_HEIGHTS:
            pins.append(((x, s * (y0 + y1) / 2, z), (S, y1 - y0, S)))
        pins.append(((x, s * p.UNDER_Y, (p.SLIDE_BOTTOM + 3) / 2), (S, S, 3 - p.SLIDE_BOTTOM)))
extra = [
    {
        "command": "solid.box",
        "params": {"length": l, "width": w, "height": h, "center": list(c), "body_name": f"pin{i}"},
    }
    for i, (c, (l, w, h)) in enumerate(pins)
]
names = [f"pin{i}" for i in range(len(pins))]
found = [i for i in interferences(extra, names + OURS + psu, OURS + names) if {i["a"], i["b"]} & set(names)]
results.append(true(not found, "all 12 fixing holes line up with the chassis's M4 holes", f"{pairs(found)}"))

# the cover slides in from the cap's open end and the rails hold it down
slide = [{"command": "solid.move", "params": {"bodies": ["Cover"], "translate": [30, 0, 0]}}]
found = interferences(slide, ["AcCap", "Cover"])
results.append(true(not found, "cover slides along its rails", f"{pairs(found)}"))
drop = [{"command": "solid.move", "params": {"bodies": ["Cover"], "translate": [0, 0, -0.5]}}]
found = interferences(drop, ["AcCap", "Cover"])
results.append(true(bool(found), "rails hold the cover up (dropped 0.5 mm it hits them)", f"{pairs(found)}"))
sys.exit(0 if all(results) else 1)
