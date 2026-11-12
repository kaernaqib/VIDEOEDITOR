---
name: reel-editor
description: Edit a vertical 9:16 Reel / TikTok / Short inside the user's own CapCut project, in one of two house styles (Authority talking-head or Cinematic Story) and one of four formats (Education, Vlog, Do & Don't, Before/After). Cuts silences, fillers and bad takes, adds word-by-word captions with yellow keyword pops, punch-ins, listicle headers, B-roll (own folder, Pixabay/Pexels stock, or AI), music and SFX, masters the voice to -14 LUFS, makes a thumbnail, and posts via Zernio after one approval. Use when the user says "edit reel", "edit video aku", "/edit-reel", gives a CapCut project/folder name, or asks to make a reel in their style.
---

# Reel Editor

The user speaks Malay (often mixed with English). Talk to them in casual Malay. Captions follow what is
actually said (BM, English or rojak), never translated.

This skill **builds on `anthropic-skills:capcut-talking-head-edit`**. Load that skill first and copy its scripts
(`cct.py analyze.py edl.py qa.py harvest.py build.py place_graphics.py overlays.py preview.py`) into
`work/scripts/`, then add the scripts in this skill's `scripts/` folder next to them. All of that skill's
**Hard rules apply unchanged** (never write while CapCut is open, re-read before every write, clone objects from
the user's own projects, write all six timeline copies, real device paths, backups).

Read before editing: `STYLE_GUIDE.md` (the look, measured from the user's 5 reference reels) and `FORMATS.md`
(the structure of each format).

## Needs

- Claude desktop app linked to the user's computer (device tools), CapCut international desktop app.
- Workspace: Python + `numpy`, `Pillow`, `faster-whisper`, `ffmpeg`.
- Optional connectors: **Epidemic Sound** (music + SFX), **Zernio** (posting), Pexels API key (stock B-roll),
  an AI video connector such as Higgsfield (generated B-roll). Stock B-roll: `PIXABAY_API_KEY` env var (free).

## Windows (the user's machine)

- Projects: `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\` (in bash shells:
  `$LOCALAPPDATA/CapCut/User Data/Projects/com.lveditor.draft`). Request that folder plus the footage folder.
- The timeline file may be `draft_content.json` instead of `draft_info.json`; all scripts accept either.
- Media paths inside the draft are Windows paths (`C:/Users/...`, forward slashes as CapCut writes them). Copy
  the exact form CapCut used in the media bin; never write `/mnt/...` or workspace paths.
- Check the first byte of the timeline file is `{`. If not, the project is encrypted: say so and stop.
- If the device shell is PowerShell, not bash, translate the ffmpeg/find commands; ffmpeg may need installing
  (`winget install ffmpeg`), so ask before installing anything.
- Stock keys: read `PIXABAY_API_KEY` (primary) or `PEXELS_API_KEY` (if set) from the environment. Never ask the
  user to paste a key into chat. If neither works, ask them to download a few clips into a B-roll folder instead.

## Inputs the user gives

1. The **CapCut project name** (`draft_name`) they uploaded the footage into. That's the folder to edit.
2. The **format**: education | vlog | dos-donts | before-after. If not said, infer it from the transcript and say
   which you picked.
3. Optional: a B-roll folder of their own footage, a music mood, the platforms to post to.

Defaults when they don't say: style from the format (see table), B-roll priority **own folder → Pixabay/Pexels → AI**,
tight pacing with punch-ins, music from Epidemic Sound, post to nothing until they approve.

| Format | Style | Notes |
|---|---|---|
| education | A Authority | listicle header if the talk has numbered points |
| dos-donts | A Authority | ❌/✅ labels, red/green accent |
| before-after | A Authority | Before/After labels, wipe at the turn |
| vlog | B Cinematic | B-roll-led, big condensed titles, small serif subs |

## Run order (make a task list from this)

| # | Step | Waits for the user? |
|---|---|---|
| 0 | Device access: CapCut projects folder, footage folder, B-roll folder, music/SFX folder | approves folder prompts |
| 1 | Find the project by `draft_name`, read the media bin, confirm it's plain JSON and 9:16 (`canvas_config` 1080x1920) | |
| 2 | Analysis: 16 kHz wav → `analyze.py` (use the multilingual model `small`, NOT `small.en`, because the user speaks BM/rojak), contact sheets | |
| 3 | Cut list (`job.json` → `edl.py` → `qa.py`), plus the format's structure from `FORMATS.md` | |
| 4 | Captions + keywords + headers → `captions.py` | |
| 5 | B-roll plan, then fetch: own folder / Pexels / AI | |
| 6 | Music + SFX (Epidemic Sound), voice loudness | |
| 7 | Templates (`harvest.py` + `harvest_text.py`), build, `text_tracks.py`, preview | |
| 8 | Thumbnail (`thumbnail.py`) | |
| 9 | **The single review:** send preview + thumbnail + caption text for the post | **approves / asks for changes** |
| 10 | Install into CapCut | **confirms CapCut is quit** (always, a hard rule) |
| 11 | User exports from CapCut (or opens and tweaks), then post via Zernio | **approves posting** |

The user chose to review **only once, before posting**. So don't stop between steps 1–8 to ask. Make the call
yourself and list every choice in the review message. The only extra stops are the hard-rule ones: CapCut quit
before a write, and approval before anything is posted publicly.

## 2. Transcription (BM / rojak)

`analyze.py` defaults to `small.en`. Run it with `--model small` (or `medium` if the machine is fast enough) so
Malay words come out right. Fillers to remove in BM as well as English: `erm, err, aaa, uhh, emm, haa, ah, apa
ni, macam, kan` (only `macam`/`kan` when they're pure filler, not part of the sentence). Keep the **last full
take** of any repeated line.

## 3. Cut list per format

Fill `job.json` as in capcut-talking-head-edit, plus:
- `pacing: "tight"`, `punch: 1.12`. Push-ins (`zooms`) on the hook, each point's title, the turn
  (Don't→Do, Before→After) and the CTA.
- **The hook must be the first 1–2 s.** If the strongest line is later in the talk, tell the user in the review.
  Don't reorder the talk silently.
- Target length 30–60 s for A-style, up to 80 s for vlog. If the raw talk would end up much longer and has
  several self-contained points, propose splitting into multiple reels in the review (one CapCut project each).

## 4. Captions (`scripts/captions.py`)

Write `work/caption_plan.json`:
```json
{"style": "A", "keywords": [12, 40, 77], "big": [40],
 "headers": [{"from_word": 30, "to_word": 95, "num": "1", "title": "I NEED TO THINK ABOUT IT"}],
 "labels": [{"from_word": 10, "to_word": 50, "text": "❌ DON'T", "kind": "bad"}]}
```
- `keywords`: word indices (from `words.json`) of the ONE word per 1–2 sentences that carries the meaning
  (price, value, a number, the payoff). They render yellow, bigger, on their own line under the chunk.
- `big`: a subset of keywords to render as UPPERCASE extra-large ("REFRAME", "BUDGET"). Use sparingly (1 per 10 s).
- `headers`: numbered listicle titles (A style), shown top-left for the whole point.
- `labels`: Do & Don't / Before-After labels.

Run `python3 scripts/captions.py work`. It reads `words_tl.json`, splits into 2–4 word chunks that never
cross a pause > 0.35 s or a sentence end, and writes `work/captions.json` (timeline seconds). Read the printout:
every chunk should read naturally on its own.

## 5. B-roll

Plan one cutaway every 3–5 s (A style) or every ~2 s (B style), each anchored to the words it illustrates
(`inserts` in `job.json`). Pick the source in this order:
1. **User's own B-roll folder:** make contact sheets, look at them, match by content.
2. **Stock, free:** Pixabay first: `https://pixabay.com/api/videos/?key=$PIXABAY_API_KEY&q=<english+keywords>&safesearch=true&per_page=10`
   (pick from `hits[].videos.large|medium.url`, prefer taller-than-wide or centred subjects that crop to 9:16). Pexels
   only if `PEXELS_API_KEY` is set (`https://api.pexels.com/videos/search?query=...&orientation=portrait`,
   header `Authorization: <key>`). Search in English even when the talk is BM. Download into the footage folder
   `B-roll (Claude)/` on the device and keep a `credits.txt` (source + page URL) next to them.
3. **AI-generated:** only for shots stock can't cover (a specific scene, a metaphor). Costs money. Count them in
   the review.

Never use movie or TV clips, even though the reference reels do. They get the account copyright strikes.

**Vertical fill:** these are full-screen cutaways, not the dark-plate style. In `build.py`'s cutaway section, drop
the plate track and set the insert scale to the cover ratio `max(1080/w, 1920/h) / min(1080/w, 1920/h)` (with a
0.03 slow push on top) instead of `0.88`. Re-check `validate()` after the change.

## 6. Music, SFX, loudness

- **Epidemic Sound:** `SearchRecordings` by mood (A: confident/corporate hip-hop beat; B: cinematic/lo-fi
  warm), download into the device music folder, then use as `music.json`. Music sits 15 dB under the voice. B style can
  switch tracks at the big turn.
- **SFX** (`SearchSoundEffects`): whoosh on each B-roll cut-in, pop on `big` keywords, riser before the turn,
  click on header appear. Use `sfx.json` + `overlays.py`. Keep them about 6.5 dB under the voice.
- **Voice:** the references are all mixed at **-14 LUFS integrated**. Measure the camera audio. If it's quiet
  or noisy, use CapCut's own "Enhance voice" / "Reduce noise" (tell the user to tick it, since those flags can't be
  cloned safely), or pre-process a cleaned WAV with
  `ffmpeg -af "afftdn=nf=-25,highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=11"` and swap it in as the audio of
  the main track (mute the camera clip audio, add the WAV on an audio track, aligned on the timeline).

## 7. Build and text tracks

1. `harvest.py` as usual (video, audio, adjustment layer).
2. **Text templates:** ask the user once (in step 0, alongside the folder approval) to make a tiny template project
   called `REEL TEMPLATE` in CapCut (if it doesn't exist yet: search by `draft_name`) that has
   two clips with one transition between them, one clip with an in-animation, and:
   - one caption text "**caption KEYWORD**" with "caption" in their white caption font and "KEYWORD" in yellow
     (one text box, two colours), with an in-animation they like
   - one header text "1 TITLE" (A style), and for B style one big condensed yellow title
   Then run `python3 scripts/harvest_text.py work/text_templates.json <REEL TEMPLATE draft_info.json>`.
   If they'd rather not, fall back to CapCut's own **Auto captions** (they click it once after install) and still
   add the keyword pops + headers from the plan as separate text clips.
3. `build.py` (empty project) → `text_tracks.py work work/build work/build_txt` → `overlays.py` for SFX.
4. `preview.py` with 540x960 (`--size 540x960`). Text tracks aren't drawn by `preview.py`; burn
   `captions.json` on top of the preview with `scripts/burn_preview_captions.py` so the user sees them.

## 7b. Transitions, clip animations, J/L-cuts, section grades

All of these are **cloned from the REEL TEMPLATE project**, never invented. The first time, open the template's
`draft_info.json`, find each object, and note its shape before you write code for it.

- **Transitions:** in the template, a camera segment's `extra_material_refs` points to a `materials.transitions`
  entry (with `duration`, `is_overlap`, `effect_id`/`resource_id`). Clone it onto the segment BEFORE the cut you
  want (whip/zoom-blur at a section turn or a location change in vlogs; never on every jump cut, since hard cuts are the style).
  Keep the transition duration ≤ 0.4 s and ≤ half of either neighbouring clip.
- **Clip animations (B-roll in/out):** a `material_animations` entry with an `animations` list on the B-roll
  segment. Clone it onto each cutaway; the in-animation must not exceed 0.3 s.
- **J-cut / L-cut:** split the camera audio from the picture. Mute the main-track camera segments (volume 0) and
  add the camera file again on an audio track (clone `audio_segment` from the template, `path` = camera file)
  with its own cut list. At a chosen cut, extend the audio segment 0.2–0.6 s **before** the picture cut (J: the
  next line is heard before we see it) or **after** it (L: the voice carries over onto the B-roll / next shot).
  Use J-cuts into each new point and L-cuts out of B-roll. Never overlap two voice segments: one audio track for
  voice, contiguous, no gaps where words are said. Check with `qa.py` that no word is doubled or clipped.
- **Section grades:** add extra adjustment-layer segments (cloned from `adjust_segment`) only over a section,
  e.g. DON'T: saturation -0.35; reflective vlog moment: saturation -1.0 (B&W). Keep the global grade segment, and
  put the section ones on a second adjust track directly above it.
- After adding any of these, run `cct.validate()`, preview, and list in the review which cuts got J/L/transition.

## 8. Thumbnail

`python3 scripts/thumbnail.py <frame.jpg> "<HOOK TEXT>" --style A|B --out work/thumbnail.jpg --font <ttf>`.
Grab the frame with the strongest expression (contact sheet of the hook + key moments). Use fonts from the device
(`fc-list` / `~/Library/Fonts`, or CapCut's cached fonts). Commit the thumbnail next to the footage.

## 9. The review message (one message, Malay)

Send: preview MP4, thumbnail, then a short list:
- format + style used, final length
- what was cut (count of fillers/retakes removed), anything left in that sounds off
- B-roll used: own / Pexels / AI (count, and the AI cost)
- music track names
- the proposed post caption + hashtags per platform
- questions only if something is genuinely ambiguous
Ask with AskUserQuestion: approve → install / change something / split into multiple reels.

## 11. Posting

CapCut must export the final video (the user clicks Export, or tell them the export path to use). Then with Zernio:
`accounts_list` → pick accounts (never guess when there are several on one platform) → `media_generate_upload_link`
→ upload → `validate_post` → `posts_create` (scheduled) or `posts_publish_now`. Always confirm the exact
accounts + caption + time before publishing.
