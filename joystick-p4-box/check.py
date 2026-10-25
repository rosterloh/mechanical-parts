# Verifies joystick_p4_box.py: volume each finishing step should change, and the fit of joystick, board and base.
# usage: python3 check.py
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import joystick_p4_box as box

SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")
TMP = tempfile.mkdtemp(prefix=f"{box.NAME}-check-")
cmds, marks = box.build(TMP)


def bodies_after(stage):
    script, res = os.path.join(TMP, f"{stage}.json"), os.path.join(TMP, f"{stage}.r.json")
    Path(script).write_text(json.dumps({"commands": cmds[: marks[stage]]}))
    subprocess.run([SC, "eval", script, "--json-out", res], check=True, capture_output=True)
    return {b["name"]: b for b in json.loads(Path(res).read_text())["bodies"]}


def close(got, want, tol, what):
    ok = abs(got - want) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {what}: got {got:.2f}, want {want:.2f} ±{tol:.2f}")
    return ok


def true(cond, what, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {what} {detail}")
    return cond


# --- volumes: each pick must hit its edge
v = {s: bodies_after(s) for s in marks}


def dv(body, a, b):
    return v[b][body]["volume_mm3"] - v[a][body]["volume_mm3"]


k = 1 - math.pi / 4
height = box.PLATE + box.H_IN + box.PANEL
holes = math.pi * (box.JOY_HOLE / 2) ** 2 * box.PANEL + 4 * math.pi * (box.JOY_SCREW_D / 2) ** 2 * box.PANEL
bb = v["joy_holes"]["Shell"]["bbox"]
results = [
    close(
        dv("Shell", "shell_layout", "groove"),
        -2 * box.X_END * (box.DOVE * (box.PLATE + box.C) - box.DOVE**2 / 2),
        1.0,
        "dovetail grooves",
    ),
    close(
        dv("Shell", "groove", "shell_corners"), -k * (2 * 3.0**2 + 2 * 1.0**2) * height, 0.5, "vertical corners r3 / r1"
    ),
    true(
        dv("Shell", "shell_corners", "panel_chamfer") < -5,
        "panel top chamfer",
        f"({dv('Shell', 'shell_corners', 'panel_chamfer'):.2f})",
    ),
    true(
        -60 < dv("Shell", "panel_chamfer", "joy_holes") + holes < -10,
        "joystick holes, countersinks beyond the plain holes",
        f"({dv('Shell', 'panel_chamfer', 'joy_holes') + holes:.2f})",
    ),
]
win_area = sum((y1 - y0) * (z1 - z0) for _, _, y0, y1, z0, z1 in box.windows().values())
results += [
    close(
        dv("Base", "base_layout", "plate_bevel"),
        -2 * (box.X_END - box.C) * box.DOVE**2 / 2,
        0.5,
        "plate dovetail bevel",
    ),
    close(dv("Base", "plate_bevel", "windows"), -box.END_T * win_area, 1.0, "port windows"),
    close(
        dv("Base", "windows", "pilots"),
        -4 * math.pi * (box.PILOT_D / 2) ** 2 * box.PILOT_DEPTH,
        0.5,
        "post pilot holes",
    ),
    close(dv("Shell", "pilots", "detent"), 2 * 2 / 3 * math.pi * (box.BUMP_D / 2) ** 3, 0.1, "detent bumps"),
    close(dv("Base", "pilots", "detent"), -2 * 2 / 3 * math.pi * (box.DIMPLE_D / 2) ** 3, 0.1, "detent dimples"),
    true(box.DETENT_X > box.X_END - box.END_T, "detent in the base end wall, where the shell walls are free to flex"),
]
for i, (lo, hi) in enumerate(((-box.T, box.X_END), (-box.T, box.W_IN + box.T), (0, height))):
    results.append(close(bb["min"][i], lo, 1e-6, f"shell bbox min {'xyz'[i]}"))
    results.append(close(bb["max"][i], hi, 1e-6, f"shell bbox max {'xyz'[i]}"))


# --- fit: the proxies are solids, so inspect.interference sees them (touching faces don't count)
def interferences(extra, bodies):
    script, res = os.path.join(TMP, "fit.json"), os.path.join(TMP, "fit.r.json")
    probe = {"command": "inspect.interference", "params": {"bodies": bodies}}
    Path(script).write_text(json.dumps({"commands": cmds + extra + [probe]}))
    subprocess.run([SC, "run", script, "--results", "--json-out", res, "--quiet"], check=True, capture_output=True)
    r = json.loads(Path(res).read_text())[-1]
    if r["unchecked"]:
        sys.exit(f"interference not checked: {r['unchecked']}")
    return r["interferences"]


def swept(name, b, reach):
    """Box b stretched in +X to `reach`: everything it passes through when the base slides out."""
    x0, _, y0, y1, z0, z1 = b
    return {
        "command": "solid.box",
        "params": {
            "length": reach - x0,
            "width": y1 - y0,
            "height": z1 - z0,
            "corner": [x0, y0, z0],
            "body_name": name,
        },
    }


def pairs(found):
    return [(i["a"], i["b"], round(i["volume_mm3"], 2)) for i in found]


units = list(box.proxies()) + list(box.ports())
found = interferences([], ["Shell", "Base", *units, *box.JOY_BELOW, *box.JOY_ABOVE])
found = [i for i in found if not {i["a"], i["b"]} <= set(box.JOY_BELOW + box.JOY_ABOVE)]  # model's own parts touch
results.append(true(not found, "no clash between shell, base, joystick, board, header and ports", f"{pairs(found)}"))

# a square pin down each panel screw hole must drop into the D400B body's Ø1.6 pilot, not hit its top face
# (square: a round pin nearly coaxial with the pilot makes the kernel's intersect fail; its 1.56 diagonal leaves 0.02)
s = 1.1
pins = [
    {
        "command": "solid.box",
        "params": {
            "length": s,
            "width": s,
            "height": 3,
            "center": [box.JOY[0] + sx * box.JOY_SQ / 2, box.JOY[1] + sy * box.JOY_SQ / 2, box.PLATE + box.H_IN - 1.5],
            "body_name": f"pin{sx}{sy}",
        },
    }
    for sx in (-1, 1)
    for sy in (-1, 1)
]
found = interferences(pins, ["Fillet1"] + [p["params"]["body_name"] for p in pins])
results.append(true(not found, "panel screw holes line up with the joystick's pilots", f"{pairs(found)}"))

plugs = [swept(f"plug{n}", p, box.X_END + 10) for n, p in box.ports().items()]
found = interferences(plugs, ["Base"] + [p["params"]["body_name"] for p in plugs])
results.append(true(not found, "plugs reach every port through its window", f"{pairs(found)}"))
# jacks sit back from the outer face, so a plug's overmold must enter the window
p = box.ports()
results.append(close(p["USB"][1], box.X_END, 0.05, "USB stack reaches the outer face (overmold clear of the wall)"))
for n in ("RJ45", "TF"):
    results.append(
        true(box.X_END - p[n][1] <= 2.0, f"{n} face at most 2 mm behind the outer face", f"({box.X_END - p[n][1]:.2f})")
    )

pull = [{"command": "solid.move", "params": {"bodies": ["Base"], "translate": [1, 0, 0]}}]
found = interferences(pull, ["Shell", "Base"])
at_detent = all(  # one pair covers both detents, so test its extent, not its centre
    box.DETENT_X - 1 < i["bbox"]["min"][0] and i["bbox"]["max"][0] < box.DETENT_X + 2 for i in found
)
results.append(true(found and at_detent, "base pulled 1 mm out is held, by the detents only", f"{pairs(found)}"))
sys.exit(0 if all(results) else 1)
