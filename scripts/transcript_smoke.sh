#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TICKER="${TICKER:-NVDA}"
PYTHONPATH="${ROOT_DIR}/src"
export PYTHONPATH

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ -z "${FMP_API_KEY:-}" ]]; then
  printf 'Missing required environment variable: FMP_API_KEY\n' >&2
  printf 'Fill it in .env or export it before running this script.\n' >&2
  exit 2
fi

python3 - "$TICKER" <<'PY'
import os
import sys

from robinhood_agent.providers import FinancialModelingPrepProvider


ticker = sys.argv[1]
events = FinancialModelingPrepProvider(api_key=os.environ["FMP_API_KEY"]).fetch_transcripts(ticker)
if not events:
    raise SystemExit(f"No transcript events returned for {ticker}")

print(f"{ticker} transcript smoke")
print(f"Events returned: {len(events)}")
for event in events[:3]:
    print(f"- {event.occurred_at.isoformat()} [{event.severity.value}] {event.title}")
    print(f"  source={event.source} type={event.event_type} id={event.id}")
PY
