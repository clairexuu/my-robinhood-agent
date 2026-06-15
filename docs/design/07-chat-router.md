# 07. 自然语言入口与用户接口

## 目标

让用户用自然语言和 agent 交互，同时把请求路由到可控的内部工作流。

## 范围

包含：

- intent router
- CLI 或 API 入口
- 用户可读响应格式
- 常见查询类型

不包含：

- 前端 UI
- 真实交易执行
- 复杂多轮投资顾问对话

## 关键设计

用户不是只能输入固定命令。

自然语言先进入 router，再映射到内部动作：

```text
用户输入
  -> intent router
  -> quick_status / event_update / full_research / explain / ledger / trade_preview
```

Router 第一版可以先用规则和少量 LLM 分类混合实现。

## Milestones

### M1: 定义 intents

定义最小 intent 集合。

建议：

- `quick_status`
- `full_research`
- `event_update`
- `explain_thesis`
- `show_ledger`
- `compare_benchmark`
- `trade_preview`

验收标准：

- 每个 intent 有明确输入、输出和允许调用的内部模块。
- 未识别请求返回澄清问题。

### M2: 实现 router

把自然语言映射到 intent 和参数。

验收标准：

- “现在 NVDA 怎么样” 路由到 `quick_status`。
- “完整刷新一下研究” 路由到 `full_research`。
- “如果买 1000 美元会怎样” 路由到 `trade_preview`。

### M3: 实现响应格式化

统一输出结构。

验收标准：

- 研究输出包含观点、置信度、仓位、风险、失效条件。
- ledger 输出包含现金、持仓、PnL、benchmark 对比。
- trade preview 明确标注不是实际下单。

## 待确认

- 第一版入口用 CLI、FastAPI，还是两者都要。
