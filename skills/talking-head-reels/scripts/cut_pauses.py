#!/usr/bin/env python3
"""Tighten the presenter's pauses (the "air") and build the program timeline.

    python3 scripts/cut_pauses.py PROJECT_DIR [--remove 2.40-2.72 --remove 27.40-27.84]
                                              [--threshold DB] [--pause-sentence 0.22] [--pause-mid 0.14]

How it decides: speech is found from the audio energy (10 ms windows), not only from the
transcript, so breaths and lip noise at the edges are not clipped. Every silent gap longer than
0.22 s is shortened to a natural pause: 0.22 s after the end of a sentence, 0.14 s inside one.
--remove cuts arbitrary source ranges (false starts, filler words, repeated takes) - read the
transcript (analysis/asr.json) and pass the ranges you want gone.

Writes:
  analysis/cuts.json           [{src_t0, src_t1, prog_t0}] frame-aligned keep segments (seconds)
  analysis/program_words.json  transcript words re-timed to the program timeline
  audio/program_raw.wav        the cut audio (5 ms fades at every join, no clicks)
"""
import argparse
import math
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import find_ffmpeg, load_json, project_config, run, save_json  # noqa: E402


def energy_db(path):
    import numpy as np
    with wave.open(path, 'rb') as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = 160
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms), len(a) / 16000.0


def main():
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--remove', action='append', default=[], help='source range to delete, e.g. 2.40-2.72')
    ap.add_argument('--threshold', type=float, default=None, help='speech threshold in dBFS (default: auto)')
    ap.add_argument('--pause-sentence', type=float, default=0.22)
    ap.add_argument('--pause-mid', type=float, default=0.14)
    ap.add_argument('--lead', type=float, default=0.06, help='kept before the first word')
    ap.add_argument('--trail', type=float, default=0.25, help='kept after the last word')
    a = ap.parse_args()
    cfg = project_config(a.project)
    P = cfg['project_dir']
    fps = cfg['src_fps'] or cfg['fps']
    db, total = energy_db(os.path.join(P, 'analysis', 'audio16k.wav'))
    words = [w for s in load_json(os.path.join(P, 'analysis', 'asr.json')) for w in s['words']]
    if not words:
        sys.exit('ERROR: empty transcript - run transcribe.py first')

    p5, p95 = float(np.percentile(db, 5)), float(np.percentile(db, 95))
    thr = a.threshold if a.threshold is not None else p5 + 0.5 * (p95 - p5)    # halfway between room tone and loud speech
    sp = db > thr
    regs, i, n = [], 0, len(db)
    while i < n:
        if sp[i]:
            j = i
            while j < n and sp[j]:
                j += 1
            regs.append([i / 100.0, j / 100.0])
            i = j
        else:
            i += 1
    m = []
    for r in regs:                                   # merge tiny gaps, drop blips
        if m and r[0] - m[-1][1] < 0.12:
            m[-1][1] = r[1]
        else:
            m.append(r)
    m = [r for r in m if r[1] - r[0] >= 0.05]
    # keep only energy regions that touch the transcript (ignores bumps, coughs before the first word)
    w0, w1 = words[0]['s'], words[-1]['e']
    m = [r for r in m if r[1] >= w0 - 0.3 and r[0] <= w1 + 0.3]
    if not m:
        sys.exit('ERROR: no speech found above %.1f dB - pass --threshold' % thr)

    def punct_before(t):
        prev = [w for w in words if w['e'] <= t + 0.15]
        return prev[-1]['w'].strip()[-1:] if prev else ''

    keeps, cur = [], [max(0.0, m[0][0] - a.lead), None]
    for k in range(1, len(m)):
        g0, g1 = m[k - 1][1], m[k][0]
        gap = g1 - g0
        if gap <= 0.22:
            continue
        target = a.pause_sentence if punct_before(g0) in '.?!' else a.pause_mid
        if gap - target < 0.12:
            continue
        tail = min(0.08, target / 2)
        cur[1] = g0 + tail
        keeps.append(cur)
        cur = [g1 - (target - tail), None]
    cur[1] = min(total, m[-1][1] + a.trail)
    keeps.append(cur)

    removes = []
    for r in a.remove:
        x, y = (float(v) for v in r.split('-'))
        removes.append((x, y))
    out = []
    for s0, s1 in keeps:
        segs = [[s0, s1]]
        for x, y in removes:
            new = []
            for u0, u1 in segs:
                if y <= u0 or x >= u1:
                    new.append([u0, u1])
                else:
                    if x > u0:
                        new.append([u0, x])
                    if y < u1:
                        new.append([y, u1])
            segs = new
        out += segs
    q = []                                            # quantize to source frames
    for s0, s1 in out:
        f0, f1 = math.floor(s0 * fps + 1e-6), math.ceil(s1 * fps - 1e-6)
        if f1 - f0 >= 2:
            if q and f0 <= q[-1][1]:
                q[-1][1] = max(q[-1][1], f1)
            else:
                q.append([f0, f1])
    cuts, prog = [], 0
    for f0, f1 in q:
        cuts.append(dict(src_t0=round(f0 / fps, 5), src_t1=round(f1 / fps, 5), prog_t0=round(prog / fps, 5)))
        prog += f1 - f0
    prog_dur = prog / fps
    save_json(cuts, os.path.join(P, 'analysis', 'cuts.json'))

    pw = []                                           # transcript on the program timeline
    for w in words:
        mid = (w['s'] + w['e']) / 2
        for c in cuts:
            if c['src_t0'] - 0.02 <= mid < c['src_t1']:
                off = c['prog_t0'] - c['src_t0']
                pw.append(dict(s=round(max(c['prog_t0'], w['s'] + off), 3), e=round(min(c['prog_t0'] + c['src_t1'] - c['src_t0'], w['e'] + off), 3),
                               w=w['w'], p=w.get('p', 1)))
                break
    save_json(pw, os.path.join(P, 'analysis', 'program_words.json'))

    ff = find_ffmpeg()                                # cut audio with micro-fades at every join
    src = os.path.join(P, 'audio', 'source_48k.wav')
    parts, labels = [], []
    for k, c in enumerate(cuts):
        d = c['src_t1'] - c['src_t0']
        parts.append('[0:a]atrim=%.5f:%.5f,asetpts=PTS-STARTPTS,afade=t=in:d=0.005,afade=t=out:st=%.5f:d=0.005[a%d]'
                     % (c['src_t0'], c['src_t1'], max(0, d - 0.005), k))
        labels.append('[a%d]' % k)
    fc = ';'.join(parts) + ';' + ''.join(labels) + 'concat=n=%d:v=0:a=1[out]' % len(cuts)
    script = os.path.join(P, 'analysis', 'cut_audio.ffscript')
    with open(script, 'w') as fh:
        fh.write(fc)
    run([ff, '-v', 'error', '-y', '-i', src, '-filter_complex_script', script, '-map', '[out]',
         '-c:a', 'pcm_s24le', '-ar', '48000', os.path.join(P, 'audio', 'program_raw.wav')])

    print('threshold %.1f dB (room %.1f, speech %.1f)' % (thr, p5, p95))
    print('segments %d   program %.2f s   (source %.2f s, removed %.2f s)\n' % (len(cuts), prog_dur, total, total - prog_dur))
    for c in cuts:
        txt = ' '.join(w['w'].strip() for w in words if c['src_t0'] - 0.05 <= w['s'] < c['src_t1'] - 0.05)
        print('%6.2f-%6.2f -> %6.2f  %s' % (c['src_t0'], c['src_t1'], c['prog_t0'], txt[:90]))
    cfg['program_dur'] = round(prog_dur, 4)
    save_json(cfg, os.path.join(P, 'project.json'))


if __name__ == '__main__':
    main()
