"""
Diagnostic: Full tongue & groove test with measurements.

Creates two boxes (tongue body on top, groove body below), draws a
centreline on the shared face, then runs the add-in's core logic
inline to test Flush and Inset modes.

Measures bounding boxes and point containment to verify:
1. Flush/Flush: tongue and groove go full path, no extra geometry
2. Inset start: groove starts inside body, tongue starts further in
3. No tabs or extrusions beyond body boundaries

Run as Script in Fusion 360. Check Text Commands for output.
"""

import traceback
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface


def _vi(cm):
    return adsk.core.ValueInput.createByReal(cm)


def _make_box(root, x0, y0, z0, x1, y1, z1):
    """Create a box from two corners (cm). Returns BRepBody."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(x0, y0, 0),
        adsk.core.Point3D.create(x1, y1, 0))
    ext = root.features.extrudeFeatures
    inp = ext.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    if z1 > z0:
        inp.setDistanceExtent(False, _vi(z1 - z0))
    else:
        inp.setDistanceExtent(False, _vi(z0 - z1))
        # Negative direction
    feat = ext.add(inp)
    return feat.bodies.item(0)


def _bb(body):
    """Return bounding box as string in mm."""
    b = body.boundingBox
    return (f'X=[{b.minPoint.x*10:.1f}, {b.maxPoint.x*10:.1f}] '
            f'Y=[{b.minPoint.y*10:.1f}, {b.maxPoint.y*10:.1f}] '
            f'Z=[{b.minPoint.z*10:.1f}, {b.maxPoint.z*10:.1f}]mm')


def _contain(body, x_mm, y_mm, z_mm):
    """Check point containment. Returns 0=inside, 1=on, 2=outside."""
    pt = adsk.core.Point3D.create(x_mm / 10.0, y_mm / 10.0, z_mm / 10.0)
    return body.pointContainment(pt)


def run(context):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a design first.')
            return
        root = design.rootComponent

        app.log('=== FULL T&G DIAGNOSTIC ===')

        # Two boxes: 50mm x 20mm x 10mm each, stacked at Z=0
        # Tongue body: Z = 0 to 10mm (top)
        # Groove body: Z = -10mm to 0 (bottom)
        sk1 = root.sketches.add(root.xYConstructionPlane)
        sk1.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))
        ext = root.features.extrudeFeatures

        # Tongue body: extrude up (positive Z)
        inp1 = ext.createInput(sk1.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp1.setDistanceExtent(False, _vi(1.0))
        tongue_body = ext.add(inp1).bodies.item(0)

        # Groove body: extrude down (negative Z)
        sk2 = root.sketches.add(root.xYConstructionPlane)
        sk2.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))
        inp2 = ext.createInput(sk2.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp2.setDistanceExtent(False, _vi(-1.0))
        groove_body = ext.add(inp2).bodies.item(0)

        app.log(f'Tongue body: {_bb(tongue_body)}')
        app.log(f'Groove body: {_bb(groove_body)}')

        # Centreline: 50mm along X at Y=10mm on the XY plane (shared face)
        path_sketch = root.sketches.add(root.xYConstructionPlane)
        line = path_sketch.sketchCurves.sketchLines.addByTwoPoints(
            adsk.core.Point3D.create(0, 1.0, 0),
            adsk.core.Point3D.create(5.0, 1.0, 0))
        app.log(f'Centreline: {line.length * 10:.1f}mm along X')

        path = adsk.fusion.Path.create(line, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        face_normal = adsk.core.Vector3D.create(0, 0, 1)  # Z-up

        # Joint dimensions (cm)
        tongue_hw = 0.3     # 6mm width / 2
        tongue_h  = 0.3     # 3mm height
        groove_hw = 0.315   # + 0.15mm side clearance
        groove_h  = 0.315   # + 0.15mm bottom clearance

        # ============================================================
        app.log(' ')
        app.log('=== TEST 1: Flush / Flush (no inset, no clearance) ===')
        # Full tongue sweep
        pl0 = root.constructionPlanes.createInput()
        pl0.setByDistanceOnPath(path, _vi(0.0))
        plane0 = root.constructionPlanes.add(pl0)

        sk_t = root.sketches.add(plane0)
        pg = plane0.geometry
        u_dot = pg.uDirection.z
        v_dot = pg.vDirection.z
        app.log(f'Profile plane: u_dot_z={u_dot:.2f} v_dot_z={v_dot:.2f}')

        if abs(v_dot) >= abs(u_dot):
            sign = 1.0 if v_dot > 0 else -1.0
            sk_t.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-tongue_hw, 0, 0),
                adsk.core.Point3D.create(tongue_hw, sign * tongue_h, 0))
        else:
            sign = 1.0 if u_dot > 0 else -1.0
            sk_t.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -tongue_hw, 0),
                adsk.core.Point3D.create(sign * tongue_h, tongue_hw, 0))

        t_prof = sk_t.profiles.item(0)
        sweeps = root.features.sweepFeatures
        si_t = sweeps.createInput(t_prof, path, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        si_t.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        si_t.participantBodies = [tongue_body]
        sweeps.add(si_t)

        app.log(f'After tongue sweep: {_bb(tongue_body)}')

        # Full groove sweep
        pl0g = root.constructionPlanes.createInput()
        pl0g.setByDistanceOnPath(path, _vi(0.0))
        plane0g = root.constructionPlanes.add(pl0g)

        sk_g = root.sketches.add(plane0g)
        pg_g = plane0g.geometry
        u_dot_g = pg_g.uDirection.z
        v_dot_g = pg_g.vDirection.z

        if abs(v_dot_g) >= abs(u_dot_g):
            sign_g = 1.0 if v_dot_g > 0 else -1.0
            sk_g.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-groove_hw, 0, 0),
                adsk.core.Point3D.create(groove_hw, sign_g * groove_h, 0))
        else:
            sign_g = 1.0 if u_dot_g > 0 else -1.0
            sk_g.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -groove_hw, 0),
                adsk.core.Point3D.create(sign_g * groove_h, groove_hw, 0))

        g_prof = sk_g.profiles.item(0)
        si_g = sweeps.createInput(g_prof, path, adsk.fusion.FeatureOperations.CutFeatureOperation)
        si_g.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        si_g.participantBodies = [groove_body]
        sweeps.add(si_g)

        app.log(f'After groove sweep: {_bb(groove_body)}')

        # Check: tongue should extend full 50mm
        app.log(f'Tongue at X=1mm: {_contain(tongue_body, 1, 10, 1.5)}')   # inside tongue protrusion
        app.log(f'Tongue at X=49mm: {_contain(tongue_body, 49, 10, 1.5)}') # inside tongue protrusion
        app.log(f'Groove at X=1mm Z=-1.5mm: {_contain(groove_body, 1, 10, -1.5)}')  # in groove channel
        app.log(f'Groove at X=49mm Z=-1.5mm: {_contain(groove_body, 49, 10, -1.5)}')

        # Check perpendicular faces: are the body edges still intact?
        # Point just outside the body at X=-0.5mm should be outside
        app.log(f'Tongue at X=-0.5mm (outside): {_contain(tongue_body, -0.5, 10, 5)}')
        app.log(f'Groove at X=-0.5mm (outside): {_contain(groove_body, -0.5, 10, -5)}')
        # Point at X=50.5mm should be outside
        app.log(f'Tongue at X=50.5mm (outside): {_contain(tongue_body, 50.5, 10, 5)}')
        app.log(f'Groove at X=50.5mm (outside): {_contain(groove_body, 50.5, 10, -5)}')

        # ============================================================
        app.log(' ')
        app.log('=== TEST 2: Inset start 5mm, Flush end ===')
        app.log('Testing fill-back at start of groove...')

        # Fill groove at start: plane at frac=0.1 (5mm), Join toward start
        fill_frac = 0.1
        pl_fill = root.constructionPlanes.createInput()
        pl_fill.setByDistanceOnPath(path, _vi(fill_frac))
        fill_plane = root.constructionPlanes.add(pl_fill)
        app.log(f'Fill plane origin: X={fill_plane.geometry.origin.x * 10:.1f}mm')

        sk_fill = root.sketches.add(fill_plane)
        pg_f = fill_plane.geometry
        u_dot_f = pg_f.uDirection.z
        v_dot_f = pg_f.vDirection.z

        # INVERTED height: profile goes INTO the body (opposite of face normal)
        if abs(v_dot_f) >= abs(u_dot_f):
            sign_f = -1.0 if v_dot_f > 0 else 1.0   # inverted
            sk_fill.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-groove_hw, 0, 0),
                adsk.core.Point3D.create(groove_hw, sign_f * groove_h, 0))
        else:
            sign_f = -1.0 if u_dot_f > 0 else 1.0   # inverted
            sk_fill.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -groove_hw, 0),
                adsk.core.Point3D.create(sign_f * groove_h, groove_hw, 0))

        fill_prof = sk_fill.profiles.item(0)
        fill_ext = root.features.extrudeFeatures.createInput(
            fill_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        # Exact distance, Negative direction (toward path start = X=0)
        fill_dist = 0.5  # 5mm in cm
        dist_def = adsk.fusion.DistanceExtentDefinition.create(_vi(fill_dist))
        fill_ext.setOneSideExtent(dist_def, adsk.fusion.ExtentDirections.NegativeExtentDirection)
        fill_ext.participantBodies = [groove_body]

        try:
            fill_feat = root.features.extrudeFeatures.add(fill_ext)
            app.log(f'Fill-to-body: health={fill_feat.healthState}')
        except RuntimeError as e:
            app.log(f'Fill-to-body FAILED: {e}')

        app.log(f'After fill: {_bb(groove_body)}')

        # Check: groove at X=2.5mm should now be filled (inside body)
        app.log(f'Groove at X=2.5mm Z=-1.5mm after fill: {_contain(groove_body, 2.5, 10, -1.5)}')
        # Groove at X=25mm should still be cut (outside or on boundary)
        app.log(f'Groove at X=25mm Z=-1.5mm (still cut): {_contain(groove_body, 25, 10, -1.5)}')
        # Check perpendicular face at X=0 is not damaged
        app.log(f'Groove at X=-0.5mm after fill: {_contain(groove_body, -0.5, 10, -5)}')

        # ============================================================
        app.log(' ')
        app.log('=== TEST 3: Tongue trim at start (inset 5mm + clearance 2mm = 7mm) ===')

        trim_frac = 0.14  # 7mm / 50mm
        pl_trim = root.constructionPlanes.createInput()
        pl_trim.setByDistanceOnPath(path, _vi(trim_frac))
        trim_plane = root.constructionPlanes.add(pl_trim)
        app.log(f'Trim plane origin: X={trim_plane.geometry.origin.x * 10:.1f}mm')

        sk_trim = root.sketches.add(trim_plane)
        pg_tr = trim_plane.geometry
        u_dot_tr = pg_tr.uDirection.z
        v_dot_tr = pg_tr.vDirection.z

        trim_hw = tongue_hw * 1.5
        trim_h = tongue_h * 1.5

        if abs(v_dot_tr) >= abs(u_dot_tr):
            sign_tr = 1.0 if v_dot_tr > 0 else -1.0
            sk_trim.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-trim_hw, 0, 0),
                adsk.core.Point3D.create(trim_hw, sign_tr * trim_h, 0))
        else:
            sign_tr = 1.0 if u_dot_tr > 0 else -1.0
            sk_trim.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -trim_hw, 0),
                adsk.core.Point3D.create(sign_tr * trim_h, trim_hw, 0))

        trim_prof = sk_trim.profiles.item(0)
        trim_ext = root.features.extrudeFeatures.createInput(
            trim_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # Exact distance, Negative direction (toward start = X=0)
        trim_dist = 0.7  # 7mm in cm
        dist_def_t = adsk.fusion.DistanceExtentDefinition.create(_vi(trim_dist))
        trim_ext.setOneSideExtent(dist_def_t, adsk.fusion.ExtentDirections.NegativeExtentDirection)
        trim_ext.participantBodies = [tongue_body]

        try:
            trim_feat = root.features.extrudeFeatures.add(trim_ext)
            app.log(f'Trim-to-plane: health={trim_feat.healthState}')
        except RuntimeError as e:
            app.log(f'Trim-to-plane FAILED: {e}')

        app.log(f'After trim: {_bb(tongue_body)}')

        # Check: tongue at X=3.5mm should be cut away (protrusion gone)
        app.log(f'Tongue protrusion at X=3.5mm Z=1.5mm after trim: {_contain(tongue_body, 3.5, 10, 1.5)}')
        # Tongue at X=10mm should still have protrusion
        app.log(f'Tongue protrusion at X=10mm Z=1.5mm: {_contain(tongue_body, 10, 10, 1.5)}')

        app.log(' ')
        app.log('=== DIAGNOSTIC COMPLETE ===')
        app.log('Legend: containment 0=inside, 1=on boundary, 2=outside')

    except:
        app.log(f'Diagnostic failed:\n{traceback.format_exc()}')
        ui.messageBox(f'Failed:\n{traceback.format_exc()}')
