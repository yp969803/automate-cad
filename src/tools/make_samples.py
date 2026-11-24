"""Generate sample part + assembly STEP files with known answers into stepfile/ (run with freecad.cmd).
  freecad.cmd -c "exec(open('src/tools/make_samples.py').read())"
Each case writes <case>_part.step (the part to select faces on, placed away from the assembly and rotated),
<case>_assembly.step (several separate closed solids, incl. decoys that must NOT match) and prints the face ids to select.
Face ids are looked up in the re-imported part file, so they are the ones FreeCAD/descriptors.py report."""
import json, sys
sys.path.insert(0, 'src/cad')
import FreeCAD, Part, Import
import descriptors, verify  # same loader as the real pipeline: face ids and positions agree with it
V = FreeCAD.Vector
OUT = "stepfile/"

def export(shapes, path):
    d = FreeCAD.newDocument("x")
    for name, s in shapes: d.addObject("Part::Feature", name).Shape = s
    Import.export(d.Objects, path); FreeCAD.closeDocument(d.Name)

def box(x, y, z, dx, dy, dz): return Part.makeBox(dx, dy, dz, V(x, y, z))

def part_file(case, shape, pick):
    """Write the part rotated/moved away from the origin; return the ids (in the written file) of faces chosen by pick(face)."""
    chosen = [i for i, f in enumerate(shape.Faces) if pick(f)]
    s = shape.copy(); s.transformShape(FreeCAD.Placement(V(-300, 80, 15), FreeCAD.Rotation(V(0, 0, 1), 30)).toMatrix())
    s.exportStep(OUT + case + "_part.step")  # Shape.exportStep keeps the move; Import.export drops a shape's location
    back = verify.shape_of(descriptors.load(OUT + case + "_part.step")[1][0]).Faces
    ids = []
    for i in chosen:  # match by centre and area, in case the file reorders faces
        c, a = s.Faces[i].CenterOfMass, s.Faces[i].Area
        ids.append(next(j + 1 for j, f in enumerate(back) if (f.CenterOfMass - c).Length < 1e-3 and abs(f.Area - a) < 1e-3))
    return sorted(ids)

def planes(f, axis_dir, tol=1e-6):  # plane whose normal is +-axis_dir
    return type(f.Surface).__name__ == "Plane" and abs(abs(f.normalAt(0, 0).dot(V(*axis_dir))) - 1) < tol

info = {}

# 1. Chuck + key: key tip 7.8 square; chuck has 4 sockets 8.2 wide (clearance 0.4); decoys with 7.0 and 9.5 holes
tip = box(-3.9, -3.9, 0, 7.8, 7.8, 14)  # 14 long: fits the 15 deep sockets with the centred placement
key = tip.fuse(Part.makeCylinder(4, 60, V(0, 0, 14))).fuse(Part.makeCylinder(4, 70, V(-35, 0, 74), V(1, 0, 0)))
chuck = Part.makeCylinder(45, 35).cut(Part.makeCylinder(12, 35))
for ang in (0, 90, 180, 270):
    socket = box(30, -4.1, 13.4, 20, 8.2, 8.2); socket.rotate(V(0, 0, 0), V(0, 0, 1), ang); chuck = chuck.cut(socket)
def decoy(w, x): return box(x, 0, 0, 40, 40, 20).cut(box(x + 20 - w / 2, 20 - w / 2, 0, w, w, 20))
# select = the 4 long side faces of the key tip
info["chuck_key"] = dict(select=part_file("chuck_key", key, lambda f: (planes(f, (1, 0, 0)) or planes(f, (0, 1, 0))) and 100 < f.Area < 115),
    expect="4 matches on part 'chuck' (one per socket); decoys 'blank_narrow' (7.0 hole) and 'blank_loose' (9.5 hole) must not match")
export([("chuck", chuck), ("blank_narrow", decoy(7.0, 200)), ("blank_loose", decoy(9.5, 300))], OUT + "chuck_key_assembly.step")

# 2. Bench vice: sliding jaw (channel 24.4 x 8.3 underneath) on the body's rail (24 x 8); decoy guide with a 30 wide rail.
#    Sizes avoid coincidences (body slab 20 thick, fixed jaw 20 thick) that would let the channel straddle other parts.
base = box(0, -35, 0, 150, 70, 12)
body = base.fuse(box(20, -12, 12, 130, 24, 8))
fixed_jaw = box(0, -35, 12, 20, 70, 45)
def jaw(ox=0, oz=0): return box(ox, -35, oz, 40, 70, 45).cut(box(ox, -12.2, oz, 40, 24.4, 8.3))  # built at its final coordinates
seated = jaw(60, 12)
guide = box(0, 200, 0, 150, 70, 12).fuse(box(0, 220, 12, 150, 30, 8))
info["vice_jaw"] = dict(select=part_file("vice_jaw", jaw(), lambda f: type(f.Surface).__name__ == "Plane" and 8 < f.BoundBox.ZMax < 8.31 and f.BoundBox.XLength > 39 and (f.BoundBox.YLength < 0.01 or f.BoundBox.ZLength < 0.01)),
    expect="1 match on part 'body' (rail walls + top); fixed_jaw/screw/guide must not match. Jaw is also present seated in the assembly (ignored, identical part)")
export([("body", body), ("fixed_jaw", fixed_jaw), ("jaw_seated", seated), ("guide_wide_rail", guide)], OUT + "vice_assembly.step")

# 3. Pin + plates: pin R5 with a head; plate has 4 holes R5.1, decoy plates have R8 / R3 holes, washer has a R5.05 hole
pin = Part.makeCylinder(5, 25, V(0, 0, 4)).fuse(Part.makeCylinder(8, 4))
plate = box(0, 0, 0, 120, 60, 10)
for x in (20, 50, 80, 110): plate = plate.cut(Part.makeCylinder(5.1, 10, V(x, 30, 0)))
decoy_plate = box(0, 100, 0, 60, 40, 10).cut(Part.makeCylinder(8, 10, V(15, 120, 0))).cut(Part.makeCylinder(3, 10, V(45, 120, 0)))
washer = Part.makeCylinder(7, 2, V(200, 0, 0)).cut(Part.makeCylinder(5.05, 2, V(200, 0, 0)))
info["pin_plate"] = dict(select=part_file("pin_plate", pin, lambda f: type(f.Surface).__name__ == "Cylinder" and abs(f.Surface.Radius - 5) < 1e-6),
    expect="5 matches: 4 holes in 'plate' and the 'washer' hole; decoy plate holes (R8, R3) must not match")
export([("plate", plate), ("decoy_plate", decoy_plate), ("washer", washer)], OUT + "pin_plate_assembly.step")

# 4. Freeform: a part with an elliptical dome (B-spline surface, semi-axes 10 x 6 x 8) on a round base;
#    the housing has two matching dome pockets (one turned 90 deg); the decoy block has a taller pocket (10 x 6 x 11)
def dome(sx, sy, sz, centre, rot=0, down=False):
    m = FreeCAD.Matrix(); m.scale(sx / 8, sy / 8, sz / 8)
    e = Part.makeSphere(8).transformGeometry(m)
    half = e.common(box(-20, -20, -20, 40, 40, 20) if down else box(-20, -20, 0, 40, 40, 20))  # keep the lower (pocket) or upper (dome) half
    half.rotate(V(0, 0, 0), V(0, 0, 1), rot); half.translate(centre); return half
handle = Part.makeCylinder(10.5, 12).fuse(dome(10, 6, 8, V(0, 0, 12)))
housing = box(0, 0, 0, 90, 40, 30).cut(dome(10, 6, 8, V(20, 20, 30), 0, True)).cut(dome(10, 6, 8, V(65, 20, 30), 90, True))
decoy_block = box(0, 100, 0, 50, 40, 30).cut(dome(10, 6, 11, V(25, 120, 30), 0, True))
info["freeform_dome"] = dict(select=part_file("freeform_dome", handle, lambda f: type(f.Surface).__name__ not in ("Plane", "Cylinder")),
    expect="2 matches on part 'housing' (the two dome pockets, found by point-cloud alignment); 'decoy_block' (taller pocket) must not match")
export([("housing", housing), ("decoy_block", decoy_block)], OUT + "freeform_dome_assembly.step")

json.dump(info, open(OUT + "samples.json", "w"), indent=1)
for k, v in info.items(): print("SAMPLE", k, "select faces", v["select"])
