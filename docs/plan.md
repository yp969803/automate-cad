# Plan: Auto-mate finder for STEP assemblies

## Context
Weekend assignment: given one part (STEP) with selected face IDs and an assembly (STEP), find every place in the assembly where those faces mate, say which part each match is on, return ALL instances (e.g. 4 slots in a 4-jaw chuck), highlight them, and justify the approach. Greenfield (empty folder). FreeCAD 1.1 is installed via snap.

## Key design decisions (and why)
- **Match by shape, not by current position.** The key is not sitting in the slot in the file, so matching must use intrinsic geometry (type, size, angles between faces), then compute where the part *would* go.
- **Match face groups, not single faces.** A vice has hundreds of planes; one plane matches everything. The selection's internal relations (angles, spacings, axes) are what make it unique.
- **Mates are complementary.** Convex ↔ concave, normals opposite, equal radius/width within a clearance tolerance. Same idea as SolidWorks SmartMates / Mate References and Reuleaux's lower pairs.
- **Don't require equal area.** A sliding jaw face is shorter than the body rail it slides on. Compare cross-section sizes (widths, radii, spacings), not areas or lengths along the free direction.
- **Use FreeCAD's bundled Python (`freecad.cmd`) first.** Already installed, includes OpenCascade via the Part module, reads STEP assemblies, and its `FaceN` numbering is the same face IDs the user sees when clicking in FreeCAD. Fallback: `pip install cadquery-ocp` (same OCC kernel, no snap sandbox; verify face numbering matches FreeCAD on one part), then pythonocc-core.
- **Two paths: analytic first, freeform fallback.** Planes/cylinders/cones/spheres/tori (nearly all of a vice or chuck) go through exact geometric matching. B-spline/freeform faces go through a slower point-cloud path (see below). Build the analytic path first; freeform is the extension.

## Alternatives considered
See [alternatives.md](alternatives.md) for pros and cons of each approach and tool.

## Spherical faces
- Descriptor: centre + radius + convex (ball) / concave (socket). No axis.
- Complementary pairs: sphere↔sphere (equal radius, opposite side), sphere↔cylinder (ball in bore, equal radius), sphere↔cone (ball in tapered seat, optional). Sphere↔plane is point contact → not a mate.
- Pose: one sphere fixes position only (3 rotations free). Sphere-only selection → report match as "spherical joint, rotation free", don't solve orientation. With other faces selected, use relations (centre–centre distance, centre–plane distance, centre on cylinder axis) to fix orientation.
- Compare radius/centre, never area (socket covers < half the ball).

## Freeform / unique shapes
- An unusual *combination* of analytic faces needs nothing extra — the relation graph handles it and rarer shapes give fewer false matches.
- B-spline faces:
  1. **Re-classify first**: sample points, least-squares fit plane/cylinder/sphere/cone; if residual < ~0.01 mm treat as that analytic type (exporters often store spheres/cylinders as B-splines).
  2. **Mixed selection**: solve pose from the analytic faces, then only verify the freeform face touches (distance ≈ 0).
  3. **Freeform-only selection**: sample points + normals, coarse pose via FPFH + RANSAC, refine with ICP into each candidate part's surface (selection → target, so partial contact works). Accept if mean distance < 0.1 mm, normals opposite, no interference. Run only on parts passing the size prefilter (slow).
- Symmetric freeform → report every pose that verifies.
- Out of scope: threads, knurling.

## Pipeline
1. **Load** the part and the assembly; flatten assembly into instances with world placement. Exclude any instance identical to the selected part itself.
2. **Face descriptors** for every face: type (plane/cylinder/cone/sphere/torus/other), radius, normal or axis, a point on it, convexity (material side from face orientation), and extents in its own frame.
3. **Selection signature**: small graph — nodes = selected faces, edges = angle between normals/axes, distance between parallel planes, coaxiality, axis offsets.
4. **Candidate search (fast)**:
   - Per-part bounding-box / size prefilter.
   - Hash index of faces by (type, rounded radius/width).
   - Anchor on the most distinctive selected face (e.g. a cylinder of a rare radius), then grow the match by checking edge relations (subgraph matching with backtracking). All candidate faces in one group must be on the same part.
5. **Compute pose**: rigid transform (proper rotation, no mirroring) that maps selected faces onto the candidate group; for planes/cylinders solve from normals/axes + points.
6. **Verify**: place the part with that pose, check face-to-face distance ≈ 0 (BRepExtrema) and overlap of mating faces; final interference check (boolean common ≈ 0 volume, allowing clearance). Reject failures.
7. **Collect all instances**; de-duplicate (a square key fits one slot in 4 rotations → keep one result per candidate face set).
8. **Label the joint** from what's left free (planar/prismatic/revolute/cylindrical/fixed via degrees of freedom) — cheap, and strengthens the write-up.
9. **Output** JSON (part name, face IDs, transform, score, joint type) + visual highlight: colour matched faces in FreeCAD and save an `.FCStd` (or coloured STEP).

## Build order
0. Project lives in `/home/yash/automate-cad`; plan at `docs/plan.md`.
1. Check `freecad.cmd` can import `Part`/`Import` and load the vice STEP (else switch to `cadquery-ocp`); dump face descriptors for one part and count face types (how many B-splines?).
2. Single-face complementary matching + highlight (proves the pipeline end-to-end).
3. Group/subgraph matching + pose.
4. Verification + de-duplication.
5. Joint labelling + JSON/report.
6. Sphere handling (rotation-free pose case) + B-spline re-classification.
7. Test on the vice (`WM290V_RedrawStart.stp`, split into sub-assemblies while iterating), a chuck + key, a peg/hole model and a ball/socket model built in FreeCAD.
8. If time: freeform point-cloud fallback (Open3D). Otherwise describe it in the write-up as the extension.
9. Write-up: approach, alternatives considered and why rejected, tolerances, limits (threads, freeform accuracy, symmetric shapes, mirrored parts, very loose fits).

## Open items
- Need the key/part STEP and the face IDs used in the Notion images (only screenshots there). Otherwise pick faces ourselves in FreeCAD.
- Tolerance values (default: 0.1 mm absolute, 1° angular, radius clearance up to ~2%).

## Verification
- Chuck key 4 faces → the slot(s); should match the 3 parts highlighted in the Notion image.
- Vice jaw sliding faces → body rails.
- Peg/hole test → exact expected hole count.
- Ball/socket test → match found, reported as spherical joint with free rotation.
- Negative test: unrelated faces → no verified matches.
- Cross-check a couple of matches by mating by hand in FreeCAD.
