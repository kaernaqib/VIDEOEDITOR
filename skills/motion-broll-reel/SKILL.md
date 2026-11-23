---
name: motion-broll-reel
description: Gaya reel promo / pengumuman "New Era" (rujukan 5 reel talking-head NEW ERA 28HB) - caption 2 tingkat di paras dada (baris kecil putih keluar perkataan demi perkataan + kata kunci besar kuning bercahaya ditaip huruf demi huruf dalam kotak garis, atau hijau limau tanpa kotak untuk tema merah), icon 3D pop-up terbang ke sebelah kepala bila benda tu disebut, cincin putih keliling muka, dan B-roll motion graphics penuh skrin yang dipilih ikut skrip (kad tajuk + pill tarikh, pill "bukan setakat" dengan potong garis, graf / candlestick neon, checklist bernombor, timeline, rangkaian nod, icon hero bawah lampu sorot) dengan peralihan flash putih atau swipe merah, SFX whoosh/pop automatik, kad jenama penutup. Dirender dengan Python + ffmpeg, tiada app edit. Guna bila orang tu kata "gaya New Era", "macam reel Fira", "motion broll", "b-roll ikut skrip", "pop up icon", "caption kotak kuning", "/motion-broll-reel", atau nak reel launch/event/promo/edukasi talking-head dengan grafik.
---

# motion-broll-reel

Gaya dari 5 reel rujukan dalam `D:\NEW ERA 28HB\` (CONTENT 1-5, promo event trading). Analisis frame (2 fps) dan transkrip dalam `D:\CLAUDE\kerja\_ref\newera\`.

## Rupa

Dua tema, pilih satu setiap reel (`"theme"`):

| | `gold` (CONTENT 2, 3, 4) | `red` (CONTENT 1, 5) |
|---|---|---|
| Caption kecil | Montserrat 500, 40 px, putih + bayang | Inter 500, 40 px, putih |
| Kata kunci besar | Montserrat 800 ~88 px kuning `#FFE000` + cahaya, **dalam kotak garis bulat** + sengkang kuning kiri kanan baris kecil | Inter Tight 700 ~124 px hijau limau `#D4FF3A`, rapat, tiada kotak |
| B-roll | latar hitam, cahaya oren di bawah, bintang berkelip, label jarak lebar "✦ BUKAN SETAKAT" | latar kelabu gelap, lampu sorot atas, bara merah naik, tajuk merah bercahaya |
| Icon 3D | diwarna emas-krim + cahaya kuning | kaca hitam + tepi merah neon |
| Peralihan | flash putih (bloom) | swipe pepenjuru merah |

Animasi:
- **Baris kecil** keluar perkataan demi perkataan ikut masa sebutan (pudar + naik 10 px, 0.14 s).
- **Kotak** (gold) muncul kosong dulu bersama baris kecil, kemudian **kata kunci ditaip huruf demi huruf** (≤0.22 s satu perkataan) dengan pop kecil.
- **Icon** terbang dari bawah sambil berpusing ke sebelah kepala, lajak sikit, terapung perlahan, kemudian hilang mengecil. Pop SFX.
- **Cincin muka:** bulatan putih dilukis 0→360° keliling muka (hanya muka besar, bukan orang lalu).
- **B-roll penuh skrin** menggantikan talking-head sepenuhnya (suara terus jalan). Elemen masuk kabur→tajam + naik. Subtitle bawah: perkataan jadi tebal putih bila disebut, `*kata*` = warna aksen.

## Template B-roll (`scenes[].type`) dan bila guna (B-roll ikut skrip)

Baca skrip penuh, cari ayat yang ada idea boleh dilukis, dan tukar 25-40% masa reel jadi B-roll (rujukan: 2-3 babak setiap 30-40 s, 2-6 s satu babak). Selebihnya talking-head dengan caption + icon.

| Bila skrip sebut... | `type` | Medan |
|---|---|---|
| nama event / produk / "nama dia X" / tarikh launch / reveal | `title` | `pill` [teks, t], `pre`, `title`, `post` ([teks, t]) |
| "bukan setakat A, B... tapi C" | `pills` | `items` [[teks, t]], `strike` t (garis potong + pudar bila sebut "tapi") |
| market, trend, naik/turun, data, plan, structure | `chart` | `style` card / candles, `draw_t`, `line_t`, `trend` up/down, `items` pill, `pre`, `title` |
| langkah, "dari A, B sampai lah C", senarai cara | `checklist` | `title`, `items` [[teks, t]] (tick ~0.35 s lepas) |
| sejarah, "dari zaman", bertahun, senarai benda yang dah buat | `timeline` | `items` [[tajuk, sub, t]] |
| connect, ekosistem, komuniti + tools + education | `network` | `center` [label, icon, t], `nodes` [[label, icon, t]] (≤5) |
| award, keputusan, satu benda besar / nombor penting | `hero` | `icon` [nama, t], `pill` [teks], `word` [teks, t] |
| penutup jenama | `endcard` (di akar pelan) | `text`, `sub`, `dur` |

Semua babak ada: `t`, `out`, `label` (pilihan), `subs` [[a, b, "teks *aksen*"]], `stamp` [TEKS, t] (cop merah condong, cth "SENDIRI"), `in` / `out_trans` (flash, swipe, blur, none).

Icon ikut kata: `scripts/icon_map.json` (Melayu + Inggeris → nama icon). Icon dalam `D:\CLAUDE\kerja\_icons\fluent3d\` (Microsoft Fluent Emoji 3D, MIT, 68 icon; tambah lagi dari github.com/microsoft/fluentui-emoji `assets/<Nama>/3D/<nama>_3d.png`). Satu icon setiap 4-6 s paling banyak, hanya pada kata yang boleh dilihat (tarikh → kalendar, link → rantai, komuniti → orang, award → trofi).

## Cara guna

1. Dapatkan masa perkataan (job.json `words` reel tu, atau transkrip faster-whisper, lihat skill `caption`).
2. Draf: `PY scripts/suggest.py words.json --video SRC --t0 A --t1 B --theme gold --out plan.json`. Ia pecah ayat, pilih kata kunci, cadang icon dan senarai `_scene_ideas`. **Draf sahaja**: Claude baca skrip, betulkan kata kunci (2-3 perkataan maksimum, perkataan yang paling penting dalam ayat, boleh tukar ke Inggeris pendek macam rujukan: "Something New", "Face to Face", "Dah Open"), buang icon yang tak masuk akal, dan tulis `scenes` dari `_scene_ideas`.
3. Medan pelan (contoh penuh: `examples/1228_reel01_sample.json`):
   - `out`, `video`, `audio` (wav sama timeline dengan `t0`; buang untuk guna bunyi video), `t0`, `pieces` [[saat sumber a, b]]
   - `theme` gold / red, `theme_overrides` (cth `{"accent": [255,255,255]}` untuk warna brand)
   - `video_width` 2160 (footage 16:9, muka tak besar + latar kabur), `video_top`; footage menegak diisi penuh skrin automatik
   - `caption_y` (default 1430 untuk 16:9, 1060 untuk menegak = paras dada bawah muka)
   - `captions` [{`small` [[kata, t]], `big` [[Kata, t]], `out`, `italic`, `box`}]
   - `icons` [{`icon`, `t`, `out`, `side` left/right, `size` 230, `tint` gold/red/none, `pos` [x, y] pilihan}]. Icon ikut muka secara automatik; untuk shot pemandangan atau ramai orang (muka kecil), tetapkan `pos` (cth kanan [820, 560], kiri [260, 560])
   - Vlog tanpa orang bercakap (banyak klip pendek): bina dulu satu video 9:16 dari senarai shot (`[[klip, mula, tempoh]]`, potret cover-crop, landskap atas latar kabur), kemudian beri video tu sebagai `video`; caption jadi teks cerita (baris kecil + kata kunci), audio = muzik + bunyi asal perlahan
   - `rings` [{`t`, `out`}]
   - `scenes` [...], `endcard` {`text`, `sub`, `dur`}
   - `sfx` [[fail dalam D:\CLAUDE\kerja\_sfx, t, vol]]; `auto_sfx` true (whoosh peralihan, pop icon, tick kata kunci)
4. Semak frame: `PY scripts/motion_reel.py plan.json --still 12 25 40` (PNG sebelah output). Ralat ffmpeg "Error muxing" dalam mod still tak apa.
5. Render: `PY scripts/motion_reel.py plan.json` (~6-8 s render untuk 1 s video dari sumber 4K). PY = `~/.claude/skills/video-effect/.venv/Scripts/python.exe`.
6. Hantar SATU sampel dulu.

Fon dalam `D:\CLAUDE\kerja\_fonts\`: Montserrat-VF, Montserrat-Italic-VF, Inter-VF, InterTight-VF (+ Playfair untuk kad jenama). Semua dari github.com/google/fonts (OFL).

## Peraturan orang tu yang tetap terpakai
- Caption di paras dada, jangan tutup muka.
- Footage 16:9: muka jangan besar, `video_width` 2160 dengan latar kabur.
- Vlog peribadi: tiada B-roll stok. B-roll dalam gaya ni ialah motion graphics (dibenarkan).
- Fail kerja dalam `D:\CLAUDE\kerja\<projek>\`, video siap sahaja dalam `D:\Video\<projek>\`.
