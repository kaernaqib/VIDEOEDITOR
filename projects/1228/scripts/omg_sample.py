"""Sample render in the "omgadrian" cinematic text style (blur-in word by word, Anton + Playfair Italic,
yellow highlight box wipe, title behind the head, EB Garamond subtitles, whip blur, light leak).

usage: PY omg_sample.py OUT.mp4
PY = ~/.claude/skills/video-effect/.venv/Scripts/python.exe (numpy, opencv, pillow, mediapipe)
"""
import os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
SRC = "D:/melbourne/melbourne 1/DJI_20251201091303_0049_D.MP4"
AUDIO = "D:/CLAUDE/kerja/1228/work/long/r01/audio.wav"
T0 = 14.0                                   # start on the reel-01 timeline
PIECES = [(18.3, 23.9667), (43.967, 55.3)]  # source ranges (reel-01 timeline 14.0 -> 31.0)
FONTS = "D:/CLAUDE/kerja/_fonts"
SEGM = os.path.expanduser("~/.claude/skills/video-effect/models/selfie_segmenter.tflite")
YUNET = os.path.expanduser("~/.claude/skills/video-effect/models/yunet.onnx")
W, H, FPS = 1080, 1920, 30
VW, VH = 2160, 1215                         # video scaled to ~2x canvas width (face not too big)
VY = 440                                    # top of video window on canvas
YEL, BLK, SUBC = (255, 210, 31), (12, 12, 12), (243, 227, 160)

# ---- text plan (times on reel-01 timeline) -------------------------------------------------------------
BLOCKS = [
    {"in": [("it", "on", 15.0), ("it", "the", 15.15), ("it", "way", 15.3)], "big": [("SHRINE", 17.3)], "out": 19.45},
    {"in": [("it", "kita", 20.27), ("it", "dah", 20.47)], "big": [("JUMPA!", 20.63)], "out": 21.75},
    {"in": [("it", "nama", 22.0), ("it", "dia", 22.32)], "big": [("SHRINE", 22.76), ("OF", 23.44)],
     "box": ("REMEMBRANCE", 23.76), "out": 26.9, "leak": 22.7},
    {"in": [("it", "so", 28.97), ("it", "inilah", 29.15)], "big": [("TEMPATNYA", 29.6)], "out": 30.85},
]
SUBS = [(14.87, 16.35, "remembrance of.."), (17.30, 19.29, "shrine ke shrine of.."),
        (19.95, 21.19, "okey kita dah jumpa dah"), (22.0, 24.68, "nama dia Shrine of Remembrance"),
        (27.1, 27.94, "ke bukan.."), (28.97, 30.6, "so inilah tempat dia..")]
WHIP = 19.667                               # the cut between the two source pieces


def font(name, size, wght=None):
    f = ImageFont.truetype(f"{FONTS}/{name}", size)
    if wght:
        f.set_variation_by_axes([wght])
    return f


F_BIG = lambda s: font("Anton-Regular.ttf", s)
F_IT = font("PlayfairDisplay-Italic-VF.ttf", 64, 600)
F_SUB = font("EBGaramond-VF.ttf", 50, 500)


def sprite(text, f, fill, pad=40, box=None):
    l, t, r, b = f.getbbox(text)
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if box:
        d.rectangle([pad - 14, pad - 10, pad + r - l + 14, pad + b - t + 10], fill=box + (255,))
    d.text((pad - l, pad - t), text, font=f, fill=fill + (255,))
    return np.array(im).astype(np.float32) / 255, pad


def layout(bl):
    """place every word of a block: italic line on top, big words below (one line), optional box line."""
    items = []
    its = [sprite(w, F_IT, YEL) + (t,) for _, w, t in bl["in"]]
    gap = 22
    tw = sum(s.shape[1] - 2 * p for s, p, _ in its) + gap * (len(its) - 1)
    x, y = (W - tw) / 2, 120
    for s, p, t in its:
        items.append((s, x - p, y - p, t))
        x += s.shape[1] - 2 * p + gap
    words = [w for w, _ in bl["big"]]
    size = 230
    while size > 90:
        f = F_BIG(size)
        tw = sum(f.getbbox(w)[2] - f.getbbox(w)[0] for w in words) + 30 * (len(words) - 1)
        if tw <= 960:
            break
        size -= 10
    f = F_BIG(size)
    x, y = (W - tw) / 2, 205
    for w, t in bl["big"]:
        s, p = sprite(w, f, YEL)
        items.append((s, x - p, y - p, t))
        x += s.shape[1] - 2 * p + 30
    bh = f.getbbox("H")[3] - f.getbbox("H")[1]
    box = None
    if "box" in bl:
        w, t = bl["box"]
        bf = F_BIG(int(size * 0.62))
        s, p = sprite(w, bf, BLK, box=YEL)
        bw = s.shape[1] - 2 * p
        box = (s, (W - bw) / 2 - p, y + bh + 40 - p, t)
    return items, box


LAYOUTS = [layout(b) for b in BLOCKS]
SUB_SPR = [(a, b, sprite(t, F_SUB, SUBC)) for a, b, t in SUBS]


def paste(dst, spr, x, y, alpha=1.0):
    s = spr
    x, y = int(round(x)), int(round(y))
    h, w = s.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = s[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sub[..., 3:4] * alpha
    dst[y0:y1, x0:x1, :3] = dst[y0:y1, x0:x1, :3] * (1 - a) + sub[..., :3] * a
    dst[y0:y1, x0:x1, 3:4] = 1 - (1 - dst[y0:y1, x0:x1, 3:4]) * (1 - a)


def blurred(spr, r):
    if r < 0.6:
        return spr
    k = int(r * 3) | 1
    s = spr.copy()
    s[..., :3] *= s[..., 3:4]                                # premultiply so edges don't go dark
    s = cv2.GaussianBlur(s, (k, k), r)
    a = np.maximum(s[..., 3:4], 1e-4)
    s[..., :3] /= a
    return s


def text_layer(t):
    lay = np.zeros((H, W, 4), np.float32)
    for bl, (items, box) in zip(BLOCKS, LAYOUTS):
        first = min(tt for *_, tt in items)
        if t < first - 0.01 or t > bl["out"] + 0.25:
            continue
        ex = np.clip((t - bl["out"]) / 0.22, 0, 1)            # exit: everything blurs away together
        for s, x, y, tt in items:
            k = np.clip((t - tt) / 0.26, 0, 1)
            if k <= 0:
                continue
            e = 1 - (1 - k) ** 3
            r = (1 - e) * 16 + ex * 20
            sc = 1.07 - 0.07 * e
            sp = blurred(s, r)
            if abs(sc - 1) > 1e-3:
                h, w = sp.shape[:2]
                sp = cv2.resize(sp, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_LINEAR)
                x, y = x - (sp.shape[1] - w) / 2, y - (sp.shape[0] - h) / 2
            paste(lay, sp, x, y, e * (1 - ex))
        if box:
            s, x, y, tt = box
            k = np.clip((t - tt) / 0.3, 0, 1)
            if k > 0:
                e = 1 - (1 - k) ** 3
                c = s.copy()
                c[:, int(c.shape[1] * e):, 3] = 0                 # wipe left -> right
                paste(lay, blurred(c, ex * 20), x, y, 1 - ex)
    return lay


def sub_layer(t):
    lay = np.zeros((H, W, 4), np.float32)
    for i, (a, b, (s, p)) in enumerate(SUB_SPR):
        nxt = SUB_SPR[i + 1][0] if i + 1 < len(SUB_SPR) else 99
        end = min(b + 0.5, nxt)
        if a <= t < end:
            al = min(1, (t - a) / 0.12) * min(1, (end - t) / 0.12)
            sh = blurred(s.copy() * [0, 0, 0, 1], 5)
            x, y = (W - s.shape[1]) / 2, 1500 - s.shape[0] / 2
            paste(lay, sh, x, y + 3, al * 0.85)
            paste(lay, s, x, y, al)
    return lay


def frames():
    """decode both source pieces scaled to VW x VH at 30 fps."""
    for a, b in PIECES:
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a}", "-t", f"{b - a}", "-i", SRC,
                              "-vf", f"fps={FPS},scale={VW}:{VH}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             stdout=subprocess.PIPE)
        n = VW * VH * 3
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(VH, VW, 3)
        p.wait()


def main():
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=SEGM), running_mode=vision.RunningMode.VIDEO,
        output_confidence_masks=True, output_category_mask=False))
    fd = cv2.FaceDetectorYN.create(YUNET, "", (VW // 4, VH // 4), 0.6, 0.3, 20)

    tmp = OUT + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    cx, prev_m = None, None
    for i, fr in enumerate(frames()):
        t = T0 + i / FPS
        small = cv2.resize(fr, (VW // 4, VH // 4), interpolation=cv2.INTER_AREA)
        _, f = fd.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
        if f is not None and len(f):
            r = max(f, key=lambda r: r[2] * r[3])
            fx = (r[0] + r[2] / 2) * 4
            cx = fx if cx is None else cx + (fx - cx) * 0.08     # smooth follow
        if cx is None:
            cx = VW / 2
        x0 = int(np.clip(cx - W / 2, 0, VW - W))
        vid = fr[:, x0:x0 + W]
        # background: same shot, covering the canvas, heavy blur, darker
        sc = H / VH
        big = cv2.resize(fr, (int(VW * sc / 2), int(VH * sc / 2)), interpolation=cv2.INTER_AREA)
        bx = int(np.clip(cx * sc / 2 - W / 4, 0, big.shape[1] - W // 2))
        bg = cv2.GaussianBlur(big[:, bx:bx + W // 2], (0, 0), 18)
        bg = cv2.resize(bg, (W, H)).astype(np.float32) * 0.55
        canvas = bg.copy()
        canvas[VY:VY + VH] = vid
        # whip blur around the cut
        dtw = t - WHIP
        if abs(dtw) < 0.14:
            k = 1 - abs(dtw) / 0.14
            ks = int(10 + 170 * k) | 1
            ker = np.zeros((1, ks), np.float32); ker[0] = 1 / ks
            shift = int(-260 * k) if dtw < 0 else int(260 * k)    # leaves to the left, new shot arrives from the right
            canvas = np.roll(canvas, shift, axis=1)
            canvas = cv2.filter2D(canvas, -1, ker)
        # person mask (for text behind head), on the canvas video window
        m_small = cv2.resize(vid, (W // 3, VH // 3), interpolation=cv2.INTER_AREA)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(m_small))
        m = seg.segment_for_video(img, int(i * 1000 / FPS)).confidence_masks[-1].numpy_view().astype(np.float32)
        m = m.reshape(m.shape[0], m.shape[1])
        m = np.clip((m - 0.5) * 2.2 + 0.5, 0, 1)
        if prev_m is not None and abs(dtw) > 0.2:
            m = 0.6 * m + 0.4 * prev_m
        prev_m = m
        m = cv2.GaussianBlur(cv2.resize(m, (W, VH)), (0, 0), 2)
        mask = np.zeros((H, W, 1), np.float32)
        mask[VY:VY + VH, :, 0] = m
        if abs(dtw) < 0.14:
            mask[:] = 0
        tl = text_layer(t)
        ta = tl[..., 3:4]
        hidden = float((ta * mask).sum() / max(ta.sum(), 1))
        occ = mask if hidden < 0.33 else 0                    # behind the head only while the title stays readable
        a = ta * (1 - occ)
        canvas = canvas * (1 - a) + tl[..., :3] * 255 * a
        # light leak
        for bl in BLOCKS:
            if "leak" in bl and 0 <= t - bl["leak"] < 0.5:
                k = np.sin(np.pi * (t - bl["leak"]) / 0.5)
                yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
                g = np.exp(-(((xx - W * 1.05) / 520) ** 2 + ((yy - H * 0.3) / 700) ** 2))[..., None]
                canvas = canvas + g * k * np.array([255, 70, 20], np.float32) * 0.85
        sl = sub_layer(t)
        canvas = canvas * (1 - sl[..., 3:4]) + sl[..., :3] * 255 * sl[..., 3:4]
        enc.stdin.write(np.clip(canvas, 0, 255).astype(np.uint8).tobytes())
        if i % 60 == 0:
            print(f"{t:.1f}s", flush=True)
    enc.stdin.close(); enc.wait()
    dur = sum(b - a for a, b in PIECES)
    # audio: reel-01 mix + a whoosh on the whip
    wt = WHIP - T0 - 0.15
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ss", str(T0), "-t", f"{dur:.3f}", "-i", AUDIO,
                    "-f", "lavfi", "-t", "0.35", "-i", "anoisesrc=c=pink:a=0.5,highpass=f=300,lowpass=f=5000,"
                    "afade=t=in:d=0.2,afade=t=out:st=0.2:d=0.15",
                    "-filter_complex", f"[2:a]adelay={int(wt * 1000)}|{int(wt * 1000)},volume=0.35[w];"
                    "[1:a][w]amix=inputs=2:normalize=0:duration=first[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT],
                   check=True)
    os.remove(tmp)
    print("done", OUT)


if __name__ == "__main__":
    main()
