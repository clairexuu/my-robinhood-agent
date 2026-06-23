# 05. LLM 分析

## 目的

LLM 只负责判断“新事件和市场信号是否改变当前 thesis”。它不能直接持久化状态、不能写 paper ledger、不能调用 Robinhood。

代码位置：

- `src/robinhood_agent/analysis/impact.py`
- `src/robinhood_agent/analysis/llm.py`
- `src/robinhood_agent/analysis/fake.py`
- `tests/test_llm_analysis.py`
- `tests/test_full_research.py`
- `tests/test_event_update.py`

## 协议

`ImpactAnalyzer` 是 agent workflow 依赖的协议：

```python
analyze(thesis: ThesisState, events: list[ResearchEvent], signals: dict[str, float]) -> ImpactAnalysis
```

实现：

- `StructuredLlmImpactAnalyzer`: 用 `LlmClient` 调模型，解析成 `ImpactAnalysis`。
- `FakeImpactAnalyzer`: 测试用规则实现。

## OpenAI Responses Client

`OpenAIResponsesLlmClient` 使用标准库 `urllib` 调用：

```text
POST {base_url}/responses
```

默认 `base_url = https://api.openai.com/v1`，模型来自 `OPENAI_MODEL`，默认值由 `config.py` 设置。

请求使用 Responses API 的 strict JSON schema：

- `changes_thesis`: boolean
- `severity`: `low | medium | high | critical`
- `key_points`: string array
- `thesis_delta`: string
- `confidence_delta`: number, `-1` 到 `1`
- `risk_updates`: string array
- `invalidation_updates`: string array

system message 要求：

- 只返回 JSON。
- 不把分析写成交易指令。
- 只基于提供事实分析 thesis impact。

## Prompt 输入

`build_impact_prompt()` 包含：

- 当前 ticker、view、confidence、target position、horizon。
- core assumptions、risks、invalidation conditions。
- 标准化事件列表：severity、title、summary、source、occurred_at。
- signals 字典，按 key 排序输出。

prompt 明确要求：

- 不编造缺失事实。
- 区分事实和推断。
- 只返回 JSON。

## 输出解析和校验

`parse_impact_analysis(raw_response)`：

1. 解析 JSON。
2. 要求顶层是 object。
3. 检查所有 required fields。
4. 校验 `changes_thesis` 是 bool。
5. 校验 list 字段都是 string list。
6. 校验 severity enum。
7. 把 `confidence_delta` 转 float。
8. 构造 domain `ImpactAnalysis`，复用 dataclass 自身校验。

失败统一抛 `LlmOutputError`。

`_extract_response_text()` 兼容两种 Responses 返回形态：

- 顶层 `output_text`
- `output[].content[].text`

如果找不到文本，也抛 `LlmOutputError`。

## Workflow 使用方式

`full_research()` 总是调用 analyzer，并基于结果更新 thesis。

`event_update()` 只在新事件包含 high/critical severity 时调用 analyzer。low/medium 事件会被保存，但不会触发 LLM，也不会更新 thesis。

## Fake Analyzer

`FakeImpactAnalyzer` 用于测试：

- 取事件最高 severity。
- high/critical 视为 changes thesis。
- 价格非负且触发 thesis change 时，`confidence_delta = 0.05`。
- 输出固定 key points。

测试应优先使用 fake analyzer 或 static JSON client，避免依赖真实网络。

## 边界

- LLM 输出不是最终状态；`agent.full_research.update_thesis()` 才决定如何应用。
- 当前 LLM 不能改变 view 或 target position；schema 中也没有这些字段。
- 不要把账户号、token、真实持仓等 Robinhood 敏感信息放进 prompt。
- 新增 LLM 字段必须同步 JSON schema、parser、domain model、fake analyzer 和 tests。
