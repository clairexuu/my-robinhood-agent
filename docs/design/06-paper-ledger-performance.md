# 06. Paper Ledger 与表现评估

## 目的

Paper ledger 是本地模拟交易账本，用于把研究目标仓位转成可审计的模拟订单和表现快照。它不依赖 Robinhood，也不会产生真实订单。

代码位置：

- `src/robinhood_agent/agent/paper_ledger.py`
- `src/robinhood_agent/agent/performance.py`
- `src/robinhood_agent/storage/repositories.py`
- `tests/test_paper_ledger.py`
- `tests/test_performance.py`

## TradePreview

`TradePreview` 是所有 paper 交易和 live safety preview 的前置对象：

- `ticker`
- `side`
- `price`
- `quantity`
- `notional`
- `fee`
- `estimated_cash_after`
- `estimated_quantity_after`
- `allowed`
- `reason`

formatter 会明确输出：

```text
This is a local paper trade preview, not a live Robinhood order.
```

## 手动 Paper Trade

`trade_preview()`：

1. 读取 watch profile。
2. 通过 market data provider 获取最新价格。
3. 要求 `amount` 或 `quantity` 至少一个。
4. 根据 side 估算交易后现金和持仓。
5. 校验 buy 是否现金足够、sell 是否持仓足够。

`execute_paper_trade()`：

1. 要求 preview `allowed=True`。
2. 拒绝执行 `hold`。
3. 创建 `PaperOrder`。
4. 调用 `repository.record_paper_order()`。
5. 返回 order、position 和 ledger summary。

## Research Paper Intent

`build_paper_intent()` 把 thesis 的 `target_position_pct` 转成 rebalance preview。

计算：

```text
current_position_value = current_quantity * latest_price
total_equity = cash + current_position_value
target_position_value = total_equity * target_position_pct
delta_value = target_position_value - current_position_value
```

行为：

- `abs(delta_value) < min_trade_notional`: 返回 `hold`。
- `delta_value > 0`: 返回 buy preview。
- `delta_value < 0`: 返回 sell preview。

默认 `min_trade_notional = 1.0`。

`full_research()` 只生成 paper intent，不自动执行。`apply_latest_paper_intent()` 才会执行最新 research update 对应的本地模拟订单。

## 账本持久化

`paper_orders` 保存订单历史。`paper_positions` 保存当前持仓。

`AgentRepository.record_paper_order()` 负责：

- buy 后更新 quantity 和加权 average cost。
- sell 后减少 quantity，保留 average cost；清仓归零。
- 拒绝卖出超过持仓。

cash 不单独存表，而是由 `get_ledger_summary()` 根据初始现金和订单历史重算。默认初始现金是 `100_000.0`。

## 表现评估

`evaluate_performance(repository, ticker, window, price_provider)`：

1. 读取 watch profile 和当前 position quantity。
2. 获取 ticker 和 benchmark 的历史价格。
3. 要求每组至少两个 price point。
4. 计算 absolute return。
5. 计算 benchmark return。
6. 计算 max drawdown。
7. 保存 `PerformanceSnapshot`。

窗口由 CLI 限制为：

- `1D`
- `1W`
- `1M`

`CsvPriceProvider` 和 `PolygonProvider` 都实现 `fetch_price_history()`。

## 指标定义

```text
absolute_return = end_price / start_price - 1
benchmark_return = benchmark_end / benchmark_start - 1
relative_return = absolute_return - benchmark_return
max_drawdown = min(point.close / running_peak - 1)
```

当前 performance 是标的价格表现，不是账户级组合收益。它会展示当前 position quantity，但 return 本身没有按仓位加权。

## 边界

- Paper order 永远不代表真实 Robinhood order。
- `hold` preview 不能执行成订单。
- 当前没有复杂回测、税费模型、滑点模型或多资产组合净值。
- 若未来加入真实交易，对账也应作为独立模块，不应复用 paper ledger 表作为券商账本。
