#!/bin/zsh
# build.sh <project dir>  — builds (or rebuilds) the reel in After Effects from <project dir>/work/plan.json.
# Creates <project dir>/reel.aep (never touches another open project: if one has unsaved changes the build stops).
set -u
HERE="${0:A:h}"
PROJ="${1:A}"
PLAN="$PROJ/work/plan.json"
[[ -f "$PLAN" ]] || { echo "no $PLAN: run reel.py plan first" >&2; exit 2; }
JSX="$PROJ/work/_build.jsx"
esc() { print -r -- "${1//\\/\\\\}" | sed 's/"/\\"/g'; }
cat > "$JSX" <<EOF
\$.global.REEL_PLAN = "$(esc "$PLAN")";
\$.global.REEL_AE = "$(esc "$HERE/ae")";
\$.evalFile(new File(\$.global.REEL_AE + "/build_reel.jsx"));
EOF
"$HERE/ae_run.sh" "$JSX" 1800
