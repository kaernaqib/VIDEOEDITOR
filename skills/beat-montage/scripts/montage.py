"""beat montage: shots cut on the beat, with zoom / punch-in / white flash / speed-up, minimal text, music bed.
usage: PY montage.py plan.json
plan: {"out", "music", "footage", "index", "shots": [{"c": clip_no, "s": start, "d": dur_on_timeline,
        "fx": ["zin"|"zout"|"punch"|"flash"|"fast"], "vol": 0..1}], "texts": [{"t0","t1","big","small"}]}
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np

P = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = P["out"]
FOOT = P.get("footage", "D:/CLAUDE/kerja/berekeh/footage")
IDX = json.load(open(P.get("index", "D:/CLAUDE/kerja/berekeh/sheets/index.json")))
FONTS = "D:/CLAUDE/kerja/_fonts"
W, H, FPS = 1080, 1920, 30
work = os.path.splitext(OUT)[0] + "_work"
os.makedirs(work, exist_ok=True)


def orient(src):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                        "-of", "json", src], capture_output=True, text=True).stdout
    s = json.loads(o)["streams"][0]
    w, h = s["width"], s["height"]
    for sd in s.get("side_data_list", []) or []:
        if abs(int(sd.get("rotation", 0) or 0)) == 90:
            w, h = h, w
    return w, h


parts, t = [], 0.0
for k, sh in enumerate(P["shots"]):
    src = os.path.join(FOOT, IDX[sh["c"] - 1])
    fx = sh.get("fx", [])
    speed = 1.6 if "fast" in fx else 1.0
    d = sh["d"]
    nf = int(round((t + d) * FPS)) - int(round(t * FPS))     # exact frames so cuts land on the beat
    w, h = orient(src)
    if h >= w:
        base = "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840"
    else:
        base = ("split[a][b];[a]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,boxblur=40:4,eq=brightness=-0.12[bg];"
                "[b]scale=2160:-2[fg];[bg][fg]overlay=0:(H-h)/2")
    z = "1.0"
    if "zin" in fx:
        z = f"1+0.10*on/{nf}"
    elif "zout" in fx:
        z = f"1.10-0.10*on/{nf}"
    elif "punch" in fx:
        z = f"if(lt(on,4),1.18-0.045*on,1.0)"
    vf = (f"setpts=PTS/{speed},fps={FPS},{base},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
          f"setsar=1,eq=contrast=1.06:saturation=1.12,tpad=stop_mode=clone:stop_duration=3")
    if "flash" in fx:
        vf += ",fade=t=in:st=0:d=0.16:color=white"
    vol = sh.get("vol", 0.0)
    p = f"{work}/p{k:03d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sh["s"]), "-t", f"{d * speed + 0.3:.3f}", "-i", src,
                    "-f", "lavfi", "-t", f"{d + 0.3:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", f"[0:v]{vf}[v];[0:a]atempo={speed},volume={vol},aresample=48000,aformat=channel_layouts=stereo[a0];[a0][1:a]amix=inputs=2:duration=longest:normalize=0[a]",
                    "-map", "[v]", "-map", "[a]", "-frames:v", str(nf), "-t", f"{nf / FPS:.4f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", p], check=True)
    parts.append(p)
    t += d
    print(f"{k} #{sh['c']} {d}s {fx}", flush=True)

lst = f"{work}/list.txt"
open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
cut = f"{work}/cut.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-af", "aresample=async=1", cut], check=True)

# text cards (PNG overlays)
def font(name, size, wght):
    f = ImageFont.truetype(f"{FONTS}/{name}", size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def card(big, small, path):
    im = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fb, fs = font("Montserrat-VF.ttf", 104, 800), font("Montserrat-VF.ttf", 46, 600)
    y = 60
    lines = []
    if small:
        lines.append((small, fs, (255, 255, 255)))
    if big:
        for ln in big.split("\n"):
            size = 104
            while font("Montserrat-VF.ttf", size, 800).getlength(ln) > 960 and size > 50:
                size -= 4
            lines.append((ln, font("Montserrat-VF.ttf", size, 800), (255, 214, 0)))
    for txt, f, col in lines:
        wdt = f.getlength(txt)
        asc, desc = f.getmetrics()
        x = (W - wdt) / 2
        for dx, dy in ((0, 5), (2, 6), (-2, 6)):
            d.text((x + dx, y + dy), txt, font=f, fill=(0, 0, 0, 150))
        d.text((x, y), txt, font=f, fill=col + (255,))
        y += asc + desc + 6
    a = np.array(im)
    sh = a.copy(); sh[..., :3] = 0
    from PIL import ImageFilter
    glow = Image.fromarray(a).filter(ImageFilter.GaussianBlur(10))
    out = Image.alpha_composite(Image.fromarray(np.zeros_like(a)), glow.point(lambda v: v * 0) if False else Image.fromarray(np.zeros_like(a)))
    out = Image.alpha_composite(out, Image.fromarray(a))
    out.save(path)


inputs, fc, last = ["-i", cut], "", "[0:v]"
for i, tx in enumerate(P.get("texts", [])):
    pth = f"{work}/text{i}.png"
    card(tx.get("big", ""), tx.get("small", ""), pth)
    inputs += ["-loop", "1", "-t", "60", "-i", pth]
    y = tx.get("y", 300)
    t0, t1 = tx["t0"], tx["t1"]
    fc += (f"[{i + 1}:v]format=rgba,fade=t=in:st={t0}:d=0.15:alpha=1,fade=t=out:st={t1 - 0.15}:d=0.15:alpha=1[t{i}];"
           f"{last}[t{i}]overlay=0:{y}:enable='between(t,{t0},{t1})'[v{i}];")
    last = f"[v{i}]"
n_in = 1 + len(P.get("texts", []))
inputs += ["-i", P["music"]]
fc += f"[0:a]volume=1.0[orig];[{n_in}:a]volume={P.get('music_vol', 0.9)}[mus];[orig][mus]amix=inputs=2:duration=shortest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", fc, "-map", last, "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{t:.3f}", "-movflags", "+faststart", OUT], check=True)
print("done", OUT, round(t, 2), "s")
