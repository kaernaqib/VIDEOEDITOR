# EDL schema (edl.json)

The EDL is the single source of truth: the renderer draws every frame from it. All times are **program seconds** (after the
pauses are cut). All coordinates are pixels in the 1080x1920 frame, origin top-left, and refer to
the centre of the item (for text: the centre of the visible letters). Relative paths resolve against the
project folder.
A complete example: `assets/examples/example_edl.json`.
The `//` comments below are explanations only - real JSON files cannot contain comments.

## Contents
1. Top level
2. presenter
3. inserts (common fields, clip objects, kinds)
4. text
5. Swapping clips
6. Tips

## 1. Top level

```json
{
  "name": "MyReel",                       // comp + file names (no spaces)
  "project_dir": "/abs/path/MyReel_reel", // optional; default = folder of edl.json
  "W": 1080, "H": 1920, "fps": 25,        // fps default = project.json
  "accent": "#ED3B22",                    // optional palette overrides
  "presenter": { ... },                   // optional; defaults come from project.json
  "audio": "audio/program_master.wav",    // default from project.json
  "zoom": [[0.0, 0.84, "tight"], [0.84, 4.8, "wide"]],   // presenter framing plan; omit = alternate per cut
  "logos": { "brand": "logos/brand_white.png" },        // keys used by inserts
  "inserts": [ ... ],
  "text": [ ... ],
  "look": { "halftone": "assets/halftone_1080x1920.png", "halftone_opacity": 24, "vignette": 42, "grain": 4 },
  "fonts": { "anton": "Anton-Regular", "serif": "Didot-Bold", "didot": "Didot", "sub": "HelveticaNeue-Medium" }   // PostScript names
}
```

## 2. presenter (all optional)

```json
"presenter": {
  "src": "footage/Name_graded.mov",       // the UNCUT recording (graded); default project.json "presenter"
  "cuts": "analysis/cuts.json",
  "faces": "analysis/faces.jsonl",
  "matte_body": "matte/presenter_body.mov",
  "matte_head": "matte/presenter_head.mov",
  "framing": {                              // scale is relative to "just fills the frame"; face_y = face height as a fraction of H
    "wide":  { "scale": 1.0125, "face_y": 0.396 },
    "tight": { "scale": 1.30,   "face_y": 0.406 },
    "half":  { "scale": 1.24,   "face_y": 0.344 }   // presenter in the bottom half of split layouts
  }
}
```

## 3. inserts

Common fields:

| field | meaning |
|---|---|
| `id` | unique, short (`hook_ai`, `fight`) |
| `t0`, `t1` | program seconds; inserts must not overlap; back-to-back inserts share the boundary exactly |
| `kind` | see below |
| `layout` | `full` (default) or `split` (insert in the top half, presenter in the bottom half) |
| `trans` | entry move: `whip`, `whipL`, `zoom`, `bulge`, `cut` (split inserts slide in on their own) |
| `flash` | `invert` (2-frame negative), `silhouette` (white presenter silhouette, needs body matte), or null |
| `norelease` | true = presenter does not settle back after this insert (use inside a run of inserts) |

### Clip object (used in `clips` and `bgclip`)

```json
{ "src": "broll/riot_street.mp4",   // video or still (.jpg/.png)
  "t_in": 0.3,                      // seconds into the clip to start from
  "speed": 1.0,                     // source seconds per program second (1 = natural; see "Swapping clips")
  "dur": 1.4,                       // seconds this clip stays before the next clip lands (omit for the last)
  "zoom": [1.0, 1.08],              // slow push from 100% to 108% of "cover" size
  "fx": 0.6,                        // horizontal focus 0..1 for wide footage cropped to the comp (0.5 = centre)
  "color": true,                    // keep colour (default: black-and-white)
  "cutout_matte": "matte/riot_person.mov",          // for band cut-outs (clip_matte.py output)
  "color_figures_matte": "matte/riot_colour.mov" }  // coloured figures on a B&W clip
```

A clip shorter than the time it must cover is slowed down automatically (up to 4x); prefer clips
that are long enough.

### Kinds

| kind | extra fields | what it is |
|---|---|---|
| `full` | `clips` (1-3), optional `logo: [key, x, y, size]`, `logos: [[key, x, y, size], ...]` | footage covering the insert area; several clips stack photo-on-photo |
| `frame` | `clips`, `rect: [cx, cy, w, h]`, `bg` colour, `noframeanim` | footage inside a rectangle on a solid background; opens from a thin line; match cuts |
| `band` | `clips` (1), `cut_txt: [{text, x, y, size, color, t0, front}]`, `staticband` | footage in a horizontal strip, big words above/below; `front: true` words sit in front of the cut-out subject (needs `cutout_matte`) |
| `vsplit` | `clips` (2), `tsplit` (s after t0) | clip A fills the area, clip B slides into the bottom half at `tsplit` |
| `logo_flash` | `slots: [[logoKey, "#hex bg"], ...]` | rapid logo cards, each slot an equal share of the insert |
| `cards` | `title`, `cards: [{logo, name, caption, t}]` (2-4), `bgclip` | a row of outlined cards appearing at their `t` (s after t0) |
| `bar` | `label`, `from`, `to`, `suffix`, `d0`, `d1`, optional `box: {bx, by, bw, bh}`, `bgclip` | a filling/draining bar with a live percentage |
| `number` | `label`, `from`, `to`, `suffix`, `count: [a, b]`, `status`, `y`, `bgclip` | a big counting number in a card |
| `converge` | `logos` (up to 4 keys), `bgclip` | four logos fly to the centre, a red ring draws around them |
| `solid` | `bg` colour, optional `bgclip` | a clean background for text-only beats (counters) |
| `cutout` | `bgclip` | the presenter cut out (body matte) in front of footage |
| `pframe` | optional `bgclip` | the presenter inside a white frame over blurred footage |

UI kinds (`cards`, `bar`, `number`, `converge`) place their own internal labels; put the beat's big
words in `text` as usual.

## 4. text

```json
{ "font": "anton",            // anton | serif (Didot Bold) | sub (Helvetica Neue Medium) | didot (Didot Regular)
  "text": "CHAOS",            // "\n" makes a second line ("COMMENT\n'TOWN'"); two lines at most
  "t0": 35.06, "t1": 35.68,   // big Anton words are extended to the end of their shot automatically
  "x": 540, "y": 1176,        // centre of the visible letters (whole block); y can be omitted when "behind" is true
  "size": 204,                // font size in px, like a design tool (Anton 130-270, serif 100-170, sub 80-100)
  "color": "#ED3B22",         // accent red or white
  "anim": "build",            // build (Anton) | soft (Didot, quiet phrases) | words (subtitles) | pop (labels)
  "tracking": -10,            // letter spacing in 1/1000 em (Anton default -10, others 0)
  "leading": 168,             // distance between lines in px (default 1.2 x size)
  "behind": false,            // true = behind the presenter's head (needs head matte; only if still readable)
  "glow": true,               // soft red glow - default: true for red Anton
  "shadow": true,             // soft black shadow - use on subtitles and labels
  "keep_t1": false,           // true = stop exactly at t1 (do not extend to the end of the shot)
  "fit": true,                // false = keep the size even if the line is wider than ~960 px
  "fadeout": true,            // false = no exit animation
  "wt": [12.32, 12.55]        // subtitles only: word start times; omitted = taken from the transcript
}
```

Subtitle convention: `{"font": "sub", "anim": "words", "size": 100, "y": 1300, "shadow": true}` over
the presenter; `y` ~1060-1100 under a big word over footage, ~950 on the seam of a split layout
(see the centre stack in `style-guide.md`). Lead-in label: `{"font": "sub", "anim": "pop", "size":
100}` ~140 px above its big word.

## 5. Swapping clips

To use different footage for a shot, change only that clip's `src` (and `t_in`) - timing, zoom and
everything around it stay the same. Two cases:

- **An unrelated clip**: set `src`, choose `t_in` after any hard cut (`clip_sheet.py` lists them),
  remove `speed`.
- **The same shot re-made** (e.g. a Seedance video edit of the original clip, which comes back at a
  different length with the motion stretched evenly): keep the motion in sync with
  `"speed": new_duration / old_duration` and scale the in-point the same way,
  `"t_in": old_t_in * speed`. Measure durations with ffmpeg (`ffmpeg -i clip.mp4` prints them).

To revert, put the old values back. Render stills of the changed beat before the full render.

## 6. Tips

- Keep `t0`/`t1` on word boundaries from `analysis/program_words.json`.
- Inserts that follow each other directly should share the boundary exactly (same number), so the
  renderer chains the camera moves and nothing reveals black.
- Text over a split insert sits on the seam: big word just above it (y ~860), subtitle on it (y ~950).
- For a counter, use a `solid` insert (or full footage) plus `sub` "no." + Anton digits as text
  items with `keep_t1` so all digits stay until the end of the beat.
- Validate after every edit: `python3 scripts/validate_edl.py edl.json`.
