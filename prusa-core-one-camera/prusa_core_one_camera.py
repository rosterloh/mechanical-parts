# Prusa Core One camera case (printables.com/model/1205313, STLs not in this repo) in two variants: esp32cam, the
# original plate, cup and bracket matched to its STLs; dfr1154, a new cup for the DFRobot DFR1154 that screws onto the
# same plate. Design notes and status: README.md
# usage: python3 prusa_core_one_camera.py [outdir]
#   then: solidcraft-cli run <outdir>/prusa-core-one-camera.json --save <outdir>/prusa-core-one-camera.solidcraft
#
# Frame: the reference STLs'. Plate z 30..58 (legs up, into the printer's corner), joint plane z 30, cup front at low
# z. Seen from the front (from -z), +x is right and -Y is picture-up. Hex flats at 0°, 60°, ... (pointy in Y).
import json
import math
import os
import sys
from pathlib import Path

NAME = "prusa-core-one-camera"  # every output file is named after the part

RIM_Z = 30.0  # joint plane: plate underside, cup rim
JOINT = [(-25.91, 0.0), (12.95, 22.44), (12.95, -22.44)]  # M3 screws, one under each leg
HEX_F = 65.82  # across flats at the joint (plate sharp-cornered: 76.0 across corners)

# plate: 1.5 thick with a 1 mm 45° top chamfer; legs are a radial profile (u from the axis, z) cut to a ±18.49° wedge
PLATE_T = 1.5
PLATE_CHAMFER = 1.0
LEG_PROFILE = [(2.37, 31.5), (29.91, 31.5), (29.91, 47.57), (15.01, 58.0), (13.08, 58.0)]
LEG_HALF_ANGLE = math.degrees(math.atan(10.0 / 29.91))
MAGNET = (8.1, 3.0, (17.04, 52.92))  # pocket diameter, depth, floor centre (u, z); square to the 35° magnet face
MAGNET_N = (0.574, 0.819)  # magnet face normal (outward u, z)
SCREW_CLEAR = 3.1
SCREW_BORE = (6.0, 32.0)  # screwdriver bore through the leg: diameter, floor z


def hexagon(flats, angle0=90.0):
    """Corners of a hexagon with the given across-flats, corners at angle0 + k·60° (pointy in Y by default)."""
    r = flats / math.sqrt(3)
    return [
        (r * math.cos(math.radians(angle0 + 60 * k)), r * math.sin(math.radians(angle0 + 60 * k))) for k in range(6)
    ]


def build(d):
    """Command script for solidcraft-cli, and the index where each checked stage ends."""
    cmds, marks = [], {}

    def mark(stage):
        marks[stage] = len(cmds)

    def cyl(name, dia, base, h, axis="Z", **kw):
        cmds.append(
            {
                "command": "solid.cylinder",
                "params": {"diameter": dia, "height": h, "base": list(base), "axis": axis, "body_name": name, **kw},
            }
        )

    def prism(name, pts, plane, distance, **kw):
        """Closed polygon on `plane` (sketch.create plane param), extruded `distance`."""
        cmds.append({"command": "sketch.create", "params": {"plane": plane, "name": name + "Sk"}})
        cmds.append({"command": "sketch.line", "params": {"points": [list(p) for p in pts], "closed": True}})
        cmds.append({"command": "sketch.finish", "params": {}})
        cmds.append({"command": "solid.extrude", "params": {"distance": distance, "body_name": name, **kw}})

    def combine(target, tools, op):
        cmds.append({"command": "solid.combine", "params": {"target": target, "tools": tools, "operation": op}})

    def export(body, part):
        for fmt in ("stl", "step"):
            path = os.path.join(d, f"{NAME}-{part}.{fmt}")
            cmds.append({"command": "file.export", "params": {"path": path, "bodies": [body]}})

    # --- plate
    xy = {"origin": [0, 0, RIM_Z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism("Plate", hexagon(HEX_F), xy, PLATE_T)
    mark("e32:plate")
    top = RIM_Z + PLATE_T
    edges = [
        [HEX_F / 2 * math.cos(math.radians(a)), HEX_F / 2 * math.sin(math.radians(a)), top] for a in range(0, 360, 60)
    ]
    cmds.append({"command": "solid.chamfer", "params": {"body": "Plate", "distance": PLATE_CHAMFER, "edges": edges}})
    mark("e32:plate_chamfer")
    # one leg at 180° (u = -x), then copies at ±120°
    radial = {"origin": [0, 0, 0], "x_dir": [-1, 0, 0], "y_dir": [0, 0, 1]}
    prism("Leg", LEG_PROFILE, radial, 40, direction="symmetric")
    t = math.tan(math.radians(LEG_HALF_ANGLE)) * 40
    wedge_plane = {"origin": [0, 0, top], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism("LegWedge", [(0, 0), (-40, t), (-40, -t)], wedge_plane, 30)
    combine("Leg", ["LegWedge"], "intersect")
    mark("e32:leg")
    dia, depth, (u, z) = MAGNET
    nu, nz = MAGNET_N
    cyl("LegMagnet", dia, (-u, 0, z), depth + 2, axis=[-nu, 0, nz], operation="cut", targets=["Leg"])
    mark("e32:magnet")
    bx, by = JOINT[0]
    cyl("LegBore", SCREW_BORE[0], (bx, by, SCREW_BORE[1]), 40, operation="cut", targets=["Leg"])
    mark("e32:bore")
    for i, a in enumerate(("120 deg", "-120 deg")):
        cmds.append(
            {"command": "solid.move", "params": {"bodies": ["Leg"], "axis": [0, 0, 1], "angle": a, "copy": True}}
        )
        cmds.append({"command": "body.rename", "params": {"body": "Leg (2)", "name": f"Leg{i + 1}"}})
    combine("Plate", ["Leg", "Leg1", "Leg2"], "join")
    mark("e32:plate_legs")
    for x, y in JOINT:
        cyl("PlateHole", SCREW_CLEAR, (x, y, RIM_Z - 1), PLATE_T + 2, operation="cut", targets=["Plate"])
    mark("e32:plate_holes")
    export("Plate", "plate")
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    )
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
