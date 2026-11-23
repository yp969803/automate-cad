import Import, FreeCAD, collections
d=FreeCAD.newDocument("a")
Import.insert("/home/yash/automate-cad/stepfile/Redraw.step","a")
c=collections.Counter(o.TypeId for o in d.Objects)
print("TREE types",dict(c))
roots=[o for o in d.Objects if not o.InList]
print("TREE roots",[(o.Label,o.TypeId) for o in roots][:10])
def show(o,depth=0,maxd=2):
    if depth>maxd: return
    print("TREE"," "*depth*2+o.Label,o.TypeId,len(getattr(o,"Group",[])),"faces",len(o.Shape.Faces) if hasattr(o,"Shape") and not o.Shape.isNull() else "-")
    for ch in getattr(o,"Group",[])[:6]: show(ch,depth+1,maxd)
for r in roots: show(r)
try:
    import numpy; print("TREE numpy",numpy.__version__)
except Exception as e: print("TREE nonumpy",e)
