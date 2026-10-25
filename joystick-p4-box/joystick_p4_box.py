# Box for a JH-D400X-R4 4-axis joystick and a Waveshare ESP32-P4-WIFI6-POE-ETH (PoE: one cable).
# Shell prints panel-down, base plate-down, no supports. Design notes and status: README.md
# usage: python3 joystick_p4_box.py [outdir]
#   then: solidcraft-cli run <outdir>/joystick-p4-box.json --save <outdir>/joystick-p4-box.solidcraft
#
# Frame (in use, z up): plate bottom z=0, plate top z=3, panel underside z=35, top z=38. Interior x 0..123.8,
# y 0..61; the shell is open at +X, where the base's end wall carries the port windows. Joystick at -X, board at +X.
import json
import os
import sys
from pathlib import Path

NAME = "joystick-p4-box"  # every output file is named after the part

C, T, PANEL, PLATE = 0.3, 3.0, 3.0, 3.0  # fit clearance, wall, panel, plate thickness
W_IN, H_IN, X_END = 61.0, 32.0, 123.8  # interior width, plate top to panel underside, open end (outer +X face)
JOY = (30.5, 30.5)  # joystick axis; pots point -X and -Y, so the 50x50 envelope sits in the interior's -X/-Y corner
JOY_HOLE = 40.0 + 2 * C  # the grommet's Ø40 inner ring can sit in it
JOY_SQ, JOY_SCREW_D, JOY_CS_D = 33.0, 2.9, 5.0  # M2.5; square from the D400B model (LowRiderJS: 33.25)
# units/d400b.step (GrabCAD "D400B 3-axis joystick with pushbutton"): body top at its y 25.75
JOY_STEP_TOP = 25.75
JOY_BELOW = ["Fillet1"] + [f"Boss-Extrude4[{i}]" for i in range(1, 6)]  # body with pots; the 5 leads
JOY_ABOVE = ["Fillet1 (2)", "Cut-Extrude1", "Revolve1"]  # grommet, ring, handle
DOVE = 1.5  # plate edges reach this far into each long wall; 45° underside bevel, so the groove prints panel-down
CORNER_R, CORNER_R_END = 3.0, 1.0  # +X corners run up the 3 mm walls, so they get less
TOP_CHAMFER = 0.5  # panel top is the shell's bed face: elephant's foot
# ESP32-P4-WIFI6-POE-ETH, 55 x 68, header edge at -X, port edge at +X; Waveshare's V2.0 STEP and drawing
BOARD_STEP = Path(__file__).resolve().parent.parent / "vendor/waveshare-esp32-p4-wifi6-poe-eth"
BOARD_STEP /= "ESP32-P4-WIFI6-POE-ETH_3d-20251213.stp"
END_T = 1.5  # base end wall: thin, so the USB stack reaches its outer face and plug overmolds clear it
USB_PROUD = 1.7  # USB stack face past the board edge; flush with the wall's outer face, board edge 0.2 inside
BOARD_X0, BOARD_Y0, POST_H, PCB = X_END - 68 - USB_PROUD, 3.0, 6.0, 1.6
POSTS = [(x, y) for x in (BOARD_X0 + 10.7, BOARD_X0 + 43.7) for y in (BOARD_Y0 + 3.5, BOARD_Y0 + 51.5)]
POST_D, PILOT_D, PILOT_DEPTH = 6.0, 2.2, 5.0  # M2.5 self-tapping
WALL_X0 = X_END - END_T  # base end wall inner face
WIN_M, TF_NAIL = 0.5, 2.0  # window margin; the microSD window drops lower for a fingernail
# 45° flare on the microSD window's outer edges: the slot sits 1.2 into the board, so a fingernail needs the room;
# not on its -Y edge, which has only 0.7 of wall to the RJ45 window
TF_FLARE = 1.2
# detent between the end wall's side edges and the shell walls at the open mouth, where the walls can flex
BUMP_D, DIMPLE_D, DETENT_X, DETENT_Z = 1.6, 1.6, X_END - END_T / 2, 20.0
PCB_TOP = PLATE + POST_H + PCB


def ports():
    """Port blocks (x0, x1, y0, y1, z0, z1) above the PCB, from the board STEP's bodies; TF height user-measured."""
    y = BOARD_Y0
    return {
        "USB": (BOARD_X0 + 52.24, BOARD_X0 + 68 + USB_PROUD, y + 4.26, y + 19.93, PCB_TOP, PCB_TOP + 16),
        "RJ45": (BOARD_X0 + 48.59, BOARD_X0 + 69.99, y + 21.86, y + 37.9, PCB_TOP, PCB_TOP + 13.3),
        "TF": (BOARD_X0 + 55.52, BOARD_X0 + 66.77, y + 39.63, y + 50.98, PCB_TOP, PCB_TOP + 2),
    }


def windows():
    """Openings in the base end wall, one per port."""
    out = {}
    for n, (_, _, y0, y1, z0, z1) in ports().items():
        nail = TF_NAIL if n == "TF" else 0
        out[n] = (WALL_X0 - 1, X_END + 1, y0 - WIN_M, y1 + WIN_M, z0 - WIN_M - nail, z1 + WIN_M)
    return out


def proxies():
    """Context boxes (x0, x1, y0, y1, z0, z1): Dupont plugs on the header (the board itself is BOARD_STEP)."""
    return {"Header": [(BOARD_X0 + 1.46, BOARD_X0 + 6.54, BOARD_Y0 + 2.1, BOARD_Y0 + 52.9, PCB_TOP, PCB_TOP + 21.5)]}


def build(d):
    """Command script for solidcraft-cli, and the index where each checked stage ends."""
    cmds, marks = [], {}
    top = PLATE + H_IN + PANEL

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

    def mark(stage):
        marks[stage] = len(cmds)

    # --- shell
    box("Shell", -T, X_END, -T, W_IN + T, 0, top)
    box("cavity", 0, X_END + 1, 0, W_IN, 0, PLATE + H_IN, operation="cut", targets=["Shell"])
    mark("shell_layout")
    box("groove", 0, X_END + 1, -DOVE, W_IN + DOVE, 0, PLATE + C)
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "groove",
                "distance": DOVE,
                "edges": [[X_END / 2, -DOVE, 0], [X_END / 2, W_IN + DOVE, 0]],
            },
        }
    )
    cmds.append({"command": "solid.combine", "params": {"target": "Shell", "tools": ["groove"], "operation": "cut"}})
    mark("groove")
    for r, x in ((CORNER_R, -T), (CORNER_R_END, X_END)):
        cmds.append(
            {
                "command": "solid.fillet",
                "params": {"body": "Shell", "radius": r, "edges": [[x, -T, top / 2], [x, W_IN + T, top / 2]]},
            }
        )
    mark("shell_corners")
    mid = (X_END - T) / 2
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "Shell",
                "distance": TOP_CHAMFER,
                "edges": [[mid, -T, top], [mid, W_IN + T, top], [-T, W_IN / 2, top], [X_END, W_IN / 2, top]],
            },
        }
    )
    mark("panel_chamfer")
    cmds.append(
        {"command": "solid.hole", "params": {"position": [*JOY, top], "diameter": JOY_HOLE, "targets": ["Shell"]}}
    )
    for sx in (-1, 1):
        for sy in (-1, 1):
            cmds.append(
                {
                    "command": "solid.hole",
                    "params": {
                        "position": [JOY[0] + sx * JOY_SQ / 2, JOY[1] + sy * JOY_SQ / 2, top],
                        "diameter": JOY_SCREW_D,
                        "type": "countersink",
                        "cs_diameter": JOY_CS_D,
                        "cs_angle": 90,
                        "targets": ["Shell"],
                    },
                }
            )
    mark("joy_holes")

    # --- base: dovetailed plate + end wall + board posts; runs to X_END so it fills the groove ends
    def cyl(name, d, x, y, z0, h):
        cmds.append(
            {
                "command": "solid.cylinder",
                "params": {"diameter": d, "height": h, "base": [x, y, z0], "operation": "new", "body_name": name},
            }
        )

    box("Base", C, X_END, -DOVE + C, W_IN + DOVE - C, 0, PLATE)
    box("endwall", WALL_X0, X_END, C, W_IN - C, 0, PLATE + H_IN - C)
    for i, (x, y) in enumerate(POSTS):
        cyl(f"post{i}", POST_D, x, y, PLATE, POST_H)
    tools = ["endwall"] + [f"post{i}" for i in range(len(POSTS))]
    cmds.append({"command": "solid.combine", "params": {"target": "Base", "tools": tools, "operation": "join"}})
    mark("base_layout")
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "Base",
                "distance": DOVE,
                "edges": [[X_END / 2, -DOVE + C, 0], [X_END / 2, W_IN + DOVE - C, 0]],
            },
        }
    )
    mark("plate_bevel")
    for n, w in windows().items():
        box(f"win{n}", *w, operation="cut", targets=["Base"])
    mark("windows")
    _, _, y0, y1, z0, z1 = windows()["TF"]
    ym, zm = (y0 + y1) / 2, (z0 + z1) / 2
    cmds.append(
        {
            "command": "solid.chamfer",
            "params": {
                "body": "Base",
                "distance": TF_FLARE,
                "edges": [[X_END, ym, z0], [X_END, ym, z1], [X_END, y1, zm]],
            },
        }
    )
    mark("tf_flare")
    for x, y in POSTS:
        cmds.append(
            {
                "command": "solid.hole",
                "params": {
                    "position": [x, y, PLATE + POST_H],
                    "diameter": PILOT_D,
                    "depth": PILOT_DEPTH,
                    "targets": ["Base"],
                },
            }
        )
    mark("pilots")
    for yb, yd in ((0, C), (W_IN, W_IN - C)):
        cmds.append(
            {
                "command": "solid.sphere",
                "params": {
                    "diameter": BUMP_D,
                    "center": [DETENT_X, yb, DETENT_Z],
                    "operation": "join",
                    "targets": ["Shell"],
                },
            }
        )
        cmds.append(
            {
                "command": "solid.sphere",
                "params": {
                    "diameter": DIMPLE_D,
                    "center": [DETENT_X, yd, DETENT_Z],
                    "operation": "cut",
                    "targets": ["Base"],
                },
            }
        )
    mark("detent")

    # context only, not exported
    for n, boxes in proxies().items():
        for i, b in enumerate(boxes):
            box(f"{n}{i}" if i else n, *b)
        if len(boxes) > 1:
            cmds.append(
                {
                    "command": "solid.combine",
                    "params": {"target": n, "tools": [f"{n}{i}" for i in range(1, len(boxes))], "operation": "join"},
                }
            )
    # D400B model is Y-up with the grommet straight on the body: turn it so the pots point -X/-Y and the leads +Y,
    # body top to the panel underside, then lift grommet, ring and handle by the panel
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units", "d400b.step")
    cmds.append({"command": "file.insert_step", "params": {"path": path, "name": "D400B"}})
    z = PLATE + H_IN - JOY_STEP_TOP
    m = [0, 0, -1, JOY[0], -1, 0, 0, JOY[1], 0, 1, 0, z]
    cmds.append({"command": "occurrence.move", "params": {"occurrence": "D400B:1", "space": "world", "matrix": m}})
    cmds.append({"command": "solid.move", "params": {"bodies": JOY_ABOVE, "translate": [0, PANEL, 0]}})  # local Y-up
    # the STEP has PCB top at z 0, header at +Y, ports at y 0
    m = [0, -1, 0, BOARD_X0 + 68, 1, 0, 0, BOARD_Y0, 0, 0, 1, PCB_TOP]
    cmds.append({"command": "file.insert_step", "params": {"path": str(BOARD_STEP), "name": "Board", "matrix": m}})
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["Shell"], "color": "#e07020"}})
    cmds.append({"command": "appearance.assign", "params": {"bodies": ["Base"], "color": "#404040"}})
    cmds.append({"command": "appearance.assign", "params": {"bodies": list(proxies()), "color": "#b8bcc2"}})
    for part in ("Shell", "Base"):
        for fmt in ("stl", "step"):
            path = os.path.join(d, f"{NAME}-{part.lower()}.{fmt}")
            cmds.append({"command": "file.export", "params": {"path": path, "bodies": [part]}})
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    )
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
