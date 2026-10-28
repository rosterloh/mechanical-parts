# mechanical-parts

3D-printable brackets and mounts, one folder per part. Each part is generated from a Python script with SolidCraft;
its README covers what it holds, what to buy, how to print and assemble it, and its current status.

## Parts

- [PoE-P4 + RS485-ISO 30x30 extrusion mount](poe-rs485-3030-mount/README.md)
- [JH-D400X-R4 joystick + ESP32-P4 PoE box](joystick-p4-box/README.md)
- [reBot B601-RS power supply covers for a Mean Well HRPG-600-48](rebot-psu-covers/README.md)
- [Protective-stop E-stop remote, ESP32-S3 and ESP32-P4 variants](protective-stop-remote/README.md)

## Building

Tools are pinned in `mise.toml` (solidcraft-cli, Python, ruff). In the repo:

```sh
mise install                          # once per checkout (and `mise trust` the first time)
mise run check                        # generate, build and render every part, then run each part's check.py
mise run check poe-rs485-3030-mount   # just one part; `mise run build` skips the checks
mise run fmt                          # format Python; `mise run lint` checks lint + formatting
```

Each part's outputs land in `<part>/out/`: STL and STEP to print, and the render its README shows.
`SOLIDCRAFT_CLI` overrides which solidcraft-cli is used.

`vendor/` holds supplier CAD shared between parts (e.g. the RS PRO 264-7862 profile STEP, from RS via TraceParts);
it appears in renders for context and is never exported. The Waveshare board STEP (27 MB) is in Git LFS: run
`git lfs install` before cloning, or `git lfs pull` after.
