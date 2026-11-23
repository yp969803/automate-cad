import Import, FreeCAD, collections, time
t=time.time()
d=FreeCAD.newDocument("a")
Import.insert("/home/yash/automate-cad/stepfile/Redraw.step","a")
objs=[o for o in d.Objects if hasattr(o,"Shape") and not o.Shape.isNull() and o.Shape.Faces]
c=collections.Counter(); n=0
for o in objs:
    for f in o.Shape.Faces:
        c[type(f.Surface).__name__]+=1; n+=1
print("PROBE objects",len(d.Objects),"shapes",len(objs),"faces",n,dict(c),"secs",round(time.time()-t))
