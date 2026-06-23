#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${DB_PATH:-${ROOT_DIR}/var/live-smoke.db}"
TICKER="${TICKER:-NVDA}"
PYTHONPATH="${ROOT_DIR}/src"
export PYTHONPATH

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

# Keep the first smoke focused on the required main chain:
# Polygon + SEC EDGAR + OpenAI. Transcript access depends on the FMP plan.
# To include FMP transcripts in this script after `scripts/transcript_smoke.sh`
# passes, run:
#
#   ENABLE_FMP_IN_LIVE_SMOKE=1 scripts/live_smoke.sh
#
if [[ "${ENABLE_FMP_IN_LIVE_SMOKE:-}" != "1" ]]; then
  export FMP_API_KEY=""
fi

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$name" >&2
    printf 'Fill it in .env or export it before running this script.\n' >&2
    exit 2
  fi
}

run() {
  printf '\n== %s ==\n' "$1"
  shift
  printf '$'
  printf ' %q' "$@"
  printf '\n'
  "$@"
}

require_env POLYGON_API_KEY
require_env SEC_USER_AGENT
require_env OPENAI_API_KEY

run "Check configuration" \
  python3 -m robinhood_agent.cli doctor

run "Initialize local SQLite state" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" init-db --seed-default-nvda

run "Run full research with Polygon, SEC EDGAR, and OpenAI" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" full-research "$TICKER"

run "Show text audit history" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" history "$TICKER"

run "Show JSON audit history" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" history "$TICKER" --format json

run "Apply latest local paper intent" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" apply-paper-intent "$TICKER"

run "Show local paper ledger" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" show-ledger "$TICKER"

run "Evaluate local paper performance" \
  python3 -m robinhood_agent.cli --db "$DB_PATH" evaluate-performance "$TICKER" --window 1W

printf '\nSmoke database: %s\n' "$DB_PATH"
