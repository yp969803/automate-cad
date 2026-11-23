"""Find where selected faces of a part mate in an assembly.
Usage: python3 src/search/match.py part.(step|json) 1,2,3 assembly.(step|json) [out.json]
STEP inputs are converted to descriptor JSON with FreeCAD (src/cad/descriptors.py).
Matching = complementary faces (opposite normals, convex<->concave, same size) that keep the
selection's pairwise relations (angles, offsets, axis distances) on ONE part. Pose + verify: not yet.
"""
import sys, os, json, itertools, subprocess
import numpy as np

CAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cad")  # modules that run inside freecad.cmd
ANG = 0.0175   # ~1 deg, on dot products
DIST = 0.1     # mm
CLEAR = 0.02   # radius clearance, 2%

def to_json(p):
    if p.endswith(".json"): return p
    out = "cache/" + os.path.basename(p) + ".json"
    if not os.path.exists(out) or os.path.getmtime(out) < max(os.path.getmtime(p), os.path.getmtime(os.path.join(CAD, "descriptors.py"))):
        subprocess.run(["freecad.cmd", "-c", f"import sys; sys.path.insert(0,{CAD!r}); import descriptors; descriptors.run({p!r},{out!r})"], check=True, stdout=subprocess.DEVNULL)
    return out

def kind(f):  # geometric role used by pair invariants
    t = f["type"]
    return "P" if t == "Plane" else "S" if t == "Sphere" else "L" if t in ("Cylinder", "Cone", "Toroid") else "F" if t in ("BSplineSurface", "SurfaceOfExtrusion") else None

def vec(f, k): return np.array(f[k])

def complementary(s, c):
    if s["type"] != c["type"] or kind(s) in (None, "F"): return False  # freeform faces go through freeform.py
    if s["type"] == "Plane": return True  # facing is checked by the pair relations: the part is not in place yet
    if s["convex"] == c["convex"]: return False
    if s["type"] == "Toroid": return all(abs(s[k] - c[k]) <= CLEAR * s[k] + 1e-6 for k in ("major", "minor"))
    if s["type"] in ("Cylinder", "Sphere"): return abs(s["radius"] - c["radius"]) <= CLEAR * s["radius"] + 1e-6
    if s["type"] == "Cone": return abs(abs(s["semi_angle"]) - abs(c["semi_angle"])) < ANG and \
        s["slant"][0] <= c["slant"][1] + DIST and c["slant"][0] <= s["slant"][1] + DIST  # angle sign = axis direction; bands from the apex must overlap
    return False

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

def unit(v): v = np.asarray(v, float); return v / np.linalg.norm(v)

def center(fs):
    bb = np.array([f["bbox"] for f in fs]); return (bb[:, :3].min(0) + bb[:, 3:].max(0)) / 2

def rotation(S, C):
    """Proper rotation R with R s ~ c for unit vector pairs, and the rotational freedom left (0, 1 or 3 axes)."""
    if not S: return np.eye(3), 3
    u, sv, vt = np.linalg.svd(np.array(S).T @ np.array(C))
    if sv[1] > 0.05 * sv[0]:
        d = np.sign(np.linalg.det(vt.T @ u.T)); return vt.T @ np.diag([1, 1, d]) @ u.T, 0
    a, b = S[0], C[0]; v = np.cross(a, b); c = a @ b
    if np.linalg.norm(v) < 1e-9:  # parallel or antiparallel
        if c > 0: return np.eye(3), 1
        p = unit(np.cross(a, [1, 0, 0] if abs(a[0]) < .9 else [0, 1, 0])); return 2 * np.outer(p, p) - np.eye(3), 1
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c), 1

LABEL = {(0, 0): "fixed", (0, 1): "slides along one axis", (1, 0): "revolute (spins)", (1, 1): "cylindrical (spins and slides)",
         (1, 2): "planar (slides in a plane, spins)", (3, 0): "ball (any rotation)"}

def poses(sel, cands):
    """Rigid motions (part -> assembly) that put sel faces onto cands faces, facing each other. Axis directions
    have no sign, so every sign choice is tried and the inconsistent ones drop out. Free motion is left centred.
    A cone seat is fixed by making the two apexes coincide (same angle => surfaces coincide), so depth is not free.
    shortcut: sphere-only fits leave rotation free (identity)."""
    lines = [i for i, f in enumerate(sel) if kind(f) == "L"]; out, seen = [], set()
    for signs in itertools.product([1, -1], repeat=len(lines)):
        sg = dict(zip(lines, signs)); S, C = [], []
        for i, (a, c) in enumerate(zip(sel, cands)):
            if kind(a) == "P": S.append(unit(a["axis"])); C.append(-unit(c["axis"]))
            elif kind(a) == "L": S.append(unit(a["axis"])); C.append(sg[i] * unit(c["axis"]))
        R, nr = rotation(S, C)
        if any(np.linalg.norm(R @ x - y) > 0.03 for x, y in zip(S, C)): continue
        rows, rhs = [], []
        for a, c in zip(sel, cands):
            ps, pc = vec(a, "point"), vec(c, "point"); k = kind(a)
            if k == "P": n = unit(c["axis"]); rows.append(n[None]); rhs.append([n @ (pc - R @ ps)])
            elif k == "L" and "apex" in a: rows.append(np.eye(3)); rhs.append(vec(c, "apex") - R @ vec(a, "apex"))
            elif k == "L": u = unit(c["axis"]); Pm = np.eye(3) - np.outer(u, u); rows.append(Pm); rhs.append(Pm @ (pc - R @ ps))
            else: rows.append(np.eye(3)); rhs.append(pc - R @ ps)
        A, b = np.vstack(rows), np.concatenate(rhs)
        t = np.linalg.lstsq(A, b, rcond=None)[0]
        if np.abs(A @ t - b).max() > DIST: continue
        _, sv, vt = np.linalg.svd(A); N = vt[(sv > 1e-6).sum():]  # N: directions the constraints leave free
        t = t + N.T @ (N @ (center(cands) - R @ center(sel) - t))  # centre the selection on the match along free directions
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t
        key = tuple(np.round(M, 3).ravel())
        if key not in seen: seen.add(key); out.append(dict(matrix=M.tolist(), free=[nr, len(N)], joint=LABEL.get((nr, len(N)), f"{nr} rotation / {len(N)} translation free")))
    return out

def run(part, ids, assembly):
    P = json.load(open(to_json(part)))[0]; A = json.load(open(to_json(assembly)))
    sel = []  # selected ids -> merged faces (a selection may hit several pieces of one merged face)
    for i in ids:
        g = next((f for f in P["faces"] if i in f["ids"]), None)
        if g is None: raise SystemExit(f"Face {i} not found in the part")
        if g not in sel: sel.append(g)
    for s in sel:
        if kind(s) is None: raise SystemExit(f"Face {s['id']} is {s['type']}: no matching rule for this surface type yet")
    if any(kind(s) == "F" for s in sel):  # freeform face selected: align point clouds instead of comparing surface types
        if not (part.endswith((".step", ".stp")) and assembly.endswith((".step", ".stp"))): raise SystemExit("freeform fallback needs STEP inputs")
        import freeform
        return freeform.find(part, assembly, sel, same_part, P)
    gap = DIST + CLEAR * max([s.get("radius", 0) for s in sel])  # contact tolerance used by verify
    res = []
    for q in A:
        if same_part(P, q): continue  # the selected part itself
        seen = set(); byid = {f["id"]: f for f in q["faces"]}
        for m in search(sel, q["faces"]):
            if frozenset(m) in seen: continue  # symmetric fits (e.g. 4 rotations) share one face set
            seen.add(frozenset(m)); cands = [byid[c] for c in m]; ps = poses(sel, cands)
            if ps: res.append(dict(part=q["part"], object=q["name"], faces={str(s["id"]): c["ids"] for s, c in zip(sel, cands)},
                                   sel={str(s["id"]): s["ids"] for s in sel}, gap_tol=gap, poses=ps))
    return res

def verify(part, assembly, cand, out, hl):
    subprocess.run(["freecad.cmd", "-c", f"import sys; sys.path.insert(0,{CAD!r}); import verify; verify.run({part!r},{assembly!r},{cand!r},{out!r},{hl!r})"], check=True, stdout=subprocess.DEVNULL)
    return json.load(open(out))

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; part, ids, asm = args[0], [int(x) for x in args[1].split(",")], args[2]
    out = args[3] if len(args) > 3 else "cache/matches.json"
    cand = run(part, ids, asm); json.dump(cand, open("cache/candidates.json", "w"))
    print(f"{len(cand)} candidate(s) by face relations for faces {ids}")
    res = cand
    if "--no-verify" not in sys.argv and cand:  # nothing to verify -> don't load the assembly in FreeCAD
        if not (part.endswith((".step", ".stp")) and asm.endswith((".step", ".stp"))): raise SystemExit("verify needs STEP inputs (use --no-verify for JSON)")
        hl = "cache/highlight"; res = verify(part, asm, "cache/candidates.json", out, hl); print(f"{len(res)} verified (placed part touches the match and does not overlap the assembly)")
    else: json.dump(res, open(out, "w"), indent=1)  # --no-verify, or no candidates
    if res and "--no-verify" not in sys.argv:
        subprocess.run(["freecad", os.path.join(CAD, "color_step.py")], env=dict(os.environ, QT_QPA_PLATFORM="offscreen", HL_PREFIX=hl),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)  # coloured STEP needs the GUI classes
        print(f"highlight: {hl}.html (browser), {hl}.FCStd and {hl}.step" + (" (coloured)" if os.path.exists(hl + ".step") else " missing: see " + hl + ".colour.log"))
    for r in res:
        for p in r["poses"]: print(" ", r["part"], r["faces"], "|", p["joint"], "|", "gap", round(p["gap"], 3), "overlap", "n/a (open shell)" if p["overlap"] is None else round(p["overlap"], 3))
