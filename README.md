# My Robinhood Agent

mcp: 
agent.robinhood.com/mcp/trading

instruction: 
https://robinhood.com/us/en/support/articles/agentic-trading-overview/#ConnectyourAIagent 

available tools: 
https://robinhood.com/us/en/support/articles/trading-with-your-agent/ 

architecture:
[ARCHITECTURE.md](ARCHITECTURE.md)

目标

* MVP 阶段只针对一个指定股票，持续跟踪公开信息，输出投资观点。
* 生成轻量研究更新，包含观点、置信度、建议仓位、失效条件与本地模拟订单。
* 探索阶段只做本地模拟交易记录，不执行真实下单。

数据层

* 研究与模拟数据源
    * Yahoo Finance / Polygon / Alpha Vantage 等市场数据 API
    * SEC/EDGAR：10-K、10-Q、8-K
    * 财报与 Earnings Call Transcript
    * 公司新闻、行业新闻、竞争对手新闻
    * 分析师预期与公开市场数据
* Robinhood MCP
    * 账户、持仓、购买力
    * 股票可交易性检查
    * 订单预检
    * 人工确认后的真实下单

系统链路

* 研究 / 模拟链路
    * 调用外部市场数据、SEC、财报、新闻等数据源。
    * 基于定期摘要和事件触发，生成研究更新与投资观点。
    * 写入本地 paper ledger，维护虚拟现金、虚拟持仓、成本、成交记录与盈亏。
    * 使用真实市场价格计算模拟收益、最大回撤、风险调整收益与持仓周期。
* 真实交易链路
    * 从研究报告生成交易意图，例如 `BUY NVDA, target_value = $1000`。
    * 通过 Robinhood MCP 读取账户信息、检查购买力与可交易性。
    * 通过 Robinhood MCP 做订单预检。
    * 必须经过人工确认后，才允许调用 Robinhood MCP 执行真实下单。
* 分层原则
    * Robinhood MCP 不作为主要研究数据源。
    * 研究报告、本地模拟交易和表现评估使用独立 market data provider。
    * Robinhood MCP 只用于账户相关信息、交易可行性检查、订单预检与真实交易执行。

MVP 范围

* 单 ticker 跟踪。
* 生成盘前、盘中、收盘后摘要，不做高频或盘中自动交易。
* 投资观点不只输出 Buy / Hold / Sell，还需要包含：
    * 置信度
    * 建议仓位
    * 观点适用周期
    * 失效条件
* 只生成本地模拟订单，并记录后续表现。
* 模拟订单不依赖 Robinhood 提供 paper trading 账户；由本项目维护虚拟现金、持仓、成本与盈亏。
* 持续对比 SPY / QQQ 等基准表现。

Research 事件模型

* Research 不只在收盘后运行，而是由轻量触发器驱动。
* 预计消息
    * 已知时间的事件，例如财报发布时间、earnings call、除权除息日、产品发布会、宏观数据发布时间。
    * MVP 只维护与目标股票直接相关的公司事件，以及少量关键宏观事件。
    * 事件前生成预案：市场预期、关键指标、可能影响、需要验证的问题。
    * 事件后生成复盘：实际结果、与预期差异、是否改变当前观点。
* 及时消息
    * 随时变化的事件，例如新闻、价格异动、成交量异动、SEC 8-K、分析师评级变化、竞争对手重大新闻。
    * MVP 不做全量实时流处理，优先采用定时轮询和去重后的事件列表。
    * 事件先分级，再决定是否触发研究更新：
        * `low`：只记录，不改变观点。
        * `medium`：写入事件笔记，进入下一次摘要。
        * `high`：触发盘中研究更新。
        * `critical`：触发告警，并重新评估投资观点与本地模拟订单。
* 定期摘要
    * 盘前摘要：关注隔夜新闻、预计事件、盘前价格变化。
    * 盘中摘要：只在有 high / critical 事件或明显价格异动时生成。
    * 收盘后摘要：汇总当天事件、价格表现、观点变化和 paper ledger 表现。
* Thesis state
    * Agent 维护当前投资假设，而不是每条新闻都重新判断 Buy / Hold / Sell。
    * 新事件只回答一个核心问题：这个事件是否改变当前 thesis？
    * Thesis state 至少包含：
        * 当前观点
        * 核心假设
        * 主要风险
        * 失效条件
        * 上次更新时间
* MVP 轻量化原则
    * 第一版只跟踪一个 ticker、一个基准和少量相关公司。
    * 第一版只接入一个主要市场数据源和一个新闻/公告来源。
    * 第一版不做复杂多 agent 协作，不做秒级监听，不做自动真实交易。

Agent 编排

* MVP 推荐使用轻量状态图，而不是自由多 agent 协作。
* 可以使用 LangGraph 表达 research / paper ledger / live trading gate 的状态流。
* Full research graph 采用 fan-out / fan-in：
    * `load_state`：读取 watch profile、thesis state、paper ledger。
    * 并行数据收集：`collect_market_data`、`collect_news`、`collect_sec_filings`、`collect_earnings_calendar`、`collect_peer_data`。
    * `normalize_and_dedupe`：合并不同来源，去重并生成统一事件列表。
    * 并行信号计算：`compute_price_moves`、`compute_volume_spike`、`compute_relative_performance`、`compute_calendar_signals`、`compute_ledger_performance`。
    * `analyze_impact`：分析重要事件是否改变 thesis。
    * `update_thesis`：更新观点、置信度、核心假设、风险和失效条件。
    * 并行输出：`generate_research_update`、`generate_paper_intent`、`evaluate_performance`。
    * `persist_outputs`：统一保存 research update、thesis state、paper ledger 和 performance snapshot。
* LLM 只参与：
    * 事件总结与影响分析。
    * 判断事件是否改变 thesis。
    * 生成研究更新和观点解释。
* 普通代码负责：
    * 数据抓取、清洗、去重。
    * 价格变化、成交量异动、相对收益、回撤、Sharpe / Sortino 等计算。
    * paper ledger 写入和持仓估值。
    * 风控边界和人工确认检查。
* UX 优化
    * `quick_status`：优先读取缓存的 thesis state 和最近研究更新，快速返回。
    * `event_update`：只处理新增事件，必要时调用一次 LLM。
    * `full_research`：完整刷新数据、更新 thesis，并生成研究报告，可后台运行。

Agent 流程

1. 根据定期摘要、预计消息或及时消息触发 research。
2. 收集最新数据（价格、新闻、财报、公告）。
3. 提取关键事件与风险信号，并更新 thesis state。
4. 综合基本面、事件面、技术面分析。
5. 生成投资观点、置信度、仓位建议与失效条件。
6. 必要时生成对应本地模拟订单并记录结果。
7. 持续评估建议、模拟收益与风险表现。

输出

* 今日关键变化
* 当前投资观点（Buy / Hold / Sell）
* 观点置信度
* 主要利好与风险
* 建议仓位
* 观点适用周期与失效条件
* 本地模拟订单方案
* 历史建议表现追踪

表现评估

* 绝对收益：建议后 1D / 1W / 1M 的模拟收益。
* 相对收益：与 SPY / QQQ 等基准的同期表现对比。
* 最大回撤：模拟持仓期间从高点到低点的最大跌幅。
* 风险调整收益：跟踪 Sharpe ratio 或 Sortino ratio 等指标。
* 持仓周期：记录每次本地模拟交易从开仓到平仓的实际持有时间。
* 观点复盘：记录观点是否触发失效条件，以及主要判断是否被后续事实验证。

安全限制

* 只能使用指定robinhood账户（通过account number配置）
* 默认禁止真实下单
* 所有交易先走本地模拟订单
* Agent 仅提供决策建议，不直接控制资金

未来扩展

* 自动回测与策略优化
* 条件触发（财报、价格异动、重大新闻）
* 将本地模拟订单转换为真实交易意图，人工确认后通过 Robinhood MCP 执行真实交易
