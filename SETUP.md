# Setup — going live

A GitHub **profile README** for [`@csdeepak`](https://github.com/csdeepak). Everything
is hand-written, animated SVG (dark · cyan `#42F5FF` · terminal), with the portrait
derived from a real photo so the likeness is preserved.

---

## 1. Repo name must equal your username ⚠️

GitHub only surfaces a profile README from a repo named **exactly** like your username:

```
github.com/csdeepak/csdeepak
```

This working copy is `deepak`, which will **not** appear on your profile. Either:

- **Rename** — *Settings → General → Rename* → `csdeepak`, then
  `git remote set-url origin https://github.com/csdeepak/csdeepak.git`, **or**
- create a new **public** repo named `csdeepak` and push this into it.

## 2. First push

```bash
git add .
git commit -m "feat: terminal-themed research profile"
git branch -M main
git push -u origin main
```

Then: *Settings → Actions → General → Workflow permissions* → **Read and write**.

---

## 3. Folder structure

```
csdeepak/
├─ README.md
├─ SETUP.md
├─ .gitignore
├─ photo/                     # source headshot (only raster asset)
├─ assets/
│  ├─ banner.svg              # 1 · animated hero
│  ├─ terminal-card.svg       # 2 · status dashboard
│  ├─ portrait.svg            # 2 · cyan halftone portrait (generated)
│  ├─ typing.svg              # animated headline
│  ├─ research.svg            # 4 · agent-memory loop diagram
│  ├─ tech-stack.svg          # 6 · stack panel
│  ├─ timeline.svg            # 9 · research timeline
│  ├─ footer.svg              # 11 · footer
│  └─ icons/                  # monoline tech icons
├─ scripts/
│  └─ generate_portrait.py    # rebuilds portrait.svg from photo/
└─ .github/workflows/
   ├─ snake.yml               # contribution snake  → output branch
   ├─ metrics.yml             # rich metrics panel   (needs METRICS_TOKEN)
   ├─ activity.yml            # recent activity block
   └─ waka.yml                # WakaTime block        (needs WAKATIME_API_KEY)
```

---

## 4. Regenerating the portrait

The portrait is generated from `photo/`. To re-tune or swap the photo:

```bash
pip install pillow numpy
python scripts/generate_portrait.py
```

It writes `assets/portrait.svg` and a QA preview `scripts/_portrait_preview.png`.
Tuning knobs live at the top of the script (`CROP`, `COLS`, `EDGE_K`, `FILL_LIFT`, …).

---

## 5. Automations

| Workflow | Does | Needs |
|----------|------|-------|
| `snake.yml`   | contribution snake → `output` branch (README points there) | nothing (built-in token) |
| `activity.yml`| fills `START_SECTION:activity` block | nothing |
| `metrics.yml` | renders `assets/metrics.svg` | secret **`METRICS_TOKEN`** (PAT: `repo`,`read:user`) |
| `waka.yml`    | fills `START_SECTION:waka` block | secret **`WAKATIME_API_KEY`** |

Both token-gated jobs **self-skip** if the secret is missing, so nothing breaks.
Trigger any once via *Actions → Run workflow*. The snake graph is blank until the
first successful run creates the `output` branch.

Profile-view counter (Contact section) is a live badge — no setup.

---

## 6. Edit points

Search the README + SVGs for `EDIT`:

- **Project repo links** — Featured Research / Projects cards.
- **Timeline dates** — `assets/timeline.svg` (placeholders).
- **Tagline** — hard-set in `assets/banner.svg` and `assets/typing.svg`.

## Design tokens

| Token | Value | | Token | Value |
|---|---|---|---|---|
| Background | `#090909` | | Accent (cyan) | `#42F5FF` |
| Panel | `#121212` | | Cyan light | `#8afcff` |
| Border | `#1e1e1e` | | Text | `#EDEDED` |
| Hairline | `#1a1a1a` | | Muted | `#6a6a6a` |
