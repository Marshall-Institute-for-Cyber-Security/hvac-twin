#!/usr/bin/env bash
# Brings the whole Phase 6 compose stack up on whatever host this runs on,
# confirms every service actually responds, fires a real attack across
# containers (attack-console -> plant, by Compose service name), confirms
# it landed, then tears everything down. Run this on any Docker host to
# check the roadmap's "docker compose up" bar for real there, the same way
# it was checked on the original dev machine -- this script *is* that
# check, made reproducible instead of a one-off manual session.
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
  echo "--- tearing down ---"
  docker compose down
}
trap cleanup EXIT

docker compose up --build -d

echo "--- waiting for services to come up ---"
ready=0
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8100/status >/dev/null \
    && curl -sf http://localhost:8101/status >/dev/null \
    && curl -sf http://localhost:8000/attacks >/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "FAILED: services never came up within 60s." >&2
  docker compose logs
  exit 1
fi

echo "--- plant (server closet) ---"
curl -sf http://localhost:8100/status
echo
echo "--- office-plant (office wing) ---"
curl -sf http://localhost:8101/status
echo
echo "--- attack console ---"
curl -sf http://localhost:8000/attacks
echo
echo "--- frontend ---"
for page in index.html closet.html office.html attack.html defenses.html; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5173/$page")
  echo "$page -> $code"
  if [ "$code" != "200" ]; then
    echo "FAILED: $page did not serve 200." >&2
    exit 1
  fi
done

echo "--- before attack ---"
curl -sf http://localhost:8100/tags/setpoint_tenths
echo

echo "--- firing setpoint-spoof from attack-console, targeting plant:5020 by Compose service name ---"
curl -sf -X POST http://localhost:8000/attacks/setpoint-spoof/start \
  -H 'content-type: application/json' \
  -d '{"host": "plant", "port": 5020, "setpoint": 900}'
echo
sleep 2

echo "--- after attack ---"
after=$(curl -sf http://localhost:8100/tags/setpoint_tenths)
echo "$after"

if echo "$after" | grep -q '"value":9000'; then
  echo
  echo "VERIFIED: a real cross-container attack landed -- this host's compose stack is healthy."
else
  echo
  echo "FAILED: setpoint_tenths did not change -- something's wrong on this host." >&2
  exit 1
fi
