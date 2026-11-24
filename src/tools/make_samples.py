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

def part_file(case, shape, pick, *more):
    """Write the part rotated/moved away from the origin; return the ids (in the written file) of faces chosen by pick(face).
    With extra pick functions, return one id list per pick (same file, different selections)."""
    picks = (pick,) + more; chosen_sets = [[i for i, f in enumerate(shape.Faces) if p(f)] for p in picks]
    chosen = sorted({i for c in chosen_sets for i in c})
    s = shape.copy(); s.transformShape(FreeCAD.Placement(V(-300, 80, 15), FreeCAD.Rotation(V(0, 0, 1), 30)).toMatrix())
    s.exportStep(OUT + case + "_part.step")  # Shape.exportStep keeps the move; Import.export drops a shape's location
    back = verify.shape_of(descriptors.load(OUT + case + "_part.step")[1][0]).Faces
    new_id = {}
    for i in chosen:  # match by centre and area, in case the file reorders faces
        c, a = s.Faces[i].CenterOfMass, s.Faces[i].Area
        new_id[i] = next(j + 1 for j, f in enumerate(back) if (f.CenterOfMass - c).Length < 1e-3 and abs(f.Area - a) < 1e-3)
    out = [sorted(new_id[i] for i in c) for c in chosen_sets]
    return out if more else out[0]

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
    expect="4 sliding/clearance matches on 'chuck' (one per socket, 8.2 vs 7.8) and 1 exact/interference match on 'blank_exact' (7.8 hole); decoys 'blank_narrow' (7.0 hole) and 'blank_loose' (9.5 hole) must not match")
export([("chuck", chuck), ("blank_narrow", decoy(7.0, 200)), ("blank_loose", decoy(9.5, 300)), ("blank_exact", decoy(7.8, 400))], OUT + "chuck_key_assembly.step")

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

# 3. Pin + plates: pin R5 with a head; plate has 4 holes R5.1, decoy plates have R8 / R3 holes, washer has a R5.2 hole, dowel plate has R5.0 and R4.98 holes
pin = Part.makeCylinder(5, 25, V(0, 0, 4)).fuse(Part.makeCylinder(8, 4))
plate = box(0, 0, 0, 120, 60, 10)
for x in (20, 50, 80, 110): plate = plate.cut(Part.makeCylinder(5.1, 10, V(x, 30, 0)))
decoy_plate = box(0, 100, 0, 60, 40, 10).cut(Part.makeCylinder(8, 10, V(15, 120, 0))).cut(Part.makeCylinder(3, 10, V(45, 120, 0)))
washer = Part.makeCylinder(7, 2, V(200, 0, 0)).cut(Part.makeCylinder(5.2, 2, V(200, 0, 0)))
info["pin_plate"] = dict(select=part_file("pin_plate", pin, lambda f: type(f.Surface).__name__ == "Cylinder" and abs(f.Surface.Radius - 5) < 1e-6),
    expect="7 matches: sliding/clearance: 4 holes in 'plate' (R5.1) and the 'washer' hole (R5.2); exact/interference: the 2 holes in 'dowel_plate' (R5.0 exact, R4.98 press fit); decoy plate holes (R8, R3) must not match")
dowel_plate = box(0, 200, 0, 60, 40, 10).cut(Part.makeCylinder(5.0, 10, V(15, 220, 0))).cut(Part.makeCylinder(4.98, 10, V(45, 220, 0)))  # exact and press fit
export([("plate", plate), ("decoy_plate", decoy_plate), ("washer", washer), ("dowel_plate", dowel_plate)], OUT + "pin_plate_assembly.step")

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


def revolve(points, centre=(0, 0)):
    """Solid of revolution about the Z axis through `centre` from (r, z) profile points."""
    pts = [V(r, 0, z) for r, z in points]; solid = Part.Face(Part.makePolygon(pts + [pts[0]])).revolve(V(0, 0, 0), V(0, 0, 1), 360)
    solid.translate(V(centre[0], centre[1], 0)); return solid

# 5. Keyed shaft: key 8 x 25 x 7. Shafts (R12, along X) have a keyway 25 long, floor at z=8: shaft_a 8.0 wide (exact),
#    shaft_b 8.2 (clearance), shaft_wrong 10.0 (must not match). The hub's keyway is 8.2 wide, ceiling at z=15.3.
#    Selection A = the two sides + bottom of the key (finds the shafts); selection B = the two sides + top (finds the hub).
key2 = box(-12.5, -4, 0, 25, 8, 7)
def shaft(y, w): return Part.makeCylinder(12, 120, V(0, y, 0), V(1, 0, 0)).cut(box(47.5, y - w / 2, 8, 25, w, 10))
hub = Part.makeCylinder(30, 30, V(0, 180, 0), V(1, 0, 0)).cut(Part.makeCylinder(12, 30, V(0, 180, 0), V(1, 0, 0))).cut(box(2.5, 180 - 4.1, 0, 25, 8.2, 15.3))
side = lambda f: planes(f, (0, 1, 0)) and 170 < f.Area < 180
bottom = lambda f: planes(f, (0, 0, 1)) and f.BoundBox.ZMax < 0.01
top = lambda f: planes(f, (0, 0, 1)) and f.BoundBox.ZMin > 6.99
ids_a, ids_b = part_file("keyed_shaft", key2, lambda f: side(f) or bottom(f), lambda f: side(f) or top(f))
info["keyed_shaft"] = dict(select=ids_a, select_hub=ids_b,
    expect="both selections: 3 matches, 'shaft_a' exact/interference (8.0 keyway), 'shaft_b' and 'hub' sliding/clearance (8.2 keyways); 'shaft_wrong' (10.0) must not match. The key is symmetric, so it also fits turned upside down: selection A (sides+bottom) fits the hub keyway with its bottom against the ceiling, B (sides+top) fits the shaft keyways with its top on the floor")
export([("shaft_a", shaft(0, 8.0)), ("shaft_b", shaft(60, 8.2)), ("shaft_wrong", shaft(120, 10.0)), ("hub", hub)], OUT + "keyed_shaft_assembly.step")

# 6/7. Pulley (profile r,z about Z): bore R12, rim R40 with a V-groove (flanks from (40,4)-(32,8) and (32,16)-(40,20)).
PULLEY = [(12, 0), (40, 0), (40, 4), (32, 8), (32, 16), (40, 20), (40, 24), (12, 24)]
pulley = revolve(PULLEY)
bore = lambda f: type(f.Surface).__name__ == "Cylinder" and abs(f.Surface.Radius - 12) < 1e-6
flank = lambda f: type(f.Surface).__name__ == "Cone"
# 6. Pulley on a motor shaft: select the bore; shafts R12.0 (exact) and R11.9 (clearance) match, R10 and R16 must not
def rod(r, c, length=80): return Part.makeCylinder(r, length, V(c[0], c[1], 0))
motor = box(-40, -40, -40, 80, 80, 40).fuse(rod(12, (0, 0)))
info["pulley_shaft"] = dict(select=part_file("pulley_shaft", pulley, bore),
    expect="2 matches: 'motor' shaft R12.0 (exact/interference) and 'countershaft' R11.9 (sliding/clearance); 'fan_shaft' (R10) and 'idler_shaft' (R16) must not match")
export([("motor", motor), ("countershaft", rod(11.9, (200, 0))), ("fan_shaft", rod(10, (300, 0))), ("idler_shaft", rod(16, (400, 0)))], OUT + "pulley_shaft_assembly.step")

# 7. V-belt on the pulley: select the two groove flanks. The belt ring has flanks 0.1 mm inside the groove (clearance);
#    decoys: a flat belt (no cones) and a belt with a shallower V (different cone angle)
def belt(slope, centre):
    low = lambda r: 8 - slope * (r - 32.5)  # lower flank z at radius r; upper flank is its mirror about z=12
    return revolve([(32.5, low(32.5)), (42, low(42)), (42, 24 - low(42)), (32.5, 24 - low(32.5))], centre)
# belt flanks = the groove flanks moved 0.1 mm into the groove (normal (4, 8)/8.944 for a flank of slope 0.5)
v_belt = revolve([(32.5, 7.861), (42, 3.115), (42, 20.885), (32.5, 16.139)], (200, 0))
shallow = belt(0.25, (400, 0)); flat = revolve([(32, 6), (44, 6), (44, 18), (32, 18)], (300, 0))
info["pulley_belt"] = dict(select=part_file("pulley_belt", pulley, flank),
    expect="1 sliding/clearance match on 'v_belt' (the two groove flanks against the belt's flanks, 0.1 mm clearance); 'flat_belt' and 'shallow_belt' (different V angle) must not match")
export([("v_belt", v_belt), ("flat_belt", flat), ("shallow_belt", shallow)], OUT + "pulley_belt_assembly.step")

json.dump(info, open(OUT + "samples.json", "w"), indent=1)
for k, v in info.items(): print("SAMPLE", k, "select faces", v["select"])
