"""Check candidate placements with the real geometry (runs inside freecad.cmd).
For each pose: move the part, then require (1) every selected face touches its matched face (gap <= tol, boxes overlap)
and (2) the moved part does not overlap the assembly. Instances identical to the part itself are ignored (a free slot
is judged without them). Poses that fail are dropped; survivors get `gap` and `overlap` added.
shortcut: overlap tolerance is 1% of the part volume; open shells can't be tested (overlap=None, and `open_parts_unchecked` counts
assembly parts skipped); a failed boolean is flagged not rejected."""
import json
import FreeCAD, Part
import descriptors

OVERLAP = 0.01

def shape_of(o):
    s = o.Shape.copy(); s.Placement = o.getGlobalPlacement(); return s

def grown(face, tol):
    bb = FreeCAD.BoundBox(face.BoundBox); bb.enlarge(tol); return bb  # flat faces have zero-thickness boxes

def solid_of(s):
    """A usable solid for booleans, or None for open shells (CATIA exports often leave parts as unclosed shells)."""
    if s.Solids: return s
    return Part.Solid(s.Shells[0]) if len(s.Shells) == 1 and s.Shells[0].isClosed() else None

def same_instance(a, b):
    return len(a.Faces) == len(b.Faces) and abs(abs(a.Volume) - abs(b.Volume)) < 1e-6 * max(1, abs(a.Volume))

def run(part_step, asm_step, cand_json, out_json):
    part = shape_of(descriptors.load(part_step)[1][0])
    shapes = {o.Name: shape_of(o) for o in descriptors.load(asm_step)[1]}
    others = {n: s for n, s in shapes.items() if not same_instance(s, part)}
    solids = {n: solid_of(s) for n, s in others.items()}; open_parts = sum(v is None for v in solids.values())
    res = []
    for m in json.load(open(cand_json)):
        target = shapes[m["object"]]; keep = []
        for p in m["poses"]:
            mat = FreeCAD.Matrix(*[x for row in p["matrix"] for x in row]); moved = part.copy(); moved.transformShape(mat)
            gap = 0.0
            for sid, ids in m["sel"].items():
                sf = [moved.Faces[i - 1] for i in ids]; cf = [target.Faces[i - 1] for i in m["faces"][sid]]
                g = min(a.distToShape(b)[0] for a in sf for b in cf); gap = max(gap, g)
                if g > m["gap_tol"] or not any(grown(a, m["gap_tol"]).intersect(b.BoundBox) for a in sf for b in cf): gap = None; break
            if gap is None: continue
            ms = solid_of(moved); over = None  # None = overlap not checked (the part is an open shell)
            if ms is not None:
                over = 0.0
                for n, s in solids.items():
                    if s is not None and ms.BoundBox.intersect(s.BoundBox):
                        try: over += abs(ms.common(s).Volume)
                        except Exception: p["unchecked"] = True
                if over > OVERLAP * max(abs(ms.Volume), 1e-9): continue
            keep.append(dict(p, gap=gap, overlap=over, open_parts_unchecked=open_parts))
        if keep: res.append(dict(m, poses=keep))
    json.dump(res, open(out_json, "w"), indent=1)
