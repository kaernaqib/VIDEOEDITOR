#!/usr/bin/env python3
"""Sediakan halaman semakan video (gaya Frame.io) untuk diterbitkan sebagai Artifact.

usage:
  python build_review.py new  <review_dir> <video.mp4> --title "1228 Reel 01" [--note "draf pertama"]
  python build_review.py add  <review_dir> <video.mp4> [--note "betulkan komen v1"]
  python build_review.py html <review_dir>          (bina semula index.html sahaja)

<review_dir> mengandungi review.json (tajuk, url artifact, senarai versi), vN.mp4 dan index.html.
Video dimampatkan ke <= 14 MB (had fail Artifact 15 MB) pada 720p bila perlu.
Selepas itu terbitkan: Artifact publish file_path=<review_dir>/index.html, files={"vN.mp4": "<review_dir>/vN.mp4"},
capabilities={"db": {}, "user": {"scopes": ["profile"]}}.
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, '..', 'templates', 'review.html')
LIMIT = 14 * 1024 * 1024


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,codec_type,width,height',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), {})
    return float(j['format']['duration']), v.get('codec_name'), v.get('width', 0), v.get('height', 0)


def prep(src, dst):
    dur, codec, w, h = probe(src)
    if os.path.getsize(src) <= LIMIT and codec == 'h264':
        shutil.copyfile(src, dst)
        return
    kbps = int(LIMIT * 8 / dur / 1000 * 0.92) - 128
    if kbps < 300:
        sys.exit(f'Video terlalu panjang ({dur:.0f}s) untuk muat 14 MB. Potong dulu atau hantar bahagian.')
    vf = 'scale=-2:1280' if h >= w else 'scale=1280:-2'
    if max(w, h) <= 1280:
        vf = 'null'
    for p in (1, 2):
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-b:v', f'{kbps}k',
               '-pass', str(p), '-passlogfile', dst + '.log']
        cmd += ['-an', '-f', 'mp4', os.devnull] if p == 1 else ['-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', dst]
        subprocess.run(cmd, check=True)
    for f in os.listdir(os.path.dirname(dst) or '.'):
        if f.startswith(os.path.basename(dst) + '.log'):
            os.remove(os.path.join(os.path.dirname(dst), f))
    if os.path.getsize(dst) > 15 * 1024 * 1024:
        sys.exit(f'{dst} masih melebihi 15 MB.')


def write_html(d, state):
    tpl = open(TEMPLATE, encoding='utf-8').read()
    data = {'title': state['title'], 'versions': state['versions']}
    js = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    html = tpl.replace('__TITLE__', state['title'].replace('<', '&lt;')).replace('__DATA__', js)
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8', newline='\n').write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['new', 'add', 'html'])
    ap.add_argument('dir')
    ap.add_argument('video', nargs='?')
    ap.add_argument('--title')
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    sp = os.path.join(a.dir, 'review.json')
    state = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {'title': a.title or 'Semakan video', 'url': None, 'versions': []}
    if a.cmd == 'new' and state['versions']:
        sys.exit('review.json dah ada versi. Guna "add" untuk versi baru.')
    if a.title:
        state['title'] = a.title
    if a.cmd in ('new', 'add'):
        if not a.video:
            sys.exit('Beri laluan video.')
        n = len(state['versions']) + 1
        name = f'v{n}.mp4'
        prep(a.video, os.path.join(a.dir, name))
        state['versions'].append({'v': n, 'file': name, 'note': a.note, 'source': os.path.abspath(a.video)})
        print(f'{name}: {os.path.getsize(os.path.join(a.dir, name)) / 1048576:.1f} MB')
    write_html(a.dir, state)
    json.dump(state, open(sp, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('index.html sedia. Versi:', ', '.join('v%d' % v['v'] for v in state['versions']))


if __name__ == '__main__':
    main()
