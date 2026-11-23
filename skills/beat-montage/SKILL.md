---
name: beat-montage
description: Montaj vlog 9:16 laju ikut beat (diluluskan 23 Nov 2026 pada reel 1 Berekeh) - footage tanpa orang bercakap (hiking, travel, event) dipotong tepat pada beat 120 BPM, 0.5-1 s satu shot, zoom / punch-in / flash putih pada drop / shot dipercepat, teks minimum (hook, drop, drop 2, penutup: Montserrat ExtraBold kuning + baris kecil putih), beat bebas hak cipta dihasilkan dengan kod (atau lagu sendiri 120 BPM), bunyi asal hanya untuk saat seronok (sorakan group photo). Python + ffmpeg, tiada app edit. Guna bila orang tu kata "montaj", "ikut beat", "laju", "beat sync", "vlog tanpa cakap", "/beat-montage", atau nak reel travel/hiking/event yang engaging dari banyak klip pendek.
---

# beat-montage

Gaya montaj yang dia luluskan pada reel 1 Berekeh ("Okay ni ngam"). Ia ganti gaya New Era untuk vlog tanpa orang bercakap, sebab dia kata New Era tak menarik untuk footage macam ni: tiada muzik, terlalu perlahan, grafik tak sesuai, shot gelap.

## Struktur (120 BPM, 60 s)

| Masa | Bahagian | Shot | Kesan |
|---|---|---|---|
| 0-8 | intro | 8 x 1 s | zoom perlahan; hook 2 baris (0.1-3.9 s) |
| 8-16 | build | 16 x 0.5 s | potong laju, snare roll + riser |
| 16-32 | drop 1 | 1 s (+2 x 0.5 s) | flash + punch-in pada 16 s, teks drop (16-18.8 s) |
| 32-40 | break | 4 x 2 s | zoom masuk / keluar, shot paling cantik |
| 40-56 | drop 2 | 1 s, atau stutter 8 x 0.5 s | flash, teks drop 2 (40-42 s) |
| 56-60 | outro | 4 s | zoom keluar, teks penutup |

Shot pertama = sekilas view terbaik (janji pada penonton), barulah cerita bermula.

## Cara guna

1. Salin footage ke `D:\CLAUDE\kerja\<projek>\footage\`, buat contact sheet: `PY scripts/contact_sheets.py FOOTAGE_DIR` (3 frame setiap klip, nombor #). Transkrip (faster-whisper) hanya untuk cari bunyi seronok.
2. Tengok sheet, buang klip rosak (0 s) dan orang yang dia minta buang (`exclude`).
3. Tulis brief reel (contoh `examples/berekeh_reels.json`): kolam klip untuk `intro`, `build`, `drop1`, `break`, `drop2`, `outro`, `texts` [[kecil, BESAR] x4], `loud` (klip yang bunyi asal dikekalkan), `drop2_rhythm: "stutter"`.
4. `PY scripts/auto_montage.py reels.json 02 OUTDIR` → `OUTDIR/plan.json` (setiap potongan jatuh tepat pada beat; jumlah mesti 60 s). Atau tulis plan sendiri (contoh `examples/berekeh_r01_plan.json`).
5. Muzik: `PY scripts/beat.py OUTDIR/beat.wav <variant 0-9>` (kunci + progression berbeza setiap reel). Kalau dia bagi lagu sendiri, potong ke 60 s pada 120 BPM dan letak sebagai `music`.
6. `PY scripts/montage.py OUTDIR/plan.json` → MP4 1080x1920, loudnorm -14 LUFS. Buat contact sheet 1 fps dan semak sebelum hantar.
7. Satu sampel dulu. Lepas lulus: copy ke `D:\Video\<projek>\`, muat naik preview 720p ke Agent Studio.

Plan keys untuk `montage.py`: `out`, `music`, `music_vol` (0.9), `footage`, `index` (senarai fail ikut nombor #), `shots` [{`c`, `s`, `d`, `fx` [zin|zout|punch|flash|fast], `vol`}], `texts` [{`t0`, `t1`, `small`, `big` (\n = baris baru), `y`}].

PY = `~/.claude/skills/video-effect/.venv/Scripts/python.exe`. Fon `D:\CLAUDE\kerja\_fonts\Montserrat-VF.ttf`.

## Lagu sebenar (NCS) - pilihan dia untuk post

Dia mahu lagu popular tanpa masalah hak cipta. Guna **NoCopyrightSounds** dari laman rasmi (bukan rip YouTube):
- Polisi ncs.io/usage-policy: percuma untuk pencipta bebas di YouTube, Facebook, Instagram, Snapchat, TikTok; Reels/TikTok/Shorts tak perlu kredit; boleh potong, tak boleh ubah lain; brand / iklan berbayar / tajaan perlu lesen.
- Muat turun: `https://ncs.io/api/download/<slug>` (slug dari halaman lagu, cth onandon, ht, skyhigh, mortals, invincible, feelgoodfunk). Simpan dalam `D:\CLAUDE\kerja\_music\ncs\`. Minta izin dia dulu sebelum muat turun lagu baru.
- Lagu trending sebenar (berhak cipta): jangan masukkan dalam video; cadangkan dia tambah sound dalam app IG/TikTok masa post.

Langkah:
1. `PY scripts/songinfo.py lagu.mp3 BPM` → fasa beat + calon drop (BPM dari halaman lagu NCS).
2. **Sahkan drop dengan mata**: lukis sampul frekuensi rendah (lowpass) seluruh lagu dengan tanda saat; drop sebenar = permulaan kick berdenyut selepas bahagian senyap/build. Pengesan boleh tersalah (Heroes Tonight: dikesan 52.5 s, sebenar 67.4 s; Feel Good Funk: 9.4 s riser, sebenar 17.6 s).
3. `PY scripts/retime.py plan.json lagu.mp3 BPM DROP plan_ncs.json` → semua tempoh x (beat lagu / 0.5 s), drop video (16 s) jatuh tepat pada drop lagu, potongan lagu jadi `music.wav`. Lagu 120-130 BPM paling sesuai (reel ~56-60 s); 101 BPM → 71 s; 88-90 BPM terlalu perlahan (82 s).
4. Render, kemudian semak gelombang audio output dengan garis pada 7.44/14.88/... s (masa bahagian x faktor) sebelum hantar.

Berekeh: Heroes Tonight 129 BPM (drop 22.3 / 67.4 / 156.7), Sky High 129 (46.3 / 191.0), Feel Good Funk 124 (17.6 / 46.2), Invincible 101 (70.3 / 145.2 / 204.0).

## Nota
- Epidemic Sound yang bersambung tiada lesen muat turun (FORBIDDEN). Jangan guna preview mp3 berkualiti rendah untuk post.
- Saya tak boleh dengar audio: semak beat dengan `showwavespic` / `showspectrumpic` (riser jangan lebih kuat dari kick).
- Klip landskap diletak atas latar kabur; klip potret di-crop penuh.
- Peraturan tetap: tiada B-roll stok untuk vlog peribadi; fail kerja dalam `D:\CLAUDE\kerja`, video siap sahaja dalam `D:\Video`.
