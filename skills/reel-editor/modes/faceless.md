# Mode: faceless

Input: a script, and/or a voiceover. No face on camera. Visuals are mixed: stock (Pixabay), AI-generated, screen
recordings, the user's own clips or photos. Builder: `build_sequence.py` (visuals on the main track, voice on an audio track).

## 1. Voice
- **User's own recording** (preferred when available): clean it first:
  `ffmpeg -i vo.wav -af "highpass=f=80,afftdn=nf=-25,loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 vo_clean.wav`.
  Cut pauses and retakes the same way as talking-head (`analyze.py` + `edl.py` + `qa.py`, audio only).
- **AI voice:** two routes, ask the user which once:
  - **CapCut Text-to-speech** (no key needed): the user pastes the script into a CapCut text, applies Text-to-speech
    with the voice they like, and quits CapCut; the agent then reads the generated audio from the project's media.
  - **ElevenLabs** (or another TTS API) if `ELEVENLABS_API_KEY` is set in the environment: generate per paragraph,
    join with 0.15 s gaps. Never ask for the key in chat.
- Whatever the source, end with ONE voice file and its word timings (`words.json`).

## 2. Visual plan
Write `visual_plan.json`: one entry per phrase, anchored to word indices, with what to show and where it comes from:
```json
[{"from_word": 0, "to_word": 9, "show": "close-up of a hand counting cash", "source": "stock", "query": "counting money hands"},
 {"from_word": 10, "to_word": 22, "show": "screen: Shopee seller dashboard", "source": "own", "device": "D:/rec/shopee.mp4", "src": 4.0},
 {"from_word": 23, "to_word": 31, "show": "a shop owner staring at an empty store, dusk", "source": "ai"}]
```
- Shots follow the style's `pacing.target_shot_s`: long phrases get 2+ visuals, very short ones merge.
- Source priority: `own` (user's folder) → `stock` (Pixabay) → `ai` (only for shots stock can't cover; count them and the
  cost in the review).
- Run `python3 scripts/faceless_plan.py work styles/<style>/style.json` to turn it into timeline times that cover the
  whole voice with no gaps, snapped to word boundaries.

## 3. Build
Fetch every visual into the footage folder `B-roll (Claude)/`, fill in `device`, `w`, `h`, `file_dur` in
`visual_plan.json` (the plan script keeps them), then `build_sequence.py`. Captions are mandatory in faceless (most
viewers watch muted): use the style's caption rules; with a subtitle-only style, still keep them large enough to read.

## 4. Hook
The first visual must be the strongest image, and the first caption must land in the first 0.3 s.
