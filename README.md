# FCi website — spec concept

Static rebuild of fci.ca with a scroll-driven 3D "Integrated Building Services" section (Three.js + GSAP).

- `index.html` — the whole site (inline CSS + JS module)
- `fci_tower.glb`, `env/`, `tex/`, `img/services/` — 3D model, lighting and imagery
- `blender/` — Blender 4.0 scripts that generate the tower (not deployed)

No build step. Deploy the repo root as a static site (Vercel framework preset: **Other**).
Local preview: any static server, e.g. `python -m http.server 8080`.
