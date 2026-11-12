# B-roll - finding, generating and preparing footage

## Contents
1. What good B-roll looks like here
2. Where it may come from (and rights)
3. Generating clips with Seedance via Higgsfield
4. Prompt template for generated shots
5. Preparing clips: in-points, focus, mattes
6. Swapping clips later

## 1. What good B-roll looks like here

- It shows exactly the thing being said, recognisable in half a second.
- It moves: a camera move, a gesture, a crowd surging, a light pulsing. 2-5 s of usable motion.
- It survives black-and-white: strong shapes and contrast, a clear subject.
- It crops to 9:16 (or to the top half, 1080x960, for split layouts): the subject must sit where
  the crop lands. Wide footage is fine - set `fx` to the subject's horizontal position.
- Cinematic beats generic: a lit close-up of hands on a keyboard beats a stock "office" wide shot.
- Interface footage (screen recordings, UI mock-ups) works well for tech topics.

## 2. Where it may come from

In order of preference:
1. **The user's own material** - other recordings, screen captures, product shots, photos (photos
   need motion: push-in or photo-on-photo stacking).
2. **Generated clips** made for this reel (section 3) - the best way to get specific, cinematic
   shots that match each sentence.
3. **Free-licence stock** - Pexels, Pixabay, Mixkit, Wikimedia Commons (check each licence; note
   attribution requirements in `PROJECT/CREDITS.md`).
4. **Licensed or press material** the user has the right to use.

Do not download or use clips from films, series, ads or other people's social posts unless the
user owns the rights or explicitly confirms they have a licence. When the user asks for "a scene
like the one in film X", generate a new shot with the same idea, camera and motion but entirely
original people, wardrobe and design.

Save files as `PROJECT/broll/<insert-id>_<n>.mp4` (or similar readable names).

## 3. Generating clips with Seedance via Higgsfield

If a Higgsfield connector is available (tools such as `generate_video`, `generate_video_batch`,
`media_upload`, `media_confirm`, `jobs_wait`), Seedance 2.5 (`seedance_2_5`) works well:

- **Text-to-video** (`mode: "t2v"`, `aspect_ratio: "9:16"` or `"1:1"`, `duration` 4-15,
  `resolution: "1080p"`, `generate_audio: false`, `bitrate_mode: "high"`): describe the whole shot in
  words (template below). This is the default for new footage.
- **Video edit** (`mode: "video_edit"`, the reference clip as `video_references`): re-makes a
  reference clip with new people/wardrobe while keeping camera and motion. Only for footage the
  user has the rights to restyle (their own clips, licensed stock).
- Before a big batch, ask for the cost with `get_cost: true` and tell the user.
- Uploading a local file: `media_upload` returns a presigned URL; PUT the bytes with curl and the
  headers `Content-Type: video/mp4` **and** `If-None-Match: *` (the URL is signed for it - without it
  the upload fails), then `media_confirm`. References must be 2-30 s long; slow a shorter clip down
  (ffmpeg `setpts`) before uploading.
- Batch independent shots with `generate_video_batch` (up to 12) and poll with `jobs_wait`.
- `ip_detected` means the reference or the prompt was recognised as a protected film/person/
  character. Do not try to get around it - write an original shot from words instead (t2v), with
  people and designs that do not resemble any real actor or famous character.
- Check every result: a face that resembles a real celebrity, readable text or logos in the frame,
  or a famous costume = regenerate with a more specific, different description (face shape, hair,
  age, distinctive details). For readable signs, a short "local fix" video edit of the result
  ("replace the lettering with neon shapes, change nothing else") usually works.
- Seedance changes clip length: outputs come back ~3.7-5 s, and a video edit of a short reference
  is stretched evenly in time. Measure the result (ffmpeg) and set `t_in`/`dur` accordingly; when a
  re-made shot replaces the original in the EDL, set `"speed": new_duration / old_duration` and
  scale `t_in` by the same factor so the motion stays in sync (`edl-schema.md`, "Swapping clips").
  1:1 outputs come back 1440x1440.
- Download results into `PROJECT/broll/` (keep the prompt next to them) - the EDL points at local
  files only.
- Generated shots are in colour; the renderer turns them B&W unless `"color": true`.

## 4. Prompt template for generated shots

Long, structured prompts give far more control than one-liners. Write them in English:

```
<SHOT TITLE> - SEEDANCE TEXT-TO-VIDEO

FORMAT
9:16 vertical, 1080p, 5 seconds, ONE continuous shot, no cuts. Ultra-realistic cinematic film frame shot on 35 mm,
not illustration, not a game render, not CGI-looking. No text of any kind: no captions, signs, logos, watermarks, numbers.

THE ONE TRICK
One or two sentences: the single idea the viewer must read in one glance.

RULE A - FRAMING
Exact crop (from where to where), where the subject sits in the frame, camera height, lens feel,
which way the subject faces and where the eyes look ("draw a line from the eyes - it leaves the frame on the left").
IF <checkable failure>; IF <...>, THE VIDEO IS WRONG AND UNUSABLE. HARD FAILURE CONDITION.

RULE B - ACTION, SECOND BY SECOND
0-1 s: ... / 1-2 s: ... / 2-3 s: ... / 3-5 s: ...
Camera: what it does (slow push 5 %, handheld float) and what it never does (no pan, no cut, no zoom snap).

RULE C - PEOPLE (unknown faces, nobody famous)
Age, build, skin, face shape, hair, distinctive details (a mole, a scar, a moustache), expression described as
muscles ("only one corner of the mouth rises", "upper lids relaxed, no white above the iris").
IF THEY LOOK LIKE ANY REAL ACTOR OR PUBLIC FIGURE, THE VIDEO IS WRONG AND UNUSABLE. HARD FAILURE CONDITION.

RULE D - WARDROBE AND PROPS
Exact garments and colours, what must NOT appear (uniforms, badges, logos, famous costumes).

RULE E - PLACE, FOCUS, LIGHT
Setting; what is sharp and what is soft; key light direction and quality; tonal separation if the shot
will be converted to black-and-white.

LOOK
Organic 35 mm grain, soft highlight roll-off, slightly lifted blacks, gentle halation, natural skin with pores.
IF IT LOOKS LIKE CLEAN DIGITAL VIDEO, HDR, OVER-SHARPENED OR AI-SMOOTH, THE VIDEO IS WRONG AND UNUSABLE.

COUNT
ONE man, ONE hand (five fingers), ZERO other people, ZERO text.

BANS
Layout / Camera / Identity / Wardrobe / Text / Style / Anatomy - one line each.
```

Why this shape works: the model follows concrete, checkable statements ("the ear on the
frame-right side is visible") much better than adjectives, and the explicit failure conditions
stop the most common drifts (famous lookalikes, text in frame, plastic skin, extra cuts).

Keep each prompt in `PROJECT/broll/prompts/<shot>.txt` - never overwrite a prompt, write `_v2`,
`_v3` so the user can compare.

## 5. Preparing clips

- `python3 scripts/clip_sheet.py PROJECT/qa/clips broll/*.mp4` - six frames per clip and the times
  of hard cuts inside it. Choose `t_in` after any hard cut, and `fx` where the subject is.
- Cut-out subjects (for `band` with `front` words, or silhouettes breaking out of a strip):
  `python3 scripts/clip_matte.py broll/x.mp4 matte/x_cut.mov --mode person|subject|largest [--smooth]`
  then `"cutout_matte": "matte/x_cut.mov"` on the clip.
- Coloured figures on a B&W clip: `--mode colorful` (or `person`), then
  `"color_figures_matte": "matte/x_figs.mov"`.
- Logos: transparent PNGs, preferably white versions, in `PROJECT/logos/`, referenced from `logos`.

## 6. Swapping clips later

When the user wants different footage for one shot, change only that clip in a new EDL version
(`edl-schema.md`, "Swapping clips"), check the beat with `--stills`, then render. To revert a swap,
put the old `src` / `t_in` / `speed` back.
