"""Weby-style reel renderer (ffmpeg + libass), no CapCut needed.

usage: python3 render.py JOB.json OUT.mp4 [--stills t1 t2 ...]

JOB.json:
  name, src (video), work (dir with a48.wav, words json), words (file name in work)
  fix          {"<word idx>": "Text"}      transcript corrections shown in captions
  drop         [[a, b, "why"], ...]         inclusive word ranges to cut (retakes, fillers)
  keywords     [idx, ...]                   yellow words
  title        ["Line one", "Line two?"]    title card shown at the start
  title_dur    seconds (default 2.6)
  face         {"x": 340, "top": 200}       face centre x / head top y in source pixels
  zooms        [1.15, 1.32]                 framing A/B alternated on jump cuts
"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30
W, H, PANEL_Y = 1080, 1920, 608
PH = H - PANEL_Y
ASSETS = "/home/user/reels/assets"
FONT_DIR = f"{ASSETS}/fonts"
YELLOW_ASS = "&H1CEAF7&"     # #F7EA1C in ASS BGR

job_path, out = sys.argv[1], sys.argv[2]
stills = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1:]] if "--stills" in sys.argv else None
J = json.load(open(job_path))
work = J["work"]
tmp = f"{work}/tmp"
os.makedirs(tmp, exist_ok=True)
Wd = json.load(open(f"{work}/{J.get('words', 'words.json')}"))
for k, v in J.get("fix", {}).items():
    Wd[int(k)]["w"] = v
dropped = set()
for a, b, *_ in J.get("drop", []):
    dropped.update(range(a, b + 1))
keep_words = [w for w in Wd if w["i"] not in dropped]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(" ".join(cmd[:30]) + "\n" + r.stderr[-2500:])
    return r


# ---------- 1. cut list (source seconds) ----------
LEAD, TAIL, MAXGAP = 0.08, 0.14, 0.30
clips = []
prev = None
for w in keep_words:
    contiguous = prev is not None and (w["i"] == prev["i"] + 1) and (w["s"] - prev["e"] <= MAXGAP)
    if contiguous:
        clips[-1]["e"] = w["e"] + TAIL
        clips[-1]["words"].append(w)
    else:
        clips.append({"s": max(0.0, w["s"] - LEAD), "e": w["e"] + TAIL, "words": [w]})
    prev = w
# split clips at silences inside them (large-v3 word times often swallow pauses)
db = np.load(f"{work}/db10ms.npy")
SIL_DB, SIL_MIN = -50.0, 0.32
split = []
for c in clips:
    a0, b0 = int(c["s"] * 100), int(c["e"] * 100)
    quiet = db[a0:b0] < SIL_DB
    cuts, k = [], 0
    while k < len(quiet):
        if quiet[k]:
            j = k
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - k) / 100 >= SIL_MIN and k > 0 and j < len(quiet):
                cuts.append(((a0 + k) / 100 + 0.10, (a0 + j) / 100 - 0.07))
            k = j
        else:
            k += 1
    s0 = c["s"]
    for x, y in cuts:
        split.append({"s": s0, "e": x, "words": [w for w in c["words"] if w["s"] < x]})
        s0 = y
    split.append({"s": s0, "e": c["e"], "words": [w for w in c["words"] if w["s"] >= s0 - 0.05]})
# cut explicit source-time ranges (retakes the transcript merged, fillers)
for r0, r1, *_ in J.get("remove_time", []):
    nxt = []
    for c in split:
        if c["e"] <= r0 or c["s"] >= r1:
            nxt.append(c); continue
        if c["s"] < r0:
            nxt.append({"s": c["s"], "e": r0, "words": [w for w in c["words"] if w["s"] < r0]})
        if c["e"] > r1:
            nxt.append({"s": r1, "e": c["e"], "words": [w for w in c["words"] if w["e"] > r1]})
    split = nxt
clips = [c for c in split if c["e"] - c["s"] > 0.12]
for a, b in zip(clips, clips[1:]):          # never overlap source audio
    if b["s"] < a["e"]:
        m = (a["e"] + b["s"]) / 2
        a["e"], b["s"] = m, m
# merge tiny clips into the next one's framing decision only (keep audio as is)
tl = 0
for c in clips:
    c["f0"] = int(round(c["s"] * FPS))
    c["n"] = max(1, int(round(c["e"] * FPS)) - c["f0"])
    c["tl0"] = tl
    tl += c["n"]
TOTAL_F = tl

# framing: alternate A/B on each jump cut, but hold framing if the previous clip was very short
ZA, ZB = J.get("zooms", [1.15, 1.32])
cur = ZA
for k, c in enumerate(clips):
    if k > 0 and clips[k - 1]["n"] >= 0.9 * FPS:
        cur = ZB if cur == ZA else ZA
    c["z"] = cur
clips[0]["push"] = 0.07      # slow push-in on the hook


def src_to_tl(t):
    for c in clips:
        if c["s"] - 1e-3 <= t <= c["e"] + 1e-3:
            return (c["tl0"] + (t - c["f0"] / FPS) * FPS) / FPS
    return None


# ---------- 2. audio ----------
wf = wave.open(f"{work}/a48.wav")
sr, ch = wf.getframerate(), wf.getnchannels()
A = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).reshape(-1, ch).astype(np.float32) / 32768
parts = []
fade = int(0.012 * sr)
ramp = np.linspace(0, 1, fade)[:, None]
for c in clips:
    a0 = int(round(c["f0"] / FPS * sr))
    n = int(round(c["n"] / FPS * sr))
    seg = A[a0:a0 + n].copy()
    if len(seg) < n:
        seg = np.vstack([seg, np.zeros((n - len(seg), ch), np.float32)])
    seg[:fade] *= ramp
    seg[-fade:] *= ramp[::-1]
    parts.append(seg)
voice = np.vstack(parts)
raw_wav = f"{tmp}/voice_raw.wav"
with wave.open(raw_wav, "wb") as o:
    o.setnchannels(ch); o.setsampwidth(2); o.setframerate(sr)
    o.writeframes((np.clip(voice, -1, 1) * 32767).astype(np.int16).tobytes())
# two-pass loudnorm to -14 LUFS
r = run(["ffmpeg", "-hide_banner", "-i", raw_wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
js = r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1]
L = json.loads(js)
voice_wav = f"{tmp}/voice.wav"
run(["ffmpeg", "-v", "error", "-y", "-i", raw_wav, "-af",
     f"highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={L['input_i']}:measured_TP={L['input_tp']}:"
     f"measured_LRA={L['input_lra']}:measured_thresh={L['input_thresh']}:offset={L['target_offset']}:linear=true",
     "-ar", "48000", voice_wav])

# ---------- 3. video clips ----------
fx, top = J["face"]["x"], J["face"]["top"]


def window(z):
    ww, wh = W / z, PH / z
    x0 = min(max(0, fx - 0.42 * ww), 1080 - ww)
    y0 = min(max(0, top - 0.085 * wh), 1920 - wh)
    return int(ww) // 2 * 2, int(wh) // 2 * 2, int(x0), int(y0)


def render_clip(k, c, frames=None):
    o = f"{tmp}/clip_{k:03d}.mp4"
    ww, wh, x0, y0 = window(c["z"])
    vf = f"crop={ww}:{wh}:{x0}:{y0},"
    if c.get("push"):
        n = c["n"]
        vf += (f"scale={W * 2}:{PH * 2},zoompan=z='1+{c['push']}*on/{max(1, n - 1)}':d=1:"
               f"x='iw/2-iw/zoom/2':y='ih*0.3-ih/zoom*0.3':s={W}x{PH}:fps={FPS}")
    else:
        vf += f"scale={W}:{PH}:flags=lanczos"
    vf += ",eq=contrast=1.04:saturation=1.06,format=yuv420p"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['f0'] / FPS:.4f}", "-i", J["src"], "-frames:v", str(c["n"]),
         "-vf", vf, "-r", str(FPS), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", o])
    return o


from concurrent.futures import ThreadPoolExecutor  # noqa: E402
with ThreadPoolExecutor(4) as ex:
    files = list(ex.map(lambda kc: render_clip(*kc), enumerate(clips)))
open(f"{tmp}/list.txt", "w").write("".join(f"file '{f}'\n" for f in files))
panel = f"{tmp}/panel.mp4"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-c", "copy", panel])

# ---------- 4. title card PNG ----------
TITLE_DUR = J.get("title_dur", 2.6)
font_t = ImageFont.truetype(f"{FONT_DIR}/Montserrat_700Bold.ttf", 62)
lines = J["title"]
pad_x, line_h, gap = 22, 92, 10
widths = [font_t.getbbox(l)[2] for l in lines]
bw = max(widths) + 2 * pad_x + 60
bh = len(lines) * (line_h + gap) + 40
img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# bracket
d.rectangle([0, 0, 14, bh], fill=(10, 10, 10, 255))
d.rectangle([0, 0, 46, 14], fill=(10, 10, 10, 255))
d.rectangle([0, bh - 14, 46, bh], fill=(10, 10, 10, 255))
y = 20
for l, lw in zip(lines, widths):
    d.rectangle([34, y, 34 + lw + 2 * pad_x, y + line_h], fill=(255, 255, 255, 255))
    d.text((34 + pad_x, y + line_h / 2), l, font=font_t, fill=(10, 10, 10, 255), anchor="lm")
    y += line_h + gap
title_png = f"{tmp}/title.png"
img.save(title_png)
TX, TY = 150, 1360

# ---------- 5. captions (ASS) ----------
words_tl = []
for w in keep_words:
    if not w["w"].strip():
        continue
    s, e = src_to_tl(w["s"] + 0.01), src_to_tl(max(w["s"] + 0.05, w["e"] - 0.01))
    if s is None or e is None:
        continue
    words_tl.append(dict(w, ts=s, te=e))
KW = set(J.get("keywords", []))
chunks, cur_c = [], []
for k, w in enumerate(words_tl):
    cur_c.append(w)
    nxt = words_tl[k + 1] if k + 1 < len(words_tl) else None
    text_len = sum(len(x["w"]) + 1 for x in cur_c)
    end_here = (nxt is None or len(cur_c) >= 3 or text_len + len(nxt["w"]) > 15
                or w["w"][-1] in ".,?!" or nxt["ts"] - w["te"] > 0.25)
    if end_here:
        chunks.append(cur_c)
        cur_c = []


def ass_t(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


ev = []
for k, c in enumerate(chunks):
    a = c[0]["ts"]
    b = chunks[k + 1][0]["ts"] if k + 1 < len(chunks) and chunks[k + 1][0]["ts"] - c[-1]["te"] < 0.6 else c[-1]["te"] + 0.25
    if b <= TITLE_DUR:
        continue
    a = max(a, TITLE_DUR)
    txt = []
    for w in c:
        t = w["w"].strip().strip(",.").upper()
        if t.endswith("?") or t.endswith("!"):
            pass
        txt.append(f"{{\\c{YELLOW_ASS}}}{t}{{\\c&HFFFFFF&}}" if w["i"] in KW else t)
    ev.append(f"Dialogue: 0,{ass_t(a)},{ass_t(b)},Cap,,0,0,0,,{{\\pos(540,1500)\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}}" + " ".join(txt))
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat ExtraBold,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,6,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n"
ass_path = f"{tmp}/captions.ass"
open(ass_path, "w").write(ass)

# ---------- 6. compose ----------
dur = TOTAL_F / FPS
slide = 0.35
fc = (f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.3f}[bg];"
      f"[bg][1:v]overlay=0:0[b1];"
      f"[b1][0:v]overlay=0:{PANEL_Y}:shortest=1[b2];"
      f"[2:v]format=rgba,fade=t=out:st={TITLE_DUR - 0.25:.2f}:d=0.25:alpha=1[tt];"
      f"[b2][tt]overlay=x='if(lt(t,{slide}),{TX}-(1-t/{slide})*(1-t/{slide})*900,{TX})':y={TY}:"
      f"enable='lte(t,{TITLE_DUR})'[b3];"
      f"[b3]subtitles={ass_path}:fontsdir={FONT_DIR},format=yuv420p[v]")
main = f"{tmp}/main.mp4"
if stills:
    run(["ffmpeg", "-v", "error", "-y", "-i", panel, "-i", f"{ASSETS}/banner.png", "-loop", "1", "-t", f"{dur:.3f}",
         "-i", title_png, "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", main])
    for t in stills:
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", main, "-frames:v", "1", "-vf", "scale=540:-2",
             f"{tmp}/still_{t:05.2f}.jpg"])
    print("stills in", tmp)
else:
    run(["ffmpeg", "-v", "error", "-y", "-i", panel, "-i", f"{ASSETS}/banner.png", "-loop", "1", "-t", f"{dur:.3f}",
         "-i", title_png, "-i", voice_wav, "-filter_complex", fc, "-map", "[v]", "-map", "3:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", main])
    run(["ffmpeg", "-v", "error", "-y", "-i", main, "-i", f"{ASSETS}/endcard.mp4", "-filter_complex",
         "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    r = run(["ffmpeg", "-nostats", "-i", out, "-af", "ebur128", "-f", "null", "-"])
    lufs = [l for l in r.stderr.splitlines() if l.strip().startswith("I:")][-1].strip()
    print(f"render -> {out}  {os.path.getsize(out) / 1e6:.1f} MB")
    print(f"loudness {lufs}")

src_dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", J["src"]]).stdout)
print(f"{J['name']}: {src_dur:.1f}s -> {dur:.1f}s (+3.7s end card), {len(clips)} clips, {len(chunks)} caption chunks")
json.dump({"clips": [{k: c[k] for k in ("s", "e", "z", "tl0", "n")} for c in clips],
           "captions": [[w["w"] for w in c] for c in chunks]}, open(f"{tmp}/plan.json", "w"), indent=1)
