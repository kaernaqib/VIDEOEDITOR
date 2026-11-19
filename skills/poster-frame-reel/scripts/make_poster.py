"""General series poster (1080 x ~610) in a bright YouTube-thumbnail look: 1-3 photos side by side with soft seams,
punchy colour, and an optional yellow title with a thick black outline. Made ONCE and reused on every reel of a series
(job "poster": {"image": "poster.jpg"}).

usage: python make_poster.py POSTER.json
  {"out": "poster.jpg",
   "tiles": [{"image": "a.jpg", "focus": [0.5, 0.35], "zoom": 1.6}, ...],   # focus = face position in the photo
   "title": ["MELBOURNE", "VLOG"],          # optional: line 1 yellow gradient, more lines white
   "title_y": 70, "title_size": 96, "vivid": 1.35}
"""
import json, sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_poster_reel import W, DEF, tile_img

J = json.load(open(sys.argv[1], encoding="utf-8"))
PH = DEF["fade"][1] + 140
tiles, feather = J["tiles"], 110
n = len(tiles)
tw = W // n
img = Image.new("RGB", (W, PH))
for k, t in enumerate(tiles):
    x = max(0, k * tw - (feather // 2 if n > 1 else 0))
    w_k = min(W - x, tw + (feather if n > 1 else 0))
    im = tile_img(dict({"contrast": 1.0, "saturation": 1.0}, **t), k, ".", w_k, PH)
    m = Image.new("L", (w_k, PH), 255)
    if k > 0:
        md = ImageDraw.Draw(m)
        for i in range(feather):
            md.line([(i, 0), (i, PH)], fill=int(255 * i / feather))
    img.paste(im, (x, 0), m)

# thumbnail grade: saturation, contrast, a touch of clarity (unsharp) and warmth
v = J.get("vivid", 1.35)
img = ImageEnhance.Color(img).enhance(v)
img = ImageEnhance.Contrast(img).enhance(1.12)
img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=2))
r, g, b = img.split()
img = Image.merge("RGB", (r.point(lambda p: min(255, int(p * 1.04))), g, b.point(lambda p: int(p * 0.97))))

title = J.get("title") or []
d = ImageDraw.Draw(img)
y = J.get("title_y", 70)
for i, line in enumerate(title):
    size = J.get("title_size", 96) if i == 0 else int(J.get("title_size", 96) * 0.62)
    f = ImageFont.truetype(J.get("title_font", DEF["head_font"]), size)
    while d.textlength(line, font=f) > W - 80 and size > 30:
        size -= 4; f = ImageFont.truetype(J.get("title_font", DEF["head_font"]), size)
    x0 = J.get("title_x", 40)
    stroke = max(4, size // 14)
    sh = Image.new("L", img.size, 0)                                  # soft drop shadow
    ImageDraw.Draw(sh).text((x0 + 6, y + 8), line, font=f, fill=220, stroke_width=stroke, stroke_fill=220)
    img.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(6)))
    if i == 0:                                                        # yellow -> orange gradient fill
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).text((x0, y), line, font=f, fill=255)
        bb = mask.getbbox() or (0, y, W, y + size)
        grad = Image.new("RGB", img.size)
        gd = ImageDraw.Draw(grad)
        for yy in range(bb[1], bb[3] + 1):
            k = (yy - bb[1]) / max(1, bb[3] - bb[1])
            gd.line([(0, yy), (W, yy)], fill=(255, int(232 - 70 * k), int(80 - 70 * k)))
        d.text((x0, y), line, font=f, fill=(0, 0, 0), stroke_width=stroke, stroke_fill=(0, 0, 0))
        img.paste(grad, (0, 0), mask)
    else:
        d.text((x0, y), line, font=f, fill=(255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0))
    y += int(size * 1.02)
img.save(J["out"], quality=95)
print("poster ->", J["out"])
