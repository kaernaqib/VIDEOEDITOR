# VIDEOEDITOR: nota untuk Claude

Baca fail ni dulu setiap kali chat baru dibuka. Ia ganti "ingatan" chat lama, supaya tak perlu sambung chat yang dah sejuk dan reread ratusan ribu token.

## Projek ni apa

Claude skills untuk edit video pendek (Reels / TikTok / Shorts), bahasa Melayu.

- `skills/reel-editor`: edit Reel 9:16 terus dalam projek CapCut (talking-head, vlog, faceless; style pack; format education, do & don't, before/after, story). Bergantung pada `capcut-talking-head-edit`.
- `skills/capcut-talking-head-edit`: tulis fail timeline CapCut terus, tambah motion graphics.
- `skills/voiceover-glass-reel`: voiceover jadi reel dokumentari 16:9 dalam After Effects.
- `skills/caption`: caption "word behind head" (perkataan besar di belakang kepala via cut-out rembg, caption kecil ikut masa whisper) + cara bina gaya caption sendiri. Skrip `scripts/word_behind_head.py` (transcribe / render / --still).
- `skills/video-effect`: 51 video effect yang ikut muka (orbit, spotlight, glass-widgets, locked-on, reject-stamp, ...), Python + ffmpeg + MediaPipe. Dari github.com/Vibha-Ramprakash/claude-video-effects, disesuaikan untuk Windows. Venv dalam folder skill (`.venv/Scripts/python.exe`).
- `skills/video-review`: semak video macam Frame.io. Video diterbitkan sebagai Artifact dengan komen ikut saat (db `comments`); Claude baca komen, edit, terbitkan v2 di link sama. Skrip `scripts/build_review.py`.
- `skills/brand-style`: papan semakan gaya (Artifact) dengan kad animasi 9:16 + SFX; dia pilih Simpan/Mungkin/Buang + nota (db `reviews/rN`), Claude buat pusingan seterusnya dan kunci gaya dalam `brand/<brand>/STYLE.md` + `style.json`. Skrip `scripts/build_board.py`.
- `skills/cinematic-text`: gaya teks omgadrian (diluluskan 23 Nov): perkataan kabur→tajam satu-satu ikut sebutan, Playfair Italic kecil + Anton kuning besar, kotak kuning tersapu, tajuk belakang kepala, subtitle EB Garamond, whip blur. Skrip `scripts/cinematic_text.py plan.json` (venv video-effect). Fon dalam `D:\CLAUDE\kerja\_fonts\`.
- `skills/motion-broll-reel`: gaya "New Era" (5 reel rujukan `D:\NEW ERA 28HB\`, 23 Nov): caption 2 tingkat (baris kecil + kata kunci kuning dalam kotak / hijau limau), icon 3D pop-up dekat kepala, cincin muka, B-roll motion graphics ikut skrip (title, pills, chart, checklist, timeline, network, hero), tema gold / red. Skrip `scripts/motion_reel.py plan.json` (venv video-effect), draf dari transkrip `scripts/suggest.py`. Icon dalam `D:\CLAUDE\kerja\_icons\fluent3d\`.
- `tools/agent-studio/index.html`: salinan Agent Studio (https://claude.ai/artifact/KaAo8haEaqFCnNngfYV4WR), dashboard pusat. Video Agent ikut pipeline: Kumpul footage → Transkrip & pecah → Render & gaya → Semak → Final di D: → Posted. Data video dalam db `projects` (medan series, review, source, finalDir, length). Kemas kini status reel dengan ArtifactData, bukan republish. Butang "Hantar ke Claude" dalam drawer video/tugas hantar arahan sebagai komen artifact (capability `comments`) ke sesi Claude yang memantau artifact tu: dalam chat baru, mula pantau Agent Studio dengan ArtifactComments supaya arahan sampai, dan balas dalam thread komen tu. Lepas render reel: buat salinan 720p bawah 20 MB, muat naik ke asset store studio (Artifact asset:true) dan tulis url ke `projects/<id>.preview`. Workflow post: Lulus (dia tekan) → "Jana caption" (Claude tulis medan `caption`) → pilih akaun Zernio (`settings/main.zernio`) → "Post guna Zernio": upload fail final penuh via presigned URL, SAHKAN dengan dia (akaun, caption, masa) sebelum posts_create, kemudian set stage `posted` + `posts`. Akaun Zernio yang bersambung ialah IG @firaworldwide dan TikTok @firaindicator: jangan post vlog peribadi ke situ tanpa dia sahkan. Kalau ubah dashboard, terbitkan ke url sama dan salin balik ke sini.
- `tools/weby-reel`: pipeline render ffmpeg + libass (`render.py`, `transcribe.py`, contoh job JSON).
- `tools/remotion-reel`: pipeline Remotion (React) untuk motion graphics. Komposisi `PosterReel` (layout poster-frame, props: poster, video, videoStartSec, durationSec, headline, captions). Media letak dalam `public/` (tak masuk git). Render: `npx remotion render src/index.ts PosterReel out/x.mp4 --props=job.json`. Studio: `npm run studio`.

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
- **Klip ada konteks penuh.** Bila potong vlog jadi reel, setiap reel 60 hingga 120 saat (boleh lebih) dan mesti ceritakan satu situasi dari awal sampai habis, supaya penonton faham apa yang berlaku. Jangan potong 20 hingga 40 saat sahaja.

## Gaya edit pilihan: poster-frame (skill `skills/poster-frame-reel`)

Diluluskan 19 Nov 2026 pada reel 01 projek 1228. Ini gaya default untuk klip pendek dia:

- Kanvas 9:16 (1080x1920). Ikut "gradient frame": poster di atas (0 hingga ~610, pudar ke hitam antara y 300 hingga 470), video landskap dikecilkan ke jalur ~4:3 di tengah (y 608 hingga 1414), dan bahagian bawah hitam.
- **Poster:** SATU poster umum untuk semua klip dalam siri, gaya thumbnail YouTube: kolaj 2-3 gambar dia sendiri di tempat cantik, warna terang, tajuk kuning bergradien dengan outline hitam (cth. "DAY 1 DI MELBOURNE"). Poster tak perlu berkait dengan isi klip. Muka mesti berada di atas headline. Buat dengan `make_poster.py`.
- **Headline hook:** 2 baris Impact huruf besar, satu baris ungu `#CA00FF` dan satu putih, di y ~375 dan ~482.
- **Tiada capsule/pill** di bawah headline.
- **Subtitle:** di bawah video (y ~1466), 1-3 perkataan, Segoe UI Bold, putih dengan satu perkataan ungu `#A773F8` dan glow ungu. JANGAN guna gaya putih bertukar kuning (karaoke); dah dicuba dan ditolak.
- **SFX / bunyi meme** di bahagian kelakar atau penting, 3-5 bunyi satu klip, volume rendah. Pustaka ada dalam `D:\CLAUDE\kerja\_sfx\library.json`.

## Simpan video

- **`D:\Video\<nama projek>\` untuk video siap SAHAJA** (versi penuh, tiada `_phone`, tiada folder kerja). Orang tu tak nak nampak fail kerja dalam folder Video. Guna copy, bukan move, dan semak saiz fail sama selepas copy.
- **Fail kerja** (venv, model AI, mask, klip potongan, preview, versi lama, SFX) dalam `D:\CLAUDE\kerja\<nama projek>\`. Pustaka SFX: `D:\CLAUDE\kerja\_sfx\`. Fail besar ni tak masuk GitHub (had 100 MB satu fail); yang masuk GitHub cuma skrip, skill dan config.
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
- 19 Nov: gaya poster-frame diluluskan. Poster umum: `D:\CLAUDE\kerja\1228\work\poster_melbourne.jpg` (config `data/poster_melbourne.json`).
- 20 Nov (v4): 15 reel pendek dianggap kurang konteks. Vlog dipecah semula jadi **10 reel panjang (70 hingga 140 saat)**, setiap satu satu situasi penuh, dipotong terus dari timeline 1228. Pelan dalam `projects/1228/scripts/data/long_plan.json` (julat masa timeline + headline), SFX ikut frasa (`"at"`) dalam `poster_hooks.json` di bawah kunci `L01`..`L10`. Render: `long_reels.py D:/CLAUDE/kerja/1228/work D:/CLAUDE/kerja/1228/preview/reels_long 01 ...`. Output: `D:\CLAUDE\kerja\1228\preview\reels_long\long_NN.mp4` (penuh) dan `long_NN_phone.mp4` (720p untuk telefon). **Pilihan dia: reel ambil konteks penuh, 60 hingga 120 saat, boleh lebih kalau perlu.** Reel poster-frame lama (`reels_poster/`) dan 15 projek CapCut lama dah tak dipakai.
- Skrip 1228 dalam `projects/1228/scripts/`. Folder kerja penuh dan preview dalam `D:\CLAUDE\kerja\1228\` (dipindah 20 Nov). 10 reel panjang (versi penuh) disalin ke `D:\Video\1228\long_NN.mp4`.
- Butiran penuh dan lokasi fail: `.claude/handoffs/2026-11-16-capcut-1228.md`.
- Nota handoff terkini: lihat fail paling baru dalam `.claude/handoffs/`.
