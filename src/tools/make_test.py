"""Make test STEP files with known answers (run with freecad.cmd).
cache/peg.step      : peg R5            -> select face 1 (cylinder)
cache/key.step      : 10mm cube         -> select faces 1,2 (two opposite planes)
cache/test.step     : assembly: plate with holes R5, R5.05, R8 ; block A with 10mm slot ; block B with 12mm slot ; ball
Expected: peg face 1 -> plate holes R5 and R5.05 (2 matches, not R8); key faces 1,2 -> slot in block A only;
peg vs test_blocked.step -> 1 candidate, 0 verified (plug in the hole).
"""
import FreeCAD, Part, Import
V = FreeCAD.Vector

def export(parts, path):
    d = FreeCAD.newDocument("t")
    for name, shp in parts: d.addObject("Part::Feature", name).Shape = shp
    Import.export(d.Objects, path)

plate = Part.makeBox(100, 40, 10)
for x, r in [(20, 5), (50, 5.05), (80, 8)]: plate = plate.cut(Part.makeCylinder(r, 10, V(x, 20, 0)))
export([("peg", Part.makeCylinder(5, 30))], "cache/peg.step")
export([("key", Part.makeBox(10, 10, 10))], "cache/key.step")
# slot cut along x through the block: walls at y = +-w/2 facing each other
def block(w, y0): return Part.makeBox(40, 30, 20, V(200, y0, 0)).cut(Part.makeBox(40, w, 15, V(200, y0 + (30 - w) / 2, 5)))
export([("plate", plate), ("blockA", block(10, 0)), ("blockB", block(12, 100)), ("ball", Part.makeSphere(8, V(0, 100, 0)))], "cache/test.step")
# negative case: hole R5 with a different solid (R3 plug) already inside -> the peg must be rejected (overlap)
blocked = Part.makeBox(40, 40, 10).cut(Part.makeCylinder(5, 10, V(20, 20, 0)))
export([("plate", blocked), ("plug", Part.makeCylinder(3, 10, V(20, 20, 0)))], "cache/test_blocked.step")
# cone seat: plug (cone r5->3, h10) and a block with a matching conical socket 40 mm away, apex-up
plug = Part.makeCone(5, 3, 10)
socket = Part.makeBox(30, 30, 20, V(100, 0, 0)).cut(Part.makeCone(5, 3, 10, V(115, 15, 4)))
export([("plug", plug)], "cache/plug.step"); export([("socket", socket)], "cache/test_cone.step")
# torus: ring (major 10, minor 2) and a block with a matching toroidal void
export([("ring", Part.makeTorus(10, 2))], "cache/ring.step")
export([("block", Part.makeBox(40, 40, 10, V(300, 0, 0)).cut(Part.makeTorus(10, 2, V(320, 20, 5)))), ("block_small_groove", Part.makeBox(40, 40, 10, V(400, 0, 0)).cut(Part.makeTorus(10, 1, V(420, 20, 5))))], "cache/test_torus.step")
# freeform: ellipsoid knob (semi-axes 8,8,12) vs blocks with an enclosed ellipsoidal void, rotated 40 deg about X
def ellipsoid(rz, centre, rot=0):
    m = FreeCAD.Matrix(); m.scale(1, 1, rz / 8)
    e = Part.makeSphere(8).transformGeometry(m)
    e.rotate(V(0, 0, 0), V(1, 0, 0), rot); e.translate(centre); return e
export([("knob", ellipsoid(12, V(0, 0, 0)))], "cache/knob.step")
export([("blockMatch", Part.makeBox(60, 60, 60, V(500, 0, 0)).cut(ellipsoid(12, V(530, 30, 30), 40))),
        ("blockWrong", Part.makeBox(60, 60, 60, V(600, 0, 0)).cut(ellipsoid(9.6, V(630, 30, 30), 40)))], "cache/test_freeform.step")
# sliding fit: key (10 wide) vs slots 10.4 (clearance, must match) and 9.6 (too narrow, must not)
export([("slot_loose", block(10.4, 0)), ("slot_tight", block(9.6, 100))], "cache/test_clearance.step")
