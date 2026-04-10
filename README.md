# OKX Agent Trade Kit

> RSI 激进抄底策略 + 技术分析引擎 — OKX 永续合约自动化交易 Skill **v1.3**

## 功能概述

### 交易机器人（okx-agent-trade-kit）

基于 RSI(14) 超卖信号的 OKX 永续合约自动交易机器人（v1.3）。

- **触发逻辑**：RSI(14) < 超卖阈值 → 市价买入开多
- **止盈逻辑**：价格上涨 +{tp-pct}% → 市价止盈卖出
- **止损逻辑**：价格下跌 -{sl-pct}% → 市价止损卖出
- **追踪止损**：浮盈 > 5% 时自动上调 SL 至成本价（锁定利润）
- **合约杠杆**：5x ~ 8x 可调
- **交易模式**：永续合约（swap）或现货（spot）
- **账户模式**：模拟盘（demo）/ 实盘（live）
- **多币种**：支持 3~6 个币种并行监控
- **飞书通知**：实时推送 RSI、强平价、资金费率、浮盈/浮亏

### 技术分析引擎（kline-indicator）

机构级技术分析中台，覆盖 100+ 指标、30+ K线形态与三支柱评分框架。

- **三支柱评分**：宏观周期 × 量价因子 × 衍生品，0-100 综合评分定位周期位置
- **130+ 量价因子**：WorldQuant Alpha 101/191 因子体系
- **自动背离检测**：RSI/MACD/OBV 背离识别
- **K线形态识别**：30+ 经典形态（吞没、锤子线、十字星等）
- **衍生品数据**：资金费率深度、DVOL、爆仓热力图
- **订单流分析**：Delta、CVD、订单簿深度
- **多面板 K 线图表**：直接在终端渲染
- **宏观周期工具**：Rainbow Chart、AHR999、MVRV 等

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

在支持 OpenClaw 等 AI 助手中，直接描述你的需求即可触发本 Skill：

```
"okx激进抄底 ETH 永续 止盈8%止损5% 杠杆8x 仓位50%"
```

```
"rsi激进 BTC-USDT-SWAP 模拟盘"
```

技术分析引擎：

```
"分析BTC"
"画个K线图"
"扫描热门币"
"BTC能不能做多"
```

## 核心参数

### 交易机器人

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--rsi-oversold` | `25` | 超卖阈值（低于此值触发买入） |
| `--tp-atr` | `2.0x ATR` | 止盈 ATR 倍数：`TP = Entry + tp_atr × ATR(14)` |
| `--sl-atr` | `1.5x ATR` | 止损 ATR 倍数：`SL = Entry - sl_atr × ATR(14)` |
| `--leverage` | `8x` | 合约杠杆（5x~8x） |
| `--order-pct` | `50%` | 单笔仓位占保证金比例 |
| `--check-interval` | `60s` | 信号轮询间隔 |

### 技术分析引擎

| 模式 | 触发词 | 说明 |
|------|--------|------|
| **quick** | "看行情"、"怎么样" | 快速扫描，一句话出结果 |
| **full** | "完整分析"、"详细分析" | 全量三支柱分析 + 订单流 |
| **scan** | "扫描"、"热门币" | 多币种批量扫描 |
| **chart** | "K线图"、"画图" | 生成多面板 K 线图表 |
| **orderflow** | "订单流"、"Delta" | 订单簿深度分析 |
| **macro** | "周期"、"宏观数据" | 宏观周期定位 |

## 策略逻辑

```
Phase 0: 启动检查 → API连接、余额查询、K线获取
Phase 1: RSI监测 → 持续轮询 RSI(14)，低于阈值触发信号
Phase 2: 执行买入 → 市价开多（现货/合约）
Phase 3: 持仓监控 → 实时追踪止盈/止损/超时
Phase 4: 平仓离场 → 止盈/止损/超时强制平仓
```

## 风险提示

> **本策略使用高杠杆（5x~8x）合约交易，存在快速亏损甚至爆仓风险。**

- 8x 杠杆：价格反向波动 ~12.5% 即触发爆仓
- RSI 超卖信号可能钝化，价格继续下跌 20%~50%
- 请务必充分了解风险后再使用
- **建议先用模拟盘（`--profile demo`）验证**

## 回测结果

> 基于 CRCL/USDT-SWAP 真实 1H K线数据（2026-03-28 ~ 2026-04-09），初始资金 1000 USDT

| 策略 | RSI | 止盈 | 止损 | 杠杆 | 仓位 | 交易数 | 胜率 | 总收益 | 最终资金 |
|------|-----|------|------|------|------|--------|------|--------|---------|
| 激进 (8x) | <30 | 8% | 5% | 8x | 50% | 4 | 75% | **+4653 USDT (+465%)** | 5653 USDT |
| 保守 (5x) | <30 | 6% | 4% | 5x | 30% | 4 | 75% | +1997 USDT (+200%) | 2997 USDT |
| 精准激进 (8x) | <25 | 8% | 5% | 8x | 50% | 2 | 50% | +1346 USDT (+135%) | 2346 USDT |

> **回测结果不代表未来收益。** 策略在 CRCL 高波动期（84.4~101.87，17.5%振幅）抓住了所有反弹。真实市场可能存在更多假信号导致亏损。

## 文件结构

```
okx-agent-trade-kit/
├── SKILL.md                        # 交易策略文档（v1.3，含 Phase 0~4 + P0/P1/P2/P3）
├── README.md                       # 本文件
├── kline-indicator/                # 技术分析引擎 Skill
│   ├── SKILL.md                    # 技术分析引擎策略文档
│   ├── _meta.json                  # Skill 元信息
│   ├── indicators.md               # 指标参考手册
│   ├── orderflow.md                # 订单流分析参考
│   ├── three-pillars.md            # 三支柱评分框架
│   ├── trading.md                  # 交易计划参考
│   ├── kline_chart.py              # K 线图表生成
│   ├── kline_ext_indicators.py     # 扩展指标计算（130+ 因子）
│   └── kline_orderflow.py          # 订单流与深度分析
│       references/
│       ├── indicators.md
│       ├── orderflow.md
│       ├── three-pillars.md
│       └── trading.md
│       scripts/
│       ├── kline_chart.py
│       ├── kline_ext_indicators.py
│       └── kline_orderflow.py
├── docs/
│   └── backtest_report_v1.1.md     # 回测报告（v1.1）
└── scripts/
    ├── auto_scan_trade.py          # 市场扫描自动交易（Python，直接 API）
    ├── auto_scan_trade.ps1         # 市场扫描自动交易（PowerShell，OKX CLI）
    ├── backtest_rsi_swap.py        # RSI 回测脚本
    ├── multi_coin_scanner.py       # 多币种 RSI+ATR 扫描器 (P2-1, P3-1)
    ├── feishu_notify.py            # 飞书通知模块 (P2-2, P3)
    └── run_tracking.py             # ATR 动态止盈止损 + 追踪止损 (P2-3, P3)
```

## 回测报告

详细回测结果见 [docs/backtest_report_v1.1.md](docs/backtest_report_v1.1.md)，包含：
- 三种策略参数对比（激进/保守/精准激进）
- 4 笔交易明细
- **P0/P1 改进**：indicator CLI 限制、bar 格式对照表、小币过滤、资金费率风控、强平价预警
- **P2 改进**：多币种并行、飞书通知增强（RSI/强平/PnL）、追踪止损（>5% SL 锁成本）、demo/live 明确区分
- **P3 改进**：ATR 动态止盈止损（Wilder 平滑）、ATR 安全检查、每轮动态更新 ATR

## 版本历史

- **v1.3** — P3 ATR 动态止盈止损：Wilder 平滑 ATR(14)、动态 TP/SL 自适应波动、ATR 安全检查
- **v1.2** — P2 体验增强：多币种扫描 + 飞书通知 + 追踪止损 + demo/live
- **v1.1** — P0/P1 修复：indicator CLI 限制 + bar 格式对照 + 资金费率 + 强平价预警
- **v1.0** — 初始版本：RSI 超卖信号 + Phase 0~4 基础框架

## License

MIT
