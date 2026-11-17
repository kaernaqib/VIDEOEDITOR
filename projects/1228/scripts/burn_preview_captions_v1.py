"""Burn captions.json onto a preview MP4 (preview.py doesn't draw CapCut text), approximating the house style.

usage: python3 burn_preview_captions.py PREVIEW.mp4 captions.json OUT.mp4 [--font "Poppins"] [--fontsdir DIR]
Style A: white bold sans, keyword yellow on its own line (bigger), mid-frame. Headers top-left.
Style B: small serif subtitle in the lower third; headers as big yellow titles.
"""
import json, subprocess, sys

src, cj, out = sys.argv[1:4]
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
C = json.load(open(cj, encoding="utf-8"))
A = C.get("style", "A") == "A"
font = arg("--font", "Poppins" if A else "Playfair Display")
fontsdir = arg("--fontsdir", None)
w, h = (int(x) for x in subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src],
    capture_output=True, text=True).stdout.strip().split(","))
k = h / 1920
YEL = "&H001FD2FF&"            # ASS is BGR: #FFD21F
t = lambda s: f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
esc = lambda s: s.replace("{", "(").replace("}", ")")

head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow
Style: Cap,{font},{int((62 if A else 40) * k)},&H00FFFFFF,&H00000000,&H80000000,1,0,{5 if A else 2},40,40,{int((0 if A else 420) * k)},1,{0 if A else 0},{int(3 * k)}
Style: Head,{font},{int((70 if A else 150) * k)},&H00FFFFFF,&H00000000,&H80000000,1,{1 if A else 0},{7 if A else 8},{int(60 * k)},40,{int(160 * k)},1,0,{int(3 * k)}

[Events]
Format: Layer, Start, End, Style, Text
"""
ev = []
for c in C["captions"]:
    txt = esc(c["text"])
    if c["keyword"]:
        size = int((62 if A else 40) * k * (2.0 if c["big"] else 1.5))
        kw = "{\\c" + YEL + "\\fs" + str(size) + "}" + esc(c["keyword"])
        txt = f"{txt}\\N{kw}" if txt else kw
    ev.append(f"Dialogue: 0,{t(c['a'])},{t(c['b'])},Cap,{txt}")
for hd in C.get("headers", []) + C.get("labels", []):
    if "num" in hd:
        txt = "{\\c" + YEL + "\\fs" + str(int(110 * k)) + "}" + hd["num"] + "{\\r} " + esc(hd["title"])
    else:
        col = {"bad": "&H00303BFF&", "good": "&H0059C734&"}.get(hd.get("kind"), YEL)
        txt = "{\\c" + col + "}" + esc(hd["text"])
    ev.append(f"Dialogue: 1,{t(hd['a'])},{t(hd['b'])},Head,{txt}")

ass = out + ".ass"
open(ass, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
vf = f"subtitles={ass}" + (f":fontsdir={fontsdir}" if fontsdir else "")
r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "23", "-c:a", "copy", out], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr[-1500:])
print("preview with captions ->", out)
