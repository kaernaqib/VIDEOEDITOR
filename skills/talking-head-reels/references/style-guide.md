# Style guide - the look and the rules

These rules come from a real production that went through 68 rounds of client notes, followed by
the client's own final pass on the type (bigger words, subtitles moved into the centre, Didot Bold,
soft shadows). Treat them as the client's taste, not as suggestions. The finished reel is
reproduced in full by `assets/examples/example_edl.json`.

## Contents
1. Format and pacing
2. Palette and grade
3. Typography
4. Text placement (the centre stack)
5. Text animation
6. The presenter
7. Inserts and layouts
8. Transitions and flashes
9. The look layers and audio
10. Review checklist

## 1. Format and pacing

- 1080x1920, frame rate = the recording's frame rate (25, 30, 24...). Length is whatever the talk
  is after tightening - typically 45-90 s.
- Pauses tightened: 0.22 s after a sentence, 0.14 s inside one (`cut_pauses.py` defaults). No
  breaths, false starts or repeated takes.
- Something changes on screen every 2-4 s: a punch-in, a big word, an insert, a split. The
  presenter is never alone for more than ~6 s, except for a deliberate moment (hook, CTA).
- Inserts are short (0.8-3.5 s) and always carry motion. No static images; a still must at least
  push in or be layered "photo on photo".

## 2. Palette and grade

- Accent red `#ED3B22`, white `#FFFFFF`, near-black `#161216` for UI backgrounds.
- B-roll is black-and-white by default: luminance, contrast +42, tinted black `#0E0C0E` -> white
  `#EDE6DE` (slightly warm paper white). High contrast, never muddy grey.
- Colour is the exception, used on purpose: a handful of shots (about 1 in 3 at most) stay in
  colour when colour carries meaning (a phone screen, a mustard jacket, a red uniform). Mark them
  `"color": true`.
- Coloured figures on a B&W shot (e.g. bright characters walking through a grey scene) are a strong
  device: matte with `clip_matte.py --mode colorful` or `person`, then `"color_figures_matte"`.
- The presenter keeps the user's own grade (graded file or LUT). Do not re-grade it inside the edit.

## 3. Typography

Three fonts, each with one job:

| role (`font`) | font | used for | size (px) | case |
|---|---|---|---|---|
| `anton` | Anton (condensed, heavy) | the 1-3 key words of a beat, numbers | 130-270, typically 170-200 | CAPITALS |
| `serif` | Didot Bold | elegant accents, the softer half of a phrase ("I told you", "same town", "brutal", "copying") | 100-170, typically 150 | lower case |
| `sub` | Helvetica Neue Medium | subtitles, lead-in words, labels, UI | 80-100 (subtitles 100, long lines 80-90) | sentence case |

`didot` (Didot Regular) exists for a rare thin accent; prefer `serif`.

- Size is the font size as in any design tool (em size). The words are big on purpose - the client
  enlarged every one of them in the final pass. Keep each line under ~960 px wide (Anton 200 fits
  about 8-9 letters); shorter words are better than smaller type.
- Up to two lines in one text item (`"COMMENT\n'TOWN'"`, `"same jobs\nand one"`) - for the CTA and
  for a subtitle chunk that would otherwise be too wide.
- Red Anton words get a soft red glow (75 %, wide and soft, no offset). White Anton words get no
  glow.
- Subtitles and most labels get a soft black shadow (45 %, small, no offset) so they read on any
  footage (`"shadow": true`).
- Anton tracking -10 (default). Didot may be tightened for short phrases (`"tracking": -60` to
  `-100`).

## 4. Text placement - the centre stack (1080x1920)

All text is centred horizontally (x 540) and lives in the middle of the frame, y ~700-1360. Nothing
goes in the bottom fifth. A beat's text is a small vertical stack, top to bottom:

```
lead-in label (sub, pop)        ~140 px above the big word
BIG WORD (anton) or accent (serif)
subtitle (sub, words)           ~130 px below the big word
```

| context | big word / accent | lead-in | subtitle |
|---|---|---|---|
| presenter on screen (hook, CTA, talking parts) | y 1120-1230, "under the neck" - never over the face | y ~1050 | y 1290-1320 |
| full-frame insert | y ~960 (700-1200) | y ~800-860 | y ~1060-1100 |
| split layout (footage top, presenter bottom) | y ~840-880, just above the seam | - | y ~940-1060, on the seam |

- Hook (first 2-6 s) and ending (last 3-5 s): text in front of the presenter, under the neck.
- When a subtitle runs alone (no big word), it sits where the big word would be: y ~960 over
  footage, y ~1300 over the presenter.
- Words behind the head (`"behind": true`) only when the word stays readable - the head may cover
  a small part of it, never the middle. When unsure, put the word in front.
- Counters (no. 1, no. 2, no. 3) appear side by side and stay on screen together until the end of
  the beat.

## 5. Text animation

- `build` (Anton): letters arrive in random order, stretched tall and widely spaced, outlined first,
  then filled, then lock into place in 3-5 stepped jumps (about 2 frames each). Slow 106%->100%
  scale drift while on screen.
- `soft` (Didot, or a quiet subtitle phrase): fades in from a blur with a slight grow (94%->100%).
- `words` (subtitles): each word appears exactly when spoken (timed from the transcript); the line
  lands with a quick 108%->100%.
- `pop` (lead-ins, labels): quick 118%->100%.
- Exit: Anton and Didot letters dissolve in random order with a slight grow and blur - never a
  hard cut, never a plain fade. Subtitles and labels fade out over ~0.16 s.
- A big word holds until the end of its shot (or until a nearby big word replaces it) - the
  planner enforces this. Set `keep_t1` for words that must stop at an exact time.

## 6. The presenter

- No head tracking. Each segment has a fixed framing; the face sits at ~40% of frame height.
- Two framings alternate at cuts: `wide` (fills the frame) and `tight` (~30% closer). Use the zoom
  plan to punch in on emphasis and to hide jump cuts.
- A slow 3% push inside every segment keeps it alive.
- Before an insert the presenter punches in (100->122% over 0.18 s) and settles back after it.
- The presenter appears whole and well framed in splits (bottom half) - never awkwardly cropped.

## 7. Inserts and layouts

- `full` layout: the insert fills the frame (most inserts).
- `split` layout: footage in the top half, presenter in the bottom half, a thin dark divider.
  Consecutive split inserts form one block (the presenter half stays, the footage changes). Use
  splits when the presenter's expression matters while the footage explains.
- Several clips in one insert are stacked "photo on photo": each new clip lands on top of the
  previous one with a small offset and shadow - never pushes the old one out leaving empty space.
- A `frame` (picture in a rectangle on red or black) opens from a thin horizontal line. Use it for
  match cuts of similar shapes (eyes, circles, screens) - each new clip lands in the same frame.
- A `band` shows the footage only in a horizontal strip; with a cut-out matte the subject breaks out
  of the strip. Its big words can sit inside the insert (`cut_txt`) or in the main text list.
- UI inserts (`cards`, `bar`, `number`, `converge`, `logo_flash`) are flat graphics on near-black
  with a faint blurred clip behind them - use them for data, rules, mechanics and brand names.
- Footage must always match the words. A generic "technology" clip under a specific sentence is
  worse than staying on the presenter.

## 8. Transitions and flashes

- Camera-move transitions only: `whip` / `whipL` (fast horizontal slide with motion blur), `zoom`
  (lands from 165%), `bulge` (lens bulge + zoom), `cut`. No rotations, no tilted camera, no spins.
- When one insert follows another, the outgoing shot stays still underneath until the new one has
  landed - nothing ever reveals black.
- `flash: "invert"` (2 frames) on most insert entries; `"silhouette"` (white presenter silhouette on
  black for 3 frames) for a hard moment like the hook.
- No empty or semi-transparent edges in any frame - during moves too. The renderer keeps every
  layer at cover size; still check the stills.

## 9. Look layers and audio

- Halftone texture (overlay, 24%), oval vignette (42%), fine grain (4) over everything.
- Voice mastered to -14 LUFS integrated, true peak -1.5 dBTP. No music unless the user supplies it.

## 10. Review checklist (every stills sheet)

- [ ] No empty, black or semi-transparent edges, including mid-transition.
- [ ] Every word fully inside the frame, readable, not over the eyes or mouth.
- [ ] Text in the centre stack; nothing in the bottom fifth; one subtitle chunk at a time.
- [ ] Big words match what is being said at that moment.
- [ ] B&W vs colour as planned; no off-palette text colours.
- [ ] The presenter's framing is steady (no drifting), face well placed, nothing cropped oddly in splits.
- [ ] Every insert moves; no still frame lingers.
- [ ] Each insert visually illustrates its sentence.
