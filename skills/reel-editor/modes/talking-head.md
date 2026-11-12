# Mode: talking-head

Input: one (or more) camera recordings of the user talking to camera, already in the CapCut project.
Builder: `build.py` (camera on the main track) from capcut-talking-head-edit, then `text_tracks.py`, `overlays.py`.

1. Transcribe the camera audio (`analyze.py --model small`), cut list (`edl.py`), read-back (`qa.py`).
2. Punch-ins and push-ins follow the style's `pacing.punch_in` / `push_in_every_s` (`job.json` `punch`, `zooms`).
3. Cutaways: `inserts` every `pacing.broll_every_s`, each anchored to the words it shows, full-screen fill in 9:16.
4. Captions from `captions.py` with the style's caption rules; titles/headers per the style.
5. Grade = the style's adjustment layer; B&W segments only if the style allows them.
