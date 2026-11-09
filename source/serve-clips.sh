#!/usr/bin/env bash
# The video source: serve a folder of .mp4 clips over plain HTTP from a MacBook (or any box with python3).
#   bash source/serve-clips.sh [CLIP_DIR] [PORT]
# CLIP_DIR defaults to this repo's sample/, PORT to 8787. Binds every interface so the edge box
# can reach it; stop it with Ctrl-C. python3's http.server serves no byte ranges, so a reader
# downloads a clip whole before it opens it (scripts/fetch-clips.sh and NanoStream both do).
set -euo pipefail
DIR=${1:-$(cd "$(dirname "$0")/.." && pwd)/sample}
PORT=${2:-8787}
cd "$DIR"
n=$(find . -maxdepth 1 -name '*.mp4' | wc -l | tr -d ' ')
[ "$n" -gt 0 ] || { echo "no .mp4 in $DIR" >&2; exit 1; }
ip=$( (ipconfig getifaddr en0 || hostname -I | awk '{print $1}') 2>/dev/null || echo "<this-host>")
echo "serving $n clip(s) from $DIR at http://$ip:$PORT/"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
