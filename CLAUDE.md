# Tongue & Groove — Fusion 360 Add-In

## Project

Single-file Fusion 360 Python add-in (`TongueGroove_v3.py`) that creates parametric tongue-and-groove joints between two solid bodies along a sketch centreline path. Designed for FDM 3D printing with configurable tolerances.

## Stack

- Python (Fusion 360 embedded runtime, currently 3.14)
- Fusion 360 API (`adsk.core`, `adsk.fusion`)
- No external dependencies

## Deployment

The add-in runs from `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/TongueGroove/`. The deploy script copies files there:

```bash
bash deploy.sh
```

The file must be named `TongueGroove.py` in the AddIns directory (no `&` — Fusion's JS command registry fails on special characters in folder names).

## Key Files

- `TongueGroove_v3.py` — the add-in source (deployed as `TongueGroove.py`)
- `deploy.sh` — copies files to Fusion AddIns directory
- `ARCHITECTURE.md` — how the code works, order of operations, known issues, failed approaches
- `PROJECT_SUMMARY.md` — historical development notes from v1

## Critical Fusion API Gotchas

Read ARCHITECTURE.md "API Methods That Don't Work As Expected" before making changes. The three most important:

1. **SWIG requires plain Python `list`** for `participantBodies`, `createOffsetInput` curves, and other `std::vector` params — NOT `ObjectCollection`
2. **`ThroughAllExtentDefinition.create()`** for one-sided through-all extrude — NOT `AllExtentDefinition.create()` (doesn't exist)
3. **`CurveEvaluator3D.getParameterExtents()`** returns `(bool, float, float)` — NOT `.parametricRange()` (doesn't exist on curves)

## Before Writing Code

Use the `fusion360-scripting` skill (installed in `.claude/skills/`) to verify ANY Fusion API method before using it. Grep the Python stubs at:

```
/Users/jesper/Library/Application Support/Autodesk/webdeploy/production/*/Autodesk Fusion.app/Contents/Api/Python/packages/adsk/fusion.py
```

Do not trust training data for Fusion 360 API signatures.

## Current Status

v3 — sweep-based architecture. Core sweep works for all path types. Known issues with end gap trimming (see ARCHITECTURE.md). The chamfer correctly excludes body boundary edges. Fillet filters to longitudinal edges.

## Testing

No automated tests. Test manually in Fusion 360:
1. Straight line on a flat face
2. Arc/spline on a flat face
3. Multi-segment connected path (line + arc + line)
4. End gaps with various "Apply To" modes
5. Chamfer and fillet toggles
6. Cancel → verify clean rollback
