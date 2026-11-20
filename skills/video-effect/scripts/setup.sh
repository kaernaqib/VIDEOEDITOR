#!/usr/bin/env bash
# One-time setup for the video-effect skill. Safe to run again: it prints READY when everything is in place.
# Works on Mac/Linux (.venv/bin/python) and Windows Git Bash (.venv/Scripts/python.exe).
set -e
cd "$(dirname "$0")/.."

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "NEED_FFMPEG: install ffmpeg first (Mac: brew install ffmpeg, Windows: winget install ffmpeg)"; exit 1
fi

venv_py() { if [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; else echo .venv/bin/python; fi; }

VP="$(venv_py)"
if [ -x "$VP" ] && "$VP" -c "import mediapipe, cv2, PIL, numpy" 2>/dev/null; then echo READY; exit 0; fi

PY=""
for v in python3.12 python3.11 python3.13 python3.10 python3 python py; do
  if command -v "$v" >/dev/null 2>&1 && "$v" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then PY="$v"; break; fi
done

if [ -n "$PY" ]; then
  "$PY" -m venv .venv
  VP="$(venv_py)"
  "$VP" -m pip install -q --upgrade pip
  "$VP" -m pip install -q -r requirements.txt
elif command -v uv >/dev/null 2>&1; then
  uv venv -q -p 3.12 .venv
  VP="$(venv_py)"
  uv pip install -q -p "$VP" -r requirements.txt
else
  echo "NEED_PYTHON: install Python 3.10 or newer (python.org/downloads), then run this again"; exit 1
fi

"$VP" -c "import mediapipe, cv2, PIL, numpy; print('READY')"
