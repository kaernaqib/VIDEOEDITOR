#!/usr/bin/env python3
"""Look at candidate B-roll quickly: size, length, fps, hard cuts inside the clip, and a 6-frame sheet.

    python3 scripts/clip_sheet.py OUT_DIR clip1.mp4 [clip2.mp4 ...]

Use it to choose in-points (t_in) that avoid hard cuts and to confirm the subject sits where the
9:16 crop will land (the "fx" horizontal focus in the EDL).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import find_ffmpeg, probe  # noqa: E402


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    ff = find_ffmpeg()
    for f in sys.argv[2:]:
        info = probe(f, ff)
        err = subprocess.run([ff, '-hide_banner', '-i', f, '-vf', "scale=320:-2,select='gt(scene,0.35)',showinfo", '-an', '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
        cuts = [round(float(x), 2) for x in re.findall(r'pts_time:([\d.]+)', err)]
        base = os.path.splitext(os.path.basename(f))[0]
        sheet = os.path.join(out, base + '_sheet.jpg')
        n = 6
        fps_s = n / max(info['dur'], 0.1)
        subprocess.run([ff, '-v', 'error', '-y', '-i', f, '-vf',
                        'fps=%f,scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2,tile=%dx1' % (fps_s, n),
                        '-frames:v', '1', sheet], check=False)
        print('%s | %dx%d | %.2f s | %.2f fps | hard cuts at: %s | %s'
              % (base, info['w'], info['h'], info['dur'], info['fps'], cuts or 'none', sheet))


if __name__ == '__main__':
    main()
