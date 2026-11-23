"""Save one leaf part of an assembly (by object name, from the descriptor JSON) as its own STEP, in world placement.
Usage (freecad.cmd): extract_part.run('asm.step', 'Part__Feature036', 'out.step')"""
import FreeCAD, Import, Part
import descriptors

def run(src, name, out):
    doc, leaves = descriptors.load(src)
    o = next(l for l in leaves if l.Name == name)
    s = o.Shape.copy(); s.Placement = o.getGlobalPlacement()
    d = FreeCAD.newDocument("x"); d.addObject("Part::Feature", "part").Shape = s
    Import.export([d.Objects[0]], out)
