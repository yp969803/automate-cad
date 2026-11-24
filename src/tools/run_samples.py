"""Run every test case, check the verified matches against the expected answer, and save the outputs to assets/.
  .venv/bin/python src/tools/run_samples.py            # the generated samples (about 3 minutes)
  .venv/bin/python src/tools/run_samples.py --lathe    # also the real chuck key on stepfile/Redraw.step (about 5 more minutes)
Per case it writes assets/<case>/matches.json (verified matches: face ids, placement, fit, gap), highlight.html (interactive
viewer, needs internet for three.js) and highlight.png (screenshot, needs google-chrome); assets/README.md summarises all.
Exit status 1 if any case differs from its expectation (a missing match or a match on a decoy)."""
import collections, json, os, shutil, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAMPLES = json.load(open(os.path.join(ROOT, "stepfile", "samples.json")))
S = lambda case, key="select": SAMPLES[case][key]
# name, part file, selected faces, assembly file, expected number of matches per part (parts not listed must have none)
CASES = [
    ("chuck_key", "chuck_key_part", S("chuck_key"), "chuck_key_assembly", {"chuck": 4, "blank_exact": 1}),
    ("vice_jaw", "vice_jaw_part", S("vice_jaw"), "vice_assembly", {"body": 1}),
    ("pin_plate", "pin_plate_part", S("pin_plate"), "pin_plate_assembly", {"plate": 4, "washer": 1, "dowel_plate": 2}),
    ("keyed_shaft_sides_bottom", "keyed_shaft_part", S("keyed_shaft"), "keyed_shaft_assembly", {"shaft_a": 1, "shaft_b": 1, "hub": 1}),
    ("keyed_shaft_sides_top", "keyed_shaft_part", S("keyed_shaft", "select_hub"), "keyed_shaft_assembly", {"shaft_a": 1, "shaft_b": 1, "hub": 1}),
    ("pulley_shaft", "pulley_shaft_part", S("pulley_shaft"), "pulley_shaft_assembly", {"motor": 1, "countershaft": 1}),
    ("pulley_belt", "pulley_belt_part", S("pulley_belt"), "pulley_belt_assembly", {"v_belt": 1}),
    ("freeform_dome", "freeform_dome_part", S("freeform_dome"), "freeform_dome_assembly", {"housing": 2}),
]
LATHE = ("lathe_chuck_key", "lathe_key_part", [2, 4, 16, 18], "Redraw", {"Pinion M1.8 10T": 1, "Pinion M1.8 10T001": 1, "Pinion M1.8 10T002": 1})

def screenshot(html, png):
    cmd = ["google-chrome", "--headless=new", "--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--window-size=1300,800", "--virtual-time-budget=20000", f"--screenshot={png}", "file://" + html]
    try: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    except (OSError, subprocess.TimeoutExpired): print("   (no screenshot: google-chrome not available)")

def views(name, part_file, ids, asm_file, out):
    """Screenshots of the selected part and of the whole assembly (meshes made in FreeCAD, rendered like the highlight)."""
    cad = os.path.join(ROOT, "src", "cad"); prefix = os.path.join(ROOT, "cache", "views_" + name)
    code = f"import sys; sys.path.insert(0,{cad!r}); import highlight; highlight.views({part_file!r},{asm_file!r},{ids!r},{prefix!r})"
    subprocess.run(["freecad.cmd", "-c", code], check=True, stdout=subprocess.DEVNULL)
    for v in ("part", "assembly"):
        screenshot(f"{prefix}_{v}.html", os.path.join(out, v + ".png")); os.remove(f"{prefix}_{v}.html")  # the pages can be large: keep only the pictures

def run_case(name, part, ids, asm, expected):
    out = os.path.join(ROOT, "assets", name); os.makedirs(out, exist_ok=True); t0 = time.time()
    asm_file = os.path.join(ROOT, "stepfile", asm + ".step")
    cmd = [sys.executable, os.path.join(ROOT, "src", "search", "match.py"), os.path.join(ROOT, "stepfile", part + ".step"),
           ",".join(map(str, ids)), asm_file, os.path.join(out, "matches.json")]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"match.py failed for {name}:\n" + (r.stderr or r.stdout)[-2000:])
    res = json.load(open(os.path.join(out, "matches.json")))
    if res:
        shutil.copy(os.path.join(ROOT, "cache", "highlight.html"), os.path.join(out, "highlight.html")); screenshot(os.path.join(out, "highlight.html"), os.path.join(out, "highlight.png"))
    views(name, os.path.join(ROOT, "stepfile", part + ".step"), ids, asm_file, out)
    got = dict(collections.Counter(m["part"].split("/")[-1] for m in res))
    return dict(name=name, ids=ids, expected=expected, got=got, ok=got == expected, secs=round(time.time() - t0), res=res)

def describe(r):
    lines = []
    for m in r["res"]:
        p = m["poses"][0]; faces = ", ".join(f"{k} -> {v}" for k, v in m["faces"].items())
        lines.append(f"- `{m['part'].split('/')[-1]}`: matched faces {faces}; **{p.get('fit', '')}**, gap {p['gap']:.2f} mm, {p['joint']}; {len(m['poses'])} pose(s)")
    return "\n".join(lines) or "- (no verified match)"

if __name__ == "__main__":
    cases = CASES + ([LATHE] if "--lathe" in sys.argv else [])
    results = []
    for c in cases:
        print(f"running {c[0]} ...", flush=True); r = run_case(*c); results.append(r)
        print(f"   {'OK  ' if r['ok'] else 'FAIL'} matches per part {r['got']} (expected {r['expected']}) in {r['secs']} s", flush=True)
    md = ["# Outputs for each test assembly", "",
          "Generated by `src/tools/run_samples.py`. Each folder has `part.png` (the selected part, selected faces in green), `assembly.png` (the whole assembly, one colour per part), `highlight.png` (the matches), `matches.json` (all verified matches with face ids, placement, fit class, gap) and `highlight.html` (interactive viewer).",
          "Highlight colours: grey = part holding the match, red = matched faces, blue = the selected part placed there, green = its selected faces.", "",
          "| Case | Selected faces | Matches per part | Check |", "|---|---|---|---|"]
    md += [f"| [{r['name']}](#{r['name']}) | {r['ids']} | {r['got']} | {'as expected' if r['ok'] else 'DIFFERS from ' + str(r['expected'])} |" for r in results]
    for r in results:
        md += ["", f"## {r['name']}", "", f"Selected faces: {r['ids']}. Time: {r['secs']} s.", "", describe(r), "",
               "| Selected part | Assembly | Highlighted matches |", "|---|---|---|",
               " | ".join(f"![{v}]({r['name']}/{v}.png)" for v in ("part", "assembly", "highlight")).join(["| ", " |"])]
    open(os.path.join(ROOT, "assets", "README.md"), "w").write("\n".join(md) + "\n")
    print("failed:", [r["name"] for r in results if not r["ok"]] or "none")
    sys.exit(0 if all(r["ok"] for r in results) else 1)
