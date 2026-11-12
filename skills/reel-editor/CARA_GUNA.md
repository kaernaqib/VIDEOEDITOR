# Reel Editor: cara guna

## Pasang sekali sahaja
1. Buka **Claude desktop app** di komputer yang ada CapCut.
2. Pergi ke Settings → Capabilities → Skills → Upload skill, kemudian pilih `reel-editor.zip`.
   Pastikan skill **capcut-talking-head-edit** juga ON. Skill ni bergantung padanya.
3. Sambung connector: **Epidemic Sound** (muzik/SFX) dan **Zernio** (post). Kalau nak B-roll stok,
   sediakan API key Pixabay yang percuma (pixabay.com/api/docs) dan set: `setx PIXABAY_API_KEY "key"`.
4. Dalam CapCut, buat satu project kecil bernama **REEL TEMPLATE** (9:16) yang ada:
   - satu teks "caption KEYWORD": perkataan "caption" putih (font caption kau), "KEYWORD" kuning,
     dalam SATU kotak teks, dengan animasi masuk yang kau suka
   - satu teks "1 TITLE": nombor kuning, tajuk putih (untuk listicle)
   - (pilihan) satu tajuk besar kuning condensed (untuk gaya vlog)
   - satu klip video, satu lagu dengan fade-in, satu adjustment layer
   Lepas tu **quit CapCut**.

## Setiap kali nak edit
1. Upload footage ke project baru dalam CapCut (9:16). Namakan project tu, contoh `Reel - harga mahal`.
   Lepas tu quit CapCut.
2. Dalam Claude desktop app, taip:
   `/reel-editor edit project "Reel - harga mahal", format education`
   (format: education / vlog / dos-donts / before-after; boleh tambah: "B-roll dalam folder X")
3. Agent buat semua sendiri, kemudian hantar **preview + thumbnail + caption post** untuk kau semak.
4. Approve → agent tanya "CapCut dah quit?" → dia tulis edit ke dalam project.
5. Buka CapCut, semak/adjust, Export. Lepas tu agent post ke TikTok/IG/YouTube (dia tanya dulu).
