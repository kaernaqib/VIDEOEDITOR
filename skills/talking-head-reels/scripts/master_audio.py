#!/usr/bin/env python3
"""Master the cut voice-over to -14 LUFS (the loudness Instagram / TikTok / Shorts normalise to).

    python3 scripts/master_audio.py PROJECT_DIR [--lufs -14] [--true-peak -1.5]

Two-pass ffmpeg loudnorm with a gentle 70 Hz high-pass and 16 kHz low-pass.
Writes audio/program_master.wav and prints the measured result.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import find_ffmpeg, project_config, run, save_json  # noqa: E402


def measure(ff, path, pre):
    err = subprocess.run([ff, '-hide_banner', '-nostats', '-i', path, '-af', pre + 'loudnorm=print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    return json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', err, re.S).group(0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--lufs', type=float, default=-14.0)
    ap.add_argument('--true-peak', type=float, default=-1.5)
    a = ap.parse_args()
    cfg = project_config(a.project)
    P = cfg['project_dir']
    ff = find_ffmpeg()
    src = os.path.join(P, 'audio', 'program_raw.wav')
    dst = os.path.join(P, 'audio', 'program_master.wav')
    pre = 'highpass=f=70,lowpass=f=16000,'
    m = measure(ff, src, pre)
    ln = ('loudnorm=I=%.1f:TP=%.1f:LRA=9:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true'
          % (a.lufs, a.true_peak, m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']))
    run([ff, '-v', 'error', '-y', '-i', src, '-af', pre + ln, '-ar', '48000', '-c:a', 'pcm_s24le', dst])
    r = measure(ff, dst, '')
    miss = a.lufs - float(r['input_i'])
    if abs(miss) > 0.3:                  # loud peaks kept loudnorm short of the target: trim gain, then a soft peak limiter
        tmp = dst.replace('.wav', '_tmp.wav')
        os.replace(dst, tmp)
        lim = 10 ** (a.true_peak / 20.0)
        run([ff, '-v', 'error', '-y', '-i', tmp, '-af', 'volume=%.2fdB,alimiter=limit=%.4f:attack=3:release=60:level=disabled' % (miss, lim),
             '-ar', '48000', '-c:a', 'pcm_s24le', dst])
        os.remove(tmp)
        r = measure(ff, dst, '')
    print('before: %s LUFS, peak %s dBTP' % (m['input_i'], m['input_tp']))
    print('after : %s LUFS, peak %s dBTP  -> %s' % (r['input_i'], r['input_tp'], dst))
    cfg['audio'] = 'audio/program_master.wav'
    save_json(cfg, os.path.join(P, 'project.json'))


if __name__ == '__main__':
    main()
