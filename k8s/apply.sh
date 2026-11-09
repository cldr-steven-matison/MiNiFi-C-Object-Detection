#!/usr/bin/env bash
# Create or update the bench agent's ConfigMap (from conf/) and Deployment, in namespace minifi-detect.
# A conf change rolls only this pod: kubectl -n minifi-detect rollout restart deploy/minifi-detect-bench
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
kubectl apply -f "$HERE/k8s/bench.yaml" --dry-run=client -o name >/dev/null
kubectl get ns minifi-detect >/dev/null 2>&1 || kubectl create ns minifi-detect
kubectl -n minifi-detect create configmap minifi-detect-conf --from-file="$HERE/conf" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/k8s/bench.yaml"
