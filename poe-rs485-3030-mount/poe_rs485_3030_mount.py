# M5Stack Unit PoE-P4 + Unit RS485-ISO mount for 30x30 slot-8 extrusion (M6 drop-in T-nuts).
# Print plate-down, no supports. Design notes and status: README.md
# usage: python3 poe_rs485_3030_mount.py [outdir]
#   then: solidcraft-cli run <outdir>/poe-rs485-3030-mount.json --save <outdir>/poe-rs485-3030-mount.solidcraft
#
# Frame: plate top z=0, extrusion along X under y=12. PoE x -0.7..63.3, y 0..24 (RJ45 + USB-C on the +X face,
# Grove on -Y, button on +Y). RS485 flat, cover up, beyond the PoE's -X end with its Grove end facing it.
import json
import math
import os
import sys
from pathlib import Path

NAME = "poe-rs485-3030-mount"  # every output file is named after the part

C, T, PLATE = 0.3, 3.0, 5.0  # fit clearance, wall, plate thickness
GAP = 20.0  # PoE end stop to RS485 end: Grove plug and cable loop
POE = {"x0": -0.7, "x1": 63.3, "y0": 0.0, "y1": 24.0, "top": 20.2}
WALL_H = 8.0
TAB_X = (10.0, 54.0)  # snap tabs, clear of the Grove, button and RJ45 end
TAB_W, TAB_T, HOOK, HOOK_H, SLOT = 10.0, 2.0, 0.8, 1.5, 1.0
TAB_ROOT_R = 0.9  # outer face: the plate ledge is 1 mm
TAB_ROOT_R_IN = 0.5  # inner face is the tension side; the PoE's rounded bottom edge leaves room for 0.5
GROVE = (37.4 - 9, 37.4 + 9)  # front-wall gap: Grove port plus room for the cable to bend out
BUTTON = (36.0, 46.0)  # back-wall gap: side button
BOSS_H, BOSS_D = 3.0, 9.0
# LEGO-style pegs: the shaft runs up the RS485's Ø4.85 bore, the ridge snaps into its top Ø6.2 counterbore (z 10.1-11)
PEG_D, RIDGE_D, RIDGE_Z0, RIDGE_H, RIDGE_CHAMFER = 4.8, 5.3, 10.2, 0.7, 0.45
PEG_SLOT_W, PEG_SLOT_Z0 = 1.0, 5.0  # slot lets the ridge squeeze through the bore
X_LOCK = (
    2.8,
    5.4,
    3.2,
    20.8,
    2.0,
)  # rib in the PoE's through-slot across its base (x 2.5-5.7, y 2.75-21.25): stops it sliding along X
RS_PAD = (-78.5, -76.5, 2.5, 21.5)  # under the RS485's far end, which is flat at z 3 there
CORNER_R, CORNER_R_RJ45 = 3.0, 1.0  # the +X corners run up the 3 mm walls, so they get less
BOTTOM_CHAMFER = 0.5  # elephant's foot
EXT_LEN = 200.0  # length of extrusion shown for context


def wall_segments(x0, x1, gaps):
    """Spans of [x0, x1] left after removing gaps, which may overlap or be unsorted."""
    segs, x = [], x0
    for g0, g1 in sorted(gaps):
        if g0 > x:
            segs.append((x, min(g0, x1)))
        x = max(x, g1)
    if x < x1:
        segs.append((x, x1))
    return segs


assert wall_segments(-4, 63.3, [(4, 16), (48, 60), (28.4, 46.4)]) == [(-4, 4), (16, 28.4), (46.4, 48), (60, 63.3)]
assert wall_segments(0, 10, [(8, 12), (-2, 1)]) == [(1, 8)]

fy0, by1 = -C - T, POE["y1"] + C + T  # plate y extent
xs0 = POE["x0"] - C - T  # outer face of the -X end stop
xe = POE["x1"]  # nothing at or beyond the RJ45/USB-C face
rs_x1 = xs0 - GAP  # RS485 Grove end
px0 = rs_x1 - 56 - 22  # plate -X end: M6 head clear of the RS485 terminal wires
PLATE_PERIMETER = 2 * (xe - px0 + by1 - fy0) - 2 * (2 - math.pi / 2) * (CORNER_R + CORNER_R_RJ45)


def place_poe(p):
    return (p[0], p[1] - 0.75, p[2] + 13.24)


def place_rs485(p):
    return (-p[1] + rs_x1, p[0] + 12, p[2] + 8 + BOSS_H)  # flat, Grove end (native y=0) facing +X


def lego():
    return [place_rs485((s, 12, 0))[:2] for s in (-8, 8)]


def build(d):
    """Command script for solidcraft-cli, and the index where each checked stage ends."""
    cmds, parts, marks = [], [], {}

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
        if not kw:
            parts.append(name)

    def wall(name, x0, x1, y0, y1, gaps):
        for i, (a, b) in enumerate(wall_segments(x0, x1, gaps)):
            box(f"{name}{i}", a, b, y0, y1, 0, WALL_H)

    def mark(stage):
        marks[stage] = len(cmds)

    tab_gaps = [(t - TAB_W / 2 - SLOT, t + TAB_W / 2 + SLOT) for t in TAB_X]
    pegs = lego()
    box("Bracket", px0, xe, fy0, by1, -PLATE, 0)
    wall("front", xs0, xe, fy0, -C, tab_gaps + [GROVE])
    box("end", xs0, POE["x0"] - C, fy0, by1, 0, WALL_H)
    wall("back", xs0, xe, POE["y1"] + C, by1, tab_gaps + [BUTTON])
    for t in TAB_X:
        x0, x1 = t - TAB_W / 2, t + TAB_W / 2
        box(f"tabF{t}", x0, x1, -C - TAB_T, -C, 0, POE["top"] + HOOK_H)
        box(f"hookF{t}", x0, x1, -C, HOOK, POE["top"] + C, POE["top"] + HOOK_H)
        box(f"tabB{t}", x0, x1, POE["y1"] + C, POE["y1"] + C + TAB_T, 0, POE["top"] + HOOK_H)
        box(f"hookB{t}", x0, x1, POE["y1"] - HOOK, POE["y1"] + C, POE["top"] + C, POE["top"] + HOOK_H)
    box("xlock", X_LOCK[0], X_LOCK[1], X_LOCK[2], X_LOCK[3], 0, X_LOCK[4])
    box("rspad", *RS_PAD, 0, BOSS_H)
    for i, (x, y) in enumerate(pegs):
        for name, dia, z0, h in (
            (f"boss{i}", BOSS_D, 0, BOSS_H),
            (f"peg{i}", PEG_D, BOSS_H, RIDGE_Z0 - BOSS_H),
            (f"ridge{i}", RIDGE_D, RIDGE_Z0, RIDGE_H),
        ):
            cmds.append(
                {
                    "command": "solid.cylinder",
                    "params": {"diameter": dia, "height": h, "base": [x, y, z0], "operation": "new", "body_name": name},
                }
            )
            parts.append(name)
    cmds.append({"command": "solid.combine", "params": {"target": "Bracket", "tools": parts[1:], "operation": "join"}})
    # 45° lead-in on each hook's inner top edge, so the PoE snaps in from above
    top = POE["top"] + HOOK_H
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "Bracket",
                "distance": HOOK - 0.05,
                "edges": [[t, HOOK, top] for t in TAB_X] + [[t, POE["y1"] - HOOK, top] for t in TAB_X],
            },
        }
    )
    mark("layout")

    peg_top = RIDGE_Z0 + RIDGE_H
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "Bracket",
                "distance": RIDGE_CHAMFER,
                "edges": [[x + RIDGE_D / 2, y, peg_top] for x, y in pegs],
            },
        }
    )
    mark("ridge_tip")
    for i, (x, y) in enumerate(pegs):  # slot across the peg so the ridge squeezes through the bore
        box(
            f"pegslot{i}",
            x - PEG_D,
            x + PEG_D,
            y - PEG_SLOT_W / 2,
            y + PEG_SLOT_W / 2,
            PEG_SLOT_Z0,
            peg_top + 1,
            operation="cut",
            targets=["Bracket"],
        )
    mark("peg_slot")

    cmds.append(
        {
            "command": "solid.fillet",
            "params": {
                "body": "Bracket",
                "radius": TAB_ROOT_R,
                "edges": [[t, -C - TAB_T, 0] for t in TAB_X] + [[t, POE["y1"] + C + TAB_T, 0] for t in TAB_X],
            },
        }
    )
    cmds.append(
        {
            "command": "solid.fillet",
            "params": {
                "body": "Bracket",
                "radius": TAB_ROOT_R_IN,
                "edges": [[t, -C, 0] for t in TAB_X] + [[t, POE["y1"] + C, 0] for t in TAB_X],
            },
        }
    )
    mark("tab_fillet")
    cmds.append(
        {
            "command": "solid.fillet",
            "params": {
                "body": "Bracket",
                "radius": CORNER_R,
                "edges": [[px0, fy0, -PLATE / 2], [px0, by1, -PLATE / 2]],
            },
        }
    )
    cmds.append(
        {
            "command": "solid.fillet",
            "params": {
                "body": "Bracket",
                "radius": CORNER_R_RJ45,
                "edges": [[xe, fy0, -PLATE / 2], [xe, by1, -PLATE / 2]],
            },
        }
    )
    mark("corners")
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {"body": "Bracket", "distance": BOTTOM_CHAMFER, "edges": [[(px0 + xe) / 2, fy0, -PLATE]]},
        }
    )
    mark("bottom_chamfer")
    for x in (xs0 - GAP / 2, rs_x1 - 56 - 16):  # in open plate, reachable with both units fitted
        cmds.append(
            {"command": "solid.hole", "params": {"position": [x, 12, 0], "clearance": "M6", "targets": ["Bracket"]}}
        )
    mark("holes")

    # context only, not exported
    units = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units")
    cmds.append({"command": "file.insert_mesh", "params": {"path": f"{units}/poe.stl", "name": "PoE-P4"}})
    cmds.append(
        {
            "command": "occurrence.move",
            "params": {
                "occurrence": "PoE-P4:1",
                "space": "world",
                "translate": list(place_poe((0, 0, 0))),
                "move_grounded": True,  # the first part inserted is grounded
            },
        }
    )
    cmds.append({"command": "file.insert_mesh", "params": {"path": f"{units}/rs485.stl", "name": "RS485-ISO"}})
    cmds.append(
        {
            "command": "occurrence.move",
            "params": {
                "occurrence": "RS485-ISO:1",
                "space": "world",
                "matrix": [0, -1, 0, rs_x1, 1, 0, 0, 12, 0, 0, 1, 8 + BOSS_H],
            },
        }
    )  # same as place_rs485
    # RS PRO 264-7862 30x30 slot-8 profile: the vendor STEP is a 100 mm piece along +Y, centred on X/Z;
    # stretch it to EXT_LEN, then run it along X under the plate, centred on the M6 holes (y=12)
    profile = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor/rs-pro-2647862/2647862.stp"
    )
    ext_x0 = (px0 + xe) / 2 - EXT_LEN / 2
    cmds.append({"command": "file.insert_step", "params": {"path": profile, "name": "RS-2647862"}})
    cmds.append({"command": "solid.press_pull", "params": {"face": [14.5, 100, 11], "distance": EXT_LEN - 100}})
    cmds.append({"command": "body.rename", "params": {"body": "2647862", "name": "Extrusion"}})
    cmds.append(
        {
            "command": "occurrence.move",
            "params": {
                "occurrence": "RS-2647862:1",
                "space": "world",
                "matrix": [0, 1, 0, ext_x0, -1, 0, 0, 12, 0, 0, 1, -PLATE - 15],
            },
        }
    )
    # README render colours: printed part orange, extrusion aluminium
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["Bracket"], "color": "#e07020"}})
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["Extrusion"], "color": "#b8bcc2"}})
    for fmt in ("stl", "step"):
        cmds.append(
            {"command": "file.export", "params": {"path": os.path.join(d, f"{NAME}.{fmt}"), "bodies": ["Bracket"]}}
        )
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    )
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
