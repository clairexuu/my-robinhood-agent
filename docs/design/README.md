# Design Docs

这些文档是后续开发的 source of truth。

实现顺序：

1. [领域模型与状态](01-domain-state.md)
2. [本地存储](02-storage.md)
3. [数据源与事件摄取](03-data-ingestion.md)
4. [LangGraph 编排](04-langgraph-orchestration.md)
5. [LLM 分析与提示词](05-llm-analysis.md)
6. [Paper Ledger 与表现评估](06-paper-ledger-performance.md)
7. [自然语言入口与用户接口](07-chat-router.md)
8. [Robinhood MCP 与真实交易安全门](08-robinhood-gate.md)

## 总体原则

- 用户用自然语言交互。
- 内部用固定、可测试的 LangGraph 状态图。
- `thesis state` 是核心业务对象。
- 默认只做本地模拟交易。
- Robinhood MCP 不作为主要研究数据源。
- 任何真实下单都必须人工确认。

## 当前 MVP 假设

- 只跟踪一个 ticker。
- 只配置一个主要 benchmark，例如 `SPY` 或 `QQQ`。
- 第一版只接一个市场数据源和一个新闻 / 公告来源。
- 第一版不做秒级监听，不做高频交易，不做自动真实下单。
