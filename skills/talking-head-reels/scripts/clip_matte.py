#!/usr/bin/env python3
"""Matte for a B-roll clip (Apple Vision): cut-out silhouettes, text between subject and background,
or coloured figures over a black-and-white clip.

    python3 scripts/clip_matte.py CLIP.mp4 OUT_matte.mov --mode person|subject|largest|colorful [--smooth]

Modes
  person    people only (person segmentation) - best for crowds, dancers, fighters
  subject   every foreground subject (people, animals, objects) - "subject lifting"
  largest   only the biggest foreground subject - one hero object/person
  colorful  saturated foreground objects (e.g. coloured 3D characters) - for colour-on-B&W shots
--smooth    rounder outline, no flickering strands (masks, hair, fabric)

The matte has the clip's own size and frame rate, so in the EDL it simply rides along with the
clip ("cutout_matte" or "color_figures_matte"); the builder applies the same framing to both.
Timing is centred (previous/current/next frame) so the matte never lags the motion.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import box_blur, find_ffmpeg, probe, write_gray_prores  # noqa: E402
from vision_tools import tool, upright_proxy  # noqa: E402


def main():
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument('clip')
    ap.add_argument('out')
    ap.add_argument('--mode', choices=('person', 'subject', 'largest', 'colorful'), default='subject')
    ap.add_argument('--smooth', action='store_true')
    a = ap.parse_args()
    ff = find_ffmpeg()
    info = probe(a.clip, ff)
    W, H, fps = info['w'], info['h'], info['fps'] or 25
    W -= W % 2
    H -= H % 2
    proxy = os.path.splitext(a.out)[0] + '_proxy.mov'
    upright_proxy(ff, a.clip, proxy, W, H, fps)
    if a.mode == 'person':
        cmd = [tool('person_track'), proxy, os.devnull, str(W), str(H)]
    elif a.mode == 'largest':
        cmd = [tool('largest_subject_mask'), proxy, str(W), str(H)]
    else:
        cmd = [tool('subject_mask'), proxy, str(W), str(H)]
    src = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    rgb = subprocess.Popen([ff, '-v', 'error', '-i', proxy, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE) \
        if a.mode == 'colorful' else None
    frames = []
    while True:
        b = src.stdout.read(W * H)
        if len(b) < W * H:
            break
        m = np.frombuffer(b, np.uint8).reshape(H, W).astype(np.float32) / 255
        if rgb is not None:
            rb = rgb.stdout.read(W * H * 3)
            img = np.frombuffer(rb, np.uint8).reshape(H, W, 3).astype(np.float32) / 255
            mx, mn = img.max(2), img.min(2)
            sat = (mx - mn) / (mx + 1e-6)
            c = ((sat > 0.45) & (mx > 0.25)).astype(np.float32)
            c = c * (box_blur(c, 30) < 0.45)               # drop big flat coloured areas (sky, walls, posters)
            m = np.clip(box_blur(c * (m > 0.5), 2) * 2.2, 0, 1)
        if a.smooth:
            m = (box_blur(m, 9) > 0.5).astype(np.float32)
            m = np.clip((box_blur(m, 3) - 0.3) / 0.4, 0, 1)
        frames.append(m.astype(np.float16))
    src.wait()
    if not frames:
        sys.exit('ERROR: no frames decoded from ' + a.clip)
    A = np.stack(frames).astype(np.float32)
    span = 4 if a.smooth else 1
    wr = write_gray_prores(ff, W, H, fps, a.out)
    for i in range(len(A)):
        o = np.median(A[max(0, i - span):i + span + 1], 0)
        o = np.clip((box_blur(o, 2) - 0.55) / 0.3, 0, 1)    # choke 1-2 px: no fringe of the old background
        wr.stdin.write((o * 255 + 0.5).astype(np.uint8).tobytes())
    wr.stdin.close(); wr.wait()
    os.remove(proxy)
    print('matte %s: %d frames %dx%d (%s%s)' % (a.out, len(A), W, H, a.mode, ', smooth' if a.smooth else ''))


if __name__ == '__main__':
    main()
