"""motion_reel.py - gaya "New Era" (rujukan reel promo talking-head): caption 2 tingkat (baris kecil keluar
perkataan demi perkataan + kata kunci besar bercahaya ditaip huruf demi huruf, pilihan dalam kotak garis),
icon 3D pop-up dekat kepala, cincin muka, dan B-roll motion graphics penuh skrin ikut skrip (kad tajuk, pill
"bukan setakat", graf/candlestick, checklist, timeline, network, icon hero) dengan peralihan flash/swipe.

usage:
  PY motion_reel.py plan.json                 render penuh
  PY motion_reel.py plan.json --still 12 31   PNG satu frame pada masa tu (semak cepat)
PY = ~/.claude/skills/video-effect/.venv/Scripts/python.exe   (numpy, opencv, pillow)
plan: lihat SKILL.md dan examples/
"""
import argparse, json, math, os, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--still", type=float, nargs="*")
A = ap.parse_args()
P = json.load(open(A.plan, encoding="utf-8"))

OUT = P["out"]
SRC = P["video"]
AUDIO = P.get("audio")
T0 = float(P.get("t0", 0.0))
FONTS = P.get("fonts", "D:/CLAUDE/kerja/_fonts")
ICONS = P.get("icons_dir", "D:/CLAUDE/kerja/_icons/fluent3d")
SFXDIR = P.get("sfx_dir", "D:/CLAUDE/kerja/_sfx")
YUNET = os.path.expanduser("~/.claude/skills/video-effect/models/yunet.onnx")
W, H, FPS = 1080, 1920, 30


def probe(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True).stdout
    j = json.loads(o)
    s = j["streams"][0]
    return s["width"], s["height"], float(j["format"]["duration"])


SW, SH, SDUR = probe(SRC)
PIECES = [tuple(x) for x in P.get("pieces") or [[0, SDUR]]]
VERT = SH > SW
if VERT:
    VW, VH, VY = W, H, 0
else:
    VW = int(P.get("video_width", 2160))           # 2160 = muka tak besar sangat (latar kabur atas bawah)
    VH = round(VW * SH / SW / 2) * 2
    VY = int(P.get("video_top", (H - VH) // 2))
NV = int(round(sum(b - a for a, b in PIECES) * FPS))
END = P.get("endcard")
NE = int(round(END.get("dur", 1.6) * FPS)) if END else 0

# ---- theme ---------------------------------------------------------------------------------------------
THEMES = {
    "gold": dict(accent=(255, 224, 0), glow=(255, 175, 0), small=("mont", 500, 40), big=("mont", 800, 88),
                 track=0, box=True, box_col=(255, 236, 160), dash=(255, 212, 0), title=(255, 255, 255),
                 title_glow=(255, 160, 40), tfont=("mont", 700), hi=(255, 150, 40), label=(205, 205, 205),
                 icon="gold", trans="flash", sub=("mont", 400, 700), pill_dot=(255, 140, 30)),
    "red": dict(accent=(212, 255, 58), glow=None, small=("inter", 500, 40), big=("tight", 700, 124),
                track=-3, box=False, box_col=None, dash=None, title=(236, 28, 48), title_glow=(236, 28, 48),
                tfont=("tight", 800), hi=(236, 36, 52), label=(200, 200, 200), icon="red", trans="swipe",
                sub=("inter", 400, 700), pill_dot=(236, 36, 52)),
}
TH = dict(THEMES[P.get("theme", "gold")])
TH.update(P.get("theme_overrides", {}))
for k, v in list(TH.items()):
    if isinstance(v, list):
        TH[k] = tuple(v)
CY = int(P.get("caption_y", 1430 if not VERT else 1060))   # tengah caption (paras dada, bawah muka)

FAMS = {"mont": "Montserrat-VF.ttf", "monti": "Montserrat-Italic-VF.ttf", "inter": "Inter-VF.ttf",
        "tight": "InterTight-VF.ttf", "play": "PlayfairDisplay-Italic-VF.ttf"}
_fc = {}


def F(fam, size, wght=400):
    key = (fam, int(size), wght)
    if key in _fc:
        return _fc[key]
    f = ImageFont.truetype(f"{FONTS}/{FAMS[fam]}", int(size))
    try:
        vals = []
        for ax in f.get_variation_axes():
            n = ax.get("name", b"")
            n = n.decode("latin-1") if isinstance(n, bytes) else str(n)
            if "eight" in n:
                vals.append(max(ax["minimum"], min(ax["maximum"], wght)))
            elif "ptical" in n:
                vals.append(max(ax["minimum"], min(ax["maximum"], size)))
            else:
                vals.append(ax.get("default", ax["minimum"]))
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    _fc[key] = f
    return f


# ---- sprite helpers (RGBA float 0..1, straight alpha) -----------------------------------------------------
def over(top, bot):
    ta, ba = top[..., 3:4], bot[..., 3:4]
    oa = ta + ba * (1 - ta)
    oc = (top[..., :3] * ta + bot[..., :3] * ba * (1 - ta)) / np.maximum(oa, 1e-6)
    return np.concatenate([oc, oa], -1)


def halo(spr, col, r, strength):
    """glow/shadow under a sprite."""
    g = cv2.GaussianBlur(spr[..., 3], (0, 0), r) * strength
    lay = np.zeros_like(spr)
    lay[..., :3] = np.array(col, np.float32) / 255
    lay[..., 3] = np.clip(g, 0, 1)
    return over(spr, lay)


def tsprite(text, f, fill, track=0, glow=None, glow_r=12, glow_s=0.7, shadow=True):
    pad = 36 if not glow else max(36, int(glow_r * 3))
    xs = [f.getlength(text[:i]) + track * i for i in range(len(text) + 1)]
    asc, desc = f.getmetrics()
    w, h = int(xs[-1]) + 2 * pad + 6, asc + desc + 2 * pad
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if track == 0:
        d.text((pad, pad), text, font=f, fill=tuple(fill) + (255,))
    else:
        for i, ch in enumerate(text):
            d.text((pad + xs[i], pad), ch, font=f, fill=tuple(fill) + (255,))
    s = np.array(im).astype(np.float32) / 255
    if shadow:
        s = halo(s, (0, 0, 0), 5, 0.55)
    if glow:
        s = halo(s, glow, glow_r, glow_s)
    return dict(img=s, pad=pad, xs=[pad + x for x in xs], w=xs[-1], h=asc + desc, asc=asc)


def blurred(s, r):
    if r < 0.6:
        return s
    k = int(r * 3) | 1
    p = s.copy()
    p[..., :3] *= p[..., 3:4]
    p = cv2.GaussianBlur(p, (k, k), r)
    p[..., :3] /= np.maximum(p[..., 3:4], 1e-4)
    return p


def scaled(s, sc):
    if abs(sc - 1) < 1e-3:
        return s
    h, w = s.shape[:2]
    return cv2.resize(s, (max(1, int(w * sc)), max(1, int(h * sc))), interpolation=cv2.INTER_LINEAR)


def paste(cv, s, x, y, al=1.0):
    """paste sprite with its top-left at (x, y) onto canvas float 0..255."""
    if al <= 0.003:
        return
    x, y = int(round(x)), int(round(y))
    h, w = s.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = s[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sub[..., 3:4] * al
    cv[y0:y1, x0:x1] = cv[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * 255 * a


def pastec(cv, s, cx, cy, al=1.0, sc=1.0, blur=0.0):
    """paste centred at (cx, cy) with scale and blur."""
    s = scaled(blurred(s, blur), sc)
    paste(cv, s, cx - s.shape[1] / 2, cy - s.shape[0] / 2, al)


def ease(k):
    k = min(1.0, max(0.0, k))
    return 1 - (1 - k) ** 3


def back(k):
    k = min(1.0, max(0.0, k))
    c = 1.9
    return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


def clip01(x):
    return min(1.0, max(0.0, x))


def rrect(w, h, r, fill=None, border=None, bw=2, glow=None, glow_r=10, glow_s=0.6):
    pad = 30 if not glow else int(glow_r * 3)
    im = Image.new("RGBA", (int(w) + 2 * pad, int(h) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=r,
                        fill=tuple(fill) if fill else None,
                        outline=tuple(border) if border else None, width=bw)
    s = np.array(im).astype(np.float32) / 255
    if glow:
        s = halo(s, glow, glow_r, glow_s)
    return s


def star_pts(cx, cy, r, ri=None):
    ri = ri or r * 0.28
    pts = []
    for k in range(8):
        a = -math.pi / 2 + k * math.pi / 4
        rr = r if k % 2 == 0 else ri
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def star_sprite(r, col=(255, 255, 255), glow=True):
    n = int(r * 2 + 40)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon(star_pts(n / 2, n / 2, r), fill=tuple(col) + (255,))
    s = np.array(im).astype(np.float32) / 255
    return halo(s, col, r * 0.6, 0.5) if glow else s


# ---- icons ---------------------------------------------------------------------------------------------
_ic = {}


def icon_sprite(name, size, mode=None):
    mode = mode or TH["icon"]
    key = (name, int(size), mode)
    if key in _ic:
        return _ic[key]
    path = name if os.path.isfile(name) else f"{ICONS}/{name}.png"
    im = Image.open(path).convert("RGBA").resize((int(size), int(size)), Image.LANCZOS)
    s = np.array(im).astype(np.float32) / 255
    pad = int(size * 0.3)
    s = np.pad(s, ((pad, pad), (pad, pad), (0, 0)))
    rgb, a = s[..., :3], s[..., 3]
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    if mode == "gold":
        xp = [0, 0.4, 0.72, 1]
        cols = np.array([(80, 40, 6), (232, 148, 22), (255, 214, 96), (255, 250, 234)], np.float32) / 255
        lum2 = np.clip(lum * 1.15, 0, 1)
        rgb = np.stack([np.interp(lum2, xp, cols[:, c]) for c in range(3)], -1)
        s = np.concatenate([rgb, a[..., None]], -1)
        s = halo(s, (255, 190, 50), size * 0.09, 0.55)
    elif mode == "red":
        body = np.clip(lum * 0.25 + 0.03, 0, 1)[..., None] * np.ones(3, np.float32)
        er = cv2.erode(a, np.ones((max(3, int(size * 0.035)),) * 2, np.uint8))
        rim = np.clip(cv2.GaussianBlur(a - er, (0, 0), 1.5) * 1.6, 0, 1)[..., None]
        spec = np.clip((lum - 0.8) * 4, 0, 1)[..., None] * 0.5
        rgb = body * (1 - rim) + np.array([1.0, 0.16, 0.2]) * rim + spec * np.array([1, 0.5, 0.5])
        s = np.concatenate([np.clip(rgb, 0, 1).astype(np.float32), a[..., None]], -1)
        s = halo(s, (255, 30, 40), size * 0.1, 0.8)
    _ic[key] = s
    return s


def rotated(s, deg):
    if abs(deg) < 0.2:
        return s
    h, w = s.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(s, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))


# ---- captions on the talking head ------------------------------------------------------------------------
def timed(words, t, end):
    """'kata kata' or [[kata, t]] -> [[kata, t]] (string = spread evenly from t)."""
    if not words:
        return []
    if isinstance(words, str):
        ws = words.split()
        span = max(0.3, (end - t)) * 0.8
        return [[w, t + span * i / max(1, len(ws))] for i, w in enumerate(ws)]
    return [[w, float(x)] for w, x in words]


class Caption:
    def __init__(self, c):
        self.out = float(c["out"])
        t = float(c.get("t", 0))
        bigl = c.get("big")
        big_t = float(c.get("big_t", self.out - 0.6))
        self.small = timed(c.get("small"), t, big_t if bigl else self.out)
        self.big = timed(bigl, big_t, self.out) if not isinstance(bigl, str) else [[w, big_t + 0.25 * i] for i, w in enumerate(bigl.split())]
        self.italic = c.get("italic", False)
        self.boxed = c.get("box", TH["box"]) and bool(self.big)
        fam, wght, size = TH["small"]
        fs = F("monti" if self.italic and fam == "mont" else fam, c.get("small_size", size), wght)
        self.ws = [(tsprite(w, fs, (255, 255, 255)), tt) for w, tt in self.small]
        sp = fs.getlength(" ")
        tot = sum(s["w"] for s, _ in self.ws) + sp * max(0, len(self.ws) - 1)
        y_small = CY - (78 if self.big else 0)
        x = W / 2 - tot / 2
        self.wpos = []
        for s, tt in self.ws:
            self.wpos.append((x - s["pad"], y_small - s["asc"] * 0.62 - s["pad"]))
            x += s["w"] + sp
        self.small_w, self.y_small = tot, y_small
        self.t_in = min([tt for _, tt in self.small] + [tt for _, tt in self.big] + [99999])
        if self.big:
            text = " ".join(w for w, _ in self.big)
            bfam, bw, bsize = TH["big"]
            bsize = c.get("big_size", bsize)
            while bsize > 40:
                f = F(bfam, bsize, bw)
                if f.getlength(text) + TH["track"] * len(text) <= (820 if self.boxed else 960):
                    break
                bsize -= 4
            self.bs = tsprite(text, f, TH["accent"], track=TH["track"], glow=TH["glow"], glow_r=12, glow_s=0.65)
            # time each character: within a word chars type over <= 0.22 s
            self.ct = []
            for w, tt in self.big:
                n = len(w)
                for j in range(n):
                    self.ct.append(tt + 0.22 * j / max(1, n))
                self.ct.append(tt + 0.22)            # the space after
            self.ct = self.ct[:len(text)]
            self.by = CY + 22
            if self.boxed:
                bw_, bh_ = self.bs["w"] + 64, self.bs["h"] * 0.92 + 30
                self.box = rrect(bw_, bh_, 14, border=TH["box_col"] + (235,), bw=3, glow=TH["glow"], glow_r=8, glow_s=0.45)
                self.box_c = (W / 2, self.by)
                dl = rrect(54, 4, 2, fill=TH["dash"] + (255,))
                self.dash = dl

    def draw(self, cv, t):
        if t < self.t_in - 0.3 or t > self.out + 0.2:
            return
        fade = 1 - clip01((t - self.out) / 0.15)
        if self.boxed:
            e = ease((t - self.t_in) / 0.28)
            if e > 0:
                pastec(cv, self.box, self.box_c[0], self.box_c[1], e * fade, 0.94 + 0.06 * e)
                half = self.small_w / 2 + 52
                for sgn in (-1, 1):
                    pastec(cv, self.dash, W / 2 + sgn * half, self.y_small, e * fade, 0.5 + 0.5 * e)
        for (s, tt), (x, y) in zip(self.ws, self.wpos):
            e = ease((t - tt) / 0.14)
            if e > 0:
                paste(cv, s["img"], x, y + 10 * (1 - e), e * fade)
        if self.big:
            n = sum(1 for x in self.ct if x <= t)
            if n == 0:
                return
            s = self.bs
            if n < len(self.ct):
                nxt = self.ct[n]
                prv = self.ct[n - 1]
                frac = clip01((t - prv) / max(1e-3, nxt - prv))
                cut = s["xs"][n - 1] + frac * (s["xs"][n] - s["xs"][n - 1])
            else:
                cut = 1e9
            img = s["img"]
            if cut < img.shape[1]:
                img = img.copy()
                cols = np.arange(img.shape[1], dtype=np.float32)
                img[..., 3] *= np.clip((cut - cols) / 10 + 0.5, 0, 1)[None, :]
            pop = 1 + 0.05 * (1 - ease((t - self.big[0][1]) / 0.18))
            pastec(cv, img, W / 2, self.by, fade, pop)


# ---- scene (full-screen B-roll motion graphics) ------------------------------------------------------------
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
RAD = np.clip(1 - np.sqrt(((XX - W / 2) / (W * 0.72)) ** 2 + ((YY - H * 0.45) / (H * 0.5)) ** 2), 0, 1)[..., None]


def make_bg(theme):
    if theme == "gold":
        bg = np.full((H, W, 3), 7, np.float32)
        g = np.exp(-(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H * 1.02) / (H * 0.24)) ** 2))[..., None]
        bg += g * np.array([200, 100, 14], np.float32) * 0.8
        v = np.exp(-(((XX - W / 2) / (W * 0.9)) ** 2 + ((YY - H * 0.35) / (H * 0.6)) ** 2))[..., None]
        bg += v * 10
    else:
        bg = np.full((H, W, 3), 9, np.float32)
        beam = np.exp(-((XX - W * 0.5) / (W * 0.33)) ** 2) * np.clip(1 - YY / (H * 0.85), 0, 1) ** 1.4
        bg += beam[..., None] * np.array([58, 58, 62], np.float32)
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        for cx, cy, r in ((150, 1600, 110), (930, 260, 90), (960, 1720, 80)):   # faint asterisks
            for k in range(6):
                a = k * math.pi / 6
                d.line([cx - r * math.cos(a), cy - r * math.sin(a), cx + r * math.cos(a), cy + r * math.sin(a)], fill=255, width=7)
        bg += (np.array(img, np.float32) / 255)[..., None] * 22
    return bg


BG = make_bg(P.get("theme", "gold"))
rng = np.random.default_rng(7)
SPARK = [(rng.uniform(80, W - 80), rng.uniform(250, 1400), rng.uniform(7, 13), rng.uniform(0, 6.28)) for _ in range(7)]
EMBER = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(25, 70), rng.uniform(1.5, 3.5), rng.uniform(0, 6.28)) for _ in range(46)]
STAR = {r: star_sprite(r) for r in range(6, 15)}
DOT = {}


def dot(r, col):
    key = (r, col)
    if key not in DOT:
        n = int(r * 8 + 8)
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([n / 2 - r, n / 2 - r, n / 2 + r, n / 2 + r], fill=tuple(col) + (255,))
        DOT[key] = halo(np.array(im).astype(np.float32) / 255, col, r * 1.5, 0.9)
    return DOT[key]


def background(t):
    cv = BG.copy()
    if P.get("theme", "gold") == "gold":
        cv *= 0.94 + 0.06 * math.sin(t * 1.7)
        for x, y, r, ph in SPARK:
            k = 0.5 + 0.5 * math.sin(t * 2.2 + ph)
            pastec(cv, STAR[int(r)], x, y, 0.25 + 0.65 * k, 0.6 + 0.4 * k)
    else:
        for x, y, sp, r, ph in EMBER:
            yy = (y - sp * t * 3) % H
            xx = x + 12 * math.sin(t * 0.9 + ph)
            a = 0.35 + 0.45 * (0.5 + 0.5 * math.sin(t * 3 + ph))
            pastec(cv, dot(int(r), (255, 70, 40)), xx, yy, a)
    return cv


def label_spr(text):
    f = F("mont", 30, 500)
    return tsprite(text.upper(), f, TH["label"], track=11, shadow=False)


def pill_spr(text, size=56, star=True, dotc=None, fill=(30, 30, 30), border=(98, 98, 98), weight=500, fam="inter"):
    f = F(fam, size, weight)
    tw = f.getlength(text)
    lead = size * 0.95 if (star or dotc) else 0
    w, h = tw + lead + size * 1.1, size * 1.9
    s = rrect(w, h, h / 2, fill=fill + (238,), border=border + (255,), bw=3)
    im = Image.fromarray((s * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    pad = 30
    asc, desc = f.getmetrics()
    tx = pad + size * 0.55 + lead
    if star:
        d.polygon(star_pts(pad + size * 0.55 + size * 0.36, pad + h / 2, size * 0.32), fill=(255, 255, 255, 255))
    elif dotc:
        r = size * 0.2
        cx = pad + size * 0.55 + size * 0.3
        d.ellipse([cx - r, pad + h / 2 - r, cx + r, pad + h / 2 + r], fill=tuple(dotc) + (255,))
    d.text((tx, pad + h / 2 - (asc + desc) / 2 + desc * 0.3), text, font=f, fill=(255, 255, 255, 255))
    out = np.array(im).astype(np.float32) / 255
    return dict(img=out, w=w, h=h, tx=tx, tw=tw)


def appear(cv, s, cx, cy, t, t0, dur=0.32, dy=26, al=1.0, blur=9):
    e = ease((t - t0) / dur)
    if e <= 0:
        return 0
    pastec(cv, s, cx, cy + dy * (1 - e), e * al, 1.0, blur * (1 - e))
    return e


class SceneSubs:
    """bottom caption in a scene: words light up (bold, white) as they are spoken; *word* = accent colour."""

    def __init__(self, subs):
        fam, w0, w1 = TH["sub"]
        self.items = []
        for a, b, text in subs:
            a, b = float(a), float(b)
            toks = text.split()
            n = len(toks)
            fb, fr = F(fam, 44, w1), F(fam, 44, w0)
            words = []
            for i, tok in enumerate(toks):
                acc = tok.startswith("*") and tok.endswith("*") and len(tok) > 2
                w = tok.strip("*")
                col = TH["hi"] if acc else (255, 255, 255)
                words.append(dict(b=tsprite(w, fb, col), r=tsprite(w, fr, col if acc else (232, 232, 232)),
                                  t=a + (b - a - 0.25) * i / max(1, n)))
            sp = fb.getlength(" ")
            lines, cur, cw = [], [], 0
            for wd in words:
                ww = wd["b"]["w"]
                if cur and cw + sp + ww > 860:
                    lines.append((cur, cw)); cur, cw = [], 0
                cw = cw + (sp if cur else 0) + ww
                cur.append(wd)
            if cur:
                lines.append((cur, cw))
            for li, (ws, lw) in enumerate(lines):
                x = W / 2 - lw / 2
                for wd in ws:
                    wd["x"] = x + wd["b"]["w"] / 2
                    wd["y"] = 1175 + li * 62
                    x += wd["b"]["w"] + sp
            self.items.append((a, b, words))

    def draw(self, cv, t):
        for a, b, words in self.items:
            if not (a - 0.05 <= t <= b + 0.15):
                continue
            al = clip01((t - a) / 0.2) * (1 - clip01((t - b) / 0.15))
            for wd in words:
                s = wd["b"] if t >= wd["t"] else wd["r"]
                pastec(cv, s["img"], wd["x"], wd["y"], al * (1.0 if t >= wd["t"] else 0.82))


def line_draw(cv, pts, k, col, th=5, glow=True, dots=False):
    """polyline drawn progressively (k 0..1)."""
    if k <= 0:
        return
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    tot, L = sum(seg), sum(seg) * k
    out = [pts[0]]
    for i, s in enumerate(seg):
        if L >= s:
            out.append(pts[i + 1]); L -= s
        else:
            f = L / s
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f))
            break
    xs = [p[0] for p in out]; ys = [p[1] for p in out]
    x0, y0 = int(max(0, min(xs) - 60)), int(max(0, min(ys) - 60))
    x1, y1 = int(min(W, max(xs) + 60)), int(min(H, max(ys) + 60))
    if x1 <= x0 or y1 <= y0:
        return
    m = np.zeros((y1 - y0, x1 - x0), np.float32)
    cv2.polylines(m, [np.array([(p[0] - x0, p[1] - y0) for p in out], np.int32)], False, 1.0, th, cv2.LINE_AA)
    a = m
    if glow:
        a = np.clip(m + cv2.GaussianBlur(m, (0, 0), th * 2.2) * 1.2, 0, 1)
    reg = cv[y0:y1, x0:x1]
    c = np.array(col, np.float32)
    reg[:] = reg * (1 - a[..., None]) + c * a[..., None]
    if dots:
        for i, p in enumerate(out[:-1] if k < 1 else out):
            pastec(cv, dot(7, (255, 255, 255)), p[0], p[1])


class Scene:
    def __init__(self, sc):
        self.s = sc
        self.a, self.b = float(sc["t"]), float(sc["out"])
        self.type = sc.get("type", "title")
        self.tin = sc.get("in", TH["trans"])
        self.tout = sc.get("out_trans", TH["trans"])
        self.subs = SceneSubs(sc.get("subs", []))
        self.label = label_spr(sc["label"]) if sc.get("label") else None
        self.stamp = None
        if sc.get("stamp"):
            txt, tt = sc["stamp"]
            f = F("inter", 46, 800)
            txt = txt.upper()
            asc, desc = f.getmetrics()
            w, h = f.getlength(txt) + 50, asc + desc + 20
            im = Image.new("RGBA", (int(w) + 80, int(h) + 80), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([40, 40, 40 + w, 40 + h], radius=6, outline=TH["hi"] + (255,), width=5)
            d.text((65, 50), txt, font=f, fill=TH["hi"] + (255,))
            self.stamp = (rotated(np.array(im).astype(np.float32) / 255, 12), float(tt))
        getattr(self, "build_" + self.type)(sc)

    # -- title: pill tag, small line, big title, small line under
    def build_title(self, sc):
        self.pill = pill_spr(sc["pill"][0], 34, star=False, dotc=TH["pill_dot"], fill=(16, 16, 16), border=(60, 60, 60), weight=700) if sc.get("pill") else None
        f = F("mont" if TH["sub"][0] == "mont" else "inter", 44, 500)
        self.pre = (tsprite(sc["pre"][0], f, (235, 235, 235)), float(sc["pre"][1])) if sc.get("pre") else None
        self.post = (tsprite(sc["post"][0], f, (210, 210, 210)), float(sc["post"][1])) if sc.get("post") else None
        self.title = self.mk_title(sc["title"]) if sc.get("title") else None

    def mk_title(self, tt, maxw=950, size=None):
        text, t0 = tt[0], float(tt[1])
        fam, wght = TH["tfont"]
        size = size or (150 if fam == "tight" else 120)
        while size > 40 and F(fam, size, wght).getlength(text) > maxw:
            size -= 4
        s = tsprite(text, F(fam, size, wght), TH["title"], track=-2 if fam == "tight" else 0,
                    glow=TH["title_glow"], glow_r=14, glow_s=0.55 if fam == "tight" else 0.3)
        ct = [t0 + min(0.45, 0.035 * len(text)) * i / max(1, len(text)) for i in range(len(text))]
        return dict(s=s, ct=ct, t=t0)

    def draw_title_spr(self, cv, T, cy, t):
        s, ct = T["s"], T["ct"]
        n = sum(1 for x in ct if x <= t)
        if n == 0:
            return
        img = s["img"]
        if n < len(ct):
            cut = s["xs"][n]
            img = img.copy()
            cols = np.arange(img.shape[1], dtype=np.float32)
            img[..., 3] *= np.clip((cut - cols) / 14 + 0.5, 0, 1)[None, :]
        e = ease((t - T["t"]) / 0.3)
        pastec(cv, img, W / 2, cy, 1.0, 1.04 - 0.04 * e, 6 * (1 - e))

    def draw_title(self, cv, t):
        if self.pill:
            appear(cv, self.pill["img"], W / 2, 640, t, float(self.s["pill"][1]))
        if self.pre:
            appear(cv, self.pre[0]["img"], W / 2, 790, t, self.pre[1])
        if self.title:
            self.draw_title_spr(cv, self.title, 880, t)
        if self.post:
            appear(cv, self.post[0]["img"], W / 2, 975, t, self.post[1])

    # -- pills: "bukan setakat" list, optional strike-through
    def build_pills(self, sc):
        self.items = [(pill_spr(x, 56), float(tt)) for x, tt in sc["items"]]
        self.strike = float(sc["strike"]) if sc.get("strike") is not None else None

    def draw_pills(self, cv, t):
        n = len(self.items)
        y0 = 760 - (n - 1) * 97
        for i, (p, tt) in enumerate(self.items):
            cy = y0 + i * 194
            al = 1.0
            ks = 0
            if self.strike is not None:
                ks = ease((t - self.strike - 0.1 * i) / 0.25)
                al = 1 - 0.45 * ks
            e = appear(cv, p["img"], W / 2, cy, t, tt, al=al)
            if e > 0 and ks > 0:
                x0 = W / 2 - p["img"].shape[1] / 2 + p["tx"] - 10
                x1 = x0 + (p["tw"] + 20) * ks
                yy = int(cy)
                cv2.line(cv, (int(x0), yy), (int(x1), yy), tuple(float(c) for c in TH["hi"]), 5, cv2.LINE_AA)

    # -- chart: glass card with a line that draws (gold) or neon candlesticks with a zigzag (red)
    def build_chart(self, sc):
        self.title = self.mk_title(sc["title"], size=120) if sc.get("title") else None
        f = F(TH["sub"][0], 42, 500)
        self.pre = (tsprite(sc["pre"][0], f, (235, 235, 235)), float(sc["pre"][1])) if sc.get("pre") else None
        self.draw_t = float(sc.get("draw_t", self.a + 0.3))
        self.items = [(pill_spr(x, 36), float(tt)) for x, tt in sc.get("items", [])]
        self.style = sc.get("style", "candles" if P.get("theme") == "red" else "card")
        self.card = rrect(760, 470, 30, fill=(22, 22, 22, 245), border=(70, 70, 70, 255), bw=2)
        r = np.random.default_rng(sc.get("seed", 3))
        down = sc.get("trend", "up") == "down"
        n = 14
        base = np.cumsum(r.normal(0.6 if not down else -0.6, 1.0, n))
        base = (base - base.min()) / (np.ptp(base) + 1e-6)
        self.cand = []
        for i in range(n):
            o = base[i - 1] if i else base[0] - 0.05
            c = base[i]
            self.cand.append((o, c, max(o, c) + r.uniform(0.03, 0.1), min(o, c) - r.uniform(0.03, 0.1)))
        self.line = [(0.06, 0.8), (0.24, 0.6), (0.38, 0.72), (0.55, 0.45), (0.68, 0.55), (0.86, 0.25), (0.94, 0.32)]
        if down:
            self.line = [(x, 1 - y) for x, y in self.line]

    def draw_chart(self, cv, t):
        if self.pre:
            appear(cv, self.pre[0]["img"], W / 2, 380, t, self.pre[1])
        if self.title:
            self.draw_title_spr(cv, self.title, 470, t)
        k = clip01((t - self.draw_t) / 0.9)
        if self.style == "card":
            cx, cy = W / 2, 790
            e = appear(cv, self.card, cx, cy, t, self.a + 0.05)
            if e > 0:
                for g in range(1, 4):
                    yy = int(cy - 235 + g * 117)
                    cv[yy:yy + 1, int(cx - 340):int(cx + 340)] = cv[yy:yy + 1, int(cx - 340):int(cx + 340)] * 0.6 + 60 * 0.4 * e
                pts = [(cx - 330 + x * 660, cy - 190 + y * 380) for x, y in self.line]
                line_draw(cv, pts, k, TH["hi"], 6)
            for j, (p, tt) in enumerate(self.items):
                tot = sum(q["img"].shape[1] - 60 for q, _ in self.items) + 20 * (len(self.items) - 1)
                x = W / 2 + 380 - tot + sum(q["img"].shape[1] - 60 + 20 for q, _ in self.items[:j]) + (p["img"].shape[1] - 60) / 2
                appear(cv, p["img"], x, 1090, t, tt, dy=14)
        else:
            x0, x1, ytop, ybot = 120, 960, 720, 1380
            n = len(self.cand)
            cw = (x1 - x0) / n
            for i, (o, c, hi, lo) in enumerate(self.cand):
                ki = clip01((t - self.draw_t + 0.3 - i * 0.05) / 0.25)
                if ki <= 0:
                    continue
                col = (40, 230, 110) if c >= o else (240, 40, 50)
                X = x0 + cw * (i + 0.5)
                Y = lambda v: ybot - v * (ybot - ytop)
                m = np.zeros((H, W), np.float32)
                cv2.line(m, (int(X), int(Y(hi))), (int(X), int(Y(lo))), 1.0, 3, cv2.LINE_AA)
                cv2.rectangle(m, (int(X - cw * 0.3), int(Y(max(o, c)))), (int(X + cw * 0.3), int(Y(min(o, c)) + 2)), 0.55, -1)
                cv2.rectangle(m, (int(X - cw * 0.3), int(Y(max(o, c)))), (int(X + cw * 0.3), int(Y(min(o, c)) + 2)), 1.0, 2)
                ys, ye = int(Y(hi)) - 40, int(Y(lo)) + 40
                xs_, xe = int(X - cw), int(X + cw)
                sub = m[ys:ye, xs_:xe]
                a = np.clip(sub + cv2.GaussianBlur(sub, (0, 0), 9) * 0.9, 0, 1) * ki
                cv[ys:ye, xs_:xe] = cv[ys:ye, xs_:xe] * (1 - a[..., None]) + np.array(col, np.float32) * a[..., None]
                # reflection
                ry0 = ybot + 40
                rs = sub[::-1] * 0.25 * ki
                rs = rs * np.clip(1 - np.arange(rs.shape[0], dtype=np.float32) / 220, 0, 1)[:, None]
                rh = min(rs.shape[0], H - ry0 - 1)
                if rh > 0:
                    cv[ry0:ry0 + rh, xs_:xe] += rs[:rh, :, None] * np.array(col, np.float32)
            kz = clip01((t - float(self.s.get("line_t", self.draw_t + 0.9))) / 0.9)
            pts = [(x0 + x * (x1 - x0), ybot - (1 - y) * (ybot - ytop)) for x, y in self.line]
            line_draw(cv, pts, kz, (240, 30, 45), 5, dots=True)

    # -- checklist: title + numbered rows with ticks
    def build_checklist(self, sc):
        self.title = self.mk_title(sc["title"], size=96) if sc.get("title") else None
        fn, ft = F("inter", 46, 800), F("inter", 40, 500)
        self.items = [(tsprite(f"{i + 1:02d}", fn, TH["hi"]), tsprite(x, ft, (240, 240, 240)), float(tt))
                      for i, (x, tt) in enumerate(sc["items"])]

    def draw_checklist(self, cv, t):
        if self.title:
            self.draw_title_spr(cv, self.title, 600, t)
        for i, (sn, st, tt) in enumerate(self.items):
            cy = 740 + i * 100
            e = ease((t - tt) / 0.3)
            if e <= 0:
                continue
            dx = -40 * (1 - e)
            paste(cv, blurred(sn["img"], 6 * (1 - e)), 150 + dx - sn["pad"], cy - sn["asc"] * 0.6 - sn["pad"], e)
            paste(cv, blurred(st["img"], 6 * (1 - e)), 245 + dx - st["pad"], cy - st["asc"] * 0.6 - st["pad"], e)
            kt = back((t - tt - 0.35) / 0.25)
            if kt > 0:
                m = np.zeros((H, W), np.float32)
                cv2.polylines(m, [np.array([(900, cy), (915, cy + 15), (944, cy - 16)], np.int32)], False, 1.0, 6, cv2.LINE_AA)
                a = np.clip(m + cv2.GaussianBlur(m, (0, 0), 8), 0, 1)[..., None] * clip01(kt)
                cv[:] = cv * (1 - a) + np.array(TH["hi"], np.float32) * a

    # -- timeline: vertical line with glowing dots and cards
    def build_timeline(self, sc):
        ft, fs = F("inter", 38, 600), F("inter", 26, 400)
        self.items = []
        for it in sc["items"]:
            title, sub, tt = (it + [None])[:3] if len(it) == 3 else (it[0], "", it[1])
            card = rrect(640, 108, 18, fill=(26, 26, 26, 240), border=(64, 64, 64, 255), bw=2)
            ts = tsprite(title, ft, (245, 245, 245), shadow=False)
            ss = tsprite(sub, fs, (150, 150, 150), shadow=False) if sub else None
            self.items.append((card, ts, ss, float(tt)))

    def draw_timeline(self, cv, t):
        n = len(self.items)
        y0 = 830 - (n - 1) * 70
        lx = 205
        if n:
            ktop = self.items[0][3]
            last = y0 + (n - 1) * 140
            kk = clip01((t - ktop) / max(0.3, (self.items[-1][3] - ktop) + 0.3))
            if kk > 0:
                y1 = int(y0 - 40 + (last - y0 + 80) * kk)
                cv[y0 - 40:y1, lx - 2:lx + 2] = cv[y0 - 40:y1, lx - 2:lx + 2] * 0.3 + np.array(TH["hi"], np.float32) * 0.7
        for i, (card, ts, ss, tt) in enumerate(self.items):
            cy = y0 + i * 140
            e = ease((t - tt) / 0.32)
            if e <= 0:
                continue
            pastec(cv, dot(9, TH["hi"]), lx, cy, e)
            cx = 260 + 320 - 40 * (1 - e)
            pastec(cv, card, cx, cy, e, 1, 6 * (1 - e))
            paste(cv, ts["img"], 300 - 40 * (1 - e) - ts["pad"], cy - (22 if ss else 0) - ts["asc"] * 0.6 - ts["pad"], e)
            if ss:
                paste(cv, ss["img"], 300 - 40 * (1 - e) - ss["pad"], cy + 22 - ss["asc"] * 0.6 - ss["pad"], e)

    # -- network: centre node + up to 4 nodes joined by drawing lines
    def build_network(self, sc):
        f = F("inter", 30, 600)
        self.center = (icon_sprite(sc["center"][1], 130), tsprite(sc["center"][0], f, (255, 255, 255)), float(sc["center"][2]))
        self.nodes = [(icon_sprite(ic, 110), tsprite(lb, f, (255, 255, 255)), float(tt)) for lb, ic, tt in sc["nodes"]]
        self.pos = [(270, 610), (810, 610), (540, 1060), (200, 1000), (880, 1000)]

    def draw_network(self, cv, t):
        C = (540, 820)
        for (ic, lb, tt), p in zip(self.nodes, self.pos):
            k = ease((t - tt) / 0.4)
            if k > 0:
                line_draw(cv, [C, (C[0] + (p[0] - C[0]) * 0.86, C[1] + (p[1] - C[1]) * 0.86)], k, TH["hi"], 3)
                e = back((t - tt - 0.25) / 0.3)
                if e > 0:
                    pastec(cv, ic, p[0], p[1], clip01(e), max(0.05, e))
                    pastec(cv, lb["img"], p[0], p[1] + 85, clip01(e))
        ic, lb, tt = self.center
        e = back((t - tt) / 0.35)
        if e > 0:
            pastec(cv, dot(46, TH["hi"]), C[0], C[1], 0.35 * clip01(e))
            pastec(cv, ic, C[0], C[1], clip01(e), max(0.05, e))
            pastec(cv, lb["img"], C[0], C[1] + 95, clip01(e))

    # -- hero: big icon under light beams + big word
    def build_hero(self, sc):
        self.icon = (icon_sprite(sc["icon"][0], sc.get("icon_size", 360)), float(sc["icon"][1]))
        self.word = self.mk_title(sc["word"], size=110) if sc.get("word") else None
        self.pill = pill_spr(sc["pill"][0], 24, star=False, dotc=None, fill=(14, 14, 14), border=TH["hi"], weight=700) if sc.get("pill") else None
        beam = np.zeros((H, W), np.float32)
        for sgn in (-1, 1):
            poly = np.array([(W / 2 + sgn * 470, 0), (W / 2 + sgn * 300, 0), (W / 2 - sgn * 10, 830), (W / 2 - sgn * 70, 830)], np.int32)
            cv2.fillPoly(beam, [poly], 1.0)
        beam = cv2.GaussianBlur(beam, (0, 0), 22) * np.clip(1 - YY / 900, 0, 1)
        self.beam = beam[..., None] * np.array(TH["glow"] or TH["hi"], np.float32) * 0.35

    def draw_hero(self, cv, t):
        kb = clip01((t - self.a) / 0.5)
        cv += self.beam * kb
        ic, tt = self.icon
        e = back((t - tt) / 0.45)
        if e > 0:
            pastec(cv, ic, W / 2, 780 + 6 * math.sin((t - tt) * 2.4), clip01(e * 1.5), max(0.05, 0.6 + 0.4 * e))
        if self.pill:
            appear(cv, self.pill["img"], W / 2, 945, t, tt + 0.25, dy=10)
        if self.word:
            self.draw_title_spr(cv, self.word, 1045, t)

    # -- end card (brand)
    def build_end(self, sc):
        self.big = tsprite(sc.get("text", ""), F("play", 110, 700), TH["accent"] if P.get("theme") == "red" else (255, 80, 170), glow=(255, 60, 160), glow_r=16, glow_s=0.6)
        self.sm = tsprite(sc.get("sub", "").upper(), F("mont", 34, 700), (255, 255, 255), track=6)

    def draw_end(self, cv, t):
        al = clip01((t - self.a) / 0.35) * (1 - clip01((t - self.b + 0.35) / 0.35))
        bw = self.big["w"] + 24 + self.sm["w"]
        x = W / 2 - bw / 2
        paste(cv, self.big["img"], x - self.big["pad"], 900 - self.big["asc"] * 0.7 - self.big["pad"], al)
        paste(cv, self.sm["img"], x + self.big["w"] + 24 - self.sm["pad"], 912 - self.sm["asc"] * 0.6 - self.sm["pad"], al)

    def render(self, t):
        cv = background(t)
        if self.label:
            k = ease((t - self.a) / 0.4)
            pastec(cv, self.label["img"], W / 2 + 24, 450, k)
            pastec(cv, STAR[10], W / 2 - self.label["w"] / 2 - 22, 450, k, 0.9)
        getattr(self, "draw_" + self.type)(cv, t)
        if self.stamp:
            s, tt = self.stamp
            e = ease((t - tt) / 0.18)
            if e > 0:
                pastec(cv, s, 760, 1010, e, 1.7 - 0.7 * e)
        self.subs.draw(cv, t)
        return cv


# ---- transitions -----------------------------------------------------------------------------------------
FLASH = np.clip(1.15 - np.sqrt(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H * 0.48) / (H * 0.42)) ** 2) * 0.75, 0, 1)[..., None]
DIAG = (XX / W + (1 - YY / H)) / 2


def transition(cv, kind, dt):
    """dt = t - boundary time."""
    if kind == "flash" and abs(dt) < 0.17:
        a = (1 - abs(dt) / 0.17) ** 1.5 * 0.92
        cv[:] = cv * (1 - a * FLASH) + 250 * a * FLASH
    elif kind == "swipe" and abs(dt) < 0.16:
        p = (dt + 0.16) / 0.32 * 1.7 - 0.35
        band = np.clip(1 - np.abs(DIAG - p) / 0.1, 0, 1) ** 0.6
        cv[:] = cv * (1 - band[..., None]) + np.array(TH["hi"], np.float32) * band[..., None]
    elif kind == "blur" and abs(dt) < 0.15:
        k = 1 - abs(dt) / 0.15
        cv[:] = cv2.GaussianBlur(cv, (0, 0), 1 + 22 * k)


# ---- plan objects ----------------------------------------------------------------------------------------
CAPS = [Caption(c) for c in P.get("captions", [])]
SCENES = [Scene(s) for s in P.get("scenes", [])]
ICON_EV = [dict(c, _fixed="pos" in c) for c in P.get("icons", [])]   # "pos": [x, y] pins an icon (scenery, crowds)
RINGS = P.get("rings", [])
if END:
    vend = T0 + NV / FPS
    SCENES.append(Scene({"type": "end", "t": vend, "out": vend + NE / FPS, "text": END.get("text", ""),
                         "sub": END.get("sub", ""), "in": END.get("in", "blur"), "out_trans": "none"}))


def draw_icon(cv, ev, t, face):
    t0, t1 = float(ev["t"]), float(ev["out"])
    if t < t0 or t > t1 + 0.25:
        return
    size = ev.get("size", 230)
    if "pos" not in ev:
        side = ev.get("side", "left")
        sgn = -1 if side == "left" else 1
        if face is not None:
            fx, fy, fw, fh = face
            cx = fx + fw / 2 + sgn * (fw * 0.55 + size * 0.62)
            cy = fy - size * 0.05
        else:
            cx, cy = W / 2 + sgn * 300, VY + VH * 0.25
        ev["pos"] = (float(np.clip(cx, size * 0.6, W - size * 0.6)), float(np.clip(cy, size * 0.6 + 60, H - size)))
    cx, cy = ev["pos"]
    sgn = -1 if ev.get("side", "left") == "left" else 1
    s = icon_sprite(ev["icon"], size, ev.get("tint"))
    k = (t - t0) / 0.42
    e, eb = ease(k), back(k)
    x = cx + sgn * 150 * (1 - e)
    y = cy + 300 * (1 - e) + 7 * math.sin((t - t0) * 2.6)
    sc = 0.3 + 0.7 * eb
    rot = -sgn * 24 * (1 - e)
    ex = clip01((t - t1) / 0.22)
    al = clip01(k * 3) * (1 - ex)
    pastec(cv, rotated(s, rot), x, y, al, max(0.05, sc * (1 - 0.2 * ex)))


def draw_ring(cv, rg, t, face):
    t0, t1 = float(rg["t"]), float(rg["out"])
    if face is None or t < t0 or t > t1 + 0.2 or face[2] < rg.get("min_face", 160):
        return                                  # no ring on small faces (passers-by)
    fx, fy, fw, fh = face
    cx, cy, r = fx + fw / 2, fy + fh / 2 - fh * 0.05, min(max(fw, fh) * 0.95, rg.get("max_r", 330))
    k = ease((t - t0) / 0.45)
    al = 1 - clip01((t - t1) / 0.2)
    x0, y0 = int(max(0, cx - r - 40)), int(max(0, cy - r - 40))
    x1, y1 = int(min(W, cx + r + 40)), int(min(H, cy + r + 40))
    m = np.zeros((y1 - y0, x1 - x0), np.float32)
    cv2.ellipse(m, (int(cx - x0), int(cy - y0)), (int(r), int(r)), -90, 0, 360 * k, 1.0, 4, cv2.LINE_AA)
    a = np.clip(m + cv2.GaussianBlur(m, (0, 0), 6) * 0.8, 0, 1)[..., None] * al
    cv[y0:y1, x0:x1] = cv[y0:y1, x0:x1] * (1 - a) + 255 * a


def active_scene(t):
    for s in SCENES:
        if s.a <= t < s.b:
            return s
    return None


def compose(t, base, face):
    sc = active_scene(t)
    if sc is not None:
        cv = sc.render(t)
    else:
        cv = base.copy() if base is not None else np.zeros((H, W, 3), np.float32)
        for rg in RINGS:
            draw_ring(cv, rg, t, face)
        for ev in ICON_EV:
            draw_icon(cv, ev, t, face)
        for c in CAPS:
            c.draw(cv, t)
    for s in SCENES:
        transition(cv, s.tin, t - s.a)
        transition(cv, s.tout, t - s.b)
    return cv


# ---- video -----------------------------------------------------------------------------------------------
def vf():
    if VERT:
        return f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=bicubic,crop={W}:{H}"
    return f"fps={FPS},scale={VW}:{VH}:flags=bicubic"


def read_frames(a, b):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a}", "-t", f"{b - a}", "-i", SRC, "-vf", vf(),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = VW * VH * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(VH, VW, 3)
    p.wait()


def frames():
    for a, b in PIECES:
        yield from read_frames(a, b)


class Base:
    """talking-head base frame: vertical = as is; landscape = face-follow crop over a blurred copy."""

    def __init__(self):
        self.fd = cv2.FaceDetectorYN.create(YUNET, "", (VW // 4, VH // 4), 0.6, 0.3, 20)
        self.cx = None
        self.face = None

    def __call__(self, fr, smooth=True):
        small = cv2.resize(fr, (VW // 4, VH // 4), interpolation=cv2.INTER_AREA)
        _, f = self.fd.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
        box = None
        if f is not None and len(f):
            r = max(f, key=lambda r: r[2] * r[3])
            box = [float(v) * 4 for v in r[:4]]
        if VERT:
            if box:
                self.face = box if self.face is None or not smooth else [p + (q - p) * 0.25 for p, q in zip(self.face, box)]
            return fr.astype(np.float32), self.face
        if box:
            fx = box[0] + box[2] / 2
            self.cx = fx if (self.cx is None or not smooth) else self.cx + (fx - self.cx) * 0.08
        if self.cx is None:
            self.cx = VW / 2
        x0 = int(np.clip(self.cx - W / 2, 0, VW - W))
        vid = fr[:, x0:x0 + W]
        sc = H / VH
        big = cv2.resize(fr, (int(VW * sc / 2), int(VH * sc / 2)), interpolation=cv2.INTER_AREA)
        bx = int(np.clip(self.cx * sc / 2 - W / 4, 0, big.shape[1] - W // 2))
        bg = cv2.GaussianBlur(big[:, bx:bx + W // 2], (0, 0), 18)
        canvas = cv2.resize(bg, (W, H)).astype(np.float32) * 0.55
        y0, y1 = max(0, VY), min(H, VY + VH)
        canvas[y0:y1] = vid[y0 - VY:y1 - VY]
        if box:
            fb = [box[0] - x0, box[1] + VY, box[2], box[3]]
            self.face = fb if (self.face is None or not smooth) else [p + (q - p) * 0.25 for p, q in zip(self.face, fb)]
        return canvas, self.face


def src_time(t):
    """timeline time -> (piece index, source time)."""
    rel = t - T0
    for a, b in PIECES:
        if rel < b - a:
            return a + rel
        rel -= b - a
    return None


def still(ts):
    base = Base()
    for t in ts:
        st = src_time(t)
        fr = next(read_frames(st, st + 0.2), None) if st is not None else None
        if fr is not None:
            bimg, face = base(fr, smooth=False)
        else:
            bimg, face = None, None
        for ev in ICON_EV:                     # let unpinned icons place themselves on this frame's face
            if not ev["_fixed"]:
                ev.pop("pos", None)
        cv = compose(t, bimg, face)
        out = os.path.splitext(OUT)[0] + f"_still_{t:.2f}.png"
        cv2.imwrite(out, cv2.cvtColor(np.clip(cv, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(out)


# ---- audio -----------------------------------------------------------------------------------------------
POP = "aevalsrc='0.55*sin(2*PI*(380+1100*exp(-t*28))*t)*exp(-t*22)':d=0.18:s=48000"
WHOOSH = ("anoisesrc=c=pink:a=0.5:d=0.45:r=48000,highpass=f=250,lowpass=f=6000,"
          "afade=t=in:d=0.25,afade=t=out:st=0.25:d=0.2")
TICK = "aevalsrc='0.3*sin(2*PI*2200*t)*exp(-t*60)':d=0.06:s=48000"


def mix_audio(tmp, total):
    vdur = NV / FPS
    if AUDIO:
        ain = ["-ss", str(T0), "-t", f"{vdur:.3f}", "-i", AUDIO]
        n_a = 1
    else:
        ain = []
        for a, b in PIECES:
            ain += ["-ss", str(a), "-t", f"{b - a:.3f}", "-i", SRC]
        n_a = len(PIECES)
    pre = "" if AUDIO else "".join(f"[{k + 1}:a]" for k in range(n_a)) + f"concat=n={n_a}:v=0:a=1[voice];"
    voice = "[1:a]" if AUDIO else "[voice]"
    ev = []                                                    # (lavfi src or file, time, vol)
    if P.get("auto_sfx", True):
        for s in SCENES:
            ev.append((WHOOSH, s.a - 0.22, 0.32))
            if s.type != "end" and s.tout != "none":
                ev.append((WHOOSH, s.b - 0.22, 0.25))
        for e in ICON_EV:
            ev.append((POP, float(e["t"]) + 0.05, 0.55))
        for c in CAPS:
            if c.big:
                ev.append((TICK, c.big[0][1], 0.35))
    for f, tt, vol in P.get("sfx", []):
        ev.append((os.path.join(SFXDIR, f), float(tt), float(vol)))
    inputs, chains = [], []
    for k, (src, tt, vol) in enumerate(ev):
        d = int(max(0, tt - T0) * 1000)
        if os.path.isfile(src):
            inputs += ["-i", src]
        else:
            inputs += ["-f", "lavfi", "-i", src]
        chains.append(f"[{1 + n_a + k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={d}|{d},volume={vol}[e{k}];")
    fc = (pre + f"{voice}aresample=48000,aformat=channel_layouts=stereo,apad[v0];" + "".join(chains) + "[v0]" +
          "".join(f"[e{k}]" for k in range(len(ev))) +
          f"amix=inputs={1 + len(ev)}:normalize=0:duration=first,atrim=0:{total:.3f}[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp] + ain + inputs +
                   ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-t", f"{total:.3f}", OUT], check=True)


def main():
    if A.still:
        still(A.still)
        return
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    tmp = OUT + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    base = Base()
    gen = frames()
    last = None
    for i in range(NV + NE):
        t = T0 + i / FPS
        fr = next(gen, None) if i < NV else None
        if fr is not None:
            last = base(fr)
        bimg, face = last if last else (None, None)
        cv = compose(t, bimg, face)
        enc.stdin.write(np.clip(cv, 0, 255).astype(np.uint8).tobytes())
        if i % 90 == 0:
            print(f"{t:.1f}s", flush=True)
    enc.stdin.close(); enc.wait()
    mix_audio(tmp, (NV + NE) / FPS)
    os.remove(tmp)
    print("done", OUT)


if __name__ == "__main__":
    main()
