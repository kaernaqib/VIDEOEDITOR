"""Poster-frame reel: 9:16 canvas, poster + hook headline on top, landscape video band in the middle,
word-chunk subtitles below on black.  Pure ffmpeg + libass + Pillow.

usage: python render_poster_reel.py JOB.json            (see ../SKILL.md for the job format)
       python render_poster_reel.py JOB.json --still    (layout check: one PNG at the poster/headline, no render)

Layout (1080x1920, measured from the reference "gradient frame"):
  0    - 608   poster image, solid at the top, fading to black by ~470; headline sits on the fade
  ~375 / ~482  headline line 1 / line 2 (condensed bold, one line accent colour, one white)
  ~582         small pill (series / source label)
  608  - 1414  video band 1080x806 (~4:3), source cropped around the face, never full 9:16
  ~1466        subtitle, 1-3 words, one word in the accent colour
  1414 - 1920  black (platform UI zone)
"""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
BAND_Y, BAND_H = 608, 806
FONTS = "C:/Windows/Fonts"
DEF = {
    "head_font": f"{FONTS}/impact.ttf", "head_size": 112, "head_y": [375, 482],
    "accent": "#CA00FF", "sub_accent": "#A773F8", "sub_font": "Segoe UI", "sub_size": 66, "sub_y": 1466, "sub_mode": "highlight", "sub_fill": "#FFD800",
    "pill_font": f"{FONTS}/segoeui.ttf", "pill_bold": f"{FONTS}/segoeuib.ttf", "pill_y": 582,
    "fade": [300, 470], "fps": 30, "crf": 20,
}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(" ".join(map(str, cmd[:16])) + "\n" + r.stderr[-1500:])
    return r.stdout


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
               "-of", "csv=p=0", path]).strip().split("\n")[0]
    w, h = tuple(int(x) for x in out.split(",") if x.strip())[:2]   # phone MOVs add a trailing empty field
    rot = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_side_data=rotation",
               "-of", "csv=p=0", path]).strip().replace(",", "")
    if rot.lstrip("-").isdigit() and abs(int(rot)) % 180 == 90:      # portrait phone video: ffmpeg auto-rotates
        w, h = h, w
    return w, h


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ass_col(h):
    r, g, b = hexrgb(h)
    return f"&H00{b:02X}{g:02X}{r:02X}&"


# ---------------------------------------------------------------- poster + headline + pill (static layer)
def grab_frame(src, t, out):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-q:v", "2", out])
    return out


def tile_img(t, k, tmp, tw, ph):
    """One poster tile tw x ph: a still (image) or a video frame (video + t), cropped so the face
    (focus = [x, y] as fractions of the source) sits at 30% of the tile height, above the headline."""
    src = t.get("image") or grab_frame(t["video"], t["t"], f"{tmp}/poster_{k}.jpg")
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")      # phone photos carry rotation in EXIF
    fx, fy = t.get("focus", [0.5, 0.35])
    ch = im.height / t.get("zoom", 1.3)
    cw = ch * tw / ph
    if cw > im.width:
        cw = im.width; ch = cw * ph / tw
    x0 = min(max(0, fx * im.width - cw / 2), im.width - cw)
    y0 = min(max(0, fy * im.height - ch * t.get("face_at", 0.30)), im.height - ch)
    im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((tw, ph), Image.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(t.get("contrast", 1.12))
    return ImageEnhance.Color(im).enhance(t.get("saturation", 1.15))


def poster_layer(job, S, tmp):
    P = job["poster"]
    tiles = P.get("tiles") or [P]                             # 1 tile = full-width poster; 2-3 = collage
    ph = S["fade"][1] + 140                                   # poster area height (rest is black anyway)
    n, feather = len(tiles), 90
    tw = W // n
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    for k, t in enumerate(tiles):
        extra = feather if n > 1 else 0
        x = max(0, k * tw - extra // 2)
        w_k = min(W - x, tw + extra)
        im = tile_img(t, k, tmp, w_k, ph)
        m = Image.new("L", (w_k, ph), 255)
        if k > 0:                                             # soft left edge blends into the previous tile
            md = ImageDraw.Draw(m)
            for i in range(feather):
                md.line([(i, 0), (i, ph)], fill=int(255 * i / feather))
        canvas.paste(im, (x, 0), m)
    a, b = S["fade"]                                          # fade poster into black between y=a..b
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for y in range(H):
        v = 0 if y <= a else min(1, (y - a) / (b - a))
        md.line([(0, y), (W, y)], fill=int(255 * (v ** 0.8)))
    canvas = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), canvas, mask)
    d = ImageDraw.Draw(canvas)

    # headline: list of lines; each "text" or {"text", "color"}; default line 1 accent, line 2 white
    lines = [l if isinstance(l, dict) else {"text": l} for l in job["headline"]]
    acc = job.get("accent_line", 0)
    for i, l in enumerate(lines):
        col = hexrgb(l.get("color") or (S["accent"] if i == acc else "#FFFFFF"))
        txt = l["text"].upper()
        size = S["head_size"]
        while size > 40:
            f = ImageFont.truetype(S["head_font"], size)
            if d.textlength(txt, font=f) <= W - 110:
                break
            size -= 4
        y = S["head_y"][i] if i < len(S["head_y"]) else S["head_y"][-1] + (i - len(S["head_y"]) + 1) * 107
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).text((W // 2, y + 4), txt, font=f, fill=200, anchor="mm")
        canvas.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(8)))
        d.text((W // 2, y), txt, font=f, fill=col, anchor="mm")

    pill = job.get("pill")                                    # "plain part" or ["plain part ", "bold part"]
    if pill:
        parts = [pill] if isinstance(pill, str) else pill
        fonts = [ImageFont.truetype(S["pill_font"], 25), ImageFont.truetype(S["pill_bold"], 25)]
        widths = [d.textlength(p, font=fonts[min(i, 1)]) for i, p in enumerate(parts)]
        tw, py = sum(widths), S["pill_y"]
        d.rounded_rectangle([W / 2 - tw / 2 - 22, py - 21, W / 2 + tw / 2 + 22, py + 21], radius=21, fill=(255, 255, 255))
        x = W / 2 - tw / 2
        for i, p in enumerate(parts):
            d.text((x, py), p, font=fonts[min(i, 1)], fill=(40, 40, 40), anchor="lm")
            x += widths[i]
    out = f"{tmp}/layer.png"
    canvas.save(out)
    return out


# ---------------------------------------------------------------- video band
def band_vf(w, h, f, s0, s1, n):
    A = W / BAND_H
    ch = h / max(1.0, s0)
    cw = min(w, ch * A)
    ch = cw / A
    x0 = max(0, min(w - cw, f * w - cw / 2))
    y0 = (h - ch) / 2
    vf = f"crop={int(cw)//2*2}:{int(ch)//2*2}:{int(x0)}:{int(y0)}"
    if abs(s1 - s0) > 0.002:
        z = s1 / s0
        vf += (f",scale=2160:1612,zoompan=z='1+{z - 1:.5f}*on/{max(1, n - 1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
               f":d=1:s={W}x{BAND_H}:fps={DEF['fps']}")
    else:
        vf += f",scale={W}:{BAND_H}:flags=lanczos"
    return vf + ",setsar=1"


def render_band(job, S, tmp):
    fps = S["fps"]
    clips = job.get("clips") or [{"path": job["video"], "t0": job.get("t0", 0), "t1": job.get("t1"), "f": job.get("f", 0.5)}]
    eq = job.get("grade", "eq=contrast=1.06:saturation=1.08")

    def one(k_c):
        k, c = k_c
        w, h = probe(c["path"])
        t0 = c["t0"] if "t0" in c else c["src0"] / job.get("edl_fps", fps)
        t1 = c.get("t1")
        if t1 is None and "src1" in c:
            t1 = c["src1"] / job.get("edl_fps", fps)
        n = c.get("frames") or (round((t1 - t0) * fps) if t1 else None)   # "frames": exact count from the caller
        o = f"{tmp}/b{k:03d}.mp4"
        if os.path.splitext(c["path"])[1].lower() in (".jpg", ".jpeg", ".png", ".webp"):
            # still photo: whole picture fitted to the band height over a blurred cover copy of itself
            run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-i", c["path"], "-frames:v", str(n),
                 "-filter_complex", f"[0:v]split[a][b];[a]scale={W}:{BAND_H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{BAND_H},boxblur=30:2[bg];[b]scale=-2:{BAND_H}[fg];[bg][fg]overlay=(W-w)/2:0,{eq},"
                 "format=yuv420p,setsar=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", o])
            return o
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.4f}", "-i", c["path"]]
        if n:
            cmd += ["-frames:v", str(n)]
        vf = f"fps={fps}," + band_vf(w, h, c.get("f", 0.5), c.get("scale0", 1.0), c.get("scale1", c.get("scale0", 1.0)), n or 1)
        # tpad: a clip that runs past the end of its file is padded, so the band never comes out short
        cmd += ["-vf", f"{vf},{eq},tpad=stop_mode=clone:stop_duration=1,format=yuv420p", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", o]
        run(cmd)
        return o

    with ThreadPoolExecutor(3) as ex:
        parts = list(ex.map(one, enumerate(clips)))
    lst = f"{tmp}/band.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    out = f"{tmp}/band.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


# ---------------------------------------------------------------- subtitles (1-3 word chunks)
STOP = set("ni tu la lah kan je jer dah nak tak ke kat dekat di dia aku kau kita yang dan itu ini pun eh ah oh ya "
           "tapi bila cam macam kalau baru lagi sangat pula pulalah jap ada boleh dengan untuk saya "
           "the a an to of in on is it and or so".split())


def chunks(job):
    words = [w for w in job.get("words") or [] if w.get("s") is not None and w.get("e") is not None]
    out = []
    for c in job["captions"]:
        if not c.get("text") and c.get("keyword"):
            out.append({"a": c["a"], "b": c["b"], "w": [c["keyword"]], "hi": 0, "t": [(c["a"], c["b"])]})
            continue
        toks = c["text"].split() + ([c["keyword"]] if c.get("keyword") else [])
        if not toks:
            continue
        inside = [w for w in words if w["s"] >= c["a"] - 0.05 and w["e"] <= c["b"] + 0.05]
        if len(inside) == len(toks):
            times = [(w["s"], w["e"]) for w in inside]
        else:                                                  # spread by character count
            tot = sum(len(t) + 1 for t in toks)
            acc, times = c["a"], []
            for t in toks:
                d = (c["b"] - c["a"]) * (len(t) + 1) / tot
                times.append((acc, acc + d)); acc += d
        n = len(toks)
        size = 3 if n % 3 == 0 or n > 4 else 2 if n % 2 == 0 else min(3, n)
        i = 0
        while i < n:
            j = min(n, i + size)
            if n - j == 1:
                j = n                                          # don't leave a single orphan word
            grp = toks[i:j]
            cand = [k for k, t in enumerate(grp) if re.sub(r"\W", "", t.lower()) not in STOP]
            hi = max(cand or range(len(grp)), key=lambda k: len(grp[k]))
            if c.get("keyword") and c["keyword"] in grp:
                hi = grp.index(c["keyword"])
            a = times[i][0] if i else c["a"]
            b = times[j - 1][1] if j < n else c["b"]
            out.append({"a": a, "b": b, "w": grp, "hi": hi, "t": times[i:j]})
            i = j
    for k in range(len(out) - 1):                              # close tiny gaps so text doesn't flicker
        if 0 < out[k + 1]["a"] - out[k]["b"] < 0.25:
            out[k]["b"] = out[k + 1]["a"]
    return out


def write_ass(job, S, path):
    """sub_mode "karaoke": every word starts white and turns sub_fill (yellow) the moment it is spoken.
    sub_mode "highlight" (default): one word per chunk in sub_accent (purple), rest white."""
    t = lambda s: f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
    kara = S["sub_mode"] == "karaoke"
    acc = ass_col(S["sub_fill"] if kara else S["sub_accent"])
    glow = "&H50000000" if kara else "&H70" + acc[4:-1]   # karaoke: soft dark halo; highlight: soft accent glow
    primary, secondary = (acc[:-1], "&H00FFFFFF") if kara else ("&H00FFFFFF", "&H00FFFFFF")
    cap = lambda w: (w[:1].upper() + w[1:]).replace("{", "(").replace("}", ")")
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow\n"
            f"Style: Sub,{S['sub_font']},{S['sub_size']},{primary},{secondary},{glow},&H96000000,1,0,5,60,60,0,1,3,0\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    ev = []
    for c in chunks(job):
        if kara:
            # ASS karaoke: text is SecondaryColour (white) until its \k time has run, then PrimaryColour (yellow).
            # An empty {\kN} syllable waits N centiseconds; the word after {\k1} flips almost instantly.
            txt, prev = "", c["a"]
            for k, w in enumerate(c["w"]):
                ws = max(prev, c["t"][k][0])
                txt += (" " if k else "") + "{\\k%d}{\\k1}%s" % (round((ws - prev) * 100), cap(w))
                prev = ws + 0.01
        else:
            txt = " ".join(("{\\c" + acc + "}" + cap(w) + "{\\c&H00FFFFFF&}") if k == c["hi"] else cap(w)
                           for k, w in enumerate(c["w"]))
        ev.append(f"Dialogue: 0,{t(c['a'])},{t(c['b'])},Sub,{{\\pos({W // 2},{S['sub_y']})\\fad(60,0)\\blur7}}{txt}")
    open(path, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- main
def main():
    job_path = sys.argv[1]
    job = json.load(open(job_path, encoding="utf-8"))
    S = dict(DEF, **job.get("style", {}))
    out = job["out"]
    tmp = job.get("tmp") or os.path.splitext(out)[0] + "_tmp"
    os.makedirs(tmp, exist_ok=True)
    layer = poster_layer(job, S, tmp)
    if "--still" in sys.argv:
        print("layout ->", layer)
        return
    band = f"{tmp}/band.mp4"
    if not ("--reuse-band" in sys.argv and os.path.exists(band)):
        band = render_band(job, S, tmp)
    ass = f"{tmp}/subs.ass"
    write_ass(job, S, ass)
    ass_ff = ass.replace("\\", "/").replace(":", "\\:")
    inputs = ["-loop", "1", "-framerate", str(S["fps"]), "-i", layer, "-i", band]
    amap, afc = [], ""
    if job.get("audio"):
        inputs += ["-i", job["audio"]]
        amap = ["-map", "2:a", "-c:a", "aac", "-b:a", "192k"]
        # SFX / meme sounds: [{"t": sec on reel timeline, "file": wav, "vol": 0.5, "dur": max sec}]
        sfx, lib = job.get("sfx") or [], job.get("sfx_dir", "")
        if sfx:
            parts, labels = [], ["[2:a]"]
            for k, s in enumerate(sfx):
                inputs += ["-i", os.path.join(lib, s["file"])]
                n, d = 3 + k, s.get("dur", 2.5)
                parts.append(f"[{n}:a]atrim=0:{d},afade=t=out:st={max(0, d - 0.3):.2f}:d=0.3,aresample=48000,"
                             f"aformat=channel_layouts=stereo,volume={s.get('vol', 0.5)},adelay={int(s['t'] * 1000)}:all=1[s{k}]")
                labels.append(f"[s{k}]")
            afc = ";" + ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[a]"
            amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    fc = f"[0:v][1:v]overlay=0:{BAND_Y}:shortest=1,subtitles='{ass_ff}',format=yuv420p[v]" + afc
    run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", fc, "-map", "[v]"] + amap +
        ["-c:v", "libx264", "-preset", "medium", "-crf", str(S["crf"]), "-r", str(S["fps"]), "-shortest",
         "-dn", "-map_metadata", "-1", "-movflags", "+faststart", out])
    print("reel ->", out)


if __name__ == "__main__":
    main()
