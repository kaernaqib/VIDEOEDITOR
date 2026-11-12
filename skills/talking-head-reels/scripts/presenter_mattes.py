#!/usr/bin/env python3
"""Face track + presenter mattes (Apple Vision), used for words behind the head, cut-outs and silhouette flashes.

    python3 scripts/presenter_mattes.py PROJECT_DIR [--width 1920]

Writes:
  analysis/faces.jsonl         one line per source frame: {"f", "x", "y", "w", "h"} (normalised, top-left origin)
  matte/presenter_body.mov     whole person, edge-refined against the picture (guided filter), steady (3-frame median)
  matte/presenter_head.mov     head and hair only (person matte x smoothed head ellipse), crisp edge

The mattes cover the full source recording (same timeline as the presenter clip), at --width
(default: 1920, or the source width if smaller). The builder scales them to match the presenter.
Runtime is roughly 2-4x real time.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import box_blur, find_ffmpeg, project_config, save_json, write_gray_prores  # noqa: E402
from vision_tools import tool, upright_proxy  # noqa: E402


def main():
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--width', type=int, default=1920)
    a = ap.parse_args()
    cfg = project_config(a.project)
    P = cfg['project_dir']
    ff = find_ffmpeg()
    sw, sh = cfg['src_w'], cfg['src_h']
    mw = min(a.width, sw)
    mw -= mw % 2
    mh = int(round(sh * mw / sw / 2)) * 2
    fps = cfg['src_fps'] or cfg['fps']

    proxy = os.path.join(P, 'analysis', 'presenter_proxy.mov')
    print('1/3 upright proxy %dx%d' % (mw, mh), flush=True)
    upright_proxy(ff, cfg['presenter'], proxy, mw, mh, fps)

    print('2/3 Vision face track + person segmentation', flush=True)
    faces_path = os.path.join(P, 'analysis', 'faces.jsonl')
    raw_path = os.path.join(P, 'analysis', 'person_raw.mov')
    tr = subprocess.Popen([tool('person_track'), proxy, faces_path, str(mw), str(mh)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    wr = write_gray_prores(ff, mw, mh, fps, raw_path)
    while True:
        b = tr.stdout.read(mw * mh)
        if len(b) < mw * mh:
            break
        wr.stdin.write(b)
    wr.stdin.close(); wr.wait(); tr.wait()

    faces = [json.loads(l) for l in open(faces_path)]
    have = [f for f in faces if 'x' in f]
    if len(have) < len(faces) * 0.5:
        print('WARNING: a face was found in only %d of %d frames - head matte and framing may be off' % (len(have), len(faces)))
    last = have[0] if have else dict(x=0.5, y=0.35, w=0.12, h=0.2)
    for f in faces:                                  # fill frames without a detection with the previous face
        if 'x' in f:
            last = f
        else:
            f.update(x=last['x'], y=last['y'], w=last['w'], h=last['h'])

    def smooth(key, n=9):
        arr = np.array([f[key] for f in faces], dtype=np.float32)
        pad = np.pad(arr, n // 2, mode='edge')
        return np.convolve(pad, np.ones(n) / n, mode='valid')
    fx, fy, fwid, fhei = smooth('x'), smooth('y'), smooth('w'), smooth('h')
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)

    print('3/3 refining body + head mattes', flush=True)
    rim = subprocess.Popen([ff, '-v', 'error', '-i', proxy, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    rma = subprocess.Popen([ff, '-v', 'error', '-i', raw_path, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    wb = write_gray_prores(ff, mw, mh, fps, os.path.join(P, 'matte', 'presenter_body.mov'))
    wh = write_gray_prores(ff, mw, mh, fps, os.path.join(P, 'matte', 'presenter_head.mov'))
    hist, n = [], 0
    r, eps = max(3, mw // 320), 0.002
    while True:
        ib, mb = rim.stdout.read(mw * mh * 3), rma.stdout.read(mw * mh)
        if len(ib) < mw * mh * 3 or len(mb) < mw * mh:
            break
        img = np.frombuffer(ib, np.uint8).reshape(mh, mw, 3).astype(np.float32) / 255
        p = np.frombuffer(mb, np.uint8).reshape(mh, mw).astype(np.float32) / 255
        I = img.mean(2)                                  # guided filter: matte edges follow the picture's edges
        mI, mp = box_blur(I, r), box_blur(p, r)
        A = (box_blur(I * p, r) - mI * mp) / (box_blur(I * I, r) - mI * mI + eps)
        q = np.clip(box_blur(A, r) * I + box_blur(mp - A * mI, r), 0, 1)
        q = np.clip((q - 0.42) / 0.22, 0, 1)
        q = q * q * (3 - 2 * q)
        hist.append(q)
        hist = hist[-3:]
        body = np.median(np.stack(hist), 0) if len(hist) == 3 else q
        wb.stdin.write((body * 255 + 0.5).astype(np.uint8).tobytes())
        i = min(n, len(faces) - 1)
        cx, cy, w, h = fx[i] * mw, fy[i] * mh, fwid[i] * mw, fhei[i] * mh
        e = ((xx - cx) / (0.98 * w)) ** 2 + ((yy - (cy - 0.22 * h)) / (1.40 * h)) ** 2
        head = body * np.clip((1.12 - e) / 0.12, 0, 1)
        head = np.clip((head - 0.35) / 0.30, 0, 1)
        head = box_blur(head * head * (3 - 2 * head), 1)
        wh.stdin.write((head * 255 + 0.5).astype(np.uint8).tobytes())
        n += 1
        if n % 250 == 0:
            print('   frame %d' % n, flush=True)
    for w_ in (wb, wh):
        w_.stdin.close(); w_.wait()
    with open(faces_path, 'w') as fh:
        for f in faces:
            fh.write(json.dumps(f) + '\n')
    cfg.update(matte_w=mw, matte_h=mh, faces='analysis/faces.jsonl', matte_body='matte/presenter_body.mov', matte_head='matte/presenter_head.mov')
    save_json(cfg, os.path.join(P, 'project.json'))
    for tmp in (raw_path, proxy):
        try:
            os.remove(tmp)
        except OSError:
            pass
    print('done: %d frames, mattes %dx%d' % (n, mw, mh))


if __name__ == '__main__':
    main()
