#!/usr/bin/env bash
# Unpack a staged minifi.tar.gz (from scripts/stage.sh) into MINIFI_HOME. Refuses to overwrite an agent.
#   bash scripts/install.sh <minifi.tar.gz> [MINIFI_HOME]
set -euo pipefail
TAR=${1:?usage: install.sh <minifi.tar.gz> [MINIFI_HOME]}
MINIFI_HOME=${2:-$HOME/minifi-cpp-2.26.09}
[ -e "$MINIFI_HOME/bin/minifi" ] && { echo "$MINIFI_HOME already holds an agent; not overwriting" >&2; exit 1; }
mkdir -p "$MINIFI_HOME"
tar -xzf "$TAR" -C "$MINIFI_HOME" --strip-components=1
mkdir -p "$MINIFI_HOME/models" "$MINIFI_HOME/minifi-python"
echo "installed into $MINIFI_HOME"
