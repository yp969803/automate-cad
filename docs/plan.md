# Plan: Auto-mate finder for STEP assemblies

## Context
Weekend assignment: given one part (STEP) with selected face IDs and an assembly (STEP), find every place in the assembly where those faces mate, say which part each match is on, return ALL instances (e.g. 4 slots in a 4-jaw chuck), highlight them, and justify the approach. The example assembly (`WM290V_RedrawStart.stp`) is a **lathe**, not a vice; the chuck key is the part named `Key` inside it. FreeCAD 1.1 (snap) is the CAD kernel; Open3D is used for the freeform fallback.

## Status (what is built and tested)
| Piece | State |
|---|---|
| Face descriptors for any STEP assembly (`cad/descriptors.py`) | done, incl. merging split faces and relabelling B-spline/extrusion faces |
| Face-group matching (`search/match.py`) | done: plane, cylinder, cone, sphere, torus |
| Placement + joint type (rotation, shift, free motion) | done |
| Fit check with real geometry (`cad/verify.py`) | done; overlap check only works on closed solids |
| Freeform fallback (`cad/clouds.py`, `search/freeform.py`) | done, tested on one synthetic shape, not on a real freeform mate |
| Highlight: HTML viewer, FCStd, coloured STEP (`cad/highlight.py`, `cad/color_step.py`) | done |
| Real test: lathe chuck key | **3 matches = the 3 `Pinion M1.8 10T` sockets** (see Results) |
| Bench-vice jaw case | not tested (no vice model) |
| Write-up | not written |

## How to run
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt     # numpy, open3d (FreeCAD is the snap)
.venv/bin/python src/search/match.py part.step 2,4,16,18 assembly.step    # face IDs = FaceN ids in FreeCAD
```
Outputs: `cache/matches.json` (verified matches with 4x4 placement, joint type, gap, overlap) and `cache/highlight.html`, `.FCStd`, `.step`. Tests with known answers: `src/tools/make_test.py`; take one part out of an assembly: `src/tools/extract_part.py`.
All sample cases in one go (checks each result against its expected answer, saves outputs to `assets/`): `.venv/bin/python src/tools/run_samples.py` (add `--lathe` for the real chuck key; needs `stepfile/Redraw.step`).

## Code layout
- `src/cad/`: runs inside `freecad.cmd` (FreeCAD's Python): descriptors, verify, clouds, highlight, color_step.
- `src/search/`: runs in the venv: `match.py` (main program), `freeform.py` (point-cloud alignment).
- `src/tools/`: `make_test.py`, `extract_part.py`.
- FreeCAD cannot read `/tmp` (snap sandbox): keep files in the project folder.

## Key design decisions (and why)
- **Match by shape, not by current position.** The key is not sitting in the slot in the file, so matching must use intrinsic geometry (type, size, angles between faces), then compute where the part *would* go.
- **Match face groups, not single faces.** A lathe has thousands of planes; one plane matches everything. The selection's internal relations (angles, spacings, axes) are what make it unique.
- **Mates are complementary.** Convex ↔ concave, equal radius/width within a clearance tolerance. Same idea as SolidWorks SmartMates / Mate References and Reuleaux's lower pairs.
- **Facing is decided by the relations, not the current normals.** The part is not in place yet, so planes are all "compatible" by type; their signed offsets and angles (which flip sign for facing pairs) decide.
- **Don't require equal area.** A short face slides on a long rail. Compare cross-section sizes (widths, radii, spacings), not areas.
- **Use FreeCAD's bundled Python first.** Includes OpenCascade, reads STEP assemblies, and its `FaceN` numbering is the face IDs the user sees. Fallback: `pip install cadquery-ocp` (same kernel; face numbering would need checking).
- **Two paths: analytic first, freeform fallback.** Analytic faces go through exact geometric matching; freeform faces through point-cloud alignment.
- **Verify with real geometry.** Relations are only necessary conditions (553 candidates → 3 verified on the real key). Every match is placed and checked for contact and overlap.

Alternatives considered (pros and cons): [alternatives.md](alternatives.md).

## Pipeline (as implemented)
1. **Load** with FreeCAD; leaf parts = objects with faces whose children carry no faces; world placement applied. Instances identical to the selected part are skipped.
2. **Descriptors** per face (`descriptors.py`): type, point, axis/normal, radius or angle, convex flag (outward normal vs axis/centre), bounding box. Cones also store apex and the slant-distance band; tori store centre (`apex`), major/minor radius.
3. **Clean-up** before matching:
   - *Relabel*: B-spline and extrusion faces are sampled and fitted; if within a size-relative tolerance (`1e-5 x model diagonal`) they become plane/cylinder/sphere (`was` field keeps the old type). On the lathe 2,938 faces were relabelled.
   - *Merge split faces*: faces sharing an edge and lying on the same surface with the same material side become one face with all original IDs in `ids`.
4. **Search** (`match.py`): for each part, backtrack over complementary candidates; pair relations must agree (angle between normals/axes, offset of parallel planes, axis distance, point distances). Plane pairs are pre-filtered with numpy (the first version took 10+ minutes on the lathe). Symmetric fits share one face set (one result).
5. **Placement**: rotation from vector pairs (SVD; sign choices for axis directions are all tried), translation by least squares, free motion left centred. Cones and tori pin position through their apex/centre; spheres only fix position.
6. **Verify** (`verify.py`, FreeCAD): move the part, require contact (gap ≤ tolerance, boxes overlap) and no overlap with the assembly (boolean common ≤ 1 % of the part volume). Identical instances of the part are ignored (a free slot is judged without them). Poses that fail are dropped.
7. **Joint label** from the free degrees of freedom: fixed, slides along one axis, revolute, cylindrical, planar, ball.
8. **Output**: JSON + highlight files (grey = part holding the match, red = matched faces, blue = part placed, green = its selected faces).

## Surface-type rules
- **Plane**: any plane is a candidate; relations decide. A socket may be wider than the part by up to `CLR = 0.5 mm` (sliding fit) but never narrower than `DIST`.
- **Cylinder**: same radius within 2 % + 0.001 mm, opposite convexity. Both axis directions are tried.
- **Sphere**: same radius (2 %), opposite convexity. Sphere only fixes position (3 rotations free). Sphere↔cylinder/cone pairs are not implemented.
- **Cone**: same half-angle (1°, sign ignored), opposite convexity, and the slant-distance bands from the apex must overlap. Depth is fixed by making the two apexes coincide (not free) → joint "revolute".
- **Torus**: same major and minor radius (2 %), opposite convexity; centre pins position → revolute.
- **Extrusion**: first relabelled to plane/cylinder if it really is one. On the lathe 282 of 314 were; the 32 true extrusions are treated as freeform.
- **Freeform** (B-spline left over, true extrusions): see below.

## Freeform fallback (point cloud)
- Used when any selected face is B-spline/extrusion. The whole selection (analytic faces included) is aligned as one cloud onto each candidate part's surface.
- Sampling (FreeCAD, `clouds.py`): random points in the face triangles, outward normals from triangle winding (checked: 150/150 faces agree with `normalAt`), spacing = selection diagonal / 50, capped at 60,000 points per part, fixed seed. Parts too small to hold the selection are skipped.
- Alignment (Open3D, `freeform.py`): FPFH features + RANSAC for a coarse pose, ICP refinement. Accept if ≥ 85 % of the selection lands within 1.5 voxels of the surface facing the right way (normal dot > 0.7). The used surface is removed and the search repeats (up to 8 instances per part). Poses then go through the same verify step.
- Details and a speed bug: [freeform-sampling.md](freeform-sampling.md).
- Limits: free motion (symmetry/slide) not analysed; a seat touched only in a small patch can fail the 85 % test; slow on big parts.

## Fit classification (exact vs sliding)
The assignment asks to tell an exact/interference fit (key in slot: faces nearly coincide) from a sliding/clearance fit (vice jaw: faces parallel or coaxial with a controlled gap, never coincident). After the part is placed, `verify.py` measures the **largest gap between a selected face and its matched face** and labels the pose:
- `exact/interference`: gap ≤ `EXACT = 0.05 mm` (faces coincide; a small overlap from a press fit is allowed, within the 1 % overlap limit).
- `sliding/clearance`: gap > 0.05 mm (up to the contact tolerance); the gap is reported.
The free motion left (slides, spins, planar...) is reported separately as `joint`. Every pose in `matches.json` carries `fit`, `gap`, `overlap` and `joint`.
Examples (generated samples): key in a slot of its own width → exact (0.0 mm); same key in a slot 0.4 mm wider → clearance (0.2 mm per side); pin in R5.0 / R4.98 holes → exact / interference (0.0 / 0.02 mm); pin in R5.1 / R5.2 holes → clearance (0.1 / 0.2 mm); vice jaw on its rail → clearance (0.2 mm).
Limits: the class depends on one threshold; a real exact fit modelled with a small clearance (the lathe's pinion sockets are 0.2 mm per side) is reported as clearance, which is what the geometry says. The gap is measured after centring, so a part resting on one side shows half of the total clearance.

## Tolerances (all in `search/match.py`)
| Name | Value | Meaning |
|---|---|---|
| `ANG` | 0.0175 (~1°) | angle tolerance on dot products |
| `DIST` | 0.1 mm | distance tolerance |
| `CLEAR` | 2 % | radius clearance for cylinders/spheres/tori; small radii get `CLR/2` (0.25 mm) instead, so a R5 pin matches a R5.2 hole |
| `CLR` | 0.5 mm | width clearance for plane pairs (tuned on the real key socket: 8.2 mm vs 7.8 mm) |
| contact gap | `DIST + CLR/2 + CLEAR x radius` | allowed gap in verify |
| overlap | 1 % of part volume | allowed interference |
| `EXACT` (`cad/verify.py`) | 0.05 mm | largest gap still called an exact/interference fit |

## Results
- **Real chuck key** (`Key`, faces 2, 4, 16, 18 = the square tip, 7.8 mm): 553 candidates by relations → **3 verified, on `Pinion M1.8 10T`, `10T001`, `10T002`** (socket 8.2 mm, gap 0.2 mm per side, joint "slides along one axis"). This matches the 3 parts highlighted in the assignment. About 4 minutes on the lathe.
- **Small tests with known answers** (`make_test.py`): peg → R5 and R5.05 holes, R8 rejected; key → 10 mm slot, 12 mm slot rejected; 10.4 mm slot accepted, 9.6 mm rejected; hole with a plug inside → rejected by overlap; cone plug lands at the exact depth; ring fits its toroidal void (1 mm-tube groove rejected); ellipsoid knob found in the matching void and not in a different one (freeform).
- **Sample scenarios** (`stepfile/`, generated by `src/tools/make_samples.py`, details in `stepfile/README.md`): chuck + key (4 sockets + exact blank), bench vice jaw on its rail, keyed shaft (shaft, hub), pulley on a motor shaft (bore on two shafts), V-belt flanks on a pulley (two cones), pin in plates (exact / interference / clearance holes), freeform dome in two pockets. Each has decoys that are rejected; all pass.
- **Lathe cones**: 60° concave seat → 3 `Retaining Pin` parts; convex 45° cone → none (nearest cone seats are ~1 mm off).

## Known limits
- Overlap cannot be checked for open shells: 53 of the lathe's 123 parts (and some selected parts) are unclosed CATIA shells, so verification there is contact only (`overlap` is `null`). Closing them is a possible fix.
- Position along a free direction (e.g. how far the key is inserted) is a centred guess, not a true seated position.
- Symmetric parts give flipped duplicate placements (e.g. a pin right way up and upside down).
- Threads, knurling, gears: out of scope. Mirrored parts are not matched (proper rotations only).
- The 0.5 mm clearance was tuned on one example; a looser or tighter fit may need a different value.
- A selection where one face is split on one part but whole on the other is handled by the merge step only for planes, cylinders, cones, spheres and tori sharing an edge.
- Freeform path tested on one synthetic shape only (the lathe's few freeform parts are threads).
- Cone seats assume equal angles (within 1°); sphere↔cylinder/cone pairs are not matched.

## Remaining (what is still left)
**Needed for the assignment**
- **Write-up**: approach and why it fits best, alternatives and why rejected, tolerances, results (the key finding the 3 pinions), limits. Most of the text exists in this plan and `alternatives.md`; it needs to be pulled into one document.
- **Test on more assemblies**: the assignment asks for it. So far only the lathe plus small generated models. The bench-vice jaw case needs a vice model (the second example in the assignment).
- **Open shells**: 53 of the lathe's 123 parts are unclosed shells, so the overlap check does not run on them and lathe results are contact-only. Try sewing the faces into closed solids; if that fails, say so in the write-up.

**Accuracy**
- **Seated position**: where a part sits along a free direction (how far the key goes into the socket) is a centred guess. Could be set from a stop face or the deepest non-overlapping position.
- **Duplicate placements**: a symmetric part gives flipped copies of the same fit (pin right way up and upside down). Could be merged by comparing the placed shapes.
- **Tolerances**: `CLR = 0.5 mm` was tuned on one socket. Could be derived from the selection size or exposed as an option.
- **Missing pair rules**: sphere↔cylinder and sphere↔cone (ball in a bore or tapered seat), cones with different angles, mirrored parts.
- **Freeform**: tested on one synthetic shape only. Needs a real freeform mate, and partial-contact seats can fail the 85 % test.
- **Face IDs**: confirm the `FaceN` ids used here match what a user sees in the FreeCAD viewer (assumed, not checked).

**Speed and robustness**
- Cache sampled point clouds per assembly (sampling is repeated on every freeform search).
- Run the search per part in parallel; each lathe run is about 4 minutes, mostly FreeCAD loading and checking.
- Automated tests: `run_samples.py` runs the 9 sample cases and compares them with the expected answers; the older small tests in `make_test.py` are still run by hand.
- Option to skip the coloured-STEP/GUI step on machines without FreeCAD's GUI classes (it already fails soft).
