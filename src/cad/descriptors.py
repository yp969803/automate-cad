"""Load a STEP assembly in FreeCAD and dump one descriptor per face (global coords) to JSON.
Run (any STEP file): freecad.cmd -c "import sys; sys.path.insert(0,'src/cad'); import descriptors; descriptors.run('in.step','out.json')"
"""
import sys, json, math, time, collections
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
    e1 = np.cross(a, [1, 0, 0])
    if np.linalg.norm(e1) < .1: e1 = np.cross(a, [0, 1, 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(a, e1)
    xy = np.c_[P @ e1, P @ e2]
    A = np.c_[2 * xy, np.ones(len(xy))]; b = (xy ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]; r2 = x[2] + x[:2] @ x[:2]
    if r2 <= 0: return None
    r = math.sqrt(r2); c = x[0] * e1 + x[1] * e2
    return c, a, r, np.abs(np.linalg.norm(xy - x[:2], axis=1) - r).max()

def samples(f, k=7, normals=True):
    u0, u1, v0, v1 = f.ParameterRange; P = []; N = []
    for u in np.linspace(u0, u1, k):
        for v in np.linspace(v0, v1, k):
            P.append(list(f.valueAt(u, v)))
            if normals: N.append(list(f.normalAt(u, v)))
    return np.array(P), np.array(N)

def classify_bspline(f):
    """Return analytic descriptor fields if the B-spline is really a plane/sphere/cylinder, else None."""
    try: P, N = samples(f)
    except Exception: return None  # no normal at a singular point: leave the face as it is
    c, n, e = fit_plane(P)
    if e < TOL: return dict(type="Plane", point=c.tolist(), axis=n.tolist())
    s = fit_sphere(P)
    if s and s[2] < TOL: return dict(type="Sphere", point=s[0].tolist(), radius=s[1])
    cy = fit_cyl(P, N)
    if cy and cy[3] < TOL: return dict(type="Cylinder", point=cy[0].tolist(), axis=cy[1].tolist(), radius=cy[2])
    return None

def is_convex(nm, pm, point, axis=None):
    """Outward normal `nm` at `pm` points away from the axis line (or the center point if axis is None)."""
    rel = np.array(pm) - np.array(point)
    if axis is not None: ax = np.array(axis); rel = rel - (rel @ ax) * ax
    return bool(np.array(nm) @ rel > 0)

def describe(f):
    """Descriptor of one face; `convex` = outward normal points away from axis/center (None if n/a)."""
    sf = f.Surface; t = type(sf).__name__; d = dict(type=t, area=f.Area)
    u0, u1, v0, v1 = f.ParameterRange; um, vm = (u0 + u1) / 2, (v0 + v1) / 2
    nm = f.normalAt(um, vm); pm = f.valueAt(um, vm)
    d["mid"] = list(pm); d["normal"] = list(nm)  # outward normal at a mid point
    if t == "Plane":
        d.update(point=list(sf.Position), axis=list(nm))
    elif t in ("Cylinder", "Cone"):
        d.update(point=list(sf.Center), axis=list(sf.Axis), convex=is_convex(nm, pm, sf.Center, sf.Axis))
        if t == "Cylinder": d["radius"] = sf.Radius
        else:
            P = samples(f, normals=False)[0]  # slant distance from the apex is monotonic along a cone, so the edges give the band
            dist = np.linalg.norm(P - np.array(sf.Apex), axis=1)
            d.update(semi_angle=sf.SemiAngle, apex=list(sf.Apex), slant=[dist.min(), dist.max()])
    elif t == "Sphere":
        d.update(point=list(sf.Center), radius=sf.Radius, convex=is_convex(nm, pm, sf.Center))
    elif t == "Toroid":
        rel = np.array(pm) - np.array(sf.Center); ax = np.array(sf.Axis); rp = rel - (rel @ ax) * ax
        tube = np.array(sf.Center) + sf.MajorRadius * rp / max(np.linalg.norm(rp), 1e-9)  # centre of the tube circle under pm
        d.update(point=list(sf.Center), apex=list(sf.Center), axis=list(sf.Axis), major=sf.MajorRadius, minor=sf.MinorRadius,
                 convex=is_convex(nm, pm, tube))  # `apex` = the point that pins position, like a cone apex
    elif t in ("BSplineSurface", "SurfaceOfExtrusion"):
        r = classify_bspline(f)  # extrusions of a line/arc are really planes/cylinders; true extrusions stay freeform
        if r:
            d["was"] = t; d.update(r)
            if r["type"] != "Plane": d["convex"] = is_convex(nm, pm, r["point"], r.get("axis"))
    bb = f.BoundBox; d["bbox"] = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    return d

def same_surface(a, b):
    """True if descriptors a, b lie on one analytic surface with the same material side."""
    if a["type"] != b["type"] or a["type"] not in ("Plane", "Cylinder", "Cone", "Sphere", "Toroid"): return False
    pa, pb, t = np.array(a["point"]), np.array(b["point"]), a["type"]
    if t == "Plane":
        na, nb = np.array(a["axis"]), np.array(b["axis"])
        return na @ nb > 1 - 1e-6 and abs((pb - pa) @ na) < TOL
    if a["convex"] != b["convex"]: return False
    if t == "Sphere": return np.linalg.norm(pb - pa) < TOL and abs(a["radius"] - b["radius"]) < TOL
    ua, ub = np.array(a["axis"]), np.array(b["axis"]); d = pb - pa
    if t == "Toroid": return np.linalg.norm(d) < TOL and abs(abs(ua @ ub) - 1) < 1e-6 and abs(a["major"] - b["major"]) < TOL and abs(a["minor"] - b["minor"]) < TOL
    if abs(abs(ua @ ub) - 1) > 1e-6 or np.linalg.norm(d - (d @ ua) * ua) > TOL: return False
    return abs(a["radius"] - b["radius"]) < TOL if t == "Cylinder" else abs(a["semi_angle"] - b["semi_angle"]) < 1e-6

def merge_faces(shape, descs):
    """Join faces that share an edge and lie on the same surface (CAD exporters split cylinders/planes arbitrarily).
    Result: one descriptor per merged face, `ids` = all original face ids, `id` = the first."""
    parent = list(range(len(descs)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    by_edge = {}
    for i, f in enumerate(shape.Faces):
        for e in f.Edges: by_edge.setdefault(e.hashCode(), []).append(i)
    for fs in by_edge.values():
        for i, j in zip(fs, fs[1:]):
            if same_surface(descs[i], descs[j]): parent[find(j)] = find(i)
    groups = {}
    for i in range(len(descs)): groups.setdefault(find(i), []).append(i)
    out = []
    for g in groups.values():
        d = dict(descs[g[0]]); d["ids"] = [descs[i]["id"] for i in g]; d["area"] = sum(descs[i]["area"] for i in g)
        bb = np.array([descs[i]["bbox"] for i in g]); d["bbox"] = np.r_[bb[:, :3].min(0), bb[:, 3:].max(0)].tolist()
        if "slant" in d: d["slant"] = [min(descs[i]["slant"][0] for i in g), max(descs[i]["slant"][1] for i in g)]
        out.append(d)
    return sorted(out, key=lambda d: d["id"])

def has_faces(o):
    return o.isDerivedFrom("Part::Feature") and not o.Shape.isNull() and bool(o.Shape.Faces)

def load(path):
    """Leaf parts = objects with faces whose own children carry no faces (containers repeat their children's faces)."""
    doc = FreeCAD.newDocument("a"); Import.insert(path, doc.Name)  # doc.Name is unique per load
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
        descs = [dict(id=i + 1, **describe(f)) for i, f in enumerate(s.Faces)]
        res.append(dict(part=part_path(o), name=o.Name, faces=merge_faces(s, descs)))
    json.dump(res, open(out, "w"))
    c = collections.Counter(f["type"] for p in res for f in p["faces"]); rec = sum(1 for p in res for f in p["faces"] if "was" in f)
    print("DESC parts", len(res), "merged faces", sum(c.values()), dict(c), "reclassified", rec, "secs", round(time.time() - t0))
