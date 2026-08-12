#!/usr/bin/env python3
"""Validate the PCM v2 structures required by KiCad's official schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def required(obj: dict, fields: list[str], label: str) -> None:
    missing = [field for field in fields if field not in obj]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "pcm/packages.json").read_text())
    repo = json.loads((root / "pcm/repository.json").read_text())
    required(repo, ["name", "packages", "schema_version"], "repository.json")
    if repo["schema_version"] != 2:
        raise ValueError("repository schema_version is not 2")
    required(repo["packages"], ["url", "update_timestamp"], "repository packages resource")
    required(package, ["packages"], "packages.json")
    if len(package["packages"]) != 1:
        raise ValueError("expected exactly one package")
    item = package["packages"][0]
    required(item, ["name", "description", "description_full", "identifier", "type", "author", "license", "resources", "versions"], "package")
    for version in item["versions"]:
        required(version, ["version", "status", "kicad_version", "download_url", "download_sha256", "download_size", "install_size"], "package version")
        if not isinstance(version["download_size"], int) or not isinstance(version["install_size"], int):
            raise ValueError("package sizes must be integers")
    print("PCM v2 required-field validation OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"PCM validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
