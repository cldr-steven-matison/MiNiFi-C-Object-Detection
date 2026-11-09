#!/usr/bin/env bash
# The pass check: for N frames in, N annotated images in out/, N JSON sidecars in meta/, nothing in fail/.
#   bash scripts/check-run.sh [WORK_DIR]
W=${1:-${WORK_DIR:-/tmp/minifi-detect}}
out=$(find "$W/out" -name '*.jpg' 2>/dev/null | wc -l | tr -d ' ')
meta=$(find "$W/meta" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
fail=$(find "$W/fail" -type f 2>/dev/null | wc -l | tr -d ' ')
echo "annotated $out  json $meta  failures $fail"
find "$W/fail" -type f 2>/dev/null | head -5 | sed 's/^/  fail: /'
python3 - "$W/meta" <<'PY'
import glob, json, sys, collections
COCO = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck", 9: "traffic light", 11: "stop sign"}
boxes, scenes = collections.Counter(), collections.Counter()
for f in glob.glob(sys.argv[1] + "/*.json"):
    d = json.load(open(f))
    det = d.get("detections") or "[]"; det = json.loads(det) if isinstance(det, str) else det
    sc = d.get("scene") or "[]"; sc = json.loads(sc) if isinstance(sc, str) else sc
    for b in det: boxes[COCO.get(b["class_id"], f"class {b['class_id']}")] += 1
    if sc: scenes[sc[0]["class_name"]] += 1
if boxes: print("boxes  ", ", ".join(f"{k} {v}" for k, v in boxes.most_common()))
if scenes: print("scene  ", ", ".join(f"{k} {v}" for k, v in scenes.most_common(5)))
PY
if [ "$out" -gt 0 ] && [ "$out" = "$meta" ] && [ "$fail" = 0 ]; then
  echo PASS
else
  echo "NOT YET (or FAIL)"
  exit 1
fi
