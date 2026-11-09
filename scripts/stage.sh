#!/usr/bin/env bash
# Stage MiNiFi C++ 2.26.09 with the extra extensions (minifi_tensor: DetectObject, DrawBoundingBox,
# ClassifyImage, TractModelService) into one minifi.tar.gz, in EFM's agent-deployer folder layout.
#
#   bash scripts/stage.sh x86_64                 # -> $EFM_BINARIES/staging/binaries/cpp/linux/2.26.09/minifi.tar.gz
#   bash scripts/stage.sh aarch64                # -> $EFM_BINARIES/staging/binaries/cpp/linuxaarch64/2.26.09/minifi.tar.gz
#   bash scripts/stage.sh aarch64 --with-models  # also bakes in ExtractVideoFrames.py, its requirements.txt
#                                                #   and the three model files from $MODELS_DIR
#
# EFM_BINARIES (default ~/efm-binaries) holds the two downloaded tarballs for the arch.
# MODELS_DIR (default models/build in this repo) holds what models/make-models.sh writes.
# The --with-models build is the one to serve from EFM: the agent's first heartbeat already
# reports ExtractVideoFrames, and TractModelService finds its models at MINIFI_HOME/models.
set -euo pipefail

ARCH=${1:?usage: stage.sh x86_64|aarch64 [--with-models]}
PAYLOAD=${2:-}
HERE=$(cd "$(dirname "$0")/.." && pwd)
MODELS=${MODELS_DIR:-$HERE/models/build}
VER=2.26.09
BUILD=b42
SRC=${EFM_BINARIES:-$HOME/efm-binaries}

case "$ARCH" in
  x86_64)  OSARCH=linux;        BASE=nifi-minifi-cpp-$VER-$BUILD-bin-linux.tar.gz;       EXTRA=nifi-minifi-cpp-$VER-$BUILD-extra-extensions-linux.tar.gz ;;
  aarch64) OSARCH=linuxaarch64; BASE=nifi-minifi-cpp-$VER-$BUILD-bin-linux-arm64.tar.gz; EXTRA=nifi-minifi-cpp-$VER-$BUILD-extra-extensions-linux-arm64.tar.gz ;;
  *) echo "arch must be x86_64 or aarch64" >&2; exit 2 ;;
esac
# The extra-python-components zip (ChunkData, Prompt*, Milvus, Partition*, TokenCount) is not
# staged: this flow uses none of it, and the agent would pip-install its requirements on first start.

for f in "$BASE" "$EXTRA"; do
  [ -f "$SRC/$f" ] || { echo "missing $SRC/$f (see README: Get the bits)" >&2; exit 1; }
done

OUT=$SRC/staging/binaries/cpp/$OSARCH/$VER
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/base" "$WORK/extra" "$OUT"

tar -xzf "$SRC/$BASE" -C "$WORK/base"
TOP=$(find "$WORK/base" -mindepth 1 -maxdepth 1 -type d | head -1)
[ -d "$TOP/extensions" ] || { echo "no extensions/ under $TOP" >&2; exit 1; }

# Copy links as links: minifi_native.so in the extra package is a symlink, and without it
# Python processors do not load.
tar -xzf "$SRC/$EXTRA" -C "$WORK/extra"
n=0
while IFS= read -r so; do cp -Pf "$so" "$TOP/extensions/"; n=$((n+1)); done < <(find "$WORK/extra" -name '*.so*' \( -type f -o -type l \))
echo "injected $n extension libraries"

find "$TOP/extensions" -iname '*tensor*' | grep -q . || { echo "no tensor extension after injection" >&2; exit 1; }

if [ "$PAYLOAD" = --with-models ]; then
  for f in yolov8s-split-norm.onnx resnet18-places365.onnx places365_labels.txt; do
    [ -f "$MODELS/$f" ] || { echo "missing $MODELS/$f (run models/make-models.sh)" >&2; exit 1; }
  done
  mkdir -p "$TOP/minifi-python" "$TOP/models"
  install -m 644 "$HERE/conf/ExtractVideoFrames.py" "$HERE/conf/requirements.txt" "$TOP/minifi-python/"
  install -m 644 "$MODELS/yolov8s-split-norm.onnx" "$MODELS/resnet18-places365.onnx" "$MODELS/places365_labels.txt" "$TOP/models/"
  echo "baked in minifi-python/ExtractVideoFrames.py, requirements.txt and models/ (yolov8s-split-norm.onnx, resnet18-places365.onnx, places365_labels.txt)"
elif [ -n "$PAYLOAD" ]; then
  echo "unknown option $PAYLOAD" >&2; exit 2
fi

tar -czf "$OUT/minifi.tar.gz" -C "$WORK/base" "$(basename "$TOP")"
( cd "$OUT" && sha256sum minifi.tar.gz | tee minifi.tar.gz.sha256 )
echo "staged $OUT/minifi.tar.gz (top dir $(basename "$TOP"))"
find "$TOP/extensions" -mindepth 1 -maxdepth 1 -printf '  %f\n' | sort
