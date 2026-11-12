# The renderer - how the reel is drawn, speed, troubleshooting

## Contents
1. Pipeline
2. Commands
3. What a frame is made of
4. Text (libass)
5. Speed
6. Troubleshooting

## 1. Pipeline

No editing application is involved. Three scripts turn `edl.json` into the MP4:

| script | job |
|---|---|
| `reel_plan.py` | resolves the EDL once: media sizes, presenter pieces (pauses removed, fixed framing), punch-in keys around inserts, insert timing (adjacent inserts, transition entries, split blocks), subtitle word times, the text rules (hold to end of shot, width limit) |
| `render_reel.py` | composites every frame with numpy (presenter, inserts, transitions, flashes, look layers), runs several worker processes on separate frame ranges, encodes H.264 and adds the program audio |
| `textass.py` | writes the kinetic type as per-frame libass subtitle events (one per text per frame, with per-letter tags) and renders them through ffmpeg's `ass` filter as transparent layers |

`fontmetrics.py` reads font files so sizes match design-tool sizes (see section 4).

## 2. Commands

```bash
# moments as PNGs + DIR/qa/stills_v1/sheet.jpg (seconds of work)
python3 scripts/render_reel.py DIR/edl.json --stills 0.6 2.4 4.8 --out-dir DIR/qa/stills_v1

# the full reel
python3 scripts/render_reel.py DIR/edl.json --out DIR/render/NAME_v1.mp4 [--workers 6]
```

The full render prints size, fps, duration, whether audio is present and the integrated loudness
(should read about -14 LUFS). Output: H.264 (CRF 12, yuv420p, BT.709), AAC 320 kbps 48 kHz,
`+faststart` for upload.

## 3. What a frame is made of (bottom to top)

1. Presenter: the uncut recording, cropped and scaled per piece (wide / tight framing, slow 3%
   push), with the punch-in keys before inserts. Pieces jump-cut where pauses were removed.
2. Words behind the head (`behind: true`), then the presenter's head (head matte) on top again.
3. Inserts at their transition positions: `full` inserts with whip / zoom / bulge entries and
   horizontal motion blur; split blocks (footage half sliding in, presenter half, divider);
   invert and silhouette flashes.
4. Front text (all other text).
5. Look: halftone overlay, vignette, grain.

Each insert is composed at its own local time like a precomp: clips cover their area (`fx` picks
the horizontal focus), push from `zoom[0]` to `zoom[1]`, play at `speed` (slowed automatically if a
clip is too short), then B&W treatment (luminance, contrast, tint) or the colour treatment.
Clip mattes (`cutout_matte`, `color_figures_matte`) are read frame by frame alongside the clip.

## 4. Text (libass)

- Fonts: Anton ships with the skill (`assets/fonts`, OFL licence); Didot, Didot Bold and Helvetica
  Neue come from macOS. Each render links them into a temporary fonts folder for libass, so nothing
  needs installing.
- libass treats a font size as the font's full line height, design tools as the em size. The
  renderer converts with the font's own metrics (`fontmetrics.py`), so `"size": 200` looks like 200
  in any design tool.
- Positions: before rendering, every line is measured once; `x, y` is the centre of the visible
  letters of the whole block, like a design tool's bounding box.
- Animations are evaluated per frame and written as per-letter override tags (opacity, scale,
  spacing, outline, blur). Glow and shadow are extra blurred copies under the text.
- Words appear at the transcript's word times (`analysis/program_words.json`) unless `wt` is set.

## 5. Speed

Stills: about one second per frame with 8 workers. A full 75 s reel at 25 fps (about 1,850 frames)
takes a few minutes on a recent Apple-silicon Mac; the 4K presenter decode is the main cost. Use
`--workers` to match the machine (default: CPU cores minus 2, at most 8). Render stills for every
check and the full video only when the stills pass.

## 6. Troubleshooting

| symptom | fix |
|---|---|
| `check_setup.py`: ffmpeg without libass | `brew install ffmpeg` or `pip install imageio-ffmpeg` in the venv; or point `$FFMPEG` at a build with libass |
| text missing in every frame | ffmpeg chosen has no libass, or a font is missing - run `check_setup.py`; look for "fonts not found for libass" in the render log |
| text in a default font | the PostScript name in `fonts` is wrong; list names with `python3 scripts/fontmetrics.py /System/Library/Fonts/Supplemental/Didot.ttc` |
| empty or black edges in a still | a clip too small for its move: raise its `zoom`, check `fx`; inserts that follow each other must share the exact boundary time |
| subtitles late/early | rerun `transcribe.py` with a bigger model, or set `wt` by hand |
| a re-made (generated) clip out of sync with the original timing | set `speed` and scale `t_in` (see "Swapping clips" in `edl-schema.md`) |
| head matte flickers / words behind the head look cut | use `behind` less; hair against a busy background is hard to matte - put the word in front |
| render seems stuck | it prints when it starts; a 75 s reel takes minutes. Run it in the background and wait; do not start a second render of the same EDL at the same time |
| "media not found" | a source file moved or an external drive is not mounted - the EDL stores paths; reconnect the drive or fix the paths |
