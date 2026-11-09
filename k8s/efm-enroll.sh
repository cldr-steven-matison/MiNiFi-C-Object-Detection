#!/usr/bin/env bash
# Enroll the pod agent into an EFM class with the command EFM generated for it.
#   bash k8s/efm-enroll.sh <deployer-command.json>
# The JSON is the response of POST /efm/api/agent-deployer/generateCommand (osArch linux, no
# agentIdentifier: EFM mints one). An existing ConfigMap is never replaced, so a re-run cannot
# swap in a second identifier.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
CMD_JSON=${1:?usage: efm-enroll.sh <deployer-command.json>}
CLASS=${EFM_CLASS:-MiNiFiCppDetect}
if ! kubectl -n minifi-detect get configmap minifi-detect-deployer >/dev/null 2>&1; then
  TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["command"])' "$CMD_JSON" > "$TMP/deploy.sh"
  if ! grep -q "agentClass=$CLASS" "$TMP/deploy.sh" || ! grep -q "osArch=linux " "$TMP/deploy.sh"; then
    echo "$CMD_JSON is not the $CLASS linux command" >&2; exit 1
  fi
  kubectl get ns minifi-detect >/dev/null 2>&1 || kubectl create ns minifi-detect
  kubectl -n minifi-detect create configmap minifi-detect-deployer --from-file=deploy.sh="$TMP/deploy.sh"
fi
kubectl apply -f "$HERE/k8s/efm.yaml"
