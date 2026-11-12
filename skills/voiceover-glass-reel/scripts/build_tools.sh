#!/bin/zsh
# build_tools.sh — compiles the Swift helpers into scripts/bin (once per Mac). Needs the Xcode command line tools.
set -e
HERE="${0:A:h}"
mkdir -p "$HERE/bin"
command -v swiftc >/dev/null || { echo "swiftc not found: run  xcode-select --install  and try again" >&2; exit 2; }
for t in to_wav transcribe facebox frames; do
  if [[ ! -x "$HERE/bin/$t" || "$HERE/tools/$t.swift" -nt "$HERE/bin/$t" ]]; then
    echo "building $t"
    extra=()
    [[ -f "$HERE/tools/${t}_Info.plist" ]] && extra=(-Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$HERE/tools/${t}_Info.plist")
    swiftc -O "$HERE/tools/$t.swift" -o "$HERE/bin/$t" "${extra[@]}"
  fi
done
echo "tools ready in $HERE/bin"
