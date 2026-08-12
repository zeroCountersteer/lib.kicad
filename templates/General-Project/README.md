# General KiCad project template

This is the default project starter for this repository. It is intentionally
blank: it contains no RK3399, SBC, or other product-specific circuitry.

The organization and project settings are based on the `wired` project:

- A4 portrait ISO 5457 page setup.
- A blank root schematic ready for hierarchical subsystem sheets.
- A blank PCB ready for board setup and stackup definition.
- A project configuration with useful BOM fields and DNP/BOM controls.
- A local `lib` symbol/footprint table for this repository's library.

The generic components in `symbols/Project_Generic.kicad_sym` are intended for
quick placement. They expose the fields normally needed for documentation and
BOM work: value, footprint, datasheet, description, manufacturer, MPN, and
assembly/BOM inclusion controls. KiCad's standard libraries remain available
through the normal system configuration.

## Create a project

After installing `lib.KiCAD` through PCM, copy this directory from the
installed package's `templates/General-Project/` directory into your project
folder and rename the three `General-Project.kicad_*` root files together.
The template is also present in the repository checkout.

Alternatively, from the repository root:

```text
python3 scripts/create_project_from_template.py path/to/new-project
```

The script copies the template and renames the root project files. Add
hierarchical sheets beside the renamed root schematic; keep each sheet in the
same directory unless you intentionally create a subdirectory hierarchy.
