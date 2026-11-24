# Auto-mating in an assembly

Given a part (STEP) with selected faces and an assembly (STEP), find every place in the assembly where those faces mate, and highlight them.

## Requirements
- Linux with FreeCAD 1.1 from snap (`freecad.cmd` and `freecad` on the PATH): `sudo snap install freecad`
- Python 3.10+
- Optional: `google-chrome` (screenshots in `run_samples.py`)

Keep STEP files in your home folder: the FreeCAD snap cannot read `/tmp`.

## Setup
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run one search
```bash
.venv/bin/python src/search/match.py <part.step> <face ids> <assembly.step> [out.json]
```
Example:
```bash
.venv/bin/python src/search/match.py stepfile/chuck_key_part.step 1,2,6,8 stepfile/chuck_key_assembly.step
```
- Face ids are FreeCAD face numbers of the part (`Face6` is `6`), comma separated.
- The first run on a file caches its descriptors in `cache/` (seconds; 1 to 2 minutes for a 22 MB assembly).
- Output: the matches on the console, `out.json` (default `cache/matches.json`), and `cache/highlight.html` (open in a browser), `cache/highlight.step` and `cache/highlight.FCStd`.
- `--no-verify` skips the geometry check and the highlight files.

## Run all test cases
```bash
.venv/bin/python src/tools/run_samples.py            # 8 generated cases, about 2 minutes
.venv/bin/python src/tools/run_samples.py --lathe    # plus the real lathe chuck key (needs stepfile/Redraw.step)
```
Each result is checked against its expected answer; outputs and screenshots go to `assets/<case>/`, summary in `assets/README.md`. The sample STEP files and their face ids are in `stepfile/` (regenerate: `freecad.cmd -c "exec(open('src/tools/make_samples.py').read())"`).

More: [docs/plan.md](docs/plan.md).
