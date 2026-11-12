"""Shared helpers for the talking-head-reels scripts (Python 3.9+).

Everything here is deliberately dependency-light: only numpy is needed by some callers,
and ffmpeg is located on PATH, through $FFMPEG, or through the imageio-ffmpeg package.
"""
import json
import os
import re
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def die(msg, code=1):
    sys.stderr.write('ERROR: ' + msg + '\n')
    sys.exit(code)


_FF = None


def ffmpeg_has_ass(ff):
    """True when this ffmpeg build has the libass `ass` filter (needed for all text)."""
    try:
        out = subprocess.run([ff, '-hide_banner', '-filters'], capture_output=True, text=True, timeout=30,
                             stdin=subprocess.DEVNULL).stdout
    except Exception:
        return False
    return re.search(r'^\s*\S*\s+ass\s', out, re.M) is not None


def ffmpeg_candidates():
    cands = []
    env = os.environ.get('FFMPEG')
    if env and os.path.exists(env):
        cands.append(env)
    on_path = shutil.which('ffmpeg')
    if on_path:
        cands.append(on_path)
    try:
        import imageio_ffmpeg  # type: ignore
        cands.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    return [c for i, c in enumerate(cands) if c not in cands[:i]]


def find_ffmpeg():
    """Return an ffmpeg binary (one with libass when available) or exit with install advice."""
    global _FF
    if _FF:
        return _FF
    cands = ffmpeg_candidates()
    if not cands:
        die('ffmpeg not found. Install it (brew install ffmpeg) or `pip install imageio-ffmpeg` '
            'in the Python environment you run these scripts with, or set $FFMPEG.')
    with_ass = [c for c in cands if ffmpeg_has_ass(c)]
    _FF = with_ass[0] if with_ass else cands[0]
    return _FF


def probe(path, ffmpeg=None):
    """Width, height, duration (s), fps, has_audio for a media file, parsed from ffmpeg's banner."""
    ff = ffmpeg or find_ffmpeg()
    err = subprocess.run([ff, '-hide_banner', '-i', path], capture_output=True, text=True).stderr
    info = dict(w=0, h=0, dur=0.0, fps=0.0, audio=False)
    m = re.search(r'Stream .*?Video:.*?(\d{2,5})x(\d{2,5})', err)
    if m:
        info['w'], info['h'] = int(m.group(1)), int(m.group(2))
    d = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    if d:
        info['dur'] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    f = re.search(r'Video:.*?(\d+(?:\.\d+)?) fps', err)
    if f:
        info['fps'] = float(f.group(1))
    else:
        f = re.search(r'Video:.*?(\d+(?:\.\d+)?) tbr', err)
        if f:
            info['fps'] = float(f.group(1))
    info['audio'] = bool(re.search(r'Stream .*?Audio:', err))
    rot = re.search(r'rotation of (-?\d+(?:\.\d+)?) degrees', err) or re.search(r'rotate\s*:\s*(-?\d+)', err)
    if rot and abs(float(rot.group(1))) % 180 == 90:      # phone video stored sideways
        info['w'], info['h'] = info['h'], info['w']
    return info


def nice_fps(fps):
    """Snap a measured frame rate to the value the render should use."""
    for target in (23.976, 24, 25, 29.97, 30, 50, 59.94, 60):
        if abs(fps - target) < 0.02:
            return target
    return round(fps, 3) if fps else 25


def load_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)


def project_config(project_dir):
    p = os.path.join(project_dir, 'project.json')
    if not os.path.exists(p):
        die('no project.json in %s - run scripts/prepare_project.py first' % project_dir)
    return load_json(p)


def run(cmd, **kw):
    """subprocess.run with check=True and a readable error."""
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        die('command failed (%s): %s' % (e.returncode, ' '.join(str(c) for c in cmd)[:400]))


def write_gray_prores(ffmpeg, w, h, fps, dst):
    """Start an ffmpeg process that turns raw 8-bit gray frames on stdin into a ProRes LT matte file."""
    return subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '%dx%d' % (w, h),
                             '-r', str(fps), '-i', '-', '-c:v', 'prores_ks', '-profile:v', '1', '-pix_fmt', 'yuv422p10le', dst],
                            stdin=subprocess.PIPE)


def box_blur(m, r):
    """Fast box blur of a 2-D float array (integral image)."""
    import numpy as np
    c = np.cumsum(np.cumsum(np.pad(m, ((r + 1, r), (r + 1, r))), 0), 1)
    return (c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]) / (2 * r + 1) ** 2
