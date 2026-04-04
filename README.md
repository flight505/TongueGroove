# Tongue & Groove — Fusion 360 Add-In

A parametric tongue-and-groove joint generator for Autodesk Fusion 360, designed for 3D printing with configurable fit clearances.

## What It Does

Creates interlocking tongue-and-groove joints between two solid bodies along a sketch centreline path. Works with straight lines, arcs, splines, and multi-segment connected curves.

- **Tongue**: rectangular protrusion joined to one body
- **Groove**: matching channel cut into the other body
- **Fit clearance**: side, bottom, and end tolerances for 3D printing
- **Chamfer**: optional lead-in on tongue top edges
- **Fillet**: optional rounding on groove inside corners

## Installation

1. Download or clone this repository
2. Run the deploy script:
   ```bash
   bash deploy.sh
   ```
3. In Fusion 360: **Shift+S → Add-Ins → TongueGroove → Run**

The add-in appears in **Solid → Modify → Tongue & Groove**.

## Usage

1. Draw a centreline sketch on the **tongue body** face
2. Click **Solid → Modify → Tongue & Groove**
3. Select the centreline path, tongue body, and groove body
4. Adjust dimensions and clearances
5. Click OK

### Parameters

**Joint Size**
- **Tongue Width** — cross-section width (default 6mm)
- **Tongue Height** — protrusion height from face (default 3mm)

**Fit Clearance**
- **Side Clearance** — groove wider than tongue per side (default 0.15mm)
- **Bottom Clearance** — groove deeper than tongue (default 0.15mm)
- **End Clearance** — tongue shorter than groove per end (default 0.2mm)

**End Behaviour** (independent per end)
- **Inset** (default) — end clearance applied. Set distance to pull both tongue and groove back from the path endpoint. Use when path stops inside the body.
- **Flush** — no end clearance, no inset. Use when path exits through a body edge.

**Options**
- **Lead-in Chamfer** — chamfer on tongue top edges for easier assembly
- **Fillet Groove Corners** — fillet on groove inside edges (helps FDM printing)

## Tips

- Draw the centreline on the tongue body face, not the groove body
- Click one curve to auto-select the full connected path
- Use Inset (default) for paths ending inside the body — end clearance ensures the tongue doesn't bottom out
- Use Flush only where the path exits through a body edge (no groove wall)
- For 3D printing: 0.1–0.2mm side clearance, 0.15mm bottom clearance, 0.2mm end clearance

## Requirements

- Autodesk Fusion 360 (macOS or Windows)
- Python 3.14+ (bundled with Fusion)

## License

MIT

## Author

[flight505](https://github.com/flight505)
