---
name: caption
description: Caption reel gaya "word behind head" - satu perkataan besar (Anton, putih, huruf besar) duduk DI BELAKANG kepala orang dalam video (orang di-cut-out dengan rembg birefnet-portrait dan diletak di atasnya), perkataan lain timbul sebagai caption kecil 1-3 perkataan di depan (Inter Bold, bayang lembut), setiap perkataan muncul tepat pada masa disebut (faster-whisper + snap ke waveform). Tiada app edit; dirender dengan Python + ffmpeg. Juga cara bina gaya caption sendiri (rujukan reel, 2 fon, warna aksen, kedalaman, SFX, nota pada frame). Guna bila orang tu kata "caption", "/caption", "word behind head", "perkataan belakang kepala", "text behind me", "caption macam viashaan", atau nak caption 3D / berlapis pada video talking-head menegak.
---

# Caption: perkataan di belakang kepala

Sumber teknik: nota Shaan Johari (@viashaan), "How I edited my captions reel with AI". Ditulis semula di sini sebagai skill yang boleh dijalankan.

## Idea teras

Setiap frame ialah tindanan lapisan, belakang ke depan:

1. frame asal (atau bilik baru, lihat "Tahap lanjut")
2. **perkataan besar** (kata kunci ayat)
3. **orang, di-cut-out** (mask alpha lembut) - sebab ini perkataan nampak di belakang kepala
4. **caption kecil** di depan

Masa caption mesti tepat pada suara. Caption yang lewat 3 frame pun terasa "pelik" walaupun penonton tak tahu kenapa.

## Apa yang orang tu perlu bagi

- Klip talking-head **menegak**, sebaiknya 5-10 saat untuk kali pertama (skrip boleh buat lebih panjang, cuma cut-out lebih lama), dengan **ruang kosong di atas kepala**. Cahaya pada muka dan rambut bantu cut-out.
- Perkataan mana nak letak di belakang kepala, atau suruh Claude pilih (pilih perkataan yang "bawa" ayat: nombor, nama benda yang dibincang).
- Nama jenama / produk yang disebut, untuk ejaan betul.

## Langkah

Cakap dengan orang tu dalam bahasa biasa. Jangan tunjuk kod melainkan diminta.

1. **Folder kerja.** Satu folder untuk setiap klip, cth `D:\CLAUDE\kerja\<projek>\caption\` (jangan dalam `D:\Video`, itu untuk video siap sahaja). Semua (venv, model, fon) dipasang dalam folder ini sahaja, jangan ubah apa-apa lain dalam PC.
2. **Setup** (sekali satu folder, atau guna semula venv yang sama):
   `powershell -ExecutionPolicy Bypass -File <skill>/scripts/setup.ps1 -Dir <folder>`
   Pasang venv + faster-whisper + rembg (CPU) + Pillow + numpy, dan fon Anton + Inter dari Google Fonts. **Beritahu dulu** sebelum model dimuat turun: cut-out ~1 GB, whisper ~0.5 GB, boleh ambil sampai 30 minit kalau internet perlahan. Perlu ~3 GB ruang. Jalankan di latar belakang dan bagi update.
3. **Transkrip:**
   `.venv\Scripts\python <skill>/scripts/word_behind_head.py transcribe klip.mp4 --out words.json --names "Shopee,CapCut" [--lang ms]`
   - Audio diekstrak 16 kHz mono, dimuat ke array numpy, dan **array** itu diberi pada faster-whisper (versi baru crash kalau beri path fail).
   - `word_timestamps=True`, **tiada initial prompt** (prompt boleh buat whisper tertinggal perkataan).
   - Setiap mula perkataan dialih ke titik audio mula naik (whisper biasanya awal ~0.1 s).
   - Skrip cetak semua perkataan dalam satu baris, perkataan meragukan ditanda `[...?]`. **Tunjuk pada orang tu, tanda frasa yang tak masuk akal, dan tunggu OK** sebelum teruskan. Betulkan ejaan terus dalam `words.json`; perkataan yang dibetulkan kekalkan masa perkataan asal.
4. **Job JSON** (contoh di bawah). `big` = indeks atau teks perkataan besar.
5. **Semak layout dulu (murah):** `... render job.json --still` buat cut-out 2 frame sahaja dan simpan satu PNG. Tunjuk PNG.
6. **Render penuh:** `... render job.json`. Cut-out hanya dibuat dari frame perkataan besar disebut hingga habis, beberapa saat satu frame di CPU, jadi **beritahu anggaran masa sebelum mula**. Mask disimpan dalam `work/masks/` dan diguna semula, jadi render semula (tukar fon, warna, kedudukan) cepat. `--force-masks` untuk buat semula.
7. **Output:** MP4 H.264 saiz dan fps sama dengan asal, warna dikekalkan (matrix warna video asal dipakai masa tukar frame ke gambar dan balik), audio asal (+ SFX kalau ada), dan PNG satu frame yang tunjuk perkataan besar. Beritahu lokasi kedua-dua fail.
8. **Tanya apa nak ubah:** perkataan, saiz/kedudukan, fon, warna, gaya caption. Ubah HANYA yang diminta, render semula, PNG baru. Kalau orang tu suruh alih perkataan, ikut walaupun kepala jadi kurang tutup (guna `style.big_y`), dan caption kekal di atasnya.
9. Siap: copy ke `D:\Video\<projek>\` (copy, bukan move; semak saiz sama). Kalau D: tiada, berhenti dan tanya.

**Satu sampel dulu:** kalau buat banyak klip, siapkan SATU dan tunggu OK sebelum yang lain.

## Peraturan layout (dalam skrip)

| Elemen | Peraturan |
|---|---|
| Perkataan besar | Anton putih, huruf besar, lebar ~85% frame (tak pernah lebih lebar dari frame) |
| Kedudukan | Cari atas kepala dari mask pada frame perkataan disebut, dalam **40% tengah** frame sahaja (tangan diangkat tak dikira). Kepala tutup ~**60%** tinggi huruf (atas kepala sampai lebih sikit separuh huruf). Kemudian pastikan kepala tutup **≥15%** piksel huruf; kalau kurang (hood tajam, topi), turunkan perkataan sampai cukup tapi masih boleh dibaca. Kekal di situ selepas itu |
| Animasi | Bila disebut: pop 80% → ~105% → 100% dalam 6 frame |
| Caption | Inter Bold, saiz fon ~7% lebar frame, putih, bayang gelap lembut, maks 3 perkataan satu kumpulan, pecah pada jeda/tanda baca semula jadi, kumpulan di tengah, setiap perkataan muncul pada masa sendiri, kumpulan kekal sampai kumpulan seterusnya mula |
| Zon caption | Di atas perkataan besar, tak pernah bertindih. Antara **15% dan 65%** tinggi frame (1/3 bawah ditutup butang dan caption Instagram; elak juga butang di kanan). Kalau kepala rapat ke atas frame dan tiada ruang di atas perkataan besar, caption turun ke paras dada (`cap_fallback_y`, default 0.62) |
| Perkataan besar | Tak dicaption dua kali |

Nota pilihan orang tu: default dia untuk subtitle ialah di bawah muka (paras dada). Dalam gaya ini caption duduk **di atas kepala**, jadi muka tetap tak tertutup. Kalau dia nak caption bawah, set `cap_min_y`/`cap_max_y` sendiri, tapi jangan masuk 1/3 bawah.

## Format job

```json
{
  "video": "klip.mp4",
  "out": "out/klip_caption.mp4",
  "work": "work",
  "words": "words.json",
  "big": "RM10k",
  "big_text": null,
  "accent_words": [6],
  "sfx_dir": "D:/CLAUDE/kerja/_sfx",
  "sfx": [{"t": 1.70, "file": "whoosh.wav", "vol": 0.25, "dur": 0.6}],
  "style": {
    "big_font": ["fonts/Anton-Regular.ttf"],
    "cap_font": ["fonts/Inter-Variable.ttf"],
    "big_color": "#FFFFFF", "big_width": 0.85,
    "head_overlap": 0.60, "min_cover": 0.15, "big_y": null,
    "pop_frames": 6, "pop_from": 0.80, "pop_overshoot": 0.05,
    "cap_color": "#FFFFFF", "cap_accent": "#FFD400", "cap_size": 0.07,
    "cap_max_words": 3, "cap_min_y": 0.15, "cap_max_y": 0.65, "cap_fallback_y": 0.62
  }
}
```

- `big`: indeks dalam `words` atau teks perkataan (tanpa tanda baca, tak kisah huruf besar/kecil). `big_text` untuk paparan lain (cth "10K").
- `accent_words`: indeks perkataan caption yang guna `cap_accent`. Satu perkataan sahaja satu ayat.
- `sfx`: bunyi kecil (tick, whoosh) pada perkataan yang bergerak, vol 0.2-0.35, di bawah suara. Pustaka orang tu: `D:\CLAUDE\kerja\_sfx\library.json`.
- `layout.json` dalam `work/` rekod kedudukan yang dipilih (big_y, cap_y, kumpulan caption) untuk semakan.

## Bina gaya caption sendiri

Satu trik ini cuma asas. Gaya sendiri ambil beberapa pusingan nota (Shaan ambil 5 pusingan). Cara kerja:

1. **Mula dari reel yang disukai.** Orang tu simpan 3-5 reel dengan caption yang dia suka (screen record, letak dalam folder). Pecahkan setiap satu: fon, saiz, cara perkataan masuk dan keluar, kedudukan, apa yang bergerak. Pilih bahagian terbaik dari setiap satu dan cuba pada klip dia.
2. **Dua fon, bukan sepuluh.** Satu fon bersih untuk kebanyakan perkataan, satu fon tebal/ekspresif untuk perkataan penting. Kontras itu buat kebanyakan kerja.
3. **Warna ada makna.** Kebanyakan perkataan satu warna. Warna aksen untuk satu perkataan satu ayat yang nak diingat.
4. **Setiap perkataan jatuh pada suara.** Semak mula setiap perkataan dengan waveform, kemudian tonton dengan bunyi.
5. **Beri kedalaman.** Sebahagian perkataan di belakang orang, sebahagian di depan, dan kamera bergerak sikit (push-in perlahan).
6. **Setiap gerakan ada bunyi.** Tick atau whoosh ringan pada perkataan yang bergerak; perlahan, di bawah suara.
7. **Jangan halang UI Instagram.** Teks keluar dari 1/3 bawah dan jauh dari butang di kanan.
8. **Nota pada frame.** Orang tu tonton setiap versi dan beri nota tepat pada saat itu, macam pada editor: "perkataan ni masuk lewat", "besarkan yang ni dan letak belakang kepala". Ubah ikut nota sahaja.
9. **Tulis apa yang dia suka.** Bila sesuatu menjadi, simpan sebagai peraturan (dalam `CLAUDE.md` repo ini, bahagian gaya, atau dalam skill ini) supaya gaya bertambah setiap video, bukan mula dari kosong.

## Tahap lanjut (reel penuh Shaan)

Reel asal guna lebih banyak alat; buat hanya kalau orang tu minta:

- **Bilik baru:** Beeble (berbayar) bina semula shot dalam bilik lain berdasarkan gambar rujukan, dan relight orang supaya padan.
- **Suara bersih:** Adobe Podcast (Enhance Speech).
- **Kamera maya 3D:** lapisan (bilik, perkataan belakang, orang, perkataan depan) disusun dalam ruang 3D dan kamera bergerak melaluinya. Paling senang dibuat dalam `tools/remotion-reel` (Remotion, React): letak setiap lapisan sebagai elemen dengan `transform: translateZ()` + `perspective`, guna mask PNG dari `work/masks/` untuk lapisan orang.
- **Sound design padat:** setiap bunyi = sesuatu yang berlaku di skrin, diletak pada frame-nya, dimix di bawah suara dan muzik (reel asal ada 153 SFX).
- **Storyboard dulu:** satu still satu baris skrip, kemudian render cut pertama, kemudian pusingan nota.

## Keperluan

Whisper dan cut-out perlu RAM bebas ~3 GB. Kalau keluar ralat `mkl_malloc` / "failed to allocate memory", tunggu render lain (Remotion, CapCut) habis atau tutup tab Chrome, kemudian cuba semula.

ffmpeg/ffprobe dalam PATH, Python 3.10+ dengan faster-whisper, rembg[cpu], Pillow, numpy (setup.ps1 pasang semua dalam venv folder kerja). Fon Anton + Inter (fallback Windows: impact.ttf, segoeuib.ttf).
