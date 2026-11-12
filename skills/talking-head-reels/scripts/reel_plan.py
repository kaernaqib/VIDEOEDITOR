"""Turn an EDL (references/edl-schema.md) into a fully resolved render plan.

Everything the renderer needs is computed here once: media sizes and durations, the presenter
pieces (pauses removed, fixed framing per piece), the presenter punch-in keys around inserts,
insert timing (adjacency, transition entry, split blocks), subtitle word timing and the text rules
(big words hold to the end of their shot, one line at the bottom; width limits are applied after measuring).
"""
import json
import os

from common import die, find_ffmpeg, load_json, probe

KNOWN_KINDS = ('full', 'frame', 'band', 'vsplit', 'logo_flash', 'cards', 'bar', 'converge', 'number', 'solid', 'cutout', 'pframe')
TD = 0.22                                                  # whip / zoom entry time


def resolve(P, rel):
    return rel if os.path.isabs(rel) else os.path.join(P, rel)


def build_plan(edl_path):
    edl = load_json(edl_path)
    P = edl.get('project_dir') or os.path.dirname(os.path.abspath(edl_path))
    cfg_path = os.path.join(P, 'project.json')
    cfg = load_json(cfg_path) if os.path.exists(cfg_path) else {}
    ff = find_ffmpeg()
    W, H = edl.get('W', 1080), edl.get('H', 1920)
    fps = float(edl.get('fps') or cfg.get('fps') or 25)
    name = edl.get('name') or cfg.get('name') or 'Reel'

    pr = dict(edl.get('presenter') or {})
    pr.setdefault('src', cfg.get('presenter'))
    pr.setdefault('cuts', 'analysis/cuts.json')
    pr.setdefault('faces', cfg.get('faces', 'analysis/faces.jsonl'))
    for k in ('matte_body', 'matte_head'):
        pr.setdefault(k, cfg.get(k, 'matte/presenter_%s.mov' % k.split('_')[1]))
    if not pr.get('src') or not os.path.exists(resolve(P, pr['src'])):
        die('presenter video not found: %s' % pr.get('src'))
    psrc = resolve(P, pr['src'])
    pinfo = probe(psrc, ff)
    sw, sh = pinfo['w'], pinfo['h']
    cuts = load_json(resolve(P, pr['cuts']))
    if cuts and 'src_f0' in cuts[0] and 'src_t0' not in cuts[0]:       # frame-based cut lists
        cuts = [dict(src_t0=c['src_f0'] / fps, src_t1=c['src_f1'] / fps, prog_t0=c['prog_f0'] / fps) for c in cuts]
    dur = round(sum(c['src_t1'] - c['src_t0'] for c in cuts), 4)

    fpath = resolve(P, pr['faces'])
    if os.path.exists(fpath):
        fl = [json.loads(l) for l in open(fpath) if l.strip()]
        xs = sorted(f['x'] for f in fl if 'x' in f)
        ys = sorted(f['y'] for f in fl if 'y' in f)
        GX, GY = xs[len(xs) // 2] * sw, ys[len(ys) // 2] * sh
    else:
        GX, GY = sw / 2, sh * 0.35
    fill = max(W / sw, H / sh)
    fill_half = max(W / sw, (H / 2) / sh)
    fr = dict(wide=dict(scale=1.0125, face_y=0.396), tight=dict(scale=1.30, face_y=0.406), half=dict(scale=1.24, face_y=0.344))
    for k, v in (pr.get('framing') or {}).items():
        fr.setdefault(k, {}).update(v)
    zoom = edl.get('zoom')
    if not zoom:
        zoom = [[c['prog_t0'], c['prog_t0'] + c['src_t1'] - c['src_t0'], 'wide' if i % 2 == 0 else 'tight'] for i, c in enumerate(cuts)]

    def zoom_at(t):
        for a, b, z in zoom:
            if a - 1e-6 <= t < b - 1e-6:
                return z
        return 'wide'

    def pieces(w, h, fixed=None):
        out = []
        for c in cuts:
            p0, p1 = c['prog_t0'], c['prog_t0'] + c['src_t1'] - c['src_t0']
            bounds = {round(p0 * fps), round(p1 * fps)}
            if not fixed:
                bounds |= {round(a * fps) for a, b, z in zoom if p0 + 1e-3 < a < p1 - 1e-3}
            bounds = sorted(bounds)
            for i in range(len(bounds) - 1):
                a, b = bounds[i] / fps, bounds[i + 1] / fps
                f = fixed or fr[zoom_at(a + 0.5 / fps)]
                s = (fill_half if fixed else fill) * f['scale']
                y0 = f['face_y'] * h
                ax = min(max(GX, w / 2 / s), sw - w / 2 / s)
                ay = min(max(GY, y0 / s), sh - (h - y0) / s)
                out.append(dict(t0=a, t1=b, off=c['src_t0'] - c['prog_t0'], s0=s, s1=s * 1.03, y0=y0, ax=ax, ay=ay))
        return out

    mattes = {}
    for k in ('matte_body', 'matte_head'):
        mp = resolve(P, pr[k])
        if os.path.exists(mp):
            mi = probe(mp, ff)
            mattes[k] = dict(src=mp, w=mi['w'], h=mi['h'], fps=mi['fps'] or fps, div=sw / float(mi['w']))

    inserts = sorted(edl.get('inserts', []), key=lambda i: i['t0'])
    for I in inserts:
        if I['kind'] not in KNOWN_KINDS:
            die('insert %s: unknown kind %s' % (I['id'], I['kind']))
        I.setdefault('layout', 'full')
        I.setdefault('trans', 'whip')
        I.setdefault('flash', None)
        for c in list(I.get('clips') or []) + ([I['bgclip']] if I.get('bgclip') else []):
            src = resolve(P, c['src'])
            if not os.path.exists(src):
                die('insert %s: clip not found: %s' % (I['id'], c['src']))
            inf = probe(src, ff)
            c.update(abs=src, w=inf['w'], h=inf['h'], srcdur=inf['dur'], fps=inf['fps'] or fps,
                     still=src.lower().endswith(('.jpg', '.jpeg', '.png')))
            for mk in ('cutout_matte', 'color_figures_matte'):
                if c.get(mk):
                    mpth = resolve(P, c[mk])
                    if not os.path.exists(mpth):
                        die('insert %s: matte not found: %s' % (I['id'], c[mk]))
                    mi = probe(mpth, ff)
                    c[mk + '_abs'], c[mk + '_w'], c[mk + '_h'], c[mk + '_fps'] = mpth, mi['w'], mi['h'], mi['fps'] or fps
    logos = {}
    for k, rel in (edl.get('logos') or {}).items():
        lp = resolve(P, rel)
        if os.path.exists(lp):
            li = probe(lp, ff)
            logos[k] = dict(src=lp, w=li['w'], h=li['h'])

    # ---- insert timing: entry/exit points, adjacency, transition entries
    n = len(inserts)
    for i, I in enumerate(inserts):
        I['vis'] = round((I['t1'] - I['t0']) * fps) / fps
        I['dur'] = I['vis'] + 0.5
        prevI = inserts[i - 1] if i else None
        nextI = inserts[i + 1] if i < n - 1 else None
        I['prevAdj'] = bool(prevI and abs(prevI['t1'] - I['t0']) < 0.02)
        I['nextAdj'] = bool(nextI and abs(nextI['t0'] - I['t1']) < 0.02)
        I['in'], I['out'] = I['t0'], I['t1']
        if I['layout'] == 'split':
            I['groupStart'] = not (I['prevAdj'] and prevI['layout'] == 'split')
            I['out'] = I['t1'] + (0.45 if I['nextAdj'] else 0)
            if not I['groupStart'] and I.get('flash') == 'invert':
                I['flash'] = None
    split_blocks = []
    for i, I in enumerate(inserts):
        if I['layout'] == 'split' and I['groupStart']:
            ge, gi = I['t1'], i + 1
            while gi < n and inserts[gi]['layout'] == 'split' and abs(inserts[gi]['t0'] - ge) < 0.02:
                ge = inserts[gi]['t1']
                gi += 1
            geAdj = gi < n and abs(inserts[gi]['t0'] - ge) < 0.02
            split_blocks.append(dict(t0=I['t0'], t1=ge + (0.45 if geAdj else 0), divider=[I['t0'] + 0.32, ge]))
            if I['prevAdj'] and i:
                inserts[i - 1]['out'] = max(inserts[i - 1]['out'], I['t0'] + 0.4)
    for i, I in enumerate(inserts):            # a split that follows a split: the previous one stays a moment underneath
        if I['layout'] == 'split' and not I['groupStart'] and i:
            inserts[i - 1]['out'] = max(inserts[i - 1]['out'], I['t0'] + 0.35)
    full = [I for I in inserts if I['layout'] != 'split']
    base_keys = []
    for q, I in enumerate(full):
        tr = I['trans']
        entry = TD if tr in ('whip', 'whipL', 'zoom', 'zoomrot') else (0.26 if tr == 'bulge' else 0.0)
        I['entry'] = entry
        prev = full[q - 1] if q else None
        adjacent = bool(prev and abs(prev['out'] - I['in']) < 0.02)
        if entry > 0 and adjacent:
            prev['out'] = I['in'] + entry + 0.02
        if not adjacent:
            base_keys += [(I['in'] - 0.18, 100.0), (I['in'], 122.0)]
        nxt = full[q + 1] if q < len(full) - 1 else None
        if (not nxt or nxt['in'] - I['out'] > 0.3) and not I.get('norelease'):
            base_keys += [(I['out'], 116.0), (I['out'] + 0.22, 100.0)]
    base_keys.sort()

    # ---- text rules
    texts = [dict(t) for t in edl.get('text', [])]
    pw_path = os.path.join(P, 'analysis', 'program_words.json')
    pwords = load_json(pw_path) if os.path.exists(pw_path) else []
    for T in texts:
        T.setdefault('color', '#FFFFFF')
        T.setdefault('anim', {'anton': 'build', 'sub': 'pop'}.get(T['font'], 'soft'))
        T.setdefault('x', W / 2)
        if T['anim'] == 'words' and not T.get('wt'):
            nw = len(T['text'].split())
            ws = [w['s'] for w in pwords if T['t0'] - 0.05 <= w['s'] < T['t1'] - 0.05]
            T['wt'] = [max(T['t0'], round(x, 3)) for x in ws] if len(ws) == nw else \
                [round(T['t0'] + (T['t1'] - 0.12 - T['t0']) * i / max(nw, 1), 3) for i in range(nw)]
        if T.get('behind') and 'y' not in T:
            T['y'] = round(fr[zoom_at(T['t0'] + 0.01)]['face_y'] * H - 0.09 * H)
        T['text'] = T['text'].replace('\r\n', '\n').replace('\r', '\n')
        T.setdefault('max_w', round(0.89 * W))                 # width limit, enforced on the measured letters
    iv = sorted((i['t0'], i['t1']) for i in inserts)

    def block_end(t):
        for a, b in iv:
            if a - 1e-3 <= t < b:
                return b
        nxt = [a for a, b in iv if a > t]
        return min(nxt) if nxt else dur
    big = [T for T in texts if T['font'] == 'anton']
    for T in big:
        if T.get('keep_t1'):
            continue
        be = block_end(T['t0'] + 0.01)
        nxt = [U['t0'] for U in big if U is not T and T['t0'] < U['t0'] < be and abs(U['y'] - T['y']) < 160 and abs(U['x'] - T['x']) < 600]
        T['t1'] = round(max(T['t1'], min([be] + nxt)), 3)
    bottom = sorted([T for T in texts if T['y'] >= 0.78 * H], key=lambda T: T['t0'])
    for a_, b_ in zip(bottom, bottom[1:]):
        if a_['t1'] > b_['t0']:
            a_['t1'] = b_['t0']
    accent = edl.get('accent', '#ED3B22')
    for T in texts:
        T['glow'] = T.get('glow', T['color'].upper() == accent.upper() and T['font'] == 'anton')
    texts = [T for T in texts if T['t1'] > T['t0'] + 0.01]

    look = dict(halftone='assets/halftone_1080x1920.png', halftone_opacity=24, vignette=42, grain=4)
    look.update(edl.get('look') or {})
    if look.get('halftone'):
        hp = resolve(P, look['halftone'])
        look['halftone'] = hp if os.path.exists(hp) else None
    audio = resolve(P, edl.get('audio') or cfg.get('audio') or 'audio/program_master.wav')
    if not os.path.exists(audio):
        die('program audio not found: %s' % audio)
    fonts = dict(dict(anton='Anton-Regular', serif='Didot-Bold', didot='Didot', sub='HelveticaNeue-Medium'), **(edl.get('fonts') or {}))
    return dict(W=W, H=H, fps=fps, dur=dur, name=name, P=P, presenter=dict(src=psrc, w=sw, h=sh, fps=pinfo['fps'] or fps),
                mattes=mattes, audio=audio, logos=logos, pieces=pieces(W, H), pieces_half=pieces(W, H // 2, fixed=fr['half']),
                inserts=inserts, split_blocks=split_blocks, base_keys=base_keys, text=texts, look=look, accent=accent,
                bw_black=edl.get('bw_black', '#0E0C0E'), bw_white=edl.get('bw_white', '#EDE6DE'), ui_bg=edl.get('ui_bg', '#161216'),
                fonts=fonts)
