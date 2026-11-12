# Higgsfield generation: models, settings, prompts

Everything visual is generated. Work through the Higgsfield tools:
- `generate_image`, `generate_video` and `generate_audio`, or their `_batch` versions for several at once;
- `media_upload` + `media_confirm` for local files (the faceboxed sheets and the host audio chunks);
- `jobs_wait` until the jobs finish;
- download the results into `<proj>/assets/`.

Before you start:
- check the balance;
- add up the cost of the whole list and ask the user **once**;
- make a project with folders 01 Characters / 02 Locations / 03 Video / 04 Audio when the tools support it.

Test one item of each kind first (one sheet, one clip). Look at it, then batch the rest.

## Shared style line (put it at the start of every image and video prompt; adapt the era and place to the script)
> Black-and-white 16mm archival documentary footage from a 1950s social-experiment film: heavy natural film grain, slight gate
> weave, soft contrast, faint scratches and dust, real practical light, observational camera.

For a modern or colour subject, swap in a matching documentary look. Keep it one look for the whole reel.

People:
- realistic adults, unretouched skin;
- modest period clothes (long sleeves, closed necklines, long skirts);
- one calm expression per sheet;
- no real public figures;
- no text, logos or watermarks in any picture.

## 1. Host portrait (1 image)
- `soul_cinematic` (or `seedream_v5_pro`), 16:9, 2k.
- If the user wants to appear, pass their photo as `image_references`: "the same person as in the reference photo, keep the exact face".

> Medium close-up portrait of a presenter looking straight into the lens, calm and confident, plain softly lit studio wall
> behind, shoulders and head centred with room above the head, 50mm lens, natural skin texture, <wardrobe>. Single person, no
> text, no logos.

## 2. TV plate (1 image)
- `soul_cinematic`, **16:9**, 2k.
- The screen must be a flat, uniform chroma green, so that `reel.py screen` and the AE key find it.

> Cinematic film still: a single vintage 1950s CRT television set standing on a low concrete plinth in a dim, minimal room with a
> seamless grey wall and one soft top light, straight-on eye-level view, the TV in the centre of the frame taking about a quarter
> of the frame width. The TV screen is a perfectly flat, uniform, solid chroma-green (#00B140) rectangle with no reflections, no
> glare, no image and no gradient. Black-and-white grade except the green screen. No people, no text, no logos.

After downloading, run `reel.py screen assets/tv_plate.png <proj>`. If the box looks wrong (tiny, or the whole frame),
regenerate.

## 3. Character sheets (one per recurring character)
- `seedream_v5_pro` with the host portrait as `image_references` when the host plays the characters.
- Otherwise `cinematic_studio_2_5`.
- 16:9, 2k.

> Three-panel character sheet on a seamless light grey studio background: left panel full-body front view standing upright, head
> to toe with both feet visible; middle panel full-body back view standing; right panel head-and-shoulders close-up. <The same
> person as in the reference photo in all three panels: keep the exact face.> Identical character in all three panels, one calm
> neutral expression. Look: <role in one line>. Wearing <full modest period wardrobe, colours and materials>. Visible fine skin
> texture, no beauty filter. Soft diffused studio lighting, unretouched photography, sharp focus. Single subject only, exactly
> one person, no props, no furniture, no text, no watermark, no logos, no frame borders.

Before a sheet goes to video, black-box the small faces on the full-body panels. The video model then takes the face from the
close-up: `S/scripts/bin/facebox sheet.png sheet_facebox.png`. Upload the `_facebox` version.

## 4. Locations (3–6)
- `soul_cinematic`, 16:9, 2k.
- One line of place, time of day, light and lens, plus "no people, no text, no logos".

## 5. Story clips (the bulk: ~1 clip per 3–5 shots)
- `seedance_2_5`, `mode: omni_reference`, `resolution: 1080p`, **aspect_ratio 16:9**, `duration` 8–12, `generate_audio: false`.
- `image_references`: the faceboxed sheets and the locations the clip needs, referred to as @Image1, @Image2 and so on.
- Write 4–6 sub-shots of 2 s each, separated by `HARD CUT.`. Each sub-shot illustrates one of the consecutive lines the clip covers.

> <style line> @Image1 is <character>, @Image2 is <character>, fully covered. Location: <place> from @Image3. Script line:
> '<the lines this clip illustrates>'.
> Shot 1 (2 s): <framing, action>.
> HARD CUT. Shot 2 (2 s): <framing, action>.
> HARD CUT. Shot 3 (2 s): ...
> Realistic, grounded, no blood. Only these people. No text, no logos, no music.

In `story.json`, point each shot at the sub-shot it needs: `in` = sub-shot start + 0.3 s (2 s sub-shots start at 0, 2, 4...).

## 6. Host lip-sync clips (after `reel.py chunks`)
- One clip per chunk: `seedance_2_5`, `omni_reference`, 1080p, 16:9, `duration` = the chunk's `gen_duration`, `generate_audio: true`.
- `generate_audio` must be true: `reel.py align` reads the clip's own sound to sync the lips.
- References:
  - `image_references`: the host portrait;
  - `audio_references`: the uploaded `work/host/host_NN.wav`.

> The same person as in @Image1, exactly the same face and clothes, medium close-up, looking straight into the lens and talking
> to the viewer, small natural head movement and hand gestures below frame, plain softly lit wall behind. Her/his lips are
> perfectly synced to the speech in @Audio1: she/he says exactly those words in that voice, starting right at the beginning.
> Static camera. Photoreal. No text, no subtitles, no music.

Save as `assets/host/host_NN.mp4`, then run `reel.py align <proj>`. A clip marked CHECK did not say the words: regenerate it.

## 7. Music (1 track)
- `elevenlabs_music_v2_5`, `force_instrumental: true`, `duration` = reel length + 2 s (from `reel.py prep`).
- Describe the mood and the structure, with timestamps taken from story.json:
  - the hook;
  - a drop to near silence at a turn;
  - building tension;
  - the peak;
  - a calm outro.

> Instrumental cinematic documentary underscore, <N> seconds, sits under a voice-over. <mood>. Structure: 0:00 <hook: a deep
> sub boom and a short glitch, then a hushed build>; <m:ss> <drop>; <m:ss> <build>; <m:ss> <peak with low hits>; <m:ss> <calm
> resolving outro that fades out>. No vocals, no lead melody fighting the voice, no pop drum kit, clean mix.

## 8. Logos (only for names that are spoken)
Find each logo on Wikimedia Commons and get the user's OK for the list (file, source page, licence). Download Commons' PNG
render of the SVG: `https://commons.wikimedia.org/wiki/Special:FilePath/<File name>.svg?width=512` gives a 512 px PNG. Use a
white or light version for the dark badge. Keep an `assets/logos/SOURCES.md` with the file, source page and licence.
