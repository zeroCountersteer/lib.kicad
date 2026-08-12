#!/usr/bin/env python3
"""Make custom model references portable without touching stock KiCad paths."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "3dmodels" / "lib.3dshapes"
MODEL_BLOCK = re.compile(r'\n\s*\(model\s+"([^"]+)".*?\n\s*\)', re.S)


def rewrite(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")

    def replace(match: re.Match[str]) -> str:
        model = match.group(1)
        if model.startswith(("${", "http:", "https:")):
            return match.group(0)
        filename = Path(model.replace("\\", "/")).name
        if (MODEL_ROOT / filename).is_file():
            return match.group(0).replace(model, f"${{KICAD10_3RD_PARTY}}/3dmodels/lib.3dshapes/{filename}")
        # This is an absolute reference to a model outside this repository;
        # dropping only that model avoids shipping a broken machine path.
        return ""

    path.write_text(MODEL_BLOCK.sub(replace, text), encoding="utf-8")


for footprint in sorted((ROOT / "footprints").rglob("*.kicad_mod")):
    rewrite(footprint)
