# 08. Robinhood MCP 与真实交易安全门

## 目标

安全接入 Robinhood MCP，用于账户读取、交易可行性检查、订单预检，以及人工确认后的真实下单。

## 范围

包含：

- 指定账户校验
- 账户、持仓、购买力读取
- 可交易性检查
- 订单预检
- 人工确认 gate

不包含：

- 自动真实交易
- 用 Robinhood 做主要研究数据源
- 绕过人工确认的下单

## 关键设计

默认禁止真实下单。

真实交易路径必须和研究 / paper trading 路径分离：

```text
research update
  -> paper intent
  -> trade preview
  -> human confirmation
  -> Robinhood order placement
```

任何 live order 都必须满足：

- account number 匹配配置
- 用户显式确认
- 订单预检成功
- 风控规则通过

## Milestones

### M1: 配置账户安全边界

读取允许账户配置和 live trading 开关。

验收标准：

- 默认 live trading 为 disabled。
- account number 不匹配时禁止继续。

### M2: 实现账户读取

通过 Robinhood MCP 读取账户、持仓和购买力。

验收标准：

- 能返回账户摘要。
- 错误信息不泄漏敏感 token。

### M3: 实现 trade preview

把研究意图转成订单预览，不真实下单。

验收标准：

- 检查购买力和可交易性。
- 输出预估订单详情。
- 明确提示需要人工确认。

### M4: 实现人工确认后的 live order

只在显式确认后调用真实下单。

验收标准：

- 未确认时不会调用下单工具。
- 确认内容包含 ticker、方向、金额或数量、账户。
- 所有真实下单都有审计记录。

## 待确认

- 人工确认的交互形式：CLI 输入、API confirmation token，还是 UI 按钮。
- 第一版是否完全禁用 live order，只保留 preview。
