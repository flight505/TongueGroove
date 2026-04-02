# TongueGroove v3 — Architecture & Known Issues

## What It Does

Creates a tongue-and-groove joint between two Fusion 360 bodies along a sketch centreline path. The tongue protrudes from one body; the groove is cut into the other. Clearances make the parts fit for 3D printing.

## Core Approach: Sweep + Trim

A rectangular cross-section is swept along the centreline path. This works for straight lines, arcs, splines, and multi-segment connected curves with a single code path.

## Order of Operations

1. **Read inputs** — width, height, clearances, gap settings from the command dialog
2. **Find connected curves** — `sketch.findConnectedCurves(firstCurve)` auto-chains all connected segments from whichever single curve the user clicks
3. **Compute total path length** — `sum(curve.length for each connected curve)` in cm
4. **Resolve gap mode** — the "Apply To" dropdown (Both/Start/End/None) maps tongue_gap and groove_gap to per-end distances
5. **Create sweep Path** — `Path.create(curves, ChainedCurveOptions)` builds the Fusion Path object
6. **Get face normal** — from `sketch.referencePlane` (BRepFace or ConstructionPlane), used to orient the profile rectangle

### Tongue (Join)

7. **Full sweep** — profile plane at position 0 on the path, rectangle profile drawn on it, swept the full path length with `JoinFeatureOperation`. The tongue merges with the tongue body.
8. **Trim start** — if start gap > 0: construction plane at `start_gap / total_len` along the path, same rectangle drawn on it, extrude-cut with `ThroughAllExtentDefinition` in the negative direction (toward path start). This physically removes the tongue material at the start.
9. **Trim end** — same, but plane at `1 - end_gap / total_len`, extrude-cut in the positive direction.
10. **Chamfer** — optional, on the tongue's top longitudinal edges only.

### Groove (Cut)

11. **Partial sweep** — profile plane at `start_gap / total_len` on the path. `distanceOne = (1 - start_frac - end_frac) / (1 - start_frac)` clips the far end. Since this is a Cut operation, the cut simply doesn't happen before the profile — so the start gap is visible without any trim step.
12. **Fillet** — optional, on the groove's longitudinal interior edges only.

## Why Tongue and Groove Use Different Gap Mechanisms

A **Join** fills any gap at the start with existing body material, making the gap invisible. Therefore the tongue requires explicit trim cuts at both ends.

A **Cut** only removes material where the sweep reaches. Placing the profile forward from the start naturally skips that region — no trim needed. This is simpler and more reliable.

## Profile Orientation

The profile rectangle must have width across the face and height along the face normal. The construction plane at `setByDistanceOnPath(path, frac)` has U and V axes determined by Fusion. We compute:

    u_dot = dot(plane.uDirection, face_normal)
    v_dot = dot(plane.vDirection, face_normal)

Whichever axis has the larger absolute dot product with the face normal is the height direction. The sign determines whether height goes in the positive or negative axis direction.

## Edge Selection for Chamfer and Fillet

**Chamfer** (tongue): only edges where both adjacent faces belong to the sweep feature (excludes edges on the body boundary where the tongue meets the original body surface). Among those, only edges longer than 30% of the longest edge (excludes short cross-section edges at end caps).

**Fillet** (groove): all edges from the groove feature longer than 30% of the longest edge, with exactly 2 adjacent faces.

## Known Issues (v3)

1. **Tongue start trim may fail on curves** — the extrude-cut is perpendicular to the path at the trim point, not along the path. For tight curves, the cut may miss parts of the tongue or cut too much. Acceptable for small gaps (<3mm).

2. **distanceOne semantics unclear** — the Fusion docs say it's "a value from 0 to 1 indicating the position along the path" but testing shows it behaves as a fraction of the forward-available path from the profile. The formula `sweep_range / (1 - start_frac)` works in most cases but has not been verified at extreme values.

3. **Chamfer face selection heuristic** — uses edge length threshold (30% of max) to distinguish longitudinal from cross-section edges. This can misfire on very short paths where all edges are similar length, or on curves where the chamfer face changes depending on the end-inset amount.

4. **Groove gap end clipping** — `distanceOne` on the groove partial sweep may not clip the far end precisely. The exact semantics of distanceOne (absolute position vs relative fraction) are not definitively resolved.

5. **Path direction dependency** — "Start" and "End" are defined by the parametric direction of the sketch curves (the order they were drawn). There is no UI indication of which end is start vs end. The user discovers this by trial and error.

## Failed Approaches

### v1: Offset + Extrude (original)
Drew offset curves around the centreline in the sketch plane using `GeometricConstraints.addOffset2`, hunted for closed profiles by area heuristics, then extruded. Failed because: separate code paths for straight vs curved, fragile profile detection, manual end cap construction, offset API bugs (FUS-172314, topology matching).

### v2: Sweep with distanceOne gap control
Placed the sweep profile at `start_frac` along the path and used `distanceOne` to clip the end. Failed because: for Join operations, the body fills the gap at the start — the gap exists geometrically but is invisible. Only the end gap (via distanceOne) was visible.

### v3 midpoint approach (abandoned)
Placed the profile at the midpoint of the desired range and used both `distanceOne` (forward) and `distanceTwo` (backward). Failed with `ASM_SWEEP_INVALID_RESULT` on curved paths — the profile orientation at the midpoint caused self-intersection.

### Groove fill via extrude-join (abandoned)
After creating a full groove cut, tried to "fill back" the ends by extruding a Join into the groove body. Failed with `EXTRUDE_BOOLEAN_FAIL` because the profile was outside the body boundary (the body had just been cut away there).

## API Methods That Don't Work As Expected

| What we tried | Why it failed |
|---|---|
| `CurveEvaluator3D.parametricRange()` | Does not exist on CurveEvaluator3D. Correct: `getParameterExtents()` → `(bool, float, float)` |
| `AllExtentDefinition.create()` | No `create()` method. This class is for hole features only. Correct: `ThroughAllExtentDefinition.create()` for one-sided through-all extrude |
| `ObjectCollection` for `participantBodies` | SWIG requires plain Python `list[BRepBody]`, not ObjectCollection |
| `ObjectCollection` for `createOffsetInput(curves, ...)` | SWIG requires plain Python `list[SketchCurve]` |
| `OffsetConstraint.dimension.value` | `dimension` returns `SketchDimension`, not a value. Correct chain: `dimension.parameter.value` |
| `OffsetConstraint.childCurves.item(i)` / `.count` | `childCurves` returns a plain Python `list`, not an API collection |
| `SweepFeatureInput.distanceTwo` on open paths | "Ignored if the path is only on one side of the profile" — when profile is at path start, distanceTwo has no effect |
| `addTwoSidesOffset` with `isTopologyMatched=True` and large dummy offset | Fails with "topology of offset curves does not match" for tight curves |

## API Methods That Were Hallucinated

| Hallucinated | Reality |
|---|---|
| `ev.parametricRange()` on CurveEvaluator3D | Only exists on SurfaceEvaluator. Curve equivalent is `getParameterExtents()` |
| `AllExtentDefinition.create()` | Class exists but has no `create()` — use `ThroughAllExtentDefinition.create()` |
| `OffsetConstraint.childCurves.item(i)` | Property returns `list`, not collection with `.item()` |
