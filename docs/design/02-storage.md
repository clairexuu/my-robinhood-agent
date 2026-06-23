# 02. 本地存储

## 目的

本地 SQLite 数据库是 agent 的 source of truth。workflow 只能通过 `AgentRepository` 读写业务状态，不直接操作 SQL。

代码位置：

- `src/robinhood_agent/storage/sqlite.py`
- `src/robinhood_agent/storage/repositories.py`
- `tests/test_storage_and_quick_status.py`
- `tests/test_history.py`

## 连接与初始化

`connect(path)`：

- 创建 `sqlite3.Connection`。
- 设置 `row_factory = sqlite3.Row`。
- 开启 `PRAGMA foreign_keys = ON`。

`initialize_database(connection)`：

- 执行 idempotent `CREATE TABLE IF NOT EXISTS` schema。
- 写入 `schema_migrations(version=1)`。
- 当前没有增量 migration runner；schema 仍处于 MVP 形态。

CLI 每次运行非 `doctor` 命令都会调用 `initialize_database()`，因此空库可自动初始化。

## Schema

当前表：

- `schema_migrations`: 当前只有 version 1。
- `watch_profiles`: ticker 主表。
- `thesis_states`: 保存所有 thesis 历史，按 `ticker, updated_at DESC` 查询最新版本。
- `research_events`: 事件审计表，`UNIQUE(source, external_id)` 用于去重。
- `research_updates`: 研究输出历史。
- `paper_orders`: 本地模拟订单历史，可关联 `research_updates.id`。
- `paper_positions`: 当前本地模拟持仓，每个 ticker 一行。
- `performance_snapshots`: 表现评估历史。

JSON list 字段用 text 存储：

- `core_assumptions_json`
- `risks_json`
- `invalidation_conditions_json`
- `key_changes_json`

repository 负责 `json.dumps` / `json.loads`，调用方只处理 domain dataclass。

## Repository API

`AgentRepository` 封装所有读写。重要方法：

- `save_watch_profile()` / `get_watch_profile()`
- `save_thesis()` / `get_latest_thesis()`
- `save_research_event()` / `list_research_events()`
- `save_research_update()` / `get_latest_research_update()` / `list_research_updates()`
- `record_paper_order()` / `get_position()` / `list_paper_orders()`
- `save_performance_snapshot()` / `get_latest_performance_snapshot()` / `list_performance_snapshots()`
- `load_state()`
- `get_ledger_summary()`

`load_state(ticker)` 是 agent workflow 的主要入口。它聚合 watch profile、最新 thesis、ledger、最新 research update，以及默认 `1W` performance snapshot。

## 事件去重

`save_research_event()` 使用 `INSERT OR IGNORE`，并返回是否插入成功。

当前去重键：

```text
UNIQUE(source, external_id)
```

设计影响：

- provider 应尽量提供稳定 `external_id`。
- 如果 `external_id` 为 `NULL`，SQLite 允许多行 `NULL`，去重不会生效。
- `id` 仍是主键；相同 `id` 也会被忽略。

新增 provider 时，必须优先设计稳定 `external_id`。

## Paper Ledger 现金计算

repository 不保存 cash 表。`get_ledger_summary()` 从初始现金和 `paper_orders` 重新计算：

```text
cash = initial_cash - net_spent

buy  net_spent += quantity * price + fee
sell net_spent -= quantity * price - fee
```

默认 `initial_cash = 100_000.0`，由 `AgentRepository` 构造函数控制。

持仓数量和 average cost 保存到 `paper_positions`，由 `record_paper_order()` 更新：

- buy: 加权平均成本包含 fee。
- sell: 不改变剩余持仓 average cost；清仓后归零。
- 卖出超过当前持仓会抛 `ValueError`。

## 外键与前置条件

多数业务表引用 `watch_profiles(ticker)`。因此 workflow 在写 thesis、event、update、order 前，需要先有 watch profile。

当前 CLI 的推荐初始化路径：

```bash
PYTHONPATH=src python3 -m robinhood_agent.cli --db var/agent.db init-db --seed-default-nvda
```

## 扩展注意事项

- 增量 migration 需要在 `schema_migrations` 之上补 runner；不要直接修改旧 schema 而不提供迁移。
- 新增列表/对象字段时，优先保持 domain 类型清晰，再决定 SQLite JSON text 存储方式。
- 多账户、多 ticker portfolio 或多用户能力会影响 ledger 计算和大部分表的主键设计，应单独设计。
