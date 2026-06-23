from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Optional

from robinhood_agent.domain import ResearchEvent, Severity

from .http import HttpJsonClient


MATERIAL_FORMS = {"8-K", "10-K", "10-Q", "20-F", "6-K"}


class SecEdgarProvider:
    def __init__(
        self,
        user_agent: str,
        base_url: str = "https://data.sec.gov",
        timeout_seconds: float = 30.0,
        company_tickers_url: str = "https://www.sec.gov/files/company_tickers.json",
        client: Optional[HttpJsonClient] = None,
        tickers_client: Optional[HttpJsonClient] = None,
    ):
        if not user_agent:
            raise ValueError("user_agent is required for SEC EDGAR access")
        self.client = client or HttpJsonClient(
            base_url,
            timeout_seconds=timeout_seconds,
            default_headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        self.tickers_client = tickers_client or HttpJsonClient(
            "",
            timeout_seconds=timeout_seconds,
            default_headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        self.company_tickers_url = company_tickers_url
        self._ticker_to_cik: Optional[Dict[str, str]] = None

    def fetch_filings(self, ticker: str) -> List[ResearchEvent]:
        normalized_ticker = ticker.upper()
        cik = self._cik_for_ticker(normalized_ticker)
        data = self.client.get_json(f"/submissions/CIK{cik}.json")
        recent = data.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            raise ValueError("SEC submissions response missing filings.recent")
        filings = _zip_recent_filings(recent)
        return [
            _filing_event(normalized_ticker, cik, filing)
            for filing in filings
            if filing.get("form") in MATERIAL_FORMS
        ][:20]

    def _cik_for_ticker(self, ticker: str) -> str:
        if self._ticker_to_cik is None:
            data = self.tickers_client.get_json_absolute(self.company_tickers_url)
            mapping: Dict[str, str] = {}
            for item in data.values():
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("ticker", "")).upper()
                cik = item.get("cik_str")
                if symbol and cik is not None:
                    mapping[symbol] = str(cik).zfill(10)
            self._ticker_to_cik = mapping
        try:
            return self._ticker_to_cik[ticker]
        except KeyError as exc:
            raise ValueError(f"SEC ticker mapping did not include {ticker}") from exc


def _zip_recent_filings(recent: Dict[str, Any]) -> List[Dict[str, Any]]:
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])
    count = min(
        len(forms),
        len(accession_numbers),
        len(filing_dates),
        len(report_dates),
        len(primary_docs),
    )
    result = []
    for index in range(count):
        result.append(
            {
                "form": forms[index],
                "accession_number": accession_numbers[index],
                "filing_date": filing_dates[index],
                "report_date": report_dates[index],
                "primary_document": primary_docs[index],
            }
        )
    return result


def _filing_event(ticker: str, cik: str, filing: Dict[str, Any]) -> ResearchEvent:
    form = str(filing["form"])
    accession_number = str(filing["accession_number"])
    filing_date = _parse_date(str(filing.get("filing_date") or ""))
    primary_document = str(filing.get("primary_document") or "")
    accession_no_dash = accession_number.replace("-", "")
    raw_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_no_dash}/{primary_document}"
        if primary_document
        else None
    )
    title = f"{ticker} filed {form}"
    report_date = filing.get("report_date")
    summary = f"SEC {form} filing"
    if report_date:
        summary = f"{summary}; report date {report_date}"
    return ResearchEvent(
        id=f"sec-filing-{_stable_id(accession_number)}",
        ticker=ticker,
        source="sec_edgar",
        external_id=accession_number,
        event_type="sec_filing",
        severity=Severity.HIGH if form == "8-K" else Severity.MEDIUM,
        title=title,
        summary=summary,
        occurred_at=filing_date,
        raw_url=raw_url,
    )


def _parse_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")
    except ValueError:
        return datetime.now(timezone.utc)


def _stable_id(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]
