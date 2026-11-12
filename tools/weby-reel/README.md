# weby-reel

Edit talking-head reels in the Weby Markets style without CapCut: Python + ffmpeg/libass.
Weby banner on top, video panel below, a title card at the start, UPPERCASE captions with yellow keywords,
alternating punch-ins on jump cuts, voice mastered to -14 LUFS, and the Weby end card.

1. `transcribe.py`: faster-whisper word timings (`WM=large-v3 SUF=_l` for the most accurate BM/rojak).
2. Write a `job.json` (see the examples): word ranges to drop, time ranges to remove, caption fixes, keywords, title, face position.
3. `render.py job.json out.mp4 [--stills t1 t2 ...]`

Needs `assets/` with `banner.png`, `endcard.mp4` and Montserrat fonts (paths are set at the top of `render.py`).
