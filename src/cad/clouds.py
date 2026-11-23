"""Sample surface points + outward normals (runs inside freecad.cmd) for the freeform fallback.
Writes an .npz with the selected faces' cloud and one cloud per candidate assembly part (with the face id of each point)."""
import json
import numpy as np
import FreeCAD
import descriptors, verify

rng = np.random.default_rng(0)  # fixed seed: same clouds every run
POINTS_PER_PART = 60000  # shortcut: big parts are sampled more coarsely so alignment stays tractable

def sample_face(f, h):
    verts, tris = f.tessellate(max(h / 4, 1e-3))  # shortcut: deflection h/4 is fine, the match tolerance is 1.5h
    if not tris: return np.zeros((0, 3)), np.zeros((0, 3))
    V = np.array([[v.x, v.y, v.z] for v in verts]); T = np.array(tris)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]; cr = np.cross(b - a, c - a); A = np.linalg.norm(cr, axis=1) / 2
    n = cr / np.maximum(2 * A, 1e-12)[:, None]; i0 = int(A.argmax())  # FreeCAD winds triangles outward (checked on 150 faces)
    want = A / h ** 2; cnt = np.floor(want).astype(int) + (rng.random(len(T)) < want % 1)  # random rounding keeps the point budget
    if cnt.sum() == 0: cnt[i0] = 1
    idx = np.repeat(np.arange(len(T)), cnt)
    r1, r2 = np.sqrt(rng.random(len(idx))), rng.random(len(idx))
    P = (1 - r1)[:, None] * a[idx] + (r1 * (1 - r2))[:, None] * b[idx] + (r1 * r2)[:, None] * c[idx]
    return P, n[idx]

def cloud(shape, ids, h):
    ps, ns, fs = [], [], []; faces = shape.Faces  # `shape.Faces` rebuilds the list on every access: fetch it once
    for i in ids:
        P, N = sample_face(faces[i - 1], h); ps.append(P); ns.append(N); fs.append(np.full(len(P), i))
    return np.vstack(ps), np.vstack(ns), np.concatenate(fs)

def run(part_step, asm_step, ids, h, diag, out):
    part = verify.shape_of(descriptors.load(part_step)[1][0])
    sp, sn, _ = cloud(part, ids, h); data = dict(sel_pts=sp, sel_nrm=sn); meta = []
    for o in descriptors.load(asm_step)[1]:
        s = verify.shape_of(o)
        if verify.same_instance(s, part) or s.BoundBox.DiagonalLength < 0.9 * diag: continue  # the part itself / too small to hold the selection
        hp = max(h, (sum(f.Area for f in s.Faces) / POINTS_PER_PART) ** 0.5)
        P, N, F = cloud(s, range(1, len(s.Faces) + 1), hp); k = len(meta)
        data.update({f"p{k}_pts": P, f"p{k}_nrm": N, f"p{k}_fid": F}); meta.append(dict(name=o.Name, part=descriptors.part_path(o), h=hp))
    np.savez_compressed(out, meta=json.dumps(meta), **data)
