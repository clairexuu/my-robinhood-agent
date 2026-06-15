# 02. 本地存储

## 目标

提供可靠的本地状态存储，用于保存 thesis、事件、研究更新、paper ledger 和表现快照。

## 范围

包含：

- SQLite 存储
- repository 层
- schema migration 的轻量方案
- 读写测试

不包含：

- 远程数据库
- 多用户权限
- 云同步

## 关键设计

第一版使用 SQLite。

建议表：

- `watch_profiles`
- `thesis_states`
- `research_events`
- `research_updates`
- `paper_orders`
- `paper_positions`
- `performance_snapshots`

Repository 层隐藏 SQL 细节，LangGraph 节点只调用 repository。

## Milestones

### M1: 建立 SQLite schema

创建初始化脚本和基础表。

验收标准：

- 空数据库能一键初始化。
- 所有表有主键和必要索引。
- 事件表能按 `ticker`、`occurred_at`、`source` 查询。

### M2: 实现 repositories

实现 thesis、event、research update、ledger、performance 的读写接口。

验收标准：

- 每个 repository 有基础单元测试。
- 写入后能正确读取。
- 重复事件可以基于 source + external id 或 hash 去重。

### M3: 接入状态加载

实现 `load_state` 所需的聚合读取接口。

验收标准：

- 给定 ticker 能读取 watch profile、最新 thesis、ledger summary。
- 没有历史数据时返回明确的空状态。

## 待确认

- 是否需要保留所有历史 thesis，默认建议保留。
