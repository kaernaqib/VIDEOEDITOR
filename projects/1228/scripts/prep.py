"""Per reel: split the 1228 window into camera parts (one per source file), extract audio + loudness,
write words.json (source-absolute seconds) and a contact sheet.

usage: python prep.py WORK_DIR [reel ids...]
"""
import json, os, subprocess, sys, wave
import numpy as np

work = sys.argv[1]
only = set(sys.argv[2:])
R = json.load(open(f"{work}/reels.json", encoding="utf-8"))
S = json.load(open(f"{work}/source_map.json", encoding="utf-8"))
segs = [g for g in S["segments"] if g["vol"] > 0 and "DJI_" in (g["path"] or "")]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(" ".join(cmd) + "\n" + r.stderr[-800:])
    return r.stdout


for r in R:
    if only and r["id"] not in only:
        continue
    t0, t1 = r["hook_tl"]
    pieces = []
    for g in segs:
        a, b = max(t0, g["tl0"]), min(t1, g["tl1"])
        if b - a > 2.0:
            pieces.append({"path": g["path"], "src_a": g["src0"] + a - g["tl0"], "src_b": g["src0"] + b - g["tl0"]})
    parts = []
    for p in pieces:          # same file back to back -> one part, the user's own cuts become removals
        if parts and parts[-1]["path"] == p["path"] and p["src_a"] >= parts[-1]["src_b"] - 0.01:
            if p["src_a"] - parts[-1]["src_b"] > 0.05:
                parts[-1]["remove"].append([parts[-1]["src_b"], p["src_a"], "cut out in 1228"])
            parts[-1]["src_b"] = p["src_b"]
        else:
            parts.append(dict(p, remove=[]))
    rd = f"{work}/r{r['id']}"
    os.makedirs(rd, exist_ok=True)
    for k, p in enumerate(parts):
        pd = f"{rd}/p{k}"
        os.makedirs(pd, exist_ok=True)
        a, b = p["src_a"], p["src_b"]
        # loudness + audio for the whole file up to src_b (front padded with digital silence before src_a)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", p["path"],
                              "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.int16)
        pad = np.zeros(int(round(a * 16000)), np.int16)
        full = np.concatenate([pad, x])
        with wave.open(f"{pd}/camera_16k.wav", "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); wf.writeframes(full.tobytes())
        f = full.astype(np.float32) / 32768
        n = len(f) // 160
        db = 20 * np.log10(np.sqrt((f[: n * 160].reshape(n, 160) ** 2).mean(1) + 1e-12))
        db[: int(a * 100)] = -100
        np.save(f"{pd}/db10ms.npy", db)
        ws = [w for w in S["words"] if w["path"] == p["path"] and w["s"] is not None and w["e"] is not None
              and a <= w["s"] and w["e"] <= b
              and not any(ra <= w["s"] < rb for ra, rb, _ in p["remove"])]
        words = [{"i": i, "w": " " + w["w"], "s": w["s"], "e": max(w["e"], w["s"] + 0.05), "p": 1.0} for i, w in enumerate(ws)]
        json.dump(words, open(f"{pd}/words.json", "w", encoding="utf-8"), ensure_ascii=False)
        p["n_words"] = len(words)
        # contact sheet: 6 frames across the part
        ts = np.linspace(a + 0.5, b - 0.5, 6)
        for j, t in enumerate(ts):
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", p["path"], "-frames:v", "1",
                 "-vf", "scale=480:-2", f"{pd}/f{j}.jpg"])
        run(["ffmpeg", "-v", "error", "-y"] + sum([["-i", f"{pd}/f{j}.jpg"] for j in range(6)], []) +
            ["-filter_complex", "[0][1][2]hstack=3[a];[3][4][5]hstack=3[b];[a][b]vstack", f"{pd}/sheet.jpg"])
    json.dump(parts, open(f"{rd}/parts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(r["id"], [(os.path.basename(p["path"]), round(p["src_a"], 2), round(p["src_b"], 2), len(p["remove"]), p["n_words"]) for p in parts])
