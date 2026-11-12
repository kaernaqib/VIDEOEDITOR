---
name: voiceover-glass-reel
description: "Turns ANY voiceover (and an optional script) into a finished 16:9 documentary-style reel in After Effects in one request: cuts pauses and breaths, writes the visual story, generates every picture in Higgsfield (characters, locations, story clips, a host lip-synced to the voice on an old TV, music), builds the edit natively in After Effects, renders a 1080p H.264 MP4. Look: dark archival documentary, clips in floating rounded glass frames with a glowing border, a moving perspective grid with keywords flipping colour, big captions, typewriter / giant-word / photo-card pages, flashes, synthesised SFX. Use whenever someone gives a voiceover, voice memo, narration or podcast clip and asks for a reel, video, short, explainer or edit made from it - 'make a video from my voiceover', 'turn this narration into a reel', 'glass frame edit', 'a clip from a voice-over', 'make a reel out of my voice recording', 'cut a video to my voice', 'glass frames and a grid' - even with no footage at all."
---

# Voiceover → glass reel

One request in, one finished MP4 out. The user gives a voiceover file (any audio or video format, any length up to ~3 min) and
optionally the script text, a topic note or reference links. You do everything else and stop only:
- **once** to get approval for the Higgsfield spend (give the total);
- **once** for downloads such as logos.

Work in the user's language in chat. Everything on screen is in the voiceover's language.

## What it makes

Turns ANY voiceover (and an optional script) into a finished 16:9 documentary-style reel in After Effects with one request. It cuts the pauses and breaths, writes the visual story, generates every picture in Higgsfield (characters, locations, story clips, a host lip-synced to the voice on an old TV, music) and builds the edit natively in After Effects. The look: dark archival documentary, every generated clip in a floating rounded glass frame with a thin glowing border and a smooth push-in, a moving perspective grid with keywords flipping colour on the word, big spoken captions, typewriter / giant-word / photo-card pages, flashes and negative flicks on the cuts, synthesised sound effects. It renders a 1080p H.264 MP4. Use it whenever someone gives a voiceover, voice memo, narration or podcast clip and asks for a reel, video, short, explainer or edit made from it: "make a video from my voiceover", "turn this narration into a reel", "glass frame edit", "a clip from a voice-over", "make a reel out of my voice recording", "cut a video to my voice", "glass frames and a grid". This holds even when they have no footage at all.

## Before you start (check once per Mac; tell the user exactly what to fix if anything fails)
1. **macOS 26 or newer** (on-device transcription) with **After Effects 2024 or newer, open**. In AE, turn on Settings → Scripting & Expressions →
   **Allow Scripts to Write Files and Access Network**.
2. Xcode command line tools (`swiftc`). Run `scripts/build_tools.sh`. It compiles `scripts/bin/{to_wav,transcribe,facebox,frames}`.
   If a script fails with "permission denied" (an uploaded skill can lose the executable bit), run `chmod +x scripts/*.sh` in this
   skill's folder once.
3. **Higgsfield connected** with credits: the `generate_image`, `generate_video`, `generate_audio` and `media_upload` tools.
   Check the balance before planning generations.
4. The first `transcribe` run may ask for Speech Recognition permission. It may also download the on-device model once.
5. If another AE project is open with unsaved changes, `build.sh` refuses. Ask the user to save it. Never discard their work.
   The build log prints `PREVIOUS_PROJECT <path>` when it closed a saved project of theirs. After the final render, reopen it:
   write a one-line jsx `app.open(new File("<path>"));` and run it with `scripts/ae_run.sh`.

`S` = this skill's folder. `PY` = `/usr/bin/python3` (or any Python 3.9+, standard library only).

## Pipeline

### 1. Project folder and voice
- Make `<proj>` = a new folder next to the voiceover named `<voiceover name>_reel`.
- Run `PY S/scripts/reel.py prep <voiceover> <proj>`. It converts the audio, transcribes it on the Mac and removes every pause and
  breath. The results are `work/voice_cut.wav` and `work/words.json` (word index → programme time).
- Then run `PY S/scripts/reel.py words <proj>` and read the whole indexed transcript.
- If the user gave a script, compare it with the transcript. Note misheard names for `spell` (for example `"28": "Grok"`).

### 2. Story (read `references/story.md`, then write `<proj>/story.json`)
1. Decide the **world** that fits the script: era, place, a recurring cast of 2–5 characters, 3–6 locations, B&W or colour.
   - Default: a black-and-white 1950s–60s archival documentary, where abstract subjects become people and places.
   - Pick a host look. When the user wants to appear themselves, use their photo as the host reference.
2. Cut the transcript into shots. Each shot starts on a word index.
   - **host** (talking to camera on the TV): 3–6 shots, 2–6 s each. Use them at the hook, the turns and the call to action. Together they take about 15–20 % of the runtime.
   - **clip** (generated footage in the glass frame): most shots, 1.5–3 s each.
   - **type** (typewriter page): the opening question or section titles, at most 6 words.
   - **giant** (one huge word with a red label and a serif sub-line): a named concept.
   - **cards** (2–4 photo cards with logo badges, a name on each word): when the voice lists people, products or brands.
     Logos appear only when they are spoken.
   - **list**: when the voice lists 2–4 points, mark that word range. Its keywords flip into the accent colour on the word.
   - **keys**: at most one per sentence.
   - **hits**: `invert` on 3–6 dramatic cuts, `strobe` on at most 2 "it got crazier" moments, `burn` on at most 2 peaks.
   - Never show the same clip moment twice.
3. Write the **generation list** from the shots:
   - each story clip is 8–12 s of 2 s sub-shots, covering consecutive shots, so one clip feeds several shots through different `in` times;
   - the host portrait, the TV plate, character sheets and locations;
   - one music bed.

### 3. Generate (read `references/higgsfield.md`)
1. Quote the total cost and get one approval.
2. Generate in this order: host portrait → TV plate → character sheets (`bin/facebox` on each, then upload) → locations →
   story clips → music. Download everything into `<proj>/assets/...` under the names `story.json` uses.
3. Host clips:
   - `PY S/scripts/reel.py chunks <proj>` writes one audio chunk per host shot to `work/host/host_NN.wav`;
   - upload each chunk and generate a lip-synced clip of the host saying it, save it as `assets/host/host_NN.mp4`;
   - `PY S/scripts/reel.py align <proj>` measures each clip's lip-sync offset from the words.
     If a clip shows **CHECK**, regenerate it.
4. Run `PY S/scripts/reel.py screen <proj>/assets/tv_plate.png <proj>`. It finds the green screen. If none is found,
   regenerate the plate.
5. Run `PY S/scripts/reel.py sfx <proj>` to synthesise the sound effects (no licences needed).

### 4. Build and check
1. Run `PY S/scripts/reel.py plan <proj>`. It writes `work/plan.json` and prints checks. Fix every ERROR in `story.json`.
   Take WARNs seriously: repeated clips, host lip-sync.
2. Run `S/scripts/build.sh <proj>`. It builds `<proj>/reel.aep` (comp **REEL**) in about 1 min for a 70 s reel. Read the log:
   fonts used, warnings.
3. Run `S/scripts/render.sh <proj> --half` for a quick check (~2 min). Then check the frames:
   - `S/scripts/bin/frames <proj>/out/reel_half.mp4 <proj>/work/check.jpg 4 <the middle second of ~16 shots>`;
   - look at `check.jpg`: captions readable and not over faces, host lips moving inside the TV, glass frames present, no black
     gaps, pages not empty.
   Fix in `story.json`, then re-run `plan`, `build` and the check.
4. **Final:** run `S/scripts/render.sh <proj>`. It writes `<proj>/out/reel_1080.mp4` (1920×1080, 25 fps, about 40 Mbps, with sound).
5. Send the MP4. Report:
   - its length;
   - what you could not verify;
   - the place to tweak by hand (`reel.aep`: every shot is its own comp in `02_SHOTS` / `03_PAGES`, the captions are in `CAPTIONS`).

## Rules
- **Rights:**
  - Generate everything: no stock or web footage.
  - Logos only from Wikimedia Commons, and only after the user's OK.
  - The music is generated.
  - The sound effects are synthesised by `reel.py sfx`.
- **The voice is the clock.**
  - Every cut lands on a word, one frame before it. `reel.py` does this.
  - Never change the speed or the words.
  - Captions show exactly what is spoken, apart from `spell` fixes of misheard names.
- **People:**
  - modest, period-appropriate clothes;
  - realistic adults;
  - no real public figures as characters;
  - AI models and companies are shown as invented characters and named only by caption and logo.
- **Re-runs are cheap.** `plan` and `build` are deterministic and rebuild `reel.aep` from scratch. Change `story.json` rather than editing `reel.aep` by hand,
  unless the user asks for hand edits. Once they edit `reel.aep` themselves, never rebuild over it without asking.
- **AE runs one script at a time.**
  - Use only `scripts/ae_run.sh`, `build.sh` and `render.sh`.
  - Exit 4 means AE is still busy: wait, never resend.
  - Exit 6 means AE did not start the script: is a dialog open?

## Files
| path | what |
|---|---|
| `scripts/reel.py` | prep / words / chunks / align / screen / sfx / plan (standard library only) |
| `scripts/build.sh`, `scripts/ae/build_reel.jsx`, `scripts/ae/reel_lib.jsx` | the After Effects build |
| `scripts/render.sh` | aerender to H.264 (`--half` for checks) |
| `scripts/ae_run.sh` | sends one script to the running AE and waits |
| `scripts/tools/*.swift` → `scripts/bin/` | audio conversion, on-device transcription, face boxes, frame sheets |
| `references/story.md` | story.json format, shot rules, a full example |
| `references/higgsfield.md` | models, settings and prompt templates for every asset |
| `references/look.md` | what the build draws (sizes, timings, colours) and how to tune it |
| `references/troubleshooting.md` | errors and fixes |
| `references/example_story.json` | the story.json of a finished 70 s reel (the EXPERIMENT test) |
| `PROMPT.md` | how to install the skill and the one prompt to send |
