#!/bin/zsh
# render.sh <project dir> [out.mp4] [--half]
# Saves reel.aep and renders its comp REEL with aerender (a separate process: AE stays usable).
# Full quality: H.264 1920x1080 25 fps ~40 Mbps with sound. --half = quick half-resolution check.
set -u
HERE="${0:A:h}"
PROJ="${1:A}"; OUT="${2:-$PROJ/out/reel_1080.mp4}"; HALF=0
for a in "$@"; do [[ "$a" == "--half" ]] && HALF=1; done
[[ "$OUT" == "--half" ]] && OUT="$PROJ/out/reel_half.mp4"
OUT="${OUT:A}"
AEP="$PROJ/reel.aep"
[[ -f "$AEP" ]] || { echo "no $AEP: run build.sh first" >&2; exit 2; }
if [[ -z "${AE_APP:-}" ]]; then
  APPDIR=$(ls -d /Applications/Adobe\ After\ Effects\ 20*/Adobe\ After\ Effects\ 20*.app 2>/dev/null | sort | tail -1)
  export AE_APP="${${APPDIR:t}%.app}"
fi
AERENDER="${AERENDER:-/Applications/$AE_APP/aerender}"
[[ -x "$AERENDER" ]] || { echo "no aerender at $AERENDER (set AERENDER)" >&2; exit 2; }
esc() { print -r -- "${1//\\/\\\\}" | sed 's/"/\\"/g'; }
PREP="$PROJ/work/_render_prep.jsx"
cat > "$PREP" <<EOF
var p = app.project, want = File("$(esc "$AEP")");
if (!p.file || p.file.fsName !== want.fsName) { if (p.dirty && p.numItems > 0) throw new Error("another project with unsaved changes is open: save or close it first"); app.open(want); p = app.project; }
var c = null; for (var i = 1; i <= p.numItems; i++) if (p.item(i) instanceof CompItem && p.item(i).name === "REEL") c = p.item(i);
if (!c) throw new Error("comp REEL not found in reel.aep");
var rq = p.renderQueue.items.add(c), om = rq.outputModule(1);
function has(l, t) { for (var k = 0; k < l.length; k++) if (l[k] === t) return true; return false; }
var omName = "";
var cands = ["H.264 - Match Render Settings - 40 Mbps", "H.264 - Match Render Settings - 15 Mbps", "High Quality"];
for (var j = 0; j < cands.length; j++) if (has(om.templates, cands[j])) { omName = cands[j]; break; }
if (!has(rq.templates, "reel_Half")) { rq.applyTemplate("Best Settings"); rq.setSettings({ "Resolution": "Half" }); rq.saveAsTemplate("reel_Half"); }
rq.remove();
p.save();
aeLog("OM " + omName);
EOF
PREP_OUT=$("$HERE/ae_run.sh" "$PREP" 300) || { print -r -- "$PREP_OUT"; echo "render prep failed" >&2; exit 3; }
OM=$(print -r -- "$PREP_OUT" | sed -n 's/^OM //p' | tail -1)
[[ -n "$OM" ]] || { echo "no H.264 output template in this After Effects" >&2; exit 3; }
[[ "$OM" == "High Quality" ]] && OUT="${OUT%.mp4}.mov"
RS="Best Settings"; (( HALF )) && RS="reel_Half"
mkdir -p "${OUT:h}"
LOG="$PROJ/work/aerender.log"
echo "rendering REEL -> $OUT ($RS, $OM); log $LOG"
"$AERENDER" -project "$AEP" -comp "REEL" -RStemplate "$RS" -OMtemplate "$OM" -output "$OUT" -v ERRORS_AND_PROGRESS > "$LOG" 2>&1
RC=$?
tail -3 "$LOG"
(( RC == 0 )) || { echo "aerender exit $RC (see $LOG)" >&2; exit $RC; }
echo "done: $OUT"
