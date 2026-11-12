#!/usr/bin/env python3
"""Create the working folder for one reel and extract what the analysis steps need.

    python3 scripts/prepare_project.py /path/to/talking_head.mov [--project DIR] [--name NAME]
                                       [--graded /path/to/graded.mov] [--lut grade.cube]

Layout created inside the project folder:
    project.json        settings shared by every other script
    footage/            graded presenter video (when --lut is used)
    audio/              source audio (48 kHz) and, later, the cut + mastered program audio
    analysis/           16 kHz speech audio, transcript, cut list, face track
    matte/              presenter mattes (body, head) and clip mattes
    broll/              insert footage (generated, own, or licensed stock)
    logos/              logo PNGs on transparent background (white versions look best)
    assets/             look textures copied from the skill
    qa/                 still frames saved for checking
    render/             final renders (only when the user asks for one)
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SKILL_DIR, find_ffmpeg, nice_fps, probe, run, save_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video', help='original talking-head recording (with its audio)')
    ap.add_argument('--project', help='project folder (default: next to the video, <name>_reel)')
    ap.add_argument('--name', help='short name used for comps and files (default: video file name)')
    ap.add_argument('--graded', help='an already colour-graded version of the same recording (same length)')
    ap.add_argument('--lut', help='.cube LUT to grade the presenter with ffmpeg (writes a ProRes 422 HQ file)')
    a = ap.parse_args()

    src = os.path.abspath(a.video)
    if not os.path.exists(src):
        sys.exit('ERROR: video not found: ' + src)
    name = (a.name or os.path.splitext(os.path.basename(src))[0]).replace(' ', '_')
    proj = os.path.abspath(a.project or os.path.join(os.path.dirname(src), name + '_reel'))
    for sub in ('footage', 'audio', 'analysis', 'matte', 'broll', 'logos', 'assets', 'qa', 'render'):
        os.makedirs(os.path.join(proj, sub), exist_ok=True)
    ff = find_ffmpeg()
    info = probe(src, ff)
    if not info['w']:
        sys.exit('ERROR: no video stream in ' + src)
    if not info['audio']:
        sys.exit('ERROR: the recording has no audio track - the edit is driven by speech')

    presenter = src
    if a.graded:
        presenter = os.path.abspath(a.graded)
        g = probe(presenter, ff)
        if abs(g['dur'] - info['dur']) > 0.2:
            print('WARNING: graded file length %.2fs differs from the source %.2fs - cuts are computed on the source timeline'
                  % (g['dur'], info['dur']))
    elif a.lut:
        presenter = os.path.join(proj, 'footage', name + '_graded.mov')
        print('grading with LUT -> ' + presenter)
        lut = os.path.abspath(a.lut).replace("'", "\\'").replace(':', '\\:')
        run([ff, '-v', 'error', '-stats', '-y', '-i', src, '-an', '-vf',
             "format=rgb48le,lut3d=file='%s':interp=tetrahedral,format=yuv422p10le" % lut,
             '-c:v', 'prores_ks', '-profile:v', '3', presenter])

    print('extracting audio')
    run([ff, '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
         os.path.join(proj, 'analysis', 'audio16k.wav')])
    run([ff, '-v', 'error', '-y', '-i', src, '-vn', '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s24le',
         os.path.join(proj, 'audio', 'source_48k.wav')])
    shutil.copy(os.path.join(SKILL_DIR, 'assets', 'textures', 'halftone_1080x1920.png'), os.path.join(proj, 'assets'))

    pinfo = probe(presenter, ff)
    cfg = dict(name=name, project_dir=proj, source=src, presenter=presenter,
               src_w=pinfo['w'], src_h=pinfo['h'], src_fps=info['fps'], src_dur=info['dur'],
               fps=nice_fps(info['fps']), W=1080, H=1920)
    save_json(cfg, os.path.join(proj, 'project.json'))
    print('\nproject ready: ' + proj)
    print('  presenter %dx%d @ %.3f fps, %.2f s' % (pinfo['w'], pinfo['h'], info['fps'], info['dur']))
    if pinfo['w'] > pinfo['h'] and pinfo['h'] < 1920 * 0.75:
        print('  NOTE: horizontal source under 1440p - the 9:16 crop will be soft; 4K or vertical recordings work best.')


if __name__ == '__main__':
    main()
