# Write-up

**In:** part STEP + selected face ids + assembly STEP.
**Out:** every place those faces mate, which part, exact or sliding fit, and a highlight file.
Built on FreeCAD 1.1 (OpenCascade) and Open3D. Results with pictures: [approach-and-results.md](approach-and-results.md).

## What I match on, and why
The part is not in its mated position, so I compare shapes, not positions.

- Same surface type and size (plane, cylinder, cone, sphere, torus). Slack of 0.5 mm on widths and 2 % on radii, so sliding fits show up.
- Opposite curvature. A pin goes in a hole, not on another pin.
- Same relations between the selected faces (angles, plane spacing, axis distance). One plane alone matches everything; three key-slot faces match very little.
- All faces on one part.
- Then a real geometry check: faces touch, no overlap. On the lathe, 96 candidates became 3, all correct.
- Gap up to 0.05 mm is exact, more is sliding.
- Freeform faces: point-cloud alignment, then the same check.

Why rules: STEP gives exact surfaces, there is no training data, and a wrong match can be traced to one number. Every generated test has decoys, and none match.

## What breaks
- 53 of 123 lathe parts are open shells, so no overlap check on them.
- Depth along a free axis is guessed (centred).
- Tolerances tuned on these samples only.
- No threads, gears or mirrored parts.
- One selected plane matches too much.
- Freeform is slow and only tested on synthetic shapes.
- Mostly generated samples; no real vice.

## With another week
1. Close open shells so overlap works everywhere.
2. Find seated depth from stop faces.
3. Test on real assemblies, then set tolerances.
4. Threads, gears, mirrored parts.
5. Faster freeform.
6. Tests in CI.

**Speed:** about 10 s for a small assembly, about 1 min 45 s on the 22 MB lathe (face data cached).
