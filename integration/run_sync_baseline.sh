#!/bin/bash
# Convenience wrapper to run the sync harness baseline measurement
# against the live Steam game. Requires:
# - Slay the Spire launched through ModTheSpire with CommunicationMod enabled
# - Bridge config installed (run integration/setup_communication_mod.sh first)
#
# Usage:
#   integration/run_sync_baseline.sh            # all Ironclad scenarios, seed 12345
#   integration/run_sync_baseline.sh <seed>     # custom seed
#
# Output:
#   - test_results/*.json   one per scenario
#   - test_results/baseline_summary.md
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SEED="${1:-12345}"
OUT_DIR="$REPO_DIR/test_results/phase_1.5_baseline"

cd "$REPO_DIR"

if [ ! -d build ]; then
    echo "Build not found at $REPO_DIR/build. Run cmake first." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Setting up .venv via uv …"
    uv venv .venv --python 3.14 --seed
    uv pip install -p .venv/bin/python pyyaml
fi

mkdir -p "$OUT_DIR"

# Sanity-check that the bridge is reachable
if [ ! -d /tmp/sts_bridge ] || [ ! -f /tmp/sts_bridge/state.json ]; then
    cat >&2 <<'WARN'
WARNING: /tmp/sts_bridge/state.json not present.
This usually means Slay the Spire is not currently running with
CommunicationMod enabled. The harness will fail to connect.

To proceed:
  1. Launch Slay the Spire through ModTheSpire
     (java -jar .../ModTheSpire.jar --mods CommunicationMod,BaseMod)
  2. Enable CommunicationMod in the ModTheSpire UI; click Play
  3. Wait for the main menu to load
  4. Re-run this script
WARN
    exit 2
fi

export PYTHONPATH="$REPO_DIR/build"

echo "=== Phase 1.5 baseline: Ironclad scenarios, seed $SEED ==="
for scenario in integration/scenarios/ironclad/*.yaml; do
    name=$(basename "$scenario" .yaml)
    echo
    echo "--- Scenario: $name ---"
    .venv/bin/python integration/run_tests.py \
        --scenario "$scenario" \
        --seed "$SEED" \
        --character IRONCLAD \
        --project sts_lightspeed \
        --verbose 2>&1 | tee "$OUT_DIR/$name.log" || true
done

echo
echo "=== Done. Logs and reports in $OUT_DIR/ ==="
