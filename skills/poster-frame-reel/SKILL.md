---
name: poster-frame-reel
description: Reformat a talking-head / vlog / podcast clip into the "poster frame" 9:16 layout - a poster thumbnail (one still or a 2-3 frame collage) at the top fading to black, a 2-line hook headline (one line purple, one white, condensed bold) with a small pill label, the landscape video shrunk into a ~4:3 band in the middle, and 1-3 word subtitles below it with one word highlighted. Rendered with ffmpeg + libass + Pillow. Use when the user says "poster frame", "format macam podcast clip", "headline atas video bawah", "frame gradient", gives the gradient reference frame, or asks to make reels look like the reference podcast clips.
---

# Poster-frame reel

Satu susun atur tetap (diukur dari "gradient frame" rujukan orang tu, 1080x1920):

| Zon | y (px) | Isi |
|---|---|---|
| Poster | 0 - ~610 | Gambar poster, jelas di atas, pudar ke hitam antara y=300 hingga 470 |
| Headline | ~375 dan ~482 | 2 baris, Impact (huruf besar), satu baris ungu `#CA00FF`, satu putih, bayang lembut |
| Pill | ~582 | PILIHAN, default tiada (orang tu suruh buang untuk 1228). Hanya kalau diminta: `"pill": [...]` |
| Video | 608 - 1414 | Video 1080x806 (~4:3), dicrop sekeliling muka. Muka kecil sikit, bukan crop penuh 9:16 |
| Subtitle | ~1466 | Segoe UI Bold 66, 1-3 perkataan, Huruf Besar Setiap Perkataan, putih dengan satu perkataan ungu `#A773F8` dan glow ungu lembut (default `sub_mode: highlight`, ini yang orang tu pilih). `sub_mode: karaoke` (putih jadi kuning bila disebut) dah dicuba dan DITOLAK, jangan guna kecuali diminta |
| Bawah | 1414 - 1920 | Hitam (zon UI TikTok/IG) |

Semua nombor boleh diubah dalam `style` job (lihat `DEF` dalam skrip).

## Langkah

1. **Hook headline.** Tulis 2 baris pendek (maks ~20 aksara satu baris) yang buat orang nak tengok: soalan, larangan, atau kejutan. Contoh: "JANGAN PAKAI TOPI / MACAM NI MASA VLOG!". `accent_line` pilih baris mana yang ungu (0 atau 1). Tukar-tukar antara reel supaya feed tak nampak sama.
2. **Poster (SATU untuk semua reel dalam siri).** Orang tu nak poster umum gaya thumbnail YouTube: warna terang, kolaj 2-3 gambar dia sendiri di tempat cantik (gambar telefon biasanya paling elok), tajuk kuning bergradien dengan outline hitam tebal (cth. "DAY 1 DI MELBOURNE"). Poster tak perlu berkait dengan isi reel. Buat sekali dengan `scripts/make_poster.py poster.json`, kemudian semua job guna `"poster": {"image": "poster.jpg", "zoom": 1.0, "contrast": 1.0, "saturation": 1.0}`. Letak `focus` = kedudukan muka dalam gambar (x, y) dan `face_at` ~0.31-0.36 supaya muka berada di zon 0-320px, di atas headline. Ukur muka dengan grid sebelum teka. Semak dengan `--still`.
2b. **SFX / bunyi meme.** Letak di bahagian yang kelakar atau penting sahaja, 3-5 bunyi satu reel, jangan melampau. Bunyi tanpa suara (windows_error, ding, ba_dun_dun, record_scratch) boleh bertindih dengan percakapan. Bunyi bersuara (bruh, hehe_boi, lol, oh_my_god) letak di celah senyap atau hujung ayat. Volume 0.35-0.6, `dur` potong bunyi panjang. Pustaka: `D:\Video\_sfx\library.json` (79 bunyi, ada `tag`: fail, reaction, timeskip, emphasis, punchline, movement, glitch). Kalau pustaka hilang, bina semula dengan `scripts/build_sfx_library.py <folder video SFX> D:/Video/_sfx` (jadual potongan dalam `references/sfx_cuts.json`).
3. **Subtitle.** Beri `captions` (frasa yang dah dibetulkan ejaannya) dan, jika ada, `words` (masa setiap perkataan). Skrip pecahkan jadi 1-3 perkataan dan pilih perkataan paling bermakna untuk diwarnakan ungu (perkataan `keyword` diutamakan).
4. **Semak layout:** `python scripts/render_poster_reel.py job.json --still` hasilkan `layer.png` (poster + headline + pill). Baiki `focus`/`zoom` sampai muka nampak elok.
5. **Render SATU reel dulu** dan hantar untuk semakan. Jangan render yang lain sebelum orang tu kata OK.
6. Selepas OK: render reel lain (`--reuse-band` kalau cuma teks/poster yang berubah, jimat masa), copy ke `D:\Video\<projek>\`.

## Format job (JSON)

```json
{
  "out": "D:/Video/projek/reel_01_poster.mp4",
  "poster": {"tiles": [
      {"video": "SRC.MP4", "t": 114.5, "focus": [0.55, 0.36], "zoom": 1.1},
      {"image": "frame.jpg", "focus": [0.45, 0.36]}]},
  "headline": ["BARIS SATU", "BARIS DUA?!"],
  "accent_line": 0,
  "clips": [{"path": "SRC.MP4", "t0": 114.4, "t1": 116.6, "f": 0.55, "scale0": 1.0, "scale1": 1.04}],
  "audio": "audio_siap_mix.mp4",
  "sfx_dir": "D:/Video/_sfx",
  "sfx": [{"t": 5.5, "file": "meme/windows_error.wav", "vol": 0.55, "dur": 0.8}],
  "captions": [{"a": 2.25, "b": 3.21, "text": "topi ni kalau pakai", "keyword": null}],
  "words": [{"w": "topi", "s": 2.25, "e": 2.61}],
  "style": {"accent": "#CA00FF", "sub_accent": "#A773F8"}
}
```

- Satu video sahaja: guna `"video": "file.mp4", "t0": 0, "t1": 30, "f": 0.5` dan bukannya `clips`.
- `clips` boleh guna `src0/src1` (nombor frame) bersama `"edl_fps": 30`. Ini format `reel_edl.json` dari pipeline reel-editor.
- `f` = kedudukan muka pada paksi x (0 sampai 1). `scale0` hingga `scale1` = zoom (push-in kalau berbeza).
- `audio` tiada: video keluar tanpa bunyi. Biasanya guna audio yang dah dimix (preview_raw).

## Untuk projek 1228

`projects/1228/scripts/poster_job.py WORK NN OUT_DIR [--still|--reuse-band]` bina job dari `rNN/` (EDL, captions, words, audio preview_raw) dan `poster_hooks.json`: `_series` (poster umum, pill dengan `{n}`, folder SFX) dan setiap reel (headline, `sfx` ikut nama dalam pustaka). Poster umum: `D:\Video\1228\work\poster_melbourne.jpg`.

## Keperluan

ffmpeg dengan libass, Python + Pillow, fon Windows `impact.ttf`, `segoeui.ttf`, `segoeuib.ttf`, "Segoe UI" (untuk libass).
