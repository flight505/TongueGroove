"""
Diagnostic v2: Find the tongue top face by normal direction.

Theory: the tongue's top face is the ONLY face on the tongue body
whose outward normal aligns with the face_normal (protrusion direction).
If we can reliably find this face, its edges are the chamfer targets.

Tests:
1. Sweep a curved tongue on a body
2. Apply trim cuts (simulate end clearance)
3. Search ALL faces on the tongue body for normal ≈ face_normal
4. Report what we find — face count, area, edge count

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

        app.log('=== CHAMFER FACE-NORMAL DIAGNOSTIC v2 ===')

        # ---- Create tongue body: 50x20x10mm ----
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))
        ext = root.features.extrudeFeatures
        inp = ext.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, _vi(1.0))
        tongue_body = ext.add(inp).bodies.item(0)

        face_normal = adsk.core.Vector3D.create(0, 0, 1)

        # ---- Draw multi-segment path: line + arc + line ----
        path_sk = root.sketches.add(root.xYConstructionPlane)
        lines = path_sk.sketchCurves.sketchLines
        arcs = path_sk.sketchCurves.sketchArcs

        l1 = lines.addByTwoPoints(
            adsk.core.Point3D.create(0.5, 1.0, 0),
            adsk.core.Point3D.create(2.0, 1.0, 0))

        a1 = arcs.addByCenterStartSweep(
            adsk.core.Point3D.create(2.5, 1.0, 0),
            adsk.core.Point3D.create(2.0, 1.0, 0),
            math.pi / 2)

        arc_end = a1.endSketchPoint.geometry
        l2 = lines.addByTwoPoints(
            adsk.core.Point3D.create(arc_end.x, arc_end.y, 0),
            adsk.core.Point3D.create(arc_end.x, arc_end.y + 0.5, 0))

        col = adsk.core.ObjectCollection.create()
        col.add(l1)
        col.add(a1)
        col.add(l2)
        path = adsk.fusion.Path.create(col, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        total_len = l1.length + a1.length + l2.length

        app.log(f'Path: {total_len * 10:.1f}mm (3 segments)')

        # ---- Sweep tongue ----
        plane_inp = root.constructionPlanes.createInput()
        plane_inp.setByDistanceOnPath(path, _vi(0.0))
        profile_plane = root.constructionPlanes.add(plane_inp)

        tongue_hw = 0.3
        tongue_h = 0.3

        sk2 = root.sketches.add(profile_plane)
        pg = profile_plane.geometry
        v_dot = pg.vDirection.z
        sign = 1.0 if v_dot > 0 else -1.0
        sk2.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(-tongue_hw, 0, 0),
            adsk.core.Point3D.create(tongue_hw, sign * tongue_h, 0))

        prof = sk2.profiles.item(0)
        sweeps = root.features.sweepFeatures
        si = sweeps.createInput(prof, path, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        si.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        si.participantBodies = [tongue_body]
        sweep_feat = sweeps.add(si)

        app.log(f'Sweep done. Body faces: {tongue_body.faces.count}')

        # ---- Find top faces BEFORE trim ----
        app.log(' ')
        app.log('--- BEFORE TRIM: faces with normal ≈ face_normal ---')
        _find_top_faces(tongue_body, face_normal, 'before trim')

        # ---- Apply trim cuts (simulate 0.2mm end clearance) ----
        for frac, toward_start in [(0.01, True), (0.99, False)]:
            tp_inp = root.constructionPlanes.createInput()
            tp_inp.setByDistanceOnPath(path, _vi(frac))
            tp = root.constructionPlanes.add(tp_inp)

            sk3 = root.sketches.add(tp)
            pg3 = tp.geometry
            v3 = pg3.vDirection.z
            s3 = 1.0 if v3 > 0 else -1.0
            sk3.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(-tongue_hw * 1.5, 0, 0),
                adsk.core.Point3D.create(tongue_hw * 1.5, s3 * tongue_h * 1.5, 0))

            trim_prof = sk3.profiles.item(0)
            trim_inp = ext.createInput(trim_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
            gap_cm = frac * total_len if toward_start else (1.0 - frac) * total_len
            dist_def = adsk.fusion.DistanceExtentDefinition.create(_vi(gap_cm + 0.005))
            direction = (adsk.fusion.ExtentDirections.NegativeExtentDirection if toward_start
                         else adsk.fusion.ExtentDirections.PositiveExtentDirection)
            trim_inp.setOneSideExtent(dist_def, direction)
            trim_inp.participantBodies = [tongue_body]
            ext.add(trim_inp)

        app.log(' ')
        app.log('--- AFTER TRIM: faces with normal ≈ face_normal ---')
        _find_top_faces(tongue_body, face_normal, 'after trim')

        # ---- Try chamfering the top face edges ----
        app.log(' ')
        app.log('--- CHAMFER ATTEMPT ---')
        top_face = _get_top_face(tongue_body, face_normal)
        if top_face:
            edges = adsk.core.ObjectCollection.create()
            for edge in top_face.edges:
                edges.add(edge)
            app.log(f'Chamfering {edges.count} edges from top face')

            ch = root.features.chamferFeatures
            ci = ch.createInput2()
            ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                edges, _vi(0.05), False)  # 0.5mm chamfer
            try:
                ch.add(ci)
                app.log(f'Chamfer succeeded on {edges.count} edges')
            except RuntimeError as e:
                app.log(f'Chamfer failed: {e}')
        else:
            app.log('No top face found')

        app.log(' ')
        app.log('=== DIAGNOSTIC COMPLETE ===')

    except:
        app.log(f'Diagnostic failed:\n{traceback.format_exc()}')
        ui.messageBox(f'Failed:\n{traceback.format_exc()}')


def _find_top_faces(body, face_normal, label):
    """Log all faces whose normal aligns with face_normal (dot > 0.9)."""
    count = 0
    for i in range(body.faces.count):
        f = body.faces.item(i)
        _, n = f.evaluator.getNormalAtPoint(f.centroid)
        dot = n.x * face_normal.x + n.y * face_normal.y + n.z * face_normal.z
        if dot > 0.9:
            c = f.centroid
            app.log(f'  [{label}] Face {i}: area={f.area*100:.1f}mm2  '
                    f'dot={dot:.4f}  edges={f.edges.count}  '
                    f'centroid=({c.x*10:.1f},{c.y*10:.1f},{c.z*10:.1f})mm')
            count += 1
    app.log(f'  Total upward faces (dot>0.9): {count}')


def _get_top_face(body, face_normal):
    """Return the face with the highest dot product with face_normal."""
    best = None
    best_dot = -1
    for i in range(body.faces.count):
        f = body.faces.item(i)
        _, n = f.evaluator.getNormalAtPoint(f.centroid)
        dot = n.x * face_normal.x + n.y * face_normal.y + n.z * face_normal.z
        if dot > best_dot:
            best_dot = dot
            best = f
    return best if best_dot > 0.9 else None
