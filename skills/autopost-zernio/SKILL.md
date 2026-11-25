---
name: autopost-zernio
description: Jadualkan atau post video yang DAH SIAP (bukan edit dari scratch) ke TikTok dan Instagram guna Zernio. Claude tengok video, tulis 3 pilihan caption, dia pilih satu, kemudian Claude jadualkan ikut masa waktu Malaysia. Juga mengendalikan permintaan dari halaman "Jadual Post" dalam Agent Studio (jana caption, jadualkan, batal, import folder Drive, semak status). Guna bila dia kata "autopost", "jadual post", "schedule video ni", "post video siap", "buat caption untuk video dalam folder ni", beri link Google Drive video/folder untuk dipost, atau bila komen Agent Studio bermula "[Agent Studio · Jadual Post".
---

# Autopost Zernio

Video yang dah siap (biasanya dalam Google Drive) → 3 caption → dia pilih → Zernio post ikut masa.
Satu-satunya tempat state disimpan: db Agent Studio, koleksi `autopost`.

## Fakta tetap

- Agent Studio: https://claude.ai/artifact/KaAo8haEaqFCnNngfYV4WR (salinan `tools/agent-studio/index.html`). Halaman `#jadual`.
- **Dia guna lebih dari satu akaun Zernio** (setiap satu pelan percuma, 2 akaun sosial) dan tukar sambungan connector Zernio dalam Claude. Dia dah tahu risiko terma Zernio dan dah buat keputusan; jangan ulang amaran tu. Analytics dan semak status tak penting bagi dia; yang penting senang jadualkan.
- **Jangan guna ID akaun tetap.** Setiap kali mula kerja Zernio (dan bila dia kata "dah tukar ke Zernio N"): `mcp__Zernio__accounts_list`, kemudian padankan dengan `settings/main.zernioWorkspaces` dalam db Agent Studio:
  - Akaun yang sama dengan satu workspace → itu yang bersambung. Set `active: true` padanya, `false` pada yang lain, kemas kini `checkedAt`.
  - Akaun yang belum dikenali → tambah workspace baru `{id: "zernio-N", name: "Zernio N", accounts, active: true}` (N seterusnya; tanya dia kalau nak nama lain).
  - Salin `accounts` workspace aktif ke `settings/main.zernio` (butang akaun dalam halaman baca dari situ).
  - Beritahu dia ringkas: "Bersambung: Zernio N (IG @…, TikTok @…)".
- Rekod setakat 25 Nov 2026: **Zernio 1** (melalui connector MCP) = IG `@firaworldwide` + TikTok `@firaindicator` (semua post NEW ERA / countdown / tiket / launching ada di sini). **Zernio 2** (melalui API key) = IG `@kaernaqib` + TikTok `@ceocarbo` (akaun peribadi / lain: jangan campur dengan kandungan brand FIRA). Satu post Zernio hanya boleh ke akaun dalam SATU workspace; komen dari studio sebut `Akaun Zernio: <nama> (guna connector | guna API key)`, ikut tu.
- **Mod API (Zernio 2):** dalam sesi cloud, API key disimpan sebagai network secret untuk `zernio.com`; proxy masukkan header sendiri. Panggil dengan `curl -H "Authorization: Bearer proxy-injected" https://zernio.com/api/v1/...` (jangan sekali-kali tulis key sebenar). Endpoint: `GET /v1/accounts`, `POST /v1/posts` (badan sama macam `posts_create_post`: `content`, `mediaItems`, `platforms[{platform, accountId}]`, `scheduledFor`, `timezone`, `externalId`), `GET /v1/posts/<id>`, `PUT /v1/posts/<id>`, `DELETE /v1/posts/<id>`, `POST /v1/media/presign`. Di PC: key dalam env var (cth. `ZERNIO_KEY_2`), bukan dalam repo. Workspace dalam db ada `via: "connector" | "api"`; kedua-duanya boleh `active: true` serentak, dan `settings/main.zernio` = gabungan akaun semua workspace aktif. Kalau dia tampal key dalam chat, jangan guna key tu: minta dia padam dan buat baru, kemudian `request_credential`.
- Hanya jadualkan, batal atau ubah post dalam workspace yang aktif. Kalau dokumen `autopost` guna akaun dari workspace lain, beritahu dia perlu tukar sambungan dulu. Post dalam workspace yang tak aktif tetap keluar sendiri.
- Tukar akaun dalam Zernio (unlink/link IG/TikTok): dalam 1 jam, akaun kekal sama dan post masa depan kekal; lebih dari 1 jam, akaun dipadam, post untuk akaun tu sahaja dibatalkan, post berbilang akaun buang akaun tu. Semak post tertunggak sebelum dia unlink.
- Facebook TIDAK disambung dalam Zernio. FB dapat Reel melalui kongsi automatik Instagram (Accounts Center).
- Zon masa sentiasa `Asia/Kuala_Lumpur` (UTC+8). Semak masa sekarang dengan `TZ=Asia/Kuala_Lumpur date` sebelum jadual.
- Akaun Zernio 1 ialah akaun brand trading (FIRA / Fira Indicator). Jangan post vlog peribadi ke situ tanpa dia sahkan.

## Dokumen `autopost/<id>`

```
title, link (share link Drive), note (konteks caption),
zAccounts [id akaun Zernio], postAt "YYYY-MM-DDTHH:mm" (waktu Malaysia),
captions [A, B, C], pick (0-2 | null), caption (teks akhir),
status  baru | pilih | jadual | posted | gagal,
waiting caption | jadual | batal | null   (Claude set null bila siap),
zernioPostId, error, posts [{platform, url}], preview (/_blob/<id>), created, updated
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
6. **Preview untuk halaman Jadual Post** (supaya dia boleh semak video betul): `ffmpeg -i v.mp4 -vf scale=540:-2 -c:v libx264 -preset veryfast -crf 30 -c:a aac -b:a 64k -movflags +faststart <id>.mp4` (bawah 20 MB). Salin ke folder sementara dalam repo (cth. `_prev_tmp/`, padam selepas), muat naik dengan Artifact `asset: true` + `file_paths` (sampai 25 sekali) ke url Agent Studio, kemudian tulis `/_blob/<id>` ke medan `preview` dokumen.

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
    "platforms": [{"platform": "tiktok", "accountId": "<id TikTok workspace aktif>"},
                  {"platform": "instagram", "accountId": "<id IG workspace aktif>"}],
    "scheduled_for": "2026-11-27T10:00:00+08:00", "timezone": "Asia/Kuala_Lumpur",
    "external_id": "AP-<id>"}
   ```
   Post sekarang: `publish_now: true` (tanpa `scheduled_for`). Zernio salin video ke storan dia masa create, jadi fail Drive boleh dipindah selepas tu.
4. Kemas kini `autopost/<id>`: `status: "jadual"`, `zernioPostId`, `waiting: null`. Kalau gagal: `status: "gagal"`, `error` (ayat ringkas yang dia faham), `waiting: null`.

## Batal / semak status

- Batal: `posts_delete` (cari dengan `search_tools`) pada `zernioPostId`, kemudian `status: "pilih"`, `zernioPostId: null`, `waiting: null`.
- Semak: untuk setiap `status: "jadual"`, `mcp__Zernio__posts_get`, atau `posts_list_posts` sekali gus. Dah keluar → `status: "posted"`, `posts` dari `platformPostUrl`. Gagal → `status: "gagal"` + `error`, tawar `posts_retry`.

## Banyak video sekali gus (pukal)

Komen `[Agent Studio · Jadual Post · Import folder Drive]` atau `[… · Import folder PC]`, atau dia beri folder dalam chat.

1. Senaraikan video dalam folder (susun ikut nama, nombor ikut nilai: countdown 2 sebelum countdown 10). Langkau yang dah ada dalam `autopost` (sama `link`/path) dan yang bukan video. Beritahu dia apa yang dilangkau.
2. Buat semua dokumen dulu dalam satu `ArtifactData` batch (`status: "baru"`, `waiting: "caption"`, `zAccounts` = semua akaun, `source: "drive"|"pc"`), supaya kad muncul serta-merta.
3. Untuk setiap video: Langkah 1-2. Tulis caption setiap video sebaik siap (batch kecil 3-5 dokumen), jangan tunggu semua siap.
4. Masa: isi `postAt` ikut slot dalam komen (cth. `10:00, 13:00, 18:00` mula tarikh X), ikut susunan nama fail, langkau slot yang dah lepas atau dah dipakai post lain (`status` jadual/posted).
5. Ikut mod dalam komen:
   - **Mod PILIH** (default): `status: "pilih"`, jangan jadualkan. Dia pilih A/B/C dalam jadual "Pilih caption & masa", kemudian tekan "Jadualkan N video" yang hantar komen `Jadual pukal` dengan senarai id.
   - **Mod TERUS JADUAL**: dia dah sahkan dengan pilih mod ni. Pilih caption paling sesuai (`pick`, `caption`), kemudian Langkah 3 untuk setiap video. Dalam balasan, senaraikan video + caption dipilih + masa supaya dia boleh semak.
6. `Jadual pukal`: untuk setiap id, baca dokumen, Langkah 3. Satu gagal tak menghentikan yang lain. Balas: berapa berjaya, mana gagal dan kenapa.

### Sumber folder PC (D:\…)

Fail dalam PC hanya boleh dibaca bila Claude jalan di PC dia (Claude Code desktop). Dalam sesi cloud, beritahu dia dan cadang buka chat di PC, atau salin folder ke Google Drive (ingat: CLAUDE.md kata jangan simpan video dalam Drive kerana storan terhad; Zernio salin video ke storan sendiri, jadi fail Drive boleh dipadam selepas dijadualkan).

Upload dari PC:
1. `mcp__Zernio__media_get_media_presigned_url` (`filename`, `content_type` "video/mp4" atau "video/quicktime", `size`).
2. `curl -X PUT -H "Content-Type: video/mp4" --data-binary @"<path>" "<uploadUrl>"`.
3. Guna `publicUrl` sebagai url video dalam `posts_create_post`, dan simpan dalam `autopost/<id>.mediaUrl` supaya tak upload dua kali.
Contact sheet terus dari path fail (ffmpeg boleh baca path Windows dalam petikan).

## Perangkap

- Token TikTok pendek (24 jam) dan biasanya diperbaharui sendiri. Sebelum jadual, `mcp__Zernio__accounts_get_all_accounts_health`; kalau `needsReconnect`, beritahu dia untuk sambung semula di zernio.com.
- `posts_cross_post` tak boleh pilih masa tepat (default 1 jam). Untuk masa tepat guna `posts_create_post` + `scheduled_for`.
- Status "publishing" boleh ambil beberapa minit. Jangan cakap "dah keluar" sebelum status `published`.
- Jangan simpan video dalam repo. Fail muat turun hanya dalam scratchpad.
