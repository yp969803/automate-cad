"""Make test STEP files with known answers (run with freecad.cmd).
cache/peg.step      : peg R5            -> select face 1 (cylinder)
cache/key.step      : 10mm cube         -> select faces 1,2 (two opposite planes)
cache/test.step     : assembly: plate with holes R5, R5.05, R8 ; block A with 10mm slot ; block B with 12mm slot ; ball
Expected: peg face 1 -> plate holes R5 and R5.05 (2 matches, not R8); key faces 1,2 -> slot in block A only.
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
