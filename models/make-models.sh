#!/usr/bin/env bash
# Build the three model files the flow loads, into models/build/ (or $MODELS_DIR):
#   yolov8s-split-norm.onnx   DetectObject: ultralytics YOLOv8s at 640, opset 17, split into
#                             scores [1,8400,80] + boxes [1,8400,4] normalised to the input
#   resnet18-places365.onnx   ClassifyImage: CSAIL Places365 ResNet18, batch pinned to 1
#   places365_labels.txt      365 lines, line N = class N
#
#   bash models/make-models.sh            # uses ./models/.venv, created on first run
#   PYTHON=/path/to/python bash models/make-models.sh
# Needs python 3.10-3.12 with pip, and network access to github.com and places2.csail.mit.edu.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${MODELS_DIR:-$HERE/build}
mkdir -p "$OUT"
if [ -z "${PYTHON:-}" ]; then
  if [ ! -x "$HERE/.venv/bin/python" ]; then
    python3 -m venv "$HERE/.venv"
    # on Linux the default torch wheel pulls the CUDA libraries; the export needs only the CPU build
    if [ "$(uname -s)" = Linux ]; then
      "$HERE/.venv/bin/pip" install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
    fi
    "$HERE/.venv/bin/pip" install -q -r "$HERE/requirements.txt"
  fi
  PYTHON=$HERE/.venv/bin/python
fi
cd "$OUT"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
# fetch <url> <sha256>: download once, and stop if the file is not the one this script was written
# against. Both checkpoints are pickles, and the CSAIL server has no HTTPS.
fetch() {
  local f=${1##*/}
  [ -f "$f" ] || curl -fsSLO "$1"
  [ "$(sha "$f" | cut -d' ' -f1)" = "$2" ] || { echo "$f: sha256 is not $2; delete it and run again" >&2; exit 1; }
}

# DetectObject: export, then split the single output0 [1,84,8400] into the two tensors it reads
fetch https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt \
      1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a
"$PYTHON" -c 'from ultralytics import YOLO; YOLO("yolov8s.pt").export(format="onnx", imgsz=640, opset=17, simplify=True)'
"$PYTHON" "$HERE/split_yolo_outputs.py" yolov8s.onnx yolov8s-split-norm.onnx --normalize 640

# ClassifyImage: the CSAIL checkpoint and its category list
fetch http://places2.csail.mit.edu/models_places365/resnet18_places365.pth.tar \
      2f4759217d470da2b803f8f66cd4488a066406b555a5fb95ee9a4663f9f05588
fetch https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt \
      2affba635eb657e7ca95f4e6cc69bd9fac29ef4c32aeb83cafdfcd06ec6a1ea6
"$PYTHON" "$HERE/export_places365.py" resnet18_places365.pth.tar categories_places365.txt resnet18-places365.onnx places365_labels.txt

ls -l yolov8s-split-norm.onnx resnet18-places365.onnx places365_labels.txt
sha yolov8s-split-norm.onnx resnet18-places365.onnx places365_labels.txt
