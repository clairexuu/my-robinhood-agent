# 架构

这是一个单股票研究 agent。用户通过 CLI 或自然语言 chat 入口交互；系统内部使用可测试的同步 Python workflow，而不是当前未接入的 LangGraph。

详细实现设计以 [docs/design](docs/design/README.md) 为准。

## 核心原则

核心对象是 `ThesisState`，也就是当前投资假设。

每次新信息进入时，agent 主要判断：

> 这条信息是否改变当前 thesis？

LLM 负责结构化 impact analysis。普通 Python 代码负责数据抓取、标准化、信号计算、状态更新、paper ledger、表现评估、风控预检和持久化。

## 分层

```text
CLI / chat message
  -> config and provider wiring
  -> agent workflow function
  -> provider protocols / impact analyzer
  -> domain dataclasses
  -> SQLite repository
```

## 当前运行模式

### `quick_status`

快速读取本地缓存状态。

用于回答：

- 当前 thesis
- 最近研究更新
- paper ledger 摘要
- 最近表现快照

不重新抓数据，不调用 LLM。

### `event_update`

处理新增研究事件。

流程：

1. 读取 watch profile 和 latest thesis。
2. 抓取行情和 research events。
3. 保存去重后的新事件。
4. 只在新事件包含 `high` 或 `critical` severity 时触发 LLM。
5. 必要时保存新 thesis 和 research update。

### `full_research`

完整刷新研究。

流程：

1. 读取 watch profile 和 latest thesis。
2. 抓取 Polygon 行情、新闻、日历事件，SEC filings，以及可选 FMP transcripts。
3. 保存去重后的事件。
4. 计算价格、benchmark 和成交量信号。
5. 调 OpenAI Responses API 生成结构化 impact analysis。
6. 更新 thesis，保存 research update。
7. 生成本地 paper rebalance preview。

## 主要模块

```text
src/robinhood_agent/
  domain/       # frozen dataclass domain models and validation
  storage/      # SQLite schema and AgentRepository
  providers/    # Polygon, SEC EDGAR, FMP, fake/CSV/JSON providers
  analysis/     # ImpactAnalyzer protocol, OpenAI client, prompt/parser
  agent/        # workflow functions, router, paper ledger, performance, safety gate
  cli.py        # argparse entrypoint and dependency wiring
  config.py     # .env and environment settings
```

## LLM 边界

LLM 只参与：

- 总结事件影响
- 判断事件是否改变 thesis
- 输出结构化 `ImpactAnalysis`

LLM 不负责：

- 写数据库
- 计算收益或回撤
- 维护 paper ledger
- 调用 Robinhood
- 执行真实交易

## 存储

SQLite 是本地 source of truth。当前保存：

- watch profiles
- thesis history
- research events
- research updates
- paper orders
- paper positions
- performance snapshots

workflow 通过 `AgentRepository` 读写，不直接执行 SQL。

## 安全边界

默认只做本地模拟交易。

当前 Robinhood 相关实现只有本地 live-order safety preview：

- live trading 默认 disabled
- account number 必须匹配配置
- paper preview 必须允许
- confirmation text 必须包含 ticker、方向、账户和金额或数量
- 代码不会真实下单

Robinhood MCP 未来只能用于账户读取、可交易性检查、订单预检和人工确认后的真实下单，不能作为主要研究数据源。
