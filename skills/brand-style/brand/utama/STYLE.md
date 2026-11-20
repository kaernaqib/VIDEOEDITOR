# Gaya Utama (dikunci 20 Nov 2026, selepas 2 pusingan)

Papan semakan: https://claude.ai/artifact/UBvTaFfTaMEPtfgyaft1oJ (semakan dalam db `reviews/r1`, `reviews/r2`).
Nilai mesin: `style.json` dalam folder ni.

Susunan rujukan: reel poster-frame 1080x1920, video di jalur tengah (y 608-1414). Ruang teks: atas (y 0-31%) dan bawah (y 74-100%). Jangan letak teks atas muka.

## Dikunci

### Skrin penuh / saat besar
- **FS-01 Kiraan potong**: "3, 2, 1, CUT" satu-satu, 0.5 s setiap satu. Instrument Serif italic, kuning `#f6d34a`, besar (~34% lebar) di tengah. Setiap item masuk dari 1.5x ke 1x (ease-out ~0.17 s). Bunyi `click` setiap item.
- **FR-01 Frasa bertindan**: frasa penting dipecah 2-3 baris (cth. MOMENT / TAK DAPAT / DILUPAKAN), setiap baris muncul ikut rentak (0.4 s), masuk dari 1.35x ke 1x. Anton huruf besar, kuning `#f6d34a`, ~13% lebar, di ruang atas (y ~6%). Bunyi `thud` setiap baris. Ganti "kata hentak satu perkataan" (BOOM).

### Muka
- **BR-01 Bracket muka**: 4 bucu putih (garis 2 px, ~12% lebar) kunci tepat pada kotak muka + 15% ruang, masuk dari luar dengan sedikit lantun (~0.35 s). Label mono putih "REC 00:00:08" di atas bucu kiri atas, berkelip 3x sesaat. Mesti ikut kedudukan muka sebenar (YuNet), bukan kedudukan tetap.

### Kata kunci
- **KW-01 Kata kunci kuning bawah**: satu perkataan (cth. SERIUS?), Anton kuning `#f6d34a` dengan glow kuning, ~15% lebar, di ruang bawah (y ~80%). Masuk 2.2x ke 1x dalam 0.16 s dengan gegar kecil, hilang selepas ~2 s. Bunyi `pop`.

### Peralihan
- **TR-01 Kilat ke hitam putih**: kilat putih ~0.12 s, shot jadi grayscale + contrast 1.2, satu perkataan putih. Bunyi `whoosh`.
- **TR-03 Kilat ke warna filem**: sama, tapi shot jadi sepia(0.85) + contrast 1.15, perkataan Instrument Serif italic putih. Bunyi `whoosh`. Guna untuk imbas kembali / momen sentimental; TR-01 untuk kejutan / "tapi...".
- **TR-02 Punch-in**: zoom laju 1x ke 1.25x dalam 0.15 s pada satu perkataan penting, kata kunci kuning muncul di bawah serentak. Bunyi `thud`. Maksimum 2-3 kali satu reel.

## Kadar guna (cadangan awal, ubah ikut maklum balas)
Satu reel 60-120 s: 1 kiraan atau frasa bertindan di saat paling besar, 2-4 kata kunci bawah, 1-2 kilat, 2-3 punch-in, bracket muka sekali di awal (hook).

## Jangan guna
- Kata hentak satu perkataan di tengah (FS-03 BOOM), frasa serif lembut (FR-02), frasa ditaip mono (FR-03).
- Graf naik dengan nombor (GB-01), tag nama bawah (TX-03).
- Kata kunci kuning di ATAS muka (TX-01).

## Belum pasti
- Subtitle ungu (SB-01) dan tajuk ungu (TX-05) ditolak dalam pusingan 1, tapi kad tu dipapar atas reel siap yang bersepah. Gaya poster-frame ungu dalam CLAUDE.md belum diubah sampai dia sahkan.
- Bracket kuning (BR-02) tak dipilih; guna putih.
