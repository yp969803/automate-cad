# Alternatives considered

Chosen: **analytic face-group matching** (approach 1), with ideas borrowed from 3 (face index prefilter) and 4 (freeform fallback). See [plan.md](plan.md).

## Matching approaches

### 1. Face-group matching by geometry (chosen)
Describe each face by type, size, normal/axis; match the selection as a small graph of angles/spacings; solve the pose; verify fit.
- **Pros:** explainable; no training data; finds all instances (e.g. 4 chuck slots); exact for planes/cylinders/cones/spheres/tori; keeps face IDs.
- **Cons:** fails on B-spline/freeform faces without a fallback; tolerances need tuning; sphere-only selections leave rotation undetermined.

### 2. Single-face pairing (SolidWorks SmartMates style)
Pair each selected face with any complementary face (cylinder ↔ hole of same radius, plane ↔ opposite plane).
- **Pros:** very simple; fast; easy to explain.
- **Cons:** floods with false matches (one plane on the vice matches hundreds); no pose for the whole part; needs group constraints anyway → becomes approach 1.

### 3. Geometric hashing / point-pair features
Fingerprint the selection from pairwise angles/distances between faces; look up in an index of all parts.
- **Pros:** fast on large assemblies; handles many parts well.
- **Cons:** fuzzy (hash collisions, rounding); still needs pose solving + verification; tuning bin sizes is fiddly.

### 4. Point-cloud registration (ICP / RANSAC, e.g. Open3D)
Sample points on the selected faces and align them to each part's surface.
- **Pros:** works on any shape, including freeform; well-known libraries.
- **Cons:** slow; needs a good initial guess; weak on partial contact (short jaw on long rail); approximate; loses face IDs (must map back).

### 5. Feature recognition (attributed adjacency graph)
Recognise slots, holes, bosses first, then match feature ↔ feature by type and dimensions.
- **Pros:** semantic results ("key fits slot"); robust once features are recognised; small search space.
- **Cons:** each recogniser is hand-written work; unknown/odd features fall through; too much for the time budget.

### 6. Machine learning on B-rep (JoinABLe, UV-Net, BRepNet)
Neural net trained on the Fusion 360 Gallery joint dataset predicts joints between two parts.
- **Pros:** state of the art for exactly this problem; can learn fuzzy/freeform cases.
- **Cons:** needs training data and a GPU; not explainable; predicts one best joint, not all instances; domain gap to this vice/chuck.

## Tooling

| Tool | Pros | Cons |
|---|---|---|
| **FreeCAD Python (`freecad.cmd`)** (chosen) | Already installed; OCC kernel; `FaceN` IDs match what the user clicks in FreeCAD | Snap sandbox can block file access/imports |
| **CadQuery / OCP (`pip install cadquery-ocp`)** (fallback) | Same kernel; pip install, no sandbox | Face numbering must be checked against FreeCAD |
| **pythonocc-core** | Full OCC API | Easiest via conda; verbose API |
| **Onshape API** | Built-in mate features | Cloud-only; uploading the model |
| **SolidWorks API** | Mature SmartMates | Windows + licence |
| **trimesh / mesh tools** | Simple, fast | Lose exact surface types and face IDs |
