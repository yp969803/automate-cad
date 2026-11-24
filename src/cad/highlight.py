"""Show verified matches (runs inside freecad.cmd, called by verify.run).
Writes <prefix>.FCStd (host parts, matched faces and the placed part as named objects, for FreeCAD) and
<prefix>.html (standalone three.js viewer with colours and a toggle per match; needs internet for three.js only).
Colours: grey = part holding the match, red = matched faces, blue = selected part placed there, green = its selected faces.
shortcut: command-line FreeCAD cannot colour shapes, so colours exist only in the HTML."""
import json, os
import FreeCAD, Part

COLOR = dict(host=(0x9a9a9a, 0.25), face=(0xe03030, 1.0), part=(0x3070e0, 0.55), sel=(0x20b050, 1.0))

PALETTE = [0x4e79a7, 0xf28e2b, 0x59a14f, 0xb07aa1, 0x76b7b2, 0xedc948, 0xff9da7, 0x9c755f, 0xbab0ac, 0x8cd17d, 0xb6992d, 0x499894]

def mesh(shape, kind, group, label, color=None, opacity=None, detail=200):
    v, t = shape.tessellate(max(shape.BoundBox.DiagonalLength / detail, 0.01))
    color, opacity = (color, opacity) if color is not None else COLOR[kind]
    return dict(kind=kind, g=group, label=label, color=color, opacity=opacity,
                v=[round(c, 3) for p in v for c in (p.x, p.y, p.z)], i=[k for tri in t for k in tri])

def write(part, shapes, res, prefix):
    doc = FreeCAD.newDocument("matches"); meshes, matches, hosts = [], [], set()
    def add(name, shape): doc.addObject("Part::Feature", name).Shape = shape
    for n, m in enumerate(res):
        host = shapes[m["object"]]; tf = host.Faces
        if m["object"] not in hosts:
            hosts.add(m["object"]); add("host_" + m["object"], host); meshes.append(mesh(host, "host", -1, m["part"]))
        ids = sorted({i for v in m["faces"].values() for i in v})
        faces = Part.makeCompound([tf[i - 1] for i in ids]); add(f"match{n}_faces", faces)
        meshes.append(mesh(faces, "face", n, m["part"]))
        for j, p in enumerate(m["poses"]):
            placed = part.copy(); placed.transformShape(FreeCAD.Matrix(*[x for row in p["matrix"] for x in row]))
            sel = Part.makeCompound([placed.Faces[i - 1] for v in m["sel"].values() for i in v])
            add(f"match{n}_pose{j}_part", placed); add(f"match{n}_pose{j}_selected", sel)
            meshes.append(mesh(placed, "part", n, "placed part")); meshes.append(mesh(sel, "sel", n, "selected faces"))
        matches.append(dict(label=f"{m['part']} | faces {sorted(m['faces'].items())} | {m['poses'][0].get('fit', '')} (gap {m['poses'][0].get('gap', 0):.2f} mm) | {m['poses'][0]['joint']}"))
    doc.recompute(); (os.path.exists(prefix + ".FCStd") and os.remove(prefix + ".FCStd")); doc.saveAs(prefix + ".FCStd")  # no .FCBak clutter
    open(prefix + ".html", "w").write(HTML.replace("__DATA__", json.dumps(dict(meshes=meshes, matches=matches))))

def page(meshes, matches, path, title=None, legend=None):
    open(path, "w").write(HTML.replace("__DATA__", json.dumps(dict(meshes=meshes, matches=matches, title=title, legend=legend))))

def views(part_step, asm_step, ids, prefix):
    """Write <prefix>_part.html (the part, selected faces green) and <prefix>_assembly.html (every part in its own colour)."""
    import descriptors, verify
    part = verify.shape_of(descriptors.load(part_step)[1][0]); faces = part.Faces
    sel = Part.makeCompound([faces[i - 1] for i in ids])
    page([mesh(part, "part", 0, "part"), mesh(sel, "sel", 0, "selected faces")], [dict(label=f"selected part, faces {ids}")], prefix + "_part.html",
         "Selected part", "blue: the part - green: the faces to mate")
    leaves = descriptors.load(asm_step)[1]
    page([mesh(verify.shape_of(o), "asm", k, o.Label, PALETTE[k % len(PALETTE)], 0.9, detail=100) for k, o in enumerate(leaves)],
         [dict(label=descriptors.part_path(o)) for o in leaves], prefix + "_assembly.html", "Assembly", f"{len(leaves)} parts, one colour each. Click a line to zoom to a part.")

HTML = """<!doctype html><meta charset="utf-8"><title>Matches</title>
<style>body{margin:0;font:13px sans-serif;display:flex;height:100vh}#side{width:340px;overflow:auto;padding:8px;background:#f4f4f4;color:#222}
#side div{margin:4px 0;cursor:pointer}#v{flex:1}small{color:#666}</style>
<div id="side"><b id="title">Verified matches</b><br><small id="legend">grey: part holding the match - red: matched faces - blue: your part placed - green: its selected faces. Click a line to zoom.</small>
<div id="hostsrow"><label><input type="checkbox" id="hosts" checked> show holding parts</label></div><div id="list"></div></div><div id="v"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const D = __DATA__, el = document.getElementById('v'), groups = {}; let fit = () => {};
function init3d() {
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0xffffff);
  const cam = new THREE.PerspectiveCamera(50, 1, 0.1, 1e6), ren = new THREE.WebGLRenderer({antialias: true}); el.appendChild(ren.domElement);
  const ctl = new THREE.OrbitControls(cam, ren.domElement); scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(1, 2, 3); scene.add(sun);
  D.meshes.forEach(m => {
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(m.v, 3)); g.setIndex(m.i); g.computeVertexNormals(); g.computeBoundingBox();
    const o = new THREE.Mesh(g, new THREE.MeshPhongMaterial({color: m.color, transparent: m.opacity < 1, opacity: m.opacity, side: THREE.DoubleSide, depthWrite: m.opacity >= 1, polygonOffset: true, polygonOffsetFactor: m.kind == 'sel' ? -2 : m.kind == 'face' ? -1 : 0}));
    scene.add(o); (groups[m.g] = groups[m.g] || []).push(o);
  });
  fit = list => { const b = new THREE.Box3(); list.forEach(o => b.union(o.geometry.boundingBox)); const c = b.getCenter(new THREE.Vector3()), r = b.getSize(new THREE.Vector3()).length() || 1;
    ctl.target.copy(c); cam.position.copy(c).add(new THREE.Vector3(1, 0.8, 1).normalize().multiplyScalar(r * 1.2)); cam.near = r / 1000; cam.far = r * 100; cam.updateProjectionMatrix(); ctl.update(); };
  const size = () => { ren.setSize(el.clientWidth, el.clientHeight); cam.aspect = el.clientWidth / el.clientHeight; cam.updateProjectionMatrix(); };
  addEventListener('resize', size); size(); fit(scene.children.filter(x => x.isMesh));
  (function loop() { requestAnimationFrame(loop); ctl.update(); ren.render(scene, cam); })();
}
const list = document.getElementById('list');
D.matches.forEach((m, n) => { const d = document.createElement('div'), c = document.createElement('input'); c.type = 'checkbox'; c.checked = true;
  c.onchange = () => (groups[n] || []).forEach(o => o.visible = c.checked); d.append(c, ' ' + (n + 1) + '. ' + m.label);
  d.onclick = e => { if (e.target !== c) fit(groups[n] || []); }; list.appendChild(d); });
document.getElementById('hosts').onchange = e => (groups[-1] || []).forEach(o => o.visible = e.target.checked);
if (D.title) { document.getElementById('title').textContent = D.title; document.getElementById('legend').textContent = D.legend; document.getElementById('hostsrow').style.display = 'none'; }
try { init3d(); } catch (e) { el.textContent = '3D view unavailable here (' + e.message + '). Open this file in a browser with WebGL; the matches are listed on the left.'; }
</script>"""
