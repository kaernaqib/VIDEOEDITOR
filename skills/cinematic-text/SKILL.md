---
name: cinematic-text
description: Gaya teks sinematik untuk reel 9:16 (rujukan omgadrian / Content College) - setiap perkataan muncul kabur ke tajam satu demi satu ikut masa sebutan, frasa kecil Playfair Display Italic di atas tajuk besar Anton kuning, baris kotak kuning (teks hitam) tersapu kiri ke kanan, tajuk duduk di belakang kepala, subtitle kecil EB Garamond kuning pucat berakhir "..", whip blur antara potongan dan kilat cahaya oren. Dirender dengan Python + ffmpeg + MediaPipe, tiada app edit. Guna bila orang tu kata "gaya omgadrian", "cinematic text", "teks kabur keluar satu-satu", "tajuk kuning besar dengan italic kecil", "/cinematic-text", atau pilih gaya omgadrian dalam Agent Studio.
---

# cinematic-text

Gaya teks dari dua reel rujukan omgadrian (Content College launch, "level up your content 2026"), diluluskan 23 Nov 2026 pada sampel reel 01 projek 1228.

## Rupa (diukur 10 fps dari rujukan)

| Elemen | Fon | Gaya |
|---|---|---|
| Tajuk besar | Anton (padanan; asal fon condensed berbayar jenis Druk) | kuning `#FFD21F`, HURUF BESAR, satu baris, lebar maks 960 px |
| Frasa kecil atas tajuk | Playfair Display Italic wght 600, 64 px | kuning, huruf kecil, perkataan muncul satu-satu |
| Baris kotak | Anton 62% saiz tajuk | teks hitam dalam kotak kuning, tersapu kiri→kanan 0.3 s |
| Subtitle | EB Garamond 500, 50 px | `#F3E3A0` + bayang gelap, y 1500 (paras dada), ayat tergantung berakhir ".." |

Animasi:
- **Masuk:** setiap perkataan kabur (radius 16) + pudar + skala 1.07 → tajam dalam 0.26 s, pada masa perkataan disebut.
- **Keluar:** seluruh blok kabur dan hilang dalam 0.22 s sebelum ayat seterusnya.
- **Belakang kepala:** teks ditutup oleh topeng orang (MediaPipe selfie segmenter). Kalau kepala tutup lebih 1/3 tajuk, tajuk duduk di depan supaya masih boleh dibaca.
- **Whip blur** pada potongan (±0.14 s, motion blur mendatar + anjakan) dengan whoosh.
- **Light leak** oren-merah dari kanan, 0.5 s, pada blok yang ada `leak`.

Fon dalam `D:\CLAUDE\kerja\_fonts\` (Anton-Regular.ttf, PlayfairDisplay-Italic-VF.ttf, EBGaramond-VF.ttf, dari github.com/google/fonts, OFL). Kalau tiada, muat turun semula dari situ.

## Cara guna

1. Dapatkan masa perkataan (job.json / transcript whisper reel tu).
2. Pilih 3-6 frasa penting satu reel minit: setiap blok = 1-4 perkataan kecil (italic) + 1-2 perkataan besar (+ kotak pilihan). Masa setiap perkataan = masa dia disebut. `out` = sebelum ayat seterusnya.
3. Tulis pelan JSON (contoh: `examples/1228_reel01_sample.json`):
   - `video`, `pieces` (julat saat sumber, dimain berturut), `t0` (masa pelan pada saat pertama)
   - `audio` (wav yang timeline-nya sama dengan `t0`; buang untuk guna bunyi video)
   - `video_width` 2160 (default, muka tak besar + latar kabur) atau 3413 (penuh skrin)
   - `video_top`, `title_top`: naikkan video kalau muka rapat ke kamera supaya tajuk tak hilang
   - `blocks`: `small` [[perkataan, t]], `big` [[PERKATAAN, t]], `box` [TEKS, t], `out`, `leak`
   - `subs`: [[a, b, "teks.."]], `whips`: [masa potongan]
4. Render: `PY scripts/cinematic_text.py plan.json` (PY = venv video-effect). ~15 s render untuk 1 s video 4K.
5. Semak contact sheet frame, kemudian hantar SATU sampel dulu (peraturan orang tu).

## Peraturan orang tu yang tetap terpakai
- Subtitle di paras dada, bukan tengah muka.
- Muka jangan besar sangat: default `video_width` 2160 dengan latar kabur.
- Fail kerja dalam `D:\CLAUDE\kerja\<projek>\`, video siap sahaja dalam `D:\Video\<projek>\`.
