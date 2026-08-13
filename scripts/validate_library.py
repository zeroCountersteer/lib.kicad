#!/usr/bin/env python3
"""Focused structural checks for the maintained KiCad library."""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def numbers(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text, re.M)


def check_equal(label: str, left: set[str], right: set[str]) -> None:
    if left != right:
        raise AssertionError(f"{label}: missing={sorted(left-right)} unexpected={sorted(right-left)}")


def main() -> int:
    a33_sym = (ROOT / "symbols/SoC_Allwinner.kicad_sym").read_text()
    a33_fp = (ROOT / "footprints/Package_SoC.pretty/Allwinner_A33_TFBGA282_14x14mm_P0.8mm.kicad_mod").read_text()
    axp_sym = (ROOT / "symbols/PMIC_XPowers.kicad_sym").read_text()
    axp_fp = (ROOT / "footprints/Package_PMIC.pretty/XPowers_AXP223_QFN-68-1EP_8x8mm_P0.4mm.kicad_mod").read_text()
    a33_pins = set(numbers(a33_sym, r'^\s*\(number "([A-U](?:1[0-7]|[1-9]))"'))
    a33_pads = set(numbers(a33_fp, r'^\s*\(pad ([A-U](?:1[0-7]|[1-9]))\s'))
    if len(a33_pins) != 282 or len(a33_pads) != 282:
        raise AssertionError(f"A33 count mismatch: symbol={len(a33_pins)} footprint={len(a33_pads)}")
    check_equal("A33 symbol/footprint balls", a33_pins, a33_pads)
    if '(name "PG8"' not in a33_sym or '(number "B16"' not in a33_sym:
        raise AssertionError("A33 PG8 is not mapped to B16")
    if '(name "PG9"' not in a33_sym or '(number "A16"' not in a33_sym:
        raise AssertionError("A33 PG9 is not mapped to A16")
    if not all(token in a33_fp for token in ('-6.4000000000', '0.8000000000', '7.0000000000')):
        raise AssertionError("A33 package geometry markers missing")

    axp_pins = set(numbers(axp_sym, r'^\s*\(number "(\d+)"'))
    axp_pads = set(numbers(axp_fp, r'^\s*\(pad (\d+)\s'))
    expected = {str(i) for i in range(1, 70)}
    check_equal("AXP223 symbol/footprint pads", expected, axp_pins)
    check_equal("AXP223 footprint pads", expected, axp_pads)
    if '(name "EP/GND"' not in axp_sym or '(number "69"' not in axp_sym:
        raise AssertionError("AXP223 exposed pad 69 is not EP/GND")
    if '(pad 69 smd rect (at 0 0) (size 5.59 5.59) (layers "F.Cu" "F.Mask"))' not in axp_fp:
        raise AssertionError("AXP223 pad 69 copper/mask definition is unexpected")
    if axp_fp.count('(layer "F.Paste")') < 3:
        raise AssertionError("AXP223 exposed pad has no windowed paste apertures")
    for file in ROOT.rglob("*"):
        if file.is_file() and file.suffix in {".kicad_mod", ".kicad_sym", ".json", ".yml", ".yaml"}:
            text = file.read_text(encoding="utf-8", errors="ignore")
            if any(bad in text for bad in ("C:/Users/", "Documents/GitHub/", "/home/az/")):
                raise AssertionError(f"development path remains in {file}")
    package = ROOT / "dist/lib.KiCAD-0.1.0.zip"
    if package.is_file():
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            for name in names:
                if not name.endswith(".kicad_mod"):
                    continue
                content = archive.read(name).decode("utf-8", errors="ignore")
                for model in re.findall(r'\(model "(\$\{KICAD10_3RD_PARTY\}/3dmodels/lib\.3dshapes/[^"]+)"', content):
                    relative = model.split("/3dmodels/", 1)[1]
                    if f"3dmodels/{relative}" not in names:
                        raise AssertionError(f"package model reference does not resolve: {name}: {model}")
            for table in ("fp-lib-table", "sym-lib-table"):
                if table not in names:
                    raise AssertionError(f"package library table is missing: {table}")
    print("A33: 282/282 balls, PG8=B16, PG9=A16")
    print("AXP223: pads 1..69, EP/GND=69, windowed exposed-pad paste")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
