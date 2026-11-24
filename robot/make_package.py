#!/usr/bin/env python3
"""Build dist/oasis_voice_robot.zip: the one file to copy onto the robot.

Run from the repo root:  python3 robot/make_package.py
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "dist")
OUT = os.path.join(OUT_DIR, "oasis_voice_robot.zip")
TOP = "oasis_voice_robot"

FILES = [
    # (source, path inside the zip)
    ("robot/package/run_robot.sh", "run_robot.sh"),
    ("robot/package/config.env.example", "config.env.example"),
    ("robot/package/QUICKSTART.md", "QUICKSTART.md"),
    ("robot/elevenlabs_robot_bridge.py", "original_bridge/elevenlabs_robot_bridge.py"),
]
DIRS = [("sdk/oasis_voice", "oasis_voice"), ("sdk/profiles", "profiles"), ("sdk/state", "state")]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for src, dst in FILES:
            info = zipfile.ZipInfo.from_file(os.path.join(ROOT, src), f"{TOP}/{dst}")
            if dst.endswith(".sh"):
                info.external_attr = 0o755 << 16  # keep it executable
            with open(os.path.join(ROOT, src), "rb") as f:
                z.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
            count += 1
        for src, dst in DIRS:
            base = os.path.join(ROOT, src)
            for folder, subdirs, names in os.walk(base):
                subdirs[:] = [d for d in subdirs if d != "__pycache__"]
                for name in sorted(names):
                    if name.endswith((".pyc", ".pyo")) or name.startswith("."):
                        continue
                    full = os.path.join(folder, name)
                    z.write(full, f"{TOP}/{dst}/{os.path.relpath(full, base)}")
                    count += 1
    print(f"Built {os.path.relpath(OUT, ROOT)} ({count} files, {os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
