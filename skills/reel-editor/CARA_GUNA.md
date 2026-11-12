# Reel Editor: cara guna

## Konsep: mode × style × format
- **Mode**: jenis video. `talking-head` (kau cakap depan kamera), `vlog` (banyak klip lokasi), `faceless`
  (tiada muka, guna voiceover sendiri atau suara AI + visual campur).
- **Style**: rupa video. `authority` (caption putih + kata kunci kuning, potongan keras) atau `omgadrian`
  (tajuk besar kuning + serif, B-roll sinematik, grade hangat). Style baru boleh ditambah dari reel rujukan.
- **Format**: struktur isi. `education`, `dos-donts`, `before-after`, `vlog` (cerita).

## Pasang sekali sahaja
1. Di **Claude desktop app**: Settings → Capabilities → Skills, upload `reel-editor` (zip folder ni).
   Pastikan **capcut-talking-head-edit** juga ON.
2. Connector: **Epidemic Sound** (muzik/SFX), **Zernio** (post). B-roll stok: `setx PIXABAY_API_KEY "key"`.
   Suara AI (pilihan): `setx ELEVENLABS_API_KEY "key"`, atau guna Text-to-speech dalam CapCut sendiri.
3. Untuk **setiap style**, buat satu project CapCut 9:16 bernama `STYLE <nama>` (contoh `STYLE omgadrian`)
   yang ada apa yang disenaraikan di bahagian "CapCut template" dalam `styles/<nama>/STYLE.md`.
   Asasnya sama untuk semua style:
   - 2 klip video dengan 1 transition di tengah, 1 klip dengan animasi masuk
   - adjustment layer dengan grade style tu
   - teks caption / tajuk dalam font dan warna style tu
   - 1 lagu dengan fade-in
   Lepas tu **quit CapCut**.

## Setiap kali nak edit
1. Masukkan footage (atau voiceover) ke project baru dalam CapCut, namakan, quit CapCut.
2. Dalam Claude desktop app (atau salin terus dari Agent Studio → Video):
   `Guna skill reel-editor. Edit project CapCut "Reel - harga mahal", mode talking-head, style authority, format education. Aku guna Windows.`
3. Agent buat semua, kemudian hantar **preview + thumbnail + caption post** untuk kau semak.
4. Approve → agent tanya "CapCut dah quit?" → tulis edit ke project → buka CapCut, semak, Export.

## Tambah style baru
Hantar 3–5 reel rujukan kepada Claude dan kata: "Buat style pack baru nama X dari reel ni."
Claude ukur warna, rentak, kedudukan teks dan loudness (`scripts/analyze_style.py`), tulis `styles/X/`, dan tambah
style tu ke Agent Studio.
