# VIDEOEDITOR: nota untuk Claude

Baca fail ni dulu setiap kali chat baru dibuka. Ia ganti "ingatan" chat lama, supaya tak perlu sambung chat yang dah sejuk dan reread ratusan ribu token.

## Projek ni apa

Claude skills untuk edit video pendek (Reels / TikTok / Shorts), bahasa Melayu.

- `skills/reel-editor`: edit Reel 9:16 terus dalam projek CapCut (talking-head, vlog, faceless; style pack; format education, do & don't, before/after, story). Bergantung pada `capcut-talking-head-edit`.
- `skills/capcut-talking-head-edit`: tulis fail timeline CapCut terus, tambah motion graphics.
- `skills/voiceover-glass-reel`: voiceover jadi reel dokumentari 16:9 dalam After Effects.
- `tools/weby-reel`: pipeline render ffmpeg + libass (`render.py`, `transcribe.py`, contoh job JSON).

Skill yang dipakai sebenarnya disalin ke `~/.claude/skills/`. Kalau ubah skill dalam repo ni, salin semula ke situ (atau sebaliknya) supaya dua-dua sama.

## Peraturan

- Jangan simpan API key dalam repo. Guna env var `PIXABAY_API_KEY`, `PEXELS_API_KEY`.
- Output render (`renders/`, `*.mp4`, `*.mov`) tak masuk git.
- Projek CapCut sendiri ada dalam folder CapCut kat PC, bukan dalam repo ni.

## Pilihan orang tu (wajib ikut)

- **Satu sampel dulu.** Lepas apa-apa perubahan gaya (framing, subtitle, B-roll, grade, susunan), render dan hantar SATU reel dulu (biasanya reel 01) untuk dia semak. Jangan render semua atau pasang ke CapCut sebelum dia kata OK. Sebab: jimat kredit.
- **Subtitle di bawah muka.** Letak subtitle di paras dada, kira-kira 76% ketinggian skrin (CapCut caption y = -0.52). Jangan letak di tengah sebab muka jadi tertutup.
- **Muka jangan besar sangat.** Untuk footage 16:9, jangan crop penuh ke 9:16. Guna bingkai yang lebih kecil (lebar ~2.0x kanvas) dengan canvas blur di atas dan bawah.
- **Tiada B-roll stok untuk vlog peribadi.** Guna footage dia sendiri sahaja.

## Simpan video

- Video yang dah siap edit: copy ke `D:\Video\<nama projek>\` (hard disk ADATA SSD, drive D:). Guna copy, bukan move, dan semak saiz fail sama selepas copy.
- Jangan simpan video dalam Google Drive (storan terhad) atau dalam repo.
- Kalau drive D: tak ada, berhenti dan beritahu orang tu. Jangan simpan di tempat lain tanpa tanya.

## Cara sambung kerja (jimat token)

1. Chat baru: buka dalam folder repo ni. Claude baca `CLAUDE.md`, kemudian nota terbaru dalam `.claude/handoffs/`.
2. Sebelum berhenti kerja (masa chat masih warm, dalam masa ~1 jam dari balasan terakhir): taip `/handoff`. Nota disimpan dalam `.claude/handoffs/` dan chat baru dibuka dari nota tu.
3. Kemas kini bahagian **Status semasa** di bawah kalau ada perubahan besar, kemudian commit dan push:
   `git add -A && git commit -m "Update status" && git push`
4. Kalau card "went cold" keluar, tekan **Start fresh**, jangan **Send anyway**.

## Status semasa

<!-- Kemas kini bahagian ni hujung setiap sesi kerja. Ringkas: apa siap, apa seterusnya. -->

- Projek CapCut aktif: **1228** (vlog Melbourne 29 minit) dipecah jadi 15 reel. Subtitle dan hook dah dibetulkan. v2 (16 Nov): framing muka dikecilkan (latar blur) dan B-roll dibuang; preview v2 dalam `reels_v2/`. Dah dipasang ke CapCut sebagai "1228 Reel 01 - ..." hingga "1228 Reel 15 - ...". Poin 1 permintaan orang tu masih belum diketahui.
- Skrip 1228 dalam `projects/1228/scripts/`. Folder kerja penuh dan preview dalam `D:\Video\1228\` (dipindah dari Temp, 17 Nov).
- Butiran penuh dan lokasi fail: `.claude/handoffs/2026-11-16-capcut-1228.md`.
- Nota handoff terkini: lihat fail paling baru dalam `.claude/handoffs/`.
