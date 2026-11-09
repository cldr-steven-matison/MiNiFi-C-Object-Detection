#!/usr/bin/env bash
# Ask EFM for a deployer command (a new agent, so no agentIdentifier: EFM mints one) and print the JSON.
#   EFM_API=http://<efm>:10090/efm/api bash scripts/efm-generate-command.sh <linux|linuxaarch64> <service-user> > deployer-command.json
# BASE_URL is the C2 URL the agent will use (default: EFM_API); set it when the agent reaches EFM by
# another name than this host does (a pod uses the in-cluster service name).
# The command it returns enrolls one agent. Run it once, on one box; never reuse it for a second agent.
set -euo pipefail
OSARCH=${1:?usage: efm-generate-command.sh <linux|linuxaarch64> <service-user>}
USER_=${2:?service user}
EFM_API=${EFM_API:-http://localhost:10090/efm/api}
BASE_URL=${BASE_URL:-$EFM_API}
CLASS=${EFM_CLASS:-MiNiFiCppDetect}
curl -fsS -X POST "$EFM_API/agent-deployer/generateCommand" -H 'Content-Type: application/json' -d @- <<JSON
{"agentClass":"$CLASS","agentType":"cpp","agentVersion":"2.26.09","osArch":"$OSARCH",
 "baseUrl":"$BASE_URL","hbPeriod":5000,"serviceUser":"$USER_",
 "serviceName":"minifi","autoConfigureSecurity":false,"trustSelfSignedCertificates":false}
JSON
