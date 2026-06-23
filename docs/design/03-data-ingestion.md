# 03. 数据源与事件摄取

## 目的

Provider 层把外部数据源和本地 fixture 统一成 agent 可消费的类型。Provider 不更新 thesis、不写 ledger、不直接持久化；workflow 决定如何使用 provider 输出。

代码位置：

- `src/robinhood_agent/providers/base.py`
- `src/robinhood_agent/providers/polygon.py`
- `src/robinhood_agent/providers/sec_edgar.py`
- `src/robinhood_agent/providers/fmp.py`
- `src/robinhood_agent/providers/composite.py`
- `src/robinhood_agent/providers/csv_provider.py`
- `src/robinhood_agent/providers/json_provider.py`
- `src/robinhood_agent/providers/fake.py`

## Provider Protocols

`base.py` 定义协议和共享数据类型：

- `MarketDataProvider.fetch_market_data(ticker, benchmark) -> MarketData`
- `NewsProvider.fetch_news(ticker) -> list[ResearchEvent]`
- `FilingProvider.fetch_filings(ticker) -> list[ResearchEvent]`
- `EarningsCalendarProvider.fetch_earnings_calendar(ticker) -> list[ResearchEvent]`
- `TranscriptProvider.fetch_transcripts(ticker) -> list[ResearchEvent]`
- `HistoricalPriceProvider.fetch_price_history(ticker, window) -> list[PricePoint]`

这些是 structural protocols；真实 provider 和 fake provider 只要实现同名方法即可注入 agent workflow。

## MarketData

`MarketData` 是行情快照：

- `ticker`
- `benchmark`
- `latest_price`
- `previous_close`
- `benchmark_latest_price`
- `benchmark_previous_close`
- `volume`
- `average_volume`

计算属性：

- `price_change_pct`
- `benchmark_change_pct`
- `relative_change_pct`

`full_research.compute_signals()` 进一步派生：

- `price_change_pct`
- `benchmark_change_pct`
- `relative_change_pct`
- `volume_ratio`

## 真实数据源

### PolygonProvider

承担三类职责：

- 市场行情：snapshot + daily aggregate bars。
- 新闻：`/v2/reference/news`。
- earnings calendar：`/vX/reference/ticker_events`。
- 历史价格：用于 performance evaluation。

新闻 severity 规则很轻：

- 有 positive/negative sentiment insight 时为 `medium`。
- 其他默认为 `low`。

日历事件 severity 为 `medium`。

### SecEdgarProvider

读取 SEC submissions，并把 material forms 转成 `ResearchEvent`。

当前 material forms：

```text
8-K, 10-K, 10-Q, 20-F, 6-K
```

severity：

- `8-K`: `high`
- 其他 material forms: `medium`

SEC 访问必须配置 `SEC_USER_AGENT`。ticker 到 CIK 的映射来自 SEC company tickers JSON，并在 provider 实例内缓存。

### FinancialModelingPrepProvider

可选 transcript provider。只有配置 `FMP_API_KEY` 时 CLI 才会注入它。

输出：

- `event_type = earnings_transcript`
- `source = financial_modeling_prep`
- `severity = medium`
- `summary` 是 transcript/content 的前 500 个字符或 title fallback。

## CompositeResearchEventProvider

`CompositeResearchEventProvider.fetch_news()` 是 workflow 看到的统一事件入口。它按顺序合并：

1. news provider
2. filing provider
3. earnings calendar provider
4. transcript provider

返回值按 `occurred_at` 倒序排序。

命名上它实现的是 `NewsProvider` 协议，实际语义是“research event provider”。这是当前代码的兼容命名，新增代码应避免把它理解成只包含新闻。

## 本地与测试 provider

- `FakeMarketDataProvider`
- `FakeNewsProvider`
- `FakeLowSeverityNewsProvider`
- `FakeHistoricalPriceProvider`
- `CsvPriceProvider`
- `JsonNewsProvider`

这些 provider 支撑单元测试和 smoke 流程。它们必须保持与真实 provider 相同的 domain 输出，避免测试绕过业务校验。

## HTTP 边界

`HttpJsonClient` 是轻量 urllib 封装：

- `get_json()`: 要求响应是 object。
- `get_json_or_list()`: 允许 object 或 array。
- `get_json_absolute()`: 访问完整 URL，例如 SEC ticker mapping。

HTTP 错误被转成 `ValueError`，provider 会在必要时补充供应商语义错误。

## 扩展规则

- 新 provider 应实现 protocol，而不是修改 agent workflow。
- provider 输出必须是 `MarketData`、`ResearchEvent` 或 `PricePoint`，不要返回供应商原始 JSON。
- 稳定 `external_id` 很重要，因为 repository 依赖 `(source, external_id)` 去重。
- severity 规则应简单、可测试；复杂影响判断留给 LLM impact analysis。
