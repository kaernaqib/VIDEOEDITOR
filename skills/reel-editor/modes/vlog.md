# Mode: vlog

Input: many clips (locations, B-roll, some talking bits) in one folder or already in the CapCut media bin, optionally a
voiceover. Builder: `build_sequence.py` (a sequence of clips on the main track, voice/music on audio tracks).

1. **Inventory:** contact sheet per clip (`ffmpeg ... tile=4x4`), note what each shows, its motion, and whether it has
   usable speech. Transcribe clips with speech (`analyze.py` per clip, or one wav of each).
2. **Story:** from the talking bits / voiceover, write the beats (hook, 3–6 beats, payoff), each with the words that
   anchor it. The hook is the most cinematic shot + the big title.
3. **Music first:** pick the track (Epidemic Sound), run `beats.py` on it, and plan cuts on beats (every 2nd or 4th
   beat for the style's `pacing.target_shot_s`).
4. **Write `sequence.json`** (format in `build_sequence.py`): every clip with its source in/out, timeline a/b, whether its
   own audio is kept (talking bits) or muted (B-roll), and a slow push on stills.
5. **Captions:** subtitle-style only over speech/voiceover; big titles per the style's `titles` rules.
6. Transitions only at location changes (style `transitions.use_on`).
