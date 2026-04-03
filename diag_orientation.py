"""
Diagnostic: Test body orientation detection.

Creates two box configurations and checks whether we can determine
the correct protrusion direction from body centroids and face normal.

Config A: tongue below, groove above (standard)
Config B: tongue above, groove below (swapped)
Config C: tongue left, groove right (horizontal)

For each: compute the direction from face to groove body centroid,
check if it aligns with or opposes the face normal.

Run as Script in Fusion 360. Check Text Commands for output.
"""

import traceback
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface


def _vi(cm):
    return adsk.core.ValueInput.createByReal(cm)


def _dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def run(context):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a design first.')
            return
        root = design.rootComponent
        ext = root.features.extrudeFeatures

        app.log('=== ORIENTATION DIAGNOSTIC ===')

        # ---- CONFIG A: tongue below (Z=0..10), groove above (Z=0..-10) ----
        # Shared face at Z=0. Face normal = +Z.
        # Tongue body centroid at Z=5. Groove body centroid at Z=-5.
        app.log(' ')
        app.log('--- CONFIG A: tongue below, groove above ---')

        sk_a = root.sketches.add(root.xYConstructionPlane)
        sk_a.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))

        inp_a1 = ext.createInput(sk_a.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp_a1.setDistanceExtent(False, _vi(1.0))  # Z = 0 to 10mm
        tongue_a = ext.add(inp_a1).bodies.item(0)

        sk_a2 = root.sketches.add(root.xYConstructionPlane)
        sk_a2.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(5.0, 2.0, 0))

        inp_a2 = ext.createInput(sk_a2.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp_a2.setDistanceExtent(False, _vi(-1.0))  # Z = 0 to -10mm
        groove_a = ext.add(inp_a2).bodies.item(0)

        face_normal_a = adsk.core.Vector3D.create(0, 0, 1)

        # Get centroids
        bb_t = tongue_a.boundingBox
        t_centroid = adsk.core.Point3D.create(
            (bb_t.minPoint.x + bb_t.maxPoint.x) / 2,
            (bb_t.minPoint.y + bb_t.maxPoint.y) / 2,
            (bb_t.minPoint.z + bb_t.maxPoint.z) / 2)

        bb_g = groove_a.boundingBox
        g_centroid = adsk.core.Point3D.create(
            (bb_g.minPoint.x + bb_g.maxPoint.x) / 2,
            (bb_g.minPoint.y + bb_g.maxPoint.y) / 2,
            (bb_g.minPoint.z + bb_g.maxPoint.z) / 2)

        # Face origin (shared face at Z=0)
        face_origin = adsk.core.Point3D.create(2.5, 1.0, 0)

        # Direction from face to groove centroid
        to_groove = adsk.core.Vector3D.create(
            g_centroid.x - face_origin.x,
            g_centroid.y - face_origin.y,
            g_centroid.z - face_origin.z)

        dot_groove = _dot(to_groove, face_normal_a)

        app.log(f'Tongue centroid: ({t_centroid.x*10:.0f}, {t_centroid.y*10:.0f}, {t_centroid.z*10:.0f})mm')
        app.log(f'Groove centroid: ({g_centroid.x*10:.0f}, {g_centroid.y*10:.0f}, {g_centroid.z*10:.0f})mm')
        app.log(f'Face normal: ({face_normal_a.x:.0f}, {face_normal_a.y:.0f}, {face_normal_a.z:.0f})')
        app.log(f'Direction face→groove: ({to_groove.x*10:.0f}, {to_groove.y*10:.0f}, {to_groove.z*10:.0f})mm')
        app.log(f'Dot(face→groove, face_normal) = {dot_groove:.2f}')
        app.log(f'Groove is {"SAME" if dot_groove > 0 else "OPPOSITE"} side as face normal')
        app.log(f'→ Tongue should protrude {"WITH" if dot_groove < 0 else "AGAINST"} face normal')

        # ---- CONFIG B: tongue above (Z=0..-10), groove below (Z=0..10) ----
        # Same geometry but swap the body assignments
        app.log(' ')
        app.log('--- CONFIG B: tongue above, groove below (swapped) ---')
        # Just swap the names
        tongue_b = groove_a  # the body at Z=-10..0
        groove_b = tongue_a  # the body at Z=0..10

        bb_tb = tongue_b.boundingBox
        tb_centroid = adsk.core.Point3D.create(
            (bb_tb.minPoint.x + bb_tb.maxPoint.x) / 2,
            (bb_tb.minPoint.y + bb_tb.maxPoint.y) / 2,
            (bb_tb.minPoint.z + bb_tb.maxPoint.z) / 2)

        bb_gb = groove_b.boundingBox
        gb_centroid = adsk.core.Point3D.create(
            (bb_gb.minPoint.x + bb_gb.maxPoint.x) / 2,
            (bb_gb.minPoint.y + bb_gb.maxPoint.y) / 2,
            (bb_gb.minPoint.z + bb_gb.maxPoint.z) / 2)

        to_groove_b = adsk.core.Vector3D.create(
            gb_centroid.x - face_origin.x,
            gb_centroid.y - face_origin.y,
            gb_centroid.z - face_origin.z)

        dot_groove_b = _dot(to_groove_b, face_normal_a)

        app.log(f'Tongue centroid: ({tb_centroid.x*10:.0f}, {tb_centroid.y*10:.0f}, {tb_centroid.z*10:.0f})mm')
        app.log(f'Groove centroid: ({gb_centroid.x*10:.0f}, {gb_centroid.y*10:.0f}, {gb_centroid.z*10:.0f})mm')
        app.log(f'Dot(face→groove, face_normal) = {dot_groove_b:.2f}')
        app.log(f'Groove is {"SAME" if dot_groove_b > 0 else "OPPOSITE"} side as face normal')
        app.log(f'→ Tongue should protrude {"WITH" if dot_groove_b < 0 else "AGAINST"} face normal')

        # ---- DETECTION RULE ----
        app.log(' ')
        app.log('=== DETECTION RULE ===')
        app.log('If dot(face→groove_centroid, face_normal) < 0:')
        app.log('  Groove is OPPOSITE to face normal → protrude WITH face normal (default)')
        app.log('If dot(face→groove_centroid, face_normal) > 0:')
        app.log('  Groove is SAME side as face normal → protrude AGAINST face normal (flip)')
        app.log(' ')
        app.log('Implementation: multiply profile height sign by -1 when dot > 0')

        app.log(' ')
        app.log('=== DIAGNOSTIC COMPLETE ===')

    except:
        app.log(f'Diagnostic failed:\n{traceback.format_exc()}')
        ui.messageBox(f'Failed:\n{traceback.format_exc()}')
