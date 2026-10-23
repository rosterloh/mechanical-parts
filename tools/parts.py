# Builds and checks parts. A part is a folder holding check.py and a generator named after the folder
# (poe-rs485-3030-mount/poe_rs485_3030_mount.py); outputs go to <part>/out/<part>.{json,solidcraft,stl,step,png}.
# The .png is the ISO view the part's README shows, so it is re-rendered on every build.
# usage: python tools/parts.py build|check [part ...]   (no part: all of them)
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")


def parts():
    return sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "check.py")))


def run(cmd, cwd):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False).returncode == 0


def build(part):
    d = os.path.join(ROOT, part)
    out = os.path.join("out", part)
    return (
        run([sys.executable, part.replace("-", "_") + ".py"], d)
        and run([SC, "run", out + ".json", "--save", out + ".solidcraft", "--quiet"], d)
        and run(
            [
                SC,
                "snapshot",
                "--in",
                out + ".solidcraft",
                "--out",
                out + ".png",
                "--view",
                "iso",
                "--no-grid",
                "--no-axes",
                "--width",
                "1200",
                "--height",
                "700",
            ],
            d,
        )
    )


def check(part):
    return build(part) and run([sys.executable, "check.py"], os.path.join(ROOT, part))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("build", "check"):
        sys.exit("usage: python tools/parts.py build|check [part ...]")
    known = parts()
    chosen = sys.argv[2:] or known
    unknown = [p for p in chosen if p not in known]
    if unknown:
        sys.exit(f"unknown part(s) {unknown}; parts: {known}")
    failed = [p for p in chosen if not {"build": build, "check": check}[sys.argv[1]](p)]
    if failed:
        sys.exit(f"failed: {failed}")
