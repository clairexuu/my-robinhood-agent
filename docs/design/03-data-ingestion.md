# 03. 数据源与事件摄取

## 目标

从外部数据源收集市场、新闻、公告和日历信息，并统一成标准事件。

## 范围

包含：

- 市场数据 provider
- 新闻 / 公告 provider
- SEC filing provider
- earnings calendar provider
- 事件归一化和去重

不包含：

- LLM 分析
- paper ledger 记账
- Robinhood 账户数据

## 关键设计

Robinhood MCP 不作为主要研究数据源。

第一版只需要接入：

- 一个市场数据源
- 一个新闻或公告来源

Provider 输出原始数据，normalizer 负责转成 `ResearchEvent`。

## Milestones

### M1: 定义 provider interface

定义统一接口，例如 `fetch_market_data`、`fetch_news`、`fetch_filings`。

验收标准：

- 可以用 fake provider 跑测试。
- provider 返回值不依赖 LangGraph。

### M2: 实现市场数据 provider

获取目标 ticker 和 benchmark 的价格、成交量、基础行情。

验收标准：

- 能返回最近价格和历史价格序列。
- 失败时返回可诊断错误，不吞异常。

### M3: 实现新闻 / 公告 provider

获取目标 ticker 的新闻或公告。

验收标准：

- 能生成标准 `ResearchEvent`。
- 同一条新闻重复抓取不会重复入库。

### M4: 实现事件分级

按规则给事件标记 `low`、`medium`、`high`、`critical`。

验收标准：

- 价格大幅异动可被标记为 high 或 critical。
- 普通重复新闻只记录为 low 或被去重。

## 待确认

- 第一版市场数据源选 Yahoo Finance、Polygon 还是 Alpha Vantage。
- 第一版新闻 / 公告来源选哪个。
