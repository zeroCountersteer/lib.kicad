#!/usr/bin/env python3
"""Build a KiCad PCM-compatible library ZIP from the repository contents.

The script discovers:
- *.kicad_sym symbol libraries
- *.pretty footprint-library directories
- common 3D-model directories and model files

It keeps the repository editable as-is and creates a clean distributable archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".github",
    "build",
    "dist",
    "output",
    "__pycache__",
}
MODEL_EXTENSIONS = {".step", ".stp", ".wrl", ".obj", ".iges", ".igs"}


def ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def unique_destination(base: Path, name: str) -> Path:
    candidate = base / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while True:
        candidate = base / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def discover_and_copy(repo: Path, package_root: Path) -> dict[str, int]:
    counts = {"symbols": 0, "footprints": 0, "models": 0}

    symbols_root = package_root / "symbols"
    footprints_root = package_root / "footprints"
    models_root = package_root / "3dmodels"

    for symbol in sorted(repo.rglob("*.kicad_sym")):
        if ignored(symbol.relative_to(repo)):
            continue
        target = unique_destination(symbols_root, symbol.name)
        copy_file(symbol, target)
        counts["symbols"] += 1

    pretty_dirs = []
    for directory in sorted(repo.rglob("*.pretty")):
        if not directory.is_dir() or ignored(directory.relative_to(repo)):
            continue
        if any(parent.suffix == ".pretty" for parent in directory.parents):
            continue
        pretty_dirs.append(directory)

    for directory in pretty_dirs:
        target = footprints_root / directory.name
        if target.exists():
            target = unique_destination(footprints_root, directory.name)
        shutil.copytree(directory, target)
        counts["footprints"] += sum(1 for _ in target.rglob("*.kicad_mod"))

    copied_models: set[Path] = set()
    model_dirs = []
    for directory in sorted(repo.rglob("*")):
        if not directory.is_dir() or ignored(directory.relative_to(repo)):
            continue
        lower = directory.name.lower()
        if lower.endswith(".3dshapes") or lower in {"3dmodels", "3d_models", "models"}:
            if any(parent in model_dirs for parent in directory.parents):
                continue
            model_dirs.append(directory)

    for directory in model_dirs:
        target_name = directory.name
        if not target_name.lower().endswith(".3dshapes"):
            target_name = f"{target_name}.3dshapes"
        target = models_root / target_name
        if target.exists():
            target = unique_destination(models_root, target_name)
        shutil.copytree(directory, target)
        for model in directory.rglob("*"):
            if model.is_file() and model.suffix.lower() in MODEL_EXTENSIONS:
                copied_models.add(model.resolve())
                counts["models"] += 1

    loose_root = models_root / "Custom.3dshapes"
    for model in sorted(repo.rglob("*")):
        if not model.is_file() or model.suffix.lower() not in MODEL_EXTENSIONS:
            continue
        if ignored(model.relative_to(repo)) or model.resolve() in copied_models:
            continue
        relative_parent = model.parent.relative_to(repo)
        copy_file(model, loose_root / relative_parent / model.name)
        counts["models"] += 1

    return counts


def load_metadata(template: Path, version: str) -> dict:
    with template.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    metadata["versions"] = [
        {
            "version": version,
            "status": "stable",
            "kicad_version": metadata.pop("kicad_version", "8.0"),
        }
    ]
    return metadata


def write_zip(source_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(source_root.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source_root).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--metadata", default="pcm/metadata.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    metadata_path = (repo / args.metadata).resolve()
    output = Path(args.output).resolve()

    if not metadata_path.is_file():
        print(f"Metadata template not found: {metadata_path}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as temporary:
        package_root = Path(temporary) / "package"
        package_root.mkdir()
        counts = discover_and_copy(repo, package_root)

        if not any(counts.values()):
            print("No KiCad symbols, footprints, or 3D models were found.", file=sys.stderr)
            return 3

        metadata = load_metadata(metadata_path, args.version)
        (package_root / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        write_zip(package_root, output)

    checksum = sha256(output)
    checksum_file = output.with_suffix(output.suffix + ".sha256")
    checksum_file.write_text(f"{checksum}  {output.name}\n", encoding="utf-8")

    print(json.dumps({"output": str(output), "sha256": checksum, **counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
