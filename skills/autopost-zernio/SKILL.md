---
name: autopost-zernio
description: Jadualkan atau post video yang DAH SIAP (bukan edit dari scratch) ke TikTok dan Instagram guna Zernio. Claude tengok video, tulis 3 pilihan caption, dia pilih satu, kemudian Claude jadualkan ikut masa waktu Malaysia. Juga mengendalikan permintaan dari halaman "Jadual Post" dalam Agent Studio (jana caption, jadualkan, batal, import folder Drive, semak status). Guna bila dia kata "autopost", "jadual post", "schedule video ni", "post video siap", "buat caption untuk video dalam folder ni", beri link Google Drive video/folder untuk dipost, atau bila komen Agent Studio bermula "[Agent Studio · Jadual Post".
---

# Autopost Zernio

Video yang dah siap (biasanya dalam Google Drive) → 3 caption → dia pilih → Zernio post ikut masa.
Satu-satunya tempat state disimpan: db Agent Studio, koleksi `autopost`.

## Fakta tetap

- Agent Studio: https://claude.ai/artifact/KaAo8haEaqFCnNngfYV4WR (salinan `tools/agent-studio/index.html`). Halaman `#jadual`.
- Akaun Zernio (pelan percuma, had 2 akaun): IG `@firaworldwide` id `6b03c59aabc9e71e8c3932e5`, TikTok `@firaindicator` id `6b03c5b9ee6b9703e7344a9d`. Senarai sama ada dalam db `settings/main.zernio`.
- Facebook TIDAK disambung dalam Zernio. FB dapat Reel melalui kongsi automatik Instagram (Accounts Center). Jangan cadang buka akaun Zernio kedua untuk elak had.
- Zon masa sentiasa `Asia/Kuala_Lumpur` (UTC+8). Semak masa sekarang dengan `TZ=Asia/Kuala_Lumpur date` sebelum jadual.
- Akaun ni akaun brand trading (FIRA / Fira Indicator). Jangan post vlog peribadi ke situ tanpa dia sahkan.

## Dokumen `autopost/<id>`

```
title, link (share link Drive), note (konteks caption),
zAccounts [id akaun Zernio], postAt "YYYY-MM-DDTHH:mm" (waktu Malaysia),
captions [A, B, C], pick (0-2 | null), caption (teks akhir),
status  baru | pilih | jadual | posted | gagal,
waiting caption | jadual | batal | null   (Claude set null bila siap),
zernioPostId, error, posts [{platform, url}], created, updated
```

Tulis dengan `ArtifactData` (update + `if_version` dari bacaan terakhir). Jangan republish halaman untuk tukar data.

## Langkah 1: tengok video

1. Dapatkan file id Drive (`/file/d/<ID>/`). Untuk folder: `mcp__Google_Drive__search_files` dengan `parentId = '<folderId>'`.
2. Muat turun ke scratchpad (fail mesti "Anyone with the link"):
   `curl -sL -o v.mp4 "https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t"`
3. Contact sheet ~20 frame dan Read gambar tu:
   `ffmpeg -v error -i v.mp4 -vf "fps=1/<durasi/20>,scale=300:-1,tile=5x4" -frames:v 1 -y s.jpg`
4. Baca teks atas skrin + apa yang disebut. Ringkaskan isi dalam satu ayat.
5. Semak kesesuaian: `mcp__Zernio__validate_media` dengan link Drive (format, saiz, had platform). Video 9:16 paling sesuai.

## Langkah 2: 3 caption

Tiga gaya berbeza, BM santai/rojak ikut nada akaun:
- **A** hook / rasa ingin tahu (soalan atau kenyataan yang buat orang berhenti scroll)
- **B** pendek, terus ke point (tarikh/offer + CTA)
- **C** bercerita: masalah → penyelesaian

Setiap satu: baris pertama hook, isi ikut video (jangan reka fakta yang tiada dalam video), satu CTA ("link di bio": link dalam caption tak boleh diklik di TikTok/IG), 4-7 hashtag (selalu `#FiraWorldwide` untuk akaun ni). Kalau ada tarikh event, sesuaikan sudut dengan masa post (cth. "ESOK" kalau sehari sebelum).

- Dalam chat: tunjuk A/B/C dan tanya mana satu + masa.
- Dari Agent Studio: tulis `captions`, `status: "pilih"`, `waiting: null`. Balas ringkas dalam thread komen.

## Langkah 3: jadual

1. Sahkan: akaun, masa (mesti masa depan), caption. Dalam chat, pilihan dia ("2C, 1:30pm") ialah pengesahan. Dari Agent Studio, butang "Jadualkan guna Zernio" ialah pengesahan (halaman tunjuk ringkasan sebelum dia tekan).
2. `mcp__Zernio__validate_post` (media_items video url Drive + platforms dengan accountId).
3. `mcp__Zernio__call_tool` `posts_create_post`:
   ```json
   {"content": "<caption>", "media_items": [{"type": "video", "url": "<link Drive>"}],
    "platforms": [{"platform": "tiktok", "accountId": "6b03c5b9ee6b9703e7344a9d"},
                  {"platform": "instagram", "accountId": "6b03c59aabc9e71e8c3932e5"}],
    "scheduled_for": "2026-11-27T10:00:00+08:00", "timezone": "Asia/Kuala_Lumpur",
    "external_id": "AP-<id>"}
   ```
   Post sekarang: `publish_now: true` (tanpa `scheduled_for`). Zernio salin video ke storan dia masa create, jadi fail Drive boleh dipindah selepas tu.
4. Kemas kini `autopost/<id>`: `status: "jadual"`, `zernioPostId`, `waiting: null`. Kalau gagal: `status: "gagal"`, `error` (ayat ringkas yang dia faham), `waiting: null`.

## Batal / semak status

- Batal: `posts_delete` (cari dengan `search_tools`) pada `zernioPostId`, kemudian `status: "pilih"`, `zernioPostId: null`, `waiting: null`.
- Semak: untuk setiap `status: "jadual"`, `mcp__Zernio__posts_get`, atau `posts_list_posts` sekali gus. Dah keluar → `status: "posted"`, `posts` dari `platformPostUrl`. Gagal → `status: "gagal"` + `error`, tawar `posts_retry`.

## Import folder Drive

Senaraikan video dalam folder. Untuk setiap video yang `link`-nya belum ada dalam `autopost`, buat dokumen baru (`status: "baru"`, `zAccounts` = semua akaun, `waiting: "caption"`), kemudian buat Langkah 1-2 untuk setiap satu. Video dengan nama sama atau tak sesuai format (bukan video, terlalu pendek) beritahu dia, jangan tambah.

## Perangkap

- Token TikTok pendek (24 jam) dan biasanya diperbaharui sendiri. Sebelum jadual, `mcp__Zernio__accounts_get_all_accounts_health`; kalau `needsReconnect`, beritahu dia untuk sambung semula di zernio.com.
- `posts_cross_post` tak boleh pilih masa tepat (default 1 jam). Untuk masa tepat guna `posts_create_post` + `scheduled_for`.
- Status "publishing" boleh ambil beberapa minit. Jangan cakap "dah keluar" sebelum status `published`.
- Jangan simpan video dalam repo. Fail muat turun hanya dalam scratchpad.
