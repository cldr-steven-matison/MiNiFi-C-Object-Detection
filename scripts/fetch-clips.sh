#!/usr/bin/env bash
# Pull the clips a video source serves into the agent's ListFile folder, one at a time.
#   bash scripts/fetch-clips.sh http://<mac>:8787/ [CLIPS_DIR] [--watch]
# CLIPS_DIR defaults to $WORK_DIR/clips (/tmp/minifi-detect/clips). Each clip downloads to a hidden
# .part file in the same folder and is renamed when it is complete, so ListFile (File Filter .*\.mp4)
# never lists a half-written clip. A clip already in the folder, or in clips/done, is skipped.
# --watch polls the source every 30 s for new clips, and keeps polling while the source is away.
# Without --watch, the exit code is 1 if the source or any clip could not be fetched.
set -euo pipefail
SRC=${1:?usage: fetch-clips.sh http://<source>:8787/ [CLIPS_DIR] [--watch]}
SRC=${SRC%/}/
DST=${2:-${WORK_DIR:-/tmp/minifi-detect}/clips}
WATCH=${3:-}
[ "$DST" = --watch ] && { WATCH=--watch; DST=${WORK_DIR:-/tmp/minifi-detect}/clips; }
mkdir -p "$DST"
pass() {
  local list href name rc=0
  # --connect-timeout: a source that is asleep or off the network drops packets instead of refusing them
  list=$(curl -fsS --connect-timeout 10 "$SRC") || { echo "source $SRC is not reachable" >&2; return 1; }
  while read -r href; do
    name=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))' "$href")
    if [ -e "$DST/$name" ] || [ -e "$DST/done/$name" ]; then continue; fi
    echo "fetching $name"
    # a download that fails part-way never becomes a clip: the .part is dropped, not renamed
    if curl -fsS --connect-timeout 10 -o "$DST/.$name.part" "$SRC$href"; then
      mv "$DST/.$name.part" "$DST/$name"
      echo "ready    $DST/$name ($(du -h "$DST/$name" | cut -f1))"
    else
      rm -f "$DST/.$name.part"
      echo "failed   $name" >&2
      rc=1
    fi
  done < <(grep -o 'href="[^"]*\.mp4"' <<<"$list" | sed 's/^href="//; s/"$//')
  return $rc
}
if [ "$WATCH" != --watch ]; then
  pass
  exit
fi
while true; do
  pass || true
  sleep 30
done
