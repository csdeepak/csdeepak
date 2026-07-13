# Setup — going live

A GitHub **profile README** for [`@csdeepak`](https://github.com/csdeepak). Dark ·
cyan `#42F5FF` · terminal. All hero art is hand-written animated SVG; the portrait
is derived from a real photo (background removal → silhouette → adaptive cyan
shading → selective halftone → edge accents).

---

## 1. Repo name must equal your username ⚠️

A profile README only renders from a repo named **exactly** like your username:

```
github.com/csdeepak/csdeepak
```

Rename this repo (*Settings → General → Rename* → `csdeepak`) or push into a new
**public** repo of that name.

## 2. Push

```bash
git remote set-url origin https://github.com/csdeepak/csdeepak.git
git add .
git commit -m "feat: terminal-themed research profile"
git branch -M main
git push -u origin main
```

Then *Settings → Actions → General → Workflow permissions* → **Read and write**.

## 3. Contribution snake

`.github/workflows/snake.yml` runs on push + every 12h and writes
`snake-dark.svg` to an **`output`** branch; the README points there. Trigger it
once via *Actions → Generate contribution snake → Run workflow*. The graph is
blank until that first run creates the branch.

---

## Structure

```
csdeepak/
├─ README.md               # Hero · Projects · Tech Stack · Stats · Contact
├─ SETUP.md
├─ photo/                  # source headshot (only raster asset)
├─ assets/
│  ├─ banner.svg           # animated hero
│  ├─ terminal-card.svg    # status dashboard
│  ├─ portrait.svg         # cyan vector portrait (generated)
│  └─ footer.svg
├─ scripts/
│  └─ generate_portrait.py # rebuilds portrait.svg from photo/
└─ .github/workflows/
   └─ snake.yml
```

## Regenerating the portrait

```bash
pip install pillow numpy
python scripts/generate_portrait.py     # → assets/portrait.svg (+ QA preview)
```

Tuning knobs are at the top of the script (`CROP`, `COLS`, `GAMMA`, `EDGE_K`).

## Design tokens

| Token | Value | | Token | Value |
|---|---|---|---|---|
| Background | `#090909` | | Accent | `#42F5FF` |
| Panel | `#0d0d0d` | | Text | `#EDEDED` |
| Border | `#1e1e1e` | | Muted | `#6a6a6a` |
