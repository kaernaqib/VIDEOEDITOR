// reel_lib.jsx — helpers for build_reel.jsx (After Effects ExtendScript, ES3: no let/const/arrow/map/forEach/JSON).
// Native keyframes only, no expressions.
$.global.R = (function () {
  var R = {};
  R.FPS = 25;
  R.warn = [];
  R.log = function (s) { try { aeLog(String(s)); } catch (e) { $.writeln(String(s)); } };
  R.readJSON = function (path) {
    var f = new File(path); f.encoding = "UTF-8";
    if (!f.open("r")) throw new Error("cannot read " + path);
    var s = f.read(); f.close();
    return eval("(" + s + ")");                     // our own plan file (written by reel.py)
  };
  R.findItem = function (name, ctor) {
    for (var i = 1; i <= app.project.numItems; i++) { var it = app.project.item(i); if (it.name === name && (!ctor || it instanceof ctor)) return it; }
    return null;
  };
  R.folder = function (name) { var f = R.findItem(name, FolderItem); return f || app.project.items.addFolder(name); };
  R.comp = function (name, w, h, dur, folder, bg) {
    var c = app.project.items.addComp(name, w, h, 1, Math.max(1 / R.FPS, dur), R.FPS);
    if (folder) c.parentFolder = folder;
    c.bgColor = bg || [0, 0, 0];
    return c;
  };
  R.hex = function (h) { h = h.replace("#", ""); return [parseInt(h.substr(0, 2), 16) / 255, parseInt(h.substr(2, 2), 16) / 255, parseInt(h.substr(4, 2), 16) / 255]; };
  R.solid = function (c, rgb, name, dur) { var L = c.layers.addSolid(rgb, name, c.width, c.height, 1, dur || c.duration); return L; };
  R.fx = function (L, match, name) { var e = L.property("ADBE Effect Parade").addProperty(match); if (name) e.name = name; return e; };
  R.set = function (eff, key, val) { try { eff.property(key).setValue(val); return true; } catch (e) { R.warn.push("set " + eff.name + "." + key + ": " + e); return false; } };
  R.tr = function (L) { return L.property("ADBE Transform Group"); };
  R.pos = function (L, xy) { R.tr(L).property("ADBE Position").setValue(xy); };
  R.scale = function (L, s) { R.tr(L).property("ADBE Scale").setValue([s, s]); };
  R.opac = function (L, o) { R.tr(L).property("ADBE Opacity").setValue(o); };
  R.anchor = function (L, xy) { R.tr(L).property("ADBE Anchor Point").setValue(xy); };
  // a HOLD key for frame N goes half a frame before N, so float error and motion blur never blend two states
  R.snap = function (t) { var f = t * R.FPS, r = Math.round(f); return Math.abs(f - r) < 0.02 ? Math.max(0, (r - 0.5) / R.FPS) : t; };
  R.hold = function (p, t, v) { t = R.snap(t); var k = p.addKey(t); p.setValueAtKey(k, v); p.setInterpolationTypeAtKey(k, KeyframeInterpolationType.HOLD, KeyframeInterpolationType.HOLD); return k; };
  R.lin = function (p, t, v) { var k = p.addKey(t); p.setValueAtKey(k, v); p.setInterpolationTypeAtKey(k, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR); return k; };
  // eases as cubic-bezier [x1, y1, x2, y2] turned into native temporal ease
  R.CURVE = { out: [0.22, 1, 0.36, 1], "in": [0.64, 0, 0.78, 0], inout: [0.83, 0, 0.17, 1], soft: [0.76, 0, 0.24, 1], ref_out: [0.05, 0, 0.05, 1] };
  R.ease = function (prop, t0, v0, t1, v1, type) {
    var b = R.CURVE[type || "inout"], T = Math.max(1e-3, t1 - t0), PT = prop.propertyValueType;
    var spatial = (PT === PropertyValueType.TwoD_SPATIAL || PT === PropertyValueType.ThreeD_SPATIAL);
    var n = (PT === PropertyValueType.TwoD) ? 2 : (PT === PropertyValueType.ThreeD ? 3 : 1);
    function pad(v) { if (!(v instanceof Array) || spatial || v.length >= n) return v; var c = v.slice(0); while (c.length < n) c.push(100); return c; }   // 2D scale [x, y] -> [x, y, 100]
    v0 = pad(v0); v1 = pad(v1);
    prop.setValueAtKey(prop.addKey(t0), v0); prop.setValueAtKey(prop.addKey(t1), v1);
    var k0 = prop.nearestKeyIndex(t0), k1 = prop.nearestKeyIndex(t1), avg = [], i;
    if (spatial) { var m = 0; for (i = 0; i < v0.length; i++) m += (v1[i] - v0[i]) * (v1[i] - v0[i]); avg = [Math.sqrt(m) / T]; }
    else if (n === 1) avg = [(PT === PropertyValueType.OneD) ? (v1 - v0) / T : 0];
    else for (i = 0; i < n; i++) avg.push((v1[i] - v0[i]) / T);
    var s0 = b[0] > 0 ? b[1] / b[0] : 0, s1 = b[2] < 1 ? (1 - b[3]) / (1 - b[2]) : 0, o0 = [], i1 = [];
    for (i = 0; i < avg.length; i++) {
      o0.push(new KeyframeEase(avg[i] * s0, Math.max(0.1, Math.min(100, b[0] * 100))));
      i1.push(new KeyframeEase(avg[i] * s1, Math.max(0.1, Math.min(100, (1 - b[2]) * 100))));
    }
    prop.setInterpolationTypeAtKey(k0, prop.keyInInterpolationType(k0), KeyframeInterpolationType.BEZIER);
    prop.setInterpolationTypeAtKey(k1, KeyframeInterpolationType.BEZIER, prop.keyOutInterpolationType(k1));
    prop.setTemporalEaseAtKey(k0, prop.keyInTemporalEase(k0), o0);
    prop.setTemporalEaseAtKey(k1, i1, prop.keyOutTemporalEase(k1));
    if (spatial) {
      var z = [], nv = prop.keyValue(k0).length; for (i = 0; i < nv; i++) z.push(0);
      prop.setSpatialAutoBezierAtKey(k0, false); prop.setSpatialAutoBezierAtKey(k1, false);
      prop.setSpatialContinuousAtKey(k0, false); prop.setSpatialContinuousAtKey(k1, false);
      prop.setSpatialTangentsAtKey(k0, prop.keyInSpatialTangent(k0), z);
      prop.setSpatialTangentsAtKey(k1, z, prop.keyOutSpatialTangent(k1));
    }
    return k1;
  };
  // fonts: the first installed PostScript name of a list
  R._fontOK = {};
  R.font = function (cands) {
    for (var i = 0; i < cands.length; i++) {
      var n = cands[i];
      if (R._fontOK[n] === undefined) {
        var ok = false;
        try { var fs = app.fonts.getFontsByPostScriptName(n); ok = !!(fs && fs.length); } catch (e) {
          try {
            var tc = app.project.items.addComp("__fonttest", 8, 8, 1, 1, 25), tl = tc.layers.addText("A"), sp = tl.property("ADBE Text Properties").property("ADBE Text Document"), td = sp.value;
            td.font = n; sp.setValue(td); td = sp.value; ok = (td.font === n); try { if (td.fontObject.isSubstitute) ok = false; } catch (e3) { }
            tc.remove();
          } catch (e2) { ok = false; }
        }
        R._fontOK[n] = ok;
      }
      if (R._fontOK[n]) return n;
    }
    R.warn.push("none of the fonts installed: " + cands.join(", "));
    return cands[cands.length - 1];
  };
  // text layer: o = {font, size, color, tracking, just: "L"|"C"|"R", x, y, leading}
  // A new text layer can cost ~1.7 s in AE 2025-26 (font set-up), while copying a styled one and setting its string costs ~0.1 s.
  // So each style is made once in a hidden comp (__text_styles) and copied wherever it is needed.
  R._proto = {}; R._protoComp = null;
  R.text = function (c, str, o) {
    var key = [o.font, o.size, o.color || "#FFFFFF", o.tracking || 0, o.just || "C", o.leading || 0].join("|"), P = R._proto[key];
    if (!P) {
      if (!R._protoComp) { R._protoComp = app.project.items.addComp("__text_styles", 100, 100, 1, 3600, R.FPS); }
      P = R._protoComp.layers.addText("x");
      var sp = P.property("ADBE Text Properties").property("ADBE Text Document"), td = sp.value;
      td.resetCharStyle(); td.resetParagraphStyle();
      td.font = o.font; td.fontSize = o.size; td.applyFill = true; td.fillColor = R.hex(o.color || "#FFFFFF"); td.applyStroke = false;
      td.tracking = o.tracking || 0;
      if (o.leading) { try { td.autoLeading = false; td.leading = o.leading; } catch (e) { } }
      td.justification = o.just === "L" ? ParagraphJustification.LEFT_JUSTIFY : (o.just === "R" ? ParagraphJustification.RIGHT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY);
      sp.setValue(td);
      R._proto[key] = P;
    }
    P.name = "__copy__";                                // the copy keeps the source's layer index, not the top: find it by name
    P.copyToComp(c);
    P.name = "__style";
    var L = (c.layer(1).name === "__copy__") ? c.layer(1) : null;
    for (var i = 1; !L && i <= c.numLayers; i++) if (c.layer(i).name === "__copy__") L = c.layer(i);
    if (!L) throw new Error("text copy not found in " + c.name);
    L.name = String(str).substr(0, 60);
    if (L.index !== 1) L.moveToBeginning();             // like addText: the new layer is on top
    L.startTime = 0; L.inPoint = 0; L.outPoint = c.duration;
    L.property("ADBE Text Properties").property("ADBE Text Document").setValue(str);
    R.pos(L, [o.x, o.y]);
    return L;
  };
  R.textDone = function () { try { if (R._protoComp) R._protoComp.remove(); } catch (e) { } R._protoComp = null; R._proto = {}; };
  R.rect = function (L, t) { return L.sourceRectAtTime(t || 0, false); };
  R.shape = function (c, name) { var L = c.layers.addShape(); L.name = name; R.anchor(L, [0, 0]); R.pos(L, [c.width / 2, c.height / 2]); return L; };
  R.rrect = function (L, w, h, r, fill, fillOp, stroke, sw) {
    var g = L.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group").property("ADBE Vectors Group");
    var rc = g.addProperty("ADBE Vector Shape - Rect"); rc.property("ADBE Vector Rect Size").setValue([w, h]); rc.property("ADBE Vector Rect Position").setValue([0, 0]); rc.property("ADBE Vector Rect Roundness").setValue(r);
    if (fill) { var f = g.addProperty("ADBE Vector Graphic - Fill"); f.property("ADBE Vector Fill Color").setValue(fill); f.property("ADBE Vector Fill Opacity").setValue(fillOp); }
    if (stroke) { var s = g.addProperty("ADBE Vector Graphic - Stroke"); s.property("ADBE Vector Stroke Color").setValue(stroke); s.property("ADBE Vector Stroke Width").setValue(sw); }
  };
  R.ellipse = function (L, d, fill, stroke, sw) {
    var g = L.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group").property("ADBE Vectors Group");
    g.addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([d, d]);
    if (fill) g.addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(fill);
    if (stroke) { var s = g.addProperty("ADBE Vector Graphic - Stroke"); s.property("ADBE Vector Stroke Color").setValue(stroke); s.property("ADBE Vector Stroke Width").setValue(sw); }
  };
  R.matte = function (layer, matteLayer) {
    try { layer.setTrackMatte(matteLayer, TrackMatteType.ALPHA); } catch (e) { matteLayer.moveBefore(layer); layer.trackMatteType = TrackMatteType.ALPHA; }
    matteLayer.enabled = false;
  };
  // footage import, once per file
  R._imp = {};
  R.imp = function (path, folder) {
    var f = new File(path);
    if (R._imp[f.fsName]) return R._imp[f.fsName];
    if (!f.exists) throw new Error("missing file " + path);
    var it = app.project.importFile(new ImportOptions(f));
    if (folder) it.parentFolder = folder;
    R._imp[f.fsName] = it;
    return it;
  };
  // a footage layer scaled to COVER w x h, centred at (x, y)
  R.cover = function (c, item, w, h, x, y) {
    var L = c.layers.add(item); R.scale(L, Math.max(w / item.width, h / item.height) * 100); R.pos(L, [x, y]);
    try { L.audioEnabled = false; } catch (e) { }
    return L;
  };
  // footage time: the layer shows source time `srcIn` at comp time `at`; too-short footage holds its last frame
  R.place = function (L, at, srcIn, until) {
    var dur = L.source.duration, need = until - at;
    if (srcIn + need > dur + 1e-3) {
      var s2 = Math.max(0, dur - need);
      if (dur >= need) srcIn = s2;
      else { srcIn = 0; R.warn.push(L.source.name + " is " + dur.toFixed(2) + " s, shorter than its " + need.toFixed(2) + " s shot: last frame held"); L.timeRemapEnabled = true; }
    }
    L.startTime = at - srcIn; L.inPoint = at; L.outPoint = until;
    return L;
  };
  // archival black-and-white look on a footage layer
  R.look = function (L, colour) {
    if (!colour) R.fx(L, "ADBE Black&White", "B&W");
    var lv = R.fx(L, "ADBE Easy Levels2", "contrast"); R.set(lv, "Input Black", 0.05); R.set(lv, "Input White", 0.9); R.set(lv, "Gamma", 0.93);
    var nz = R.fx(L, "ADBE Noise", "grain"); R.set(nz, "Amount of Noise", 2.5); R.set(nz, "Noise Type", 0);
  };
  R.levels = function (L) { return L.property("ADBE Audio Group").property("ADBE Audio Levels"); };
  return R;
})();
