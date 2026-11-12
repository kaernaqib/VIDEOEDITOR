#!/bin/zsh
# ae_run.sh <script.jsx> [timeoutSec=900]
# Sends one ExtendScript file to the running After Effects and waits for it. The only way this skill talks to AE.
#   Inside the script use  aeLog("text")  to report (DoScript return values are useless). Printed here when AE finishes.
# Env: AE_APP (app name, default: newest "Adobe After Effects 20xx" in /Applications), AE_LOCK_ROOT (lock + logs).
# Exit: 0 ok · 3 script threw (ERROR line) · 4 AE still running it after the timeout (do NOT resend; wait, then check the log)
#       5 lock busy · 6 AE never started it (not running / modal dialog open) — safe to resend after fixing that.
set -u
ROOT="${AE_LOCK_ROOT:-$HOME/Library/Caches/voiceover-glass-reel/ae}"
LOCK="$ROOT/lock"
if [[ -z "${AE_APP:-}" ]]; then
  APPDIR=$(ls -d /Applications/Adobe\ After\ Effects\ 20*/Adobe\ After\ Effects\ 20*.app 2>/dev/null | sort | tail -1)
  [[ -n "$APPDIR" ]] || { echo "[ae_run] After Effects not found in /Applications (set AE_APP)" >&2; exit 2; }
  AE_APP="${${APPDIR:t}%.app}"
fi
[[ $# -ge 1 ]] || { echo "usage: ae_run.sh <script.jsx> [timeoutSec]" >&2; exit 2; }
SCRIPT="${1:A}"; TIMEOUT="${2:-900}"
[[ -f "$SCRIPT" ]] || { echo "no such script: $SCRIPT" >&2; exit 2; }
mkdir -p "$ROOT/out" "$ROOT/wrap"

# ---------- lock (one script at a time per Mac); a lock older than 30 min or of a dead process is taken over
waited=0
while ! mkdir "$LOCK" 2>/dev/null; do
  pid=$(cat "$LOCK/pid" 2>/dev/null); age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || date +%s) ))
  if (( age > 1800 )) || { [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null && [[ ! -f "$LOCK/timeout" ]]; }; then
    rm -rf "$LOCK"; continue
  fi
  (( waited == 0 )) && echo "[ae_run] waiting for another AE script to finish" >&2
  sleep 2; waited=$(( waited + 2 ))
  (( waited > 1800 )) && { echo "[ae_run] gave up waiting for the lock" >&2; exit 5; }
done
print -r -- $$ > "$LOCK/pid"
KEEP=0
trap '[[ $KEEP == 0 ]] && rm -rf "$LOCK"' EXIT
trap 'exit 130' INT TERM

STAMP=$(date +%Y%m%d_%H%M%S)_$$
OUT="$ROOT/out/${SCRIPT:t:r}_${STAMP}.txt"; WRAP="$ROOT/wrap/${SCRIPT:t:r}_${STAMP}.jsx"
: > "$OUT"
esc() { print -r -- "${1//\\/\\\\}" | sed 's/"/\\"/g'; }
cat > "$WRAP" <<EOF
(function(){
  var __o = "$(esc "$OUT")";
  if (File(__o + ".cancel").exists) return;
  function __w(s){ var f = new File(__o); f.encoding = "UTF-8"; f.lineFeed = "Unix"; f.open("a"); f.writeln(String(s)); f.close(); }
  __w("__START__");
  \$.global.aeLog = __w;
  \$.global.AE_SCRIPT_PATH = "$(esc "$SCRIPT")";
  var t0 = new Date().getTime();
  app.beginSuppressDialogs();
  try { \$.evalFile(new File(\$.global.AE_SCRIPT_PATH)); }
  catch (e) { __w("ERROR: " + e.toString() + " | line " + e.line + " | " + (e.fileName ? File(e.fileName).name : "")); }
  try { app.endSuppressDialogs(false); } catch (e2) {}
  __w("__DONE__ " + ((new Date().getTime() - t0) / 1000).toFixed(1) + " s");
})();
EOF
osascript -e "with timeout of $TIMEOUT seconds" -e "tell application \"$AE_APP\" to DoScriptFile \"$WRAP\"" -e "end timeout" >/dev/null 2>"$OUT.osa" &
OSA=$!
n=0
while ! grep -q "^__START__" "$OUT" && (( n < 160 )); do
  if ! kill -0 $OSA 2>/dev/null && (( n < 148 )); then n=148; fi
  sleep 0.25; n=$(( n + 1 ))
done
if ! grep -q "^__START__" "$OUT"; then
  : > "$OUT.cancel"; kill $OSA 2>/dev/null
  echo "[ae_run] AE did not start the script (is After Effects open, with no dialog showing? $(cat "$OUT.osa" 2>/dev/null))" >&2
  echo "[ae_run] Also check: Settings > Scripting & Expressions > Allow Scripts to Write Files and Access Network." >&2
  exit 6
fi
wait $OSA 2>/dev/null
for i in {1..30}; do grep -q "__DONE__" "$OUT" && break; sleep 2; done
grep -v "^__START__" "$OUT"
if ! grep -q "__DONE__" "$OUT"; then
  echo "[ae_run] AE is still running the script; the lock stays until it finishes. Do NOT resend. Log: $OUT" >&2
  KEEP=1; : > "$LOCK/timeout"; exit 4
fi
rm -f "$WRAP" "$OUT.osa"
grep -q "^ERROR: " "$OUT" && exit 3
exit 0
