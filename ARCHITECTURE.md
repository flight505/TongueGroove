# TongueGroove v3 — Scratchpad

## Coordinate System

All Fusion API values are in **centimetres** and **radians**. User-facing UI is in mm. Conversion: `cm = mm / 10`.

Path positions are fractional: `frac = distance_from_start_cm / total_path_length_cm`, range 0.0 to 1.0.

"Start" and "End" of a path are defined by the **parametric direction** of the sketch curves — the order they were drawn. There is no visual indicator in the UI.

## What Gets Created (in order)

### Step 1: Read inputs + resolve end behaviour

UI parameters and what they control:

    Joint Size:
      Tongue Width      → cross-section width (cm)
      Tongue Height     → protrusion height from face (cm)

    Fit Clearance (always applies, both ends, like a tolerance):
      Side Clearance    → groove half_w = tongue half_w + side_clear (per side)
      Bottom Clearance  → groove height = tongue height + bottom_clear
      End Clearance     → tongue is shorter than groove by this per end

    End Behaviour (per-end, independent):
      Path Start        → Flush (joint to path endpoint) or Inset (pull back)
      Path End          → Flush or Inset
      Inset Distance    → how far both tongue+groove pull back (only when Inset)

Resolution to per-end distances:

    inset_start = inset_cm if start_mode == 'Inset' else 0
    inset_end   = inset_cm if end_mode == 'Inset' else 0

    tongue_start = inset_start + end_clearance    (always applies)
    tongue_end   = inset_end + end_clearance
    groove_start = inset_start                    (no end clearance)
    groove_end   = inset_end

The difference tongue - groove = end_clearance at each end. This is the fit gap.

### Step 2: Build sweep Path

If user selected 1 curve → `sketch.findConnectedCurves(curve)` returns all connected curves in order. `Path.create(collection, noChainedCurves)`.

If user selected 2+ curves → `Path.create(ObjectCollection of selected, noChainedCurves)`. No auto-chaining.

`total_len` must be computed from the same set of curves that `_make_path` uses. Mismatch = wrong fractions.

### Step 3: Get face normal

`sketch.referencePlane` → cast to BRepFace → `evaluator.getNormalAtPoint(centroid)` → Vector3D.

Fallback: ConstructionPlane → `geometry.normal`. Last resort: (0,0,1).

### Step 4: Tongue — full sweep

1. **Construction plane** at frac=0.0 via `setByDistanceOnPath(path, 0.0)`. Plane is perpendicular to path at its start. The plane's normal = path tangent at that point.

2. **Profile sketch** on that plane. Rectangle oriented by comparing plane.geometry.uDirection / vDirection against face_normal via dot product. The axis with larger |dot| with face_normal is the height direction. Sign of dot determines if height goes + or - in that axis.

3. **Sweep** with `JoinFeatureOperation`, `PerpendicularOrientationType`, `participantBodies=[tongue_body]`. The sweep runs the full path (distanceOne defaults to 1.0).

**Result**: tongue body now has a rectangular protrusion running the entire path length.

### Step 5: Tongue — trim ends

For each end with a gap > 0:

1. **Trim plane** at `frac = gap_cm / total_len` (start) or `1.0 - gap_cm / total_len` (end). This plane is perpendicular to the path at the trim position.

2. **Profile** on trim plane: same rectangle but **1.5x oversized** in both width and height. Oversized ensures the cut fully covers the tongue even if the plane orientation is slightly off at curves.

3. **Extrude-cut** from trim plane toward the path endpoint using `DistanceExtentDefinition`. Distance = `gap_cm * 1.5 + 0.1cm`. Direction: `NegativeExtentDirection` toward start, `PositiveExtentDirection` toward end (relative to trim plane normal = path tangent at that point). `participantBodies=[tongue_body]` limits the cut.

**Critical**: The construction plane normal is the path tangent. Positive/Negative directions are along the tangent, NOT along the face normal. The extrude cuts a slab along the path direction, shaving off the tongue end. This works because the tongue cross-section on the trim plane overlaps the tongue body, and the extrude extends along the path to cover the gap region.

**Known failure**: If the path tangent at the trim point is perpendicular to the face (unlikely for typical paths on faces), the extrude goes through the face into the body interior, which could cut more than intended. `participantBodies` limits damage.

**Known failure**: At the path end, if the tongue only extends a fraction of a mm past the trim plane, the PositiveExtentDirection extrude may not find enough body to cut, giving "No target body." The 1.5x oversize profile + 150% distance margin are meant to mitigate this.

### Step 6: Tongue — chamfer (optional)

Collects edges from `sweep_feature.faces`. Filters:
1. Both adjacent faces must belong to the sweep (excludes body boundary edges where tongue meets the original body surface)
2. Edge length >= 30% of longest candidate edge (excludes short cross-section edges at end caps)

`chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, size, tangentChain=False)`. Tangent chain disabled to prevent edge propagation onto body faces.

If chamfer fails (too large), retries at 50% size. If that fails too, skips silently.

### Step 7: Groove — partial sweep

1. **Construction plane** at `frac = groove_start_gap / total_len`. For a Cut operation, this reliably clips the start — the cut doesn't happen before the profile position.

2. **Profile** on that plane: rectangle with `half_w = width/2 + lateral_clearance`, `h = height + depth_clearance`.

3. **Sweep** with `CutFeatureOperation`. `distanceOne` clips the far end:

        forward_available = 1.0 - start_frac
        sweep_range = 1.0 - start_frac - end_frac
        d1 = sweep_range / forward_available

    d1 is a fraction of the path ahead of the profile. 1.0 = sweep to path end. 0.95 = stop at 95% of remaining path.

**Why this is different from tongue**: A Cut only removes material where the sweep reaches. Placing the profile forward naturally creates a start gap — no trim needed. For the tongue (Join), the body fills the gap, making it invisible — hence the explicit trim cuts.

### Step 8: Groove — fillet (optional)

Collects all edges from `groove_feature.faces`. Filters: length >= 30% of longest, face count == 2. Uses `addConstantRadiusEdgeSet` with `isRollingBallCorner=True`.

## Fusion API Surface Area Used

| Object | Method/Property | What we use it for |
|---|---|---|
| `Sketch` | `findConnectedCurves(curve)` | Auto-chain connected sketch curves |
| `Path` | `Path.create(curves, chainOptions)` | Build sweep path. ObjectCollection for multi, single SketchCurve for single |
| `ConstructionPlanes` | `createInput().setByDistanceOnPath(path, frac)` | Perpendicular plane at fractional path position |
| `Sketch` | `sketches.add(constructionPlane)` | Create profile sketch on construction plane |
| `SketchLines` | `addTwoPointRectangle(p1, p2)` | Draw tongue/groove cross-section |
| `SweepFeatures` | `createInput(profile, path, operation)` | Build sweep input |
| `SweepFeatureInput` | `.orientation`, `.participantBodies`, `.distanceOne` | Configure sweep |
| `ExtrudeFeatures` | `createInput(profile, CutFeatureOperation)` | Trim extrude |
| `DistanceExtentDefinition` | `.create(ValueInput)` | Finite distance for trim cut |
| `ExtrudeFeatureInput` | `.setOneSideExtent(extent, direction)` | One-directional extrude |
| `ChamferFeatures` | `createInput2()`, `addEqualDistanceChamferEdgeSet` | Tongue top chamfer |
| `FilletFeatures` | `createInput()`, `addConstantRadiusEdgeSet` | Groove corner fillet |
| `BRepFace` | `.evaluator.getNormalAtPoint()`, `.centroid`, `.boundingBox` | Face normal, validation |
| `SketchCurve` | `.length`, `.parentSketch` | Path length, sketch reference |
| `Feature` | `.healthState`, `.errorOrWarningMessage`, `.faces` | Validation + edge selection |

## SWIG Type Mapping (memorize these)

| API expects | Python type | NOT this |
|---|---|---|
| `list[BRepBody]` | `[body]` | `ObjectCollection` |
| `list[SketchCurve]` | `[c1, c2]` | `ObjectCollection` |
| `CurveEvaluator3D.getParameterExtents()` | returns `(bool, float, float)` | not `.parametricRange()` |
| `OffsetConstraint.childCurves` | returns `list` | not `.item(i)` / `.count` |
| Through-all extrude (one side) | `ThroughAllExtentDefinition.create()` | not `AllExtentDefinition.create()` |
| Through-all extrude (both sides) | `ext_input.setAllExtent(SymmetricExtentDirection)` | not `AllExtentDefinition` |

## Body Orientation Auto-Detection

The add-in determines protrusion direction by comparing the groove body centroid
against the face normal from `sketch.referencePlane`.

    face_origin = centroid of the sketch's reference face
    groove_centroid = bounding box center of the groove body
    direction_to_groove = groove_centroid - face_origin
    dot = dot(direction_to_groove, face_normal)

    if dot >= 0: groove is on face-normal side → profile direction = face normal (default)
    if dot < 0:  groove is opposite → flip face normal

This works when:
- Centreline is drawn on the tongue body's face (face normal points toward groove)
- Both bodies are adjacent to the sketch face
- The centreline connects to both body edges

This FAILS when:
- Centreline is drawn on the groove body's face (face normal points away from tongue)
- The user swaps tongue/groove selection from the body that owns the sketch face
- The bodies are not symmetric relative to the face

Root cause: `face.evaluator.getNormalAtPoint()` returns the outward normal of the face's
**owning body**. If the sketch face belongs to body A, the normal points away from A.
When the user selects body A as "groove" and body B as "tongue," the normal points away
from the groove body — the dot product gives the wrong sign.

**Current workaround**: tooltips tell the user to draw the centreline on the tongue body.

**Future fix**: detect which body owns the sketch face. If the owner is the groove body
(not the tongue body), additionally flip the normal. This requires comparing
`sketch.referencePlane` (cast to BRepFace) against the selected tongue/groove bodies
to determine ownership. Pseudocode:

    face = BRepFace.cast(sketch.referencePlane)
    if face and face.body == groove_body:
        # Centreline is on the groove body → normal points away from groove
        # Flip so it points toward groove (same as standard case)
        face_normal = -face_normal

## Open Issues

1. **Chamfer too large** — if chamfer size >= half the tongue's shortest edge, it fails. The auto-retry at 50% helps. Could also pre-compute max safe chamfer from tongue height and width.

2. **Path direction ambiguity** — "Start" and "End" are defined by sketch curve parameterization. No UI hint. User must trial-and-error.

3. **distanceOne has no effect on Cut sweeps** — verified by diagnostic. Groove uses full sweep + fill-back instead.

4. **Curve trim accuracy** — the trim extrude is a flat slab perpendicular to the path tangent at the trim point. For tight curves, this flat cut doesn't follow the curve precisely. Acceptable for gaps < 3mm.

5. **Body orientation when centreline is not on tongue body** — see "Body Orientation Auto-Detection" section above. Current workaround: tooltips. Future fix documented.
