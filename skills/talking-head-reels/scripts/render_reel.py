#!/usr/bin/env python3
"""Render the reel straight from the EDL - no editing app. Python + numpy composite every frame,
libass (inside ffmpeg) draws the kinetic type, ffmpeg decodes and encodes.

    python3 scripts/render_reel.py PROJECT/edl.json --out PROJECT/render/NAME_vN.mp4 [--workers 6]
    python3 scripts/render_reel.py PROJECT/edl.json --stills 3.2 10.5 47.1 [--out-dir PROJECT/qa/stills]

--stills renders only those moments to PNG (plus a contact sheet) - use it for every check
before a full render. A full 75 s reel takes a few minutes with several workers.
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import find_ffmpeg, probe  # noqa: E402
from reel_plan import TD, build_plan  # noqa: E402
import textass  # noqa: E402
from textass import bez, ramp  # noqa: E402

SHUTTER = 220 / 360.0


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0


# ----------------------------------------------------------------------------------------------- media
class Reader:
    """Sequential frame reader with re-seek; frames as float32 arrays (H, W, C) in 0..1."""

    def __init__(self, ff, path, fps, w, h, crop=None, gray=False, out_size=None):
        self.ff, self.path, self.fps, self.gray = ff, path, fps, gray
        self.crop, self.out_size = crop, out_size
        self.w, self.h = (out_size or ((crop[0], crop[1]) if crop else (w, h)))
        self.p, self.k, self.cur = None, -10, None

    def _open(self, k):
        if self.p:
            self.p.kill()
        vf = []
        if self.crop:
            vf.append('crop=%d:%d:%d:%d' % tuple(self.crop))
        if self.out_size:
            vf.append('scale=%d:%d:flags=bicubic' % self.out_size)
        args = [self.ff, '-v', 'error', '-ss', '%.4f' % (k / self.fps), '-i', self.path, '-an']
        if vf:
            args += ['-vf', ','.join(vf)]
        args += ['-f', 'rawvideo', '-pix_fmt', 'gray' if self.gray else 'rgb24', '-']
        self.p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        self.k = k - 1

    def frame(self, t):
        k = max(0, int(round(t * self.fps + 1e-6)))
        if self.p is None or k < self.k or k - self.k > 50:
            self._open(k)
        nb = self.w * self.h * (1 if self.gray else 3)
        while self.k < k:
            buf = self.p.stdout.read(nb)
            if len(buf) < nb:
                break                                      # past the end: keep the last frame
            self.cur = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, *(() if self.gray else (3,)))
            self.k += 1
        if self.cur is None:
            return np.zeros((self.h, self.w) + (() if self.gray else (3,)), np.float32)
        self.k = k
        return self.cur.astype(np.float32) / 255.0

    def close(self):
        if self.p:
            self.p.kill()


def src_time(spec, tau, cdur):
    """Source time of a clip at local time tau. 'speed' = source seconds per second (1 = real time);
    a clip too short for its slot is slowed down (up to 4x) so it never runs out."""
    sp = float(spec.get('speed') or 1.0)
    t_in = spec.get('t_in') or 0
    avail = (spec.get('srcdur') or 99) - t_in - 0.04
    need = cdur * sp
    st = min(400.0, need / avail * 100) if avail < need else 100.0
    return t_in + tau * sp * 100.0 / st


def load_rgba(ff, path, max_side=None):
    info = probe(path, ff)
    w, h = info['w'], info['h']
    vf = []
    if max_side and max(w, h) > max_side:
        f = max_side / float(max(w, h))
        w, h = max(2, int(w * f)), max(2, int(h * f))
        vf = ['-vf', 'scale=%d:%d:flags=area' % (w, h)]
    out = subprocess.run([ff, '-v', 'error', '-i', path] + vf + ['-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(out, np.uint8).reshape(h, w, 4).astype(np.float32) / 255.0


# ----------------------------------------------------------------------------------------------- pixels
def sample(img, ow, oh, ax, ay, sx, sy, px, py):
    """Draw img so that its pixel (ax, ay) lands at (px, py) scaled by (sx, sy). Returns (x0, y0, patch, cover)."""
    h, w = img.shape[:2]
    X0 = px + (0 - ax) * sx
    X1 = px + (w - ax) * sx
    Y0 = py + (0 - ay) * sy
    Y1 = py + (h - ay) * sy
    x0, x1 = max(0, int(math.floor(min(X0, X1)))), min(ow, int(math.ceil(max(X0, X1))))
    y0, y1 = max(0, int(math.floor(min(Y0, Y1)))), min(oh, int(math.ceil(max(Y0, Y1))))
    if x1 <= x0 or y1 <= y0:
        return None
    xs = ax + (np.arange(x0, x1, dtype=np.float32) + 0.5 - px) / sx - 0.5
    ys = ay + (np.arange(y0, y1, dtype=np.float32) + 0.5 - py) / sy - 0.5
    if sx < 0.6 or sy < 0.6:                                # strong downscale: pre-shrink to avoid aliasing
        f = max(1, int(1.0 / max(sx, sy, 0.05)))
        if f > 1:
            hh, ww = (h // f) * f, (w // f) * f
            small = img[:hh, :ww].reshape(hh // f, f, ww // f, f, *img.shape[2:]).mean(axis=(1, 3))
            return sample(small, ow, oh, ax / f, ay / f, sx * f, sy * f, px, py)
    xi = np.floor(xs).astype(np.int32)
    yi = np.floor(ys).astype(np.int32)
    fx = (xs - xi)
    fy = (ys - yi)
    xa, xb = np.clip(xi, 0, w - 1), np.clip(xi + 1, 0, w - 1)
    ya, yb = np.clip(yi, 0, h - 1), np.clip(yi + 1, 0, h - 1)
    r0, r1 = img[ya], img[yb]
    if img.ndim == 3:
        fx3, fy3 = fx[None, :, None], fy[:, None, None]
    else:
        fx3, fy3 = fx[None, :], fy[:, None]
    top = r0[:, xa] * (1 - fx3) + r0[:, xb] * fx3
    bot = r1[:, xa] * (1 - fx3) + r1[:, xb] * fx3
    patch = top * (1 - fy3) + bot * fy3
    return x0, y0, patch, None


def over(canvas, patch, x0, y0, alpha=None, opacity=1.0):
    h, w = patch.shape[:2]
    reg = canvas[y0:y0 + h, x0:x0 + w]
    if patch.shape[2] == 4:
        a = patch[:, :, 3:4] * opacity
        rgb = patch[:, :, :3]
    else:
        a = (alpha[:, :, None] if alpha is not None else np.ones((h, w, 1), np.float32)) * opacity
        rgb = patch
    reg *= (1 - a)
    reg += rgb * a


def put(canvas, img, ax, ay, s, px, py, opacity=1.0, sy=None, mblur=0.0):
    r = sample(img, canvas.shape[1], canvas.shape[0], ax, ay, s, s if sy is None else sy, px, py)
    if not r:
        return
    x0, y0, patch, _ = r
    if mblur > 1.5:
        patch = hblur(patch, int(mblur))
    over(canvas, patch, x0, y0, opacity=opacity)


def hblur(a, n):
    n = max(1, min(n, a.shape[1] - 1))
    c = np.cumsum(np.pad(a, ((0, 0), (n // 2 + 1, n - n // 2), (0, 0)), mode='edge'), axis=1)
    return (c[:, n:n + a.shape[1]] - c[:, :a.shape[1]]) / n


def blur(a, r):
    """Fast separable box blur (3 passes ~ gaussian)."""
    r = int(max(0, r))
    if r < 1:
        return a
    out = a
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(out.ndim)], mode='edge'), axis=ax)
            n = out.shape[ax]
            out = (np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, range(0, n), axis=ax)) / (2 * r + 1)
    return out


def contrast(x, c):
    k = 1 + c / 100.0
    return np.clip((x - 0.5) * k + 0.5, 0, 1)


def treat_bw(rgb, black, white):
    y = rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114
    y = contrast(y, 42)
    return black + (white - black) * y[:, :, None]


def treat_color(rgb, c=22, sat=-18):
    rgb = contrast(rgb, c)
    y = (rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114)[:, :, None]
    return np.clip(y + (rgb - y) * (1 + sat / 100.0), 0, 1)


def noise(canvas, amt, rng):
    n = (rng.random(canvas.shape[:2], dtype=np.float32) * 2 - 1) * (amt / 100.0)
    canvas += n[:, :, None]
    np.clip(canvas, 0, 1, out=canvas)


def rrect_sdf(W, H, cx, cy, w, h, r):
    xs = np.arange(W, dtype=np.float32)[None, :] + 0.5 - cx
    ys = np.arange(H, dtype=np.float32)[:, None] + 0.5 - cy
    qx, qy = np.abs(xs) - w / 2 + r, np.abs(ys) - h / 2 + r
    return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r


def draw_rect(canvas, cx, cy, w, h, col, stroke=None, round_=0.0, scale=1.0, opacity=1.0):
    w, h, round_ = w * scale, h * scale, round_ * scale
    d = rrect_sdf(canvas.shape[1], canvas.shape[0], cx, cy, w, h, round_)
    if stroke:
        sw = stroke * scale
        a = np.clip(sw / 2 + 0.5 - np.abs(d), 0, 1)
    else:
        a = np.clip(0.5 - d, 0, 1)
    a *= opacity
    canvas *= (1 - a[:, :, None])
    canvas += col * a[:, :, None]


def draw_ring(canvas, cx, cy, rad, sw, col, end):
    W, H = canvas.shape[1], canvas.shape[0]
    xs = np.arange(W, dtype=np.float32)[None, :] + 0.5 - cx
    ys = np.arange(H, dtype=np.float32)[:, None] + 0.5 - cy
    r = np.sqrt(xs * xs + ys * ys)
    a = np.clip(sw / 2 + 0.5 - np.abs(r - rad), 0, 1)
    ang = (np.degrees(np.arctan2(xs, -ys)) + 360) % 360           # 0 at 12 o'clock, clockwise
    a = a * (ang <= end * 3.6)
    canvas *= (1 - a[:, :, None])
    canvas += col * a[:, :, None]


# ----------------------------------------------------------------------------------------------- renderer
class Renderer:
    def __init__(self, plan, cache):
        self.p, self.cache = plan, cache
        self.ff = find_ffmpeg()
        self.W, self.H, self.fps = plan['W'], plan['H'], plan['fps']
        self.black, self.white = hexrgb(plan['bw_black']), hexrgb(plan['bw_white'])
        self.accent, self.uibg = hexrgb(plan['accent']), hexrgb(plan['ui_bg'])
        self.readers, self.stills, self.logo_img = {}, {}, {}
        self.rng = np.random.default_rng(7)
        pr = plan['presenter']
        self.crop = self._presenter_crop()
        cw, ch, cx, cy = self.crop
        self.pres = Reader(self.ff, pr['src'], pr['fps'], pr['w'], pr['h'], crop=self.crop)
        self.mattes = {}
        for k, m in plan['mattes'].items():
            d = m['div']
            mc = (int(round(cw / d)) // 2 * 2, int(round(ch / d)) // 2 * 2, int(round(cx / d)), int(round(cy / d)))
            mc = (min(mc[0], m['w'] - mc[2]), min(mc[1], m['h'] - mc[3]), mc[2], mc[3])
            self.mattes[k] = (Reader(self.ff, m['src'], m['fps'], m['w'], m['h'], crop=mc, gray=True), d, mc)
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        e = np.sqrt(((xx - self.W / 2) / (self.W * 0.44)) ** 2 + ((yy - self.H / 2) / (self.H * 0.48)) ** 2)
        dist = (e - 1) * min(self.W * 0.44, self.H * 0.48)
        self.vignette = np.clip((dist + 130) / 260.0, 0, 1) * (plan['look'].get('vignette', 0) / 100.0)
        self.halftone = None
        if plan['look'].get('halftone'):
            ht = load_rgba(self.ff, plan['look']['halftone'])
            if ht.shape[:2] != (self.H, self.W):
                r = sample(ht, self.W, self.H, 0, 0, self.W / ht.shape[1], self.H / ht.shape[0], 0, 0)
                ht = r[2]
            self.halftone = ht
        self.ins_text = {}

    # --- presenter
    def _presenter_crop(self):
        p = self.p
        pr = p['presenter']
        xs0, xs1, ys0, ys1 = [], [], [], []
        for pcs, h in ((p['pieces'], self.H), (p['pieces_half'], self.H // 2)):
            for pc in pcs:
                s = pc['s0'] / 1.004
                xs0.append(pc['ax'] - (self.W / 2) / s)
                xs1.append(pc['ax'] + (self.W / 2) / s)
                ys0.append(pc['ay'] - pc['y0'] / s)
                ys1.append(pc['ay'] + (h - pc['y0']) / s)
        x0 = max(0, int(min(xs0)) - 8)
        x1 = min(pr['w'], int(max(xs1)) + 8)
        y0 = max(0, int(min(ys0)) - 8)
        y1 = min(pr['h'], int(max(ys1)) + 8)
        w, h = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
        return (w, h, x0, y0)

    def piece(self, pcs, t):
        for pc in pcs:
            if pc['t0'] - 1e-6 <= t < pc['t1'] - 1e-6:
                return pc
        return pcs[-1] if t >= pcs[-1]['t1'] else pcs[0]

    def presenter(self, t, half=False, base=100.0, matte=None, h=None):
        """Presenter (or one of its mattes) at program time t on a canvas W x h. base = punch-in scale %."""
        pcs = self.p['pieces_half'] if half else self.p['pieces']
        h = h or (self.H // 2 if half else self.H)
        pc = self.piece(pcs, t)
        u = (t - pc['t0']) / max(pc['t1'] - pc['t0'] - 1.0 / self.fps, 1e-3)
        s = pc['s0'] + (pc['s1'] - pc['s0']) * min(1.0, max(0.0, u))
        k = base / 100.0
        cw, ch, cx, cy = self.crop
        if matte:
            rd, d, mc = self.mattes[matte]
            img = rd.frame(t + pc['off'])
            ax, ay, S = (pc['ax'] - cx) / d, (pc['ay'] - cy) / d, s * d * k
        else:
            img = self.pres.frame(t + pc['off'])
            ax, ay, S = pc['ax'] - cx, pc['ay'] - cy, s * k
        py = h / 2 + k * (pc['y0'] - h / 2)
        canvas = np.zeros((h, self.W) if matte else (h, self.W, 3), np.float32)
        r = sample(img, self.W, h, ax, ay, S, S, self.W / 2, py)
        if r:
            x0, y0, patch, _ = r
            canvas[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
        return canvas

    def base_scale(self, t):
        keys = self.p['base_keys']
        v = 100.0
        if keys:
            if t <= keys[0][0]:
                v = keys[0][1]
            elif t >= keys[-1][0]:
                v = keys[-1][1]
            else:
                for (ta, va), (tb, vb) in zip(keys, keys[1:]):
                    if ta <= t < tb:
                        v = va + (vb - va) * bez((t - ta) / max(tb - ta, 1e-6), 0.8, 0.8)
                        break
        return max(v, 100.4)

    # --- clips
    def reader(self, path, fps, w, h):
        key = path
        if key not in self.readers:
            self.readers[key] = Reader(self.ff, path, fps, w, h)
        return self.readers[key]

    def still(self, path, max_side=2400):
        if path not in self.stills:
            self.stills[path] = load_rgba(self.ff, path, max_side)
        return self.stills[path]

    def clip(self, spec, w, h, tau, cdur):
        """A clip precomp: the clip covering w x h, slow push, B&W or colour, at local time tau."""
        z0, z1 = (spec.get('zoom') or [1.0, 1.08])
        z = z0 + (z1 - z0) * min(1.0, max(0.0, tau / max(cdur, 1e-3)))

        def frame_of(path, sw, sh, fps, gray=False):
            if spec.get('still') and not gray:
                return self.still(path)[:, :, :3]
            tsrc = src_time(spec, tau, cdur)
            key = path + ('#g' if gray else '')
            if key not in self.readers:
                self.readers[key] = Reader(self.ff, path, fps, sw, sh, gray=gray)
            return self.readers[key].frame(tsrc)

        def place(img, sw, sh):
            s = max(w / sw, h / sh)
            offx = (0.5 - spec['fx']) * max(0, sw * s - w) if spec.get('fx') is not None else 0
            out = np.zeros((h, w) + img.shape[2:], np.float32)
            r = sample(img, w, h, sw / 2, sh / 2, s * z, s * z, w / 2 + offx, h / 2)
            if r:
                x0, y0, patch, _ = r
                out[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
            return out
        src = frame_of(spec['abs'], spec['w'], spec['h'], spec['fps'])
        img = place(src, spec['w'], spec['h'])
        if spec.get('color'):
            out = treat_color(img)
        else:
            out = treat_bw(img, self.black, self.white)
            if spec.get('color_figures_matte_abs'):
                m = frame_of(spec['color_figures_matte_abs'], spec['color_figures_matte_w'], spec['color_figures_matte_h'],
                             spec['color_figures_matte_fps'], gray=True)
                mm = place(m, spec['color_figures_matte_w'], spec['color_figures_matte_h'])[:, :, None]
                out = out * (1 - mm) + contrast(img, 15) * mm
        return out

    def cut_matte(self, spec, w, h, tau, cdur):
        z0, z1 = (spec.get('zoom') or [1.0, 1.08])
        z = z0 + (z1 - z0) * min(1.0, max(0.0, tau / max(cdur, 1e-3)))
        sw, sh = spec['cutout_matte_w'], spec['cutout_matte_h']
        key = spec['cutout_matte_abs'] + '#g'
        if key not in self.readers:
            self.readers[key] = Reader(self.ff, spec['cutout_matte_abs'], spec['cutout_matte_fps'], sw, sh, gray=True)
        m = self.readers[key].frame(src_time(spec, tau, cdur))
        s = max(w / sw, h / sh)
        offx = (0.5 - spec['fx']) * max(0, sw * s - w) if spec.get('fx') is not None else 0
        out = np.zeros((h, w), np.float32)
        r = sample(m, w, h, sw / 2, sh / 2, s * z, s * z, w / 2 + offx, h / 2)
        if r:
            x0, y0, patch, _ = r
            out[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
        return out

    def logo(self, c, key, x, y, size, t0, tau):
        lg = self.p['logos'].get(key)
        if not lg or tau < t0:
            return
        img = self.still(lg['src'], max_side=int(size * 1.4) + 8)
        s = size / max(img.shape[0], img.shape[1])
        k = ramp(tau, t0, t0 + 0.12, 0.0, 1.15) if tau < t0 + 0.12 else ramp(tau, t0 + 0.12, t0 + 0.22, 1.15, 1.0)
        if k <= 0.01:
            return
        put(c, img, img.shape[1] / 2, img.shape[0] / 2, s * k, x, y)

    # --- inserts
    def seq_clips(self, c, clips, w, h, x, y, vis, tau, collapse=False):
        n = len(clips)
        t = 0.0
        full = (w == c.shape[1] and h == c.shape[0])
        OX, OY = [0, 26, -22, 30], [0, 18, 32, 44]
        for k in range(n):
            d = clips[k].get('dur') or (vis / n)
            if k == n - 1:
                d = vis - t
            keep = vis + 0.55 - t
            if tau >= t:
                lt = tau - t
                img = self.clip(clips[k], w, h, lt, keep + 0.05)
                if k == 0 and collapse and not full:
                    hh = ramp(lt + t, 0.04, 0.36, 4.0, float(h), 0.85)
                    m0 = int(round(h / 2 - hh / 2))
                    m1 = int(round(h / 2 + hh / 2))
                    img2 = np.zeros((h, w, 4), np.float32)
                    img2[m0:m1, :, :3] = img[m0:m1]
                    img2[m0:m1, :, 3] = 1
                    put(c, img2, w / 2, h / 2, 1.0, x, y)
                elif k == 0:
                    put(c, img, w / 2, h / 2, 1.0, x, y)
                else:
                    ox, oy = (0, 0) if full else (OX[k % 4], OY[min(k, 3)])
                    px = ramp(tau, t, t + 0.2, x + ox * 2.4, x + ox, 0.8)
                    py = ramp(tau, t, t + 0.2, y + oy * 2.4 - 40, y + oy, 0.8)
                    sc = ramp(tau, t, t + 0.2, 1.14, 1.0, 0.8)
                    op = ramp(tau, t, t + 0.05, 0.0, 1.0)
                    if not full:                                    # soft drop shadow like a photo laid on top
                        sh = np.zeros((h + 120, w + 120, 4), np.float32)
                        sh[60:60 + h, 60:60 + w, 3] = 0.7
                        sh[:, :, 3] = blur(sh[:, :, 3], 15)
                        put(c, sh, (w + 120) / 2 - 7, (h + 120) / 2 - 7, sc, px, py, opacity=op)
                    put(c, np.dstack([img, np.ones(img.shape[:2], np.float32)]), w / 2, h / 2, sc, px, py, opacity=op)
            t += d

    def insert_texts(self, I, w, h):
        """Texts that live inside an insert (band words, UI labels), in the insert's own time."""
        out = []
        vis = I['vis']
        acc = self.p['accent']
        if I['kind'] == 'band':
            for ct in I.get('cut_txt') or []:
                out.append(dict(font=ct.get('font', 'anton'), text=ct['text'], x=ct['x'], y=ct['y'], size=ct['size'], color=ct.get('color', '#FFFFFF'),
                                anim='build', glow=(ct.get('color', '') or '').upper() == acc.upper(), t0=(ct.get('t0') or 0) + 0.2, t1=vis,
                                front=bool(ct.get('front'))))
        elif I['kind'] == 'cards':
            cs = I.get('cards') or []
            nC = max(len(cs), 1)
            cw = w * 0.84 / nC
            chh = cw * 1.4
            cyy = h * 0.55
            if I.get('title'):
                out.append(dict(font='sub', text=I['title'], x=w / 2, y=h * 0.12, size=30, color='#FFFFFF', anim='pop', t0=0.05, t1=vis))
            for a, cd in enumerate(cs):
                at, xa = cd.get('t') or 0, w * 0.08 + cw * (a + 0.5)
                if cd.get('name'):
                    out.append(dict(font='anton', text=cd['name'].upper(), x=xa, y=cyy + chh * 0.24, size=round(cw * 0.2), color='#FFFFFF', anim='build', t0=at + 0.05, t1=vis))
                if cd.get('caption'):
                    out.append(dict(font='sub', text=cd['caption'], x=xa, y=cyy + chh * 0.39, size=round(cw * 0.085), color=acc, anim='pop', t0=at + 0.2, t1=vis))
        elif I['kind'] == 'bar':
            E = I.get('box') or dict(bx=90, by=380 if I['layout'] == 'split' else 860, bw=900, bh=70 if I['layout'] == 'split' else 84)
            d0, d1 = I.get('d0') or 0.5, I.get('d1') or max((I.get('d0') or 0.5) + 0.5, vis - 0.4)
            vf, vt, suf = I.get('from', 100), I.get('to', 0), I.get('suffix', '%')
            out.append(dict(font='sub', text=I.get('label') or 'ENERGY', x=E['bx'] + 70, y=E['by'] - 44, size=36, color='#FFFFFF', anim='pop', t0=0, t1=vis))
            out.append(dict(font='sub', text='%d%s' % (vf, suf), x=E['bx'] + E['bw'] - 60, y=E['by'] - 44, size=36, color='#FFFFFF', anim='pop', t0=0, t1=vis,
                            counter=(d0, d1, vf, vt, suf)))
        elif I['kind'] == 'number':
            ny = I.get('y') or h * 0.5
            c0, c1 = (I.get('count') or [0.1, 0.5])
            nf, nt, ns = I.get('from', 0), I.get('to', 100), I.get('suffix', '')
            if I.get('label'):
                out.append(dict(font='sub', text=I['label'], x=w / 2, y=ny - 110, size=34, color='#FFFFFF', anim='pop', t0=0.04, t1=vis))
            out.append(dict(font='anton', text='%d%s' % (nt, ns), x=w / 2, y=ny + 5, size=150, color='#FFFFFF', anim='pop', t0=0.06, t1=vis, counter=(c0, c1, nf, nt, ns)))
            if I.get('status'):
                out.append(dict(font='sub', text=I['status'], x=w / 2, y=ny + 110, size=34, color=acc, anim='pop', t0=c1, t1=vis))
        return out

    def text_frames(self, I, w, h):
        """Pre-render an insert's texts once: list (per frame) of (x0, y0, rgba crop), split by layer group."""
        if I['id'] in self.ins_text:
            return self.ins_text[I['id']]
        texts = self.insert_texts(I, w, h)
        res = {'back': [], 'front': []}
        if texts:
            for grp in ('back', 'front'):
                ts = [T for T in texts if bool(T.get('front')) == (grp == 'front')]
                if not ts:
                    continue
                for T in ts:
                    T.setdefault('_uid', zlib.crc32(('%s|%s' % (I['id'], T['text'])).encode()) % 100000)
                fdir = textass.fonts_dir(self.cache)
                fac = textass.font_factors(fdir)
                textass.measure(self.ff, ts, self.p['fonts'], fac, fdir, self.cache, self.fps, tag='%s_%s_%d' % (I['id'], grp, os.getpid()))
                nfr = int(math.ceil(I['dur'] * self.fps))
                expanded = []
                for T in ts:                                    # counters: the number changes every frame
                    if T.get('counter'):
                        a0, a1, v0, v1, suf = T['counter']
                        for k in range(int(T['t0'] * self.fps), int(math.ceil(T['t1'] * self.fps))):
                            tt = k / self.fps
                            U = dict(T, text='%d%s' % (round(ramp(tt, a0, a1, v0, v1)), suf), t0=tt, t1=tt + 1.0 / self.fps)
                            U['anim'] = 'pop' if tt < T['t0'] + 0.08 else 'none'
                            U['fadeout'] = False
                            U['_offset'] = T['_offset']
                            expanded.append(U)
                    else:
                        expanded.append(T)
                ap = os.path.join(self.cache, 'ins_%s_%s_%d.ass' % (I['id'], grp, os.getpid()))
                textass.write_ass(ap, expanded, w, h, self.fps, self.p['fonts'], fac, 0.0, I['dur'])
                proc = textass.render_stream(self.ff, ap, fdir, w, h, self.fps, 0.0, nfr)
                frames = []
                for k in range(nfr):
                    buf = proc.stdout.read(w * h * 4)
                    if len(buf) < w * h * 4:
                        break
                    a = np.frombuffer(buf, np.uint8).reshape(h, w, 4)
                    ys = np.nonzero(a[:, :, 3].max(axis=1))[0]
                    if not len(ys):
                        frames.append(None)
                        continue
                    xs = np.nonzero(a[:, :, 3].max(axis=0))[0]
                    crop = a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1].astype(np.float32) / 255.0
                    frames.append((int(xs[0]), int(ys[0]), crop))
                proc.wait()
                res[grp] = frames
        self.ins_text[I['id']] = res
        return res

    def draw_text_group(self, c, I, grp, tau):
        fr = self.text_frames(I, c.shape[1], c.shape[0]).get(grp) or []
        k = int(round(tau * self.fps))
        if 0 <= k < len(fr) and fr[k]:
            x0, y0, crop = fr[k]
            over(c, crop, x0, y0)

    def insert(self, I, tau):
        """The insert comp (W x H, or W x H/2 for split layout) at its local time tau."""
        W = self.W
        h = self.H // 2 if I['layout'] == 'split' else self.H
        vis, dur = I['vis'], I['dur']
        c = np.zeros((h, W, 3), np.float32)
        kind = I['kind']
        if kind == 'logo_flash':
            sl = len(I['slots'])
            sd = vis / sl
            k = min(sl - 1, int(tau / sd))
            c[:] = hexrgb(I['slots'][k][1])
            self.logo(c, I['slots'][k][0], W / 2, h * 0.4, min(W, h) * 0.28, k * sd, tau)
        elif kind == 'frame':
            c[:] = hexrgb(I.get('bg') or '#0B0B0B')
            r = I['rect']
            self.seq_clips(c, I['clips'], int(r[2]), int(r[3]), r[0], r[1], vis, tau, collapse=not I.get('noframeanim'))
            if I.get('logo'):
                self.logo(c, I['logo'][0], I['logo'][1], I['logo'][2], I['logo'][3], 0.15, tau)
        elif kind == 'full':
            self.seq_clips(c, I['clips'], W, h, W / 2, h / 2, vis, tau)
            c *= 0.9
            if I.get('logo'):
                self.logo(c, I['logo'][0], I['logo'][1], I['logo'][2], I['logo'][3], 0.15, tau)
            for q, lg in enumerate(I.get('logos') or []):
                self.logo(c, lg[0], lg[1], lg[2], lg[3], 0.1 + q * 0.2, tau)
        elif kind == 'solid':
            c[:] = hexrgb(I.get('bg') or self.p['ui_bg'])
            self.faint(c, I.get('bgclip'), tau, dur, 0.20)
        elif kind == 'band':
            c[:] = 0.043
            spec = I['clips'][0]
            img = self.clip(spec, W, h, tau, dur)
            cy, bh = h / 2 + 20, round(h * 0.176)
            if I.get('staticband'):
                y0, y1 = cy - bh, cy + bh
            else:
                y0 = ramp(tau, 0.18, 0.42, 0, cy - bh, 0.85)
                y1 = ramp(tau, 0.18, 0.42, h, cy + bh, 0.85)
            c[int(y0):int(y1)] = img[int(y0):int(y1)]
            self.draw_text_group(c, I, 'back', tau)
            if spec.get('cutout_matte_abs'):
                m = self.cut_matte(spec, W, h, tau, dur)[:, :, None]
                c[:] = c * (1 - m) + img * m
                self.draw_text_group(c, I, 'front', tau)
                if 0.42 <= tau < 0.50:
                    c[:] = c * (1 - m) + m
            else:
                self.draw_text_group(c, I, 'front', tau)
        elif kind == 'vsplit':
            ts2 = I.get('tsplit') or vis / 2
            c[:] = self.clip(I['clips'][0], W, h, tau, dur)
            if tau >= ts2:
                b = self.clip(I['clips'][1], W, h // 2, tau - ts2, dur - ts2)
                x = ramp(tau, ts2, ts2 + 0.4, W * 1.5, W / 2, 0.85)
                v = abs(ramp(tau + 0.02, ts2, ts2 + 0.4, W * 1.5, W / 2, 0.85) - ramp(tau - 0.02, ts2, ts2 + 0.4, W * 1.5, W / 2, 0.85)) / 0.04
                put(c, np.dstack([b, np.ones(b.shape[:2], np.float32)]), W / 2, h / 4, 1.0, x, h * 0.75, mblur=v * SHUTTER / self.fps)
                if tau >= ts2 + 0.36:
                    c[int(h / 2 - 3):int(h / 2 + 3)] = np.array([0.06, 0.05, 0.06], np.float32)
        elif kind == 'cards':
            c[:] = self.uibg
            self.faint(c, I.get('bgclip'), tau, dur, 0.20)
            cs = I.get('cards') or []
            nC = max(len(cs), 1)
            cw = W * 0.84 / nC
            chh = cw * 1.4
            cyy = h * 0.55
            if I.get('title'):
                draw_rect(c, W / 2, h * 0.16, W * 0.8, 2, np.ones(3, np.float32))
            for a, cd in enumerate(cs):
                at, xa = cd.get('t') or 0, W * 0.08 + cw * (a + 0.5)
                if tau < at:
                    continue
                sc = ramp(tau, at, at + 0.16, 0.92, 1.0, 0.75)
                draw_rect(c, xa, cyy, cw * 0.92, chh, np.ones(3, np.float32), stroke=2, round_=6, scale=sc)
                if cd.get('logo'):
                    self.logo(c, cd['logo'], xa, cyy - chh * 0.17, cw * 0.5, at, tau)
            self.draw_text_group(c, I, 'back', tau)
        elif kind == 'bar':
            c[:] = self.uibg
            self.faint(c, I.get('bgclip'), tau, dur, 0.22)
            E = I.get('box') or dict(bx=90, by=380 if I['layout'] == 'split' else 860, bw=900, bh=70 if I['layout'] == 'split' else 84)
            d0, d1 = I.get('d0') or 0.5, I.get('d1') or max((I.get('d0') or 0.5) + 0.5, vis - 0.4)
            vf, vt = I.get('from', 100), I.get('to', 0)
            smax = max(abs(vf), abs(vt), 1)
            draw_rect(c, E['bx'] + E['bw'] / 2, E['by'] + E['bh'] / 2, E['bw'] + 24, E['bh'] + 24, np.ones(3, np.float32), stroke=4)
            frac = ramp(tau, d0, d1, vf / smax, vt / smax)
            if frac > 0:
                c[int(E['by']):int(E['by'] + E['bh']), int(E['bx']):int(E['bx'] + E['bw'] * frac)] = self.accent
            self.draw_text_group(c, I, 'back', tau)
        elif kind == 'number':
            c[:] = self.uibg
            self.faint(c, I.get('bgclip'), tau, dur, 0.22)
            ny = I.get('y') or h * 0.5
            draw_rect(c, W / 2, ny, 760, 330, np.ones(3, np.float32), stroke=3, round_=12, scale=ramp(tau, 0, 0.15, 0.9, 1.0, 0.75))
            self.draw_text_group(c, I, 'back', tau)
        elif kind == 'converge':
            c[:] = self.uibg
            self.faint(c, I.get('bgclip'), tau, dur, 0.22)
            keys = I.get('logos') or []
            g0 = [(W * 0.22, h * 0.28), (W * 0.78, h * 0.28), (W * 0.22, h * 0.72), (W * 0.78, h * 0.72)]
            for b2 in range(min(4, len(keys))):
                tx, ty = W / 2 + (g0[b2][0] - W / 2) * 0.22, h / 2 + (g0[b2][1] - h / 2) * 0.22
                x = ramp(tau, 0.25, 1.3, g0[b2][0], tx, 0.85)
                y = ramp(tau, 0.25, 1.3, g0[b2][1], ty, 0.85)
                self.logo(c, keys[b2], x, y, min(W, h) * 0.16, 0.0, tau)
            end = ramp(tau, 1.3, 1.8, 0, 100, 0.75)
            if end > 0:
                draw_ring(c, W / 2, h / 2, min(W, h) * 0.21, 5, self.accent, end)
        elif kind == 'cutout':
            c[:] = self.clip(I['bgclip'], W, h, tau, dur) * 0.85
            if 'matte_body' in self.p['mattes']:
                t = I['t0'] + tau
                sc = ramp(tau, 0, 0.3, 0.9, 1.0, 0.8) if tau < 0.3 else ramp(tau, 0.3, dur, 1.0, 1.03, 0.8)
                k = 0.86 * sc
                pres = self.presenter(t)
                m = self.presenter(t, matte='matte_body')
                img = np.dstack([pres, m])
                put(c, img, W / 2, h / 2, k, W / 2, h / 2 + h * (1 - 0.86) / 2)
        elif kind == 'pframe':
            if I.get('bgclip'):
                c[:] = blur(self.clip(I['bgclip'], W, h, tau, dur), 5) * 0.7
            sc = ramp(tau, 0, 0.28, 0.86, 1.0, 0.8) * 0.58
            draw_rect(c, W / 2, h / 2 + 20, W * 0.58 + 16, h * 0.58 + 16, np.ones(3, np.float32), scale=sc / 0.58)
            pres = self.presenter(I['t0'] + tau)
            put(c, pres, W / 2, h / 2, sc, W / 2, h / 2 + 20)
        noise(c, 5, self.rng)
        return c

    def faint(self, c, spec, tau, dur, op):
        if not spec:
            return
        img = blur(self.clip(spec, c.shape[1], c.shape[0], tau, dur), 4)
        c *= (1 - op)
        c += img * op

    # --- main comp
    def entry(self, I, t):
        """Position x, scale, motion-blur length and bulge amount of a full insert layer at time t."""
        W = self.W
        a4, b4, tr = I['in'], I['out'], I['trans']
        endS = 100.0 if I.get('norelease') else 104.0
        x, s, bulge = W / 2, 100.0, 0.0
        if tr in ('whip', 'whipL'):
            d = -1 if tr == 'whipL' else 1
            x = ramp(t, a4, a4 + TD, W / 2 + d * W, W / 2, 0.85)
            s = ramp(t, a4 + TD, b4, 100, endS)
        elif tr in ('zoom', 'zoomrot'):
            s = ramp(t, a4, a4 + TD, 165, 100, 0.85) if t < a4 + TD else ramp(t, a4 + TD, b4, 100, 104, 0.85)
        elif tr == 'bulge':
            s = ramp(t, a4, a4 + 0.26, 175, 100, 0.85) if t < a4 + 0.26 else ramp(t, a4 + 0.26, b4, 100, 104, 0.85)
            bulge = ramp(t, a4, a4 + 0.26, 70, 0, 0.85)
        else:
            s = ramp(t, a4, b4, 100, endS)
        if t >= a4 + I.get('entry', 0):
            s = max(s, 100.4)
        return x, s, bulge

    def frame(self, t, front=None, behind=None):
        W, H = self.W, self.H
        base = self.base_scale(t)
        c = self.presenter(t, base=base)
        if behind is not None and behind[:, :, 3].max() > 0:           # words behind the head
            pres = c.copy()
            over(c, behind, 0, 0)
            if 'matte_head' in self.p['mattes']:
                m = self.presenter(t, base=base, matte='matte_head')[:, :, None]
                c = c * (1 - m) + pres * m
        for I in self.p['inserts']:
            if I['layout'] == 'split':
                blk = next((b for b in self.p['split_blocks'] if b['t0'] - 1e-6 <= I['t0'] < b['t1']), None)
                if I.get('groupStart') and blk and blk['t0'] <= t < blk['t1']:
                    pass
                if not (I['in'] - 1e-6 <= t < I['out'] - 1e-6):
                    if I.get('groupStart') and blk and blk['t0'] <= t < blk['t1']:
                        self.split_half(c, blk, t)
                    continue
                img = self.insert(I, t - I['t0'])
                if I.get('groupStart'):
                    y = ramp(t, I['t0'], I['t0'] + 0.35, -H / 4, H / 4, 0.85)
                    v = abs(ramp(t + 0.02, I['t0'], I['t0'] + 0.35, -H / 4, H / 4, 0.85) - ramp(t - 0.02, I['t0'], I['t0'] + 0.35, -H / 4, H / 4, 0.85)) / 0.04
                    put(c, img, W / 2, H / 4, 1.0, W / 2, y)
                    if blk:
                        self.split_half(c, blk, t)
                else:
                    x = ramp(t, I['t0'], I['t0'] + 0.3, W * 1.5, W / 2, 0.85)
                    v = abs(ramp(t + 0.02, I['t0'], I['t0'] + 0.3, W * 1.5, W / 2, 0.85) - ramp(t - 0.02, I['t0'], I['t0'] + 0.3, W * 1.5, W / 2, 0.85)) / 0.04
                    put(c, np.dstack([img, np.ones(img.shape[:2], np.float32)]), W / 2, H / 4, 1.0, x, H / 4, mblur=v * SHUTTER / self.fps)
            else:
                if not (I['in'] - 1e-6 <= t < I['out'] - 1e-6):
                    continue
                img = self.insert(I, t - I['t0'])
                x, s, bulge = self.entry(I, t)
                if bulge > 0.5:
                    img = self.bulge(img, bulge)
                v = abs(self.entry(I, t + 0.02)[0] - self.entry(I, t - 0.02)[0]) / 0.04
                put(c, np.dstack([img, np.ones(img.shape[:2], np.float32)]), W / 2, H / 2, s / 100.0, x, H / 2, mblur=v * SHUTTER / self.fps)
            if I.get('flash') == 'invert' and I['t0'] <= t < I['t0'] + 2.0 / self.fps:
                c[:] = 1 - c
            if I.get('flash') == 'silhouette' and I['t0'] <= t < I['t0'] + 3.0 / self.fps and 'matte_body' in self.p['mattes']:
                m = self.presenter(t, matte='matte_body')
                c[:] = m[:, :, None]
        if front is not None:
            over(c, front[:, :, :], 0, 0)
        if self.halftone is not None:
            o = self.p['look'].get('halftone_opacity', 24) / 100.0 * self.halftone[:, :, 3:4]
            s = self.halftone[:, :, :3]
            ov = np.where(c < 0.5, 2 * c * s, 1 - 2 * (1 - c) * (1 - s))
            c += (ov - c) * o
        c *= (1 - self.vignette[:, :, None])
        noise(c, self.p['look'].get('grain', 4), self.rng)
        return np.clip(c, 0, 1)

    def split_half(self, c, blk, t):
        W, H = self.W, self.H
        if not (blk['t0'] <= t < blk['t1']):
            return
        img = self.presenter(t, half=True)
        y = ramp(t, blk['t0'], blk['t0'] + 0.35, H * 1.25, H * 0.75, 0.85)
        put(c, np.dstack([img, np.ones(img.shape[:2], np.float32)]), W / 2, H / 4, 1.0, W / 2, y)
        if blk['divider'][0] <= t < blk['divider'][1]:
            c[int(H / 2 - 3):int(H / 2 + 3)] = np.array([0.06, 0.05, 0.06], np.float32)

    def bulge(self, img, fov):
        h, w = img.shape[:2]
        k = fov / 70.0 * 0.35
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx, ny = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
        r2 = nx * nx + ny * ny
        f = 1 - k * (1 - np.clip(r2, 0, 1)) * 0.5
        sx, sy = w / 2 + nx * f * (w / 2), h / 2 + ny * f * (h / 2)
        xi, yi = np.clip(sx.astype(np.int32), 0, w - 1), np.clip(sy.astype(np.int32), 0, h - 1)
        return img[yi, xi]


# ----------------------------------------------------------------------------------------------- driver
def front_texts(plan):
    return [T for T in plan['text'] if not T.get('behind')]


def behind_texts(plan):
    return [T for T in plan['text'] if T.get('behind')]


def text_groups(plan):
    """(name, texts) with stable animation seeds: front texts 0.., behind texts 5000.."""
    out = []
    for name, ts, base in (('front', front_texts(plan), 0), ('behind', behind_texts(plan), 5000)):
        for i, T in enumerate(ts):
            T['_uid'] = base + i
        if ts:
            out.append((name, ts))
    return out


def prepare_text(plan, cache):
    ff = find_ffmpeg()
    fdir = textass.fonts_dir(cache)
    fac = textass.font_factors(fdir)
    missing = [f for f in plan['fonts'].values() if f not in fac]
    if missing:
        print('WARNING: fonts not found for libass: %s' % ', '.join(missing))
    for name, ts in text_groups(plan):
        textass.measure(ff, ts, plan['fonts'], fac, fdir, cache, plan['fps'], tag=name)
        wide = [T for T in ts if T.get('fit', True) and T.get('_inkw', 0) > T.get('max_w', 0.89 * plan['W'])]
        for T in wide:                                   # too wide: shrink to the limit, then measure again
            T['size'] = int(T['size'] * T.get('max_w', 0.89 * plan['W']) / T['_inkw'])
            print('note: "%s" shrunk to size %d to fit the frame' % (T['text'].replace('\n', ' ')[:30], T['size']))
        if wide:
            textass.measure(ff, wide, plan['fonts'], fac, fdir, cache, plan['fps'], tag=name + '_fit')
    return fdir, fac


def work(args):
    plan_path, cache, f0, f1, seg, mode, out_dir = args
    plan = json.load(open(plan_path))
    R = Renderer(plan, cache)
    ff = R.ff
    fps, W, H = plan['fps'], plan['W'], plan['H']
    fdir = textass.fonts_dir(cache)
    fac = textass.font_factors(fdir)
    groups = text_groups(plan)
    frames = list(range(f0, f1)) if mode == 'range' else f0

    def read_rgba(proc):
        buf = proc.stdout.read(W * H * 4)
        return np.frombuffer(buf, np.uint8).reshape(H, W, 4).astype(np.float32) / 255.0 if len(buf) == W * H * 4 else None

    def streams(t_from, t_to, n, tag):
        procs = {}
        for name, ts in groups:
            ap = os.path.join(cache, '%s_%s.ass' % (name, tag))
            textass.write_ass(ap, ts, W, H, fps, plan['fonts'], fac, t_from, t_to)
            procs[name] = textass.render_stream(ff, ap, fdir, W, H, fps, t_from, n)
        return procs

    if mode == 'range':
        procs = streams(f0 / fps, f1 / fps, f1 - f0, 'r%d' % f0)
        enc = subprocess.Popen([ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(fps), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709',
                                '-color_trc', 'bt709', '-colorspace', 'bt709', seg], stdin=subprocess.PIPE)
        for k in frames:
            lay = {name: read_rgba(pr) for name, pr in procs.items()}
            img = R.frame(k / fps, lay.get('front'), lay.get('behind'))
            enc.stdin.write((img * 255 + 0.5).astype(np.uint8).tobytes())
        enc.stdin.close()
        enc.wait()
        for pr in procs.values():
            pr.wait()
    else:
        for k in frames:
            t = k / fps
            procs = streams(t, t + 1.0 / fps, 1, 's%d' % k)
            lay = {name: read_rgba(pr) for name, pr in procs.items()}
            for pr in procs.values():
                pr.wait()
            img = R.frame(t, lay.get('front'), lay.get('behind'))
            png = os.path.join(out_dir, 'f_%07.2f.png' % t)
            subprocess.run([ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-i', '-', png],
                           input=(img * 255 + 0.5).astype(np.uint8).tobytes(), check=True)
    for r in list(R.readers.values()) + [R.pres] + [m[0] for m in R.mattes.values()]:
        r.close()
    return seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('edl')
    ap.add_argument('--out')
    ap.add_argument('--stills', nargs='*', type=float)
    ap.add_argument('--out-dir')
    ap.add_argument('--workers', type=int, default=max(1, min(8, (os.cpu_count() or 4) - 2)))
    a = ap.parse_args()
    t_start = time.time()
    plan = build_plan(a.edl)
    cache = tempfile.mkdtemp(prefix='reel_')
    prepare_text(plan, cache)
    plan_path = os.path.join(cache, 'plan.json')
    json.dump(plan, open(plan_path, 'w'), default=lambda o: None)
    ff = find_ffmpeg()
    fps = plan['fps']
    nfr = int(round(plan['dur'] * fps))
    if a.stills:
        out_dir = a.out_dir or os.path.join(plan['P'], 'qa', 'stills_' + time.strftime('%H%M%S'))
        os.makedirs(out_dir, exist_ok=True)
        ks = [min(nfr - 1, int(round(t * fps))) for t in a.stills]
        chunks = [ks[i::a.workers] for i in range(min(a.workers, len(ks)))]
        with mp.Pool(len(chunks)) as pool:
            pool.map(work, [(plan_path, cache, ch, None, None, 'stills', out_dir) for ch in chunks])
        files = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith('.png'))
        args = [ff, '-v', 'error', '-y']
        for f in files:
            args += ['-i', f]
        cols = min(8, len(files))
        rows = (len(files) + cols - 1) // cols
        fl = ''.join('[%d:v]scale=270:480,drawtext=text=%s:x=6:y=6:fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.6:fontfile=/System/Library/Fonts/Helvetica.ttc[v%d];'
                     % (i, os.path.basename(f)[2:-4].lstrip('0') or '0', i) for i, f in enumerate(files))
        pads = cols * rows - len(files)
        fl += ''.join('color=black:s=270x480:d=1[p%d];' % p for p in range(pads))
        lay = '|'.join('%d_%d' % ((k % cols) * 270, (k // cols) * 480) for k in range(cols * rows))
        fl += ''.join('[v%d]' % i for i in range(len(files))) + ''.join('[p%d]' % p for p in range(pads)) + \
            ('xstack=inputs=%d:layout=%s' % (cols * rows, lay) if cols * rows > 1 else 'null') + ',format=yuvj420p'
        subprocess.run(args + ['-filter_complex', fl, '-frames:v', '1', os.path.join(out_dir, 'sheet.jpg')], check=True, stdin=subprocess.DEVNULL)
        print('stills -> %s (%.0f s)' % (os.path.join(out_dir, 'sheet.jpg'), time.time() - t_start))
        return
    out = os.path.abspath(a.out or os.path.join(plan['P'], 'render', plan['name'] + '.mp4'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    nw = max(1, a.workers)
    bounds = [round(nfr * i / nw) for i in range(nw + 1)]
    jobs = [(plan_path, cache, bounds[i], bounds[i + 1], os.path.join(cache, 'seg_%02d.mp4' % i), 'range', None) for i in range(nw)]
    print('rendering %d frames with %d workers ...' % (nfr, nw), flush=True)
    with mp.Pool(nw) as pool:
        segs = pool.map(work, jobs)
    lst = os.path.join(cache, 'segs.txt')
    with open(lst, 'w') as fh:
        for s in segs:
            fh.write("file '%s'\n" % s)
    subprocess.run([ff, '-v', 'error', '-nostdin', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', plan['audio'], '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out], check=True)
    info = probe(out, ff)
    lufs = None
    try:
        err = subprocess.run([ff, '-hide_banner', '-nostats', '-i', out, '-map', '0:a', '-af', 'ebur128', '-f', 'null', '-'],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
        import re
        m = re.findall(r'I:\s+(-?[\d.]+) LUFS', err)
        lufs = float(m[-1]) if m else None
    except Exception:
        pass
    print('done: %s  %dx%d  %.3g fps  %.2f s  audio %s  loudness %s  (%.0f s)' % (
        out, info['w'], info['h'], info['fps'], info['dur'], 'yes' if info['audio'] else 'NO',
        '%.1f LUFS' % lufs if lufs is not None else '?', time.time() - t_start))


if __name__ == '__main__':
    main()
