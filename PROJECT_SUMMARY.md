# Tongue & Groove Add-In: Development Summary

This document serves as a comprehensive history of the development process for the Tongue & Groove Fusion 360 Add-in. It tracks the core features fully implemented, the technical hurdles we encountered, various approaches we attempted (and why they failed), and the final robust solutions we deployed.

---

## 1. Core Achievements & What Works
We successfully converted a basic script into a deeply integrated, highly functional Fusion 360 Add-In that dynamically previews and generates tongue and groove woodworking/3D-printing joints.

*   **Persistent UI Integration**: The tool installs persistently into the `SolidModifyPanel` as a native-feeling command, featuring dynamic tooltips, categorized inputs (Dimensions, Tolerances, Options), and live preview rendering that rolls back safely if cancelled.
*   **Intelligent Geometry Dispatcher**: We wrote a custom Python bridge that reads user-selected centerlines and automatically generates the precise 2D profile needed for extrusion.
*   **Analytical Straight-Line Engine**: A highly-optimized mathematical solver explicitly calculates unit vectors, perpendiculars, and arc winding sweeps for standard straight lines. This ensures millimeter-perfect accuracy.
*   **Curved/Spline Path Support**: We integrated Fusion's native `addOffset2` solver to support complex, organic shapes like arcs and splines, ensuring the slot offsets gracefully follow the original curve.
*   **"End Inset" & Flush Caps**: Instead of drawing semicircle caps that unintentionally protrude past the centerline bounding box, the system dynamically calculates inset vectors. This keeps the slot perfectly flush with the underlying edge, with a user-configurable gap length.

---

## 2. What We Tried & What Didn't Work

A significant portion of development was spent working around the quirks and limitations of the Fusion 360 Python API. 

### Attempt 1: Drawing Slots in a "New Sketch" (Failed)
*   **The Idea**: To avoid polluting the user's selected sketch with our construction lines, we created a brand-new sketch on the same underlying `referencePlane` and tried to draw the slot there.
*   **Why it Failed**: Two sketches on the identical face in Fusion 360 do *not* share the same local coordinate system. The origin can shift, and the X/Y axes can be inverted or rotated natively. Our attempts to use `Matrix3D` bridge transformations via World Space fixed the origin translation but failed to normalize the arc winding directions (CCW vs CW), leading to exploded profile geometry at small tongue widths.

### Attempt 2: Approximating Curved Paths with Math (Failed)
*   **The Idea**: Calculating offset nodes by iterating over the curve evaluator's parametric points (start/end nodes). 
*   **Why it Failed**: Reconstructing splines and arcs using discrete points creates choppy geometry that doesn't resolve well into a selectable `Profile` area. We had to abandon math-based generation for curves in favor of Fusion's native geometric constraint solver (`addOffset2`).

### Attempt 3: Returning an `ObjectCollection` for `participantBodies` (Failed)
*   **The Idea**: The Fusion 360 Python API documentation loosely implies that most plural parameters accept an `ObjectCollection`. We passed our selected Bodies into `ext_input.participantBodies`.
*   **Why it Failed**: It triggered a deep C++ SWIG wrapper crash (`TypeError: in method 'ExtrudeFeatureInput__set_participantBodies', argument 2 of type 'std::vector< adsk::core::Ptr< adsk::fusion::BRepBody [...]`). Fusion actually strictly requires a standard Python `list()` like `[tongue_body]` for participant bodies, not an API collection. 

### Attempt 4: Bash Deployment Scripts (Failed)
*   **The Idea**: Using standard macOS bash `cp` or `cat` commands to sync code from the project directory to the isolated `Application Support/.../AddIns` directory.
*   **Why it Failed**: macOS Sandbox security (`com.apple.provenance` extended attributes) silently blocked the shell from overwriting the files. The terminal reported success, but the cached `TongueGroove.py` file never actually updated on disk, causing days of phantom bugs.
*   **The Fix**: We bypassed the bash file locks by utilizing Python `open('/path', 'wb').write()` streams to inject the raw data directly over the old files, which respected the permissions correctly.

---

## 3. Key Design Decisions

1.  **Original Sketch Canvas**: We decided to draw our 2D boundaries directly into the user's *original* sketch containing the centerline. We utilize the fact that Fusion 360's command preview system establishes a rigid database transaction; if the user clicks "Cancel" (or when a preview redraws), Fusion instantly rolls back all our dynamically drawn arcs and lines seamlessly.
2.  **Bisection Filtering**: To cleanly extrude the slot, we needed to programmatically select the closed profile. Because the centerline runs precisely down the middle of the slot, it bisects the geometric cut into two "D-shaped" halves. We wrote an area-and-centroid mathematical filtering algorithm to cleanly sniff out exactly these two halves, merge them into a single collection, and pass them to the Extrude feature.
3.  **Naming Convention limits**: We permanently renamed the plugin directory from `Tongue&Groove` to `TongueGroove` for the deployment. Fusion 360's internal JavaScript command registry strictly fails to load plugins containing special characters like `&` in their folder names.
