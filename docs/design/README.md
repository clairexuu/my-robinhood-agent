# Design Docs

这些文档描述当前代码实现，而不是未来路线图。读者应能从这里快速理解项目边界、主要数据流，以及后续迭代应该改哪个模块。

## 当前架构

```text
CLI / chat message
  -> configuration and provider wiring
  -> agent workflow function
  -> provider protocols
  -> domain dataclasses
  -> SQLite repository
```

核心实现位于 `src/robinhood_agent/`：

- `domain/`: 投资研究、事件、paper ledger 和表现快照的数据模型。
- `storage/`: SQLite schema 和 `AgentRepository`，负责持久化与聚合读取。
- `providers/`: 外部数据源与测试数据源，统一输出行情、事件和历史价格。
- `analysis/`: LLM impact analysis 的协议、prompt、OpenAI Responses API client 和解析校验。
- `agent/`: 可测试的同步 workflow 函数，包括 quick status、full research、event update、paper ledger、performance、router 和 Robinhood safety gate。
- `cli.py`: 命令行入口，负责解析参数、加载配置、初始化数据库、组装真实 provider。

## 文档边界

1. [领域模型与状态](01-domain-state.md): 业务对象、校验规则、状态聚合语义。
2. [本地存储](02-storage.md): SQLite schema、repository API、去重和 ledger 现金计算。
3. [数据源与事件摄取](03-data-ingestion.md): provider protocols、真实数据源、fixture 数据源、事件标准化。
4. [Agent Workflows](04-agent-workflows.md): 当前同步编排函数和跨模块调用关系。
5. [LLM 分析](05-llm-analysis.md): LLM 的输入输出边界、JSON schema、错误处理。
6. [Paper Ledger 与表现评估](06-paper-ledger-performance.md): 本地模拟订单、目标仓位意图、收益评估。
7. [自然语言与 CLI 入口](07-chat-router.md): argparse 命令、规则路由、响应格式。
8. [Robinhood Safety Gate](08-robinhood-gate.md): live order preview 的本地安全门和未实现边界。

## 设计原则

- 当前项目是单 ticker 研究 agent；多 ticker 支持要先扩展 `WatchProfile`、repository 查询和 CLI/router 参数。
- `ThesisState` 是核心业务状态；研究更新、paper intent 和表现评估都围绕它展开。
- LLM 只分析“新事实是否改变 thesis”，不能写账本、不能执行交易、不能绕过代码校验。
- Provider 只负责把外部数据转成统一类型；业务判断放在 `agent/` 或 `analysis/`。
- SQLite 是本地 source of truth；workflow 函数应通过 `AgentRepository` 读写，不直接写 SQL。
- 所有 Robinhood 真实交易能力默认禁用；当前代码没有真实下单调用。

## 主要运行路径

```text
quick-status
  -> repository.load_state
  -> format_quick_status

full-research
  -> load watch profile + thesis
  -> fetch market data and research events
  -> persist deduped events
  -> compute market signals
  -> LLM impact analysis
  -> save new thesis and research update
  -> build local paper rebalance preview

event-update
  -> load watch profile + thesis
  -> fetch market data and research events
  -> persist only new events
  -> trigger LLM only for high/critical new events
  -> optionally save new thesis and research update

paper-trade / apply-paper-intent
  -> build or reuse local paper preview
  -> validate local cash/position rules
  -> record paper order and update paper position

live-preview
  -> build paper preview
  -> apply RobinhoodGateConfig checks
  -> optionally validate human confirmation text
  -> never place a live order
```

## 与代码同步时的维护规则

- 新增业务字段时，先更新 `domain` 模型，再同步 SQLite schema、repository mapping、formatters 和相关测试。
- 新增外部数据源时，实现对应 provider protocol，尽量不要让 workflow 感知供应商字段。
- 新增 agent 能力时，在 `agent/` 中新增小的 workflow 函数，再从 CLI/router 调用。
- 修改 live trading 相关代码时，必须同时更新 [Robinhood Safety Gate](08-robinhood-gate.md)，并明确哪些步骤仍然不会真实下单。
