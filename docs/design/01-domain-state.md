# 01. 领域模型与状态

## 目标

定义系统的核心业务对象，尤其是 `thesis state`、事件、研究更新和本地模拟交易状态。

## 范围

包含：

- ticker watch profile
- thesis state
- research event
- research update
- paper ledger 基础状态

不包含：

- 数据源接入
- LangGraph 节点实现
- Robinhood MCP 调用

## 关键设计

`thesis state` 是核心对象。新事件进入后，系统主要判断它是否改变当前 thesis。

建议核心类型：

```python
class ThesisState(BaseModel):
    ticker: str
    view: Literal["buy", "hold", "sell"]
    confidence: float
    target_position_pct: float
    horizon: str
    core_assumptions: list[str]
    risks: list[str]
    invalidation_conditions: list[str]
    updated_at: datetime

class ResearchEvent(BaseModel):
    id: str
    ticker: str
    source: str
    event_type: str
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    summary: str
    occurred_at: datetime
    raw_url: str | None = None

class ResearchUpdate(BaseModel):
    id: str
    ticker: str
    thesis_before: str
    thesis_after: str
    key_changes: list[str]
    view: Literal["buy", "hold", "sell"]
    confidence: float
    suggested_position_pct: float
    invalidation_conditions: list[str]
    created_at: datetime
```

## Milestones

### M1: 定义核心 Pydantic models

实现 `ThesisState`、`ResearchEvent`、`ResearchUpdate`、`WatchProfile`。

验收标准：

- models 能被单元测试实例化。
- 必填字段和枚举值校验生效。
- 时间字段统一使用 timezone-aware `datetime`。

### M2: 定义状态转换规则

实现 thesis 更新的最小规则：保留上一版、生成新版、记录变化原因。

验收标准：

- 能从旧 thesis 和 impact analysis 生成新 thesis。
- 能记录 thesis 是否变化。
- 不允许缺失 `invalidation_conditions`。

### M3: 定义 fixture

创建一组本地测试 fixture，例如 `NVDA` + `SPY`。

验收标准：

- 测试可以加载 fixture。
- fixture 覆盖 buy / hold / sell 至少一种状态。

## 待确认

- 第一只默认 ticker 是什么。
- benchmark 默认用 `SPY` 还是 `QQQ`。
