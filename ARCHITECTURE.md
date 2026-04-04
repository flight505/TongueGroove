# TongueGroove v3 — Scratchpad

## Units

All Fusion API values: **centimetres** (length), **radians** (angles). UI shows mm.

Path positions: fractional 0.0–1.0 along the path. `frac = distance_cm / total_path_length_cm`.

## Operation Sequence

### 1. Read inputs + resolve gaps

    Fit Clearance (always applies):
      side_clear  → groove_hw = tongue_hw + side_clear
      bottom_clear → groove_h = tongue_h + bottom_clear
      end_clear   → tongue is shorter than groove by this per end

    End Behaviour (per-end, independent):
      Inset (default) → end clearance applied, optional pullback
      Flush           → no clearance, no inset (path goes to body edge)

    Resolution:
      inset_start = inset_cm if start_mode == 'Inset' else 0
      inset_end   = inset_cm if end_mode == 'Inset' else 0
      tongue_start = inset_start + end_clear  (Inset ends only)
      tongue_end   = inset_end + end_clear
      groove_start = inset_start
      groove_end   = inset_end

### 2. Build sweep path

1 curve selected → `sketch.findConnectedCurves(curve)` auto-chains all connected curves.
2+ curves selected → uses exactly those curves, no chaining.
`total_len` computed from the same curve set.

### 3. Get face normal + auto-detect orientation

Face normal from `sketch.referencePlane` → BRepFace normal or ConstructionPlane normal.

Auto-detect: `dot(face_origin → groove_centroid, face_normal)`.
If `dot < 0`: groove is opposite to face normal → flip normal.
If `dot >= 0`: default (no flip).

Limitation: works when centreline is on the tongue body's face. May give wrong results
if centreline is on the groove body's face (see CLAUDE.md for details).

### 4. Tongue sweep (Join, full path)

1. Construction plane at frac=0.0 via `setByDistanceOnPath(path, 0.0)`
2. Rectangle profile oriented by dot(plane.uDirection/vDirection, face_normal)
3. Sweep with `JoinFeatureOperation`, `PerpendicularOrientationType`, `participantBodies=[tongue_body]`
4. Result: tongue protrusion runs entire path length

### 5. Chamfer (BEFORE trim cuts)

Chamfer must run before trims because trim cuts invalidate `sweep_feat.faces`.

Edge selection:
1. Exclude `sweep_feat.startFaces` and `sweep_feat.endFaces` (body-coincident faces)
2. Among remaining sweep faces, pick the one with largest area = tongue top face
3. Select edges of that face where the OTHER adjacent face is also a sweep face
4. These are the longitudinal top edges

Retry logic: if chamfer fails (geometry too small), retry at 50% size. Skip if that fails too.
Tangent chain disabled to prevent edge propagation onto body boundary.

### 6. Tongue trim cuts (end clearance)

For each end with gap > 0:
1. Construction plane at `gap_cm / total_len` (start) or `1.0 - gap_cm / total_len` (end)
2. Rectangle profile 1.5x oversized
3. Extrude-cut with `DistanceExtentDefinition(gap_cm + 0.005)` — 0.05mm margin for curve slivers
4. Direction: Negative toward start, Positive toward end
5. `participantBodies = [tongue_body]`

### 7. Groove sweep (Cut, full path)

Same as tongue sweep but with `CutFeatureOperation` and `participantBodies=[groove_body]`.
Profile uses groove dimensions (tongue + side_clear, tongue_h + bottom_clear).

### 8. Groove fill-back (inset ends)

`distanceOne` does NOT work for Cut sweeps (verified by diagnostic). Groove uses
full sweep then fill-back instead.

For each end with groove gap > 0:
1. Construction plane at gap position on path
2. Rectangle profile at exact groove dimensions (NOT inverted — same direction as sweep)
3. Extrude-Join with exact gap distance, `participantBodies=[groove_body]`
4. Direction: Negative toward start, Positive toward end

### 9. Fillet (groove corners)

Uses `groove_feat.faces` (valid because nothing modifies groove body after sweep+fill).
Filters to edges: length >= 30% of longest, face count == 2.

## SWIG Type Rules

| API expects | Pass this | NOT this |
|---|---|---|
| `list[BRepBody]` | `[body]` | `ObjectCollection` |
| `list[SketchCurve]` | `[c1, c2]` | `ObjectCollection` |

## Verified API Facts

- `distanceOne` has NO effect on Cut sweeps
- `AllExtentDefinition.create()` does not exist — use `ThroughAllExtentDefinition.create()`
- `CurveEvaluator3D.parametricRange()` does not exist — use `getParameterExtents()`
- `setOneSideToExtent(body)` fails when profile is in a void
- `setOneSideToExtent(plane)` fails with oversized profiles
- `app.log('')` crashes — use `app.log(' ')` for blank lines
- Toolclip images: 300x200px PNG
- Icon sizes: 16x16, 32x32, 64x64 PNG in Resources/ folder

## Open Issues

1. **Chamfer fails on small tongues** — when chamfer size exceeds tongue geometry. Graceful skip.
2. **Path direction ambiguity** — "Start"/"End" defined by sketch curve parameterization. No UI hint.
3. **Orientation detection** — works when centreline is on tongue body face. May fail otherwise.
4. **Curve trim accuracy** — flat extrude at trim point. 0.05mm margin catches most slivers.
