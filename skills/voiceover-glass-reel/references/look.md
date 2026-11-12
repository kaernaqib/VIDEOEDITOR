# What build_reel.jsx draws (1920×1080, 25 fps)

Everything is native AE layers with keyframes: no expressions, no plug-ins. Keylight (bundled with AE) keys the TV; if it is
missing, the build falls back to Color Key.

| element | how it is built | numbers |
|---|---|---|
| Voice | `work/voice_cut.wav` at 0 | pauses and breaths removed by `reel.py prep`; joins on whole frames with 8 ms fades |
| Host on TV | TV plate scaled to cover the frame, green screen keyed; the host clip under it, cover-fit to the screen box | B&W, levels, grain, CRT bloom; screen spill (blur 160, screen 26 %); vignette 40 %; whole shot pushes in 2 %/s, linear |
| Glass clip | clip cover-fit to a 1500×844 frame (78 % width), rounded matte r 34 | push-in 100→107 % over the shot (ease in-out); glass pane white 9 %; border 2 px `glow` colour at 80 % + Glow (r 18, ×1.6); 1 px inner edge at 28 %; drop shadow (opacity 160, distance 22, softness 70); floats 546→534 px; enters 95→100 % in 6 f (quint out) on a new run of clips |
| Ambient light | the same clip at 125 %, blur 90, exposure −1.8, behind the glass | outside the list section only |
| List grid | 3D floor of 3 px lines every 120 px, rotate X 78°, cyan `#7FDFFF` 55 %, glow; slides 2 cells/s toward the viewer; horizon fade, centre haze | one comp across the whole list section |
| Keyword flip | text animator on the caption word: scale Y 100→0 (2 f, quint in) →100 (2 f, quint out); colour holds to `accent` at +2 f | plus a "tick" sound |
| Captions | one line per phrase (≤ 4 words), spread across 1380 px, gaps 48–200 px; normal words 58 px medium #E6E6E6, keys 82 px bold white | words cut in on their frame and stay to the phrase end; keys flicker in 35/100/35/100/35/100 %; y 560 over clips, 880 over the host; soft glow + dark halo |
| Type page | black, typewriter font 76 px, letters appear one by one over min(0.05 s × characters, 70 % of the shot) | glow, grain, vignette, typing sound |
| Giant page | dark page with a faint 96 px grid; the word in condensed black, fitted to 1560 px wide; red label box; serif italic sub-line | drifts sideways 12 px/s and pushes in 2 %/s |
| Cards page | up to 4 paper cards (340×410, rotated ±4–5°) at the corners, a clip or image in each, round logo badge | each card snaps in on its word, 108→100 % in 5 f (ref out curve 5/95 %); the name in the middle changes per card |
| Flash | adjustment layer: exposure +4, +2.2, +0.8, 0 on the first 4 frames of a clip or cards shot | HOLD keys half a frame early so motion blur never blends two states |
| Hits | invert: negative frame before the cut, 1 normal, 1 near-black; strobe: W/B/W/B/W from −3 f; burn: 2 blown-out posterised frames | glitch or flash sound |
| Film grain | adjustment layer, Noise 2 % over everything | |
| Music | the bed at `music_db` (default −17 dB), 0.4 s fade-in, 1.5 s fade-out | |
| SFX | synthesised by `reel.py sfx`: whoosh before new cuts (−15), impact on pages (−9), flash (−17), pop on cards and labels (−13), tick on flips (−12), typing on type pages (−15), glitch on hits (−12) | |

## Tuning
- Colours: `accent` and `glow` in story.json.
- Fonts: the build picks the first installed font of each list (top of `build_reel.jsx`, `FONT`). It prefers SF Pro if installed, then
  Helvetica Neue, Georgia and American Typewriter; every Mac has the latter. The log prints the fonts used.
- Caption size and position: `N`, `K`, `AVAIL` in the captions block; `y` per phrase comes from `reel.py plan` (880 host / 560 else).
- Glass frame: `FW`, `FH`, `RAD`, `PAD` in `glass()`.
- Anything else: open `reel.aep`. Every shot is its own comp (`02_SHOTS`, `03_PAGES`) and the master is `REEL`.
