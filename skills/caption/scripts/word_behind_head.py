"""Word-behind-head caption reel.

Satu perkataan besar duduk DI BELAKANG kepala (person cut-out di atasnya),
dan perkataan lain timbul sebagai caption kecil di depan, ikut masa suara.

Subcommand:
  transcribe VIDEO --out words.json [--names "Shopee,CapCut"]
      Ekstrak audio 16 kHz mono -> numpy -> faster-whisper (small, word
      timestamps, TIADA initial prompt). Snap setiap mula perkataan ke titik
      audio mula kuat (whisper selalu awal ~0.1 s). Tulis words.json.

  render job.json [--still] [--force-masks]
      Cut-out (rembg birefnet-portrait, cache dalam work/masks), susun lapisan
      belakang ke depan: frame asal -> perkataan besar -> orang -> caption.
      Export H.264 MP4 (saiz, fps dan warna sama dengan asal) + still PNG.
      --still: render satu frame PNG sahaja (untuk semak layout, jimat masa).

Job JSON (lihat SKILL.md untuk penuh):
  {"video": "clip.mp4", "out": "out/clip_caption.mp4",
   "words": "words.json", "big": 5,
   "style": {...}, "sfx": [{"t": 1.2, "file": "whoosh.wav", "vol": 0.3}]}

Keperluan: ffmpeg/ffprobe dalam PATH, Python: faster-whisper, rembg (cpu),
Pillow, numpy. Model disimpan dalam folder kerja (U2NET_HOME, HF_HOME).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent

DEF_STYLE = {
    "big_font": ["fonts/Anton-Regular.ttf", "C:/Windows/Fonts/impact.ttf"],
    "cap_font": ["fonts/Inter-Bold.ttf", "fonts/Inter-Variable.ttf",
                 "C:/Windows/Fonts/segoeuib.ttf"],
    "big_color": "#FFFFFF",
    "big_width": 0.85,        # lebar perkataan besar / lebar frame
    "big_uppercase": True,
    "head_overlap": 0.60,     # kepala tutup ~60% tinggi huruf (dari bawah)
    "min_cover": 0.15,        # sekurang-kurangnya 15% piksel huruf ditutup kepala
    "big_y": None,            # override: pusat-y perkataan besar (0-1 tinggi frame)
    "pop_frames": 6,          # pop 80% -> ~105% -> 100%
    "pop_from": 0.80,
    "pop_overshoot": 0.05,
    "cap_color": "#FFFFFF",
    "cap_accent": None,       # cth "#FFD400" untuk warnakan satu perkataan / kumpulan
    "cap_size": 0.07,         # saiz fon caption / lebar frame
    "cap_max_words": 3,
    "cap_shadow": 0.55,       # kelegapan bayang lembut
    "cap_min_y": 0.15,        # zon caption: 15% hingga 65% tinggi frame
    "cap_max_y": 0.65,
    "cap_gap": 0.02,          # jarak caption di atas perkataan besar (x tinggi frame)
    "cap_fallback_y": 0.62,   # kalau tiada ruang di atas perkataan besar: paras dada
    "crf": 17,
    "preset": "medium",
}


# ----------------------------------------------------------------- utils

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def ffprobe(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
        "-show_format", "-of", "json", str(path)])
    j = json.loads(out)
    s = j["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if "rotate" in (s.get("tags") or {}):
        rot = int(s["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (s.get("avg_frame_rate") or s["r_frame_rate"]).split("/")
    fps_str = s.get("avg_frame_rate") or s["r_frame_rate"]
    fps = float(num) / float(den or 1)
    nb = s.get("nb_frames")
    dur = float(s.get("duration") or j["format"].get("duration") or 0)
    n = int(nb) if nb and nb.isdigit() else int(round(dur * fps))
    return {
        "w": w, "h": h, "fps": fps, "fps_str": fps_str, "n": n, "dur": dur,
        "space": s.get("color_space"), "primaries": s.get("color_primaries"),
        "transfer": s.get("color_transfer"), "range": s.get("color_range"),
    }


def matrix_name(space):
    """Nama matrix untuk filter scale ffmpeg."""
    return {"bt709": "bt709", "bt470bg": "bt601", "smpte170m": "bt601",
            "bt2020nc": "bt2020", "bt2020c": "bt2020", "fcc": "fcc",
            "smpte240m": "smpte240m"}.get(space or "", "bt709")


def find_font(cands, size):
    for c in cands:
        p = Path(c)
        if not p.is_absolute():
            for base in (Path.cwd(), SKILL):
                if (base / p).exists():
                    p = base / p
                    break
        if p.exists():
            f = ImageFont.truetype(str(p), size)
            if "[" in p.name or "Variable" in p.name:  # fon variable: pilih Bold
                try:
                    f.set_variation_by_name("Bold")
                except Exception:
                    pass
            return f
    raise SystemExit(f"Fon tak jumpa: {cands}. Muat turun Anton & Inter ke ./fonts/")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def model_dirs(work: Path):
    """Simpan semua model dalam folder kerja, bukan dalam profil user."""
    os.environ.setdefault("U2NET_HOME", str(work / "models" / "rembg"))
    os.environ.setdefault("HF_HOME", str(work / "models" / "hf"))
    Path(os.environ["U2NET_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["HF_HOME"]).mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------ transcribe

def load_audio(video, sr=16000):
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
        "-ar", str(sr), "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32).copy()


def snap_onsets(words, audio, sr=16000, back=0.05, fwd=0.25):
    """Alih mula perkataan ke titik audio mula naik (envelope RMS 10 ms)."""
    hop = int(sr * 0.01)
    n = len(audio) // hop
    env = np.sqrt(np.mean(audio[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    floor = np.percentile(env, 20)
    for w in words:
        s = w["s"]
        a = max(0, int((s - back) / 0.01))
        b = min(n - 1, int((s + fwd) / 0.01))
        if b <= a + 2:
            continue
        seg = env[a:b]
        peak = seg.max()
        thr = floor + 0.35 * (peak - floor)
        idx = np.argmax(seg >= thr)
        # undur ke tepi naik (bukan puncak)
        while idx > 0 and seg[idx - 1] > floor + 0.15 * (peak - floor):
            idx -= 1
        new = (a + idx) * 0.01
        if new < w["e"] - 0.03:
            w["s_raw"] = s
            w["s"] = round(float(new), 3)
    # pastikan masa sentiasa naik
    for i in range(1, len(words)):
        if words[i]["s"] < words[i - 1]["s"]:
            words[i]["s"] = words[i - 1]["s"]
    return words


def cmd_transcribe(a):
    video = Path(a.video)
    work = Path(a.work or video.parent / "work")
    work.mkdir(parents=True, exist_ok=True)
    model_dirs(work)
    from faster_whisper import WhisperModel  # import lambat, selepas HF_HOME

    audio = load_audio(video)
    model = WhisperModel(a.model, device="cpu", compute_type="int8",
                         download_root=str(work / "models" / "whisper"))
    # PENTING: beri array, bukan path (versi baru crash dengan path);
    # TIADA initial_prompt (prompt boleh buat whisper buang perkataan).
    segs, info = model.transcribe(audio, language=a.lang, word_timestamps=True,
                                  vad_filter=False, beam_size=5)
    words = []
    for seg in segs:
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(float(w.start), 3),
                              "e": round(float(w.end), 3),
                              "p": round(float(w.probability), 2)})
    words = snap_onsets(words, audio)
    names = [n.strip() for n in (a.names or "").split(",") if n.strip()]
    for w in words:  # tanda perkataan meragukan untuk disemak
        core = re.sub(r"[^\w']", "", w["w"]).lower()
        w["check"] = bool(w["p"] < 0.55)
        for nm in names:
            if core and core != nm.lower() and _close(core, nm.lower()):
                w["suggest"] = nm
                w["check"] = True
    out = Path(a.out)
    out.write_text(json.dumps({"lang": info.language, "words": words},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    line = " ".join(("[" + w["w"] + "?]") if w["check"] else w["w"] for w in words)
    print(f"{len(words)} perkataan -> {out}\n{line}")


def _close(a, b):
    """Jarak edit kecil (untuk cadang ejaan nama jenama)."""
    if abs(len(a) - len(b)) > 2:
        return False
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1] <= max(1, len(b) // 4)


# ---------------------------------------------------------------- frames

def read_frames(video, info, start=0, count=None):
    m = matrix_name(info["space"])
    rng = "tv" if info["range"] != "pc" else "pc"
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start / info['fps']:.6f}"]
    cmd += ["-i", str(video)]
    if count:
        cmd += ["-frames:v", str(count)]
    cmd += ["-vf",
            f"scale=in_color_matrix={m}:in_range={rng}:flags=bicubic+accurate_rnd+full_chroma_int,format=rgb24",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = info["w"] * info["h"] * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(info["h"], info["w"], 3)
    p.wait()


def make_masks(video, info, start_frame, mdir: Path, force=False):
    mdir.mkdir(parents=True, exist_ok=True)
    todo = [i for i in range(start_frame, info["n"])
            if force or not (mdir / f"{i:05d}.png").exists()]
    if not todo:
        return
    from rembg import new_session, remove
    secs_guess = len(todo) * 3
    print(f"Cut-out {len(todo)} frame (anggaran {secs_guess // 60}-{secs_guess // 30} min)...")
    sess = new_session("birefnet-portrait")
    want = set(todo)
    for k, fr in enumerate(read_frames(video, info, start_frame)):
        i = start_frame + k
        if i not in want:
            continue
        m = remove(Image.fromarray(fr), session=sess, only_mask=True,
                   post_process_mask=False)  # simpan tepi lembut (rambut/hood)
        m.convert("L").save(mdir / f"{i:05d}.png")
        if k % 25 == 0:
            print(f"  mask {k + 1}/{len(todo)}", flush=True)


def load_mask(mdir, i, info):
    p = mdir / f"{i:05d}.png"
    if not p.exists():
        return None
    m = Image.open(p).convert("L")
    if m.size != (info["w"], info["h"]):
        m = m.resize((info["w"], info["h"]), Image.BILINEAR)
    return m


# ---------------------------------------------------------------- layout

def head_top(mask: Image.Image):
    """Baris paling atas kepala, cari dalam 40% tengah frame sahaja
    (supaya tangan yang diangkat di tepi tak dikira)."""
    a = np.asarray(mask, np.float32) / 255.0
    h, w = a.shape
    mid = a[:, int(w * 0.30): int(w * 0.70)]
    rows = (mid > 0.5).sum(axis=1)
    thr = max(3, int(mid.shape[1] * 0.04))
    ys = np.where(rows >= thr)[0]
    return int(ys[0]) if len(ys) else int(h * 0.35)


def render_word(text, font_cands, target_w, color, max_w):
    """Render perkataan besar sebagai RGBA, lebar = target_w (dipotong pada max_w)."""
    probe = find_font(font_cands, 400)
    l, t, r, b = probe.getbbox(text)
    size = max(10, int(400 * target_w / max(1, r - l)))
    f = find_font(font_cands, size)
    l, t, r, b = f.getbbox(text)
    while r - l > max_w and size > 10:
        size = int(size * 0.97)
        f = find_font(font_cands, size)
        l, t, r, b = f.getbbox(text)
    img = Image.new("RGBA", (r - l, b - t), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-l, -t), text, font=f, fill=color + (255,))
    return img


def place_big(word_img, mask, info, st):
    """Pusat-y perkataan besar supaya kepala tutup ~60% tingginya dan
    sekurang-kurangnya min_cover piksel huruf."""
    W, H = info["w"], info["h"]
    wh = word_img.height
    if st.get("big_y") is not None:
        return int(st["big_y"] * H - wh / 2)
    top = head_top(mask)
    y = int(top - (1 - st["head_overlap"]) * wh)  # atas perkataan
    alpha = np.asarray(word_img.split()[-1], np.float32) / 255.0
    m = np.asarray(mask, np.float32) / 255.0
    x0 = (W - word_img.width) // 2
    for _ in range(60):
        y0, y1 = max(0, y), min(H, y + wh)
        if y1 <= y0:
            break
        a = alpha[y0 - y: y1 - y, max(0, -x0): max(0, -x0) + min(W, word_img.width)]
        mm = m[y0:y1, max(0, x0): max(0, x0) + a.shape[1]]
        cover = (a * mm).sum() / max(1.0, alpha.sum())
        if cover >= st["min_cover"] or y + wh > H * 0.80:
            break
        y += max(2, wh // 40)  # turunkan sikit, masih boleh dibaca
    return y


def ease_pop(k, n, p0, over):
    """Skala pada frame k selepas perkataan disebut: p0 -> 1+over -> 1."""
    if k >= n:
        return 1.0
    t = (k + 1) / n
    if t < 0.65:
        u = t / 0.65
        return p0 + (1 + over - p0) * (1 - (1 - u) ** 3)
    u = (t - 0.65) / 0.35
    return 1 + over - over * (u * u * (3 - 2 * u))


# --------------------------------------------------------------- captions

def group_words(words, big_idx, max_n):
    """Kumpulan <=max_n perkataan, pecah pada tanda baca / jeda; buang perkataan besar."""
    groups, cur = [], []
    for i, w in enumerate(words):
        if i == big_idx:
            if cur:
                groups.append(cur)
            cur = []
            continue
        if cur and (len(cur) >= max_n or w["s"] - cur[-1]["e"] > 0.45):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.,!?;:]$", w["w"]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    # elak kumpulan 1 perkataan tergantung jika boleh gabung
    out = []
    for g in groups:
        if out and len(g) == 1 and len(out[-1]) < max_n and \
                not re.search(r"[.,!?;:]$", out[-1][-1]["w"]) and \
                g[0]["s"] - out[-1][-1]["e"] < 0.3:
            out[-1] = out[-1] + g
        else:
            out.append(g)
    return out


def caption_layer(groups, t, font, info, y_top, st, big_word_shown):
    """Lukis kumpulan caption aktif pada masa t (perkataan muncul ikut masa sendiri)."""
    W, H = info["w"], info["h"]
    active = None
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else 1e9
        if g[0]["s"] <= t < nxt:
            active = g
            break
    if not active:
        return None
    full = " ".join(re.sub(r"[.,;:]$", "", w["w"]) for w in active)
    l, tp, r, b = font.getbbox(full)
    tw, th = r - l, b - tp
    x = (W - tw) // 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    d = ImageDraw.Draw(lay)
    col = hex_rgb(st["cap_color"])
    acc = hex_rgb(st["cap_accent"]) if st.get("cap_accent") else None
    cx = x
    for w in active:
        token = re.sub(r"[.,;:]$", "", w["w"])
        wl = font.getbbox(token + " ")
        adv = font.getlength(token + " ")
        if w["s"] <= t:
            c = acc if (acc and w.get("accent")) else col
            sd.text((cx - l, y_top - tp), token, font=font, fill=255)
            d.text((cx - l, y_top - tp), token, font=font, fill=c + (255,))
        cx += adv
    blur = max(2, int(font.size * 0.12))
    sh = shadow.filter(ImageFilter.GaussianBlur(blur))
    sh = sh.point(lambda v: int(v * st["cap_shadow"]))
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    base.putalpha(sh)
    base = Image.alpha_composite(base, lay)
    return base


# ----------------------------------------------------------------- render

def cmd_render(a):
    job_path = Path(a.job).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    base = job_path.parent
    video = (base / job["video"]).resolve()
    out = (base / job.get("out", Path(job["video"]).stem + "_caption.mp4")).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = (base / job.get("work", "work")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    model_dirs(work)
    st = dict(DEF_STYLE, **job.get("style", {}))

    wj = job["words"]
    if isinstance(wj, str):
        wj = json.loads((base / wj).read_text(encoding="utf-8"))
    words = wj["words"] if isinstance(wj, dict) else wj
    big_idx = job["big"]
    if isinstance(big_idx, str):  # boleh beri perkataan, bukan indeks
        key = big_idx.lower()
        big_idx = next(i for i, w in enumerate(words)
                       if re.sub(r"[^\w']", "", w["w"]).lower() == key)
    big = words[big_idx]
    big_text = job.get("big_text") or re.sub(r"[^\w'%$-]", "", big["w"])
    if st["big_uppercase"]:
        big_text = big_text.upper()
    for i in job.get("accent_words", []):
        words[i]["accent"] = True

    info = ffprobe(video)
    fps = info["fps"]
    f_big = int(math.floor(big["s"] * fps + 1e-6))
    mdir = work / "masks"

    # mask hanya diperlukan dari frame perkataan besar sampai habis
    if a.still:
        make_masks_range(video, info, f_big, mdir, a.force_masks)
    else:
        make_masks(video, info, f_big, mdir, a.force_masks)

    ref_mask = load_mask(mdir, f_big, info)
    word_img = render_word(big_text, st["big_font"], int(info["w"] * st["big_width"]),
                           hex_rgb(st["big_color"]), info["w"])
    big_y = place_big(word_img, ref_mask, info, st)

    cap_font = find_font(st["cap_font"], max(12, int(info["w"] * st["cap_size"])))
    l, tp, r, b = cap_font.getbbox("Ag")
    cap_h = b - tp
    H = info["h"]
    cap_y = big_y - int(st["cap_gap"] * H) - cap_h
    if cap_y < st["cap_min_y"] * H:
        # Tiada ruang di atas perkataan besar: JANGAN tindih huruf. Pindah ke
        # paras dada (pilihan orang tu: subtitle bawah muka), masih atas 1/3 bawah.
        cap_y = int(st["cap_fallback_y"] * H)
    cap_y = int(min(cap_y, st["cap_max_y"] * H - cap_h))
    groups = group_words(words, big_idx, st["cap_max_words"])
    layout = {"big_text": big_text, "big_frame": f_big, "big_y": big_y,
              "big_h": word_img.height, "cap_y": cap_y,
              "groups": [" ".join(w["w"] for w in g) for g in groups]}
    (work / "layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=1),
                                      encoding="utf-8")

    def compose(i, fr):
        img = Image.fromarray(fr).convert("RGBA")
        t = i / fps
        if i >= f_big:
            s = ease_pop(i - f_big, st["pop_frames"], st["pop_from"], st["pop_overshoot"])
            wi = word_img
            if abs(s - 1) > 1e-3:
                nw = min(info["w"], max(1, int(word_img.width * s)))
                nh = max(1, int(word_img.height * nw / word_img.width))
                wi = word_img.resize((nw, nh), Image.LANCZOS)
            cy = big_y + word_img.height // 2
            img.alpha_composite(wi, ((info["w"] - wi.width) // 2, cy - wi.height // 2))
            m = load_mask(mdir, i, info)
            if m is not None:  # orang di atas perkataan besar
                person = Image.fromarray(fr).convert("RGBA")
                person.putalpha(m)
                img.alpha_composite(person)
        cap = caption_layer(groups, t, cap_font, info, cap_y, st, i >= f_big)
        if cap is not None:
            img.alpha_composite(cap)
        return img.convert("RGB")

    still_i = min(info["n"] - 1, f_big + st["pop_frames"] + int(fps * 0.4))
    if a.still:
        fr = next(read_frames(video, info, still_i, 1))
        p = out.with_suffix(".png")
        compose(still_i, fr).save(p)
        print(f"Still: {p}\nLayout: {json.dumps(layout, ensure_ascii=False)}")
        return

    m = matrix_name(info["space"])
    silent = work / "video_noaudio.mp4"
    enc = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{info['w']}x{info['h']}", "-r", info["fps_str"], "-i", "-",
           "-vf", f"scale=out_color_matrix={m}:out_range=tv:flags=bicubic+accurate_rnd+full_chroma_int,format=yuv420p",
           "-c:v", "libx264", "-crf", str(st["crf"]), "-preset", st["preset"]]
    for flag, key in (("-colorspace", "space"), ("-color_primaries", "primaries"),
                      ("-color_trc", "transfer")):
        if info.get(key) and info[key] != "unknown":
            enc += [flag, info[key]]
    enc += ["-color_range", "tv", str(silent)]
    p = subprocess.Popen(enc, stdin=subprocess.PIPE)
    still_img = None
    for i, fr in enumerate(read_frames(video, info)):
        im = compose(i, fr)
        if i == still_i:
            still_img = im
        p.stdin.write(im.tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{info['n']}", flush=True)
    p.stdin.close()
    p.wait()

    mux_audio(video, silent, out, job.get("sfx", []), base, job.get("sfx_dir"))
    if still_img is not None:
        still_img.save(out.with_suffix(".png"))
    print(f"Siap: {out}\nStill: {out.with_suffix('.png')}")


def make_masks_range(video, info, f, mdir, force):
    """Untuk --still: mask frame perkataan besar + frame still sahaja."""
    mdir.mkdir(parents=True, exist_ok=True)
    sess = None
    for i in {f, min(info["n"] - 1, f + 6 + int(info["fps"] * 0.4))}:
        p = mdir / f"{i:05d}.png"
        if p.exists() and not force:
            continue
        from rembg import new_session, remove
        sess = sess or new_session("birefnet-portrait")
        fr = next(read_frames(video, info, i, 1))
        remove(Image.fromarray(fr), session=sess, only_mask=True,
               post_process_mask=False).convert("L").save(p)


def mux_audio(video, silent, out, sfx, base, sfx_dir):
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(video)]
    filt, labels = [], ["[1:a]"]
    for k, s in enumerate(sfx):
        f = Path(s["file"])
        if not f.is_absolute():
            f = Path(sfx_dir or base) / f
        cmd += ["-i", str(f)]
        ms = int(s["t"] * 1000)
        dur = f",atrim=0:{s['dur']}" if s.get("dur") else ""
        filt.append(f"[{k + 2}:a]aresample=48000{dur},volume={s.get('vol', 0.3)},"
                    f"adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
    if sfx:
        filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[a]")
        cmd += ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a?", "-c:a", "copy"]
    cmd += ["-c:v", "copy", "-shortest", "-movflags", "+faststart", str(out)]
    run(cmd)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("video")
    t.add_argument("--out", default="words.json")
    t.add_argument("--work")
    t.add_argument("--model", default="small")
    t.add_argument("--lang", default=None, help="cth 'ms' atau 'en'; kosong = auto")
    t.add_argument("--names", help="nama jenama, dipisah koma")
    r = sub.add_parser("render")
    r.add_argument("job")
    r.add_argument("--still", action="store_true")
    r.add_argument("--force-masks", action="store_true")
    a = ap.parse_args()
    {"transcribe": cmd_transcribe, "render": cmd_render}[a.cmd](a)


if __name__ == "__main__":
    main()
