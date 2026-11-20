#!/usr/bin/env python3
"""Bina papan semakan gaya (brand-style) dari fail pusingan JSON.

usage:
  python build_board.py <round.json> <out_dir> [--frame frame.jpg]

<round.json>: {"brand": "...", "round": 1, "intro": "...", "categories": [{"name","desc"}], "cards": [{"id","cat","title","desc","preset","p":{...}}]}
--frame: satu still dari video dia (cth. ffmpeg -ss 5 -i video.mp4 -frames:v 1 -vf scale=540:-2 frame.jpg). Disalin sebagai frame.jpg; kad dengan "bg": "frame" gunakannya.
Hasil: <out_dir>/index.html (+ frame.jpg). Terbitkan dengan files={"frame.jpg": "<out_dir>/frame.jpg"} dan capabilities={"db": {}, "user": {}}.
"""
import argparse, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, '..', 'templates', 'style_review.html')
PRESETS = {'count', 'stack', 'slam', 'fadeup', 'nametag', 'brackets', 'type', 'graph', 'bars', 'caption', 'flash', 'punch', 'sound'}

ap = argparse.ArgumentParser()
ap.add_argument('round_json')
ap.add_argument('out_dir')
ap.add_argument('--frame')
a = ap.parse_args()

data = json.load(open(a.round_json, encoding='utf-8'))
ids = set()
for c in data['cards']:
    if c['id'] in ids:
        sys.exit(f"id kad berulang: {c['id']}")
    ids.add(c['id'])
    if c.get('preset') not in PRESETS:
        sys.exit(f"{c['id']}: preset tak dikenali '{c.get('preset')}'. Pilih: {', '.join(sorted(PRESETS))}")
cat_names = [x['name'] for x in data.get('categories', [])]
for c in data['cards']:
    if cat_names and c['cat'] not in cat_names:
        sys.exit(f"{c['id']}: kategori '{c['cat']}' tiada dalam categories")

os.makedirs(a.out_dir, exist_ok=True)
if a.frame:
    shutil.copyfile(a.frame, os.path.join(a.out_dir, 'frame.jpg'))
    data['frame'] = 'frame.jpg'
html = open(TEMPLATE, encoding='utf-8').read()
title = f"{data['brand']} gaya"
js = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
html = html.replace('__TITLE__', title.replace('<', '&lt;')).replace('__DATA__', js)
open(os.path.join(a.out_dir, 'index.html'), 'w', encoding='utf-8', newline='\n').write(html)
print(f"{a.out_dir}/index.html: pusingan {data['round']}, {len(data['cards'])} kad")
