# 08. Robinhood Safety Gate

## 目的

Robinhood safety gate 是 live order 的本地前置检查。当前实现只做 preview 和 confirmation text 校验，不会调用 Robinhood MCP，也不会真实下单。

代码位置：

- `src/robinhood_agent/agent/robinhood_gate.py`
- `src/robinhood_agent/config.py`
- `src/robinhood_agent/cli.py`
- `tests/test_robinhood_gate.py`

## 当前能力

`preview_live_order(config, paper_preview, account_number)` 把本地 `TradePreview` 转成 `LiveOrderPreview`。

`validate_live_order_confirmation(preview, confirmation_text)` 校验用户确认文本是否包含必要信息。

`format_live_order_preview()` 输出检查结果，并固定提示：

```text
No live Robinhood order was placed.
```

## 配置

`RobinhoodGateConfig`：

- `allowed_account_number: Optional[str] = None`
- `live_trading_enabled: bool = False`

来源：

- `ROBINHOOD_ALLOWED_ACCOUNT_NUMBER`
- `ROBINHOOD_LIVE_TRADING_ENABLED`

默认 live trading disabled。

## Preview Gate 规则

`preview_live_order()` 依次检查：

1. `live_trading_enabled` 必须为 true。
2. `allowed_account_number` 必须已配置。
3. 请求传入的 account number 必须匹配 allowed account。
4. paper preview 必须 `allowed=True`。
5. paper preview side 不能是 `hold`。

任一失败都会返回 `allowed=False` 和明确 reason。

全部通过时，返回：

```text
allowed=True
reason="live order preview passed local safety gate; human confirmation still required"
```

这仍然不是下单许可，只表示本地前置检查通过。

## Human Confirmation

`validate_live_order_confirmation()` 只在 preview 已 allowed 时继续检查。

确认文本必须包含：

- ticker
- side
- account number
- rounded notional 或 rounded quantity

缺字段时返回新的 `LiveOrderPreview(allowed=False)`，reason 会列出缺失片段。

通过时 reason 为：

```text
human confirmation accepted; live placement is not implemented in this MVP
```

## CLI live-preview

CLI 命令：

```bash
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db live-preview NVDA buy --amount 1000 --account-number RH123
```

流程：

1. 构造 market data provider。
2. 基于输入生成本地 paper trade preview。
3. 构造 `RobinhoodGateConfig`。
4. 调 `preview_live_order()`。
5. 如果提供 `--confirmation`，再调 `validate_live_order_confirmation()`。
6. 打印 live order safety preview。

即使 confirmation 通过，当前代码也不会继续调用任何下单 API。

## 与 Paper Ledger 的关系

live preview 依赖 `TradePreview`，因为真实交易前应先经过同一套本地金额、数量、现金和持仓检查。

但两者仍是不同边界：

- paper ledger 可以记录本地模拟订单。
- Robinhood safety gate 只做 live order 预检状态。
- 当前没有从 `LiveOrderPreview` 到真实 broker order 的实现。

## 未实现项

当前没有：

- Robinhood MCP client。
- 账户读取。
- 持仓或购买力从 Robinhood 同步。
- order preview API 调用。
- live order placement。
- live order 审计表。

README 中保留 Robinhood MCP 链接作为后续接入参考，但代码没有 wiring。

## 扩展前置要求

实现真实交易前，应先补齐：

- 明确的 MCP client 接口和 fake client。
- 账户读取与 allowed account 二次校验。
- Robinhood order preview 结果模型。
- 人工确认 token 或强格式确认文本。
- live order 审计表。
- 单元测试覆盖所有拒绝路径。

任何真实下单调用必须在所有 gate 通过后单独实现，不能放进 formatter 或 router。
