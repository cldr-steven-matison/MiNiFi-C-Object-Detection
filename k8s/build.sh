#!/usr/bin/env bash
# Build the demo image (minifi-detect:2.26.09-b42) from the staged x86_64 tarball and the models.
# On minikube it builds straight into the node (MINIKUBE_PROFILE, default minikube); otherwise docker build.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
TAR=${EFM_BINARIES:-$HOME/efm-binaries}/staging/binaries/cpp/linux/2.26.09/minifi.tar.gz
MODELS=${MODELS_DIR:-$HERE/models/build}
[ -f "$TAR" ] || { echo "missing $TAR (bash scripts/stage.sh x86_64)" >&2; exit 1; }
CTX=$(mktemp -d); trap 'rm -rf "$CTX"' EXIT
cp "$HERE/k8s/Dockerfile" "$HERE/scripts/install.sh" "$HERE/scripts/run-agent.sh" "$TAR" "$CTX/"
mkdir -p "$CTX/models"
cp "$MODELS/yolov8s-split-norm.onnx" "$MODELS/resnet18-places365.onnx" "$MODELS/places365_labels.txt" "$CTX/models/"
if command -v minikube >/dev/null && minikube -p "${MINIKUBE_PROFILE:-minikube}" status >/dev/null 2>&1; then
  minikube -p "${MINIKUBE_PROFILE:-minikube}" image build -t minifi-detect:2.26.09-b42 "$CTX"
else
  docker build -t minifi-detect:2.26.09-b42 "$CTX"
fi
