#!/usr/bin/env python3
"""Create a new KiCad project from the reusable SBC project template."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATE = REPOSITORY / "templates" / "General-Project"
ROOT_FILES = (
    "General-Project.kicad_pro",
    "General-Project.kicad_sch",
    "General-Project.kicad_pcb",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--name", help="root project filename stem (default: directory name)")
    args = parser.parse_args()

    destination = args.destination.resolve()
    name = args.name or destination.name
    if not name or "/" in name or "\\" in name:
        parser.error("project name must be a non-empty filename stem")
    if destination.exists() and any(destination.iterdir()):
        parser.error(f"destination is not empty: {destination}")

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True)

    for filename in ROOT_FILES:
        source = destination / filename
        source.rename(destination / filename.replace("General-Project", name, 1))

    for path in destination.glob("*.kicad_sch"):
        text = path.read_text()
        text = text.replace('(project "General-Project"', f'(project "{name}"')
        path.write_text(text)

    project = destination / f"{name}.kicad_pro"
    text = project.read_text()
    text = text.replace('"filename": "General-Project.kicad_pro"', f'"filename": "{name}.kicad_pro"')
    text = text.replace('"filename": "General-Project.kicad_sch"', f'"filename": "{name}.kicad_sch"')
    text = text.replace('"name": "General-Project"', f'"name": "{name}"')
    project.write_text(text)
    print(f"Created {destination}")
    print(f"Open {name}.kicad_pro in KiCad 10 or newer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
