"""Cut SFX compilation videos into single sounds (trimmed, loudness-matched WAVs) + library.json.

usage: python build_sfx_library.py SRC_DIR OUT_DIR [CUTS.json]
  SRC_DIR  folder holding the compilation videos named in CUTS["sources"]
  OUT_DIR  e.g. D:/CLAUDE/kerja/_sfx   ->  OUT_DIR/<source>/<name>.wav and OUT_DIR/library.json
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

src_dir, out = sys.argv[1], sys.argv[2]
cuts_p = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "..", "references", "sfx_cuts.json")
C = json.load(open(cuts_p, encoding="utf-8"))
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")


def one(c):
    srcname, name, a, b, tag = c
    d = os.path.join(out, srcname)
    os.makedirs(d, exist_ok=True)
    o = os.path.join(d, name + ".wav")
    af = f"{TRIM},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,afade=t=out:st={max(0, b - a - 0.25):.2f}:d=0.25"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a}", "-t", f"{b - a}", "-i",
                        os.path.join(src_dir, C["sources"][srcname]), "-vn", "-af", af, "-ac", "2", o],
                       capture_output=True, text=True)
    if r.returncode:
        return {"name": name, "error": r.stderr[-300:]}
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", o],
                               capture_output=True, text=True).stdout.strip() or 0)
    return {"name": name, "file": f"{srcname}/{name}.wav", "dur": round(dur, 2), "tag": tag}


with ThreadPoolExecutor(4) as ex:
    lib = list(ex.map(one, C["cuts"]))
json.dump(lib, open(os.path.join(out, "library.json"), "w", encoding="utf-8"), indent=1)
bad = [x for x in lib if "error" in x]
print(f"{len(lib) - len(bad)} sounds -> {out}", *(f"FAILED {x['name']}: {x['error']}" for x in bad), sep="\n")
