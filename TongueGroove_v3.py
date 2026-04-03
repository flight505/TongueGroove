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

            # Fit Clearance
            inp.addTextBoxCommandInput('_t', '', '<b>Fit Clearance</b>', 1, True)
            inp.addValueInput('val_side_clear', 'Side Clearance (per side)', 'mm', adsk.core.ValueInput.createByString('0.15 mm'))
            inp.addValueInput('val_bottom_clear', 'Bottom Clearance', 'mm', adsk.core.ValueInput.createByString('0.15 mm'))
            inp.addValueInput('val_end_clear', 'End Clearance (per end)', 'mm', adsk.core.ValueInput.createByString('0.2 mm'))

            # End Behaviour
            inp.addTextBoxCommandInput('_g', '', '<b>End Behaviour</b>', 1, True)
            dd_start = inp.addDropDownCommandInput('dd_start_end', 'Path Start',
                                                    adsk.core.DropDownStyles.TextListDropDownStyle)
            dd_start.listItems.add('Flush', True)
            dd_start.listItems.add('Inset', False)

            dd_end = inp.addDropDownCommandInput('dd_end_end', 'Path End',
                                                  adsk.core.DropDownStyles.TextListDropDownStyle)
            dd_end.listItems.add('Flush', True)
            dd_end.listItems.add('Inset', False)

            inp.addValueInput('val_inset', 'Inset Distance', 'mm',
                              adsk.core.ValueInput.createByString('0.5 mm')).isVisible = False

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
            if changed.id in ('dd_start_end', 'dd_end_end'):
                s = adsk.core.DropDownCommandInput.cast(inputs.itemById('dd_start_end')).selectedItem.name
                e = adsk.core.DropDownCommandInput.cast(inputs.itemById('dd_end_end')).selectedItem.name
                inputs.itemById('val_inset').isVisible = (s == 'Inset' or e == 'Inset')
            elif changed.id == 'bool_chamfer':
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
                  adsk.core.ValueCommandInput.cast(inp.itemById('val_end_clear')).value >= 0)
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
    width_cm       = _read_val(inputs, 'val_width')
    height_cm      = _read_val(inputs, 'val_height')
    side_clear_cm   = _read_val(inputs, 'val_side_clear')
    bottom_clear_cm = _read_val(inputs, 'val_bottom_clear')
    end_clear_cm    = _read_val(inputs, 'val_end_clear')
    inset_cm        = _read_val(inputs, 'val_inset')

    start_mode = adsk.core.DropDownCommandInput.cast(
        inputs.itemById('dd_start_end')).selectedItem.name  # 'Flush' or 'Inset'
    end_mode = adsk.core.DropDownCommandInput.cast(
        inputs.itemById('dd_end_end')).selectedItem.name

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

    # Path length must match what _make_path actually uses
    if len(curves) == 1:
        all_connected = sketch.findConnectedCurves(curves[0])
        total_len = sum(all_connected.item(i).length for i in range(all_connected.count))
    else:
        total_len = sum(c.length for c in curves)

    # Resolve per-end behaviour:
    #   Flush  → inset = 0 (joint goes to path endpoint)
    #   Inset  → inset = inset_cm (joint pulls back by this amount)
    #
    # End clearance ALWAYS applies (tongue shorter than groove).
    # Tongue = inset + end_clearance.  Groove = inset.
    inset_start = inset_cm if start_mode == 'Inset' else 0.0
    inset_end   = inset_cm if end_mode == 'Inset' else 0.0

    t_start = inset_start + end_clear_cm
    t_end   = inset_end + end_clear_cm
    g_start = inset_start
    g_end   = inset_end

    _log(f'total_len={total_len * 10:.2f}mm  end_clear={end_clear_cm * 10:.2f}mm')
    _log(f'start_mode={start_mode} (inset={inset_start * 10:.2f}mm)  '
         f'end_mode={end_mode} (inset={inset_end * 10:.2f}mm)')
    _log(f'tongue: start={t_start * 10:.2f}mm  end={t_end * 10:.2f}mm')
    _log(f'groove: start={g_start * 10:.2f}mm  end={g_end * 10:.2f}mm')

    if t_start + t_end >= total_len * 0.95:
        raise ValueError(
            f'Tongue insets ({(t_start + t_end) * 10:.1f}mm) exceed '
            f'95% of path length ({total_len * 10:.1f}mm).')

    # ---- Pre-flight validation ----
    # Check tongue width against body bounding box at the face
    ref = sketch.referencePlane
    face = adsk.fusion.BRepFace.cast(ref)
    if face:
        bb = face.boundingBox
        face_width = max(
            bb.maxPoint.x - bb.minPoint.x,
            bb.maxPoint.y - bb.minPoint.y,
            bb.maxPoint.z - bb.minPoint.z)
        if width_cm > face_width:
            raise ValueError(
                f'Tongue width ({width_cm * 10:.1f}mm) exceeds the face '
                f'dimension ({face_width * 10:.1f}mm). Reduce tongue width.')
        _log(f'Face bounding box max dimension: {face_width * 10:.1f}mm')

    if chamfer_cm > 0 and chamfer_cm >= height_cm * 0.5:
        _log(f'WARNING: chamfer ({chamfer_cm * 10:.1f}mm) is >= 50% of tongue height '
             f'({height_cm * 10:.1f}mm) — may fail')

    # Build path + face normal
    sweep_path  = _make_path(curves)
    face_normal = _face_normal(sketch)

    # ---- TONGUE ----
    _log('--- TONGUE ---')
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
    # Full sweep cut, then fill-back at each end.
    # distanceOne does NOT work for Cut sweeps (confirmed by diagnostic).
    _log('--- GROOVE ---')
    groove_hw = width_cm / 2.0 + side_clear_cm
    groove_h  = height_cm + bottom_clear_cm
    groove_feat = _full_sweep(
        root, sweep_path, face_normal,
        half_w=groove_hw, h=groove_h,
        body=groove_body,
        op=adsk.fusion.FeatureOperations.CutFeatureOperation)

    _fill_groove_ends(root, sweep_path, face_normal,
                      half_w=groove_hw, h=groove_h,
                      body=groove_body,
                      start_gap_cm=g_start, end_gap_cm=g_end,
                      total_len=total_len)

    if fillet_cm > 0 and groove_feat:
        _fillet_corners(root, groove_feat, fillet_cm)


# ---------------------------------------------------------------------------
# Path + geometry
# ---------------------------------------------------------------------------
def _make_path(curves):
    """Create sweep Path from selected SketchCurves.

    If 1 curve selected: findConnectedCurves auto-chains the full path.
    If 2+ curves selected: uses exactly those curves (user's explicit choice).
    """
    if len(curves) == 1:
        sketch = curves[0].parentSketch
        connected = sketch.findConnectedCurves(curves[0])
        _log(f'Path: 1 selected → findConnectedCurves found {connected.count} curves')
        if connected.count == 1:
            return adsk.fusion.Path.create(
                connected.item(0),
                adsk.fusion.ChainedCurveOptions.connectedChainedCurves)
        return adsk.fusion.Path.create(
            connected,
            adsk.fusion.ChainedCurveOptions.noChainedCurves)
    else:
        _log(f'Path: {len(curves)} curves explicitly selected')
        col = adsk.core.ObjectCollection.create()
        for c in curves:
            col.add(c)
        return adsk.fusion.Path.create(
            col, adsk.fusion.ChainedCurveOptions.noChainedCurves)


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
        d1 = min(d1, 1.0)
        si.distanceOne = _vi(d1)
        _log(f'Partial sweep: d1={d1:.4f} (sweep_range={sweep_range:.4f}, forward={forward:.4f})')
    else:
        _log(f'Partial sweep: d1=1.0 (full forward, no end clip)')

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
        _log(f'Trim tongue start: gap={start_gap_cm * 10:.2f}mm → frac={frac:.4f} '
             f'(absolute={frac * total_len * 10:.2f}mm from start)')
        _trim_one_end(root, path, face_normal, half_w, h, body, frac,
                      toward_start=True, total_len=total_len)

    if end_gap_cm > 0:
        frac = 1.0 - (end_gap_cm / total_len)
        _log(f'Trim tongue end: gap={end_gap_cm * 10:.2f}mm → frac={frac:.4f} '
             f'(absolute={(1.0 - frac) * total_len * 10:.2f}mm from end)')
        _trim_one_end(root, path, face_normal, half_w, h, body, frac,
                      toward_start=False, total_len=total_len)


def _trim_one_end(root, path, face_normal, half_w, h, body, frac, toward_start, total_len):
    """Cut away tongue material between the trim plane and the path endpoint.

    The trim plane is perpendicular to the path at `frac`. We extrude the
    tongue cross-section from this plane toward the nearest path endpoint.

    The extrude distance = gap size (the distance from trim plane to endpoint).
    Direction: Negative (toward start) or Positive (toward end) relative to
    the construction plane normal (which is the path tangent at that point).
    """
    try:
        side = 'START' if toward_start else 'END'
        # The gap distance in cm
        if toward_start:
            gap_cm = frac * total_len
        else:
            gap_cm = (1.0 - frac) * total_len

        _log(f'Trim {side}: frac={frac:.4f}, gap={gap_cm * 10:.2f}mm')

        plane = _make_profile_plane(root, path, frac)
        # Slightly oversized profile to ensure full coverage of the tongue
        _, prof = _draw_rect(root, plane, face_normal, half_w * 1.5, h * 1.5)
        if prof is None:
            _log(f'Trim {side}: no profile created')
            return

        extrudes = root.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # Extrude by gap distance + margin, toward the path endpoint.
        # Add 50% margin to guarantee full coverage.
        cut_dist = gap_cm * 1.5 + 0.1  # cm, with margin
        direction = (adsk.fusion.ExtentDirections.NegativeExtentDirection if toward_start
                     else adsk.fusion.ExtentDirections.PositiveExtentDirection)

        dist_def = adsk.fusion.DistanceExtentDefinition.create(_vi(cut_dist))
        ext_input.setOneSideExtent(dist_def, direction)
        ext_input.participantBodies = [body]

        feat = extrudes.add(ext_input)
        if feat:
            _log(f'Trim {side}: cut succeeded (dist={cut_dist * 10:.2f}mm)')
        else:
            _log(f'Trim {side}: extrude returned null')
    except:
        _log(f'Trim cut failed (non-critical):\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Groove end fill-back (fill the groove channel at each end with Join)
# ---------------------------------------------------------------------------
def _fill_groove_ends(root, path, face_normal, half_w, h, body,
                      start_gap_cm, end_gap_cm, total_len):
    """Fill the groove channel at each end by extruding a Join.

    After a full groove sweep (which cuts the full path), we fill material
    back into the groove at each end where a gap is needed. This shortens
    the groove channel from each end by gap_cm.

    Confirmed by diagnostic: extrude-Join from a plane on the path works.
    Direction: Positive = along path tangent, Negative = against.
    At the start (plane at gap_frac), Negative fills toward X=0.
    At the end (plane at 1-gap_frac), Positive fills toward X=max.
    """
    if start_gap_cm > 0:
        frac = start_gap_cm / total_len
        _log(f'Fill groove start: gap={start_gap_cm * 10:.2f}mm → frac={frac:.4f}')
        _fill_one_end(root, path, face_normal, half_w, h, body,
                      frac, gap_cm=start_gap_cm, toward_start=True)

    if end_gap_cm > 0:
        frac = 1.0 - (end_gap_cm / total_len)
        _log(f'Fill groove end: gap={end_gap_cm * 10:.2f}mm → frac={frac:.4f}')
        _fill_one_end(root, path, face_normal, half_w, h, body,
                      frac, gap_cm=end_gap_cm, toward_start=False)


def _fill_one_end(root, path, face_normal, half_w, h, body, frac, gap_cm, toward_start):
    """Extrude-Join from a plane at frac toward the nearest path endpoint."""
    try:
        side = 'START' if toward_start else 'END'
        plane = _make_profile_plane(root, path, frac)
        _, prof = _draw_rect(root, plane, face_normal, half_w, h)
        if prof is None:
            _log(f'Fill {side}: no profile created')
            return

        extrudes = root.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        # Fill distance = gap + small margin to ensure full coverage
        fill_dist = gap_cm + 0.01  # cm
        # Negative = toward path start, Positive = toward path end
        direction = (adsk.fusion.ExtentDirections.NegativeExtentDirection if toward_start
                     else adsk.fusion.ExtentDirections.PositiveExtentDirection)
        dist_def = adsk.fusion.DistanceExtentDefinition.create(_vi(fill_dist))
        ext_input.setOneSideExtent(dist_def, direction)
        ext_input.participantBodies = [body]

        feat = extrudes.add(ext_input)
        if feat:
            _log(f'Fill {side}: succeeded (dist={fill_dist * 10:.2f}mm)')
        else:
            _log(f'Fill {side}: extrude returned null')
    except:
        _log(f'Fill failed (non-critical):\n{traceback.format_exc()}')




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
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, _vi(chamfer_cm), False)
        try:
            ch.add(ci)
            _log(f'Chamfer applied: {chamfer_cm * 10:.2f}mm on {edges.count} edges')
        except RuntimeError as e:
            if 'UNFIN_SHEET' in str(e) or 'Compute Failed' in str(e):
                _log(f'Chamfer too large ({chamfer_cm * 10:.1f}mm), trying half size...')
                ci2 = ch.createInput2()
                ci2.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, _vi(chamfer_cm * 0.5), False)
                try:
                    ch.add(ci2)
                    _log(f'Chamfer applied at reduced size: {chamfer_cm * 5:.2f}mm')
                except:
                    _log(f'Chamfer failed even at reduced size — skipping')
            else:
                raise
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
