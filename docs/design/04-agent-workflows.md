# 04. Agent Workflows

## 目的

当前实现不是 LangGraph。Agent 层由一组同步、可测试的 Python 函数组成。每个 workflow 接收 repository 和 provider/analyzer 依赖，返回 dataclass 结果或格式化文本。

代码位置：

- `src/robinhood_agent/agent/full_research.py`
- `src/robinhood_agent/agent/event_update.py`
- `src/robinhood_agent/agent/quick_status.py`
- `src/robinhood_agent/agent/paper_ledger.py`
- `src/robinhood_agent/agent/performance.py`
- `src/robinhood_agent/agent/history.py`
- `src/robinhood_agent/agent/router.py`
- `src/robinhood_agent/agent/robinhood_gate.py`

## 依赖方向

```text
cli/router
  -> agent workflow
  -> storage.AgentRepository
  -> domain models

agent workflow
  -> provider protocols
  -> analysis.ImpactAnalyzer
```

规则：

- `agent/` 可以协调多个模块，但不应包含供应商 HTTP 细节。
- `agent/` 可以创建新的 domain 对象，但持久化必须走 repository。
- `agent/` formatter 只负责用户可读输出，不应改变状态。

## quick_status

入口：

```python
quick_status(repository, ticker) -> str
```

流程：

1. `repository.load_state(ticker)`
2. `format_quick_status(ticker, state)`

特点：

- 不调用外部 provider。
- 不调用 LLM。
- watch profile 缺失时返回 setup 提示。
- thesis 缺失时返回明确空状态。
- 会展示 ledger、最新 research update 和最新 `1W` performance snapshot。

## full_research

入口：

```python
full_research(repository, ticker, market_data_provider, news_provider, impact_analyzer)
```

流程：

1. 标准化 ticker。
2. 通过 `repository.load_state()` 读取 watch profile 和 latest thesis。
3. 缺 watch profile 或 thesis 时抛 `ValueError`。
4. `market_data_provider.fetch_market_data(profile.ticker, profile.benchmark)`。
5. `news_provider.fetch_news(profile.ticker)`；当前这个 provider 可能是 composite research event provider。
6. 对每个 event 调用 `repository.save_research_event()`，统计新插入数量。
7. `compute_signals(market_data)`。
8. `impact_analyzer.analyze(prior_thesis, events, signals)`。
9. `update_thesis(prior_thesis, impact)` 并保存。
10. `build_research_update()` 并保存。
11. `build_paper_intent()` 生成本地 paper rebalance preview。

返回 `FullResearchResult`，formatter 会明确提示 paper intent 不是 live order。

## event_update

入口：

```python
event_update(repository, ticker, market_data_provider, news_provider, impact_analyzer)
```

流程与 `full_research` 类似，但只在新事件有 `high` 或 `critical` severity 时触发 LLM。

关键差异：

- LLM 判断依据是 `new_events`，不是所有 fetched events。
- low/medium 新事件只保存事件和 signals，不更新 thesis，不保存 research update。
- 返回 `triggered_analysis` 标记。

触发函数：

```python
_should_trigger_analysis(events)
```

当前规则：

```text
any(event.severity in {high, critical})
```

## Thesis 更新

`update_thesis(prior, impact)` 当前行为：

- `confidence = clamp(prior.confidence + impact.confidence_delta, 0, 1)`。
- 追加不重复的 `risk_updates`。
- 追加不重复的 `invalidation_updates`。
- 保持 view、target position、horizon、core assumptions 不变。
- 创建新 UUID 和当前 UTC `updated_at`。

这意味着 LLM 不能直接改变仓位目标或评级。若后续需要支持这些变更，应先扩展 `ImpactAnalysis` schema，再更新此函数和测试。

## Research Update 生成

`build_research_update()` 从 prior/updated thesis 和 impact 生成审计记录：

- `thesis_before`: 简短 view + confidence。
- `thesis_after`: 简短 view + confidence。
- `key_changes`: impact key points，加上置信度变化说明；为空时补 `No material changes.`。
- `suggested_position_pct`: 当前 updated thesis 的 target position。

## history

`load_history()` 从 repository 按 kind 加载 events、updates、orders、performance snapshots。支持 text formatter 和 JSON formatter。

这条路径只读数据库，不调用 provider 或 LLM。

## 与未来 LangGraph 的关系

旧文档曾把 LangGraph 作为默认编排方式，但当前代码没有依赖 LangGraph。未来如果引入图编排，应把现有 workflow 函数当作节点候选，而不是重写业务逻辑：

- 节点输入输出沿用当前 result dataclass 或更小的纯数据对象。
- checkpoint 仍不能替代 SQLite source of truth。
- quick status 应继续保持无外部调用。
