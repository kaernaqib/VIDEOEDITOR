"""Compile (once) and locate the Apple Vision command-line tools in scripts/vision/*.swift.

Binaries are cached in ~/Library/Caches/talking-head-reels/bin so the skill folder stays read-only.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/Library/Caches/talking-head-reels/bin')
TOOLS = ('person_track', 'subject_mask', 'largest_subject_mask')


def tool(name):
    if name not in TOOLS:
        raise ValueError(name)
    src = os.path.join(HERE, 'vision', name + '.swift')
    exe = os.path.join(CACHE, name)
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
        return exe
    swiftc = shutil.which('swiftc')
    if not swiftc:
        sys.exit('ERROR: swiftc not found - install the Xcode command line tools: xcode-select --install')
    os.makedirs(CACHE, exist_ok=True)
    print('compiling %s ...' % name, flush=True)
    res = subprocess.run([swiftc, '-O', src, '-o', exe], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit('ERROR: could not compile %s:\n%s' % (name, res.stderr[-2000:]))
    return exe


def upright_proxy(ffmpeg, src, dst, w, h, fps):
    """ffmpeg applies the rotation flag of phone videos; Vision then sees the picture the way players show it."""
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', src, '-an', '-vf', 'scale=%d:%d:flags=bicubic,fps=%s' % (w, h, fps),
                    '-c:v', 'prores_ks', '-profile:v', '0', dst], check=True)
    return dst
