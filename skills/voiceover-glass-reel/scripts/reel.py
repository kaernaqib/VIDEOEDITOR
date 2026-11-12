#!/usr/bin/env python3
"""reel.py: the data side of the voiceover glass reel. Python 3.9+, standard library only.

  reel.py prep    <voice file> <project dir>   convert, transcribe, cut pauses/breaths -> work/voice_cut.wav, work/words.json
  reel.py words   <project dir>                print the words with index and programme time (to write story.json)
  reel.py chunks  <project dir>                cut the voice into audio chunks for the host's lip-synced clips
  reel.py align   <project dir>                measure each host clip's lip-sync offset against its chunk
  reel.py screen  <plate.png> <project dir>    find the green TV screen in the TV plate
  reel.py sfx     <project dir>                synthesise the sound effects into work/sfx
  reel.py plan    <project dir>                story.json -> work/plan.json for After Effects (+ checks)

The project dir holds story.json (written by Claude, see references/story.md) and assets/.
Everything is local: no network, no third-party packages.
"""
import array
import difflib
import json
import math
import os
import random
import re
import subprocess
import sys
import wave

FPS = 25
HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "bin")


# ---------------------------------------------------------------- helpers
def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def tool(name):
    p = os.path.join(BIN, name)
    if not os.path.exists(p):
        die("missing %s: run scripts/build_tools.sh first" % p)
    return p


def fr(t):
    return int(round(t * FPS))


def read_wav(path):
    w = wave.open(path, "rb")
    if w.getsampwidth() != 2:
        die("%s: expected 16-bit PCM" % path)
    ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    a = array.array("h")
    a.frombytes(raw)
    if sys.byteorder == "big":
        a.byteswap()
    return a, ch, sr


def write_wav(path, samples, ch, sr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = array.array("h", samples)
    if sys.byteorder == "big":
        a.byteswap()
    w = wave.open(path, "wb")
    w.setnchannels(ch)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(a.tobytes())
    w.close()


def envelope(a, ch, sr, hop_s=0.01, stride=6):
    """dB per hop (10 ms), mono, sub-sampled."""
    hop = int(sr * hop_s) * ch
    out = []
    for i in range(0, len(a) - hop + 1, hop):
        seg = a[i:i + hop:stride * ch]
        s = 0
        for v in seg:
            s += v * v
        out.append(10 * math.log10(s / max(1, len(seg)) / 1073741824.0 + 1e-12))
    return out


def runs(b):
    out, i = [], 0
    while i < len(b):
        j = i
        while j < len(b) and b[j] == b[i]:
            j += 1
        out.append((b[i], i, j))
        i = j
    return out


def clean(w):
    return re.sub(r"^[^\w$#@%&']+|[^\w%']+$", "", w)


def paths(proj):
    proj = os.path.abspath(proj)
    return {
        "work": os.path.join(proj, "work"),
        "story": os.path.join(proj, "story.json"),
        "words": os.path.join(proj, "work", "words.json"),
        "cuts": os.path.join(proj, "work", "cuts.json"),
        "voice": os.path.join(proj, "work", "voice_cut.wav"),
        "chunks": os.path.join(proj, "work", "host_chunks.json"),
        "tv": os.path.join(proj, "work", "tv_screen.json"),
        "sfx": os.path.join(proj, "work", "sfx"),
        "plan": os.path.join(proj, "work", "plan.json"),
    }


# ---------------------------------------------------------------- prep: transcribe + cut pauses and breaths
def cmd_prep(voice, proj):
    P = paths(proj)
    os.makedirs(P["work"], exist_ok=True)
    src = os.path.join(P["work"], "voice_src.wav")
    subprocess.run([tool("to_wav"), voice, src], check=True)
    wsrc = os.path.join(P["work"], "words_src.json")
    loc = os.environ.get("REEL_LOCALE", "en-US")
    if os.environ.get("REEL_WORDS"):                # word times from elsewhere (older macOS): skip the transcriber
        wsrc = os.path.abspath(os.environ["REEL_WORDS"])
        r = subprocess.CompletedProcess([], 0)
    else:
        r = subprocess.run([tool("transcribe"), src, wsrc, loc])
    if r.returncode != 0 or not os.path.exists(wsrc):
        die("transcription failed (exit %d). It needs macOS 26 or newer (on-device SpeechAnalyzer). On older macOS save word "
            "times as {\"words\": [{\"w\": ..., \"start\": ..., \"end\": ...}]} and run prep with REEL_WORDS=<that file>" % r.returncode)
    words = [w for w in jload(wsrc)["words"] if w.get("start") is not None and clean(w["w"])]
    if not words:
        die("no words recognised: is the voiceover in %s? set REEL_LOCALE=xx-XX" % loc)
    a, ch, sr = read_wav(src)
    db = envelope(a, ch, sr)
    n = len(db)
    total_f = int(round(len(a) / ch / sr * FPS))
    # thresholds from this recording: speech level = median of hops inside words, noise = 10th percentile
    allh = sorted(db)
    speech = sorted(db[i] for w in words for i in range(int(w["start"] * 100), min(n, int(w["end"] * 100))))
    sp_med = speech[len(speech) // 2] if speech else -30.0
    noise = allh[len(allh) // 10]
    th = max(noise + 8.0, sp_med - 6.0)
    v = [x > th for x in db]
    for val, s, e in runs(v):                       # dips < 90 ms inside speech are speech
        if not val and e - s < 9 and s > 0 and e < n:
            for i in range(s, e):
                v[i] = True
    for val, s, e in runs(v):                       # blips < 50 ms are noise
        if val and e - s < 5:
            for i in range(s, e):
                v[i] = False
    for w in words:                                 # protect every word onset
        for i in range(max(0, int((w["start"] - 0.03) * 100)), min(n, int((w["start"] + 0.10) * 100))):
            v[i] = True
    starts = [w["start"] for w in words]
    spans = [(w["start"], w["end"]) for w in words]

    def is_speech(s, e):                            # a sounding run with no word in it is a breath or mouth noise
        return (any(s - 0.06 <= st <= e + 0.02 for st in starts)
                or any(min(e, en) - max(s, st) >= 0.06 for st, en in spans)
                or any(-0.02 <= s - en <= 0.12 for st, en in spans))
    seg = [(s / 100.0, e / 100.0) for val, s, e in runs(v) if val and is_speech(s / 100.0, e / 100.0)]
    merged = []
    for s, e in seg:                                # 20 ms of air before, 60 ms after; gaps < 60 ms stay
        s, e = max(0.0, s - 0.02), e + 0.06
        if merged and s - merged[-1][1] < 0.06:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    frs = []
    for s, e in merged:                             # whole frames, snapped outward
        f0, f1 = int(math.floor(s * FPS)), min(total_f, int(math.ceil(e * FPS)))
        if frs and f0 <= frs[-1][1]:
            frs[-1][1] = max(frs[-1][1], f1)
        else:
            frs.append([f0, f1])
    out = []                                        # silences >= 140 ms still inside a piece are cut too
    for f0, f1 in frs:
        h0, h1, s0, i = f0 * 4, f1 * 4, f0, f0 * 4
        while i < h1:
            if i < n and db[i] < th:
                j = i
                while j < h1 and j < n and db[j] < th:
                    j += 1
                if j - i >= 14 and i > h0 and j < h1:
                    c0, c1 = int(math.ceil((i / 100.0 + 0.04) * FPS)), int(math.floor((j / 100.0 - 0.03) * FPS))
                    if c1 - c0 >= 2 and c0 > s0:
                        out.append([s0, c0])
                        s0 = c1
                i = j
            else:
                i += 1
        if f1 > s0:
            out.append([s0, f1])
    trimmed = []                                    # each piece keeps only 30 ms before its first sound and 60 ms after its last
    for f0, f1 in out:
        hs = [h for h in range(f0 * 4, min(f1 * 4, n)) if db[h] >= th]
        if not hs:
            continue
        n0 = max(f0, int(math.floor((hs[0] / 100.0 - 0.03) * FPS)))
        n1 = min(f1, int(math.ceil((hs[-1] / 100.0 + 0.07) * FPS)))
        if n1 <= n0:
            continue
        if trimmed and n0 <= trimmed[-1][1]:
            trimmed[-1][1] = max(trimmed[-1][1], n1)
        else:
            trimmed.append([n0, n1])
    out = trimmed
    segs, pf = [], 0
    for f0, f1 in out:
        segs.append({"src_f0": f0, "src_f1": f1, "prog_f0": pf})
        pf += f1 - f0
    # the cut voice, 8 ms fades at every join
    spf = sr // FPS
    fade = int(sr * 0.008)
    buf = array.array("h")
    for s in segs:
        piece = a[s["src_f0"] * spf * ch:s["src_f1"] * spf * ch]
        m = len(piece) // ch
        for k in range(min(fade, m // 2)):
            g = k / float(fade)
            for c in range(ch):
                piece[k * ch + c] = int(piece[k * ch + c] * g)
                piece[(m - 1 - k) * ch + c] = int(piece[(m - 1 - k) * ch + c] * g)
        buf.extend(piece)
    write_wav(P["voice"], buf, ch, sr)

    def to_prog(t, end=False):
        for s in segs:
            a0, a1 = s["src_f0"] / FPS, s["src_f1"] / FPS
            if a0 <= t < a1 or (end and a0 < t <= a1):
                return s["prog_f0"] / FPS + (t - a0)
            if t < a0:
                return s["prog_f0"] / FPS
        return pf / FPS
    prog = []
    for i, w in enumerate(words):
        t0 = to_prog(w["start"])
        t1 = max(t0 + 0.04, to_prog(w["end"], True))
        prog.append({"i": i, "w": clean(w["w"]), "raw": w["w"], "t0": round(t0, 3), "t1": round(t1, 3),
                     "end": bool(re.search(r"[.?!]$", w["w"].strip()))})
    dur = round((pf + 20) / float(FPS), 2)          # 0.8 s tail after the last word
    jsave(P["cuts"], {"fps": FPS, "threshold_db": round(th, 1), "src_s": round(len(a) / ch / sr, 2),
                      "prog_s": round(pf / float(FPS), 2), "dur": dur, "segments": segs})
    jsave(P["words"], {"fps": FPS, "dur": dur, "words": prog})
    print("voice: %.2f s -> %.2f s (%d pieces, threshold %.1f dB), %d words, reel length %.2f s"
          % (len(a) / ch / sr, pf / float(FPS), len(segs), th, len(prog), dur))
    print("next: reel.py words %s" % proj)


# ---------------------------------------------------------------- words
def cmd_words(proj):
    W = jload(paths(proj)["words"])
    line = []
    for w in W["words"]:
        line.append("%d:%s" % (w["i"], w["w"]))
        if w["end"] or len(line) >= 14:
            print("%6.2f  %s" % (W["words"][int(line[0].split(":")[0])]["t0"], "  ".join(line) + ("  |" if w["end"] else "")))
            line = []
    if line:
        print("%6.2f  %s" % (W["words"][int(line[0].split(":")[0])]["t0"], "  ".join(line)))
    print("reel length %.2f s, %d words" % (W["dur"], len(W["words"])))


# ---------------------------------------------------------------- shots from story.json
def shot_times(story, W):
    words = W["words"]
    shots = story["shots"]
    out = []
    for k, s in enumerate(shots):
        wi = s["at"]
        if not (0 <= wi < len(words)):
            die("shot %d: word index %s out of range" % (k + 1, wi))
        if k and wi <= shots[k - 1]["at"]:
            die("shot %d starts at word %d, not after the previous shot (word %d): word indices must rise" % (k + 1, wi, shots[k - 1]["at"]))
        t0 = 0.0 if k == 0 else max(0, fr(words[wi]["t0"]) - 1) / float(FPS)   # cut 1 frame before the word
        out.append(dict(s, t0=t0))
    for k in range(len(out)):
        out[k]["t1"] = out[k + 1]["t0"] if k + 1 < len(out) else W["dur"]
        if out[k]["t1"] - out[k]["t0"] < 0.2:
            die("shot %d (word %d) is shorter than 0.2 s: two shots start on almost the same word" % (k + 1, out[k]["at"]))
    return out


def word_time(W, i, lead=1):
    return max(0, fr(W["words"][i]["t0"]) - lead) / float(FPS)


# ---------------------------------------------------------------- chunks: audio for the lip-synced host clips
def cmd_chunks(proj):
    P = paths(proj)
    story, W = jload(P["story"]), jload(P["words"])
    a, ch, sr = read_wav(P["voice"])
    total = len(a) / ch / float(sr)
    shots = shot_times(story, W)
    chunks, n = [], 0
    for s in shots:
        if s["kind"] != "host":
            continue
        n += 1
        L = s["t1"] - s["t0"]
        if L > 14.0:
            die("host shot at word %d is %.1f s: split it into host shots of 14 s or less" % (s["at"], L))
        c0, c1 = max(0.0, s["t0"] - 0.2), min(total, s["t1"] + 0.2)
        if c1 - c0 < 5.0:                           # the video model wants at least ~5 s: take more voice after (or before)
            c1 = min(total, c0 + 5.0)
            c0 = max(0.0, c1 - 5.0)
        cid = "host_%02d" % n
        wav = os.path.join(P["work"], "host", cid + ".wav")
        write_wav(wav, a[int(c0 * sr) * ch:int(c1 * sr) * ch], ch, sr)
        dur = int(math.ceil(c1 - c0))
        chunks.append({"id": cid, "at": s["at"], "t0": round(c0, 3), "t1": round(c1, 3), "wav": wav,
                       "clip": "assets/host/%s.mp4" % cid, "gen_duration": dur, "lag": None,
                       "says": " ".join(w["w"] for w in W["words"] if c0 <= w["t0"] < c1)})
    old = {c["id"]: c for c in (jload(P["chunks"])["chunks"] if os.path.exists(P["chunks"]) else [])}
    for c in chunks:                                # keep a measured lag when the chunk did not change
        o = old.get(c["id"])
        if o and abs(o["t0"] - c["t0"]) < 1e-3 and abs(o["t1"] - c["t1"]) < 1e-3:
            c["lag"] = o.get("lag")
    jsave(P["chunks"], {"chunks": chunks})
    for c in chunks:
        print("%s  %6.2f-%6.2f  gen %2d s  -> %s   \"%s\"" % (c["id"], c["t0"], c["t1"], c["gen_duration"], c["clip"], c["says"]))
    print("%d chunks in work/host. Generate one lip-synced clip per chunk (references/higgsfield.md), save as the clip path." % len(chunks))


# ---------------------------------------------------------------- align: lip-sync offset of each host clip
def env100(path):
    """onset strength per 10 ms: rises of the level (syllable starts), lightly smoothed"""
    a, ch, sr = read_wav(path)
    e = envelope(a, ch, sr, stride=2)
    m = max(e) if e else 0
    e = [max(0.0, x - (m - 40)) for x in e]         # 40 dB window, silence = 0
    on = [0.0] + [max(0.0, e[i] - e[i - 2]) for i in range(1, len(e))]
    return [(on[max(0, i - 1)] + 2 * on[i] + on[min(len(on) - 1, i + 1)]) / 4.0 for i in range(len(on))]


def pearson_lag_range(x, y, lo, hi):
    """lag (hops) in [lo, hi] at which y best matches x shifted: y[i + lag] ~ x[i]"""
    best, bl = -2.0, 0
    for lag in range(lo, hi + 1):
        i0, i1 = max(0, -lag), min(len(x), len(y) - lag)
        if i1 - i0 < 0.4 * min(len(x), len(y)):
            continue
        xs, ys = x[i0:i1], y[i0 + lag:i1 + lag]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxy = sxx = syy = 0.0
        for p, q in zip(xs, ys):
            p -= mx
            q -= my
            sxy += p * q
            sxx += p * p
            syy += q * q
        sc = sxy / math.sqrt(sxx * syy + 1e-9)
        if sc > best:
            best, bl = sc, lag
    return bl, best


def cmd_align(proj):
    P = paths(proj)
    C = jload(P["chunks"])
    spans = {s["at"]: (s["t0"], s["t1"]) for s in shot_times(jload(P["story"]), jload(P["words"])) if s["kind"] == "host"}
    for c in C["chunks"]:
        clip = os.path.join(proj, c["clip"])
        if not os.path.exists(clip):
            print("%s: no clip yet (%s)" % (c["id"], c["clip"]))
            continue
        tmp = os.path.join(P["work"], "host", c["id"] + "_clipaudio.wav")
        r = subprocess.run([tool("to_wav"), clip, tmp], capture_output=True, text=True)
        if r.returncode != 0:
            print("%s: clip has no audio, lag set to 0 (check lip-sync by eye)" % c["id"])
            c["lag"] = 0.0
            continue
        # 1) words: transcribe the clip and match its words with the chunk's words -> median onset difference
        W = jload(P["words"])["words"]
        cw = [(w["w"].lower(), w["t0"] - c["t0"]) for w in W if c["t0"] <= w["t0"] < c["t1"]]
        tj = os.path.join(P["work"], "host", c["id"] + "_clipwords.json")
        subprocess.run([tool("transcribe"), tmp, tj, os.environ.get("REEL_LOCALE", "en-US")], capture_output=True)
        vw = [(clean(w["w"]).lower(), w["start"]) for w in (jload(tj)["words"] if os.path.exists(tj) else []) if w.get("start") is not None]
        sm = difflib.SequenceMatcher(None, [a for a, _ in cw], [a for a, _ in vw], autojunk=False)
        span = spans.get(c["at"], (0.0, 1e9))       # the words the shot actually shows count first
        diffs, near = [], []
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                d = vw[blk.b + k][1] - cw[blk.a + k][1]
                diffs.append(d)
                if span[0] - 0.05 <= cw[blk.a + k][1] + c["t0"] <= span[0] + 2.0:
                    near.append(d)
        if len(near) >= 2:
            diffs = near
        x, y = env100(c["wav"]), env100(tmp)
        if len(diffs) >= 2:
            diffs.sort()
            guess = diffs[len(diffs) // 2]
            g = int(round(guess * 100))
            bl, best = pearson_lag_range(x, y, g - 8, g + 8)    # 2) refine within +-80 ms on syllable onsets
            how = "%d matching words" % len(diffs)
        else:
            bl, best = pearson_lag_range(x, y, -120, 120)
            how = "sound only (words did not match)"
        c["lag"] = bl / 100.0
        c["match_words"] = len(diffs)
        print("%s: lag %+.2f s (%s, onset match %.2f)%s" % (c["id"], c["lag"], how, best,
              "  CHECK: the clip does not say the chunk's words; check the lips by eye or regenerate" if len(diffs) < 2 else ""))
    jsave(P["chunks"], C)


# ---------------------------------------------------------------- screen: green TV screen in the plate
def cmd_screen(png, proj):
    P = paths(proj)
    bmp = os.path.join(P["work"], "_plate.bmp")
    os.makedirs(P["work"], exist_ok=True)
    subprocess.run(["sips", "-s", "format", "bmp", png, "--out", bmp], check=True, capture_output=True)
    with open(bmp, "rb") as f:
        d = f.read()
    off = int.from_bytes(d[10:14], "little")
    W, H = int.from_bytes(d[18:22], "little", signed=True), int.from_bytes(d[22:26], "little", signed=True)
    bpp = int.from_bytes(d[28:30], "little")
    flip = H > 0
    H = abs(H)
    bpx = bpp // 8
    row = (W * bpx + 3) // 4 * 4
    xs, ys, rs, gs, bs = [], [], [], [], []
    for y in range(0, H, 2):
        ry = (H - 1 - y) if flip else y
        base = off + ry * row
        for x in range(0, W, 2):
            p = base + x * bpx
            b, g, r = d[p], d[p + 1], d[p + 2]
            if g > 70 and g > 1.35 * r + 10 and g > 1.2 * b + 10:
                xs.append(x)
                ys.append(y)
                rs.append(r)
                gs.append(g)
                bs.append(b)
    os.remove(bmp)
    if len(xs) < 400:
        die("no green screen found in %s: regenerate the plate with a flat chroma-green screen" % png)
    xs.sort()
    ys.sort()
    k = max(1, len(xs) // 200)                      # robust box: ignore 0.5 % stray pixels on each side
    box = [xs[k], ys[k], xs[-k] + 2, ys[-k] + 2]
    key = [sorted(rs)[len(rs) // 2], sorted(gs)[len(gs) // 2], sorted(bs)[len(bs) // 2]]
    out = {"plate": os.path.relpath(os.path.abspath(png), proj), "w": W, "h": H, "box": box, "key": key}
    jsave(P["tv"], out)
    print("screen box x %d-%d y %d-%d (%dx%d) in %dx%d, key rgb %s -> work/tv_screen.json"
          % (box[0], box[2], box[1], box[3], box[2] - box[0], box[3] - box[1], W, H, key))


# ---------------------------------------------------------------- sfx: synthesised, licence-free
def cmd_sfx(proj):
    out = paths(proj)["sfx"]
    os.makedirs(out, exist_ok=True)
    sr = 48000
    rnd = random.Random(7)

    def save(name, x):
        m = max(1e-9, max(abs(v) for v in x))
        write_wav(os.path.join(out, name + ".wav"), [int(v / m * 0.89 * 32767) for v in x], 1, sr)

    def noise(n):
        return [rnd.uniform(-1, 1) for _ in range(n)]

    def lp(x, a):                                   # one-pole low-pass, a = per-sample coefficient (list or float)
        y, s = [], 0.0
        for i, v in enumerate(x):
            k = a[i] if isinstance(a, list) else a
            s += k * (v - s)
            y.append(s)
        return y
    # whoosh: band of noise sweeping up then down, 0.55 s
    n = int(0.55 * sr)
    cut = [0.01 + 0.25 * math.sin(math.pi * i / n) ** 2 for i in range(n)]
    nz = noise(n)
    lo = lp(nz, cut)
    lo2 = lp(lo, cut)
    save("whoosh", [(lo[i] - lo2[i] * 0.6) * math.sin(math.pi * i / n) ** 1.5 for i in range(n)])
    # impact: low sine drop + soft noise thump, 1.1 s
    n = int(1.1 * sr)
    ph, x = 0.0, []
    lowz = lp(noise(n), 0.02)
    for i in range(n):
        t = i / float(sr)
        f = 38 + 70 * math.exp(-t * 18)
        ph += 2 * math.pi * f / sr
        x.append(math.sin(ph) * math.exp(-t * 4.0) + lowz[i] * 3 * math.exp(-t * 30))
    save("impact", x)
    # flash: bright crack 0.3 s
    n = int(0.3 * sr)
    hz = noise(n)
    hl = lp(hz, 0.5)
    save("flash", [(hz[i] - hl[i]) * math.exp(-i / float(sr) * 22) for i in range(n)])
    # glitch: chopped bit-crushed tones 0.35 s
    n = int(0.35 * sr)
    x, seg = [], 0
    while len(x) < n:
        L = int(sr * rnd.uniform(0.012, 0.045))
        f = rnd.choice([180, 330, 660, 1250, 2400])
        on = rnd.random() < 0.8
        for i in range(L):
            v = math.copysign(1, math.sin(2 * math.pi * f * i / sr)) if on else 0
            v += rnd.uniform(-0.4, 0.4) if on else 0
            x.append(round(v * 4) / 4.0)
        seg += 1
    save("glitch", [v * (1 - i / float(n)) ** 0.5 for i, v in enumerate(x[:n])])
    # pop: short tuned tick 0.12 s
    n = int(0.12 * sr)
    save("pop", [math.sin(2 * math.pi * 1300 * i / sr) * math.exp(-i / float(sr) * 45) + rnd.uniform(-1, 1) * math.exp(-i / float(sr) * 300)
                 for i in range(n)])
    # tick: tiny click for keyword flips 0.05 s
    n = int(0.05 * sr)
    save("tick", [rnd.uniform(-1, 1) * math.exp(-i / float(sr) * 160) for i in range(n)])

    def key():                                      # one typewriter key: click + body
        m = int(0.07 * sr)
        f = rnd.uniform(1800, 2600)
        return [rnd.uniform(-1, 1) * math.exp(-i / float(sr) * 220) * 0.9 + math.sin(2 * math.pi * f * i / sr) * math.exp(-i / float(sr) * 90) * 0.35
                + math.sin(2 * math.pi * 140 * i / sr) * math.exp(-i / float(sr) * 60) * 0.5 for i in range(m)]
    # typing: 8 s of keys at 11-15 keys/s
    n = int(8 * sr)
    x = [0.0] * n
    t = 0.05
    while t < 7.9:
        k = key()
        g = rnd.uniform(0.6, 1.0)
        p = int(t * sr)
        for i, v in enumerate(k):
            if p + i < n:
                x[p + i] += v * g
        t += rnd.uniform(0.055, 0.1)
    save("typing", x)
    print("sfx written to work/sfx: whoosh impact flash glitch pop tick typing")


# ---------------------------------------------------------------- plan: story.json -> work/plan.json
def cmd_plan(proj):
    P = paths(proj)
    proj = os.path.abspath(proj)
    story, W = jload(P["story"]), jload(P["words"])
    words = W["words"]
    shots = shot_times(story, W)
    warn, err = [], []

    def ab(p):
        if not p:
            return None
        q = p if os.path.isabs(p) else os.path.join(proj, p)
        if not os.path.exists(q):
            err.append("missing file: %s" % p)
        return q
    chunks = {c["at"]: c for c in (jload(P["chunks"])["chunks"] if os.path.exists(P["chunks"]) else [])}
    tv = jload(P["tv"]) if os.path.exists(P["tv"]) else None
    used = {}
    lst = story.get("list")
    L0 = word_time(W, lst["from"]) if lst else None
    L1 = (word_time(W, lst["to"] + 1) if lst and lst["to"] + 1 < len(words) else W["dur"]) if lst else None
    out_shots = []
    for k, s in enumerate(shots):
        o = {"id": "S%02d" % (k + 1), "kind": s["kind"], "t0": round(s["t0"], 3), "t1": round(s["t1"], 3), "at": s["at"]}
        kind = s["kind"]
        if kind == "host":
            c = chunks.get(s["at"])
            if not c:
                err.append("host shot at word %d has no chunk: run reel.py chunks" % s["at"])
                continue
            o["file"] = ab(s.get("file") or c["clip"])
            lag = c.get("lag")
            if lag is None:
                warn.append("%s: lip-sync offset not measured (reel.py align), using 0" % c["id"])
                lag = 0.0
            o["in"] = round(s["t0"] - c["t0"] + lag, 3)
            if o["in"] < 0:
                if o["in"] < -0.04:
                    warn.append("%s: the clip starts speaking %.2f s too late for this shot; lips run %.2f s early" % (c["id"], -o["in"], -o["in"]))
                o["in"] = 0.0
            o["mode"] = s.get("mode", "tv")
            if o["mode"] == "tv" and not tv:
                err.append("host shot in TV mode but no work/tv_screen.json: run reel.py screen")
        elif kind == "clip":
            o["file"] = ab(s.get("file"))
            o["in"] = float(s.get("in", 0.0))
            o["color"] = bool(s.get("color", False))
            key = (s.get("file"), round(o["in"], 1))
            if key in used:
                warn.append("%s repeats the clip of %s (%s at %.1f s): every shot should be new footage" % (o["id"], used[key], s.get("file"), o["in"]))
            used[key] = o["id"]
        elif kind == "type":
            o["text"] = s["text"]
        elif kind == "giant":
            o["word"] = s["word"]
            o["label"] = s.get("label", "")
            o["sub"] = s.get("sub", "")
            o["label_t"] = round(word_time(W, s["label_at"]), 3) if "label_at" in s else o["t0"]
            o["sub_t"] = round(word_time(W, s["sub_at"]), 3) if "sub_at" in s else o["t0"]
        elif kind == "cards":
            o["line"] = s.get("line", "")
            items = []
            for it in s["items"]:
                items.append({"t": round(word_time(W, it["at"]) if "at" in it else s["t0"], 3), "file": ab(it["file"]),
                              "in": float(it.get("in", 0.0)), "logo": ab(it.get("logo")), "name": it.get("name", "")})
            if len(items) > 4:
                err.append("%s: cards take at most 4 items" % o["id"])
            o["items"] = items
        else:
            err.append("unknown shot kind %r at word %d" % (kind, s["at"]))
        o["hit"] = s.get("hit")
        o["flash"] = s.get("flash", kind in ("clip", "cards"))
        o["in_list"] = bool(lst) and L0 <= s["t0"] < L1
        out_shots.append(o)
    # captions: phrases of up to 4 words, one line, never over pages that carry their own text
    keys = set(story.get("keys", []))
    flips = set(lst.get("flip", [])) if lst else set()
    spell = {int(k): v for k, v in story.get("spell", {}).items()}   # fixes for misheard names: {"28": "Grok"}

    def shot_at(t):
        for o in out_shots:
            if o["t0"] <= t < o["t1"]:
                return o
        return out_shots[-1]
    caps, cur = [], None
    for w in words:
        t = word_time(W, w["i"], 0)
        sh = shot_at(t)
        if sh["kind"] in ("type", "giant", "cards"):
            if cur:
                caps.append(cur)
                cur = None
            continue
        brk = (cur is None or len(cur["words"]) >= 4 or sum(len(x[1]) for x in cur["words"]) + len(w["w"]) > 26
               or cur["shot"] != sh["id"] or words[w["i"] - 1]["end"] or w["t0"] - words[w["i"] - 1]["t1"] > 0.25)
        if brk:
            if cur:
                caps.append(cur)
            y = 880 if sh["kind"] == "host" else 560
            cur = {"shot": sh["id"], "y": y, "words": []}
        cur["words"].append([t, spell.get(w["i"], w["w"]), w["i"] in keys or w["i"] in flips, w["i"] in flips])
    if cur:
        caps.append(cur)
    for k, c in enumerate(caps):
        sh = [o for o in out_shots if o["id"] == c["shot"]][0]
        nxt = caps[k + 1]["words"][0][0] if k + 1 < len(caps) else W["dur"]
        c["t0"] = c["words"][0][0]
        c["t1"] = round(min(sh["t1"], nxt), 3)
    # hits, flashes and sound effects
    hits, sfx = [], []
    prev = None
    for o in out_shots:
        if o["hit"]:
            hits.append({"t": o["t0"], "type": o["hit"]})
            sfx.append({"t": o["t0"] - (3 if o["hit"] == "strobe" else 1) / float(FPS), "name": "glitch" if o["hit"] != "strobe" else "flash", "db": -12})
        if o["t0"] > 0:
            if o["kind"] in ("type", "giant", "cards"):
                sfx.append({"t": o["t0"], "name": "impact", "db": -9})
            elif not (prev and prev["kind"] == o["kind"] == "clip"):
                sfx.append({"t": o["t0"] - 0.12, "name": "whoosh", "db": -15})
        if o["flash"] and o["t0"] > 0:
            sfx.append({"t": o["t0"], "name": "flash", "db": -17})
        if o["kind"] == "type":
            sfx.append({"t": o["t0"] + 0.1, "name": "typing", "db": -15, "len": round(min(len(o["text"]) * 0.05, (o["t1"] - o["t0"]) * 0.7), 2)})
        if o["kind"] == "cards":
            for it in o["items"][1:] if o["items"] and abs(o["items"][0]["t"] - o["t0"]) < 0.05 else o["items"]:
                sfx.append({"t": it["t"], "name": "pop", "db": -13})
        if o["kind"] == "giant" and o["label"]:
            sfx.append({"t": o["label_t"], "name": "pop", "db": -13})
        prev = o
    for c in caps:
        for wd in c["words"]:
            if wd[3]:
                sfx.append({"t": wd[0] + 2 / float(FPS), "name": "tick", "db": -12})
    music = story.get("music")
    plan = {"root": proj, "aep": os.path.join(proj, story.get("aep", "reel.aep")), "fps": FPS, "dur": W["dur"],
            "title": story.get("title", "REEL"), "accent": story.get("accent", "#FFD23F"), "glow": story.get("glow", "#CFF3FF"),
            "voice": P["voice"], "music": ab(music) if music else None, "music_db": story.get("music_db", -17),
            "sfx_dir": P["sfx"], "tv": None, "list": [L0, L1] if lst else None,
            "shots": out_shots, "captions": caps, "hits": hits, "sfx": sorted(sfx, key=lambda e: e["t"])}
    if tv:
        plan["tv"] = dict(tv, plate=ab(tv["plate"]))
    if not os.path.exists(os.path.join(P["sfx"], "whoosh.wav")):
        warn.append("no sound effects yet: run reel.py sfx")
    jsave(P["plan"], plan)
    n = {}
    for o in out_shots:
        n[o["kind"]] = n.get(o["kind"], 0) + 1
    print("plan: %.2f s, %d shots %s, %d caption phrases, %d hits, %d sfx -> work/plan.json"
          % (W["dur"], len(out_shots), n, len(caps), len(hits), len(sfx)))
    host_s = sum(o["t1"] - o["t0"] for o in out_shots if o["kind"] == "host")
    print("host on screen %.1f s of %.1f s, average shot %.2f s" % (host_s, W["dur"], W["dur"] / max(1, len(out_shots))))
    for m in warn:
        print("WARN " + m)
    for m in err:
        print("ERROR " + m)
    if err:
        sys.exit(1)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    c = a[0]
    if c == "prep" and len(a) == 3:
        cmd_prep(a[1], a[2])
    elif c == "words" and len(a) == 2:
        cmd_words(a[1])
    elif c == "chunks" and len(a) == 2:
        cmd_chunks(a[1])
    elif c == "align" and len(a) == 2:
        cmd_align(a[1])
    elif c == "screen" and len(a) == 3:
        cmd_screen(a[1], a[2])
    elif c == "sfx" and len(a) == 2:
        cmd_sfx(a[1])
    elif c == "plan" and len(a) == 2:
        cmd_plan(a[1])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
