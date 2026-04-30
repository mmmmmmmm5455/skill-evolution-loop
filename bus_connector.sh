#!/usr/bin/env bash
# bus_connector.sh — Bus integration for Skill Evolution Loop
# Sources bus_helper.sh, registers as skill-evolution-loop role
# Run via: bash bus_connector.sh [--once|--loop]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUS_HELPER="C:/Users/qwqwh/.claude/projects/agent-mesh/bus_helper.sh"

if [[ -f "$BUS_HELPER" ]]; then
  source "$BUS_HELPER"
else
  echo "[FATAL] bus_helper.sh not found at $BUS_HELPER"
  exit 1
fi

export BUS_ROLE="skill-evolution-loop"

# ── Register ────────────────────────────────────────────────────────────────
bus_register "$BUS_ROLE" "w-evolution-loop"

# ── Process pending evolution requests ──────────────────────────────────────
process_once() {
  local messages count
  messages=$(msg_poll 5 2>/dev/null || echo "[]")
  count=$(echo "$messages" | python -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

  if [[ $count -gt 0 ]]; then
    echo "$messages" | python -c "
import json, sys, subprocess
msgs = json.load(sys.stdin)
for m in msgs:
    skill = m.get('payload', {}).get('skill', '')
    if skill:
        r = subprocess.run(['python', r'${SCRIPT_DIR}/evolution_loop.py', skill],
                          capture_output=True, text=True)
        print(f'[EVO] {skill}: {r.stdout.strip()[:200]}')
    else:
        print(f'[EVO] No skill in message {m.get(\"msg_id\",\"?\")}')
"
  fi

  bus_heartbeat
}

# ── CLI ─────────────────────────────────────────────────────────────────────
case "${1:-}" in
  --once)
    process_once
    echo "[evo-bus] Done."
    ;;
  --loop)
    echo "[evo-bus] Starting poll loop (interval: 30s)"
    while true; do
      process_once
      sleep 30
    done
    ;;
  *)
    echo "Usage: bus_connector.sh [--once|--loop]"
    exit 1
    ;;
esac
