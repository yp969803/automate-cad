# Freeform fallback: point sampling notes

How `src/cad/clouds.py` samples surfaces for the freeform (point-cloud) fallback, and two things learned while building it.

## Triangle direction (winding) and outward normals

- `Face.tessellate()` in FreeCAD returns a face as triangles, each given as three vertex indices, e.g. (0, 1, 2).
- The **winding** is the order of those three corners. By the right-hand rule, going 0→1→2 anticlockwise as seen from the front gives a normal pointing at the viewer: `n = (b - a) x (c - a)`.
- The alignment needs every sampled point to carry an **outward normal** (out of the material), because a mate means the two surfaces face each other (normals opposite). We take the normals from the triangle winding.
- **Check:** on 150 random faces of the lathe's Scroll Plate, the normal from the winding agreed with the face's own `normalAt` (the true outward normal) on all 150, including reversed faces. So FreeCAD winds triangles outward, and `clouds.py` uses the winding directly.
- **Limit:** tested on one part and 150 faces, relying on FreeCAD's behaviour rather than a documented guarantee. If normals ever look flipped, restore the per-face check against `normalAt` (it was removed because projecting the point to get `u, v` was slow).

## Why sampling was slow (and the fix)

Searching the lathe with a freeform selection took 5 min 33 s. Per-step timings:

| Step | Time |
|---|---|
| Load the lathe in FreeCAD | ~30 s, every FreeCAD start |
| Sample points (should have been the main cost) | 278 s before the fix |
| Align (FPFH + RANSAC + ICP) | ~1 s per part |

One part, the Scroll Plate (1,929 faces), took 171 s of the sampling. Tessellating all its faces takes only ~10 s. The real cause was `shape.Faces[i - 1]` inside a loop: FreeCAD **rebuilds the whole face list on every `.Faces` access**, so the loop did 1,929 x 1,929 face wrappers. Fix: read `shape.Faces` once into a variable (done in `clouds.py` and `src/cad/verify.py`). Sampling went from 5 min 33 s to 1 min 27 s.

Other things that did **not** help (so don't retry them): loosening the tessellation tolerance from h/10 to h/4, and removing the `Surface.parameter` call. They were kept because they are harmless, not because they were the cause.

## Other sampling choices

- Points are drawn at random inside each triangle with **random rounding** of the expected count (`area / h^2`), so tiny triangles don't each force one point. Before this, one part got 957,000 points against a 60,000 budget (`POINTS_PER_PART`).
- Spacing `h` is the selection's bounding-box diagonal / 50, raised per part so a part stays within the point budget.
- A fixed random seed makes the clouds identical on every run.
- Parts whose bounding-box diagonal is under 0.9 x the selection's are skipped (too small to hold it), as is any instance identical to the selected part.
