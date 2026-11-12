#!/usr/bin/env python3
"""Check an EDL against the schema and the house style before rendering.

    python3 scripts/validate_edl.py PROJECT_DIR/edl.json

Errors stop the render (broken structure, missing files, overlapping inserts). Warnings point at
style-rule breaks that the user usually catches in review: text too wide, two lines at the bottom,
a big word placed in the subtitle zone, long stretches without an insert, a fourth font, off-palette
colours. Fix them or consciously accept them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json  # noqa: E402

KINDS = {'full': ['clips'], 'frame': ['clips', 'rect'], 'band': ['clips'], 'vsplit': ['clips', 'tsplit'], 'logo_flash': ['slots'],
         'cards': ['cards'], 'bar': [], 'converge': ['logos'], 'number': [], 'solid': [], 'cutout': ['bgclip'], 'pframe': []}
TRANS = {'whip', 'whipL', 'zoom', 'zoomrot', 'bulge', 'cut', 'panels'}
FONTS = {'anton', 'serif', 'didot', 'sub'}
ANIMS = {'build', 'words', 'pop', 'soft'}
CHAR_W = {'anton': 0.41, 'serif': 0.47, 'didot': 0.45, 'sub': 0.44}     # average letter width / size, measured
CAPS_W = 1.25                                                           # capitals are wider (except Anton)


def main():
    path = sys.argv[1]
    edl = load_json(path)
    P = edl.get('project_dir') or os.path.dirname(os.path.abspath(path))
    W, H = edl.get('W', 1080), edl.get('H', 1920)
    accent = edl.get('accent', '#ED3B22').upper()
    palette = {accent, '#FFFFFF', '#161216', '#0B0B0B', '#000000'}
    err, warn = [], []
    cuts_p = os.path.join(P, (edl.get('presenter') or {}).get('cuts', 'analysis/cuts.json'))
    dur = None
    if os.path.exists(cuts_p):
        cuts = load_json(cuts_p)
        dur = sum(c['src_t1'] - c['src_t0'] for c in cuts)
    else:
        err.append('cut list not found: ' + cuts_p)

    def exists(rel):
        return os.path.exists(rel if os.path.isabs(rel) else os.path.join(P, rel))

    ins = sorted(edl.get('inserts', []), key=lambda i: i['t0'])
    ids = set()
    for k, I in enumerate(ins):
        tag = 'insert %s' % I.get('id')
        if I.get('id') in ids:
            err.append(tag + ': duplicate id')
        ids.add(I.get('id'))
        if I.get('kind') not in KINDS:
            err.append(tag + ': unknown kind %s' % I.get('kind'))
            continue
        for req in KINDS[I['kind']]:
            if not I.get(req):
                err.append(tag + ': needs "%s"' % req)
        if I['t1'] <= I['t0']:
            err.append(tag + ': t1 must be after t0')
        if I['t1'] - I['t0'] < 0.6:
            warn.append(tag + ': only %.2f s - inserts under ~0.6 s read as a glitch' % (I['t1'] - I['t0']))
        if dur and I['t1'] > dur + 0.02:
            err.append(tag + ': ends after the program (%.2f s)' % dur)
        if k and I['t0'] < ins[k - 1]['t1'] - 0.02:
            err.append(tag + ': overlaps %s' % ins[k - 1]['id'])
        if I.get('layout', 'full') not in ('full', 'split'):
            err.append(tag + ': layout must be full or split')
        if I.get('trans', 'whip') not in TRANS:
            err.append(tag + ': unknown transition %s' % I.get('trans'))
        if I['kind'] == 'vsplit' and len(I.get('clips') or []) < 2:
            err.append(tag + ': vsplit needs two clips')
        for c in (I.get('clips') or []) + ([I['bgclip']] if I.get('bgclip') else []):
            if not c.get('src') or not exists(c['src']):
                err.append(tag + ': clip missing %s' % c.get('src'))
            for mk in ('cutout_matte', 'color_figures_matte'):
                if c.get(mk) and not exists(c[mk]):
                    err.append(tag + ': %s missing %s' % (mk, c[mk]))
            if c.get('src', '').lower().endswith(('.jpg', '.jpeg', '.png')):
                warn.append(tag + ': still image %s - prefer moving footage (a photo needs a push or parallax at least)' % c['src'])
        for key in [s[0] for s in I.get('slots', [])] + list(I.get('logos', []) if I['kind'] == 'converge' else []) + \
                [c.get('logo') for c in I.get('cards', []) if c.get('logo')]:
            if key not in (edl.get('logos') or {}):
                err.append(tag + ': logo key "%s" not in "logos"' % key)
    prev = 0.0
    for I in ins:
        if I['t0'] - prev > 6.0:
            warn.append('presenter alone %.1f-%.1f s (%.1f s) - the style wants a visual change every ~2-4 s' % (prev, I['t0'], I['t0'] - prev))
        prev = I['t1']
    if dur and dur - prev > 6.0:
        warn.append('presenter alone at the end %.1f-%.1f s' % (prev, dur))

    texts = edl.get('text', [])
    for T in texts:
        tag = 'text "%s" @%.2f' % (T.get('text', '')[:24], T.get('t0', -1))
        if T.get('font') not in FONTS:
            err.append(tag + ': font must be anton, serif, didot or sub')
            continue
        if T.get('anim', 'pop') not in ANIMS:
            err.append(tag + ': unknown anim %s' % T.get('anim'))
        for req in ('text', 't0', 't1', 'size'):
            if req not in T:
                err.append(tag + ': needs %s' % req)
        if 'y' not in T and not T.get('behind'):
            err.append(tag + ': needs y')
        if T.get('t1', 0) <= T.get('t0', 0):
            err.append(tag + ': t1 must be after t0')
        lines = T.get('text', '').split('\n')
        if len([ln for ln in lines if ln.strip()]) > 2:
            warn.append(tag + ': more than two lines - split it into separate text items')
        longest = max(lines, key=len)
        caps = T['font'] != 'anton' and longest.isupper()
        est = CHAR_W[T['font']] * (CAPS_W if caps else 1) * T.get('size', 0) * len(longest)
        if est > 0.89 * W:
            warn.append(tag + ': ~%d px wide (> %d) - %s' % (est, 0.89 * W, 'the renderer will shrink it to fit' if T.get('fit', True) else
                                                             '"fit": false keeps it - check it is inside the frame'))
        if T.get('y', 0) >= 0.78 * H:
            warn.append(tag + ': text in the bottom fifth - the house style keeps all text between y 700 and 1350')
        col = T.get('color', '#FFFFFF').upper()
        if col not in palette:
            warn.append(tag + ': colour %s is off-palette (accent, white)' % col)
        if T['font'] == 'anton' and T.get('text', '') != T.get('text', '').upper():
            warn.append(tag + ': big Anton words are set in capitals')
    subs = sorted([T for T in texts if T.get('anim') == 'words'], key=lambda T: T['t0'])
    for a, b in zip(subs, subs[1:]):
        if a['t1'] > b['t0'] + 0.01 and abs(a.get('y', 0) - b.get('y', 0)) < 120:
            warn.append('subtitles overlap: "%s" and "%s" (only one line at a time)' % (a['text'][:20], b['text'][:20]))

    for e in err:
        print('ERROR  ' + e)
    for w in warn:
        print('warn   ' + w)
    print('\n%d inserts, %d text items, program %.2f s: %d error(s), %d warning(s)'
          % (len(ins), len(texts), dur or 0, len(err), len(warn)))
    sys.exit(1 if err else 0)


if __name__ == '__main__':
    main()
