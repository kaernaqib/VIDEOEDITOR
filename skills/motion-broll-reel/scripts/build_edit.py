"""build a 9:16 edit from a shot list -> edit video (1080x1920 30fps) + ambient audio.
usage: PY build_edit.py shots.json OUT.mp4
shots.json: [[clip_no, start_s, dur_s], ...]  (clip_no = # in sheets/index.json)
portrait clips: cover-crop; landscape: fit width over a blurred copy.
"""
import json, os, subprocess, sys
D = "D:/CLAUDE/kerja/berekeh/footage"
idx = json.load(open("D:/CLAUDE/kerja/berekeh/sheets/index.json"))
shots = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
tmp = os.path.splitext(OUT)[0] + "_parts"
os.makedirs(tmp, exist_ok=True)
parts = []
for k, (no, ss, du) in enumerate(shots):
    src = os.path.join(D, idx[no - 1])
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                        "-of", "json", src], capture_output=True, text=True).stdout
    s = json.loads(o)["streams"][0]
    w, h = s["width"], s["height"]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        rot = int(sd.get("rotation", 0) or 0)
    if abs(rot) == 90:
        w, h = h, w
    if h >= w:
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"
        fc = ["-vf", vf]
    else:
        fc = ["-filter_complex", "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,eq=brightness=-0.12[bg];"
              "[b]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1,fps=30,format=yuv420p"]
    p = f"{tmp}/p{k:02d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-t", str(du), "-i", src] + fc +
                   ["-af", "aresample=48000,aformat=channel_layouts=stereo", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", p], check=True)
    parts.append(p)
    print(k, idx[no - 1], ss, du, flush=True)
lst = f"{tmp}/list.txt"
open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-af", "aresample=async=1", OUT], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", OUT, "-vn", "-ac", "2", "-ar", "48000", os.path.splitext(OUT)[0] + "_ambient.wav"], check=True)
print("done", OUT)
