#!/usr/bin/env bash
# Flow v1's zero-code video-to-frames leg: ExecuteProcess runs this on a timer. Every clip in
# $WORK_DIR/clips becomes JPEG frames in $WORK_DIR/in/<stem>__<n>.jpg, then moves to clips/done so
# the next run skips it. Uses only ffmpeg flags that NVIDIA's Jetson build and Ubuntu's apt build
# both have. FPS / MAX_SECONDS from the environment, default 2 and 60.
set -u
W=${WORK_DIR:-/tmp/minifi-detect}; FPS=${FPS:-2}; MAX=${MAX_SECONDS:-60}
mkdir -p "$W/clips/done" "$W/in" "$W/.frames"
for f in "$W"/clips/*.mp4; do
  [ -e "$f" ] || continue
  stem=$(basename "$f" .mp4)
  rm -rf "$W/.frames/$stem"; mkdir -p "$W/.frames/$stem"
  if ffmpeg -hide_banner -loglevel error -nostdin -t "$MAX" -i "$f" -vf "fps=$FPS" -q:v 3 \
       "$W/.frames/$stem/${stem}__%06d.jpg"; then
    mv "$W/.frames/$stem"/*.jpg "$W/in/" && rmdir "$W/.frames/$stem"
    mv "$f" "$W/clips/done/"
    echo "frames: $stem ok"
  else
    echo "frames: ffmpeg failed on $stem" >&2
  fi
done
