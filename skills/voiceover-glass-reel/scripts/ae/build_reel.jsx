// build_reel.jsx — builds the whole reel in After Effects from work/plan.json (written by reel.py plan).
// Run through build.sh (it sets $.global.REEL_PLAN and $.global.REEL_AE). Re-runnable: it rebuilds reel.aep from scratch.
// Look: dark archival documentary, host on an old TV, every generated clip in a floating rounded glass frame (thin glowing
// border, smooth push-in, its own blurred light behind it), a moving perspective grid under the list section with keywords
// flipping colour on the word, big spoken captions spread across the frame, typewriter / giant-word / photo-card pages,
// bleach flashes and negative flicks on the cuts, sound effects on every visual event.
$.evalFile(new File($.global.REEL_AE + "/reel_lib.jsx"));
(function () {
  var P = R.readJSON($.global.REEL_PLAN), FPS = P.fps, W = 1920, H = 1080, DUR = P.dur;
  R.FPS = FPS;
  function F(n) { return n / FPS; }
  var t00 = new Date().getTime();

  // ---------------------------------------------------------------- project
  var want = new File(P.aep);
  if (app.project.file && app.project.file.fsName === want.fsName) {
    for (var ri = app.project.numItems; ri >= 1; ri--) { try { app.project.item(ri).remove(); } catch (e) { } }
  } else {
    var ours = !app.project.file && R.findItem("01_SOURCE", FolderItem) && R.findItem("02_SHOTS", FolderItem);   // our own build that failed before saving
    if (!ours && app.project.numItems > 0 && app.project.dirty) throw new Error("Another After Effects project with unsaved changes is open. Save or close it, then run the build again.");
    if (ours) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    else if (app.project.file) R.log("PREVIOUS_PROJECT " + app.project.file.fsName);   // reopen it for the user when you are done
    app.newProject();
    app.project.save(want);                             // saved at once: a failed build reopens and rebuilds this same file
  }
  // keep the viewer on a tiny empty comp: AE redraws the open comp after every scripted edit (10x slower otherwise)
  try { var idle = R.comp("__idle", 16, 16, 1 / FPS, null, [0, 0, 0]); idle.openInViewer(); } catch (e) { }
  var tph = new Date().getTime();
  function phase(name) { var n = new Date().getTime(); R.log("  " + name + " " + ((n - tph) / 1000).toFixed(1) + " s"); tph = n; }
  app.beginUndoGroup("build reel");
  var FD = { src: R.folder("01_SOURCE"), shots: R.folder("02_SHOTS"), pages: R.folder("03_PAGES"), text: R.folder("04_TEXT"), audio: R.folder("05_AUDIO") };
  var ACC = R.hex(P.accent || "#FFD23F"), GLOW = R.hex(P.glow || "#CFF3FF");
  var FONT = {
    sans: R.font(["SFProDisplay-Medium", "HelveticaNeue-Medium", "Helvetica", "ArialMT"]),
    bold: R.font(["SFProDisplay-Bold", "HelveticaNeue-Bold", "Helvetica-Bold", "Arial-BoldMT"]),
    black: R.font(["HelveticaNeue-CondensedBlack", "SFProDisplay-Black", "Impact", "Arial-BoldMT"]),
    serif: R.font(["Georgia", "Baskerville", "TimesNewRomanPSMT"]),
    serifI: R.font(["Georgia-Italic", "Baskerville-Italic", "TimesNewRomanPS-ItalicMT"]),
    type: R.font(["AmericanTypewriter", "Courier-Bold", "CourierNewPS-BoldMT"])
  };
  var M = R.comp("REEL", W, H, DUR, null, [0, 0, 0]);
  M.workAreaStart = 0; M.workAreaDuration = DUR;
  M.comment = P.title + " — built by build_reel.jsx from work/plan.json";

  // ---------------------------------------------------------------- shared pieces
  var PAGE = null;
  function pageBG() {                                   // dark page with a faint 1 px grid and a vignette
    if (PAGE) return PAGE;
    PAGE = R.comp("PAGE_BG", W, H, DUR, FD.pages, [0, 0, 0]);
    R.solid(PAGE, R.hex("#0B0D10"), "page");
    var g = R.shape(PAGE, "grid lines"), RG = g.property("ADBE Root Vectors Group");
    function ln(w, h, x, y) { var gg = RG.addProperty("ADBE Vector Group").property("ADBE Vectors Group"); var rc = gg.addProperty("ADBE Vector Shape - Rect"); rc.property("ADBE Vector Rect Size").setValue([w, h]); rc.property("ADBE Vector Rect Position").setValue([x, y]); }
    for (var x = -960; x <= 960; x += 96) ln(1, H, x, 0);
    for (var y = -540; y <= 540; y += 96) ln(W, 1, 0, y);
    RG.addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue([1, 1, 1]);
    R.opac(g, 6);
    vignette(PAGE, 55);
    return PAGE;
  }
  function vignette(c, op) {
    var v = R.solid(c, [0, 0, 0], "vignette"), m = v.property("ADBE Mask Parade").addProperty("ADBE Mask Atom"), e = new Shape();
    var rx = c.width * 0.62, ry = c.height * 0.66, cx = c.width / 2, cy = c.height / 2, kx = rx * 0.5523, ky = ry * 0.5523;
    e.vertices = [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]]; e.inTangents = [[-kx, 0], [0, -ky], [kx, 0], [0, ky]]; e.outTangents = [[kx, 0], [0, ky], [-kx, 0], [0, -ky]]; e.closed = true;
    m.property("ADBE Mask Shape").setValue(e); m.maskMode = MaskMode.SUBTRACT; m.property("ADBE Mask Feather").setValue([320, 320]);
    R.opac(v, op);
    return v;
  }
  // the moving perspective grid of the list section (one comp for the whole section, so it keeps moving across cuts)
  var PG = null;
  if (P.list) {
    var GD = P.list[1] - P.list[0] + 1;
    PG = R.comp("LIST_GRID", W, H, GD, FD.pages, [0, 0, 0]);
    R.solid(PG, R.hex("#05070B"), "grid base");
    var gr = PG.layers.addShape(); gr.name = "grid floor"; gr.threeDLayer = true; R.anchor(gr, [0, 0, 0]);
    var RG = gr.property("ADBE Root Vectors Group"), STEP = 120, HALF = 3600;
    var gline = function (w, h, x, y) { var g = RG.addProperty("ADBE Vector Group").property("ADBE Vectors Group"); var rc = g.addProperty("ADBE Vector Shape - Rect"); rc.property("ADBE Vector Rect Size").setValue([w, h]); rc.property("ADBE Vector Rect Position").setValue([x, y]); };
    for (var gx = -HALF; gx <= HALF; gx += STEP) gline(3, 2 * HALF, gx, 0);
    for (var gy = -HALF; gy <= HALF; gy += STEP) gline(2 * HALF, 3, 0, gy);
    RG.addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(R.hex("#7FDFFF"));
    R.tr(gr).property("ADBE Rotate X").setValue(78); R.opac(gr, 55);
    R.tr(gr).property("ADBE Position").setValue([960, 860, 0]);
    var ga = R.tr(gr).property("ADBE Anchor Point"); R.lin(ga, 0, [0, 0, 0]); R.lin(ga, GD, [0, 2 * STEP * GD, 0]);   // 2 cells a second toward the viewer
    var gg = R.fx(gr, "ADBE Glo2", "grid glow"); R.set(gg, "Glow Radius", 16); R.set(gg, "Glow Intensity", 1.2);
    var hz = R.solid(PG, [0, 0, 0], "horizon fade"), hm = hz.property("ADBE Mask Parade").addProperty("ADBE Mask Atom"), hs = new Shape();
    hs.vertices = [[-200, -200], [2120, -200], [2120, 560], [-200, 560]]; hs.closed = true; hm.property("ADBE Mask Shape").setValue(hs); hm.property("ADBE Mask Feather").setValue([0, 260]);
    var hzz = R.solid(PG, [1, 1, 1], "grid haze"); hzz.blendingMode = BlendingMode.SCREEN; R.opac(hzz, 10);
    var glm = hzz.property("ADBE Mask Parade").addProperty("ADBE Mask Atom"), gs = new Shape(), rx = 900, ry = 160, kx = rx * 0.5523, ky = ry * 0.5523;
    gs.vertices = [[960, 540 - ry], [960 + rx, 540], [960, 540 + ry], [960 - rx, 540]]; gs.inTangents = [[-kx, 0], [0, -ky], [kx, 0], [0, ky]]; gs.outTangents = [[kx, 0], [0, ky], [-kx, 0], [0, -ky]]; gs.closed = true;
    glm.property("ADBE Mask Shape").setValue(gs); glm.property("ADBE Mask Feather").setValue([300, 300]);
  }

  // ---------------------------------------------------------------- shot builders (each returns {comp, push})
  function hostTV(s) {
    var D = s.t1 - s.t0, c = R.comp(s.id + "_HOST_TV", W, H, D, FD.shots, [0, 0, 0]), tv = P.tv;
    var plate = R.imp(tv.plate, FD.src), S = Math.max(W / plate.width, H / plate.height);
    var bx = tv.box, kx = plate.width / tv.w, scx = (bx[0] + bx[2]) / 2 * kx, scy = (bx[1] + bx[3]) / 2 * kx;
    var extraX = (plate.width * S - W) / 2, extraY = (plate.height * S - H) / 2;
    var px = 960 + Math.max(-extraX, Math.min(extraX, 960 - (960 + (scx - plate.width / 2) * S)));
    var py = 540 + Math.max(-extraY, Math.min(extraY, 540 - (540 + (scy - plate.height / 2) * S)));
    var sx = px + (scx - plate.width / 2) * S, sy = py + (scy - plate.height / 2) * S;
    var sw = (bx[2] - bx[0]) * kx * S + 10, sh = (bx[3] - bx[1]) * kx * S + 10;
    var host = R.imp(s.file, FD.src);
    var hl = R.cover(c, host, sw, sh, sx, sy); hl.name = "HOST " + host.name; R.place(hl, 0, s["in"], D); R.look(hl);
    var bl = R.fx(hl, "ADBE Glo2", "crt bloom"); R.set(bl, "Glow Threshold", 70); R.set(bl, "Glow Radius", 10); R.set(bl, "Glow Intensity", 0.4);
    var pl = c.layers.add(plate); pl.name = "TV PLATE"; R.scale(pl, S * 100); R.pos(pl, [px, py]);
    try { var key = R.fx(pl, "Keylight 906", "screen key"); R.set(key, "Screen Colour", [tv.key[0] / 255, tv.key[1] / 255, tv.key[2] / 255]); }
    catch (e) { key = R.fx(pl, "ADBE Color Key", "screen key"); R.set(key, "Key Color", [tv.key[0] / 255, tv.key[1] / 255, tv.key[2] / 255]); R.set(key, "Color Tolerance", 60); R.set(key, "Edge Feather", 1.5); }
    R.look(pl);
    var sp = R.cover(c, host, sw * 1.05, sh * 1.05, sx, sy); sp.name = "SCREEN SPILL"; R.place(sp, 0, s["in"], D);
    sp.blendingMode = BlendingMode.SCREEN; R.fx(sp, "ADBE Black&White", "B&W"); R.set(R.fx(sp, "ADBE Gaussian Blur 2", "spill"), "Blurriness", 160); R.opac(sp, 26);
    vignette(c, 40);
    return { comp: c, push: [sx, sy] };
  }
  function hostFull(s) {
    var D = s.t1 - s.t0, c = R.comp(s.id + "_HOST_FULL", W, H, D, FD.shots, [0, 0, 0]);
    var hl = R.cover(c, R.imp(s.file, FD.src), W, H, 960, 540); R.place(hl, 0, s["in"], D); R.look(hl);
    vignette(c, 35);
    return { comp: c, push: [960, 470] };
  }
  var FW = 1500, FH = 844, RAD = 34, PAD = 14;
  function glass(s, enter) {
    var D = s.t1 - s.t0, src = R.imp(s.file, FD.src);
    var fc = R.comp(s.id + "_GLASS_FRAME", W, H, D, FD.shots, [0, 0, 0]);
    var cl = R.cover(fc, src, FW, FH, 960, 540); cl.name = "clip"; R.place(cl, 0, s["in"], D); R.look(cl, s.color);
    var k = R.tr(cl).property("ADBE Scale").value[0];
    R.ease(R.tr(cl).property("ADBE Scale"), 0, [k, k], D, [k * 1.07, k * 1.07], "inout");          // smooth push-in inside the frame
    var pane = R.shape(fc, "glass pane"); R.rrect(pane, FW + 2 * PAD, FH + 2 * PAD, RAD + PAD, [1, 1, 1], 9); pane.moveAfter(cl);
    var mt = R.shape(fc, "clip matte"); R.rrect(mt, FW, FH, RAD, [1, 1, 1], 100); mt.moveBefore(cl); R.matte(cl, mt);
    var bd = R.shape(fc, "glow border"); R.rrect(bd, FW + 2 * PAD, FH + 2 * PAD, RAD + PAD, null, 0, GLOW, 2); R.opac(bd, 80);
    var bg = R.fx(bd, "ADBE Glo2", "border glow"); R.set(bg, "Glow Radius", 18); R.set(bg, "Glow Intensity", 1.6);
    var ib = R.shape(fc, "inner edge"); R.rrect(ib, FW, FH, RAD, null, 0, [1, 1, 1], 1); R.opac(ib, 28);
    var w = R.comp(s.id + "_GLASS", W, H, D, FD.shots, [0, 0, 0]);
    if (!s.in_list) {                                     // the clip itself, huge, blurred and dark: the glass floats over its own light
      var amb = R.cover(w, src, W * 1.25, H * 1.25, 960, 540); amb.name = "ambient light"; R.place(amb, 0, s["in"], D);
      if (!s.color) R.fx(amb, "ADBE Black&White", "B&W");
      var ab = R.fx(amb, "ADBE Gaussian Blur 2", "ambient blur"); R.set(ab, "Blurriness", 90); R.set(ab, "Repeat Edge Pixels", 1);
      R.set(R.fx(amb, "ADBE Exposure2", "ambient dark"), "Exposure", -1.8);
    }
    var fr = w.layers.add(fc); fr.name = "GLASS FRAME";
    var ds = R.fx(fr, "ADBE Drop Shadow", "float shadow"); R.set(ds, "Shadow Color", [0, 0, 0]); R.set(ds, "Opacity", 160); R.set(ds, "Direction", 180); R.set(ds, "Distance", 22); R.set(ds, "Softness", 70);
    R.ease(R.tr(fr).property("ADBE Position"), 0, [960, 546], D, [960, 534], "inout");            // floating
    if (enter) R.ease(R.tr(fr).property("ADBE Scale"), 0, [95, 95], Math.min(F(6), D), [100, 100], "out");   // lands on the cut in 6 frames
    return { comp: w, push: null };
  }
  function typePage(s) {
    var D = s.t1 - s.t0, c = R.comp(s.id + "_TYPE", W, H, D, FD.pages, [0, 0, 0]);
    R.solid(c, R.hex("#050505"), "black");
    var txt = String(s.text).replace(/\n/g, "\r"), lines = txt.split("\r").length;
    var T = R.text(c, txt, { font: FONT.type, size: 76, color: "#F2F2F2", tracking: 0, just: "C", x: 960, y: 560 - (lines - 1) * 50, leading: 100 });
    T.name = "TYPED";
    var r = R.rect(T, 0); if (r.width > 1640) R.scale(T, 1640 / r.width * 100);
    var A = T.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator"); A.name = "typewriter";
    A.property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity").setValue(0);
    var S = A.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
    try { S.property("ADBE Text Range Advanced").property("ADBE Text Selector Smoothness").setValue(0); } catch (e) { R.warn.push("typewriter smoothness: " + e); }
    var ty = Math.min(txt.length * 0.05, D * 0.7);
    var st = S.property("ADBE Text Percent Start"); R.lin(st, F(2), 0); R.lin(st, F(2) + ty, 100);
    var gl = R.fx(T, "ADBE Glo2", "ink glow"); R.set(gl, "Glow Threshold", 50); R.set(gl, "Glow Radius", 12); R.set(gl, "Glow Intensity", 0.5);
    var gn0 = R.solid(c, [1, 1, 1], "grain", D); gn0.adjustmentLayer = true;
    R.set(R.fx(gn0, "ADBE Noise", "grain"), "Amount of Noise", 3);
    vignette(c, 50);
    return { comp: c, push: [960, 540] };
  }
  function giantPage(s) {
    var D = s.t1 - s.t0, c = R.comp(s.id + "_GIANT", W, H, D, FD.pages, [0, 0, 0]);
    var bg = c.layers.add(pageBG()); bg.startTime = 0;
    // stacked from the bottom up: the giant word (fitted to 1560 px), the serif sub-line above it, the red label above that
    var GB = 900, G = R.text(c, String(s.word).toUpperCase(), { font: FONT.black, size: 420, color: "#E6E6E6", tracking: -10, just: "C", x: 960, y: GB });
    G.name = "GIANT " + s.word;
    var gr0 = R.rect(G, 0), gk = Math.max(0.4, Math.min(2.6, 1560 / Math.max(1, gr0.width)));
    if (gr0.height * gk > 560) gk = 560 / gr0.height;
    R.scale(G, gk * 100);
    var top = GB + gr0.top * gk;                          // top of the giant letters in the comp
    if (s.sub) {
      var SB = R.text(c, s.sub, { font: FONT.serifI, size: 110, color: "#FFFFFF", just: "C", x: 960, y: top - 36 });
      SB.name = "SUB"; SB.inPoint = Math.max(0, s.sub_t - s.t0);
      top = top - 36 + R.rect(SB, 0).top;
    }
    if (s.label) {
      var ly = top - 44, LT = R.text(c, s.label, { font: FONT.bold, size: 56, color: "#FFFFFF", just: "C", x: 960, y: ly });
      var lr = R.rect(LT, 0), box = R.shape(c, "label box");
      R.rrect(box, lr.width + 44, lr.height + 26, 6, R.hex("#E5202E"), 100); R.pos(box, [960, ly + lr.top + lr.height / 2]);
      box.moveAfter(LT); LT.name = "LABEL";
      var lt = Math.max(0, s.label_t - s.t0); LT.inPoint = lt; box.inPoint = lt;
    }
    return { comp: c, push: [960, 600], drift: true };
  }
  var CARD = [[490, 315, -5], [1430, 315, 4], [490, 765, 4], [1430, 765, -4]];
  function cardsPage(s) {
    var D = s.t1 - s.t0, c = R.comp(s.id + "_CARDS", W, H, D, FD.pages, [0, 0, 0]);
    var bg = c.layers.add(pageBG()); bg.startTime = 0;
    var CW = 340, CH = 410, IW = 304, IH = 316;
    for (var i = 0; i < s.items.length && i < 4; i++) {
      var it = s.items[i], at = Math.max(0, it.t - s.t0);
      var ic = R.comp(s.id + "_CARD" + (i + 1) + "_IMG", IW, IH, D, FD.pages, [0, 0, 0]);
      var src = R.imp(it.file, FD.src), il = R.cover(ic, src, IW, IH, IW / 2, IH / 2);
      if (src.duration > 0 && !src.mainSource.isStill) R.place(il, at, it["in"], D);
      R.look(il);
      var cc = R.comp(s.id + "_CARD" + (i + 1), CW, CH, D, FD.pages, [0, 0, 0]);
      R.solid(cc, R.hex("#EFEDE6"), "paper");
      var im = cc.layers.add(ic); R.pos(im, [CW / 2, 18 + IH / 2]);
      if (it.logo) {
        var bd = R.shape(cc, "badge"); R.ellipse(bd, 92, R.hex("#F4F4F2"), R.hex("#111111"), 3); R.pos(bd, [CW - 40, 40]);
        var lg = R.imp(it.logo, FD.src), ll = cc.layers.add(lg); R.scale(ll, 54 / Math.max(lg.width, lg.height) * 100); R.pos(ll, [CW - 40, 40]);
      }
      var L = c.layers.add(cc); L.name = "CARD " + (i + 1); L.inPoint = at;
      R.pos(L, [CARD[i][0], CARD[i][1]]); R.tr(L).property("ADBE Rotate Z").setValue(CARD[i][2]);
      var ds = R.fx(L, "ADBE Drop Shadow", "shadow"); R.set(ds, "Opacity", 150); R.set(ds, "Distance", 16); R.set(ds, "Softness", 40);
      R.ease(R.tr(L).property("ADBE Scale"), at, [108, 108], at + F(5), [100, 100], "ref_out");
      if (it.name) {
        var nt = i + 1 < s.items.length ? Math.max(at + F(4), s.items[i + 1].t - s.t0) : D;
        var NL = R.text(c, it.name, { font: FONT.serif, size: 92, color: "#FFFFFF", just: "C", x: 960, y: 600 });
        NL.name = "NAME " + it.name; NL.inPoint = at; NL.outPoint = nt;
      }
    }
    if (s.line) { var LN = R.text(c, s.line, { font: FONT.sans, size: 46, color: "#D0D0D0", just: "C", x: 960, y: 480 }); LN.name = "LINE"; }
    return { comp: c, push: [960, 540] };
  }

  phase("setup + grid");
  // ---------------------------------------------------------------- shots into the master
  var gridL = null;
  if (PG) { gridL = M.layers.add(PG); gridL.name = "LIST GRID"; gridL.startTime = P.list[0]; gridL.inPoint = P.list[0]; gridL.outPoint = P.list[1]; }
  var prevKind = null, nShots = 0, shotLayers = [];
  for (var si = 0; si < P.shots.length; si++) {
    var s = P.shots[si], D = s.t1 - s.t0, b = null;
    if (s.kind === "host") b = (s.mode === "full") ? hostFull(s) : hostTV(s);
    else if (s.kind === "clip") b = glass(s, prevKind !== "clip");
    else if (s.kind === "type") b = typePage(s);
    else if (s.kind === "giant") b = giantPage(s);
    else if (s.kind === "cards") b = cardsPage(s);
    if (!b) { R.warn.push("skipped shot " + s.id + " (" + s.kind + ")"); continue; }
    var L = M.layers.add(b.comp); L.name = s.id + " " + s.kind; L.startTime = s.t0; L.inPoint = s.t0; L.outPoint = s.t1;
    if (b.push) {                                         // slow linear push, 2 % a second (the refs' TV push)
      R.anchor(L, b.push); R.pos(L, b.push);
      var sc = R.tr(L).property("ADBE Scale"); R.lin(sc, s.t0, [100, 100]); R.lin(sc, s.t1, [100 + 2 * D, 100 + 2 * D]);
      if (b.drift) { var pp = R.tr(L).property("ADBE Position"); R.lin(pp, s.t0, b.push); R.lin(pp, s.t1, [b.push[0] - 12 * D, b.push[1]]); }
    }
    shotLayers.push(L); prevKind = s.kind; nShots++;
  }
  phase("shots");
  // bleach-in flash on the cut: exposure +4, +2.2, +0.8, 0 over the first frames of the shot
  var flashes = 0;
  for (var fi = 0; fi < P.shots.length; fi++) {
    var fs = P.shots[fi]; if (!fs.flash || fs.t0 <= 0) continue;
    var FL = M.layers.addSolid([1, 1, 1], "FLASH " + fs.id, W, H, 1, F(4)); FL.adjustmentLayer = true; FL.startTime = fs.t0; FL.inPoint = fs.t0; FL.outPoint = fs.t0 + F(4);
    var ex = R.fx(FL, "ADBE Exposure2", "bleach").property("Exposure"), BX = [4, 2.2, 0.8, 0];
    for (var q = 0; q < 4; q++) R.hold(ex, fs.t0 + F(q), BX[q]);      // key times are composition times
    flashes++;
  }

  // ---------------------------------------------------------------- captions: big spoken words spread across one line
  var C = R.comp("CAPTIONS", W, H, DUR, FD.text, [0, 0, 0]);
  var N = { font: FONT.sans, size: 58, color: "#E6E6E6", tracking: -10 }, K = { font: FONT.bold, size: 82, color: "#FFFFFF", tracking: -20 };
  var AVAIL = 1380, nWords = 0, nFlips = 0;
  function flip(T, t) {                                // the keyword flips (scale Y 100 -> 0 -> 100 over 4 f) and lands in the accent colour
    var A = T.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator"); A.name = "keyword flip";
    A.property("ADBE Text Animator Properties").addProperty("ADBE Text Fill Color");
    A.property("ADBE Text Animator Properties").addProperty("ADBE Text Scale 3D");
    A.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
    var PR = A.property("ADBE Text Animator Properties"), fc = PR.property("ADBE Text Fill Color"), sc = PR.property("ADBE Text Scale 3D");
    R.hold(fc, 0, [1, 1, 1]); R.hold(fc, t + F(2), ACC);
    R.ease(sc, t, [100, 100, 100], t + F(2), [100, 0, 100], "in"); R.ease(sc, t + F(2), [100, 0, 100], t + F(4), [100, 100, 100], "out");
  }
  for (var ci = 0; ci < P.captions.length; ci++) {
    var cp = P.captions[ci], ws = cp.words, Ls = [], wid = [], tot = 0;
    for (var k = 0; k < ws.length; k++) {
      var st = ws[k][2] ? K : N;
      var T = R.text(C, ws[k][1], { font: st.font, size: st.size, color: st.color, tracking: st.tracking, x: 0, y: cp.y, just: "L" });
      var w = R.rect(T, 0).width; wid.push(w); tot += w; Ls.push(T);
      T.name = ("00" + ci).slice(-3) + " " + ws[k][1] + (ws[k][3] ? " FLIP" : (ws[k][2] ? " *" : ""));
      T.inPoint = ws[k][0]; T.outPoint = Math.max(ws[k][0] + F(2), cp.t1);
      if (ws[k][3]) { flip(T, ws[k][0]); nFlips++; }
      else if (ws[k][2]) { var op = R.tr(T).property("ADBE Opacity"), fl = [35, 100, 35, 100, 35, 100]; for (var fq = 0; fq < fl.length; fq++) R.hold(op, ws[k][0] + F(fq), fl[fq]); }
      nWords++;
    }
    var gap = ws.length > 1 ? Math.max(48, Math.min(200, (AVAIL - tot) / (ws.length - 1))) : 0, x = 960 - (tot + gap * (ws.length - 1)) / 2;
    if (tot + gap * (ws.length - 1) > 1760) { var kk = 1760 / (tot + gap * (ws.length - 1)); for (var z = 0; z < Ls.length; z++) R.scale(Ls[z], kk * 100); tot *= kk; gap *= kk; for (var z2 = 0; z2 < wid.length; z2++) wid[z2] *= kk; x = 960 - (tot + gap * (ws.length - 1)) / 2; }
    for (var q2 = 0; q2 < Ls.length; q2++) { R.pos(Ls[q2], [x, cp.y]); x += wid[q2] + gap; }
  }
  phase("captions");
  var cg = R.solid(C, [1, 1, 1], "caption glow"); cg.adjustmentLayer = true; cg.moveToBeginning();
  var gw2 = R.fx(cg, "ADBE Glo2", "bloom"); R.set(gw2, "Glow Threshold", 45); R.set(gw2, "Glow Radius", 14); R.set(gw2, "Glow Intensity", 0.5);
  var CL = M.layers.add(C); CL.name = "CAPTIONS";
  var halo = R.fx(CL, "ADBE Drop Shadow", "halo"); R.set(halo, "Opacity", 200); R.set(halo, "Distance", 0); R.set(halo, "Softness", 60);

  // ---------------------------------------------------------------- cut hits: negative flick, strobe, burn
  var nh = 0;
  function one(name, rgb, t, adj) { var L = M.layers.addSolid(rgb, name, W, H, 1, F(1)); L.adjustmentLayer = !!adj; L.startTime = t; L.inPoint = t; L.outPoint = t + F(1); nh++; return L; }
  for (var h = 0; h < P.hits.length; h++) {
    var hv = P.hits[h], t = hv.t;
    if (hv.type === "invert") { R.fx(one("HIT negative", [1, 1, 1], t - F(1), true), "ADBE Invert", "negative"); R.set(R.fx(one("HIT dip", [1, 1, 1], t + F(1), true), "ADBE Easy Levels2", "dip"), "Output White", 0.1); }
    else if (hv.type === "strobe") { var SQ = [[1, 1, 1], [0, 0, 0], [1, 1, 1], [0, 0, 0], [1, 1, 1]]; for (var sq = 0; sq < SQ.length; sq++) one("HIT strobe", SQ[sq], t + (sq - 3) * F(1)); }
    else if (hv.type === "burn") {
      for (var bq = 0; bq < 2; bq++) { var bL = one("HIT burn", [1, 1, 1], t - F(1) + bq * F(1), true); R.set(R.fx(bL, "ADBE Exposure2", "burn"), "Exposure", bq ? 1.8 : 2.6); R.set(R.fx(bL, "ADBE Posterize", "posterize"), "Level", 6); var bg2 = R.fx(bL, "ADBE Glo2", "glow"); R.set(bg2, "Glow Radius", 80); R.set(bg2, "Glow Intensity", 2); }
    }
  }
  // ---------------------------------------------------------------- film grain over everything
  var gn = R.solid(M, [1, 1, 1], "FILM GRAIN"); gn.adjustmentLayer = true; gn.moveToBeginning();
  R.set(R.fx(gn, "ADBE Noise", "grain"), "Amount of Noise", 2);

  phase("hits + grain");
  // ---------------------------------------------------------------- sound
  var VO = M.layers.add(R.imp(P.voice, FD.audio)); VO.name = "VOICE"; VO.startTime = 0; VO.moveToEnd();
  if (P.music) {
    var MU = M.layers.add(R.imp(P.music, FD.audio)); MU.name = "MUSIC"; MU.startTime = 0; MU.outPoint = Math.min(DUR, MU.outPoint); MU.moveToEnd();
    var ml = R.levels(MU), g = P.music_db, e0 = Math.min(DUR, MU.outPoint);
    R.lin(ml, 0, [-60, -60]); R.lin(ml, 0.4, [g, g]); R.lin(ml, Math.max(0.5, e0 - 1.5), [g, g]); R.lin(ml, e0, [-60, -60]);
  }
  var SX = R.comp("SFX", 100, 100, DUR, FD.audio, [0, 0, 0]), nsfx = 0;
  for (var xi = 0; xi < P.sfx.length; xi++) {
    var ev = P.sfx[xi], f = new File(P.sfx_dir + "/" + ev.name + ".wav");
    if (!f.exists) { R.warn.push("missing sfx " + ev.name); continue; }
    var SL = SX.layers.add(R.imp(f.fsName, FD.audio)); SL.name = ev.name + " " + ev.t.toFixed(2);
    SL.startTime = Math.max(0, ev.t); if (ev.len) SL.outPoint = Math.min(SL.outPoint, SL.startTime + ev.len);
    R.levels(SL).setValue([ev.db, ev.db]); nsfx++;
  }
  var SXL = M.layers.add(SX); SXL.name = "SFX"; SXL.startTime = 0; SXL.moveToEnd();

  phase("sound");
  app.endUndoGroup();
  try { idle.remove(); } catch (e) { }
  R.textDone();
  app.project.save(want);
  R.log("REEL built: " + DUR.toFixed(2) + " s, " + nShots + " shots, " + flashes + " flashes, " + nWords + " caption words (" + nFlips + " keyword flips), " + nh + " hit frames, " + nsfx + " sfx");
  R.log("fonts: " + FONT.sans + " / " + FONT.bold + " / " + FONT.black + " / " + FONT.serif + " / " + FONT.type);
  R.log("saved " + want.fsName + " in " + ((new Date().getTime() - t00) / 1000).toFixed(1) + " s");
  for (var wi = 0; wi < R.warn.length; wi++) R.log("WARN " + R.warn[wi]);
})();
