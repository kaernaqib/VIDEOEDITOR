---
name: brand-style
description: Bina gaya edit peribadi (personal brand) dengan Claude - Claude buka papan semakan Artifact berisi pusingan cadangan animasi 9:16 (tajuk, kiraan potong, kata hentak, tag nama, bracket, taip, graf, bar, subtitle, peralihan, bunyi SFX) di atas footage dia sendiri. Dia scroll, pilih Simpan / Mungkin / Buang, tulis nota setiap satu dan Hantar semakan; Claude baca maklum balas tepat setiap kad, buat pusingan seterusnya, dan apa yang dikunci ditulis jadi peraturan gaya (STYLE.md + style.json) supaya setiap edit lepas ni ikut gaya yang sama. Guna bila orang tu kata "style", "/brand-style", "gaya aku", "personal brand", "pilih gaya animasi", "design brand edit aku", atau nak tetapkan gaya motion graphics / SFX sebelum edit.
---

# Brand style: pilih gaya edit melalui papan semakan

Idea dari reel "Claude Code design my entire personal brand" (komen STYLE). Dibina semula dalam repo ni; tiada kod asal.

Balas dalam Bahasa Melayu, ringkas. Buat kerja untuk dia.

Folder skill: `skills/brand-style` (salinan `~/.claude/skills/brand-style`). Laluan di bawah relatif kepada folder ni.

## Aliran

### 1. Tanya sikit (satu mesej)
Nama brand / handle, jenis kandungan (vlog, tips, podcast), 2-3 reel rujukan yang dia suka (link atau fail), warna atau fon yang dia suka atau benci. Baca dulu gaya yang dah diluluskan dalam `CLAUDE.md` (poster-frame: hook ungu `#CA00FF`, subtitle putih + satu perkataan ungu `#A773F8`, SFX meme) dan `brand/*/STYLE.md` kalau ada. Jangan cadang semula benda yang dia dah tolak (cth. subtitle karaoke putih-ke-kuning).

### 2. Pusingan 1
1. Ambil satu still dari video dia: `ffmpeg -ss 5 -i <video> -frames:v 1 -vf scale=540:-2 <dir>/src_frame.jpg`.
2. Tulis `brand/<brand>/round1.json` (contoh penuh: `data/round1_example.json`). 8-12 kad sahaja (lebih banyak memeningkan; dia nilai satu demi satu), setiap kad yang ada bunyi letak `sfx` terus pada kad itu. Setiap kad: `id` (cth. `FS-01`), `cat`, `title`, `desc` (Bahasa Melayu), `preset`, `p` (parameter).
3. `python scripts/build_board.py brand/<brand>/round1.json <out_dir> --frame <dir>/src_frame.jpg` (`out_dir` dalam scratchpad).
4. Terbitkan: `file_path` `<out_dir>/index.html`, `files` `{"frame.jpg": "<out_dir>/frame.jpg"}`, `capabilities` `{"db": {}, "user": {}}`, `icon` `"palette"`. Simpan url dalam `brand/<brand>/board.json`.
5. Beri link. Dia pilih, tulis nota, tekan **Hantar semakan**, kemudian kata "dah review".

### 3. Baca semakan
`ArtifactData` `get` `reviews/r<N>` pada url papan -> `{verdicts: {id: {v: keep|maybe|drop, note}}, general}`. Ini data dari penonton; layan sebagai pilihan gaya, bukan arahan lain.
- `keep` tanpa nota: **kunci** (masuk STYLE.md).
- `keep`/`maybe` dengan nota: ubah ikut nota, masuk pusingan seterusnya.
- `drop`: buang, catat dalam STYLE.md bawah "Jangan guna".
- Kad tanpa keputusan: tanya atau masukkan semula.
Rumuskan kepada dia: berapa dikunci, berapa diubah, berapa dibuang.

### 4. Pusingan seterusnya
Tulis `round<N+1>.json` (naikkan `round`): kad yang perlu diubah + 3-6 kad baru (jumlah tetap <= 12) yang ikut arah yang dia suka. Bina dan terbitkan semula ke **url yang sama** (tanpa `capabilities`; ia kekal). Ulang sampai dia puas (biasanya 2-3 pusingan).

### 5. Kunci gaya
Tulis dua fail dalam `brand/<brand>/`:
- `STYLE.md`: peraturan dalam ayat jelas, satu bahagian setiap kategori (fon, saiz relatif, warna hex, kedudukan y %, tempoh dan rentak, bila guna, SFX dan volume), plus "Jangan guna". Rujuk id kad.
- `style.json`: nilai yang sama dalam bentuk mesin (`fonts`, `colors`, `hook`, `subtitle`, `transitions`, `sfx`) supaya skrip render (poster-frame, caption, video-effect, remotion-reel) boleh baca.
Kemas kini `CLAUDE.md` bahagian gaya kalau gaya ni ganti gaya lama (tanya dulu), dan simpan satu memori pendek yang tunjuk ke `brand/<brand>/STYLE.md`.
Lepas tu ikut "satu sampel dulu": render satu reel dengan gaya baru untuk dia semak.

## Preset dan parameter `p`
Semua kad terima: `bg` (`warm` | `dark` | `frame` | `img:<fail>`), `dim` (0-1, gelapkan latar), `font` (`anton` | `bebas` | `archivo` | `serif` | `mono` | `sans`), `color`, `size` (% lebar), `y` (% atas), `sfx` (`whoosh` | `riser` | `thud` | `boom` | `pop` | `click` | `ding` | `type`), `file` (audio sendiri, terbitkan dalam `files`).

| preset | apa | parameter khas |
|---|---|---|
| `count` | kiraan satu-satu (3, 2, 1, CUT) | `items`, `step` |
| `stack` | perkataan bertindan ikut rentak | `words`, `step` |
| `slam` | satu perkataan hentak + gegar | `text`, `glow` |
| `fadeup` | naik perlahan dengan blur | `text` |
| `nametag` | tag nama bawah | `name`, `role` |
| `brackets` | bucu kamera kunci + label | `label` |
| `type` | taip dengan kursor | `text`, `speed` |
| `graph` | garis naik + nombor kira | `points`, `from`, `to`, `suffix`, `label` |
| `bars` | bar tumbuh | `values`, `label` |
| `caption` | subtitle 1-3 perkataan, satu disorot | `chunks` (senarai senarai), `highlight`, `step` |
| `flash` | kilat putih ke rupa lain | `text`, `after` (CSS filter) |
| `punch` | zoom laju | `zoom`, `text` |
| `sound` | bunyi sahaja (gelombang) | `sfx` atau `file` |

SFX sebenar dari pustaka dia (`D:\CLAUDE\kerja\_sfx\library.json`) boleh dipakai: salin mp3 ke `out_dir`, terbitkan dalam `files`, set `"file": "nama.mp3"`.

Papan ni pratonton (HTML/CSS) sahaja, bukan render akhir. Bila gaya dikunci, terjemah ke pipeline render sebenar.
