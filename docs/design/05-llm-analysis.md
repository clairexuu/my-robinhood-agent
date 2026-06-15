# 05. LLM 分析与提示词

## 目标

定义 LLM 在系统中的边界：只做事件理解、影响判断和研究更新生成。

## 范围

包含：

- impact analysis prompt
- research update prompt
- structured output schema
- LLM 调用封装

不包含：

- 价格计算
- 仓位记账
- 真实下单

## 关键设计

LLM 不直接计算收益，不直接写 ledger，不直接调用 Robinhood。

LLM 输出必须是结构化结果，再由普通代码校验和持久化。

建议输出：

```python
class ImpactAnalysis(BaseModel):
    changes_thesis: bool
    severity: Literal["low", "medium", "high", "critical"]
    key_points: list[str]
    thesis_delta: str
    confidence_delta: float
    risk_updates: list[str]
    invalidation_updates: list[str]
```

## Milestones

### M1: 定义 structured output schema

定义 `ImpactAnalysis` 和 `ResearchUpdateDraft`。

验收标准：

- LLM 输出必须能被 schema 校验。
- 校验失败时有重试或错误返回。

### M2: 编写 impact analysis prompt

输入旧 thesis、事件列表和信号，输出是否改变 thesis。

验收标准：

- prompt 明确禁止编造缺失数据。
- prompt 要求区分事实、推断和不确定性。

### M3: 编写 research update prompt

生成面向用户的研究更新。

验收标准：

- 输出包含观点、置信度、建议仓位、适用周期、失效条件。
- 文本简洁，不像交易指令。

### M4: 接入 graph 节点

实现 `analyze_impact` 和 `generate_research_update`。

验收标准：

- fake LLM 和真实 LLM 都能通过同一接口。
- LLM 调用日志不泄漏敏感账户信息。

## 待确认

- 使用哪个模型。
- 是否需要中文、英文或双语输出，默认中文。
