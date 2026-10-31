# Agent notes

How parts are built is in README.md. These are the traps that cost time before.

## Tools
- `solidcraft-cli` is pinned in `mise.toml`; after bumping it, rebuild every part and run its `check.py`, since kernel
  changes can move geometry. `check.py` honours `SOLIDCRAFT_CLI`.
- If `solidcraft-cli` produces no output at all, the OS may be blocking an unsigned binary; test it with
  `solidcraft-cli commands` before debugging anything else.
- `solidcraft-cli commands` dumps every command with its params as JSON (large; filter it).
- `file.insert_mesh` names the occurrence `<name>:1`; `occurrence.move` takes a row-major 3x4 `matrix`.
- The first part inserted into a design is grounded: `occurrence.move` refuses it without `move_grounded: true`.
- `solid.move` `translate` is in world axes, also for bodies of a rotated occurrence (0.20 used the occurrence's
  local axes); the command docs don't say so, and nothing errors when a body goes the wrong way.
- `inspect.interference` skips mesh bodies and `mesh.convert` only handles constant-section meshes, so clearance to the
  vendor unit models is checked in Python against the exported STL (see `poe-rs485-3030-mount/check.py`).

## CLI or MCP
- CLI (`mise run build|check`, `solidcraft-cli run`) for anything that produces or proves a part: generator changes,
  exports, checks, comparing versions, and any work in parallel (subagents, worktrees). It rebuilds from an empty design
  at the pinned version every run.
- MCP (`solidcraft` in `.mcp.json`: the pinned CLI, headless, repo paths only) for finding out what to write: look
  (`screenshot`), find an edge point for a fillet (`body_topology`), read a clearance (`measure`), try a feature and
  undo it. `mise run build <part>`, then `open` `out/<part>.solidcraft` (`open` refuses the `.json` build script).
- Nothing made over MCP is kept: `out/` is rebuilt by every build. Put what worked into the generator, then prove it
  with `mise run check`. The MCP holds one design shared by everyone in the session, so one agent at a time.

## Working on a part
- Every part has a `README.md` in the same shape as `poe-rs485-3030-mount/README.md`: purpose, the render
  (`out/<part>.png`, re-rendered by every build), bill of materials, printing, assembly, design notes (the reasons
  the code can't show), status/known issues, files. Changing a part means updating its Design notes and Status;
  the root README only links to part READMEs.
- A part is a folder with `check.py` and a generator `<part_name>.py` matching the folder `<part-name>`; `tools/parts.py`
  finds parts by that convention, and outputs are named via the generator's `NAME`.
- Before calling work done: `mise run check` and `mise run lint` both pass. A new feature gets a check, and the
  check is seen failing on a broken copy before it is trusted. A cut or fillet that reports success but leaves the
  volume unchanged has missed its edge.
- `vendor/<supplier>-<part>/` holds supplier CAD shared by parts (STEP plus the supplier's metadata txt); context only,
  never exported. The RS 264-7862 STEP is a 100 mm piece along +Y; generators stretch it with `solid.press_pull`.
- `units/` holds trimmed vendor meshes; the originals are no longer available, so don't overwrite them.
- Confirm port and connector positions with the user; the vendor meshes don't always model them (the PoE-P4 RJ45 isn't).
  Read hole and opening geometry from the mesh by vertical ray casting: planar slices have misread through-holes as
  blind and openings as material.

## poe-rs485-3030-mount
- Frame: plate top z=0, extrusion along X under y=12. PoE-P4 x -0.7..63.3, y 0..24.
- PoE-P4 ports: RJ45 and USB-C on the +X face (nothing of the bracket at or beyond x 63.3), Grove on -Y, side button on +Y.
- RS485-ISO lies flat beyond the PoE's -X end, Grove end facing it; its LEGO holes are through-holes
  (bore Ø4.85, Ø6.2 counterbores top and bottom).
- Design reasons and known issues are in its README.
