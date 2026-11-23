"""Load a STEP assembly in FreeCAD and dump one descriptor per face (global coords) to JSON.
Run (any STEP file): freecad.cmd -c "import sys; sys.path.insert(0,'src'); import descriptors; descriptors.run('in.step','out.json')"
"""
import sys, json, math, time
import numpy as np
import FreeCAD, Import

TOL = 0.01  # B-spline -> analytic fit residual; run() rescales it to the model size

def fit_plane(P):
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c); n = vt[2]
    return c, n, np.abs((P - c) @ n).max()

def fit_sphere(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]; c = x[:3]; r2 = x[3] + c @ c
    if r2 <= 0: return None
    r = math.sqrt(r2); return c, r, np.abs(np.linalg.norm(P - c, axis=1) - r).max()

def fit_cyl(P, N):
    a = np.linalg.svd(N)[2][2]  # normals are perpendicular to the axis
    e1 = np.cross(a, [1, 0, 0]);
    if np.linalg.norm(e1) < .1: e1 = np.cross(a, [0, 1, 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(a, e1)
    xy = np.c_[P @ e1, P @ e2]
    A = np.c_[2 * xy, np.ones(len(xy))]; b = (xy ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]; r2 = x[2] + x[:2] @ x[:2]
    if r2 <= 0: return None
    r = math.sqrt(r2); c = x[0] * e1 + x[1] * e2
    return c, a, r, np.abs(np.linalg.norm(xy - x[:2], axis=1) - r).max()

def samples(f, k=7):
    u0, u1, v0, v1 = f.ParameterRange; P = []; N = []
    for u in np.linspace(u0, u1, k):
        for v in np.linspace(v0, v1, k):
            P.append(list(f.valueAt(u, v))); N.append(list(f.normalAt(u, v)))
    return np.array(P), np.array(N)

def classify_bspline(f):
    """Return analytic descriptor fields if the B-spline is really a plane/sphere/cylinder, else None."""
    P, N = samples(f)
    c, n, e = fit_plane(P)
    if e < TOL: return dict(type="Plane", point=c.tolist(), axis=n.tolist())
    s = fit_sphere(P)
    if s and s[2] < TOL: return dict(type="Sphere", point=s[0].tolist(), radius=s[1])
    cy = fit_cyl(P, N)
    if cy and cy[3] < TOL: return dict(type="Cylinder", point=cy[0].tolist(), axis=cy[1].tolist(), radius=cy[2])
    return None

def describe(f):
    """Descriptor of one face; `convex` = outward normal points away from axis/center (None if n/a)."""
    sf = f.Surface; t = type(sf).__name__; d = dict(type=t, area=f.Area)
    u0, u1, v0, v1 = f.ParameterRange; um, vm = (u0 + u1) / 2, (v0 + v1) / 2
    nm = f.normalAt(um, vm); pm = f.valueAt(um, vm)
    d["mid"] = list(pm); d["normal"] = list(nm)  # outward normal at a mid point
    if t == "Plane":
        d.update(point=list(sf.Position), axis=list(nm))
    elif t in ("Cylinder", "Cone"):
        ax = np.array(sf.Axis); rel = np.array(pm) - np.array(sf.Center)
        rad = rel - (rel @ ax) * ax
        d.update(point=list(sf.Center), axis=list(sf.Axis), convex=bool(np.array(nm) @ rad > 0))
        d["radius" if t == "Cylinder" else "semi_angle"] = sf.Radius if t == "Cylinder" else sf.SemiAngle
    elif t == "Sphere":
        d.update(point=list(sf.Center), radius=sf.Radius, convex=bool(np.array(nm) @ (np.array(pm) - np.array(sf.Center)) > 0))
    elif t == "Toroid":
        d.update(point=list(sf.Center), axis=list(sf.Axis), major=sf.MajorRadius, minor=sf.MinorRadius)
    elif t in ("BSplineSurface", "SurfaceOfExtrusion"):
        r = classify_bspline(f) if t == "BSplineSurface" else None
        if r:
            d["was"] = t; d.update(r)
            if r["type"] != "Plane":
                rel = np.array(pm) - np.array(r["point"])
                if r["type"] == "Sphere": d["convex"] = bool(np.array(nm) @ rel > 0)
                else:
                    ax = np.array(r["axis"]); rad = rel - (rel @ ax) * ax; d["convex"] = bool(np.array(nm) @ rad > 0)
    bb = f.BoundBox; d["bbox"] = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    return d

def has_faces(o):
    return o.isDerivedFrom("Part::Feature") and not o.Shape.isNull() and bool(o.Shape.Faces)

def load(path):
    """Leaf parts = objects with faces whose own children carry no faces (containers repeat their children's faces)."""
    doc = FreeCAD.newDocument("a"); Import.insert(path, "a")
    return doc, [o for o in doc.Objects if has_faces(o) and not any(has_faces(c) for c in o.OutList)]

def part_path(o):
    names = [];
    while o: names.append(o.Label); o = next((p for p in o.InList if p.TypeId == "App::Part"), None)
    return "/".join(reversed(names))

def run(src, out):
    """Dump descriptors of every face of every leaf part in `src` (any STEP file) to JSON `out`."""
    global TOL; t0 = time.time()
    doc, leaves = load(src); res = []
    diag = max(o.Shape.BoundBox.DiagonalLength for o in doc.Objects if has_faces(o))
    TOL = max(1e-3, 1e-5 * diag)  # scale-relative so mm/m/inch models behave alike
    for o in leaves:
        s = o.Shape.copy(); s.Placement = o.getGlobalPlacement()
        res.append(dict(part=part_path(o), name=o.Name, faces=[dict(id=i + 1, **describe(f)) for i, f in enumerate(s.Faces)]))
    json.dump(res, open(out, "w"))
    import collections
    c = collections.Counter(f["type"] for p in res for f in p["faces"]); rec = sum(1 for p in res for f in p["faces"] if "was" in f)
    print("DESC parts", len(res), "faces", sum(c.values()), dict(c), "reclassified", rec, "secs", round(time.time() - t0))
