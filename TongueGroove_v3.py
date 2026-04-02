"""
Tongue & Groove Add-in for Autodesk Fusion 360
================================================
Sweep-based architecture with explicit end-gap trimming.

The add-in sweeps a rectangular cross-section along a centreline path to
create the tongue (Join) and groove (Cut), then trims the ends with small
extrude-cuts to produce precise gaps at either or both path endpoints.

Author : flight505
Version: 3.0.0
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
# Helpers
# ---------------------------------------------------------------------------
def _vi(cm: float) -> adsk.core.ValueInput:
    """ValueInput from centimetres."""
    return adsk.core.ValueInput.createByReal(cm)


def _log(msg: str):
    adsk.core.Application.get().log(f'{CMD_NAME}: {msg}')


# ---------------------------------------------------------------------------
# Add-in lifecycle
# ---------------------------------------------------------------------------
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        _log('run() starting...')

        old = ui.commandDefinitions.itemById(CMD_ID)
        if old:
            old.deleteMe()

        cmdDef = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESC, '')
        handler = _OnCommandCreated()
        cmdDef.commandCreated.add(handler)
        _handlers.append(handler)

        panel = (ui.allToolbarPanels.itemById('SolidModifyPanel') or
                 ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel'))
        if panel:
            ctrl = panel.controls.addCommand(cmdDef)
            ctrl.isPromotedByDefault = True
            _log(f'button added to "{panel.id}"')

        _log('run() completed ✓')
    except:
        msg = f'{CMD_NAME} run() failed:\n{traceback.format_exc()}'
        try: adsk.core.Application.get().log(msg)
        except: pass
        if ui: ui.messageBox(msg)


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        _log('stop() starting...')

        for pid in ('SolidModifyPanel', 'SolidScriptsAddinsPanel'):
            panel = ui.allToolbarPanels.itemById(pid)
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()
                    _log(f'button removed from "{pid}"')

        cmdDef = ui.commandDefinitions.itemById(CMD_ID)
        if cmdDef:
            cmdDef.deleteMe()

        _handlers.clear()
        _log('stop() completed ✓')
    except:
        msg = f'{CMD_NAME} stop() failed:\n{traceback.format_exc()}'
        try: adsk.core.Application.get().log(msg)
        except: pass
        if ui: ui.messageBox(msg)


# ---------------------------------------------------------------------------
# Command UI
# ---------------------------------------------------------------------------
class _OnCommandCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = adsk.core.CommandCreatedEventArgs.cast(args).command
            inp = cmd.commandInputs
            cmd.isExecutedWhenPreEmpted = False

            # Selections
            sp = inp.addSelectionInput('sel_path', 'Centreline Path',
                                       'Select sketch curve(s) for the joint centreline')
            sp.addSelectionFilter('SketchCurves')
            sp.setSelectionLimits(1, 0)

            st = inp.addSelectionInput('sel_tongue', 'Tongue Body',
                                       'Body that receives the tongue protrusion')
            st.addSelectionFilter('SolidBodies')
            st.setSelectionLimits(1, 1)

            sg = inp.addSelectionInput('sel_groove', 'Groove Body',
                                       'Body that receives the groove cut')
            sg.addSelectionFilter('SolidBodies')
            sg.setSelectionLimits(1, 1)

            # Dimensions
            inp.addTextBoxCommandInput('_d', '', '<b>Dimensions</b>', 1, True)
            inp.addValueInput('val_width',  'Tongue Width',  'mm', adsk.core.ValueInput.createByString('6 mm'))
            inp.addValueInput('val_height', 'Tongue Height', 'mm', adsk.core.ValueInput.createByString('3 mm'))

            # Tolerances
            inp.addTextBoxCommandInput('_t', '', '<b>Tolerances</b>', 1, True)
            inp.addValueInput('val_lat_clear',   'Lateral Clearance (per side)', 'mm', adsk.core.ValueInput.createByString('0.15 mm'))
            inp.addValueInput('val_depth_clear',  'Depth Clearance',             'mm', adsk.core.ValueInput.createByString('0.15 mm'))

            # End gaps
            inp.addTextBoxCommandInput('_g', '', '<b>End Gaps</b>', 1, True)
            dd = inp.addDropDownCommandInput('dd_gap_mode', 'Apply To',
                                             adsk.core.DropDownStyles.TextListDropDownStyle)
            dd.listItems.add('Both ends', True)
            dd.listItems.add('Start only', False)
            dd.listItems.add('End only', False)
            dd.listItems.add('None', False)
            inp.addValueInput('val_tongue_gap', 'Tongue Gap (per end)', 'mm', adsk.core.ValueInput.createByString('0.2 mm'))
            inp.addValueInput('val_groove_gap', 'Groove Gap (per end)', 'mm', adsk.core.ValueInput.createByString('0 mm'))

            # Options
            inp.addTextBoxCommandInput('_o', '', '<b>Options</b>', 1, True)
            inp.addBoolValueInput('bool_chamfer', 'Add Lead-in Chamfer', True, '', True)
            inp.addValueInput('val_chamfer', 'Chamfer Size', 'mm', adsk.core.ValueInput.createByString('0.5 mm'))
            inp.addBoolValueInput('bool_fillet', 'Fillet Groove Corners', True, '', False)
            inp.addValueInput('val_fillet', 'Fillet Radius', 'mm', adsk.core.ValueInput.createByString('0.2 mm')).isVisible = False

            # Sub-handlers
            for cls, event in [(_OnInputChanged,    cmd.inputChanged),
                               (_OnExecute,         cmd.execute),
                               (_OnPreview,         cmd.executePreview),
                               (_OnValidate,        cmd.validateInputs)]:
                h = cls()
                event.add(h)
                _handlers.append(h)
        except:
            _log(f'CommandCreated failed:\n{traceback.format_exc()}')


class _OnInputChanged(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            ea = adsk.core.InputChangedEventArgs.cast(args)
            changed, inputs = ea.input, ea.inputs
            if changed.id == 'bool_chamfer':
                inputs.itemById('val_chamfer').isVisible = adsk.core.BoolValueCommandInput.cast(changed).value
            elif changed.id == 'bool_fillet':
                enabled = adsk.core.BoolValueCommandInput.cast(changed).value
                fi = inputs.itemById('val_fillet')
                fi.isVisible = enabled
                if enabled:
                    h_mm = adsk.core.ValueCommandInput.cast(inputs.itemById('val_height')).value * 10.0
                    fi.value = max(0.02, min(0.04, h_mm * 0.001))
        except:
            _log(f'InputChanged failed:\n{traceback.format_exc()}')


class _OnValidate(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            ea = adsk.core.ValidateInputsEventArgs.cast(args)
            inp = ea.inputs
            ok = (adsk.core.SelectionCommandInput.cast(inp.itemById('sel_path')).selectionCount >= 1 and
                  adsk.core.SelectionCommandInput.cast(inp.itemById('sel_tongue')).selectionCount == 1 and
                  adsk.core.SelectionCommandInput.cast(inp.itemById('sel_groove')).selectionCount == 1 and
                  adsk.core.ValueCommandInput.cast(inp.itemById('val_width')).value > 0 and
                  adsk.core.ValueCommandInput.cast(inp.itemById('val_height')).value > 0 and
                  adsk.core.ValueCommandInput.cast(inp.itemById('val_tongue_gap')).value >= 0 and
                  adsk.core.ValueCommandInput.cast(inp.itemById('val_groove_gap')).value >= 0)
            ea.areInputsValid = ok
        except:
            pass


class _OnPreview(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            ea = adsk.core.CommandEventArgs.cast(args)
            _generate(ea.command.commandInputs)
            ea.isValidResult = True
        except:
            _log(f'Preview failed:\n{traceback.format_exc()}')


class _OnExecute(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            _generate(adsk.core.CommandEventArgs.cast(args).command.commandInputs)
        except:
            adsk.core.Application.get().userInterface.messageBox(
                f'{CMD_NAME} failed:\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------
def _read_val(inputs, id_):
    return adsk.core.ValueCommandInput.cast(inputs.itemById(id_)).value


def _generate(inputs):
    """Main driver: sweep + trim."""
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    root   = design.rootComponent

    # Read selections
    path_sel   = adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_path'))
    tongue_body = adsk.fusion.BRepBody.cast(
        adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_tongue')).selection(0).entity)
    groove_body = adsk.fusion.BRepBody.cast(
        adsk.core.SelectionCommandInput.cast(inputs.itemById('sel_groove')).selection(0).entity)

    # Read values
    width_cm      = _read_val(inputs, 'val_width')
    height_cm     = _read_val(inputs, 'val_height')
    lat_clear_cm  = _read_val(inputs, 'val_lat_clear')
    depth_clear_cm = _read_val(inputs, 'val_depth_clear')
    tongue_gap_cm = _read_val(inputs, 'val_tongue_gap')
    groove_gap_cm = _read_val(inputs, 'val_groove_gap')

    gap_mode = adsk.core.DropDownCommandInput.cast(
        inputs.itemById('dd_gap_mode')).selectedItem.name

    do_chamfer = adsk.core.BoolValueCommandInput.cast(inputs.itemById('bool_chamfer')).value
    chamfer_cm = _read_val(inputs, 'val_chamfer') if do_chamfer else 0.0
    do_fillet  = adsk.core.BoolValueCommandInput.cast(inputs.itemById('bool_fillet')).value
    fillet_cm  = _read_val(inputs, 'val_fillet') if do_fillet else 0.0

    # Collect curves
    curves = [adsk.fusion.SketchCurve.cast(path_sel.selection(i).entity)
              for i in range(path_sel.selectionCount)]
    if not curves:
        raise ValueError('No path curves selected.')

    sketch = curves[0].parentSketch

    # Get all connected curves for accurate total length
    all_connected = sketch.findConnectedCurves(curves[0])
    total_len = sum(all_connected.item(i).length for i in range(all_connected.count))

    # Resolve gap mode → per-end gap distances (cm)
    def _gap(gap_cm):
        """Return (start_gap_cm, end_gap_cm) based on mode."""
        if gap_mode == 'Both ends':    return gap_cm, gap_cm
        elif gap_mode == 'Start only': return gap_cm, 0.0
        elif gap_mode == 'End only':   return 0.0, gap_cm
        else:                          return 0.0, 0.0

    tongue_total = tongue_gap_cm + groove_gap_cm
    t_start, t_end = _gap(tongue_total)
    g_start, g_end = _gap(groove_gap_cm)

    if t_start + t_end >= total_len * 0.95:
        raise ValueError('Tongue gaps exceed path length.')

    # Build path + face normal
    sweep_path  = _make_path(curves)
    face_normal = _face_normal(sketch)

    # ---- TONGUE ----
    tongue_feat = _full_sweep(
        root, sweep_path, face_normal,
        half_w=width_cm / 2.0, h=height_cm,
        body=tongue_body,
        op=adsk.fusion.FeatureOperations.JoinFeatureOperation)

    _trim_ends(root, sweep_path, face_normal,
               half_w=width_cm / 2.0, h=height_cm,
               body=tongue_body,
               start_gap_cm=t_start, end_gap_cm=t_end,
               total_len=total_len)

    if chamfer_cm > 0 and tongue_feat:
        _chamfer_top(root, tongue_feat, chamfer_cm)

    # ---- GROOVE ----
    # For groove (Cut), profile placement works for the start gap because
    # the cut simply doesn't happen before the profile. No fill needed.
    g_start_frac = g_start / total_len if g_start > 0 else 0.0
    g_end_frac   = g_end / total_len if g_end > 0 else 0.0
    groove_feat = _partial_sweep(
        root, sweep_path, face_normal,
        half_w=width_cm / 2.0 + lat_clear_cm,
        h=height_cm + depth_clear_cm,
        body=groove_body,
        op=adsk.fusion.FeatureOperations.CutFeatureOperation,
        start_frac=g_start_frac,
        end_frac=g_end_frac)

    if fillet_cm > 0 and groove_feat:
        _fillet_corners(root, groove_feat, fillet_cm)


# ---------------------------------------------------------------------------
# Path + geometry
# ---------------------------------------------------------------------------
def _make_path(curves):
    """Create sweep Path from selected SketchCurves.

    Always uses findConnectedCurves from the first selected curve to get
    the full connected path, regardless of how many curves the user clicked.
    This matches Fusion's native sweep behavior.
    """
    sketch = curves[0].parentSketch
    connected = sketch.findConnectedCurves(curves[0])

    # findConnectedCurves returns an ObjectCollection in connected order
    if connected.count == 1:
        return adsk.fusion.Path.create(
            connected.item(0),
            adsk.fusion.ChainedCurveOptions.connectedChainedCurves)
    return adsk.fusion.Path.create(
        connected,
        adsk.fusion.ChainedCurveOptions.noChainedCurves)


def _face_normal(sketch):
    """Outward normal of the sketch's reference plane."""
    ref = sketch.referencePlane
    face = adsk.fusion.BRepFace.cast(ref)
    if face:
        _, n = face.evaluator.getNormalAtPoint(face.centroid)
        return n
    plane = adsk.fusion.ConstructionPlane.cast(ref)
    if plane:
        return plane.geometry.normal
    return adsk.core.Vector3D.create(0, 0, 1)


def _make_profile_plane(root, path, frac):
    """Construction plane perpendicular to path at fractional position."""
    inp = root.constructionPlanes.createInput()
    inp.setByDistanceOnPath(path, _vi(frac))
    return root.constructionPlanes.add(inp)


def _draw_rect(root, plane, face_normal, half_w, h):
    """Draw oriented rectangle on a construction plane. Returns (sketch, profile)."""
    sk = root.sketches.add(plane)
    pg = plane.geometry
    u, v = pg.uDirection, pg.vDirection

    u_dot = u.x*face_normal.x + u.y*face_normal.y + u.z*face_normal.z
    v_dot = v.x*face_normal.x + v.y*face_normal.y + v.z*face_normal.z

    if abs(v_dot) >= abs(u_dot):
        sign = 1.0 if v_dot > 0 else -1.0
        p1 = adsk.core.Point3D.create(-half_w, 0, 0)
        p2 = adsk.core.Point3D.create(half_w, sign * h, 0)
    else:
        sign = 1.0 if u_dot > 0 else -1.0
        p1 = adsk.core.Point3D.create(0, -half_w, 0)
        p2 = adsk.core.Point3D.create(sign * h, half_w, 0)

    sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
    prof = sk.profiles.item(0) if sk.profiles.count > 0 else None
    return sk, prof


# ---------------------------------------------------------------------------
# Sweep (full path, no gaps)
# ---------------------------------------------------------------------------
def _full_sweep(root, path, face_normal, half_w, h, body, op):
    """Create a full-length sweep along the entire path."""
    plane = _make_profile_plane(root, path, 0.0)
    _, prof = _draw_rect(root, plane, face_normal, half_w, h)
    if prof is None:
        raise RuntimeError('Failed to create sweep profile.')

    sweeps = root.features.sweepFeatures
    si = sweeps.createInput(prof, path, op)
    si.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    si.participantBodies = [body]

    feat = sweeps.add(si)
    if feat is None:
        raise RuntimeError('Sweep returned null.')
    if feat.healthState == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
        raise RuntimeError(f'Sweep failed: {feat.errorOrWarningMessage}')
    return feat


def _partial_sweep(root, path, face_normal, half_w, h, body, op,
                   start_frac=0.0, end_frac=0.0):
    """Create a sweep that starts at start_frac and clips the end at end_frac.

    For Cut operations, profile placement reliably clips the start because
    the cut simply doesn't happen where the sweep hasn't reached.
    distanceOne clips the end.
    """
    plane = _make_profile_plane(root, path, start_frac)
    _, prof = _draw_rect(root, plane, face_normal, half_w, h)
    if prof is None:
        raise RuntimeError('Failed to create sweep profile.')

    sweeps = root.features.sweepFeatures
    si = sweeps.createInput(prof, path, op)
    si.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    si.participantBodies = [body]

    # distanceOne clips the far end — fraction of forward-available path
    if end_frac > 0.001:
        sweep_range = 1.0 - start_frac - end_frac
        forward = 1.0 - start_frac
        d1 = sweep_range / forward if forward > 0.01 else 1.0
        si.distanceOne = _vi(min(d1, 1.0))

    feat = sweeps.add(si)
    if feat is None:
        raise RuntimeError('Partial sweep returned null.')
    if feat.healthState == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
        raise RuntimeError(f'Partial sweep failed: {feat.errorOrWarningMessage}')
    return feat


# ---------------------------------------------------------------------------
# End-gap trimming (tongue only — groove uses _partial_sweep)
# ---------------------------------------------------------------------------
def _trim_ends(root, path, face_normal, half_w, h, body,
               start_gap_cm, end_gap_cm, total_len):
    """Trim tongue ends by extruding cuts at the gap boundaries.

    For each end that needs a gap:
    1. Create a construction plane at the gap position on the path
    2. Draw the same cross-section rectangle on that plane
    3. Extrude-cut through-all in the direction toward the path endpoint
       This removes the tongue material between the trim plane and the endpoint.
    """
    if start_gap_cm > 0:
        frac = start_gap_cm / total_len
        _trim_one_end(root, path, face_normal, half_w, h, body, frac, toward_start=True)

    if end_gap_cm > 0:
        frac = 1.0 - (end_gap_cm / total_len)
        _trim_one_end(root, path, face_normal, half_w, h, body, frac, toward_start=False)


def _trim_one_end(root, path, face_normal, half_w, h, body, frac, toward_start):
    """Extrude-cut from the trim plane toward the nearest path endpoint."""
    try:
        plane = _make_profile_plane(root, path, frac)
        _, prof = _draw_rect(root, plane, face_normal, half_w, h)
        if prof is None:
            _log('Trim: no profile created')
            return

        extrudes = root.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # ThroughAllExtentDefinition (NOT AllExtentDefinition) for one-sided through-all
        through_all = adsk.fusion.ThroughAllExtentDefinition.create()
        direction = (adsk.fusion.ExtentDirections.NegativeExtentDirection if toward_start
                     else adsk.fusion.ExtentDirections.PositiveExtentDirection)
        ext_input.setOneSideExtent(through_all, direction)

        ext_input.participantBodies = [body]
        extrudes.add(ext_input)
    except:
        _log(f'Trim cut failed (non-critical):\n{traceback.format_exc()}')




# ---------------------------------------------------------------------------
# Chamfer + Fillet
# ---------------------------------------------------------------------------
def _chamfer_top(root, sweep_feat, chamfer_cm):
    """Chamfer edges on the tongue top face only.

    Only select edges where BOTH adjacent faces belong to the sweep.
    Then filter to longitudinal edges (longer ones).
    """
    try:
        sweep_fids = {f.tempId for f in sweep_feat.faces}

        candidates = []
        seen = set()
        for face in sweep_feat.faces:
            for edge in face.edges:
                eid = edge.tempId
                if eid in seen:
                    continue
                seen.add(eid)
                if all(af.tempId in sweep_fids for af in edge.faces):
                    candidates.append(edge)

        if not candidates:
            return

        max_len = max(e.length for e in candidates)
        edges = adsk.core.ObjectCollection.create()
        for e in candidates:
            if e.length >= max_len * 0.3:
                edges.add(e)

        if edges.count == 0:
            return

        ch = root.features.chamferFeatures
        ci = ch.createInput2()
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, _vi(chamfer_cm), True)
        ch.add(ci)
    except:
        _log(f'Chamfer failed (non-critical):\n{traceback.format_exc()}')


def _fillet_corners(root, groove_feat, fillet_cm):
    """Fillet the long interior edges of the groove."""
    try:
        all_edges = []
        seen = set()
        for face in groove_feat.faces:
            for edge in face.edges:
                eid = edge.tempId
                if eid not in seen:
                    seen.add(eid)
                    all_edges.append(edge)

        if not all_edges:
            return

        max_len = max(e.length for e in all_edges)
        edges = adsk.core.ObjectCollection.create()
        for e in all_edges:
            if e.length >= max_len * 0.3 and e.faces.count == 2:
                edges.add(e)

        if edges.count == 0:
            return

        fi = root.features.filletFeatures
        fii = fi.createInput()
        fii.addConstantRadiusEdgeSet(edges, _vi(fillet_cm), True)
        fii.isRollingBallCorner = True
        fi.add(fii)
    except:
        _log(f'Fillet failed (non-critical):\n{traceback.format_exc()}')
