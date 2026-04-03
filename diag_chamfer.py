"""
Diagnostic: Understand tongue edge geometry for chamfer selection.

Creates a test body with a multi-segment path (line + arc + line),
sweeps a tongue, then logs detailed info about every face and edge
on the resulting body. The goal: find a reliable way to identify
the "top" edges of the tongue protrusion for chamfering.

Run as Script in Fusion 360. Check Text Commands for output.
"""

import traceback
import math
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface


def _vi(cm):
    return adsk.core.ValueInput.createByReal(cm)


def run(context):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a design first.')
            return
        root = design.rootComponent

        app.log('=== CHAMFER EDGE DIAGNOSTIC ===')

        # ---- Create tongue body: 50x20x10mm ----
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))
        ext = root.features.extrudeFeatures
        inp = ext.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, _vi(1.0))
        tongue_body = ext.add(inp).bodies.item(0)

        app.log(f'Body created: {tongue_body.faces.count} faces, edges count below')

        # Count edges before sweep
        pre_edges = set()
        for face in tongue_body.faces:
            for edge in face.edges:
                pre_edges.add(edge.tempId)
        app.log(f'Before sweep: {len(pre_edges)} unique edges')

        # ---- Draw multi-segment centreline: line + arc + line ----
        path_sk = root.sketches.add(root.xYConstructionPlane)
        lines = path_sk.sketchCurves.sketchLines
        arcs = path_sk.sketchCurves.sketchArcs

        # Line from (0.5, 1.0) to (2.0, 1.0) — 15mm straight
        l1 = lines.addByTwoPoints(
            adsk.core.Point3D.create(0.5, 1.0, 0),
            adsk.core.Point3D.create(2.0, 1.0, 0))

        # Arc from (2.0, 1.0) to (3.0, 1.5) with center at (2.0, 1.5) — quarter circle r=0.5cm
        a1 = arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(2.5, 1.0, 0),
            adsk.core.Point3D.create(2.0, 1.0, 0),
            math.pi / 2)

        # Line from arc end upward
        arc_end = a1.endSketchPoint.geometry
        l2 = lines.addByTwoPoints(
            adsk.core.Point3D.create(arc_end.x, arc_end.y, 0),
            adsk.core.Point3D.create(arc_end.x, arc_end.y + 0.5, 0))

        app.log(f'Path: line({l1.length*10:.1f}mm) + arc({a1.length*10:.1f}mm) + line({l2.length*10:.1f}mm)')

        # Create path
        col = adsk.core.ObjectCollection.create()
        col.add(l1)
        col.add(a1)
        col.add(l2)
        path = adsk.fusion.Path.create(col, adsk.fusion.ChainedCurveOptions.noChainedCurves)

        face_normal = adsk.core.Vector3D.create(0, 0, 1)

        # ---- Sweep tongue ----
        plane_inp = root.constructionPlanes.createInput()
        plane_inp.setByDistanceOnPath(path, _vi(0.0))
        profile_plane = root.constructionPlanes.add(plane_inp)

        tongue_hw = 0.3   # 6mm width / 2
        tongue_h = 0.3     # 3mm height

        sk2 = root.sketches.add(profile_plane)
        pg = profile_plane.geometry
        u_dot = pg.uDirection.z
        v_dot = pg.vDirection.z

        if abs(v_dot) >= abs(u_dot):
            sign = 1.0 if v_dot > 0 else -1.0
            sk2.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-tongue_hw, 0, 0),
                adsk.core.Point3D.create(tongue_hw, sign * tongue_h, 0))
        else:
            sign = 1.0 if u_dot > 0 else -1.0
            sk2.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -tongue_hw, 0),
                adsk.core.Point3D.create(sign * tongue_h, tongue_hw, 0))

        prof = sk2.profiles.item(0)
        sweeps = root.features.sweepFeatures
        si = sweeps.createInput(prof, path, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        si.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        si.participantBodies = [tongue_body]
        sweep_feat = sweeps.add(si)

        app.log(f'Sweep health: {sweep_feat.healthState}')

        # ---- Analyze sweep feature faces ----
        app.log(' ')
        app.log('=== SWEEP FEATURE FACES ===')
        app.log(f'sweep_feat.faces.count = {sweep_feat.faces.count}')

        for i in range(sweep_feat.faces.count):
            f = sweep_feat.faces.item(i)
            _, n = f.evaluator.getNormalAtPoint(f.centroid)
            c = f.centroid
            app.log(f'  Face {i}: area={f.area*100:.2f}mm2  '
                    f'normal=({n.x:.2f},{n.y:.2f},{n.z:.2f})  '
                    f'centroid=({c.x*10:.1f},{c.y*10:.1f},{c.z*10:.1f})mm  '
                    f'edges={f.edges.count}')

        if sweep_feat.startFaces:
            app.log(f'startFaces: {sweep_feat.startFaces.count}')
        if sweep_feat.endFaces:
            app.log(f'endFaces: {sweep_feat.endFaces.count}')
        if sweep_feat.sideFaces:
            app.log(f'sideFaces: {sweep_feat.sideFaces.count}')

        # ---- Analyze ALL edges on sweep feature ----
        app.log(' ')
        app.log('=== SWEEP FEATURE EDGES ===')

        sweep_fids = {f.tempId for f in sweep_feat.faces}
        all_sweep_edges = []
        seen = set()
        for face in sweep_feat.faces:
            for edge in face.edges:
                eid = edge.tempId
                if eid not in seen:
                    seen.add(eid)
                    both_sweep = all(af.tempId in sweep_fids for af in edge.faces)
                    mp = edge.pointOnEdge
                    adj_normals = []
                    for af in edge.faces:
                        _, an = af.evaluator.getNormalAtPoint(af.centroid)
                        adj_normals.append(f'({an.x:.2f},{an.y:.2f},{an.z:.2f})')

                    app.log(f'  Edge {eid}: len={edge.length*10:.2f}mm  '
                            f'both_sweep={both_sweep}  '
                            f'midpt=({mp.x*10:.1f},{mp.y*10:.1f},{mp.z*10:.1f})mm  '
                            f'adj_faces={edge.faces.count}  '
                            f'normals={" & ".join(adj_normals)}')
                    all_sweep_edges.append((edge, both_sweep))

        # ---- Identify the "top" face ----
        app.log(' ')
        app.log('=== TOP FACE ANALYSIS ===')
        app.log('Looking for the face with normal closest to (0,0,1)...')

        best_face = None
        best_dot = -999
        for face in sweep_feat.faces:
            _, n = face.evaluator.getNormalAtPoint(face.centroid)
            dot = n.x * face_normal.x + n.y * face_normal.y + n.z * face_normal.z
            if dot > best_dot:
                best_dot = dot
                best_face = face

        if best_face:
            _, bn = best_face.evaluator.getNormalAtPoint(best_face.centroid)
            app.log(f'Top face: area={best_face.area*100:.2f}mm2  '
                    f'normal=({bn.x:.2f},{bn.y:.2f},{bn.z:.2f})  '
                    f'dot={best_dot:.4f}  edges={best_face.edges.count}')
            app.log(f'Top face edges:')
            for edge in best_face.edges:
                mp = edge.pointOnEdge
                app.log(f'  len={edge.length*10:.2f}mm  '
                        f'midpt=({mp.x*10:.1f},{mp.y*10:.1f},{mp.z*10:.1f})mm')

        # ---- Check if sweep faces survive after a trim cut ----
        app.log(' ')
        app.log('=== AFTER TRIM CUT ===')

        # Trim at start: plane at frac=0.01
        trim_inp = root.constructionPlanes.createInput()
        trim_inp.setByDistanceOnPath(path, _vi(0.01))
        trim_plane = root.constructionPlanes.add(trim_inp)

        sk3 = root.sketches.add(trim_plane)
        pg3 = trim_plane.geometry
        u3_dot = pg3.uDirection.z
        v3_dot = pg3.vDirection.z
        thw = tongue_hw * 1.5
        th = tongue_h * 1.5

        if abs(v3_dot) >= abs(u3_dot):
            s3 = 1.0 if v3_dot > 0 else -1.0
            sk3.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-thw, 0, 0),
                adsk.core.Point3D.create(thw, s3 * th, 0))
        else:
            s3 = 1.0 if u3_dot > 0 else -1.0
            sk3.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, -thw, 0),
                adsk.core.Point3D.create(s3 * th, thw, 0))

        trim_prof = sk3.profiles.item(0)
        trim_ext = ext.createInput(trim_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
        dist_def = adsk.fusion.DistanceExtentDefinition.create(_vi(0.1))
        trim_ext.setOneSideExtent(dist_def, adsk.fusion.ExtentDirections.NegativeExtentDirection)
        trim_ext.participantBodies = [tongue_body]
        ext.add(trim_ext)

        app.log('Trim cut applied. Checking sweep faces...')
        try:
            app.log(f'sweep_feat.faces.count after trim = {sweep_feat.faces.count}')
            still_valid = 0
            for i in range(sweep_feat.faces.count):
                f = sweep_feat.faces.item(i)
                if f.isValid:
                    still_valid += 1
            app.log(f'Valid sweep faces after trim: {still_valid}/{sweep_feat.faces.count}')
        except Exception as e:
            app.log(f'Cannot access sweep faces after trim: {e}')

        # Check if we can still find the top face on the BODY
        app.log(' ')
        app.log('=== BODY FACES AFTER TRIM (face normal analysis) ===')
        for i in range(tongue_body.faces.count):
            f = tongue_body.faces.item(i)
            _, n = f.evaluator.getNormalAtPoint(f.centroid)
            dot = n.x * face_normal.x + n.y * face_normal.y + n.z * face_normal.z
            if dot > 0.8:  # Faces roughly pointing up (toward groove)
                c = f.centroid
                app.log(f'  Upward face: area={f.area*100:.2f}mm2  '
                        f'normal=({n.x:.2f},{n.y:.2f},{n.z:.2f})  dot={dot:.3f}  '
                        f'centroid=({c.x*10:.1f},{c.y*10:.1f},{c.z*10:.1f})mm  '
                        f'edges={f.edges.count}')

        app.log(' ')
        app.log('=== DIAGNOSTIC COMPLETE ===')

    except:
        app.log(f'Diagnostic failed:\n{traceback.format_exc()}')
        ui.messageBox(f'Failed:\n{traceback.format_exc()}')
