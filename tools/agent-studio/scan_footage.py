"""scan_footage.py - senarai folder footage dalam D: untuk dropdown "Footage" dalam Agent Studio.

usage: python scan_footage.py [D:/] > folders.json
Kemudian tulis ke db studio: settings/main.folders (ArtifactData update).
Folder kerja (CLAUDE), video siap (Video) dan folder sistem dilangkau.
"""
import json, os, sys, datetime

ROOT = sys.argv[1] if len(sys.argv) > 1 else "D:/"
SKIP = {"claude", "video", "$recycle.bin", "system volume information", "found.000", "recovery"}
VID = {".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".m4v", ".insv", ".lrv"}
BULAN = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"]


def when(ts):
    d = datetime.datetime.fromtimestamp(ts)
    return f"{BULAN[d.month - 1]} {d.year}"


out = []
for dirpath, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(dirpath, ROOT)
    depth = 0 if rel == "." else rel.count(os.sep) + 1
    if depth == 1 and os.path.basename(dirpath).lower() in SKIP:
        dirs[:] = []
        continue
    dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in SKIP] if depth < 4 else []
    vids = []
    for f in files:
        if os.path.splitext(f)[1].lower() in VID:
            try:
                st = os.stat(os.path.join(dirpath, f))
            except OSError:
                continue
            if st.st_size > 0:
                vids.append(st)
    if not vids or depth == 0:
        continue
    size = sum(s.st_size for s in vids)
    t0, t1 = min(s.st_mtime for s in vids), max(s.st_mtime for s in vids)
    span = when(t0) if when(t0) == when(t1) else f"{when(t0)} – {when(t1)}"
    path = os.path.normpath(dirpath)
    name = " › ".join(os.path.normpath(rel).split(os.sep))
    out.append({"path": path, "label": f"{name} ({len(vids)} video, {size / 1e9:.1f} GB, {span})",
                "count": len(vids), "gb": round(size / 1e9, 1), "latest": int(t1)})
out.sort(key=lambda x: -x["latest"])
print(json.dumps(out, ensure_ascii=False, indent=1))
