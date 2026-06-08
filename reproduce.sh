#!/usr/bin/env bash
# reproduce.sh — Single-command pipeline reproduction
#
# Reproduces the per-arm contrasts and the headroom dose-response from the
# committed per-arm outcomes.csv files. Conforms to PUBLIC_MIRROR_STANDARD.md v1.0.0.
#
# Usage:
#   ./reproduce.sh                  # Run analysis for every arm
#   ./reproduce.sh --check-only     # Verify dependencies; do not run analysis
#
# Outputs are teed to output/logs/. The master run log is output/logs/master_run.log.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

mkdir -p output/figures output/tables output/logs
LOG_FILE="output/logs/master_run.log"

echo "==================================================" | tee -a "$LOG_FILE"
echo "Pipeline run: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Repo: $REPO_ROOT" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"

CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    *) echo "Unknown flag: $arg"; exit 2 ;;
  esac
done

# 1. Dependency check
echo ">>> Checking dependencies..." | tee -a "$LOG_FILE"
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found. Install via 'curl -LsSf https://astral.sh/uv/install.sh | sh'" | tee -a "$LOG_FILE"
  exit 1
fi
echo "uv: $(uv --version)" | tee -a "$LOG_FILE"

if [[ "$CHECK_ONLY" == "1" ]]; then
  echo ">>> Check-only mode; exiting before analysis." | tee -a "$LOG_FILE"
  exit 0
fi

UV_RUN="uv run --with pandas --with scipy --with numpy --with statsmodels python"

# 2. Per-arm contrasts and effect sizes (code/analyze.py)
for ARM in data data_study2 data_haiku data_ablation_full data_frontier data_paraphrase; do
  CSV="${ARM}/outcomes.csv"
  if [[ -f "$CSV" ]]; then
    echo ">>> analyze.py — arm: ${ARM}" | tee -a "$LOG_FILE"
    $UV_RUN code/analyze.py --input "$CSV" 2>&1 \
      | tee "output/logs/analyze_${ARM}.log" | tee -a "$LOG_FILE"
  else
    echo ">>> SKIP ${ARM} (no ${CSV})" | tee -a "$LOG_FILE"
  fi
done

# 3. Graded-headroom dose-response (code/compute_headroom.py)
if [[ -f "data_headroom/outcomes.csv" ]]; then
  echo ">>> compute_headroom.py — arm: data_headroom" | tee -a "$LOG_FILE"
  $UV_RUN code/compute_headroom.py --input data_headroom/outcomes.csv 2>&1 \
    | tee "output/logs/compute_headroom.log" | tee -a "$LOG_FILE"
else
  echo ">>> SKIP data_headroom (no data_headroom/outcomes.csv)" | tee -a "$LOG_FILE"
fi

echo "==================================================" | tee -a "$LOG_FILE"
echo "Pipeline complete: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
