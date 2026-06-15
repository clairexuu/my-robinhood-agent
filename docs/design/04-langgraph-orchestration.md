# 04. LangGraph 编排

## 目标

用 LangGraph 表达可测试、可恢复的研究流程。

## 范围

包含：

- `AgentState`
- 三种内部运行模式
- graph nodes
- fan-out / fan-in
- 路由条件

不包含：

- 自然语言 intent router
- 具体 provider 实现细节
- Robinhood 下单

## 关键设计

用户可以自然语言交互，但内部 research workflow 只有三种运行模式：

- `quick_status`
- `event_update`
- `full_research`

主流程：

```text
load_state
  -> collect_data
  -> normalize_and_dedupe
  -> compute_signals
  -> analyze_impact
  -> update_thesis
  -> generate_outputs
  -> persist_outputs
```

`quick_status` 应尽量只走 `load_state` 和格式化输出。

## Milestones

### M1: 定义 `AgentState`

实现 LangGraph 使用的状态类型。

验收标准：

- 状态字段覆盖 thesis、events、signals、outputs。
- 类型能被节点测试复用。

### M2: 实现 `quick_status` graph

只读取缓存状态并返回摘要。

验收标准：

- 不调用外部数据源。
- 不调用 LLM。
- 无 thesis 时返回清晰空状态。

### M3: 实现 `full_research` graph skeleton

串起所有节点，provider 和 LLM 可先用 fake 实现。

验收标准：

- graph 可以端到端运行。
- 每个节点输入输出可测试。
- 失败节点能返回可诊断错误。

### M4: 实现 `event_update` graph

只处理新增事件，按重要性决定是否复评 thesis。

验收标准：

- low 事件不触发 LLM。
- high / critical 事件触发 impact analysis。
- 更新结果被持久化。

## 待确认

- 第一版是否需要 LangGraph checkpoint，默认建议先不用，只保留数据库状态。
