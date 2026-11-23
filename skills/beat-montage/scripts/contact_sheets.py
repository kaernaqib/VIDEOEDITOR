"""usage: PY contact_sheets.py FOOTAGE_DIR [OUT_DIR]
contact sheets: 3 frames per clip (10%, 50%, 90%), labelled with clip index, 6 clips per row."""
import json, os, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont
import sys
D = sys.argv[1] if len(sys.argv) > 1 else "footage"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(D)), "sheets")
os.makedirs(OUT, exist_ok=True)
files = sorted(f for f in os.listdir(D) if f.lower().endswith((".mov", ".mp4")) and os.path.getsize(os.path.join(D, f)) > 0)
F = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
TW, TH = 120, 213   # per-frame thumb (portrait); landscape gets letterboxed


def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout
    try:
        return float(o.strip())
    except ValueError:
        return 0


def frame(p, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", p, "-frames:v", "1", "-vf",
                        f"scale={TW}:{TH}:force_original_aspect_ratio=decrease,pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(r) < TW * TH * 3:
        return Image.new("RGB", (TW, TH), (40, 0, 0))
    return Image.fromarray(np.frombuffer(r[:TW * TH * 3], np.uint8).reshape(TH, TW, 3))


cells = []
for i, f in enumerate(files):
    p = os.path.join(D, f)
    d = dur(p)
    cell = Image.new("RGB", (TW * 3, TH + 30), (15, 15, 15))
    for k, fr in enumerate((0.1, 0.5, 0.9)):
        cell.paste(frame(p, max(0, d * fr)), (k * TW, 30))
    ImageDraw.Draw(cell).text((6, 3), f"#{i + 1}  {d:.0f}s  {f[11:16].replace('_', ':')}", font=F, fill=(255, 220, 0))
    cells.append(cell)
per, cols = 24, 6
for s in range(0, len(cells), per):
    chunk = cells[s:s + per]
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (TW * 3 + 8), rows * (TH + 38)), (0, 0, 0))
    for j, c in enumerate(chunk):
        sheet.paste(c, ((j % cols) * (TW * 3 + 8), (j // cols) * (TH + 38)))
    sheet.save(f"{OUT}/sheet_{s // per + 1:02d}.jpg", quality=80)
    print("sheet", s // per + 1, flush=True)
json.dump(files, open(f"{OUT}/index.json", "w"), indent=0)
