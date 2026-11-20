---
name: video-effect
description: Tambah mana-mana daripada 51 video effect pada video talking-head (orbit, spotlight, glitter-spotlight, glass-widgets, locked-on, reject-stamp, red-collage, scribble, countdown-flip, timeline, checklist, headline-wall, comment-box, tap/Follow, phone-fan, liquid-glass-graph, match-cut, apple-toggles, led-sign, over-the-shoulder-zoom, messages/iMessage, place-in-grid dan lain-lain). Effect ikut muka dan boleh duduk di belakang kepala (cut-out MediaPipe). Dirender dengan Python + ffmpeg, tiada app edit. Guna bila orang tu kata "video effect", "/video-effect", "/effects", sebut nama mana-mana effect, atau minta tambah effect, zoom, grade, sticker atau animasi pada video.
---

# Video effect: 51 effect permulaan

Sumber: github.com/Vibha-Ramprakash/claude-video-effects (MIT, oleh @vibha.in.progress). Disalin ke repo VIDEOEDITOR sebagai `skills/video-effect` dan ke `~/.claude/skills/video-effect`.

Balas dalam Bahasa Melayu, ringkas. Buat kerja untuk dia, jangan suruh dia jalankan arahan sendiri.

Semua laluan di bawah relatif kepada folder skill ni. Guna laluan penuh dalam arahan.

## 1. Setup (sekali sahaja)
Jalankan `bash scripts/setup.sh` (Git Bash). Ia cetak `READY` bila siap (kali pertama 1 hingga 3 minit).
- `NEED_FFMPEG`: `winget install ffmpeg`.
- `NEED_PYTHON`: `winget install Python.Python.3.12`, kemudian jalankan setup lagi.
- Python venv di Windows: `.venv/Scripts/python.exe` (Mac/Linux: `.venv/bin/python`). Di bawah ditulis `PY`.

## 2. Video dan effect
- Video: fail yang dia hantar atau laluan yang dia beri. Video menegak (9:16) paling sesuai; untuk footage landskap, render effect dulu kemudian masukkan ke layout poster-frame.
- Effect: dari `/video-effect <nama>` atau apa yang dia terangkan. Padankan dengan jadual di bawah. Tak pasti? Tunjuk senarai.
- Effect dalam reel contoh dia yang TIADA dalam pek percuma ni: vertigo, digital-zoom, shadow-puppet, paper-cut, giant-captions, ascii-me, claude-ui, pullback (versi berbayar Hop Studio). Cadangkan yang paling dekat (cth. digital-zoom -> `locked-on` atau `slow-push`, giant-captions -> `backdrop-word`) dan beritahu dia terus terang.

## 3. Masa
- "pada perkataan X" / "bila aku cakap ...": jalankan `PY scripts/words.py <video>` dan guna masa tu. (Untuk Bahasa Melayu, set env `WHISPER_MODEL=small` atau lebih besar supaya lebih tepat.)
- Tiada masa diberi: guna seluruh klip, atau tanya satu soalan pendek bahagian mana.
- Tetingkap pendek paling cantik: 1.5 hingga 4 saat satu effect.

## 4. Draf, semak, render
1. Tulis pelan sebelah video sebagai `<nama-video>_effects.json`:
   ```json
   {"effects": [
     {"fx": "orbit", "start": 3.2, "end": 6.0},
     {"fx": "backdrop-word", "start": 14.0, "end": 16.3, "text": "CLAUDE"}
   ]}
   ```
2. Semak frame dulu (cepat): `PY scripts/fx.py --plan <plan.json> <video> <folder>/check.png --still 4.5,15.2` (tengah setiap effect). Tengok PNG sendiri. Betulkan teks, masa atau pilihan kalau tutup muka, terpotong di tepi, atau tak terbaca.
3. Render: `PY scripts/fx.py --plan <plan.json> <video> <nama-video>_effects.mp4`. Audio asal kekal. Default 1080p; `--width 2160` untuk 4K (lambat).
4. **Satu sampel dulu**: hantar SATU klip untuk dia semak sebelum render banyak. Video siap: copy ke `D:\Video\<nama projek>\` (semak saiz sama). Jangan simpan dalam repo atau Google Drive.

Satu effect tanpa pelan: `PY scripts/fx.py orbit <video> <out.mp4> --start 3 --end 6 --text "..." --opt key=value`.

## The 51 effects
| # | `fx` name | What it does | Options (all optional) |
|---|---|---|---|
| 1 | `noise` | Reels pile up behind your head, one every quarter second | `images` (folder of screenshots or clips), `size` |
| 2 | `lineup` | Numbered tiles fan out in an arc above your head | `text` (tile names joined with `\|`) |
| 3 | `locked-on` | Corner brackets snap onto your face, the camera follows you | `zoom` (default 1.35), `text` (tag) |
| 4 | `orbit` | Your reels circle your head: in front at the bottom, behind at the top | `images`, `count`, `speed`, `size` |
| 5 | `lean-in` | A fast punch-in on one word | `zoom` (default 1.45, max 2), `speed` |
| 6 | `backdrop-word` | A giant word drops in behind you | `text`, `color` (hex), `font` (`bold` or `serif`) |
| 7 | `spotlight` | Kills the lights, keeps you lit | `text` (glowing word behind you), `color`, `push` |
| 8 | `the-bill` | Prints your instructions like a receipt into the wall above your head | `text` (lines joined with `\|`) |
| 9 | `moody` | A moody colour grade | `grade` (`moody`, `bw`, `warm`, `cool`, `pop`) |
| 10 | `swipe` | A before and after slider sweeps across you | `grade` (the "after" look) |
| 11 | `todo` | A checklist card beside your head ticks off as you talk | `text` (items with `\|`), `ticks` (video seconds with `\|`), `title` |
| 12 | `comment-box` | An Instagram comment bar types a word and posts it | `text` (default EFFECTS) |
| 13 | `tap` | A Follow button pops up and flips to Following | `at` (video second of the flip), `x`, `y` (0 to 1), `color` |
| 14 | `pause-point` | Freezes the frame and points at you with a hand-drawn arrow | `text` (label), `color`, `label_x` |
| 15 | `uninstall` | A glitchy uninstall bar breaks the frame apart | `text` |
| 16 | `reel-frame` | Your video shrinks into an Instagram reel card | `text` (handle) |
| 17 | `shortcut-rain` | Keyboard keys rain down behind you | `text` (keys with `\|`), `count` |
| 18 | `reject-stamp` | A big red stamp slams onto the screen | `text`, `color`, `angle`, `y` |
| 19 | `countdown-flip` | A 3, 2, 1 flip clock above your head | `from` |
| 20 | `rabbit-hole` | The frame tunnels into itself, spinning | `ratio`, `speed`, `spin` |
| 21 | `cover-star` | You become a magazine cover, title behind your head | `text` (title), `lines` (with `\|`), `issue`, `color` |
| 22 | `scribble` | Marker doodles draw themselves around you | `text` (label), `color` |
| 23 | `glass-widgets` | Frosted glass widgets and mini artifacts float around your head, plus an Edited by Claude pill | `text` (big number), `name`, `handle`, `look` (`simple` for the 3-widget version) |
| 24 | `red-collage` | Black and white you, a giant red word behind, three lines slam in | `text` (red word), `lines` (with `\|`), `tag` |
| 25 | `split-headline` | A headline card slides down and pushes you to the bottom half | `text` (lines with `\|`), `hl` (highlighted word), `pill` |
| 26 | `pastel-word` | Lavender room, giant word behind you, a profile card gets followed | `text`, `name`, `handle` |
| 27 | `check-pills` | Grid-paper room, reel boards behind you, a cursor clicks blue pills | `text` (pills with `\|`), `images` |
| 28 | `timeline` | A dark red film grade with an editing timeline, a REC timecode and a glowing playhead | `text` (title), `sub`, `tc` |
| 29 | `headline-box` | A punch-in with a two-line headline, the second line in a white box | `text` (lines with `\|`), `zoom` |
| 30 | `profile-wall` | Your reels grid fills the wall behind you while a counter ticks up | `images`, `count`, `label` |
| 31 | `tier-list` | A tier list drops in and Claude flies into S tier | `title`, `item`, `others` |
| 32 | `broll-split` | B-roll on top with a price-tag sticker, you below | `images`, `text` (tag) |
| 33 | `phone-fan` | Your reels fan out like a hand of phones under a headline | `images`, `text` (lines with `\|`) |
| 34 | `dot-reveal` | Your shot builds out of glowing dots, then snaps to the full picture | `color`, `cell` |
| 35 | `headline-wall` | Your own headlines pile up behind your head, then a total pops in front | `text` (`headline::meta\|...`), `total`, `label` |
| 36 | `checklist` | A Claude task list under your chin: each step spins, then ticks green | `text` (`step::meta\|...`), `title` |
| 37 | `liquid-glass-graph` | A liquid glass card under your chin: a green graph climbs while the number counts up | `text` (label), `from`, `to` (e.g. `197K`, `59%`), `color` |
| 38 | `carousel-spin` | Your reels spin around you in a 3D carousel, then slow to a stop | `images`, `count`, `size`, `turns` |
| 39 | `match-cut` | News pages cut on one word, locked in a red box behind your head | `text` (the word, default Claude), `color` |
| 40 | `apple-toggles` | An iPhone settings card under your chin flips its switches on, one line at a time | `text` (rows with `\|`), `ticks` (seconds with `\|`), `color` |
| 41 | `led-sign` | The lights drop and a glowing LED sign types itself out behind you | `text` (lines with `\|`), `color`, `push` |
| 42 | `slow-push` | A slow cinematic push-in to your face while the room melts out of focus | `zoom` (default 1.6), `blur` |
| 43 | `over-the-shoulder-zoom` | The camera pushes into one top corner and a see-through liquid glass graph pops beside your head (line climbs, number counts up), pulls back, then the other corner with a second, related bar graph. Your head stays in front | `text` (two labels with `\|`), `to` (two numbers with `\|`, e.g. `197K\|672K`), `zoom` (default 2.0) |
| 44 | `messages` | iMessage notifications pop in one after another, creamy glass with a soft glow, stacking up above the bottom of the frame | `text` (messages with `\|`), `title` (default Messages), `y` |
| 45 | `place-in-grid` | You shrink into the centre tile of your 3x3 profile grid on frosted glass, then 8 reels pop in around you, one per frame, with Instagram view counts on every tile | `images` (folder of your reels or covers), `views` (9 counts with `\|`, the 9th is yours) |
| 46 | `tape-label` | A level strip of yellow tape with your line lands on your chest, kept off your face | `text` |
| 47 | `select-resize` | A blue selection box with handles grabs your number above your head and a cursor drags it bigger | `text` (default 2X) |
| 48 | `wave-trim` | A dark panel above your head shows your voice; the red dotted silence on both ends collapses until only your words are left | none |
| 49 | `huge-strike` | One huge serif word wipes in behind your head, then a red line crosses it out | `text`, `at` (seconds into the effect when the strike lands, default 0.6) |
| 50 | `crayon-write` | A red crayon writes your word behind your head, then underlines it and flies off | `text` |
| 51 | `fan-build` | Your reel covers deal into a fan behind your head, one card at a time | `images` (folder of your covers), `count` (default 13) |

**Named looks** (same effect, a fancier look; they don't add to the count):
- `glitter-spotlight` = `spotlight` with `look=sparkle`: the room goes dark, golden rays burst from behind your head, a big gold word with a shine sweep, twinkling sparkles and a glow around you. `text` (the word), `color`, `push`.
- `cover-star` with `look=editorial`: a soft warm film look, a classic serif masthead behind your head, an issue line and elegant cover lines. `text` (masthead), `issue`, `lines` (3 lines with `\|`), `right` (lines with `\|`), `color`, `accent`, `lines_y`, `right_y`.
- `liquid-glass-graph` with `look=bento`: the climbing graph moves to a smoked glass screen behind your head, with glass bento tiles in front of you (a donut, a KPI, bars). `text`, `from`, `to`, `donut` (`29%::label`), `kpi` (`672K::label`), `bars` (`197\|140\|124::label`).
- `apple-toggles` now sits above you, tucked behind your head, with a gentle zoom (`pos=below` for the old under-the-chin card; `overlap`, `zoom`).

Aliases work too: `bill`, `to-do`, `follow`, `stamp`, `countdown`, `cover`, `rain`, `pause`.

## Peraturan
- Jangan tutup muka. Semua sama ada di belakang orang atau mengelak muka sendiri; kalau frame semak masih tunjuk teks atas muka, alih (`x`, `y`) atau pendekkan teks.
- Effect dijalankan ikut susunan. Letak effect kamera (`locked-on`, `lean-in`, `spotlight`) dulu kalau bertindih.
- Zoom tak lebih 2x supaya video kekal tajam.
- Skill ni tambah visual sahaja. Subtitle: guna skill `caption` / gaya poster-frame (subtitle bawah muka). SFX: pustaka `D:\CLAUDE\kerja\_sfx\library.json`.
- Ini versi permulaan. Jujur kalau dia banding dengan reel yang dia nampak.
