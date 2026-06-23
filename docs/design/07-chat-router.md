# 07. 自然语言与 CLI 入口

## 目的

入口层负责把用户请求路由到可控 workflow，并组装真实依赖。当前入口是 CLI；自然语言能力由规则 router 提供。

代码位置：

- `src/robinhood_agent/cli.py`
- `src/robinhood_agent/config.py`
- `src/robinhood_agent/agent/router.py`
- `tests/test_router.py`
- `tests/test_config.py`

## CLI 职责

`cli.py` 负责：

- 加载 `.env` 和 shell 环境变量。
- 创建 argparse subcommands。
- 初始化 SQLite 数据库。
- 构造 `AgentRepository`。
- 按命令构造真实 provider 和 analyzer。
- 调用 agent workflow。
- 打印 formatter 输出。

CLI 不应包含业务状态转换逻辑。新增业务行为应先进入 `agent/`，再从 CLI 暴露。

## 配置

`load_settings()` 从 `.env` 和 `os.environ` 读取配置；shell 环境变量优先。

关键变量：

- `ROBINHOOD_AGENT_DB`: 默认 `var/agent.db`
- `ROBINHOOD_AGENT_DEFAULT_TICKER`: 默认 `NVDA`
- `POLYGON_API_KEY`
- `SEC_USER_AGENT`
- `FMP_API_KEY`: 可选
- `OPENAI_API_KEY`
- `OPENAI_MODEL`: 默认由 `config.py` 指定
- `ROBINHOOD_ALLOWED_ACCOUNT_NUMBER`
- `ROBINHOOD_LIVE_TRADING_ENABLED`

`doctor` 命令输出配置状态和安全默认值，不要求真实 provider 可用。

## CLI Commands

状态和研究：

- `init-db [--seed-default-nvda]`
- `doctor`
- `quick-status [ticker]`
- `full-research [ticker]`
- `event-update [ticker]`
- `history [ticker] [--kind ...] [--limit ...] [--format text|json]`

账本和表现：

- `show-ledger [ticker]`
- `trade-preview ticker side --amount/--quantity`
- `paper-trade ticker side --amount/--quantity`
- `apply-paper-intent [ticker]`
- `evaluate-performance [ticker] --window 1D|1W|1M`

自然语言和 live safety：

- `chat "message" [--default-ticker NVDA]`
- `live-preview ticker side --amount/--quantity --account-number ...`

`full-research`、`event-update`、`chat` 中需要真实研究时，会要求 Polygon、SEC 和 OpenAI 配置；FMP transcript 只有配置 key 时加入 composite provider。

## Rule-based Router

`route_message(message, default_ticker)` 返回 `RoutedIntent`。

支持 intent：

- `quick_status`
- `full_research`
- `event_update`
- `show_ledger`
- `trade_preview`
- `clarify`

关键词示例：

- “现在 NVDA 怎么样” -> `quick_status`
- “完整刷新一下研究” -> `full_research`
- “有什么新闻/事件” -> `event_update`
- “账本/持仓/现金/pnl” -> `show_ledger`
- “如果买 1000 美元” -> `trade_preview`

ticker 提取：

- 先找 1 到 5 位大写 token，忽略 `BUY`、`SELL`、`HOLD`、`USD`、`CLI`、`API`、`FULL`。
- 中文“英伟达”和英文 `nvidia` 映射到 `NVDA`。
- `spy` 映射到 `SPY`。

trade preview 提取：

- side: 中文买/卖或英文 buy/sell。
- amount: `$1000`、`1000 美元`、`amount=1000` 等。
- quantity: `10 shares`、`10 股`、`quantity=10` 等。

## handle_message

`handle_message()` 是自然语言执行入口：

1. 调 `route_message()`。
2. 如需澄清，直接返回 clarification。
3. 根据 intent 调对应 workflow。
4. 如果 workflow 依赖缺失，返回可读错误，而不是抛异常。

例如 `full_research` intent 必须提供 market data provider、news provider 和 impact analyzer；否则返回：

```text
Full research requires configured market data, news, and LLM providers.
```

## 输出格式

formatter 分散在各 agent 模块中：

- `format_full_research_result`
- `format_event_update_result`
- `format_trade_preview`
- `format_ledger_summary`
- `format_history_report`
- `format_history_json`
- `format_live_order_preview`

这些 formatter 是 CLI/user-facing 边界。它们可以聚合字段展示，但不应改变状态或触发外部调用。

## 扩展规则

- 新 intent 先扩展 `RoutedIntent` 和 `route_message()` 测试，再接 `handle_message()`。
- 复杂自然语言分类如果引入 LLM，也必须保持 allowlist intent，不允许模型直接调用任意函数。
- CLI 参数校验应尽量在 argparse 或 workflow 前置校验完成，避免半执行后失败。
