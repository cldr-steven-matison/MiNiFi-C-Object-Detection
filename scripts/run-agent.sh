#!/usr/bin/env bash
# Lay the demo config over MINIFI_HOME and run the agent in the foreground, C2 off.
#   bash scripts/run-agent.sh [CONF_DIR] [MINIFI_HOME]
# CONF_DIR (default conf/) holds config.yml (the flow), *.properties drop-ins, *.py processors with
# their requirements.txt, and *.sh helpers (installed to MINIFI_HOME/bin-demo).
# The flow's @MINIFI_HOME@ and @WORK_DIR@ tokens are filled in here; WORK_DIR defaults to /tmp/minifi-detect.
# If MODELS_DIR is set, its model files are copied into MINIFI_HOME/models first.
set -euo pipefail
CONF_DIR=${1:-$(cd "$(dirname "$0")/.." && pwd)/conf}
export MINIFI_HOME=${2:-$HOME/minifi-cpp-2.26.09}
export WORK_DIR=${WORK_DIR:-/tmp/minifi-detect}   # flow v1's frames.sh reads it too
WORK=$WORK_DIR
mkdir -p "$WORK"/{clips,in,out,meta,fail} "$MINIFI_HOME/minifi.properties.d" "$MINIFI_HOME/minifi-python" "$MINIFI_HOME/models"
if [ -n "${MODELS_DIR:-}" ]; then
  cp -f "$MODELS_DIR"/yolov8s-split-norm.onnx "$MODELS_DIR"/resnet18-places365.onnx "$MODELS_DIR"/places365_labels.txt "$MINIFI_HOME/models/"
fi
for f in yolov8s-split-norm.onnx resnet18-places365.onnx places365_labels.txt; do
  [ -f "$MINIFI_HOME/models/$f" ] || { echo "missing $MINIFI_HOME/models/$f (models/make-models.sh, then MODELS_DIR=...)" >&2; exit 1; }
done
if [ -f "$CONF_DIR/config.yml" ]; then
  sed -e "s#@MINIFI_HOME@#$MINIFI_HOME#g" -e "s#@WORK_DIR@#$WORK#g" "$CONF_DIR/config.yml" > "$MINIFI_HOME/conf/config.yml"
fi
for f in "$CONF_DIR"/*.properties; do [ -e "$f" ] && cp -f "$f" "$MINIFI_HOME/minifi.properties.d/"; done
for f in "$CONF_DIR"/*.py "$CONF_DIR"/requirements.txt; do [ -e "$f" ] && cp -f "$f" "$MINIFI_HOME/minifi-python/"; done
mkdir -p "$MINIFI_HOME/bin-demo"
for f in "$CONF_DIR"/*.sh; do [ -e "$f" ] && install -m 755 "$f" "$MINIFI_HOME/bin-demo/"; done
cd "$MINIFI_HOME"
exec ./bin/minifi.sh run
