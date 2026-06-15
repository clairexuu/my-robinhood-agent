# 架构

这是一个基于 LangGraph 的单股票研究 agent。

用户可以用自然语言交互；系统内部用固定、可测试的状态图执行。

详细实现设计以 [docs/design](docs/design/README.md) 为准。

## 核心原则

核心对象是 `thesis state`，也就是当前投资假设。

每次新信息进入时，agent 主要判断：

> 这条信息是否改变当前 thesis？

LLM 负责总结、影响分析和解释。普通代码负责数据抓取、清洗、计算、记账、风控和持久化。

## 分层

```text
Chat / CLI / API
  -> 自然语言路由
  -> LangGraph 运行模式
  -> 状态图节点
  -> 本地存储
```

## 内部运行模式

### `quick_status`

快速读取缓存状态。

用于回答：

- 当前观点
- 最近研究更新
- paper ledger 摘要
- 最近表现

不重新抓数据，尽量不调用 LLM。

### `event_update`

处理新增事件。

例如新闻、SEC 文件、分析师变化、价格异动、成交量异动。

先给事件分级，只有重要事件才触发 thesis 复评。

### `full_research`

完整刷新研究。

拉取市场数据、新闻、公告、财报日历、同行数据和 ledger 表现，然后更新 thesis 并生成研究报告。

## LangGraph 主流程

```text
load_state
  -> 并行收集数据
  -> normalize_and_dedupe
  -> 并行计算信号
  -> analyze_impact
  -> update_thesis
  -> 并行生成输出
  -> persist_outputs
```

## 状态

```python
class AgentState(TypedDict):
    ticker: str
    benchmark: str
    run_type: Literal["quick_status", "event_update", "full_research"]

    watch_profile: dict
    thesis: dict
    paper_ledger: dict

    market_data: dict
    news_items: list[dict]
    sec_filings: list[dict]
    calendar_events: list[dict]
    peer_data: dict

    events: list[dict]
    signals: dict

    impact_analysis: dict
    updated_thesis: dict

    research_update: dict
    paper_intent: dict | None
    performance_snapshot: dict
```

## LLM 负责

- 总结事件
- 判断事件是否改变 thesis
- 解释投资观点
- 生成研究更新

## 普通代码负责

- 抓取和清洗数据
- 去重事件
- 计算价格、成交量、相对表现、回撤和收益
- 维护本地 paper ledger
- 执行风控边界
- 保存状态和输出

## 建议目录结构

```text
src/
  agent/
    graph.py
    state.py
    nodes/

  domain/
    thesis.py
    events.py
    paper_ledger.py
    performance.py

  providers/
    market_data.py
    news.py
    sec.py
    robinhood.py

  storage/
    sqlite.py
    repositories.py

  prompts/
    impact_analysis.md
    research_update.md
```

## MVP 顺序

1. 定义 `ThesisState` 和 `PaperLedger`。
2. 实现 `quick_status`。
3. 接一个市场数据源，跑通 `full_research` 骨架。
4. 加新闻 / 公告事件，支持 `event_update`。
5. 最后接 Robinhood MCP，只做账户读取、交易检查、订单预检和人工确认下单。

## 安全边界

默认只做本地模拟交易。

Robinhood MCP 不作为主要研究数据源，只用于账户、持仓、购买力、可交易性检查、订单预检和人工确认后的真实下单。

任何真实下单都必须经过人工确认。
