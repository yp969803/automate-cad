"""Freeform fallback: align the selected faces' point cloud onto each candidate part's surface.
Coarse pose from FPFH features + RANSAC, then ICP; accept if most selected points land on the surface facing the
right way. Repeats on the leftover surface to find every instance on a part. Poses are checked later by verify.py.
shortcut: free motion (symmetry/slide) is not analysed, and a seat touched only in a small patch can fail the 85% test."""
import json, os, subprocess
import numpy as np
import open3d as o3d

reg = o3d.pipelines.registration
o3d.utility.random.seed(0)  # RANSAC is random: fixed seed so a rerun gives the same result
CAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cad")  # modules that run inside freecad.cmd
FIT, RMSE, MAX_INSTANCES = 0.85, 0.6, 8  # inlier fraction, rmse in voxels

def pcd(P, N):
    c = o3d.geometry.PointCloud(); c.points = o3d.utility.Vector3dVector(P); c.normals = o3d.utility.Vector3dVector(N); return c

def align(src, tgt, v):
    s, t = src.voxel_down_sample(v), tgt.voxel_down_sample(v); s.normalize_normals(); t.normalize_normals()
    f = lambda c: reg.compute_fpfh_feature(c, o3d.geometry.KDTreeSearchParamHybrid(radius=5 * v, max_nn=100))
    r = reg.registration_ransac_based_on_feature_matching(
        s, t, f(s), f(t), True, 1.5 * v, reg.TransformationEstimationPointToPoint(False), 3,
        [reg.CorrespondenceCheckerBasedOnEdgeLength(0.9), reg.CorrespondenceCheckerBasedOnDistance(1.5 * v)],
        reg.RANSACConvergenceCriteria(200000, 0.999))
    return reg.registration_icp(s, t, v, r.transformation, reg.TransformationEstimationPointToPlane()).transformation

def nearest(A, B, chunk=100):
    """Index and distance of the nearest B point for every A point (brute force, chunked)."""
    b2 = (B ** 2).sum(1); idx = np.empty(len(A), int); d = np.empty(len(A))
    for i in range(0, len(A), chunk):
        a = A[i:i + chunk]; d2 = (a ** 2).sum(1)[:, None] + b2[None] - 2 * a @ B.T
        idx[i:i + chunk] = d2.argmin(1); d[i:i + chunk] = np.sqrt(np.maximum(d2.min(1), 0))
    return idx, d

def instances(sp, sn, P, N, F, v, ids):
    """Poses placing the selection cloud (sp, sn) on the part surface (P, N: normals already flipped to face the selection)."""
    out, alive = [], np.arange(len(P)); sub = np.arange(0, len(sp), max(1, len(sp) // 1500))
    for _ in range(MAX_INSTANCES):
        if len(alive) < 50: break
        T = align(pcd(sp, sn), pcd(P[alive], N[alive]), v); R, t = T[:3, :3], T[:3, 3]
        q = sp[sub] @ R.T + t; idx, d = nearest(q, P[alive]); dot = ((sn[sub] @ R.T) * N[alive][idx]).sum(1)
        ok = (d < 1.5 * v) & (dot > 0.7)
        if ok.mean() < FIT or np.sqrt((d[ok] ** 2).mean()) > RMSE * v: break
        hit = sorted(set(F[alive][idx[ok]].tolist()))
        out.append(dict(matrix=T.tolist(), free=None, joint="freeform fit (aligned by point cloud; free motion not analysed)", faces=hit))
        _, dt = nearest(P[alive], q); alive = alive[dt > 2 * v]  # remove the used surface, look for another instance
    return out

def find(part, assembly, sel, same_part, P0):
    ids = sorted({i for s in sel for i in s["ids"]})
    bb = np.array([s["bbox"] for s in sel]); D = float(np.linalg.norm(bb[:, 3:].max(0) - bb[:, :3].min(0))); h = max(D / 50, 0.05)
    out = "cache/clouds.npz"
    subprocess.run(["freecad.cmd", "-c", f"import sys; sys.path.insert(0,{CAD!r}); import clouds; clouds.run({part!r},{assembly!r},{ids!r},{h!r},{D!r},{out!r})"], check=True, stdout=subprocess.DEVNULL)
    z = np.load(out); meta = json.loads(str(z["meta"])); res = []
    print(f"freeform fallback: {len(ids)} selected face(s), {len(z['sel_pts'])} points, {len(meta)} candidate part(s)")
    for k, m in enumerate(meta):
        for inst in instances(z["sel_pts"], z["sel_nrm"], z[f"p{k}_pts"], -z[f"p{k}_nrm"], z[f"p{k}_fid"], m["h"], ids):
            faces = inst.pop("faces")
            res.append(dict(part=m["part"], object=m["name"], faces={"pc": faces}, sel={"pc": ids}, gap_tol=1.5 * m["h"], poses=[inst]))
    return res
