# Polymath Robotics' protective-stop remote (github.com/polymathrobotics/protective-stop, CERN-OHL-P-2.0) in two
# variants: s3, their own design for the ESP32-S3-ETH, matched to their STLs; p4, taller, for a flipped
# ESP32-P4-POE-ETH. Base prints floor-down, lid face-down. Design notes and status: README.md
# usage: python3 protective_stop_remote.py [outdir]
#   then: solidcraft-cli run <outdir>/protective-stop-remote.json --save <outdir>/protective-stop-remote.solidcraft
#
# Frame: Polymath's. Button axis and body centre at (46, 9); pod at -X, its end wall's outer face x -18; base bottom
# z -2. Both variants are built here, exported, then p4 is moved +Y for the render.
import json
import math
import os
import sys
from pathlib import Path

NAME = "protective-stop-remote"  # every output file is named after the part
CX, CY = 46.0, 9.0  # body centre and button axis

VARIANTS = {
    "s3": {
        "prefix": "S3",
        "r_out": 46.2,  # body outer radius
        "r_in": 43.0,
        "z_bot": -2.0,
        "floor_top": 1.2,
        "rim": 24.2,  # body wall top
        "pod_top": 24.0,  # pod and channel walls top
        "pod_y": (-3.45, 22.55),  # pod and channel outer faces
        "pod_x0": -18.0,  # pod end wall outer face
        "chan_t": 1.0,  # pod, channel and end walls
        "chan_x1": 58.5,  # channel end wall outer face, inside the body
        "chan_floor": 0.0,
        "fillet_body": 3.2,  # bottom outer edges
        "fillet_pod": 2.0,  # end wall bottom edge only
        "posts": [(46.0, -29.0), (46.0, 47.0), (84.0, 9.0), (11.53, -7.0), (12.01, 26.0)],  # lid screws, r 38
        "post_d": 8.0,
        "post_hole_d": 5.0,  # M3 heat-set insert, down to the floor
        # x, y, top, Ø, hole Ø (2.5: M1.6 heat-set insert)
        "standoffs": [(x, y, 4.5, 4.0, 2.5) for x, y in ((0.0, 0.0), (54.25, 0.0), (0.0, 18.3), (54.25, 18.3))],
        "standoff_hole_depth": 4.5,  # down to the channel floor
        "chan_end": True,  # channel closed by an end wall inside the body
        "windows": {"RJ45": (1.23, 17.79, 6.52, 19.91), "USB": (4.97, 14.03, 1.63, 4.95)},  # end wall: y0, y1, z0, z1
        "cross_hole": (-5.85, 3.5, 1.5),  # x, z, Ø: through both pod side walls
        "floor_hole": (-3.48, 4.51, 2.0),  # x, y, Ø: through the channel floor
        "wire_slot": (9.55, 21.0, 2.0),  # y, z of the flat side, r: half-disc through the channel end wall
        "wall_notch": (52.5, 3.0),  # x, Ø: half-round notch in the top of both channel side walls
        "lid_bot": 24.1,  # Polymath's lid underside sits 0.1 into the base's rim
        "lid_top": 28.1,
        "lid_fillet": 3.0,
        "lip": (-16.8, -0.8, -2.25, 21.35, 22.2),  # x0, x1, y0, y1, z0: plug into the pod channel only
        "diffuser_d": 49.0,
        "screw_d": 3.2,  # M3
        "cb_d": 6.2,
        "cb_depth": 2.0,
        "ring_pocket": (14.0, 23.0, 0.4),  # inner r, outer r, skin over the LEDs
        "ring_bumps": (21.5, 3.0, 0.4),  # inner r, width, height: four snaps at 0/90/180/270°
        "button_hole": (16.2, 7.78, 1.7, 18.8),  # Ø, flats at ±x, key width, key end y: FF01 cutout
    },
}


VENDOR = Path(__file__).resolve().parent.parent / "vendor/polymath-protective-stop"
FF01_SEAL = 10.0076  # FF01 STEP (Y up): underside of the seal, where the panel's top goes
RING_Y, RING_Z = 0.105, 2.48  # LED.step: ring centre is at y -0.105, its board's underside at z 2.48

# ESP32-P4-ETH (vendor/waveshare-esp32-p4-eth): STEP frame PCB top z 0 (components up), x 0..21, y 0..78, RJ45 end y 0
P4_STEP = Path(__file__).resolve().parent.parent / "vendor/waveshare-esp32-p4-eth/ESP32-P4-ETH_3d-20251219.stp"
P4_RJ45_FRONT = -0.865  # STEP y of the jack's face
P4_RJ45_MOUTH = (3.69, 17.31, 0.65, 10.57)  # STEP x0, x1 and height above the PCB of the plug opening
P4_PIN_TIP = 9.9  # STEP: pins reach 9.9 below the PCB top (8.3 past its back)
P4_HOLES_Y = (22.26, 76.42)  # STEP y of the M1.6 hole pairs, at x 1.38 and 19.62
P4_ROW_X = 19.39  # the pin row with VBUS (STEP x)
P4_PIN0_Y, PITCH = 25.07, 2.54  # STEP y of pin 21 (RJ45 end of that row); pin 21 + k is k pitches on
# VBUS (pin 40), GND (28) and GPIO27/32/33/46/47 (27, 26, 25, 24, 22): sockets kept clear of the button
P4_PINS = {"VBUS": 19, "GND": 7, "GPIO27": 6, "GPIO32": 5, "GPIO33": 4, "GPIO46": 3, "GPIO47": 1}
MODULE = (36.0, 14.7, 2.0)  # PoE Module (B): length, far face from the main PCB's top, its hole from its edge (user)
MODULE_GAP = 3.0  # module far face above the channel floor: posts tall enough for an M1.6 insert
SOCKET_H, BEND = 16.5, 6.0  # Dupont socket top above the PCB's back, wire bend room above that (assumed)
PIN_CLEAR, FF01_BELOW = 1.0, 13.6  # pin tips under the FF01's terminals; FF01 depth behind its panel
ADAPTER = (20.0, 12.0, 7.0)  # 90° USB-C adapter stand-in: length, width, height (guess)


def p4_frame(v):
    """Board placement (xb, yb, zb): STEP y 0 at world x xb, flipped so its PCB top (components) faces down at zb."""
    xb = v["pod_x0"] + v["chan_t"] - P4_RJ45_FRONT  # jack face against the end wall's inner face
    return xb, CY - 10.5, v["chan_floor"] + MODULE_GAP + MODULE[1]


def p4_height(v):
    """Lid underside: the larger of pins under the FF01's terminals and sockets plus wire bend; both, for the check."""
    zb = p4_frame(v)[2]
    pins = zb + P4_PIN_TIP + PIN_CLEAR + FF01_BELOW
    sockets = zb + 1.6 + SOCKET_H + BEND
    return max(pins, sockets), pins, sockets


def p4_variant():
    v = dict(VARIANTS["s3"], prefix="P4", chan_end=False, cross_hole=None, floor_hole=None, wire_slot=None)
    v["wall_notch"] = None
    xb, yb, zb = p4_frame(v)
    lb = p4_height(v)[0]
    v.update(rim=lb, pod_top=lb - 0.2, lid_bot=lb, lid_top=lb + 4.0)
    v["lip"] = v["lip"][:4] + (lb - 1.9,)
    # (84, 9) would sit on the USB-C adapter: two posts at ±40° instead
    a = math.radians(40)
    v["posts"] = v["posts"][:2] + v["posts"][3:] + [(CX + 38 * math.cos(a), CY + s * 38 * math.sin(a)) for s in (1, -1)]
    # module posts up to its far face at the header-end holes, board posts up to the PCB at the USB-C end
    ys = (yb + 1.38, yb + 19.62)
    # module posts Ø6 (Ø5 grazed the channel walls by 0.17 and broke the kernel) with M1.6 inserts; the board's
    # USB-C-end holes are 1.8 from its header row, so those posts are Ø3.4 with a pilot for M1.6 self-tapping screws
    v["standoffs"] = [(xb + P4_HOLES_Y[0], y, zb - MODULE[1], 6.0, 2.5) for y in ys]
    v["standoffs"] += [(xb + P4_HOLES_Y[1], y, zb, 3.4, 1.3) for y in ys]
    v["standoff_hole_depth"] = 4.0
    # plugging the RJ45 in pushes the board inward: lugs at its USB-C end's corners, clear of the USB-C, take that.
    # 0.34 off the board's end and off the thin posts (closer, the kernel trips over the near-touching faces)
    x0 = xb + 78 + 0.335
    v["board_stops"] = [(x0, x0 + 2.0, y - 1.5, y + 1.5, v["floor_top"] - 0.5, zb + 1.6) for y in ys]
    mx0, mx1, mz0, mz1 = P4_RJ45_MOUTH
    v["windows"] = {"RJ45": (yb + mx0 - 0.5, yb + mx1 + 0.5, zb - mz1 - 0.5, zb - mz0 + 0.5)}
    return v


def p4_standins(v):
    """Context boxes (x0, x1, y0, y1, z0, z1) for parts with no model: PoE module, Dupont sockets, USB-C adapter."""
    xb, yb, zb = p4_frame(v)
    m0 = xb + P4_HOLES_Y[0] - MODULE[2]
    sockets = []
    for k in P4_PINS.values():
        x, y = xb + P4_PIN0_Y + k * PITCH, yb + P4_ROW_X
        sockets.append(
            (x - PITCH / 2, x + PITCH / 2, y - PITCH / 2, y + PITCH / 2, zb + 1.6, zb + 1.6 + SOCKET_H + BEND)
        )
    ax = xb + 78 + 1.4
    al, aw, ah = ADAPTER
    return {
        "P4Module": [(m0, m0 + MODULE[0], yb, yb + 21, zb - MODULE[1], zb)],
        "P4Sockets": sockets,
        "P4Adapter": [(ax, ax + al, CY - aw / 2, CY + aw / 2, zb - 1.6 - ah / 2, zb - 1.6 + ah / 2)],
    }


VARIANTS["p4"] = p4_variant()


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

    def cyl(name, dia, x, y, z0, h, **kw):
        cmds.append(
            {
                "command": "solid.cylinder",
                "params": {"diameter": dia, "height": h, "base": [x, y, z0], "body_name": name, **kw},
            }
        )

    def hole(top, dia, depth, body):
        cmds.append(
            {"command": "solid.hole", "params": {"position": top, "diameter": dia, "depth": depth, "targets": [body]}}
        )

    def combine(target, tools, op):
        cmds.append({"command": "solid.combine", "params": {"target": target, "tools": tools, "operation": op}})

    for key, v in VARIANTS.items():

        def mark(stage, key=key):
            marks[f"{key}:{stage}"] = len(cmds)

        P = v["prefix"]
        base = P + "Base"
        y0, y1 = v["pod_y"]
        t = v["chan_t"]
        ym = (y0 + y1) / 2
        # fillet each primitive before combining: on the hollowed body the r3.2 blend outgrows the 3.2 wall. The pod
        # box reaches into the wall; ending it on the body's surface, as Polymath's does, makes the join fail
        cyl(base, 2 * v["r_out"], CX, CY, v["z_bot"], v["rim"] - v["z_bot"])
        box(P + "pod", v["pod_x0"], CX - v["r_in"] - 1, y0, y1, v["z_bot"], v["pod_top"])
        mark("base_layout")
        cmds.append(
            {
                "command": "solid.fillet",
                "params": {"body": base, "radius": v["fillet_body"], "edges": [[CX + v["r_out"], CY, v["z_bot"]]]},
            }
        )
        pod_edges = [[v["pod_x0"], ym, v["z_bot"]]]  # Polymath rounds only the end wall's bottom edge
        cmds.append(
            {"command": "solid.fillet", "params": {"body": P + "pod", "radius": v["fillet_pod"], "edges": pod_edges}}
        )
        mark("base_fillets")
        cyl(P + "interior", 2 * v["r_in"], CX, CY, v["floor_top"], v["rim"], operation="cut", targets=[base])
        # pod box only reaches into the body wall; inside, the channel walls stand on the floor
        # down into the floor: flush on its top face, the export keeps an internal face there
        box(P + "chanwalls", CX - v["r_in"] - 1, v["chan_x1"], y0, y1, v["chan_floor"], v["pod_top"])
        combine(base, [P + "pod", P + "chanwalls"], "join")
        cx1 = v["chan_x1"] - t if v["chan_end"] else v["chan_x1"] + 1
        box(P + "channel", v["pod_x0"] + t, cx1, y0 + t, y1 - t, v["chan_floor"], v["rim"] + 1)
        combine(base, [P + "channel"], "cut")
        mark("channel")
        for i, (x, y) in enumerate(v["posts"]):
            cyl(f"{P}post{i}", v["post_d"], x, y, v["floor_top"], v["rim"] - v["floor_top"])
        combine(base, [f"{P}post{i}" for i in range(len(v["posts"]))], "join")
        mark("posts")
        for x, y in v["posts"]:
            hole([x, y, v["rim"]], v["post_hole_d"], v["rim"] - v["floor_top"], base)
        mark("post_holes")
        # plain posts sunk 0.5 into the floor (a flush join is refused). Polymath rounds their feet r2; blending that
        # onto the floor between the walls is refused and blending it on a scratch body makes the join take minutes
        fl = v["chan_floor"]
        tools = [f"{P}so{i}" for i in range(len(v["standoffs"]))]
        for so, (x, y, top, dia, _) in zip(tools, v["standoffs"]):
            cyl(so, dia, x, y, fl - 0.5, top - fl + 0.5)
        combine(base, tools, "join")
        mark("standoffs")
        for x, y, top, _, hole_d in v["standoffs"]:
            hole([x, y, top], hole_d, v["standoff_hole_depth"], base)
        mark("standoff_holes")
        x0 = v["pod_x0"]
        for n, (wy0, wy1, wz0, wz1) in v["windows"].items():
            box(f"{P}win{n}", x0 - 1, x0 + t + 1, wy0, wy1, wz0, wz1, operation="cut", targets=[base])
        mark("windows")
        for i, b in enumerate(v.get("board_stops", [])):
            box(f"{P}stop{i}", *b, operation="join", targets=[base])
        mark("board_stops")
        if v.get("cross_hole"):
            x, z, dia = v["cross_hole"]
            cyl(f"{P}cross", dia, x, y0 - 1, z, y1 - y0 + 2, axis="Y", operation="cut", targets=[base])
        if v.get("floor_hole"):
            x, y, dia = v["floor_hole"]
            h = v["chan_floor"] - v["z_bot"] + 1
            cyl(f"{P}floorhole", dia, x, y, v["z_bot"] - 1, h, operation="cut", targets=[base])
        if v.get("wire_slot"):
            y, z, r = v["wire_slot"]
            xe = v["chan_x1"] - t - 1
            cyl(f"{P}slot", 2 * r, xe, y, z, t + 2, axis="X")
            low = (xe - 1, xe + t + 3, y - r - 1, y + r + 1, z - r - 1, z)
            box(f"{P}slotlow", *low, operation="cut", targets=[f"{P}slot"])
            combine(base, [f"{P}slot"], "cut")
        mark("small_holes")
        if v.get("wall_notch"):
            x, dia = v["wall_notch"]
            cyl(f"{P}notch", dia, x, y0 - 1, v["pod_top"], y1 - y0 + 2, axis="Y", operation="cut", targets=[base])
        mark("wall_notches")

        # --- lid: plate over body and pod, a lip only into the pod channel, the diffuser in a hole over the ring
        lid = P + "Lid"
        lb, lt = v["lid_bot"], v["lid_top"]
        cyl(lid, 2 * v["r_out"], CX, CY, lb, lt - lb)
        box(P + "lidpod", v["pod_x0"], CX - v["r_in"] - 1, y0, y1, lb, lt)
        combine(lid, [P + "lidpod"], "join")
        mark("lid_layout")
        edges = [[CX + v["r_out"], CY, lt], [v["pod_x0"], ym, lt], [-10, y0, lt], [-10, y1, lt]]
        cmds.append({"command": "solid.fillet", "params": {"body": lid, "radius": v["lid_fillet"], "edges": edges}})
        mark("lid_fillet")
        lx0, lx1, ly0, ly1, lz0 = v["lip"]
        box(P + "lip", lx0, lx1, ly0, ly1, lz0, lb + 0.5)  # into the plate: a flush join is refused
        combine(lid, [P + "lip"], "join")
        mark("lip")
        hole([CX, CY, lt], v["diffuser_d"], lt - lb, lid)
        mark("diffuser_hole")
        for x, y in v["posts"]:
            cmds.append(
                {
                    "command": "solid.hole",
                    "params": {
                        "position": [x, y, lt],
                        "diameter": v["screw_d"],
                        "type": "counterbore",
                        "cb_diameter": v["cb_d"],
                        "cb_depth": v["cb_depth"],
                        "targets": [lid],
                    },
                }
            )
        mark("lid_holes")

        # --- diffuser: a disc with the ring's pocket underneath, snap bumps holding the ring, the button's hole
        dif = P + "Diffuser"
        cyl(dif, v["diffuser_d"], CX, CY, lb, lt - lb)
        mark("diffuser_layout")
        pr0, pr1, skin = v["ring_pocket"]
        ptop = lt - skin
        cyl(P + "pocket", 2 * pr1, CX, CY, lb - 1, ptop - lb + 1)
        cyl(P + "hub", 2 * pr0, CX, CY, lb - 2, ptop - lb + 3)
        combine(P + "pocket", [P + "hub"], "cut")
        combine(dif, [P + "pocket"], "cut")
        mark("ring_pocket")
        br0, bw, bh = v["ring_bumps"]
        for i, (dx, dy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
            r_mid = (br0 + pr1 + 0.2) / 2
            ln, wd = pr1 + 0.2 - br0, bw  # radial, tangential; 0.2 into the pocket wall
            sx, sy = (ln, wd) if dx else (wd, ln)
            cx, cy = CX + dx * r_mid, CY + dy * r_mid
            box(
                f"{P}bump{i}",
                cx - sx / 2,
                cx + sx / 2,
                cy - sy / 2,
                cy + sy / 2,
                lb,
                lb + bh,
                operation="join",
                targets=[dif],
            )
        mark("ring_bumps")
        bd, flat, key_w, key_y = v["button_hole"]
        cyl(P + "btn", bd, CX, CY, lb - 1, lt - lb + 2)
        box(
            P + "btnflats",
            CX - flat,
            CX + flat,
            CY - bd,
            CY + bd,
            lb - 2,
            lt + 2,
            operation="intersect",
            targets=[P + "btn"],
        )
        box(P + "btnkey", CX - key_w / 2, CX + key_w / 2, CY, key_y, lb - 1, lt + 1)
        combine(P + "btn", [P + "btnkey"], "join")
        combine(dif, [P + "btn"], "cut")
        mark("button_hole")

        for part in ("base", "lid", "diffuser"):
            for fmt in ("stl", "step"):
                path = os.path.join(d, f"{NAME}-{key}-{part}.{fmt}")
                cmds.append({"command": "file.export", "params": {"path": path, "bodies": [P + part.capitalize()]}})

    # --- p4 context, never exported: board, stand-ins, button and ring
    v = VARIANTS["p4"]
    xb, yb, zb = p4_frame(v)
    lb, lt = v["lid_bot"], v["lid_top"]
    for n, boxes in p4_standins(v).items():
        for i, b in enumerate(boxes):
            box(f"{n}{i}" if i else n, *b)
        if len(boxes) > 1:
            combine(n, [f"{n}{i}" for i in range(1, len(boxes))], "join")
    for x, y, top, *_ in v["standoffs"][:2]:  # the module's holes, where its screws pass
        cyl("P4modhole", 2.2, x, y, top - 1, MODULE[1] + 2, operation="cut", targets=["P4Module"])
    m = [0, 1, 0, xb, 1, 0, 0, yb, 0, 0, -1, zb]  # STEP y along world x, flipped: components down
    cmds.append({"command": "file.insert_step", "params": {"path": str(P4_STEP), "name": "P4Board", "matrix": m}})
    # the FF01 STEP is Y-up with no panel between seal and nut: seal on the diffuser, nut down by the hub's thickness
    m = [1, 0, 0, CX, 0, 0, -1, CY, 0, 1, 0, lt - FF01_SEAL]
    cmds.append(
        {
            "command": "file.insert_step",
            "params": {"path": str(VENDOR / "FF0126BBCAEA01.stp"), "name": "FF01", "matrix": m},
        }
    )
    cmds.append({"command": "solid.move", "params": {"bodies": ["FF01N"], "translate": [0, -(lt - lb), 0]}})
    # the ring board rests on the diffuser's snap bumps, LEDs up
    m = [1, 0, 0, CX, 0, 1, 0, CY + RING_Y, 0, 0, 1, lb + v["ring_bumps"][2] - RING_Z]
    cmds.append(
        {"command": "file.insert_step", "params": {"path": str(VENDOR / "LED.step"), "name": "Ring", "matrix": m}}
    )
    for bodies, color in (
        (["P4Base", "S3Base"], "#e8e8e8"),
        (["P4Lid", "S3Lid"], "#f0c020"),
        (list(p4_standins(v)), "#b8bcc2"),
    ):
        cmds.append({"command": "appearance.assign", "params": {"bodies": bodies, "color": color}})
    # s3 beside p4 in the render
    cmds.append(
        {"command": "solid.move", "params": {"bodies": ["S3Base", "S3Lid", "S3Diffuser"], "translate": [0, -120, 0]}}
    )
    return cmds, marks


if __name__ == "__main__":
    d = os.path.abspath(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    )
    os.makedirs(d, exist_ok=True)
    Path(d, f"{NAME}.json").write_text(json.dumps({"commands": build(d)[0]}, indent=1))
