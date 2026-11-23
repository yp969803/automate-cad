"""Colour the highlight objects and export a coloured STEP (needs FreeCAD's GUI classes, run offscreen).
Run: HL_PREFIX=cache/highlight QT_QPA_PLATFORM=offscreen freecad src/cad/color_step.py
Opens <prefix>.FCStd (written by highlight.py), colours it, saves it again and writes <prefix>.step.
Colours: grey = part holding the match, red = matched faces, blue = placed part, green = its selected faces."""
import glob, os, traceback
prefix = os.environ["HL_PREFIX"]; log = open(prefix + ".colour.log", "w")
COLORS = [("host_", (0.6, 0.6, 0.6)), ("_faces", (0.88, 0.19, 0.19)), ("_selected", (0.13, 0.69, 0.31)), ("_part", (0.19, 0.44, 0.88))]
try:
    import FreeCAD, FreeCADGui, ImportGui
    doc = FreeCAD.openDocument(prefix + ".FCStd"); FreeCADGui.updateGui()
    for o in doc.Objects:
        for key, rgb in COLORS:
            if o.ViewObject and (o.Name.startswith(key) or o.Name.endswith(key)): o.ViewObject.ShapeColor = rgb; break
    ImportGui.export(doc.Objects, prefix + ".step"); doc.save(); log.write("ok\n"); [os.remove(f) for f in glob.glob(prefix + ".*.FCBak")]  # saving leaves a backup
except Exception: log.write(traceback.format_exc())
log.close(); os._exit(0)  # the GUI event loop would otherwise keep running
