# Prusa Core One camera case (ESP32-CAM and DFR1154)

A camera for the inside top corner of a Prusa Core One, for the
[`prusa_cam`](https://github.com/rosterloh/zephyr-applications/tree/main/applications/prusa_cam) firmware. A hex plate
sits in the corner on three magnets, and a cup holding the camera screws under it with three M3 screws.

- **esp32cam**: the [Prusa Core One ESP32 camera case](https://www.printables.com/model/1205313-prusa-core-one-esp32-camera-case)
  from Printables (plate, cup for the AI-Thinker ESP32-CAM, U-bracket), rebuilt as a generator and checked against
  its STLs. Licence not confirmed; the STLs are not in this repo.
- **dfr1154**: a new cup for the DFRobot [DFR1154](https://wiki.dfrobot.com/dfr1154) (ESP32-S3, OV3660 160° lens, IR
  LEDs, mic, ambient light sensor) that screws onto the same plate, so an installed plate stays where it is.

![ISO view: esp32cam plate, cup and bracket left, dfr1154 cup with a stand-in board right](out/prusa-core-one-camera.png)

## Bill of materials

| Qty | esp32cam | dfr1154 |
|-----|----------|---------|
| 1 | `out/prusa-core-one-camera-plate.stl` (shared) | the same plate, already installed |
| 1 | `out/prusa-core-one-camera-esp32cam-cup.stl` | `out/prusa-core-one-camera-dfr1154-cup.stl` |
| 1 | `out/prusa-core-one-camera-bracket.stl` (optional) | - |
| 3 | Ø8 × 3 round magnets | same |
| 3 | M3 × 6 self-tapping screws, plate to cup | same |
| 4 | - | M3 × 6 self-tapping screws, board to cup |
| 1 | AI-Thinker ESP32-CAM | DFRobot DFR1154 + straight USB-C cable |

STEP files sit beside each STL.

## Printing

No supports, PLA or PETG. Plate legs up. Cups front face down. The dfr1154 cup's bosses hang from the rim with
45° undersides; its front wall's lens funnel overhangs about 3 mm at 26° across the 1.6 mm wall.

## Assembly (dfr1154)

1. Lay the board in the cup camera side down, logo edge toward the cup's top corner (the corner opposite the USB
   slot). Screw it onto the four posts.
2. Plug the USB-C cable through the slot in the bottom corner.
3. Unscrew the old cup from the plate. Screw the new one on in the position that leaves the USB slot at the bottom.
   The picture is upright when the logo edge points up. If it comes out upside down, set vflip and hflip in the
   firmware. The firmware's rotation setting only fixes Prusa Connect and snapshots, not the stream.

## Design notes

- The joint (rim outline, three Ø2.5 × 4 pilots with a 1 mm lead-in at radius 25.91, angles 180° and ±60°) is the
  original cup's. `check.py` compares the two cups there.
- Straight hex rather than the original taper. The 42 mm board needs ~59 mm across the flats inside, which the
  tapered cup only has in its last few mm, and with the board that deep the 160° lens would see the walls.
- The lens sits 1 mm behind the front wall. The opening is a 4:3 funnel: 160° is taken as the picture's diagonal,
  so 64° across and 48° along. A round 80° cone would merge with the IR LED windows.
- Each IR LED, the light sensor and the mic has a tube from the front wall to 0.3 mm off the board. The board sits
  7.5 mm behind the wall (the camera module's height), so without tubes the IR would bounce inside onto the lens.
- The 42 mm board overlaps the screw circle however it is turned, so the bosses are 6 mm gussets hanging from the
  rim (the original's are 8). The +60° boss sits over the USB plug, and that sets the cup's depth (22.3 mm).
- Vents: three slots in each wall without a boss or the USB slot, behind the board.
- The original's vents were placed by hand per wall, so the generator keeps a table per wall.

## Status

Not printed. **The DFR1154 dimensions are estimates** from DFRobot's function diagram and dimension drawing (PCB
v1.0). Before printing, measure the board and update the constants at the top of the generator:

- `CAM_H` (lens front above the PCB) and `BACK_H` (screw terminal): these set the cup's depth.
- `USB_X`, `USB_Z` and the plug size, plus the positions of `CAM`, `IR`, `MIC`, `ALS` and `BACK_PARTS`.
- The PCB revision: a v1.1 board may have a different layout.

Known issues:

- Unconfirmed: which way the sensor's long side lies (the funnel assumes across the board), and whether 160° is the
  diagonal.
- The tubes could hit small parts on the board's camera side that DFRobot's diagram doesn't show.
- The esp32cam rebuild is matched to the STLs (≤0.1 % surface misses at 0.5 mm, volume within 0.5 %). The
  Printables licence hasn't been checked (the page refused automated access).

## Files

| Path | What |
|------|------|
| `prusa_core_one_camera.py` | Generator: every dimension is a named constant at the top |
| `check.py` | STL match (esp32cam, reads the STLs from `$PRUSA_CAM_REF`, default `~/Downloads/3D`; SKIP when missing), cut volumes, the dfr1154 joint, fit and openings; must pass (`mise run check prusa-core-one-camera`) |
| `out/` | STL and STEP to print, and this README's render |
