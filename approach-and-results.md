# Approach and results

## Approach
A mate is two complementary surfaces: convex against concave, same size, with a gap that is either almost zero (exact) or controlled (sliding). The selected faces are a group, so they must also keep the same angles and spacings. We compare shapes, not positions, then check the result in real geometry.

**What we compare**
- **Face type and size:** plane, cylinder (radius), cone (angle, apex), sphere (radius), torus (two radii). Clearance allowed: width up to 0.5 mm, radius 2 % (at least 0.25 mm).
- **Convex or concave:** a pin goes into a hole, not against another pin.
- **Relations inside the selection:** angle between normals or axes, offset between parallel planes, distance between axes. They do not change with position or orientation, and one plane alone would match every plane.
- **Same part:** all faces of a match are on one part.

**Steps**
1. Describe every face; merge faces the exporter split; relabel B-splines that are really planes, cylinders or spheres.
2. Search each part for complementary faces that keep the selection's relations.
3. Place the part (rotation by SVD, shift by least squares); name the free motion.
4. Check in real geometry: faces touch, no overlap with the assembly.
5. Label the fit: gap ≤ 0.05 mm is `exact/interference`, more is `sliding/clearance`.
6. Report every instance; a symmetric part gives several poses.
7. Freeform faces: align a point cloud onto each part (FPFH + RANSAC + ICP), then check as above.

**Why:** no training data, every result is explained by the numbers above, and the real-geometry check removes chance matches (96 candidates become 3 on the lathe key).

**Limits:** overlap needs closed solids (53 of 123 lathe parts are open shells, so only contact is checked); seated depth along a free direction is a centred guess; clearance values tuned on these examples; no threads, gears or mirrored parts; freeform is slow on big parts. See [docs/plan.md](docs/plan.md).

## Pictures
Part: blue, selected faces green. Assembly: one colour per part, only to tell them apart. Highlight: grey = part holding the match, red = matched faces, blue = your part placed, green = its selected faces.

## Results

### Lathe chuck key (real)
Faces `2, 4, 16, 18`. Found the sockets of the 3 pinions, `sliding/clearance`, gap 0.2 mm, 4 poses each.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/lathe_chuck_key/part.png) | ![](assets/lathe_chuck_key/assembly.png) | ![](assets/lathe_chuck_key/highlight.png) |

### Chuck and key
Faces `1, 2, 6, 8`. Found 4 sockets (`sliding/clearance`, 0.2 mm) and the 7.8 mm blank (`exact/interference`). The 7.0 and 9.5 mm blanks are rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/chuck_key/part.png) | ![](assets/chuck_key/assembly.png) | ![](assets/chuck_key/highlight.png) |

### Bench vice jaw
Faces `5, 6, 7`. Found the body's rail (`sliding/clearance`, 0.2 mm). Fixed jaw and wide-rail guide rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/vice_jaw/part.png) | ![](assets/vice_jaw/assembly.png) | ![](assets/vice_jaw/highlight.png) |

### Keyed shaft: sides and bottom
Faces `3, 4, 5`. Found `shaft_a` (8.0 keyway, `exact/interference`), `shaft_b` and the hub (8.2 keyways, `sliding/clearance`). The 10 mm keyway is rejected. The key also fits the hub upside down.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/keyed_shaft_sides_bottom/part.png) | ![](assets/keyed_shaft_sides_bottom/assembly.png) | ![](assets/keyed_shaft_sides_bottom/highlight.png) |

### Keyed shaft: sides and top
Faces `3, 4, 6`. Same three matches.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/keyed_shaft_sides_top/part.png) | ![](assets/keyed_shaft_sides_top/assembly.png) | ![](assets/keyed_shaft_sides_top/highlight.png) |

### Pulley on a motor shaft
Face `8` (bore). Found the R12.0 motor shaft (`exact/interference`) and the R11.9 countershaft (`sliding/clearance`). R10 and R16 shafts rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/pulley_shaft/part.png) | ![](assets/pulley_shaft/assembly.png) | ![](assets/pulley_shaft/highlight.png) |

### Pulley on a V-belt
Faces `3, 5` (two V flanks). Found the V-belt (`sliding/clearance`, 0.1 mm, revolute). Flat belt and different V angle rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/pulley_belt/part.png) | ![](assets/pulley_belt/assembly.png) | ![](assets/pulley_belt/highlight.png) |

### Pin in plates
Face `1`. Found 7 holes: 4 in `plate` and the washer (`sliding/clearance`), 2 in `dowel_plate` (R5.0 and R4.98 press fit, `exact/interference`). R8 and R3 holes rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/pin_plate/part.png) | ![](assets/pin_plate/assembly.png) | ![](assets/pin_plate/highlight.png) |

### Freeform dome
Face `4` (B-spline). Found both dome pockets by point-cloud alignment (`exact/interference`). The taller pocket is rejected.

| Part | Assembly | Highlight |
|---|---|---|
| ![](assets/freeform_dome/part.png) | ![](assets/freeform_dome/assembly.png) | ![](assets/freeform_dome/highlight.png) |
