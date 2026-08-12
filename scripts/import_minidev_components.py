#!/usr/bin/env python3
"""Convert the two audited legacy MiniDev components to KiCad 10 syntax.

This is intentionally kept as an auditable, deterministic importer rather than
copying the MiniDev project.  The input checkout is supplied explicitly and is
not part of the library repository.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

PIN_RE = re.compile(r"^X\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\d+)\s+([LRUD])\s+\d+\s+\d+\s+(\d+)\s+\d+\s+(\S+)")


def esc(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def pin_type(name: str, manufacturer: str) -> str:
    upper = name.upper()
    if manufacturer == "A33":
        if upper in {"NMI", "RESET"}:
            return "input"
        if upper.startswith(("V", "A", "GND")) and upper not in {"USB-DM0", "USB-DP0", "USB-DM1", "USB-DP1"}:
            return "power_in"
        return "bidirectional"
    if upper.startswith("EP") or "PGND" in upper or upper.startswith("GND"):
        return "power_in"
    if upper.startswith(("VIN", "ACIN", "VBUS", "BATSENSE", "CHSENSE", "TS", "SCK", "SDA")):
        return "power_in" if upper.startswith(("VIN", "ACIN", "VBUS")) else "bidirectional"
    if upper.startswith(("DCDC", "ALDO", "DLDO", "ELDO", "VREF", "PWROK", "VINT", "IPSOUT")):
        return "power_out"
    if upper.startswith(("GPIO", "IRQ", "PWRON")):
        return "bidirectional"
    return "passive"


def parse_legacy(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    definition = next(line for line in lines if line.startswith("DEF ")).split()
    name = definition[1]
    units = int(definition[7])
    pins = []
    for line in lines:
        match = PIN_RE.match(line)
        if match:
            pname, number, x, y, length, orientation, unit, ptype = match.groups()
            pins.append({"name": pname, "number": number, "x": int(x), "y": int(y), "length": int(length), "orientation": orientation, "unit": int(unit), "legacy_type": ptype})
    return name, units, pins


def property_block(name: str, value: str, hidden: bool = True) -> str:
    hide = f"\n\t\t\t(hide {'yes' if hidden else 'no'})" if hidden else ""
    return f'''\t\t(property "{name}" "{esc(value)}"
\t\t\t(at 0 0 0)
\t\t\t(show_name no)
\t\t\t(do_not_autoplace no)
{hide}\n\t\t\t(effects (font (size 1.27 1.27)))
\t\t)'''


def make_symbol(name: str, units: int, pins: list[dict], manufacturer: str, footprint: str, datasheet: str, description: str) -> str:
    out = ["(kicad_symbol_lib", "\t(version 20251024)", '\t(generator "kicad_symbol_editor")', '\t(generator_version "10.0")', f'\t(symbol "{name}"',
           "\t\t(pin_names", "\t\t\t(offset 1.016)", "\t\t)", "\t\t(exclude_from_sim no)", "\t\t(in_bom yes)", "\t\t(on_board yes)", "\t\t(in_pos_files yes)", "\t\t(duplicate_pin_numbers_are_jumpers no)", property_block("Reference", "U", False),
           property_block("Value", name, False), property_block("Footprint", footprint),
           property_block("Datasheet", datasheet), property_block("Description", description),
           property_block("Manufacturer", manufacturer), property_block("MPN", name)]
    unit_values = [0] if units == 1 else list(range(1, units + 1))
    grouped = {unit: [p for p in pins if p["unit"] == unit] for unit in unit_values}
    if units > 1:
        xs = [p["x"] * 0.0254 for p in pins]
        ys = [p["y"] * 0.0254 for p in pins]
        out += [f'\t\t(symbol "{name}_0_1"', f'\t\t\t(rectangle (start {min(xs)-5.08:.4f} {max(ys)+2.54:.4f}) (end {max(xs)+5.08:.4f} {min(ys)-2.54:.4f})', '\t\t\t\t(stroke (width 0) (type default)) (fill (type background)))', '\t\t)']
    for unit, unit_pins in grouped.items():
        if not unit_pins:
            continue
        xs = [p["x"] * 0.0254 for p in unit_pins]
        ys = [p["y"] * 0.0254 for p in unit_pins]
        left, right = min(xs) - 5.08, max(xs) + 5.08
        bottom, top = min(ys) - 2.54, max(ys) + 2.54
        suffix = "0" if units == 1 else "1"
        out += [f'\t\t(symbol "{name}_{unit}_{suffix}"',
                f'\t\t\t(rectangle (start {left:.4f} {top:.4f}) (end {right:.4f} {bottom:.4f})',
                '\t\t\t\t(stroke (width 0) (type default)) (fill (type background)))']
        for p in unit_pins:
            x, y, length = p["x"] * 0.0254, p["y"] * 0.0254, p["length"] * 0.0254
            angle = {"R": 0, "L": 180, "U": 90, "D": 270}[p["orientation"]]
            out += [f'\t\t\t(pin {pin_type(p["name"], manufacturer)} line', f'\t\t\t\t(at {x:.4f} {y:.4f} {angle})', f'\t\t\t\t(length {length:.4f})',
                    f'\t\t\t\t(name "{esc(p["name"])}" (effects (font (size 0.9 0.9))))', f'\t\t\t\t(number "{p["number"]}" (effects (font (size 0.9 0.9))))', '\t\t\t)']
        out.append("\t\t)")
    out += ["\t)", "\t(embedded_fonts no)", ")", ""]
    return "\n".join(out)


def convert_footprint(source: Path, destination: Path, name: str, axp: bool = False) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    if axp:
        # Convert the legacy module wrapper and add a modern header.
        text = re.sub(r'^\(module\s+([^\s]+).*?\n', f'(footprint "{name}"\n  (version 20240108)\n  (generator pcbnew)\n  (layer "F.Cu")\n', text, count=1, flags=re.S)
        text = text.replace("(fp_text reference IC**", '(fp_text reference REF**')
        text = text.replace('(fp_text user %R', '(fp_text user "%R"')
        text = text.replace('(fp_text value "QFN40P800X800X80-69N-D"', f'(fp_text value "{name}"')
        paste_windows = []
        for x in (-1.6, 0.0, 1.6):
            for y in (-1.6, 0.0, 1.6):
                paste_windows.append(f'  (fp_rect (start {x - 0.55:g} {y - 0.55:g}) (end {x + 0.55:g} {y + 0.55:g}) (stroke (width 0) (type default)) (fill solid) (layer "F.Paste"))')
        text = text.replace('(pad 69 smd rect (at 0 0 0) (size 5.59 5.59) (layers F.Cu F.Paste F.Mask))', '(pad 69 smd rect (at 0 0) (size 5.59 5.59) (layers "F.Cu" "F.Mask"))\n' + '\n'.join(paste_windows))
        text = text.replace(' F.Cu F.Paste F.Mask', ' "F.Cu" "F.Paste" "F.Mask"')
        text = text.replace('(layer F.', '(layer "F.')
        text = re.sub(r'\(layer "F\.([A-Za-z]+)\)', r'(layer "F.\1")', text)
        text = text.replace('(model AXP223.stp', '')
        text = re.sub(r'\n\s*\(at \(xyz 0 0 0\)\).*?\n\s*\)', '', text, flags=re.S)
        text = text.replace('\n)', '\n  (descr "X-Powers AXP223, 8 x 8 mm QFN, 0.4 mm pitch; exposed-pad paste is windowed; place thermal vias in the PCB as required.\")\n)')
    else:
        text = re.sub(r'^\(module .*?\(layer F\.Cu\).*?\)\n', f'(footprint "{name}"\n  (version 20240108)\n  (generator pcbnew)\n  (layer "F.Cu")\n', text, count=1, flags=re.S)
        text = re.sub(r'\(layer ([A-Z][A-Za-z]+)\)', r'(layer "\1")', text)
        text = re.sub(r'\(layers ([A-Z]\.[A-Za-z]+) ([A-Z]\.[A-Za-z]+) ([A-Z]\.[A-Za-z]+)\)', r'(layers "\1" "\2" "\3")', text)
        text = text.replace('(layer F.', '(layer "F.')
        text = re.sub(r'\(layer "F\.([A-Za-z]+)\)', r'(layer "F.\1")', text)
        text = re.sub(r'\n\(model .*?\n\s*\)', '', text, flags=re.S)
        text = text.replace('\n)', '\n  (descr "Allwinner A33 TFBGA-282, 14 x 14 mm, 0.8 mm pitch; sparse 17 x 17 ball population derived from A33-MiniDev and audited against the package drawing.\")\n)')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def convert_legacy_symbol(source: Path, destination: Path, footprint: str, manufacturer: str, description: str, axp: bool = False) -> None:
    """Use KiCad's own legacy importer, then apply only audited corrections."""
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run(["kicad-cli", "sym", "upgrade", "--output", temporary, str(source)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        converted = Path(temporary) / ("AXP223.kicad_sym" if axp else "A33.kicad_sym")
        text = converted.read_text(encoding="utf-8")
    text = re.sub(r'(\(property "Footprint" ")[^"]+"', rf'\g<1>{footprint}"', text, count=1)
    text = re.sub(r'(\(property "Description" ")[^"]+"', rf'\g<1>{description}"', text, count=1)
    if axp:
        text = re.sub(r'(\(pin .*?\(name ")EP(".*?\(number ")69(")', lambda match: match.group(1) + "EP/GND" + match.group(2) + "69" + match.group(3), text, count=1, flags=re.S)
        text = re.sub(r'(\(property "Manufacturer_Name" ")[^"]+"', rf'\g<1>{manufacturer}"', text, count=1)
    else:
        # The MiniDev source has the two GPIO ball numbers reversed.
        for pin_name, old, new in (("PG8", "A16", "B16"), ("PG9", "B16", "A16")):
            block = re.compile(rf'(\(pin .*?\(name "{pin_name}".*?\(number "){old}(".*?\n\s*\))', re.S)
            text = block.sub(rf'\g<1>{new}\g<2>', text, count=1)
        # The A33 legacy file has no manufacturer property; add one before the unit data.
        marker = '\t\t(symbol "A33_0_1"'
        text = text.replace(marker, f'\t\t(property "Manufacturer" "{manufacturer}" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))\n{marker}', 1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.repo.resolve()
    a33 = args.source / "A33-MiniDev-r1/A33"
    axp = args.source / "A33-MiniDev-r1/AXP223"
    _, a33_units, a33_pins = parse_legacy(a33 / "eec.lib")
    _, axp_units, axp_pins = parse_legacy(axp / "AXP223.lib")
    for p in axp_pins:
        p["unit"] = 0
    a33_pins = [{**p, "number": p["number"]} for p in a33_pins]
    for p in a33_pins:
        if p["name"] == "PG8": p["number"] = "B16"
        if p["name"] == "PG9": p["number"] = "A16"
    for p in axp_pins:
        if p["number"] == "69": p["name"] = "EP/GND"
    convert_legacy_symbol(a33 / "eec.lib", root / "symbols/SoC_Allwinner.kicad_sym", "Package_SoC:Allwinner_A33_TFBGA282_14x14mm_P0.8mm", "Allwinner", "Allwinner A33 quad-core ARM Cortex-A7 SoC; 282-ball TFBGA.")
    convert_legacy_symbol(axp / "AXP223.lib", root / "symbols/PMIC_XPowers.kicad_sym", "Package_PMIC:XPowers_AXP223_QFN-68-1EP_8x8mm_P0.4mm", "X-Powers", "X-Powers AXP223 power management IC; exposed pad 69 is EP/GND.", True)
    convert_footprint(a33 / "A33.pretty/Allwinner_Technology_Co.,_Ltd.-A33-0.kicad_mod", root / "footprints/Package_SoC.pretty/Allwinner_A33_TFBGA282_14x14mm_P0.8mm.kicad_mod", "Allwinner_A33_TFBGA282_14x14mm_P0.8mm")
    convert_footprint(axp / "QFN40P800X800X80-69N-D.kicad_mod", root / "footprints/Package_PMIC.pretty/XPowers_AXP223_QFN-68-1EP_8x8mm_P0.4mm.kicad_mod", "XPowers_AXP223_QFN-68-1EP_8x8mm_P0.4mm", True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
