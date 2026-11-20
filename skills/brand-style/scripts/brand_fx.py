#!/usr/bin/env python3
"""Tambah elemen gaya brand (style.json) sebagai lapisan atas reel yang dah siap.

usage: PY brand_fx.py <plan.json> [--still 20.7,23.5] [--style <style.json>]
  PY = ~/.claude/skills/video-effect/.venv/Scripts/python.exe (perlu numpy, opencv, pillow)

plan.json:
{"video": "D:/Video/1228/long_01.mp4", "out": ".../long_01_brand.mp4", "band": [608, 1414],
 "fx": [
   {"type": "brackets", "t": 0.0, "dur": 2.6, "label": "REC 00:00:08"},
   {"type": "keyword", "t": 20.6, "text": "JUMPA!", "punch": true, "sfx": "pop"},
   {"type": "phrase", "t": 22.7, "lines": ["SHRINE OF", "REMEMBRANCE"], "sfx": "thud"},
   {"type": "countdown", "t": 50.0, "items": ["3", "2", "1", "CUT"], "sfx": "click"},
   {"type": "flash", "t": 37.4, "until": 52.6, "look": "film" | "bw", "text": "1914-1918", "text_t": 51.5, "sfx": "whoosh"}
 ]}
Teks hanya di jalur bawah (kata kunci, frasa) atau atas video (kiraan, teks kilat). Poster, tajuk dan subtitle asal tidak disentuh.
"""
import argparse, json, math, os, subprocess, sys, tempfile, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(HERE, '..', 'fonts'), os.path.expanduser('~/.claude/skills/video-effect/fonts'),
             os.path.join(HERE, '..', '..', 'video-effect', 'fonts')]
YUNET = [os.path.expanduser('~/.claude/skills/video-effect/models/yunet.onnx'), os.path.join(HERE, '..', '..', 'video-effect', 'models', 'yunet.onnx')]
FONTS = {'display': 'Anton-Regular.ttf', 'serif': 'InstrumentSerif-Italic.ttf', 'mono': 'SpaceMono-Bold.ttf'}


def find(name, dirs):
    for d in dirs:
        p = os.path.join(d, name) if not name.startswith(('/', 'C:', 'D:')) else name
        if os.path.exists(p):
            return p
    sys.exit(f'tak jumpa {name}')


def font(kind, size):
    return ImageFont.truetype(find(FONTS[kind], FONT_DIRS), size)


ease = lambda x: 1 - (1 - min(1, max(0, x))) ** 3
def back(x):
    x = min(1, max(0, x)); c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def sprite(text, kind, size, color, glow=False, shadow=True):
    """RGBA numpy sprite of one line of text."""
    f = font(kind, size)
    l, t, r, b = f.getbbox(text)
    pad = int(size * .35)
    W, H = r - l + pad * 2, b - t + pad * 2
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + 3, pad - t + 5), text, font=f, fill=(0, 0, 0, 170))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(size * .06)))
    if glow:
        g = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((pad - l, pad - t), text, font=f, fill=color + (230,))
        img = Image.alpha_composite(img, g.filter(ImageFilter.GaussianBlur(size * .12)))
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=f, fill=color + (255,))
    return np.array(img)


def paste(frame, spr, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        spr = cv2.resize(spr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = spr.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    H, W = frame.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x0 + w), min(H, y0 + h)
    if x1c <= x0c or y1c <= y0c:
        return
    s = spr[sy0:sy0 + (y1c - y0c), sx0:sx0 + (x1c - x0c)].astype(np.float32)
    a = s[..., 3:4] / 255 * alpha
    roi = frame[y0c:y1c, x0c:x1c].astype(np.float32)
    frame[y0c:y1c, x0c:x1c] = (roi * (1 - a) + s[..., :3] * a).astype(np.uint8)


# ---------- synthesised SFX (same sounds as the review board) ----------
def synth(kind, sr=48000):
    rng = np.random.default_rng(7)
    def env(n, a, d): t = np.arange(n) / sr; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
    if kind in ('whoosh', 'riser'):
        dur = .6 if kind == 'whoosh' else 1.4; n = int(sr * dur); x = rng.standard_normal(n)
        cut = np.linspace(300, 3000 if kind == 'whoosh' else 6000, n) / sr
        y = np.zeros(n); lp = 0; hp = 0
        for i in range(n):                                    # moving band-pass: one-pole LP minus slower LP
            a = 1 - math.exp(-2 * math.pi * cut[i]); lp += a * (x[i] - lp); hp += (a * .25) * (lp - hp); y[i] = lp - hp
        t = np.arange(n) / n; y *= np.sin(np.pi * t) ** 1.5
    elif kind in ('thud', 'boom'):
        dur = .45 if kind == 'thud' else .9; n = int(sr * dur); t = np.arange(n) / sr
        f = 40 + 100 * np.exp(-t / .08); y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, .002, .12 if kind == 'thud' else .3)
    elif kind == 'pop':
        n = int(sr * .1); t = np.arange(n) / sr; f = 600 + 6000 * t; y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, .001, .02)
    elif kind == 'click':
        n = int(sr * .05); y = np.sign(np.sin(2 * np.pi * 1800 * np.arange(n) / sr)) * env(n, .0005, .008)
    else:
        return None
    y = y / (np.abs(y).max() + 1e-9) * .9
    return y.astype(np.float32)


def write_wav(path, y, sr=48000):
    d = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(d.tobytes())


# ---------- main ----------
ap = argparse.ArgumentParser()
ap.add_argument('plan')
ap.add_argument('--still')
ap.add_argument('--style', default=os.path.join(HERE, '..', 'brand', 'utama', 'style.json'))
a = ap.parse_args()
plan = json.load(open(a.plan, encoding='utf-8'))
style = json.load(open(a.style, encoding='utf-8'))
E, TR = style['elements'], style['transitions']
YEL = hexrgb(style['colors']['yellow'])
src = plan['video']
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration',
                                '-of', 'json', src], capture_output=True, text=True, check=True).stdout)
W, H = pr['streams'][0]['width'], pr['streams'][0]['height']
num, den = map(int, pr['streams'][0]['r_frame_rate'].split('/')); FPS = num / den
DUR = float(pr['format']['duration'])
B0, B1 = plan.get('band', [608, 1414])
B0, B1 = int(B0 * H / 1920), int(B1 * H / 1920)
FX = sorted(plan['fx'], key=lambda f: f['t'])

# pre-render sprites
kw_size = int(W * E['keyword_bottom']['width_frac'])
ph_size = int(W * E['phrase_stack']['width_frac'] * .85)
for f in FX:
    if f['type'] == 'keyword':
        f['_s'] = sprite(f['text'].upper(), 'display', kw_size, YEL, glow=True)
        f.setdefault('y', int(H * .86))
    elif f['type'] == 'phrase':
        f['_s'] = [sprite(l.upper(), 'display', ph_size, YEL) for l in f['lines']]
        f.setdefault('y', int(H * .875))
    elif f['type'] == 'countdown':
        f['_s'] = [sprite(x, 'serif', int(W * E['countdown']['width_frac']), YEL) for x in f.get('items', E['countdown']['items'])]
    elif f['type'] == 'flash' and f.get('text'):
        look = TR['flash_film' if f.get('look') == 'film' else 'flash_bw']
        f['_s'] = sprite(f['text'], 'serif' if look['text_font'] == 'serif' else 'display', int(W * .13), (255, 255, 255))
    elif f['type'] == 'brackets':
        f['_lab'] = sprite(f.get('label', E['face_brackets']['label']), 'mono', int(W * .038), (255, 255, 255), shadow=True)

det = None
if any(f['type'] == 'brackets' or f.get('punch') for f in FX):
    det = cv2.FaceDetectorYN.create(next(p for p in YUNET if os.path.exists(p)), '', (W // 2, (B1 - B0) // 2), 0.6)
face_state = {'box': None}


def face_box(frame):
    band = cv2.resize(frame[B0:B1], (W // 2, (B1 - B0) // 2))
    _, fs = det.detect(cv2.cvtColor(band, cv2.COLOR_RGB2BGR))
    if fs is None or not len(fs):
        return face_state['box']
    x, y, w, h = (fs[0][:4] * 2).tolist(); y += B0
    nb = np.array([x, y, x + w, y + h])
    face_state['box'] = nb if face_state['box'] is None else face_state['box'] * .6 + nb * .4
    return face_state['box']


def flash_filter(img, look):
    if look == 'film':
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
        sep = np.stack([g * 1.07 + 20, g * .88 + 12, g * .66], -1)
        out = img.astype(np.float32) * .15 + sep * .85
        out = (out - 128) * 1.15 + 128
    else:
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
        out = np.repeat(((g - 128) * 1.2 + 128)[..., None], 3, -1)
    return np.clip(out, 0, 255).astype(np.uint8)


def process(frame, t):
    fr = frame
    # band effects first (punch, flash look), then overlays
    for f in FX:
        dt = t - f['t']
        if f.get('punch') and -0.01 <= dt <= 1.6:
            z = TR['punch_in']['zoom']
            k = ease(dt / TR['punch_in']['in_s']) if dt < 1.2 else 1 - ease((dt - 1.2) / .3)
            s = 1 + (z - 1) * k
            if s > 1.001:
                bx = face_box(fr) if det is not None else None
                cx = (bx[0] + bx[2]) / 2 if bx is not None else W / 2
                cy = ((bx[1] + bx[3]) / 2 if bx is not None else (B0 + B1) / 2) - B0
                band = fr[B0:B1]; bh = B1 - B0
                cw, ch = W / s, bh / s
                x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), bh - ch)
                fr[B0:B1] = cv2.resize(band[int(y0):int(y0 + ch), int(x0):int(x0 + cw)], (W, bh), interpolation=cv2.INTER_CUBIC)
        if f['type'] == 'flash':
            until = f.get('until', f['t'] + 1.5)
            if f['t'] <= t <= until:
                fr[B0:B1] = flash_filter(fr[B0:B1], f.get('look', 'bw'))
            for edge in (f['t'], until):
                d = abs(t - edge)
                if d < TR['flash_bw']['flash_s']:
                    al = 1 - d / TR['flash_bw']['flash_s']
                    fr[B0:B1] = (fr[B0:B1].astype(np.float32) * (1 - al) + 255 * al).astype(np.uint8)
    for f in FX:
        dt = t - f['t']
        ty = f['type']
        if ty == 'keyword' and 0 <= dt <= 2.3:
            sc = 2.2 - 1.2 * ease(dt / .16) if dt < .16 else 1
            sh = math.sin(dt * 90) * (1 - dt / .35) * 8 if dt < .35 else 0
            al = 1 - (dt - 2.0) / .3 if dt > 2.0 else 1
            paste(fr, f['_s'], W / 2 + sh, f['y'], sc, al)
        elif ty == 'phrase':
            step = E['phrase_stack']['step_s']; n = len(f['_s']); end = (n - 1) * step + 2.6
            if 0 <= dt <= end + .3:
                al = 1 - (dt - end) / .3 if dt > end else 1
                lh = ph_size * 1.02
                y0 = f['y'] - (n - 1) * lh / 2
                for i, s in enumerate(f['_s']):
                    k = (dt - i * step) / .18
                    if k > 0:
                        paste(fr, s, W / 2, y0 + i * lh, 1.35 - .35 * ease(k), al)
        elif ty == 'countdown':
            step = E['countdown']['step_s']; n = len(f['_s'])
            if 0 <= dt <= n * step + .3:
                i = min(n - 1, int(dt / step)); k = (dt - i * step) / step
                paste(fr, f['_s'][i], W / 2, (B0 + B1) / 2, 1.5 - .5 * ease(k * 3), 1 if dt < n * step else 1 - (dt - n * step) / .3)
        elif ty == 'flash' and f.get('_s') is not None:
            tt = t - f.get('text_t', f['t'] + .15)
            if 0 <= tt <= 2.6:
                al = min(1, tt / .25) * (1 - (tt - 2.3) / .3 if tt > 2.3 else 1)
                paste(fr, f['_s'], W / 2, (B0 + B1) / 2, 1, al)
        elif ty == 'brackets' and 0 <= dt <= f.get('dur', 2.6):
            bx = face_box(fr)
            if bx is None:
                continue
            pad = E['face_brackets']['pad']; x0, y0, x1, y1 = bx
            pw, ph = (x1 - x0) * pad, (y1 - y0) * pad
            x0, y0, x1, y1 = max(8, x0 - pw), max(B0 + 8, y0 - ph), min(W - 8, x1 + pw), min(B1 - 8, y1 + ph)
            o = (1 - back(dt / E['face_brackets']['in_s'])) * W * .18
            x0, y0, x1, y1 = x0 - o, y0 - o, x1 + o, y1 + o
            L = W * E['face_brackets']['corner_frac']; th = E['face_brackets']['stroke_px']
            out = 1 - (dt - f.get('dur', 2.6) + .3) / .3 if dt > f.get('dur', 2.6) - .3 else 1
            ov = fr.copy()
            for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                p = (int(cx), int(cy))
                cv2.line(ov, p, (int(cx + sx * L), int(cy)), (255, 255, 255), th, cv2.LINE_AA)
                cv2.line(ov, p, (int(cx), int(cy + sy * L)), (255, 255, 255), th, cv2.LINE_AA)
            fr[:] = (fr.astype(np.float32) * (1 - out) + ov.astype(np.float32) * out).astype(np.uint8)
            if dt > E['face_brackets']['in_s'] and int(dt * E['face_brackets']['blink_hz'] * 2) % 2 == 0:
                lab = f['_lab']; paste(fr, lab, x0 + lab.shape[1] / 2 - lab.shape[0] * .3, y0 - lab.shape[0] * .45, 1, out)
    return fr


def read_frame(t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', src, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()


if a.still:
    base = os.path.splitext(plan['out'])[0]
    os.makedirs(os.path.dirname(base) or '.', exist_ok=True)
    for ts in a.still.split(','):
        t = float(ts)
        # warm up face tracking with a few frames before t
        for k in range(6, 0, -1):
            if det is not None and t - k / FPS >= 0:
                face_box(read_frame(t - k / FPS))
        img = process(read_frame(t), t)
        p = f'{base}_still_{t:.1f}.png'
        Image.fromarray(img).save(p); print(p)
    sys.exit()

# audio: original + synthesised SFX
tmp = tempfile.mkdtemp(prefix='brandfx_')
sfx = []
for f in FX:
    kind = f.get('sfx', None)
    if not kind:
        continue
    times = [f['t']]
    if f['type'] == 'phrase':
        times = [f['t'] + i * E['phrase_stack']['step_s'] for i in range(len(f['lines']))]
    elif f['type'] == 'countdown':
        times = [f['t'] + i * E['countdown']['step_s'] for i in range(len(f.get('items', E['countdown']['items'])))]
    elif f['type'] == 'flash':
        times = [f['t'] - .25]
    for tt in times:
        p = os.path.join(tmp, f'{kind}.wav')
        if not os.path.exists(p):
            write_wav(p, synth(kind))
        sfx.append((max(0, tt), p, f.get('vol', .35)))

out = plan['out']
os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
vtmp = os.path.join(tmp, 'v.mp4')
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, bufsize=10 ** 8)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f'{num}/{den}', '-i', '-',
                        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', vtmp], stdin=subprocess.PIPE)
active = [(f['t'] - .3, max(f.get('until', 0), f['t'] + 4.5)) for f in FX]
n = 0; fsz = W * H * 3
while True:
    buf = dec.stdout.read(fsz)
    if len(buf) < fsz:
        break
    t = n / FPS
    if any(s <= t <= e for s, e in active):
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        enc.stdin.write(process(fr, t).tobytes())
    else:
        face_state['box'] = None if not any(s - .5 <= t <= e for s, e in active) else face_state['box']
        enc.stdin.write(buf)
    n += 1
    if n % 600 == 0:
        print(f'{t:.0f}s / {DUR:.0f}s', flush=True)
enc.stdin.close(); enc.wait(); dec.wait()

inputs = ['-i', vtmp, '-i', src]
fc, labels = [], ['[1:a]']
for i, (tt, p, vol) in enumerate(sfx):
    inputs += ['-i', p]
    fc.append(f'[{i + 2}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={int(tt * 1000)}:all=1[s{i}]')
    labels.append(f'[s{i}]')
fc.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.95[a]')
subprocess.run(['ffmpeg', '-v', 'error', '-y'] + inputs + ['-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], check=True)
print('siap:', out, f'({os.path.getsize(out) / 1048576:.1f} MB)')
