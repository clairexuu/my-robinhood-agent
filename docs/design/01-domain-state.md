# 01. 领域模型与状态

## 目的

领域模型定义 agent 能持久化、传递和测试的业务对象。当前实现使用 frozen `dataclass`，不依赖 Pydantic；校验逻辑写在 `__post_init__` 中。

代码位置：

- `src/robinhood_agent/domain/models.py`
- `src/robinhood_agent/fixtures.py`
- `tests/test_domain_models.py`

## 核心类型

### 枚举

- `View`: `buy`、`hold`、`sell`，用于 thesis 和 research update。
- `Severity`: `low`、`medium`、`high`、`critical`，用于事件和 impact analysis。
- `OrderSide`: `buy`、`sell`、`hold`，用于 paper preview/order。

字符串输入会被 `_coerce_enum` 转成枚举；非法值抛 `ValueError`。

### WatchProfile

`WatchProfile` 描述一个被跟踪标的。

字段：

- `ticker`: 统一转大写，必填。
- `benchmark`: 统一转大写，默认 `SPY`。
- `display_name`: 可选展示名。
- `created_at` / `updated_at`: 必须是 timezone-aware `datetime`。

当前 fixture 只提供 NVDA：`nvda_watch_profile()`。

### ThesisState

`ThesisState` 是项目的核心状态。它表示当前投资假设，而不是交易指令。

字段：

- `ticker`
- `view`
- `confidence`: `0.0` 到 `1.0`
- `target_position_pct`: `0.0` 到 `1.0`
- `horizon`
- `core_assumptions`
- `risks`
- `invalidation_conditions`: 必须非空
- `updated_at`
- `id`: repository 保存时可自动补 UUID

当前 `update_thesis()` 只根据 `ImpactAnalysis.confidence_delta` 调整置信度，并追加新的 risk/invalidation 条件；不会自动改变 `view`、`target_position_pct`、`horizon` 或 core assumptions。

### ResearchEvent

`ResearchEvent` 是所有外部事实的统一格式。Polygon 新闻、Polygon 日历、SEC filing、FMP transcript、JSON fixture 和 fake provider 都输出这个类型。

字段：

- `id`: 事件主键，由 provider 生成稳定 ID。
- `ticker`
- `source`: 例如 `polygon_news`、`sec_edgar`。
- `external_id`: 可选，用于 source-level 去重。
- `event_type`: 例如 `news`、`sec_filing`、`earnings_calendar`、`earnings_transcript`。
- `severity`
- `title`
- `summary`
- `occurred_at`
- `raw_url`

所有事件时间必须 timezone-aware。provider 如果拿不到可靠时间，会回退到当前 UTC 时间。

### ImpactAnalysis

`ImpactAnalysis` 是 LLM 或 fake analyzer 的结构化输出，也是 thesis 更新的唯一分析输入。

字段：

- `changes_thesis`
- `severity`
- `key_points`
- `thesis_delta`
- `confidence_delta`: `-1.0` 到 `1.0`
- `risk_updates`
- `invalidation_updates`

`changes_thesis` 目前主要用于展示；代码实际更新 thesis 时会应用 `confidence_delta` 和追加列表字段。

### ResearchUpdate

`ResearchUpdate` 是一次研究输出的审计记录。

字段：

- `thesis_before`
- `thesis_after`
- `key_changes`
- `view`
- `confidence`
- `suggested_position_pct`
- `invalidation_conditions`
- `created_at`

`full_research()` 和触发分析的 `event_update()` 会保存 research update。`apply_latest_paper_intent()` 会把 paper order 关联到最新 research update。

### Paper 和 Performance 类型

- `PaperOrder`: 本地模拟订单，记录 side、quantity、price、fee、可选 `research_update_id`。
- `PaperPosition`: 当前本地模拟持仓，记录 quantity 和 average cost。
- `PerformanceSnapshot`: 记录某个窗口的绝对收益、benchmark 收益、最大回撤；`relative_return` 是计算属性。

## 状态聚合

`storage.repositories.LoadedState` 是 workflow 常用的聚合读取结果，不在 `domain` 包中：

- `watch_profile`
- `thesis`
- `ledger`
- `latest_research_update`
- `latest_performance_snapshot`

这意味着 domain 模型保持纯业务对象，跨表聚合属于 storage/repository 边界。

## 约束

- 新增字段要同步 domain 校验、SQLite schema、repository mapping、formatter 和测试。
- 时间字段必须保持 timezone-aware；不要在 provider 或测试里传 naive datetime。
- 不要把供应商原始 JSON 泄漏进 domain 模型；provider 应先标准化。
