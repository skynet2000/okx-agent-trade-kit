# OKX Agent Trade Kit

> RSI 激进抄底策略 — OKX 永续合约自动化交易 Skill

## 功能概述

基于 RSI(14) 超卖信号的 OKX 永续合约自动交易机器人。

- **触发逻辑**：RSI(14) < 超卖阈值 → 市价买入开多
- **止盈逻辑**：价格上涨 +{tp-pct}% → 市价止盈卖出
- **止损逻辑**：价格下跌 -{sl-pct}% → 市价止损卖出
- **合约杠杆**：5x ~ 8x 可调
- **交易模式**：永续合约（swap）或现货（spot）
- **账户模式**：模拟盘（demo）/ 实盘（live）

## 快速开始

### 前置依赖

1. 安装 OKX CLI：
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```

2. 配置 API 密钥：
   ```bash
   okx config init
   ```

3. 确认依赖 Skill 已安装：
   - `okx-cex-market`
   - `okx-cex-trade`
   - `okx-cex-portfolio`

### 使用方法

在支持 WorkBuddy / CodeBuddy 的 AI 助手中，直接描述你的需求即可触发本 Skill：

```
"okx激进抄底 ETH 永续 止盈8%止损5% 杠杆8x 仓位50%"
```

或：

```
"rsi激进 BTC-USDT-SWAP 模拟盘"
```

## 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--rsi-oversold` | `25` | 超卖阈值（低于此值触发买入） |
| `--tp-pct` | `8%` | 止盈涨幅百分比 |
| `--sl-pct` | `5%` | 止损跌幅百分比 |
| `--leverage` | `8x` | 合约杠杆（5x~8x） |
| `--order-pct` | `50%` | 单笔仓位占保证金比例 |
| `--check-interval` | `60s` | 信号轮询间隔 |

## 策略逻辑

```
Phase 0: 启动检查 → API连接、余额查询、K线获取
Phase 1: RSI监测 → 持续轮询 RSI(14)，低于阈值触发信号
Phase 2: 执行买入 → 市价开多（现货/合约）
Phase 3: 持仓监控 → 实时追踪止盈/止损/超时
Phase 4: 平仓离场 → 止盈/止损/超时强制平仓
```

## 风险提示

⚠️ 本策略使用高杠杆（5x~8x）合约交易，存在快速亏损甚至爆仓风险。

- 8x 杠杆：价格反向波动 ~12.5% 即触发爆仓
- RSI 超卖信号可能钝化，价格继续下跌 20%~50%
- 请务必充分了解风险后再使用
- **建议先用模拟盘（`--profile demo`）验证**

## 文件结构

```
okx-agent-trade-kit/
├── SKILL.md    # 完整策略文档（含执行流程、命令示例、风险提示）
└── README.md   # 本文件
```

## License

MIT
