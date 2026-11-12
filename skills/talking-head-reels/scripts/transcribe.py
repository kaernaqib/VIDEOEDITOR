#!/usr/bin/env python3
"""Word-level transcript of the presenter with faster-whisper.

    python3 scripts/transcribe.py PROJECT_DIR [--model small] [--language en]

Writes analysis/asr.json: [{start, end, text, words: [{s, e, w, p}]}] in source seconds.
The first run downloads the model (internet needed once). For noisy rooms or accents use
--model medium or large-v3 (slower on CPU, better word timing).
"""
import argparse
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import project_config, save_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--model', default=None, help='faster-whisper model name or local path (default: small / small.en)')
    ap.add_argument('--language', default=None, help='spoken language code, e.g. en; omit to auto-detect')
    ap.add_argument('--threads', type=int, default=8)
    a = ap.parse_args()
    cfg = project_config(a.project)
    import numpy as np
    from faster_whisper import WhisperModel

    model_name = a.model or ('small.en' if a.language == 'en' else 'small')
    model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=a.threads)
    with wave.open(os.path.join(cfg['project_dir'], 'analysis', 'audio16k.wav'), 'rb') as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, info = model.transcribe(audio, language=a.language, beam_size=5, word_timestamps=True,
                                  vad_filter=False, condition_on_previous_text=False)
    res = []
    for s in segs:
        res.append(dict(start=s.start, end=s.end, text=s.text,
                        words=[dict(s=w.start, e=w.end, w=w.word, p=w.probability) for w in (s.words or [])]))
        print('%6.2f-%6.2f %s' % (s.start, s.end, s.text), flush=True)
    save_json(res, os.path.join(cfg['project_dir'], 'analysis', 'asr.json'))
    cfg['language'] = info.language
    save_json(cfg, os.path.join(cfg['project_dir'], 'project.json'))
    print('\nlanguage: %s   words: %d' % (info.language, sum(len(r['words']) for r in res)))


if __name__ == '__main__':
    main()
