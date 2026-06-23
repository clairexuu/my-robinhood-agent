# My Robinhood Agent

## Provider Choice

The production CLI now expects real providers:

* market data, technical/history data, news, and reference calendar events: Polygon
* official company filings: SEC EDGAR
* earnings call transcripts: Financial Modeling Prep, optional
* LLM analysis: OpenAI Responses API with structured JSON output
* live trading: still blocked by the local Robinhood gate; no live order placement is implemented

Recommended first production setup:

```bash
cp .env.example .env
```

Then fill `POLYGON_API_KEY`, `SEC_USER_AGENT`, `OPENAI_API_KEY`, and optionally `FMP_API_KEY` / `OPENAI_MODEL` in `.env`. Shell environment variables override `.env` values when both are present.

Polygon handles quote/history/news/reference events. SEC EDGAR handles official filings. FMP is used only when a transcript key is configured. OpenAI is used only for impact analysis; all ledger, performance, and safety decisions remain ordinary Python code.

## Commands

Initialize local state:

```bash
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db init-db --seed-default-nvda
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db doctor
```

Run the agent:

```bash
scripts/live_smoke.sh
scripts/transcript_smoke.sh
ENABLE_FMP_IN_LIVE_SMOKE=1 scripts/live_smoke.sh
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db quick-status NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db full-research NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db event-update NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db trade-preview NVDA buy --amount 1000
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db paper-trade NVDA buy --amount 1000
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db apply-paper-intent NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db evaluate-performance NVDA --window 1W
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db show-ledger NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db history NVDA
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db history NVDA --format json
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db chat "现在 NVDA 怎么样"
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db live-preview NVDA buy --amount 1000 --account-number RH123
```

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Current Slice

Implemented:

* domain models for thesis, research events, research updates, watch profile, paper orders, positions, and performance snapshots
* SQLite storage and audit history
* Polygon provider for market data, historical bars, news, and reference calendar events
* SEC EDGAR provider for official filings
* optional Financial Modeling Prep provider for earnings call transcripts
* OpenAI Responses API client with strict structured output for impact analysis
* full research, event update, quick status, paper ledger, performance evaluation, and JSON history export
* rule-based chat router that uses injected real providers from the CLI
* Robinhood live-order gate that remains disabled by default

The agent still maintains a local paper ledger. Robinhood MCP integration for account checks, order preview, and human-confirmed live orders is intentionally not wired yet.

mcp:
agent.robinhood.com/mcp/trading

instruction:
https://robinhood.com/us/en/support/articles/agentic-trading-overview/#ConnectyourAIagent

available tools:
https://robinhood.com/us/en/support/articles/trading-with-your-agent/

architecture:
[ARCHITECTURE.md](ARCHITECTURE.md)
