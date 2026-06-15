# 06. Paper Ledger 与表现评估

## 目标

维护本地模拟交易账本，并评估研究观点的后续表现。

## 范围

包含：

- 虚拟现金
- 虚拟持仓
- 模拟订单
- 成本和 PnL
- benchmark 对比
- 最大回撤和基础风险指标

不包含：

- 真实下单
- 券商账户对账
- 复杂回测引擎

## 关键设计

Paper ledger 是本项目自己维护的本地账本，不依赖 Robinhood paper trading。

模拟订单来自 research update 或用户明确要求，但执行仍是本地记录。

## Milestones

### M1: 定义 ledger models

定义 `PaperOrder`、`PaperPosition`、`LedgerSnapshot`。

验收标准：

- 支持 buy / sell / hold。
- 记录数量、价格、时间、费用字段。

### M2: 实现模拟成交

用市场价格生成本地模拟成交记录。

验收标准：

- buy 后现金减少、持仓增加。
- sell 后现金增加、持仓减少。
- 不允许卖出超过持仓。

### M3: 实现表现评估

计算绝对收益、相对 benchmark 收益、最大回撤和持仓周期。

验收标准：

- 给定历史价格 fixture，计算结果稳定。
- 支持 1D / 1W / 1M 观察窗口。

### M4: 接入 research output

把研究观点和模拟订单关联起来。

验收标准：

- 每条模拟订单能追溯到 research update。
- 表现快照能显示建议后的后续表现。

## 待确认

- 初始虚拟现金金额，默认建议 `$100,000`。
- 是否允许 fractional shares，默认允许。
