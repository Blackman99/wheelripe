# wheelripe design brief

**Reference object:** a wheel of Emmental cut open on a cheesemonger's board. PyPI started life as "the Cheese Shop", and Python *wheels* are named after cheese wheels. The cut face is your dependency set: every package is a spot in the paste. Where a package has a wheel for the target Python, the paste is solid. Where it doesn't, there is a hole (an "eye"). A small eye with an arrow is a version bump; a big open eye is blocked upstream.

Metaphor in one line: *the newer the Python you ask for, the more holes in the cheese* — and wheelripe tells you which hole is which.

- **Base tone:** mid, warm, saturated **Mimolette orange `#e8742a`** fills the landing page. No other project has an orange base (linelore uses `#ff5b00` only as an accent on white; rackhands is metallic brass `#c79a3b`, a darker, less saturated ochre with metal texture).
- **Palette:** orange `#e8742a` · paste yellow `#ffd978` (wedge face, docs base) · rind `#a8471a` · eye shadow `#6e2c0e` · cocoa ink `#2a160b` (all text, command panels) · blue-vein `#2b5f73` (links, BUMP arrows, focus rings). No red ink, no beige/cream page, no gradients.
- **Type:** **Bagel Fat One** (fat rounded display — the only display face, headings and the wedge title) + **Bricolage Grotesque** 400/600/800 (body) + **Reddit Mono** 400/600 (commands and wheel filenames only). All self-hosted woff2 (OFL).
- **Texture:** organic. The paste carries a scatter of tiny closed eyes (SVG ellipses); the rind is a smooth darker band with a soft wavy edge. No paper grain, no scanlines, no brushed metal, no corrugation, no grid lines.
- **Rendering:** flat organic vector cross-section in inline SVG — ellipses and blobs, every eye drawn as two flat tones (dark crescent + shadow interior), no straight-line diagrams, no 3D, no isometric, no map lines.
- **Layout:** diagonal **wedge**. The hero is one huge cheese wedge cutting in from the right edge at a slant; `<h1>` is set across its cut face. Sections below are separated by diagonal "slice" cuts (clip-path), alternating orange and paste. Legends and steps follow the slant instead of a grid. No centered title stack, no cards, no columns of features.
- **Motion (demonstrates the mechanism):**
  1. Intro: a cheese wire sweeps diagonally across the wedge and the cut face appears; then each dependency's spot is checked in turn — solid spots close, blockers *open* into eyes (scale from 0 with a soft overshoot), bumps open small and sprout a blue arrow with the fixing version.
  2. Target dial (3.13 · 3.14 · 3.15 · 3.15t) and platform switch (Linux · macOS · Windows): eyes open and close to the real verdicts — precomputed by running wheelripe against the live PyPI at build time (`site/data.json`).
  3. Wheel-filename slicer: `msgpack-1.2.3-cp315-cp315t-win_amd64.whl` is cut into python · abi · platform slices that slide apart when scrolled into view; each slice turns solid or holed for the chosen target.
  - `prefers-reduced-motion`: no wire, no pop; final states shown immediately; dial still works (instant swap).
- **Logo:** a flat cheese wedge seen side-on (right-pointing triangle with a rind back), paste `#ffd978`, rind `#a8471a`, two closed eyes and one open eye cut through the edge. Transparent background, no rounded-square tile, no outline stroke. Favicon: the wedge with one eye.
- **OG / social preview:** same orange field; the wedge spans diagonally with real package eyes labelled; "wheelripe" in Bagel Fat One across the cut face.
- **Banned-trope check:** no dark bg + cyan/purple gradient, no gradient text, no glow, no glassmorphism, no left-copy/right-card hero (the h1 is *on* the object), no three-column feature cards, no SaaS template, no Inter + mono, no paper/stamp/typewriter, no rounded-square icon logo.
