"""
Tongue & Groove Add-in for Autodesk Fusion 360
================================================
Creates a parametric tongue-and-groove joint between two solid bodies,
with configurable dimensions and 3D-printing tolerances.

Workflow:
  1. Draw a centreline sketch curve on a planar face of one of your bodies.
  2. Click  Solid → Modify → Tongue & Groove.
  3. Select the path, choose the tongue body and the groove body.
  4. Tune width, height, clearance and chamfer.
  5. Click OK.

The add-in:
  • Creates a sweep Path from the selected centreline curves.
  • Builds a rectangular cross-section profile perpendicular to the path.
  • Sweeps that profile along the path to form the TONGUE (Join) and
    GROOVE (Cut) on the respective bodies.
  • Optionally chamfers the tongue top edges and fillets groove corners.

Author : flight505
Version: 2.0.0
"""

import traceback

import adsk.core
import adsk.fusion

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CMD_ID   = 'TongueGroove_Cmd'
CMD_NAME = 'Tongue & Groove'
CMD_DESC = ('Creates a 3D-print-ready tongue and groove joint between '
            'two bodies along a sketch centreline path.')

_handlers = []


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------
def mm(val: float) -> float:
    """Convert millimetres to centimetres (Fusion API unit)."""
    return val / 10.0


def vi_real(val: float) -> adsk.core.ValueInput:
    """Create a ValueInput from a centimetre value."""
    return adsk.core.ValueInput.createByReal(val)


# ---------------------------------------------------------------------------
# Add-in entry points
# ---------------------------------------------------------------------------
def run(context):
    """Called by Fusion when the add-in starts."""
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        app.log(f'{CMD_NAME}: run() starting...')

        cmdDef = ui.commandDefinitions.itemById(CMD_ID)
        if cmdDef:
            cmdDef.deleteMe()
        app.log(f'{CMD_NAME}: old command definition cleaned up')

        cmdDef = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC, '')
        app.log(f'{CMD_NAME}: command definition created')

        on_created = TGCommandCreatedHandler()
        cmdDef.commandCreated.add(on_created)
        _handlers.append(on_created)
        app.log(f'{CMD_NAME}: CommandCreated handler attached')

        panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        if panel:
            app.log(f'{CMD_NAME}: found SolidModifyPanel')
        else:
            panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                app.log(f'{CMD_NAME}: SolidModifyPanel not found, using SolidScriptsAddinsPanel')

        if panel:
            ctrl = panel.controls.addCommand(cmdDef)
            ctrl.isPromotedByDefault = True
            app.log(f'{CMD_NAME}: button added to panel "{panel.id}"')
        else:
            app.log(f'{CMD_NAME}: WARNING — no target panel found')

        app.log(f'{CMD_NAME}: run() completed successfully ✓')

    except:
        msg = f'{CMD_NAME} run() failed:\n{traceback.format_exc()}'
        try:
            adsk.core.Application.get().log(msg)
        except Exception:
            pass
        if ui:
            ui.messageBox(msg)


def stop(context):
    """Called by Fusion when the add-in is stopped; clean up all UI."""
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        app.log(f'{CMD_NAME}: stop() starting...')

        for panel_id in ('SolidModifyPanel', 'SolidScriptsAddinsPanel'):
            panel = ui.allToolbarPanels.itemById(panel_id)
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()
                    app.log(f'{CMD_NAME}: button removed from "{panel_id}"')

        cmdDef = ui.commandDefinitions.itemById(CMD_ID)
        if cmdDef:
            cmdDef.deleteMe()
            app.log(f'{CMD_NAME}: command definition deleted')

        _handlers.clear()
        app.log(f'{CMD_NAME}: stop() completed ✓')

    except:
        msg = f'{CMD_NAME} stop() failed:\n{traceback.format_exc()}'
        try:
            adsk.core.Application.get().log(msg)
        except Exception:
            pass
        if ui:
            ui.messageBox(msg)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

class TGCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Builds the dialog UI when the user clicks the toolbar button."""

    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            cmd        = event_args.command
            inputs     = cmd.commandInputs

            cmd.isExecutedWhenPreEmpted = False

            # ---- Selection inputs ----
            sel_path = inputs.addSelectionInput(
                'sel_path', 'Centreline Path',
                'Select the sketch curve(s) that define the joint centreline')
            sel_path.addSelectionFilter('SketchCurves')
            sel_path.setSelectionLimits(1, 0)

            sel_tongue = inputs.addSelectionInput(
                'sel_tongue', 'Tongue Body',
                'Select the body that will receive the tongue protrusion')
            sel_tongue.addSelectionFilter('SolidBodies')
            sel_tongue.setSelectionLimits(1, 1)

            sel_groove = inputs.addSelectionInput(
                'sel_groove', 'Groove Body',
                'Select the body that will receive the groove cut')
            sel_groove.addSelectionFilter('SolidBodies')
            sel_groove.setSelectionLimits(1, 1)

            # ---- Dimensions ----
            inputs.addTextBoxCommandInput('sep1', '', '<b>Dimensions</b>', 1, True)

            inputs.addValueInput(
                'val_width', 'Tongue Width', 'mm',
                adsk.core.ValueInput.createByString('6 mm'))

            inputs.addValueInput(
                'val_height', 'Tongue Height', 'mm',
                adsk.core.ValueInput.createByString('3 mm'))

            # ---- Tolerances ----
            inputs.addTextBoxCommandInput('sep2', '', '<b>Tolerances</b>', 1, True)

            inputs.addValueInput(
                'val_clearance', 'Lateral Clearance (per side)', 'mm',
                adsk.core.ValueInput.createByString('0.15 mm'))

            inputs.addValueInput(
                'val_vclear', 'Depth Clearance', 'mm',
                adsk.core.ValueInput.createByString('0.15 mm'))

            inputs.addValueInput(
                'val_end_clear', 'End Clearance (each end)', 'mm',
                adsk.core.ValueInput.createByString('0.2 mm'))

            # ---- Options ----
            inputs.addTextBoxCommandInput('sep3', '', '<b>Options</b>', 1, True)

            inputs.addBoolValueInput('bool_chamfer', 'Add Lead-in Chamfer', True, '', True)

            inputs.addValueInput(
                'val_chamfer', 'Chamfer Size', 'mm',
                adsk.core.ValueInput.createByString('0.5 mm'))

            inputs.addBoolValueInput(
                'bool_groove_fillet', 'Fillet Groove Inside Corners', True, '', False)

            inputs.addValueInput(
                'val_fillet', 'Fillet Radius', 'mm',
                adsk.core.ValueInput.createByString('0.2 mm')).isVisible = False

            inputs.addValueInput(
                'val_end_inset', 'End Inset (each side)', 'mm',
                adsk.core.ValueInput.createByString('0 mm'))

            # ---- Connect sub-handlers ----
            on_input_changed = TGInputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)

            on_execute = TGExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_preview = TGExecutePreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_validate = TGValidateInputsHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

        except:
            app = adsk.core.Application.get()
            app.log(f'TGCommandCreatedHandler failed:\n{traceback.format_exc()}')


class TGInputChangedHandler(adsk.core.InputChangedEventHandler):
    """Show / hide dependent inputs when toggles change."""

    def notify(self, args):
        try:
            event_args = adsk.core.InputChangedEventArgs.cast(args)
            changed    = event_args.input
            inputs     = event_args.inputs

            if changed.id == 'bool_chamfer':
                enabled = adsk.core.BoolValueCommandInput.cast(changed).value
                inputs.itemById('val_chamfer').isVisible = enabled

            elif changed.id == 'bool_groove_fillet':
                enabled = adsk.core.BoolValueCommandInput.cast(changed).value
                fillet_input = inputs.itemById('val_fillet')
                fillet_input.isVisible = enabled
                if enabled:
                    height_cm = adsk.core.ValueCommandInput.cast(
                        inputs.itemById('val_height')).value
                    height_mm  = height_cm * 10.0
                    auto_mm    = max(0.2, min(0.4, height_mm * 0.1))
                    fillet_input.value = auto_mm / 10.0

        except:
            app = adsk.core.Application.get()
            app.log(f'TGInputChangedHandler failed:\n{traceback.format_exc()}')


class TGValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """Enable OK button only when all required inputs are satisfied."""

    def notify(self, args):
        try:
            event_args = adsk.core.ValidateInputsEventArgs.cast(args)
            inputs     = event_args.inputs

            path_sel   = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_path'))
            tongue_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_tongue'))
            groove_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_groove'))

            ok = (path_sel.selectionCount >= 1 and
                  tongue_sel.selectionCount == 1 and
                  groove_sel.selectionCount == 1)

            if ok:
                val_width  = adsk.core.ValueCommandInput.cast(inputs.itemById('val_width'))
                val_height = adsk.core.ValueCommandInput.cast(inputs.itemById('val_height'))
                ok = (val_width.value > 0 and val_height.value > 0)

            if ok:
                # End inset must not consume more than half the path
                val_inset = adsk.core.ValueCommandInput.cast(inputs.itemById('val_end_inset'))
                if val_inset.value < 0:
                    ok = False

            event_args.areInputsValid = ok

        except:
            pass


class TGExecutePreviewHandler(adsk.core.CommandEventHandler):
    """Runs geometry generation in preview mode (rolled back on cancel)."""

    def notify(self, args):
        try:
            event_args = adsk.core.CommandEventArgs.cast(args)
            _generate(event_args.command.commandInputs, preview=True)
            event_args.isValidResult = True
        except:
            app = adsk.core.Application.get()
            app.log(f'TGExecutePreviewHandler failed:\n{traceback.format_exc()}')


class TGExecuteHandler(adsk.core.CommandEventHandler):
    """Runs final geometry generation on OK."""

    def notify(self, args):
        try:
            event_args = adsk.core.CommandEventArgs.cast(args)
            _generate(event_args.command.commandInputs, preview=False)
        except:
            app = adsk.core.Application.get()
            ui  = app.userInterface
            ui.messageBox(f'{CMD_NAME} failed:\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Core geometry generation (sweep-based)
# ---------------------------------------------------------------------------

def _generate(inputs: adsk.core.CommandInputs, preview: bool):
    """Main geometry driver. Sweep-based approach for all path types."""
    app    = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root   = design.rootComponent

    # ---- Read inputs ----
    path_sel   = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_path'))
    tongue_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_tongue'))
    groove_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_groove'))

    tongue_body = adsk.fusion.BRepBody.cast(tongue_sel.selection(0).entity)
    groove_body = adsk.fusion.BRepBody.cast(groove_sel.selection(0).entity)

    width_cm     = adsk.core.ValueCommandInput.cast(inputs.itemById('val_width')).value
    height_cm    = adsk.core.ValueCommandInput.cast(inputs.itemById('val_height')).value
    clear_cm     = adsk.core.ValueCommandInput.cast(inputs.itemById('val_clearance')).value
    vclear_cm    = adsk.core.ValueCommandInput.cast(inputs.itemById('val_vclear')).value
    end_clear_cm = adsk.core.ValueCommandInput.cast(inputs.itemById('val_end_clear')).value
    end_inset_cm = adsk.core.ValueCommandInput.cast(inputs.itemById('val_end_inset')).value

    do_chamfer = adsk.core.BoolValueCommandInput.cast(inputs.itemById('bool_chamfer')).value
    chamfer_cm = adsk.core.ValueCommandInput.cast(inputs.itemById('val_chamfer')).value if do_chamfer else 0.0
    do_fillet  = adsk.core.BoolValueCommandInput.cast(inputs.itemById('bool_groove_fillet')).value

    if do_fillet:
        fillet_input = adsk.core.ValueCommandInput.cast(inputs.itemById('val_fillet'))
        if fillet_input.isVisible and fillet_input.value > 0:
            fillet_cm = fillet_input.value
        else:
            height_mm = height_cm * 10.0
            fillet_cm = max(0.02, min(0.04, height_mm * 0.001))
        fillet_cm = fillet_input.value if fillet_input.isVisible else fillet_cm
    else:
        fillet_cm = 0.0

    # ---- Collect path curves ----
    path_curves = []
    for i in range(path_sel.selectionCount):
        path_curves.append(adsk.fusion.SketchCurve.cast(path_sel.selection(i).entity))
    if not path_curves:
        raise ValueError('No path curves selected.')

    sketch = path_curves[0].parentSketch

    # ---- Compute path length and validate ----
    total_len = sum(c.length for c in path_curves)
    min_required = 2.0 * (end_inset_cm + end_clear_cm) + width_cm * 0.1
    if total_len < min_required:
        raise ValueError(
            f'Path too short ({total_len * 10:.1f} mm) for the requested '
            f'end inset + clearance. Reduce inset or use a longer path.')

    # ---- Create sweep path ----
    sweep_path = _create_sweep_path(path_curves)
    if sweep_path is None:
        raise RuntimeError('Failed to create sweep path from selected curves.')

    # ---- Get face normal for profile orientation ----
    face_normal = _get_face_normal(sketch)

    # ---- Build Tongue ----
    tongue_inset_frac = (end_inset_cm + end_clear_cm) / total_len
    tongue_feat = _sweep_joint(
        root, sweep_path, face_normal,
        half_width=width_cm / 2.0,
        height=height_cm,
        body=tongue_body,
        operation=adsk.fusion.FeatureOperations.JoinFeatureOperation,
        start_frac=tongue_inset_frac,
        end_frac=tongue_inset_frac)

    if chamfer_cm > 0 and tongue_feat:
        _chamfer_sweep_top(root, tongue_feat, chamfer_cm)

    # ---- Build Groove ----
    groove_inset_frac = end_inset_cm / total_len if end_inset_cm > 0 else 0
    groove_feat = _sweep_joint(
        root, sweep_path, face_normal,
        half_width=width_cm / 2.0 + clear_cm,
        height=height_cm + vclear_cm,
        body=groove_body,
        operation=adsk.fusion.FeatureOperations.CutFeatureOperation,
        start_frac=groove_inset_frac,
        end_frac=groove_inset_frac)

    if do_fillet and fillet_cm > 0 and groove_feat:
        _fillet_groove_corners(root, groove_feat, fillet_cm)

    return tongue_feat, groove_feat


# ---------------------------------------------------------------------------
# Sweep infrastructure
# ---------------------------------------------------------------------------

def _create_sweep_path(path_curves):
    """Create a Path object from the selected sketch curves."""
    if len(path_curves) == 1:
        return adsk.fusion.Path.create(
            path_curves[0],
            adsk.fusion.ChainedCurveOptions.connectedChainedCurves)
    else:
        col = adsk.core.ObjectCollection.create()
        for c in path_curves:
            col.add(c)
        return adsk.fusion.Path.create(
            col,
            adsk.fusion.ChainedCurveOptions.noChainedCurves)


def _get_face_normal(sketch):
    """Get the outward face normal of the sketch's reference plane."""
    ref = sketch.referencePlane
    face = adsk.fusion.BRepFace.cast(ref)
    if face:
        # Get normal at the centroid of the face
        _, normal = face.evaluator.getNormalAtPoint(face.centroid)
        return normal
    # Construction plane fallback
    plane = adsk.fusion.ConstructionPlane.cast(ref)
    if plane:
        return plane.geometry.normal
    # Last resort: Z-up
    return adsk.core.Vector3D.create(0, 0, 1)


def _sweep_joint(root, sweep_path, face_normal,
                 half_width, height, body, operation,
                 start_frac=0.0, end_frac=0.0):
    """
    Create a sweep feature (tongue or groove) along the path.

    start_frac / end_frac: fraction of path to skip at each end (0..0.5).

    The profile is placed at start_frac along the path. distanceOne clips
    the far end. The near end is handled by the profile position itself
    (setting the construction plane forward from the path start).
    """
    sweep_range = 1.0 - start_frac - end_frac
    if sweep_range < 0.01:
        raise ValueError('End inset + clearance leaves no room for the joint.')

    # Place profile at the start of the desired range
    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByDistanceOnPath(sweep_path, vi_real(start_frac))
    profile_plane = planes.add(plane_input)
    if profile_plane is None:
        raise RuntimeError('Failed to create profile plane on path.')

    # ---- Draw rectangular cross-section ----
    profile_sketch = root.sketches.add(profile_plane)
    profile = _draw_oriented_rect(
        profile_sketch, profile_plane, face_normal, half_width, height)
    if profile is None:
        raise RuntimeError('Failed to create rectangular profile.')

    # ---- Create sweep ----
    sweeps = root.features.sweepFeatures
    sweep_input = sweeps.createInput(profile, sweep_path, operation)
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep_input.participantBodies = [body]

    # distanceOne is a 0..1 fraction of the path AHEAD of the profile.
    # 1.0 = sweep all the way to path end (default).
    # Profile is at start_frac; path ahead = (1.0 - start_frac).
    # We want to stop at (1.0 - end_frac), so the fraction of the
    # forward path we need is: sweep_range / (1.0 - start_frac).
    if end_frac > 0.001:
        forward_available = 1.0 - start_frac
        d1 = sweep_range / forward_available if forward_available > 0.01 else 1.0
        sweep_input.distanceOne = vi_real(min(d1, 1.0))
    # else: distanceOne defaults to 1.0 (full forward sweep), which is correct

    sweep_feat = sweeps.add(sweep_input)

    # ---- Validate result ----
    if sweep_feat is None:
        raise RuntimeError('Sweep feature creation returned null.')
    if sweep_feat.healthState == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
        msg = sweep_feat.errorOrWarningMessage
        raise RuntimeError(f'Sweep failed: {msg}')

    return sweep_feat


def _draw_oriented_rect(sketch, profile_plane, face_normal, half_width, height):
    """
    Draw a rectangle on the profile sketch, oriented so that:
    - width spans across the face (perpendicular to both path and face normal)
    - height goes outward along the face normal
    """
    plane_geom = profile_plane.geometry
    u_dir = plane_geom.uDirection
    v_dir = plane_geom.vDirection

    # Determine which sketch axis (U or V) aligns with the face normal
    u_dot = u_dir.x * face_normal.x + u_dir.y * face_normal.y + u_dir.z * face_normal.z
    v_dot = v_dir.x * face_normal.x + v_dir.y * face_normal.y + v_dir.z * face_normal.z

    lines = sketch.sketchCurves.sketchLines

    if abs(v_dot) >= abs(u_dot):
        # V axis aligns with face normal → height along Y, width along X
        sign = 1.0 if v_dot > 0 else -1.0
        p1 = adsk.core.Point3D.create(-half_width, 0, 0)
        p2 = adsk.core.Point3D.create(half_width, sign * height, 0)
    else:
        # U axis aligns with face normal → height along X, width along Y
        sign = 1.0 if u_dot > 0 else -1.0
        p1 = adsk.core.Point3D.create(0, -half_width, 0)
        p2 = adsk.core.Point3D.create(sign * height, half_width, 0)

    lines.addTwoPointRectangle(p1, p2)

    if sketch.profiles.count == 0:
        return None
    return sketch.profiles.item(0)


# ---------------------------------------------------------------------------
# Post-processing: chamfer and fillet
# ---------------------------------------------------------------------------

def _chamfer_sweep_top(root, sweep_feature, chamfer_cm):
    """Chamfer the top longitudinal edges of the tongue sweep.

    Strategy: collect ALL edges created by the sweep feature, then filter
    to only edges where BOTH adjacent faces belong to the sweep. This
    excludes edges on the body boundary (where one face is the sweep's
    end face and the other is the original body face).
    Then among those, pick only the long (longitudinal) edges.
    """
    try:
        # Build set of face IDs that belong to the sweep feature
        sweep_face_ids = set()
        for face in sweep_feature.faces:
            sweep_face_ids.add(face.tempId)

        # Collect edges where BOTH adjacent faces are sweep faces
        # (excludes edges on the body boundary)
        candidate_edges = []
        seen = set()
        for face in sweep_feature.faces:
            for edge in face.edges:
                eid = edge.tempId
                if eid in seen:
                    continue
                seen.add(eid)
                # Both adjacent faces must belong to the sweep
                all_sweep = True
                for adj_face in edge.faces:
                    if adj_face.tempId not in sweep_face_ids:
                        all_sweep = False
                        break
                if all_sweep:
                    candidate_edges.append(edge)

        if not candidate_edges:
            return

        # Filter to longitudinal edges only (longer ones)
        max_len = max(e.length for e in candidate_edges)
        threshold = max_len * 0.3

        edges = adsk.core.ObjectCollection.create()
        for edge in candidate_edges:
            if edge.length >= threshold:
                edges.add(edge)

        if edges.count == 0:
            return

        chamfers = root.features.chamferFeatures
        ch_input = chamfers.createInput2()
        ch_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edges, vi_real(chamfer_cm), True)
        chamfers.add(ch_input)
    except:
        app = adsk.core.Application.get()
        app.log(f'Chamfer failed (non-critical):\n{traceback.format_exc()}')


def _fillet_groove_corners(root, groove_feature, fillet_cm):
    """Fillet the inside longitudinal edges of the groove cut.

    For a rectangular-cross-section sweep cut, the groove has 4 longitudinal
    edges running along the path and shorter edges at the end caps. We only
    want the long longitudinal edges (the inside corners of the channel).
    """
    try:
        # Collect all unique edges from the groove feature
        all_edges = []
        seen = set()
        for face in groove_feature.faces:
            for edge in face.edges:
                eid = edge.tempId
                if eid not in seen:
                    seen.add(eid)
                    all_edges.append(edge)

        if not all_edges:
            return

        # Find the longest edge length to distinguish longitudinal from cross-section
        max_len = max(e.length for e in all_edges)

        # Longitudinal edges are roughly path-length long.
        # Cross-section edges are roughly width or height sized.
        # Threshold: edges longer than 30% of the longest edge are longitudinal.
        threshold = max_len * 0.3

        inside_edges = adsk.core.ObjectCollection.create()
        for edge in all_edges:
            if edge.length >= threshold and edge.faces.count == 2:
                inside_edges.add(edge)

        if inside_edges.count == 0:
            return

        fillets = root.features.filletFeatures
        fillet_input = fillets.createInput()
        fillet_input.addConstantRadiusEdgeSet(
            inside_edges, vi_real(fillet_cm), True)
        fillet_input.isRollingBallCorner = True
        fillets.add(fillet_input)
    except:
        app = adsk.core.Application.get()
        app.log(f'Fillet failed (non-critical):\n{traceback.format_exc()}')
