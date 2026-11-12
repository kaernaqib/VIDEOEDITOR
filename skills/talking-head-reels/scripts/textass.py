"""Kinetic typography through libass (ffmpeg's `ass` filter): one subtitle event per frame per text,
with per-letter override tags. This reproduces the house animations:

  build  - letters arrive in random order, stretched tall and spread wide, outline first, then fill,
           in stepped jumps (2 frames each); the whole word drifts 106% -> 100% while on screen
  soft   - fades in from a blur with a slight grow (serif accents)
  words  - subtitles: every word appears exactly when it is spoken
  pop    - small labels: 118% -> 100% in 2 frames
  exit   - big/serif words dissolve letter by letter (fade + grow + blur); other text fades out

Text is positioned like a design tool: (x, y) is the centre of the visible ink, measured once per
text in a measurement pass, so libass's line-box centring does not shift anything.
"""
import math
import os
import random
import subprocess

import numpy as np

from fontmetrics import extract_faces, faces, libass_factor

FONT_FILES = {
    'Anton-Regular': None,                                    # bundled
    'Didot': '/System/Library/Fonts/Supplemental/Didot.ttc',
    'HelveticaNeue-Medium': '/System/Library/Fonts/HelveticaNeue.ttc',
}
EXTRA_FONT_FILES = [p for p in os.environ.get('REEL_FONT_FILES', '').split(os.pathsep) if p]   # more .ttf/.otf/.ttc
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fonts_dir(cache):
    """A folder with one .ttf per face (Anton + the macOS Didot and Helvetica Neue collections), as libass needs them."""
    d = os.path.join(cache, 'fonts')
    os.makedirs(d, exist_ok=True)
    sources = [os.path.join(SKILL, 'assets', 'fonts', 'Anton-Regular.ttf'), FONT_FILES['Didot'], FONT_FILES['HelveticaNeue-Medium']]
    for src in sources + list(EXTRA_FONT_FILES):
        if src and os.path.exists(src):
            extract_faces(src, d)
    return d


FACE_INFO = {}        # PostScript name -> family / weight / italic (filled by font_factors)


def font_factors(fdir):
    """libass size factor per PostScript name; also records how to select each face in libass."""
    out = {}
    for fn in sorted(os.listdir(fdir)):
        if not fn.lower().endswith(('.ttf', '.otf', '.ttc')):
            continue
        for f in faces(os.path.join(fdir, fn)):
            if f.get('ps'):
                out[f['ps']] = libass_factor(f)
                FACE_INFO[f['ps']] = dict(family=f['family'] or f['ps'], weight=f['weight'], italic=f['italic'])
    return out


def font_tags(ps):
    """libass does not find faces of a family by PostScript name: select family (style) + exact weight (tag)."""
    info = FACE_INFO.get(ps)
    if not info:
        return ''
    return '\\b%d\\i%d' % (info['weight'], 1 if info['italic'] else 0)


def hexcol(h):
    return h[5:7] + h[3:5] + h[1:3]           # #RRGGBB -> BBGGRR for ASS


def a8(opacity):
    return '%02X' % int(round(255 * (1 - max(0.0, min(1.0, opacity)))))


def bez(u, i_out, i_in):
    """Keyframe-style temporal ease (speed 0, influence i_out / i_in in 0..1) as a progress curve."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    x1, x2 = i_out, 1 - i_in
    s = u
    for _ in range(12):
        x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
        dx = 3 * (1 - s) ** 2 * x1 + 6 * (1 - s) * s * (x2 - x1) + 3 * s * s * (1 - x2)
        if abs(dx) < 1e-6:
            break
        s = min(1.0, max(0.0, s - (x - u) / dx))
    return 3 * (1 - s) * s * s + s ** 3


def ramp(t, t0, t1, v0, v1, ease=None):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    u = (t - t0) / (t1 - t0)
    if ease:
        u = bez(u, ease, ease)
    return v0 + (v1 - v0) * u


def esc(ch):
    return {'{': '\\{', '}': '\\}', '\\': '\\\\'}.get(ch, ch)


def text_lines(text):
    """Split on newlines: list of (first char index, line text)."""
    out, i = [], 0
    for ln in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        out.append((i, ln))
        i += len(ln) + 1
    return out


def tracking_px(T):
    """Letter spacing in design pixels: 'tracking' is in 1/1000 em like design tools (Anton default -10)."""
    return T.get('tracking', -10 if T['font'] == 'anton' else 0) / 1000.0 * T['size']


def leading_px(T):
    return T.get('leading', 1.2 * T['size'])


def ass_time(t):
    cs = int(math.floor(t * 100 + 1e-6))
    return '%d:%02d:%02d.%02d' % (cs // 360000, (cs // 6000) % 60, (cs // 100) % 60, cs % 100)


class TextAnim:
    """Evaluates one text item frame by frame. Times are in the time base of the canvas it lives on."""

    def __init__(self, T, fps, uid):
        self.T, self.fps = T, fps
        self.t0, self.t1 = T['t0'], T['t1']
        self.chars = list(T['text'].replace('\r\n', '\n').replace('\r', '\n'))
        self.ns = [i for i, c in enumerate(self.chars) if not c.isspace()]
        n = len(self.ns)
        rnd = random.Random(1000 + uid)
        self.pos_build = self._perm(rnd, n)
        self.pos_outline = self._perm(random.Random(7000 + uid), n)
        self.pos_exit = self._perm(random.Random(3000 + uid), n)
        nch = n
        self.steps = 3 if nch <= 3 else (4 if nch <= 6 else 5)
        self.stepT = 2.0 / fps
        self.ed = min(0.3, (self.t1 - self.t0) * 0.3)
        self.has_exit = T.get('fadeout', True) is not False and self.ed > 0.06
        words, cur = [], []
        for i, c in enumerate(self.chars):
            if c.isspace():
                if cur:
                    words.append(cur)
                    cur = []
            else:
                cur.append(i)
        if cur:
            words.append(cur)
        self.words = words

    @staticmethod
    def _perm(rnd, n):
        order = list(range(n))
        rnd.shuffle(order)
        pos = [0] * n
        for p, i in enumerate(order):
            pos[i] = p
        return pos

    def stepped(self, t, delay_steps):
        """Hold-keyed selector start (0..1) for the build / outline animators."""
        k = math.floor((t - self.t0) / self.stepT + 1e-6) - delay_steps
        return max(0.0, min(1.0, k / float(self.steps)))

    def state(self, t):
        """Per-layer and per-character parameters at time t (None = not visible)."""
        T, a = self.T, self.T['anim']
        if t < self.t0 - 1e-6 or t >= self.t1 - 1e-6:
            return None
        lay = dict(scale=100.0, opacity=1.0, blur=0.0)
        n = len(self.ns)
        ch = [dict(op=1.0, fill=1.0, sx=100.0, sy=100.0, sp=0.0, bord=0.0, blur=0.0) for _ in self.chars]
        if a == 'build':
            lay['scale'] = ramp(t, self.t0, self.t1, 106, 100)
            s1 = self.stepped(t, 0)
            s2 = self.stepped(t, 2)
            sw = max(2, round(T['size'] / 60.0))
            for j, i in enumerate(self.ns):
                a1 = max(0.0, min(1.0, (self.pos_build[j] + 1) - n * s1))
                a2 = max(0.0, min(1.0, (self.pos_outline[j] + 1) - n * s2))
                c = ch[i]
                c['op'] *= 1 - a1
                c['sx'] = 100 + (60 - 100) * a1
                c['sy'] = 100 + (300 - 100) * a1
                c['sp'] = 0.18 * a1 * T['size']
                c['fill'] = 1 - a2
                c['bord'] = sw * a2
        elif a == 'words':
            lay['scale'] = ramp(t, self.t0, self.t0 + 0.12, 108, 100, 0.75)
            wt = T.get('wt') or []
            for w, idx in enumerate(self.words):
                vis = (w < len(wt) and t >= wt[w] - 1e-6) or w >= len(wt)
                if not vis:
                    for i in idx:
                        ch[i]['op'] = 0.0
        elif a == 'pop':
            lay['scale'] = ramp(t, self.t0, self.t0 + 0.08, 118, 100)
        elif a == 'soft':
            lay['opacity'] *= ramp(t, self.t0, self.t0 + 0.2, 0, 1)
            lay['blur'] = ramp(t, self.t0, self.t0 + 0.26, 30, 0)
            lay['scale'] = ramp(t, self.t0, self.t0 + 0.3, 94, 100, 0.8)
        if self.has_exit:
            if T['font'] != 'sub':                     # display fonts dissolve letter by letter
                e = ramp(t, self.t1 - self.ed, self.t1 - 0.02, 0, 1, 0.55)
                for j, i in enumerate(self.ns):
                    a3 = max(0.0, min(1.0, n * e - self.pos_exit[j]))
                    c = ch[i]
                    c['op'] *= 1 - a3
                    c['sx'] *= 1 + 0.16 * a3
                    c['sy'] *= 1 + 0.16 * a3
                    c['blur'] = 16 * a3
            else:
                lay['opacity'] *= ramp(t, self.t1 - 0.16, self.t1, 1, 0, 0.5)
        if T.get('opacity_keys'):                       # optional explicit fades
            for (ta, va), (tb, vb) in zip(T['opacity_keys'], T['opacity_keys'][1:]):
                if ta <= t < tb:
                    lay['opacity'] *= ramp(t, ta, tb, va, vb) / 100.0
        return lay, ch


def event_text(T, lay, ch, factor, offset, colour, opacity_mul=1.0, blur_add=0.0, border_colour=None, glow=False):
    """Event bodies (one per non-empty line). Lines are stacked with design-tool leading around (x, y)."""
    sc = lay['scale'] / 100.0
    fs = T['size'] * factor
    trk = tracking_px(T)
    lines = text_lines(''.join(T['_chars']))
    offs = T.get('_offsets') or [offset] * len(lines)
    lead = leading_px(T)
    out = []
    for k, (i0, ln) in enumerate(lines):
        if not ln.strip():
            continue
        off = offs[k] if k < len(offs) and offs[k] is not None else offset
        x = T['x'] - off[0] * sc
        y = T['y'] + (k - (len(lines) - 1) / 2.0) * lead * sc - off[1] * sc
        parts = ['{\\an5\\pos(%.1f,%.1f)%s\\fs%.2f\\1c&H%s&\\3c&H%s&\\shad0\\bord0}' % (x, y, T.get('_ftags', ''), fs, hexcol(colour), hexcol(border_colour or colour))]
        for j, char in enumerate(ln):
            c = ch[i0 + j]
            op = c['op'] * lay['opacity'] * opacity_mul
            fill_op = op * (c['fill'] if not glow else max(c['fill'], 0.0))
            bl = c['blur'] * 0.5 + lay['blur'] * 0.5 + blur_add
            parts.append('{\\1a&H%s&\\3a&H%s&\\fscx%.1f\\fscy%.1f\\fsp%.2f\\bord%.2f\\blur%.2f}%s' % (
                a8(fill_op), a8(op), c['sx'] * sc, c['sy'] * sc, (c['sp'] + trk) * sc, c['bord'] * sc, bl, esc(char)))
        out.append(''.join(parts))
    return out


def header(W, H, fonts):
    styles = []
    for key, ps in fonts.items():
        ps = FACE_INFO.get(ps, {}).get('family', ps)
        styles.append('Style: %s,%s,60,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1' % (key, ps))
    return ('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, '
            'StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n%s\n\n'
            '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n') % (W, H, '\n'.join(styles))


def write_ass(path, texts, W, H, fps, fonts, factors, t_from, t_to, glow_soft=11.0, shadow_soft=5.0):
    """Per-frame events for every text visible in [t_from, t_to)."""
    lines = [header(W, H, fonts)]
    f0, f1 = int(math.floor(t_from * fps + 1e-6)), int(math.ceil(t_to * fps - 1e-6))
    for uid, T in enumerate(texts):
        anim = T.get('_anim') or TextAnim(T, fps, T.get('_uid', uid))
        T['_anim'] = anim
        T['_chars'] = anim.chars
        fac = factors[fonts[T['font']]]
        T['_ftags'] = font_tags(fonts[T['font']])
        off = T.get('_offset', (0.0, 0.0))
        a = max(f0, int(math.floor(T['t0'] * fps + 1e-6)))
        b = min(f1, int(math.ceil(T['t1'] * fps - 1e-6)))
        for k in range(a, b):
            t = k / fps
            st = anim.state(t)
            if not st:
                continue
            lay, ch = st
            # event times are local to the chunk (frame f0 = 0); render_stream always starts at 0
            ts, te = ass_time((k - f0) / fps), ass_time((k - f0 + 1) / fps)
            evs = []
            if T.get('glow'):
                evs += [(0, b) for b in event_text(T, lay, ch, fac, off, T.get('glow_color', T['color']), 0.75, glow_soft, glow=True)]
            if T.get('shadow'):
                evs += [(0, b) for b in event_text(T, lay, ch, fac, off, '#000000', 0.45, shadow_soft, '#000000')]
            evs += [(1, b) for b in event_text(T, lay, ch, fac, off, T['color'])]
            for layer, body in evs:
                lines.append('Dialogue: %d,%s,%s,%s,,0,0,0,,%s\n' % (layer, ts, te, T['font'], body))
    with open(path, 'w', encoding='utf-8') as fh:
        fh.writelines(lines)


def render_stream(ffmpeg, ass_path, fdir, W, H, fps, t_from, n_frames):
    """Start an ffmpeg process that emits n_frames RGBA frames (W x H) of a subtitle canvas.

    write_ass() stores event times relative to its t_from, so the stream always starts at 0
    (t_from is kept for the call signature only; offsetting PTS does not reach the ass filter)."""
    src = 'color=c=black@0.0:s=%dx%d:r=%s:d=%.5f,format=rgba' % (W, H, fps, (n_frames + 1) / fps)
    esc_ass = ass_path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
    esc_fd = fdir.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
    return subprocess.Popen([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', src, '-vf', "ass='%s':fontsdir='%s':alpha=1" % (esc_ass, esc_fd),
                             '-frames:v', str(n_frames), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)


def measure(ffmpeg, texts, fonts, factors, fdir, workdir, fps, tag='front'):
    """Ink-centre offset of every line of every text relative to its \\pos (static, final state, 100%)."""
    if not texts:
        return
    Wm, Hm = 3000, 1400
    lines = [header(Wm, Hm, fonts)]
    jobs = []                                    # (text, line index) per rendered frame
    for T in texts:
        fs = T['size'] * factors[fonts[T['font']]]
        trk = tracking_px(T)
        for li, (_, ln) in enumerate(text_lines(T['text'])):
            if not ln.strip():
                continue
            k = len(jobs)
            jobs.append((T, li))
            lines.append('Dialogue: 1,%s,%s,%s,,0,0,0,,{\\an5\\pos(%d,%d)%s\\fs%.2f\\fsp%.2f\\bord0\\shad0}%s\n' % (
                ass_time(k / fps), ass_time((k + 1) / fps), T['font'], Wm // 2, Hm // 2, font_tags(fonts[T['font']]), fs, trk,
                ''.join(esc(c) for c in ln)))
    p = os.path.join(workdir, 'measure_%s.ass' % tag)
    with open(p, 'w', encoding='utf-8') as fh:
        fh.writelines(lines)
    for T in texts:
        T['_offsets'] = [None] * len(text_lines(T['text']))
        T.pop('_inkw', None)
        T.pop('_ink', None)
    proc = render_stream(ffmpeg, p, fdir, Wm, Hm, fps, 0.0, len(jobs))
    for T, li in jobs:
        buf = proc.stdout.read(Wm * Hm * 4)
        a = np.frombuffer(buf, np.uint8).reshape(Hm, Wm, 4)[:, :, 3]
        ys = np.nonzero(a.max(axis=1) > 96)[0]
        xs = np.nonzero(a.max(axis=0) > 96)[0]
        if len(ys) and len(xs):
            T['_offsets'][li] = ((xs[0] + xs[-1]) / 2.0 - Wm / 2, (ys[0] + ys[-1]) / 2.0 - Hm / 2)
            T['_inkw'] = max(T.get('_inkw', 0), int(xs[-1] - xs[0] + 1))
            if '_ink' not in T:
                T['_ink'] = (int(xs[-1] - xs[0] + 1), int(ys[-1] - ys[0] + 1))
        else:
            T['_offsets'][li] = (0.0, 0.0)
    proc.wait()
    for T in texts:
        first = [o for o in T['_offsets'] if o is not None]
        T['_offset'] = first[0] if first else (0.0, 0.0)
