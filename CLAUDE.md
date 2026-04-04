# Tongue & Groove — Fusion 360 Add-In

## Project

Single-file Fusion 360 Python add-in (`TongueGroove_v3.py`) that creates parametric tongue-and-groove joints between two solid bodies along a sketch centreline path. Designed for FDM 3D printing with configurable fit clearances.

## Stack

- Python (Fusion 360 embedded runtime, currently 3.14)
- Fusion 360 API (`adsk.core`, `adsk.fusion`)
- No external dependencies

## Deployment

```bash
bash deploy.sh
```

Copies to `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/TongueGroove/`.
File must be named `TongueGroove.py` in AddIns (no `&` in folder names).

## Key Files

| File | Purpose |
|------|---------|
| `TongueGroove_v3.py` | Add-in source (deployed as `TongueGroove.py`) |
| `Resources/` | Icons (16/32/64px), toolclip (300x200), help.html |
| `deploy.sh` | Copy files to Fusion AddIns directory |
| `ARCHITECTURE.md` | Operation sequence, verified API facts, open issues |
| `PROJECT_SUMMARY.md` | Historical v1 development notes |

## Before Writing Code

1. Use the `fusion360-scripting` skill (`.claude/skills/`) — check `verified-findings.md` first
2. Grep the Python stubs for exact method signatures before using any Fusion API method
3. Write diagnostic scripts to test uncertain behaviour — don't guess
4. SWIG requires plain Python `list` for `participantBodies` and similar — NOT `ObjectCollection`

## Critical Operation Order

Tongue: sweep → **chamfer** → trim cuts (chamfer before trims — sweep faces go stale after trims)
Groove: sweep → fill-back (distanceOne doesn't work for Cut sweeps)

## Orientation Detection

The centreline should be drawn on the **tongue body** face. The add-in auto-detects
protrusion direction by checking which side of the face the groove body is on.
This fails when the centreline is on the groove body's face.

Future fix documented in ARCHITECTURE.md: check `face.body == groove_body`.

## End Behaviour

- **Inset** (default): end clearance applied. Use when path stops inside the body.
- **Flush**: no clearance. Use only when path exits through a body edge.
- End clearance is a fit tolerance (like side clearance) — always applied at Inset ends.

## Testing

No automated tests. Test manually in Fusion 360:
1. Straight line on a flat face (basic case)
2. Multi-segment curved path (line + arc + line)
3. Path connecting both body edges perpendicular
4. End Behaviour: Flush/Flush, Inset/Inset, mixed
5. Chamfer on straight and curved paths
6. Fillet on groove
7. Cancel → verify clean rollback
