"""Find where selected faces of a part mate in an assembly.
Usage: python3 src/match.py part.(step|json) 1,2,3 assembly.(step|json) [out.json]
STEP inputs are converted to descriptor JSON with FreeCAD (src/descriptors.py).
Matching = complementary faces (opposite normals, convex<->concave, same size) that keep the
selection's pairwise relations (angles, offsets, axis distances) on ONE part. Pose + verify: not yet.
"""
import sys, os, json, itertools, subprocess
import numpy as np

ANG = 0.0175   # ~1 deg, on dot products
DIST = 0.1     # mm
CLEAR = 0.02   # radius clearance, 2%

def to_json(p):
    if p.endswith(".json"): return p
    out = "cache/" + os.path.basename(p) + ".json"
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(p):
        subprocess.run(["freecad.cmd", "-c", f"import sys; sys.path.insert(0,'src'); import descriptors; descriptors.run({p!r},{out!r})"], check=True, stdout=subprocess.DEVNULL)
    return out

def kind(f):  # geometric role used by pair invariants
    t = f["type"]
    return "P" if t == "Plane" else "S" if t == "Sphere" else "L" if t in ("Cylinder", "Cone", "Toroid") else None

def vec(f, k): return np.array(f[k])

def complementary(s, c):
    if s["type"] != c["type"] or kind(s) is None: return False
    if s["type"] == "Plane": return True  # facing is checked by the pair relations: the part is not in place yet
    if s["type"] == "Toroid" or s["convex"] == c["convex"]: return False  # torus: no rule yet
    if s["type"] in ("Cylinder", "Sphere"): return abs(s["radius"] - c["radius"]) <= CLEAR * s["radius"] + 1e-6
    if s["type"] == "Cone": return abs(s["semi_angle"] - c["semi_angle"]) < ANG
    return False  # Toroid: no rule yet

def inv(a, b):
    """Rotation-invariant relation of faces a,b. Returns (list of values, list of signs): a candidate pair
    must show values*signs; planes flip sign because complementary faces have opposite normals."""
    ka, kb = kind(a), kind(b); pa, pb = vec(a, "point"), vec(b, "point")
    if ka == "P" and kb == "P":
        na, nb = vec(a, "axis"), vec(b, "axis"); dot = na @ nb; v = [dot]
        if abs(abs(dot) - 1) < ANG ** 2: v.append((pb - pa) @ na)  # parallel: offset, flips sign
        return v, [1, -1]
    if ka == "P" or kb == "P":  # plane vs line/point
        if kb == "P": a, b, pa, pb = b, a, pb, pa; ka, kb = kb, ka
        n = vec(a, "axis")
        if kb == "S": return [(pb - pa) @ n], [-1]
        u = vec(b, "axis"); v = [abs(n @ u)]
        if v[0] < ANG: v.append((pb - pa) @ n)
        return v, [1, -1]
    if ka == "S" and kb == "S": return [np.linalg.norm(pb - pa)], [1]
    if ka == "S" or kb == "S":  # point vs line: distance
        if ka == "S": a, b, pa, pb = b, a, pb, pa
        u = vec(a, "axis"); d = pb - pa; return [np.linalg.norm(d - (d @ u) * u)], [1]
    ua, ub = vec(a, "axis"), vec(b, "axis"); c = np.cross(ua, ub); d = pb - pa
    v = [abs(ua @ ub)]
    dist = np.linalg.norm(d - (d @ ua) * ua) if np.linalg.norm(c) < ANG else abs(d @ c) / np.linalg.norm(c)
    return v + [dist], [1, 1]

def pair_ok(sa, sb, ca, cb):
    (v, sg), (w, _) = inv(sa, sb), inv(ca, cb)
    if len(v) != len(w): return False
    return all(abs(x * g - y) <= (ANG if i == 0 else DIST) for i, (x, y, g) in enumerate(zip(v, w, sg + [1] * 9)))

def search(sel, faces):
    """All assignments sel[i] -> faces[j] (one part) with complementary faces and consistent pair relations."""
    cands = [[c for c in faces if complementary(s, c)] for s in sel]
    out = []
    def rec(i, chosen):
        if i == len(sel): out.append(tuple(c["id"] for c in chosen)); return
        for c in cands[i]:
            if all(c["id"] != d["id"] and pair_ok(sel[j], sel[i], d, c) for j, d in enumerate(chosen)): rec(i + 1, chosen + [c])
    rec(0, []); return out

def same_part(p, q):
    return len(p["faces"]) == len(q["faces"]) and abs(sum(f["area"] for f in p["faces"]) - sum(f["area"] for f in q["faces"])) < 1e-6

def run(part, ids, assembly):
    P = json.load(open(to_json(part)))[0]; A = json.load(open(to_json(assembly)))
    sel = [next(f for f in P["faces"] if f["id"] == i) for i in ids]
    for s in sel:
        if kind(s) is None: raise SystemExit(f"Face {s['id']} is {s['type']}: no matching rule for this surface type yet")
    res = []
    for q in A:
        if same_part(P, q): continue  # the selected part itself
        seen = set()
        for m in search(sel, q["faces"]):
            if frozenset(m) in seen: continue  # symmetric fits (e.g. 4 rotations) share one face set
            seen.add(frozenset(m)); res.append(dict(part=q["part"], object=q["name"], faces=dict(zip(map(str, ids), m))))
    return res

if __name__ == "__main__":
    part, ids, asm = sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3]
    res = run(part, ids, asm)
    json.dump(res, open(sys.argv[4] if len(sys.argv) > 4 else "cache/matches.json", "w"), indent=1)
    print(f"{len(res)} match(es) for faces {ids}")
    for r in res: print(" ", r["part"], r["faces"])
