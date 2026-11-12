"""Reel thumbnail / cover (1080x1920) from a video frame plus hook text, in style A or B.

usage: python3 thumbnail.py FRAME.jpg "HOOK TEXT" --out thumb.jpg [--style A|B] [--font BOLD.ttf]
       [--serif ITALIC_SERIF.ttf] [--small "lead-in words"]
  A: bold white sans, last word yellow and larger, centred at ~62% height, soft dark gradient behind.
  B: small italic serif lead-in ("Do you wanna make") above a huge condensed yellow word ("BETTER"), top third.
Text stays inside the 9:16 safe zone (clear of the top 12% and the bottom 20% where IG/TikTok UI sits).
"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

frame, hook = sys.argv[1], sys.argv[2]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
out, style = arg("--out", "thumbnail.jpg"), arg("--style", "A")
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
font_p, serif_p, small = arg("--font", FALLBACK), arg("--serif", arg("--font", FALLBACK)), arg("--small", "")
W, H = 1080, 1920
YEL, WHITE = (255, 210, 31), (255, 255, 255)

img = Image.open(frame).convert("RGB")
s = max(W / img.width, H / img.height)
img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
x0, y0 = (img.width - W) // 2, (img.height - H) // 2
img = img.crop((x0, y0, x0 + W, y0 + H))

# gradient for legibility
grad = Image.new("L", (W, H), 0)
gd = ImageDraw.Draw(grad)
for y in range(H):
    if style == "A":
        v = max(0, (y - H * 0.40) / (H * 0.45))
    else:
        v = max(0, 1 - y / (H * 0.45))
    gd.line([(0, y), (W, y)], fill=int(170 * min(1, v)))
img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, grad)
d = ImageDraw.Draw(img)


def fit(text, path, target_w, max_size):
    size = max_size
    while size > 20:
        f = ImageFont.truetype(path, size)
        if d.textlength(text, font=f) <= target_w:
            return f
        size -= 4
    return ImageFont.truetype(path, size)


def shadowed(xy, text, font, fill, anchor="mm"):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 6), text, font=font, fill=(0, 0, 0, 200), anchor=anchor)
    img.paste(sh.filter(ImageFilter.GaussianBlur(10)), (0, 0), sh.filter(ImageFilter.GaussianBlur(10)))
    d.text(xy, text, font=font, fill=fill, anchor=anchor)


if style == "A":
    words = hook.split()
    lead, last = " ".join(words[:-1]), words[-1].upper()
    y = H * 0.62
    if lead:
        f1 = fit(lead, font_p, W * 0.86, 96)
        shadowed((W / 2, y), lead, f1, WHITE)
        y += f1.size * 1.05
    f2 = fit(last, font_p, W * 0.9, 200)
    shadowed((W / 2, y + f2.size * 0.45), last, f2, YEL)
else:
    big = hook.upper()
    y = H * 0.20
    if small:
        fs = fit(small, serif_p, W * 0.8, 84)
        shadowed((W / 2, y), small, fs, YEL)
        y += fs.size * 0.9
    fb = fit(big, font_p, W * 0.92, 320)
    shadowed((W / 2, y + fb.size * 0.5), big, fb, YEL)

img.save(out, quality=92)
print("thumbnail ->", out)
