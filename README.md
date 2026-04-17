# Agent Trade Kit

> RSI 激进抄底策略 + 技术分析引擎 — 永续合约自动化交易 Skill **v1.4**
>
> ⚠️ **第三方声明**：本工具为第三方社区作品，**与 OKX 官方无关**，仅供学习研究。

## 功能概述

### 交易机器人（agent-trade-kit）

基于 RSI(14) 超卖信号的永续合约自动交易机器人（v1.4），通过 OKX CLI 访问交易所 API。

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

## Skills

本项目包含以下交易Skills：

| Skill | 说明 |
|-------|------|
| [gold-grid-arbitrage](skills/gold-grid-arbitrage.md) | 黄金网格套利策略 |

### 黄金网格套利 (gold-grid-arbitrage)

针对XAU-USDT-SWAP(黄金合约)的自动化网格交易和套利策略。

- **核心逻辑**：在震荡行情中，通过多档网格委托低买高卖
- **AI判断**：5维度综合分析(价格位置/趋势/波动率/情绪/成交量)
- **风控**：仓位控制/资金管理/熔断机制

触发词："做黄金交易"、"黄金网格"、"XAU交易"

---

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
agent-trade-kit/
├── SKILL.md                        # 交易策略文档（v1.4，含 Phase 0~4 + P0/P1/P2/P3）
├── README.md                       # 本文件
├── kline-indicator/                # 技术分析引擎 Skill
│   ├── SKILL.md                    # 技术分析引擎策略文档
│   ├── _meta.json                  # Skill 元信息
│   ├── indicators.md               # 指标参考手册
│   ├── orderflow.md                # 订单流分析参考
│   ├── three-pillars.md            # 三支柱评分框架
│   ├── trading.md                  # 交易计划参考
│   ├── references/                 # 参考文档
│   │   ├── indicators.md
│   │   ├── orderflow.md
│   │   ├── three-pillars.md
│   │   └── trading.md
│   └── scripts/                    # 分析脚本
│       ├── kline_chart.py          # K 线图表生成
│       ├── kline_ext_indicators.py # 扩展指标计算（130+ 因子）
│       └── kline_orderflow.py      # 订单流与深度分析
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

### v1.3 — P3 ATR 动态止盈止损（2026-04-10）

ATR（Average True Range）驱动的自适应止盈止损系统，替代固定百分比策略。

**新增功能：**
- Wilder 平滑 ATR(14) 计算，替代简单移动平均
- 动态 TP/SL：`TP = Entry + tp_atr × ATR(14)`，`SL = Entry - sl_atr × ATR(14)`
- 每轮交易前自动刷新 ATR 值，适应市场波动变化
- ATR 安全检查：ATR 过小时拒绝开仓（防止低波动假信号）

**相关脚本：** `run_tracking.py`（ATR 动态止盈止损 + 追踪止损）

**提交：** `ff2b484`

---

### v1.2 — P2 体验增强（2026-04-10）

从单币种手动运行升级为多币种自动化监控 + 实时通知。

**新增功能：**
- 多币种 RSI+ATR 并行扫描器（`multi_coin_scanner.py`），支持 3~6 个币种同时监控
- 飞书通知增强（`feishu_notify.py`）：RSI 预警卡片、强平价预警、浮盈/浮亏推送、资金费率提醒
- 追踪止损：浮盈 > 5% 时自动上调 SL 至成本价，锁定利润
- `--profile demo/live` 明确区分模拟盘和实盘，全链路参数隔离

**相关脚本：** `multi_coin_scanner.py`、`feishu_notify.py`、`run_tracking.py`

**提交：** `00a9690`

---

### v1.1 — P0/P1 基础修复与回测（2026-04-09）

针对 v1.0 实际运行中发现的问题进行修复，并加入回测验证。

**P0 紧急修复：**
- OKX `indicator` CLI 调用限制修复（API 返回 403 问题）
- K 线 bar 格式对照表（确保各交易所格式兼容）
- `usdt_swaps` 过滤（仅扫描 USDT 永续合约，排除币本位）

**P1 风控增强：**
- 资金费率（Funding Rate）获取 + 高 FR 降仓逻辑
- 强平价计算（`calc_liquidation_price`）+ 距强平价过近预警
- CRCL/USDT-SWAP 14 天回测（2026-03-28 ~ 2026-04-09，初始 1000 USDT）
- 独立回测报告文件 `docs/backtest_report_v1.1.md`

**回测结果：** 激进策略 (8x) 4 笔交易 75% 胜率 +465%

**相关脚本：** `backtest_rsi_swap.py`

**提交：** `d3b4059`、`ae246cb`

---

### v1.0 — 初始版本（2026-04-09）

项目从零搭建，实现 RSI 超卖信号自动抄底的核心框架。

**核心功能：**
- Phase 0~4 完整交易生命周期（启动检查 → RSI 监测 → 执行买入 → 持仓监控 → 平仓离场）
- RSI(14) 超卖信号触发市价开多
- 固定百分比止盈/止损（`+8%` / `-5%`）
- 5x~8x 可调杠杆，逐仓模式
- 现货（spot）/ 永续合约（swap）双模式
- 基础持仓监控与平仓逻辑

**提交：** `394828f`

---

### 安全修复（2026-04-10）

移除脚本中硬编码的 API 密钥，改为环境变量读取。

- `auto_scan_trade.py`：硬编码 → `os.environ.get("OKX_API_KEY", "")`
- `auto_scan_trade.ps1`：硬编码 → `$env:OKX_API_KEY` 环境变量
- 启动时检查环境变量是否设置，未设置则退出并提示

**提交：** `16fca3b`

---

### 文档更新（2026-04-10）

README 增加 `kline-indicator` 技术分析引擎和 `auto_scan_trade` 脚本描述。

**新增内容：**
- 技术分析引擎功能概述（三支柱评分、130+ 因子、订单流等）
- 技术分析引擎使用模式表（quick/full/scan/chart/orderflow/macro）
- 更新文件结构，补充 `kline-indicator/` 和 `auto_scan_trade` 脚本

**提交：** `b73b0dd`

## License

MIT
