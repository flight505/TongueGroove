"""
Diagnostic v2: Verify groove fill-back with precise distance.

Result from v1: distanceOne=0.9 has NO EFFECT on Cut sweeps.
The groove always cuts the full path regardless of distanceOne.

This test: full groove sweep, then fill-back from a plane at 90% of
the path using extrude-Join with NEGATIVE direction (toward path end)
and a precise distance of 5mm (= the gap we want to fill).

Run as Script in Fusion 360. Check Text Commands for output.
"""

import traceback
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface


def run(context):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a design first.')
            return
        root = design.rootComponent

        app.log('=== GROOVE FILL-BACK DIAGNOSTIC v2 ===')

        # ---- Create groove body: 50x20x10mm ----
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))
        ext = root.features.extrudeFeatures
        inp = ext.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-1.0))
        body = ext.add(inp).bodies.item(0)
        app.log(f'Body: {body.name}')

        bb0 = body.boundingBox
        app.log(f'Before groove: X=[{bb0.minPoint.x*10:.1f}, {bb0.maxPoint.x*10:.1f}]mm')

        # ---- Centreline: 50mm along X, centered at Y=1cm ----
        sk2 = root.sketches.add(root.xYConstructionPlane)
        line = sk2.sketchCurves.sketchLines.addByTwoPoints(
            adsk.core.Point3D.create(0, 1.0, 0),
            adsk.core.Point3D.create(5.0, 1.0, 0))
        path = adsk.fusion.Path.create(line, adsk.fusion.ChainedCurveOptions.noChainedCurves)

        face_normal = adsk.core.Vector3D.create(0, 0, 1)

        # ---- Full groove sweep (cuts X=0 to X=50mm) ----
        plane0 = root.constructionPlanes.createInput()
        plane0.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0.0))
        pl0 = root.constructionPlanes.add(plane0)

        sk3 = root.sketches.add(pl0)
        pg = pl0.geometry
        u, v = pg.uDirection, pg.vDirection
        u_dot = u.x*face_normal.x + u.y*face_normal.y + u.z*face_normal.z
        v_dot = v.x*face_normal.x + v.y*face_normal.y + v.z*face_normal.z

        hw = 0.3   # 3mm half-width
        h  = 0.3   # 3mm height

        if abs(v_dot) >= abs(u_dot):
            sign = 1.0 if v_dot > 0 else -1.0
            p1 = adsk.core.Point3D.create(-hw, 0, 0)
            p2 = adsk.core.Point3D.create(hw, sign * h, 0)
        else:
            sign = 1.0 if u_dot > 0 else -1.0
            p1 = adsk.core.Point3D.create(0, -hw, 0)
            p2 = adsk.core.Point3D.create(sign * h, hw, 0)

        sk3.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
        prof = sk3.profiles.item(0)

        sweeps = root.features.sweepFeatures
        si = sweeps.createInput(prof, path, adsk.fusion.FeatureOperations.CutFeatureOperation)
        si.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        si.participantBodies = [body]
        sweeps.add(si)

        bb1 = body.boundingBox
        app.log(f'After full groove: X=[{bb1.minPoint.x*10:.1f}, {bb1.maxPoint.x*10:.1f}]mm')

        # ---- Fill back the last 5mm (X=45 to X=50) ----
        # Create plane at frac=0.9 (45mm position)
        app.log('--- FILL TEST: plane at 0.9 (45mm), fill toward end ---')

        fill_plane_inp = root.constructionPlanes.createInput()
        fill_plane_inp.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0.9))
        fill_plane = root.constructionPlanes.add(fill_plane_inp)

        app.log(f'Fill plane origin: X={fill_plane.geometry.origin.x*10:.1f}mm')
        app.log(f'Fill plane normal: ({fill_plane.geometry.normal.x:.2f}, '
                f'{fill_plane.geometry.normal.y:.2f}, {fill_plane.geometry.normal.z:.2f})')

        # Draw fill rectangle (same size as groove, slightly oversized)
        sk4 = root.sketches.add(fill_plane)
        pg4 = fill_plane.geometry
        u4, v4 = pg4.uDirection, pg4.vDirection
        u4_dot = u4.x*face_normal.x + u4.y*face_normal.y + u4.z*face_normal.z
        v4_dot = v4.x*face_normal.x + v4.y*face_normal.y + v4.z*face_normal.z

        fill_hw = hw * 1.0  # exact same size as groove
        fill_h = h * 1.0

        if abs(v4_dot) >= abs(u4_dot):
            sign4 = 1.0 if v4_dot > 0 else -1.0
            r1 = adsk.core.Point3D.create(-fill_hw, 0, 0)
            r2 = adsk.core.Point3D.create(fill_hw, sign4 * fill_h, 0)
        else:
            sign4 = 1.0 if u4_dot > 0 else -1.0
            r1 = adsk.core.Point3D.create(0, -fill_hw, 0)
            r2 = adsk.core.Point3D.create(sign4 * fill_h, fill_hw, 0)

        sk4.sketchCurves.sketchLines.addTwoPointRectangle(r1, r2)
        fill_prof = sk4.profiles.item(0)

        # The plane normal is (1,0,0) = +X direction.
        # Positive = toward X=50 (path end).
        # We want to fill FROM 45mm TOWARD 50mm = Positive direction.
        # Distance = 5mm = 0.5 cm.
        fill_dist = 0.5  # 5mm in cm

        ext_inp = root.features.extrudeFeatures.createInput(
            fill_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        dist_def = adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(fill_dist))
        ext_inp.setOneSideExtent(dist_def, adsk.fusion.ExtentDirections.PositiveExtentDirection)
        ext_inp.participantBodies = [body]

        try:
            fill_feat = root.features.extrudeFeatures.add(ext_inp)
            app.log(f'Fill POSITIVE 5mm: health={fill_feat.healthState}')
        except RuntimeError as e:
            app.log(f'Fill POSITIVE 5mm FAILED: {e}')
            app.log('Trying NEGATIVE...')
            sk5 = root.sketches.add(fill_plane)
            if abs(v4_dot) >= abs(u4_dot):
                sk5.sketchCurves.sketchLines.addTwoPointRectangle(r1, r2)
            else:
                sk5.sketchCurves.sketchLines.addTwoPointRectangle(r1, r2)
            fill_prof2 = sk5.profiles.item(0)
            ext_inp2 = root.features.extrudeFeatures.createInput(
                fill_prof2, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            dist_def2 = adsk.fusion.DistanceExtentDefinition.create(
                adsk.core.ValueInput.createByReal(fill_dist))
            ext_inp2.setOneSideExtent(dist_def2, adsk.fusion.ExtentDirections.NegativeExtentDirection)
            ext_inp2.participantBodies = [body]
            try:
                fill_feat2 = root.features.extrudeFeatures.add(ext_inp2)
                app.log(f'Fill NEGATIVE 5mm: health={fill_feat2.healthState}')
            except RuntimeError as e2:
                app.log(f'Fill NEGATIVE 5mm FAILED: {e2}')

        bb2 = body.boundingBox
        app.log(f'After fill: X=[{bb2.minPoint.x*10:.1f}, {bb2.maxPoint.x*10:.1f}]mm')

        # ---- Also test fill at the start (X=0 to X=5mm) ----
        app.log('--- FILL TEST: plane at 0.1 (5mm), fill toward start ---')

        start_plane_inp = root.constructionPlanes.createInput()
        start_plane_inp.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0.1))
        start_plane = root.constructionPlanes.add(start_plane_inp)
        app.log(f'Start fill plane origin: X={start_plane.geometry.origin.x*10:.1f}mm')

        sk6 = root.sketches.add(start_plane)
        pg6 = start_plane.geometry
        u6, v6 = pg6.uDirection, pg6.vDirection
        u6_dot = u6.x*face_normal.x + u6.y*face_normal.y + u6.z*face_normal.z
        v6_dot = v6.x*face_normal.x + v6.y*face_normal.y + v6.z*face_normal.z

        if abs(v6_dot) >= abs(u6_dot):
            sign6 = 1.0 if v6_dot > 0 else -1.0
            s1 = adsk.core.Point3D.create(-fill_hw, 0, 0)
            s2 = adsk.core.Point3D.create(fill_hw, sign6 * fill_h, 0)
        else:
            sign6 = 1.0 if u6_dot > 0 else -1.0
            s1 = adsk.core.Point3D.create(0, -fill_hw, 0)
            s2 = adsk.core.Point3D.create(sign6 * fill_h, fill_hw, 0)

        sk6.sketchCurves.sketchLines.addTwoPointRectangle(s1, s2)
        start_prof = sk6.profiles.item(0)

        # Plane normal is (1,0,0). To fill toward start (X=0), need NEGATIVE.
        ext_inp3 = root.features.extrudeFeatures.createInput(
            start_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        dist_def3 = adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(fill_dist))
        ext_inp3.setOneSideExtent(dist_def3, adsk.fusion.ExtentDirections.NegativeExtentDirection)
        ext_inp3.participantBodies = [body]

        try:
            fill_feat3 = root.features.extrudeFeatures.add(ext_inp3)
            app.log(f'Start fill NEGATIVE 5mm: health={fill_feat3.healthState}')
        except RuntimeError as e:
            app.log(f'Start fill NEGATIVE FAILED: {e}')
            app.log('Trying POSITIVE...')
            sk7 = root.sketches.add(start_plane)
            sk7.sketchCurves.sketchLines.addTwoPointRectangle(s1, s2)
            start_prof2 = sk7.profiles.item(0)
            ext_inp4 = root.features.extrudeFeatures.createInput(
                start_prof2, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            dist_def4 = adsk.fusion.DistanceExtentDefinition.create(
                adsk.core.ValueInput.createByReal(fill_dist))
            ext_inp4.setOneSideExtent(dist_def4, adsk.fusion.ExtentDirections.PositiveExtentDirection)
            ext_inp4.participantBodies = [body]
            try:
                fill_feat4 = root.features.extrudeFeatures.add(ext_inp4)
                app.log(f'Start fill POSITIVE 5mm: health={fill_feat4.healthState}')
            except RuntimeError as e2:
                app.log(f'Start fill POSITIVE FAILED: {e2}')

        bb3 = body.boundingBox
        app.log(f'After both fills: X=[{bb3.minPoint.x*10:.1f}, {bb3.maxPoint.x*10:.1f}]mm')

        # Check if the groove is actually filled by testing a point inside the fill zone
        # Point at X=47.5mm (should be inside body if fill worked), Y=10mm, Z=-5mm
        test_pt_end = adsk.core.Point3D.create(4.75, 1.0, -0.5)
        containment_end = body.pointContainment(test_pt_end)
        app.log(f'Point at X=47.5mm Y=10mm Z=-5mm containment: {containment_end}')
        # 0=inside, 1=on boundary, 2=outside, 3=unknown

        test_pt_start = adsk.core.Point3D.create(0.25, 1.0, -0.5)
        containment_start = body.pointContainment(test_pt_start)
        app.log(f'Point at X=2.5mm Y=10mm Z=-5mm containment: {containment_start}')

        # Point in the middle of the groove (should be outside/on boundary)
        test_pt_mid = adsk.core.Point3D.create(2.5, 1.0, -0.15)
        containment_mid = body.pointContainment(test_pt_mid)
        app.log(f'Point at X=25mm Y=10mm Z=-1.5mm (in groove): {containment_mid}')

        app.log('=== DIAGNOSTIC v2 COMPLETE ===')

    except:
        app.log(f'Diagnostic failed:\n{traceback.format_exc()}')
        ui.messageBox(f'Diagnostic failed:\n{traceback.format_exc()}')
