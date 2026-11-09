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

# esp32cam cup: hex shell tapering out from the front (z 0) to the rim, rounded corners, 1.8 floor and walls
CUP_FRONT_F = 45.04  # across flats at z 0; 65.82 at the rim
CUP_TAPER = math.degrees(math.atan(10.39 / RIM_Z))  # walls lean out 19.1°
CUP_CORNER_R = 1.9
CUP_FLOOR = 1.8
CUP_INNER_F = 42.48  # across flats inside at the floor
PLATFORM = (-20.0, 20.0, -13.0, 13.0, CUP_FLOOR, 3.0)  # ESP32-CAM seat, with a lip at -X
LIP = (-20.0, -18.0, -13.0, 13.0, 3.0, 5.5)
POSTS = [(-4.0, 4.0, 13.5, 23.5), (-4.0, 4.0, -23.5, -13.5)]  # to z 8, 1 mm chamfers, pilot below
POST_TOP = 8.0
POST_PILOT = (2.6, 6.0, 19.0)  # diameter, depth, |y|
LENS_RECESS = (5.0, 15.0, -5.0, 5.0, 1.0)  # x0, x1, y0, y1, floor z
LENS_HOLE = (8.6, 10.0, 0.0)
FLASH = (-12.0, -7.88, 8.0, 12.0)
BOSS_PROFILE = [(19.91, 30.0), (27.91, 22.0), (29.0, 22.0), (32.0, 30.0)]  # (u, z), gusset with a 45° underside
BOSS_W = 9.0
PILOT = (2.5, 4.0)  # M3 self-tapping, from the rim
CABLE = ((-7.5, 12.0), (7.5, 22.0), 2.5)  # 180° wall: (y, z) corners, corner radius
PILOT_LEAD = 1.0  # 45° lead-in at the rim
# vents on the 0°, 120°, 240° walls: stadiums running 40° up from horizontal in the wall's plane, placed by hand per
# wall in the original. Per slot: its two sides s0, s1 across and its tips u0, u1 along, in wall coordinates (a along
# the wall, b up the slope from the axis), read off the STL
VENT_ANGLE = 40.0
VENTS = {
    0: [
        (3.37, 5.87, 9.36, 20.17),
        (8.65, 11.15, 3.07, 26.62),
        (13.93, 16.43, -2.37, 33.07),
        (19.20, 21.70, 0.59, 33.05),
        (24.48, 26.98, 3.55, 26.76),
        (29.76, 32.27, 6.51, 20.47),
        (35.03, 37.53, 9.47, 14.19),
    ],
    120: [
        (3.15, 5.50, 9.03, 20.48),
        (8.44, 10.78, 2.74, 26.41),
        (13.72, 16.06, -3.54, 33.38),
        (18.99, 21.34, -0.19, 34.26),
        (24.27, 26.61, 2.77, 27.97),
        (29.52, 32.27, 5.74, 21.68),
        (34.82, 37.17, 8.72, 15.40),
    ],
    240: [
        (3.33, 5.83, 9.42, 20.12),
        (8.46, 11.06, 3.13, 26.07),
        (13.88, 16.38, -3.16, 33.01),
        (19.16, 21.66, 0.57, 33.10),
        (24.44, 26.94, 3.53, 26.82),
        (29.71, 32.27, 6.49, 20.53),
        (34.99, 37.49, 9.45, 14.24),
    ],
}

# bracket: 1.5 mm U along this centreline, 10 tall, r1 bends, flange ends chamfered, Ø3.1 holes across the flanges
BRACKET_PATH = [
    (-115.84, 23.0),
    (-115.84, 14.75),
    (-128.84, 14.75),
    (-128.84, -14.75),
    (-115.84, -14.75),
    (-115.84, -23.0),
]
BRACKET_T = 1.5
BRACKET_H = 10.0

# --- dfr1154: DFRobot DFR1154 (ESP32-S3, OV3660 160° lens). Board coordinates: mm from the top-left corner seen from
# the camera side, logo edge at the top. Estimates from DFRobot's function diagram (10 px/mm) and dimension drawing,
# PCB v1.0, not checked against a board: measure before printing (README).
PCB = 42.0
PCB_T = 1.6
HOLES = [(3.5, 3.5), (38.5, 3.5), (3.5, 38.5), (38.5, 38.5)]
HOLE_D = 3.1
CAM = (21.0, 14.8)  # lens centre
CAM_BODY = (9.0, 10.0)
CAM_H = 6.5  # lens front above the PCB's camera side
APERTURE_R = 3.5
FOV_X, FOV_Y = 64.0, 48.0  # half-angles: 160° taken as the diagonal of a 4:3 picture, long side across the board
IR = [(5.5, 11.3), (5.5, 20.3), (36.5, 11.3), (36.5, 20.3)]
IR_SIZE = (3.5, 3.0)
MIC = (6.5, 29.8)
MIC_SIZE = (3.5, 2.7)
ALS = (14.8, 38.1)
ALS_SIZE = (2.0, 2.0)
FRONT_PART_H = 1.0  # LEDs, mic and light sensor
# back side, in the same camera-side coordinates: (x0, x1, y0, y1, height)
BACK_LOW_H = 2.0  # everything not listed
BACK_H = 8.5  # screw terminal, the tallest part
BACK_PARTS = {"terminal": (34.7, 42.0, 24.6, 31.2, BACK_H), "gravity": (9.0, 21.1, 34.0, 42.0, 6.0)}
USB_X = 28.0  # USB-C centre along the bottom edge
USB_Z = 1.6  # its centre above the PCB's back
USB_PLUG = (12.5, 7.0, 15.0)  # plug overmould: width, height, length past the board edge

# dfr1154 cup: straight hex with the esp32cam cup's rim, board right behind the front wall
WALL = 2.0
FRONT_T = 1.6
LENS_GAP = 1.0  # lens front behind the front wall's inside
POST_D = 6.0
POST_PILOT_D = 2.5  # M3 self-tapping through the board holes
POST_PILOT_DEPTH = 6.0
BOSS_H = 6.0  # gussets hang this far from the rim: pilot depth + 2
CLEAR = 0.5
TUBE_WALL = 0.8  # light tubes from the front wall to just above the board, so no IR reaches the lens inside
TUBE_GAP = 0.3  # tube ends this far off the board
WINDOW_CLEAR = 1.0  # window and tube bore over the part's size
MIC_HOLE = 1.5
VENT = (2.0, 4.0)  # slot width, spacing; three per free flat, from the board's back to 3 below the rim


def board_to_world(bx, by):
    """Camera-side board coordinates to world x, y: board centred on the axis, logo edge toward -Y (picture-up)."""
    return bx - PCB / 2, by - PCB / 2


def depth():
    """Rim above the front face: the board stack, then whichever needs more room, the tallest back part or a boss
    over the USB plug."""
    stack = FRONT_T + LENS_GAP + CAM_H + PCB_T
    tallest = max(h for *_, h in BACK_PARTS.values()) + 1.0
    plug = USB_Z + USB_PLUG[1] / 2 + CLEAR + BOSS_H
    return stack + max(tallest, plug)


def z_front():
    return RIM_Z - depth()


def z_inner():
    return z_front() + FRONT_T


def z_lens():
    return z_inner() + LENS_GAP


def z_pcb_front():
    return z_lens() + CAM_H


def z_pcb_back():
    return z_pcb_front() + PCB_T


def dfr_standins():
    """Board, parts and USB plug as world boxes (x0, x1, y0, y1, z0, z1) per body: context only, never exported."""

    def part(cx, cy, w, h, z0, z1):
        x, y = board_to_world(cx, cy)
        return (x - w / 2, x + w / 2, y - h / 2, y + h / 2, z0, z1)

    zf, zb = z_pcb_front(), z_pcb_back()
    h = PCB / 2
    front = [part(*c, *IR_SIZE, zf - FRONT_PART_H, zf) for c in IR]
    front += [part(*MIC, *MIC_SIZE, zf - FRONT_PART_H, zf), part(*ALS, *ALS_SIZE, zf - FRONT_PART_H, zf)]
    back = [(-h, h, -h, h, zb, zb + BACK_LOW_H)]
    for x0, x1, y0, y1, ht in BACK_PARTS.values():
        (wx0, wy0), (wx1, wy1) = board_to_world(x0, y0), board_to_world(x1, y1)
        back.append((wx0, wx1, wy0, wy1, zb, zb + ht))
    ux, _ = board_to_world(USB_X, PCB)
    w, ht, length = USB_PLUG
    uz = zb + USB_Z
    return {
        "DfrPcb": [(-h, h, -h, h, zf, zb)],
        "DfrCam": [part(*CAM, *CAM_BODY, z_lens(), zf)],
        "DfrFront": front,
        "DfrBack": back,
        "DfrPlug": [(ux - w / 2, ux + w / 2, h, h + length, uz - ht / 2, uz + ht / 2)],
    }


for _bx, _by in [CAM, MIC, ALS, *IR, *HOLES]:
    assert 0 <= _bx <= PCB and 0 <= _by <= PCB, (_bx, _by)
assert board_to_world(*CAM)[0] == 0 and abs(board_to_world(*CAM)[1] + 6.2) < 1e-9  # lens 6.2 above centre


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

    def rotated_copies(body):
        """body1 and body2: copies turned +120° and -120° about Z (180° → 300° and 60°)."""
        for i, a in enumerate(("120 deg", "-120 deg")):
            cmds.append(
                {"command": "solid.move", "params": {"bodies": [body], "axis": [0, 0, 1], "angle": a, "copy": True}}
            )
            cmds.append({"command": "body.rename", "params": {"body": f"{body} (2)", "name": f"{body}{i + 1}"}})

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
    rotated_copies("Leg")
    combine("Plate", ["Leg", "Leg1", "Leg2"], "join")
    mark("e32:plate_legs")
    for x, y in JOINT:
        cyl("PlateHole", SCREW_CLEAR, (x, y, RIM_Z - 1), PLATE_T + 2, operation="cut", targets=["Plate"])
    mark("e32:plate_holes")
    export("Plate", "plate")

    # --- esp32cam cup
    cup = "E32Cup"
    tan_t = math.tan(math.radians(CUP_TAPER))
    front = {"origin": [0, 0, 0], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism(cup, hexagon(CUP_FRONT_F), front, RIM_Z, taper=f"{CUP_TAPER} deg")
    mark("e32:cup_shell")
    corner = (CUP_FRONT_F / 2 + RIM_Z / 2 * tan_t) / math.cos(math.radians(30))
    edges = [
        [corner * math.cos(math.radians(90 + 60 * k)), corner * math.sin(math.radians(90 + 60 * k)), RIM_Z / 2]
        for k in range(6)
    ]
    cmds.append({"command": "solid.fillet", "params": {"body": cup, "radius": CUP_CORNER_R, "edges": edges}})
    mark("e32:cup_corners")
    floor = {"origin": [0, 0, CUP_FLOOR], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism("CupInside", hexagon(CUP_INNER_F), floor, RIM_Z, taper=f"{CUP_TAPER} deg", operation="cut", targets=[cup])
    mark("e32:cup_hollow")
    for i, (x0, x1, y0, y1) in enumerate(POSTS):
        box(f"CupPost{i}", x0, x1, y0, y1, CUP_FLOOR, POST_TOP)
    mark("e32:posts")
    # chamfer the posts before they join the floor: on the joined body the bottom corners refuse the blend
    for i, (x0, x1, y0, y1) in enumerate(POSTS):
        xm, ym, zm = (x0 + x1) / 2, (y0 + y1) / 2, (CUP_FLOOR + POST_TOP) / 2
        edges = [[x0, ym, POST_TOP], [x1, ym, POST_TOP], [xm, y0, POST_TOP], [xm, y1, POST_TOP]]
        edges += [[x, y, zm] for x in (x0, x1) for y in (y0, y1)]
        cmds.append({"command": "solid.chamfer", "params": {"body": f"CupPost{i}", "distance": 1.0, "edges": edges}})
    mark("e32:post_chamfers")
    box("CupPlatform", *PLATFORM)
    box("CupLip", *LIP)
    combine(cup, ["CupPlatform", "CupLip", "CupPost0", "CupPost1"], "join")
    mark("e32:cup_inside")
    dia, depth, py = POST_PILOT
    for y in (py, -py):
        cyl("CupPostPilot", dia, (0, y, POST_TOP - depth), depth + 1, operation="cut", targets=[cup])
    mark("e32:post_pilots")
    x0, x1, y0, y1, z0 = LENS_RECESS
    box("CupLensRecess", x0, x1, y0, y1, z0, PLATFORM[5] + 1, operation="cut", targets=[cup])
    dia, x, y = LENS_HOLE
    cyl("CupLensHole", dia, (x, y, -1), z0 + 2, operation="cut", targets=[cup])
    mark("e32:lens")
    box("CupFlash", *FLASH, -1, PLATFORM[5] + 1, operation="cut", targets=[cup])
    mark("e32:flash")
    radial = {"origin": [0, 0, 0], "x_dir": [-1, 0, 0], "y_dir": [0, 0, 1]}
    prism("CupBoss", BOSS_PROFILE, radial, BOSS_W, direction="symmetric")
    rotated_copies("CupBoss")
    combine(cup, ["CupBoss", "CupBoss1", "CupBoss2"], "join")
    mark("e32:bosses")
    dia, depth = PILOT
    for x, y in JOINT:
        cyl("CupPilot", dia, (x, y, RIM_Z - depth), depth + 1, operation="cut", targets=[cup])
    edges = [[x + PILOT[0] / 2, y, RIM_Z] for x, y in JOINT]
    cmds.append({"command": "solid.chamfer", "params": {"body": cup, "distance": PILOT_LEAD, "edges": edges}})
    mark("e32:cup_pilots")
    side = {"origin": [-36, 0, 0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]}
    cmds.append({"command": "sketch.create", "params": {"plane": side, "name": "CupCableSk"}})
    p0, p1, rc = CABLE
    cmds.append({"command": "sketch.rectangle.rounded", "params": {"p0": list(p0), "p1": list(p1), "radius": rc}})
    cmds.append({"command": "sketch.finish", "params": {}})
    cmds.append({"command": "solid.extrude", "params": {"distance": 14, "operation": "cut", "targets": [cup]}})
    mark("e32:cable")
    t = math.radians(CUP_TAPER)
    outer = CUP_FRONT_F / 2 * math.cos(t)  # outer wall plane's distance from the axis, along its normal
    ca, sa = math.cos(math.radians(VENT_ANGLE)), math.sin(math.radians(VENT_ANGLE))
    for k, phi in enumerate(VENTS):
        cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
        n = (math.cos(t) * cp, math.cos(t) * sp, -math.sin(t))
        plane = {
            "origin": [(outer - 2.2) * c for c in n],
            "x_dir": [-sp, cp, 0],
            "y_dir": [math.sin(t) * cp, math.sin(t) * sp, math.cos(t)],
        }
        cmds.append({"command": "sketch.create", "params": {"plane": plane, "name": f"CupVents{k}Sk"}})
        for s0, s1, u0, u1 in VENTS[phi]:
            sv, r = (s0 + s1) / 2, (s1 - s0) / 2
            ends = [(-sa * sv + ca * u, ca * sv + sa * u) for u in (u0 + r, u1 - r)]
            cmds.append(
                {
                    "command": "sketch.slot.center_to_center",
                    "params": {"p0": list(ends[0]), "p1": list(ends[1]), "width": s1 - s0},
                }
            )
        cmds.append({"command": "sketch.finish", "params": {}})
        cmds.append({"command": "solid.extrude", "params": {"distance": 5, "operation": "cut", "targets": [cup]}})
    mark("e32:vents")
    export(cup, "esp32cam-cup")

    # --- bracket
    br = "Bracket"
    cmds.append({"command": "sketch.create", "params": {"plane": "XY", "name": "BracketSk"}})
    cmds.append({"command": "sketch.line", "params": {"points": [list(q) for q in BRACKET_PATH]}})
    cmds.append({"command": "sketch.finish", "params": {}})
    cmds.append(
        {
            "command": "solid.extrude",
            "params": {"distance": BRACKET_H, "thin": True, "thickness": BRACKET_T, "side": "center", "body_name": br},
        }
    )
    mark("e32:bracket")
    h = BRACKET_T / 2
    (xf, _), (xb, yb) = BRACKET_PATH[0], BRACKET_PATH[2]
    zm = BRACKET_H / 2
    convex = [[xf + h, sy * (yb - h), zm] for sy in (1, -1)] + [[xb - h, sy * (yb + h), zm] for sy in (1, -1)]
    concave = [[xf - h, sy * (yb + h), zm] for sy in (1, -1)] + [[xb + h, sy * (yb - h), zm] for sy in (1, -1)]
    cmds.append({"command": "solid.fillet", "params": {"body": br, "radius": 1.0, "edges": convex}})
    mark("e32:bracket_convex")
    cmds.append({"command": "solid.fillet", "params": {"body": br, "radius": 1.0, "edges": concave}})
    mark("e32:bracket_rounds")
    yend = BRACKET_PATH[0][1]
    edges = [[xf, sy * yend, z] for sy in (1, -1) for z in (0, BRACKET_H)]
    cmds.append({"command": "solid.chamfer", "params": {"body": br, "distance": 2.0, "edges": edges}})
    mark("e32:bracket_chamfers")
    for sy in (1, -1):
        cyl("BracketHole", SCREW_CLEAR, (xf - 2, sy * 19.0, BRACKET_H / 2), 4, axis="X", operation="cut", targets=[br])
    mark("e32:bracket_holes")
    export(br, "bracket")

    # --- dfr1154 cup
    dc = "DfrCup"
    zf = z_front()
    plane = {"origin": [0, 0, zf], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism(dc, hexagon(HEX_F), plane, RIM_Z - zf)
    corner = HEX_F / 2 / math.cos(math.radians(30))
    zm = (zf + RIM_Z) / 2
    edges = [
        [corner * math.cos(math.radians(90 + 60 * k)), corner * math.sin(math.radians(90 + 60 * k)), zm]
        for k in range(6)
    ]
    cmds.append({"command": "solid.fillet", "params": {"body": dc, "radius": CUP_CORNER_R, "edges": edges}})
    mark("dfr:shell")
    plane = {"origin": [0, 0, z_inner()], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}
    prism("DfrInside", hexagon(HEX_F - 2 * WALL), plane, RIM_Z, operation="cut", targets=[dc])
    mark("dfr:hollow")
    for i, (bx, by) in enumerate(HOLES):
        x, y = board_to_world(bx, by)
        cyl(f"DfrPost{i}", POST_D, (x, y, z_inner() - 0.5), z_pcb_front() - z_inner() + 0.5)
    combine(dc, [f"DfrPost{i}" for i in range(len(HOLES))], "join")
    mark("dfr:posts")
    for bx, by in HOLES:
        x, y = board_to_world(bx, by)
        top = z_pcb_front()
        cyl(
            "DfrPostPilot",
            POST_PILOT_D,
            (x, y, top - POST_PILOT_DEPTH),
            POST_PILOT_DEPTH + 1,
            operation="cut",
            targets=[dc],
        )
    mark("dfr:post_pilots")
    zb = RIM_Z - BOSS_H
    u0 = BOSS_PROFILE[0][0]
    profile = [(u0, RIM_Z), (u0 + BOSS_H, zb), (HEX_F / 2 - WALL / 2, zb), (HEX_F / 2 - WALL / 2, RIM_Z)]
    prism("DfrBoss", profile, radial, BOSS_W, direction="symmetric")
    rotated_copies("DfrBoss")
    combine(dc, ["DfrBoss", "DfrBoss1", "DfrBoss2"], "join")
    mark("dfr:bosses")
    dia, dep = PILOT
    for x, y in JOINT:
        cyl("DfrPilot", dia, (x, y, RIM_Z - dep), dep + 1, operation="cut", targets=[dc])
    edges = [[x + dia / 2, y, RIM_Z] for x, y in JOINT]
    cmds.append({"command": "solid.chamfer", "params": {"body": dc, "distance": PILOT_LEAD, "edges": edges}})
    mark("dfr:pilots")
    ((px0, px1, _, _, pz0, pz1),) = dfr_standins()["DfrPlug"]
    # through the 60° wall only, from 1 mm inside its inner face at the slot's far side
    y_in = (HEX_F / 2 - WALL - 0.5 * (px1 + CLEAR)) / math.cos(math.radians(30)) - 1
    box("DfrUsb", px0 - CLEAR, px1 + CLEAR, y_in, RIM_Z + 20, pz0 - CLEAR, pz1 + CLEAR, operation="cut", targets=[dc])
    mark("dfr:usb")
    w, pitch = VENT
    z0, z1 = z_pcb_back() + CLEAR, RIM_Z - 3
    for phi in (0, 120, 240):
        for k in (-1, 0, 1):
            # built on the 0° flat, then turned into place
            r = HEX_F / 2 - WALL / 2
            box("DfrVent", r - WALL, r + WALL, k * pitch - w / 2, k * pitch + w / 2, z0, z1)
            if phi:
                cmds.append(
                    {
                        "command": "solid.move",
                        "params": {"bodies": ["DfrVent"], "axis": [0, 0, 1], "angle": f"{phi} deg"},
                    }
                )
            combine(dc, ["DfrVent"], "cut")
    mark("dfr:vents")
    # lens: a 4:3 funnel from the aperture at the lens front, opening at the field-of-view half-angles; lofted between
    # rectangles 0.5 past both faces of the front wall
    lx, ly = board_to_world(*CAM)
    for name, z in (("DfrLensIn", z_inner() + 0.5), ("DfrLensOut", z_front() - 0.5)):
        dl = z_lens() - z
        hx = APERTURE_R + dl * math.tan(math.radians(FOV_X))
        hy = APERTURE_R + dl * math.tan(math.radians(FOV_Y))
        pts = [(lx - hx, ly - hy), (lx + hx, ly - hy), (lx + hx, ly + hy), (lx - hx, ly + hy)]
        cmds.append(
            {
                "command": "sketch.create",
                "params": {"plane": {"origin": [0, 0, z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}, "name": name},
            }
        )
        cmds.append({"command": "sketch.line", "params": {"points": [list(q) for q in pts], "closed": True}})
        cmds.append({"command": "sketch.finish", "params": {}})
    cmds.append(
        {
            "command": "solid.loft",
            "params": {
                "sections": [{"sketch": "DfrLensIn"}, {"sketch": "DfrLensOut"}],
                "operation": "cut",
                "targets": [dc],
            },
        }
    )
    mark("dfr:lens")
    tube_top = z_pcb_front() - TUBE_GAP
    holes = [(c, IR_SIZE, None) for c in IR] + [(ALS, ALS_SIZE, None), (MIC, MIC_SIZE, MIC_HOLE)]
    tubes = []
    for i, (c, (w, h), _) in enumerate(holes):
        x, y = board_to_world(*c)
        hw, hh = w / 2 + WINDOW_CLEAR / 2 + TUBE_WALL, h / 2 + WINDOW_CLEAR / 2 + TUBE_WALL
        box(f"DfrTube{i}", x - hw, x + hw, y - hh, y + hh, z_inner() - 0.5, tube_top)
        tubes.append(f"DfrTube{i}")
    combine(dc, tubes, "join")
    mark("dfr:tubes")
    for c, (w, h), hole in holes:
        x, y = board_to_world(*c)
        hw, hh = w / 2 + WINDOW_CLEAR / 2, h / 2 + WINDOW_CLEAR / 2
        if hole:  # mic: a small hole through the front, the tube's bore stops at the wall
            box("DfrBore", x - hw, x + hw, y - hh, y + hh, z_inner(), tube_top + 1, operation="cut", targets=[dc])
            cyl("DfrMicHole", hole, (x, y, z_front() - 1), FRONT_T + 2, operation="cut", targets=[dc])
        else:
            box("DfrWindow", x - hw, x + hw, y - hh, y + hh, z_front() - 1, tube_top + 1, operation="cut", targets=[dc])
    mark("dfr:windows")
    export(dc, "dfr1154-cup")
    for name, boxes in dfr_standins().items():
        for i, b in enumerate(boxes):
            box(f"{name}{i}" if i else name, *b)
        if len(boxes) > 1:
            combine(name, [f"{name}{i}" for i in range(1, len(boxes))], "join")
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    )
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
