# reBot B601-RS power supply covers, adapted from Seeed's design to a Mean Well HRPG-600-48.
# Two end caps (IEC inlet at the AC end, two XT60 at the DC end) and two identical sliding bottom covers.
# Port of the Fusion script "RebotFit" revision 4 (2026-09-30). Design notes and status: README.md
# usage: python3 rebot_psu_covers.py [outdir]
#   then: solidcraft-cli run <outdir>/rebot-psu-covers.json --save <outdir>/rebot-psu-covers.solidcraft
#
# Frame: PSU chassis x 0..218 (AC end at x=0, DC at x=218), y -52.5..52.5, z 0..63.5 (Case 977A drawing).
# Each cap is built at the AC end (x -65..42.5); the DC cap is then turned 180° about Z and moved to x=218.
import json
import os
import sys
from pathlib import Path

NAME = "rebot-psu-covers"  # every output file is named after the part
HERE = os.path.dirname(os.path.abspath(__file__))

PSU_LENGTH, PSU_WIDTH, PSU_HEIGHT = 218.0, 105.0, 63.5
CLEARANCE, TOP_CLEARANCE, WALL = 1.0, 1.5, 3.2
CAP_DEPTH, OVERLAP = 65.0, 42.5  # cap reaches 65 beyond the chassis end and 42.5 along it
SLIDE_THICKNESS, SLIDE_CLEARANCE = 4.0, 0.6
SLIDE_TOP, SLIDE_SIDE_GAP = -1.2, 0.4  # 1.2 mm under the chassis for shims
SLIDE_BOTTOM = SLIDE_TOP - SLIDE_THICKNESS
RAIL_TOP = SLIDE_BOTTOM - SLIDE_CLEARANCE / 2
BASE_Z = RAIL_TOP - WALL
IW = PSU_WIDTH / 2 + CLEARANCE  # inner half-width
ROOF = PSU_HEIGHT + TOP_CLEARANCE  # roof underside
MOUNT_THICKNESS, BORE_D, HEAD_D = 4.0, 4.5, 8.9  # M4 countersunk, 90°
PAD_R, PAD_FLARE = 7.35, 0.85  # 45° flare from the wall out to the 4 mm screw seat
MOUNT_INSET, MOUNT_HEIGHTS = 32.8, (12.5, 50.8)
UNDER_Y = 31.75  # underside M4 rows
DC_PORT_OFFSETS = (-23.0, 23.0)  # 46 mm pitch
IEC_BODY_W, IEC_BODY_H, IEC_FIT = 27.2, 47.0, 0.3  # user-measured replacement inlet; fit allowance per edge
IEC_Y, IEC_Z = -27.0, 30.0
IEC_SCREW_PITCH, IEC_SCREW_D = 40.0, 4.5
# Seeed "RS-power-Top Cover" placed so its XT60 patch lands on the cap's front face (Fusion: rows of R, then t)
SEEED_MATRIX = [-1, 0, 0, 0, 0, 0, 1, -35.49014, 0, 1, 0, -5.45135]
XT60_WINDOW = (-65.0, -56.0, -18.49014, 18.50986, 4.54865, 25.54865)  # patch kept from the Seeed part, at y offset 0
# Mean Well HRPG/MSP-600 STEP: AC end to x=0, centred on width (x = 263.08 - sx, y = 114.86 - sy)
PSU_MATRIX = [-1, 0, 0, 263.077829, 0, -1, 0, 114.857686, 0, 0, 1, 0]

# print tuning for PETG, on top of the Fusion revision
CORNER_R = 3.0  # long outer edges, vertical when printing: less corner lift
FOOT = 0.5  # elephant's foot chamfer on bed faces
LEAD_IN = 1.0  # rail and lip ends, so the cover finds its slot

SIDE_VENTS = range(8, 60, 6)
ROOF_VENTS = range(-45, 46, 6)
AC_VENTS = range(5, 62, 6)
DC_VENTS = range(31, 62, 6)


def build(d):
    """Command script for solidcraft-cli, and the index where each checked stage ends."""
    cmds, marks = [], {}

    def box(name, x0, x1, y0, y1, z0, z1, **kw):
        cmds.append(
            {
                "command": "solid.box",
                "params": {
                    "length": x1 - x0,
                    "width": y1 - y0,
                    "height": z1 - z0,
                    "corner": [x0, y0, z0],
                    "body_name": name,
                    **kw,
                },
            }
        )

    def cut(target, *b):
        box("cut", *b, operation="cut", targets=[target])

    def mark(stage):
        marks[stage] = len(cmds)

    def cap(cap_name, kind):
        box(cap_name, -CAP_DEPTH, OVERLAP, -IW - WALL, IW + WALL, BASE_Z, ROOF + WALL)
        cut(cap_name, -CAP_DEPTH + WALL, OVERLAP + 1, -IW, IW, BASE_Z - 1, ROOF)
        tools = []
        for side in (-1, 1):
            yl, yh = sorted((side * IW, side * (IW - 3)))
            box(f"{cap_name}rail{side}", -62.5, OVERLAP, yl, yh, BASE_Z, RAIL_TOP)  # carries the sliding cover
            z = SLIDE_TOP + SLIDE_CLEARANCE / 2
            box(f"{cap_name}lip{side}", -62.5, -19, yl, yh, z, z + WALL)  # holds it down, clear of the terminals
            tools += [f"{cap_name}rail{side}", f"{cap_name}lip{side}"]
            for z in MOUNT_HEIGHTS:
                pad = f"{cap_name}pad{side}{z}"
                y0 = side * (IW + MOUNT_THICKNESS - 2 * PAD_FLARE)  # buried in the wall up to the flare
                cmds.append(
                    {
                        "command": "solid.cylinder",
                        "params": {
                            "radius": PAD_R,
                            "height": 2 * PAD_FLARE,
                            "base": [MOUNT_INSET, y0, z],
                            "axis": [0, side, 0],
                            "operation": "new",
                            "body_name": pad,
                        },
                    }
                )
                y1 = side * (IW + MOUNT_THICKNESS)
                cmds.append(
                    {
                        "command": "solid.chamfer",
                        "params": {"body": pad, "distance": PAD_FLARE, "edges": [[MOUNT_INSET + PAD_R, y1, z]]},
                    }
                )
                tools.append(pad)
        cmds.append({"command": "solid.combine", "params": {"target": cap_name, "tools": tools, "operation": "join"}})
        mark(f"{kind}_layout")
        for side in (-1, 1):
            for z in MOUNT_HEIGHTS:
                cmds.append(
                    {
                        "command": "solid.hole",
                        "params": {
                            "position": [MOUNT_INSET, side * (IW + MOUNT_THICKNESS), z],
                            "diameter": BORE_D,
                            "depth": MOUNT_THICKNESS + 2,  # not through all: that reaches the far wall
                            "type": "countersink",
                            "cs_diameter": HEAD_D,
                            "cs_angle": 90,
                            "targets": [cap_name],
                        },
                    }
                )
        mark(f"{kind}_holes")
        for side in (-1, 1):  # outside the chassis, clear of the terminal end planes
            y0, y1 = sorted((side * (IW - 1), side * (IW + WALL + 1)))
            for z in SIDE_VENTS:
                cut(cap_name, -55, -15, y0, y1, z, z + 3)
        for y in ROOF_VENTS:
            cut(cap_name, -55, -15, y, y + 3, ROOF - 1, ROOF + WALL + 1)
        mark(f"{kind}_vents")

    def chamfer(body, dist, edges):
        cmds.append({"command": "solid.chamfer", "params": {"body": body, "distance": dist, "edges": edges}})

    def tune(cap_name, kind, front_edges=()):
        """Print tuning, after the Fusion geometry: the cap prints standing on its front face (x=-65)."""
        yo, zb, zt = IW + WALL, BASE_Z, ROOF + WALL
        edges = [[0, s * yo, z] for s in (-1, 1) for z in (zb, zt)]
        cmds.append({"command": "solid.fillet", "params": {"body": cap_name, "radius": CORNER_R, "edges": edges}})
        mark(f"{kind}_corners")
        for s in (-1, 1):  # cover enters at the open end: ramps down off the rail top, in off its inner face
            chamfer(
                cap_name,
                LEAD_IN,
                [[OVERLAP, s * (IW - 1.5), RAIL_TOP], [OVERLAP, s * (IW - 3), (BASE_Z + RAIL_TOP) / 2]],
            )
            lip = SLIDE_TOP + SLIDE_CLEARANCE / 2
            chamfer(cap_name, LEAD_IN, [[-19, s * (IW - 1.5), lip], [-19, s * (IW - 3), lip + WALL / 2]])
        mark(f"{kind}_leadin")
        x, k = -CAP_DEPTH, CORNER_R * (1 - 0.5**0.5)  # k: fillet arc midpoint's inset from the sharp corner
        edges = [[x, 0, zb], [x, 0, zt], [x, -yo, 30], [x, yo, 30]]
        edges += [[x, s * (yo - k), z + (k if z == zb else -k)] for s in (-1, 1) for z in (zb, zt)]
        chamfer(cap_name, FOOT, edges + list(front_edges))
        mark(f"{kind}_foot")

    # --- AC cap: measured replacement IEC inlet, straight holes for through-bolts and nuts
    cap("AcCap", "ac")
    hw, hh = IEC_BODY_W / 2 + IEC_FIT, IEC_BODY_H / 2 + IEC_FIT
    cut("AcCap", -66, -61, IEC_Y - hw, IEC_Y + hw, IEC_Z - hh, IEC_Z + hh)
    for s in (-1, 1):
        cmds.append(
            {
                "command": "solid.hole",
                "params": {
                    "position": [-CAP_DEPTH, IEC_Y + s * IEC_SCREW_PITCH / 2, IEC_Z],
                    "diameter": IEC_SCREW_D,
                    "depth": WALL + 1,
                    "targets": ["AcCap"],
                },
            }
        )
    for z in AC_VENTS:  # front vents start at y=2, leaving the inlet flange on solid panel
        cut("AcCap", -66, -61, 2, 48, z, z + 3)
    mark("iec")
    y0, y1, z0, z1 = IEC_Y - hw, IEC_Y + hw, IEC_Z - hh, IEC_Z + hh
    iec = [[-CAP_DEPTH, y0, IEC_Z], [-CAP_DEPTH, y1, IEC_Z], [-CAP_DEPTH, IEC_Y, z0], [-CAP_DEPTH, IEC_Y, z1]]
    tune("AcCap", "ac", iec)  # the opening's bed edges too: its fit allowance is only 0.3

    # --- DC cap: two copies of Seeed's XT60 aperture, fixing holes and nut pockets, swapped into the front face
    cap("DcCap", "dc")
    x0, x1, y0, y1, z0, z1 = XT60_WINDOW
    for i, off in enumerate(DC_PORT_OFFSETS):
        cmds.append(
            {
                "command": "file.insert_step",
                "params": {
                    "path": os.path.join(HERE, "units", "seeed-top-cover.stp"),
                    "name": f"Seeed{i}",
                    "matrix": SEEED_MATRIX[:7] + [SEEED_MATRIX[7] + off] + SEEED_MATRIX[8:],
                },
            }
        )
        cmds.append({"command": "body.rename", "params": {"body": "RS-POWER-00", "name": f"xt60_{i}"}})
        box(f"keep{i}", x0, x1, y0 + off, y1 + off, z0, z1)
        cmds.append(
            {
                "command": "solid.combine",
                "params": {"target": f"xt60_{i}", "tools": [f"keep{i}"], "operation": "intersect"},
            }
        )
        cut("DcCap", x0 - 1, x1 + 1, y0 + off, y1 + off, z0, z1)
        cmds.append(
            {"command": "solid.combine", "params": {"target": "DcCap", "tools": [f"xt60_{i}"], "operation": "join"}}
        )
    for z in DC_VENTS:
        cut("DcCap", -66, -61, -47, 47, z, z + 3)
    mark("xt60")
    tune("DcCap", "dc")
    cmds.append({"command": "solid.move", "params": {"bodies": ["DcCap"], "axis": [0, 0, 1], "angle": "180 deg"}})
    cmds.append({"command": "solid.move", "params": {"bodies": ["DcCap"], "translate": [PSU_LENGTH, 0, 0]}})

    # --- sliding cover: one design, print two; slides in from the cap's open end before the cap is fixed
    box("Cover", -CAP_DEPTH + WALL + 0.3, OVERLAP, -IW + SLIDE_SIDE_GAP, IW - SLIDE_SIDE_GAP, SLIDE_BOTTOM, SLIDE_TOP)
    for y in (-UNDER_Y, UNDER_Y):
        cmds.append(
            {
                "command": "solid.hole",
                "params": {
                    "position": [MOUNT_INSET, y, SLIDE_BOTTOM],
                    "diameter": BORE_D,
                    "type": "countersink",
                    "cs_diameter": HEAD_D,
                    "cs_angle": 90,
                    "targets": ["Cover"],
                },
            }
        )
    mark("cover")
    cx0, cy = -CAP_DEPTH + WALL + 0.3, IW - SLIDE_SIDE_GAP  # prints flat on its countersunk face; edges ride the rails
    edges = [[cx0, 0, SLIDE_BOTTOM], [OVERLAP, 0, SLIDE_BOTTOM], [0, -cy, SLIDE_BOTTOM], [0, cy, SLIDE_BOTTOM]]
    chamfer("Cover", FOOT, edges)
    mark("cover_foot")

    # context only, not exported: the DC end's cover and Mean Well's PSU model
    cmds.append(
        {"command": "solid.move", "params": {"bodies": ["Cover"], "axis": [0, 0, 1], "angle": "180 deg", "copy": True}}
    )
    cmds.append({"command": "body.rename", "params": {"body": "Cover (2)", "name": "CoverDc"}})
    cmds.append({"command": "solid.move", "params": {"bodies": ["CoverDc"], "translate": [PSU_LENGTH, 0, 0]}})
    cmds.append(
        {
            "command": "file.insert_step",
            "params": {"path": os.path.join(HERE, "units", "hrpg-600.stp"), "name": "HRPG-600", "matrix": PSU_MATRIX},
        }
    )
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["AcCap", "DcCap"], "color": "#e07020"}})
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["Cover", "CoverDc"], "color": "#404040"}})
    # STEP in assembly position; STL in print position (caps on their front face, cover flat), via throwaway copies
    turns = {"AcCap": ([0, 1, 0], "-90 deg", CAP_DEPTH), "DcCap": ([0, 1, 0], "90 deg", PSU_LENGTH + CAP_DEPTH)}
    for body, part in (("AcCap", "ac-cap"), ("DcCap", "dc-cap"), ("Cover", "cover")):
        cmds.append(
            {"command": "file.export", "params": {"path": os.path.join(d, f"{NAME}-{part}.step"), "bodies": [body]}}
        )
        printed = f"{body}Print"
        if body in turns:
            axis, angle, lift = turns[body]
            cmds.append(
                {"command": "solid.move", "params": {"bodies": [body], "axis": axis, "angle": angle, "copy": True}}
            )
        else:
            lift = -SLIDE_BOTTOM
            cmds.append({"command": "solid.move", "params": {"bodies": [body], "translate": [0, 0, 0], "copy": True}})
        cmds.append({"command": "body.rename", "params": {"body": f"{body} (2)", "name": printed}})
        cmds.append({"command": "solid.move", "params": {"bodies": [printed], "translate": [0, 0, lift]}})
        mark(f"print_{part}")
        cmds.append(
            {"command": "file.export", "params": {"path": os.path.join(d, f"{NAME}-{part}.stl"), "bodies": [printed]}}
        )
        cmds.append({"command": "solid.remove", "params": {"bodies": [printed]}})
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
