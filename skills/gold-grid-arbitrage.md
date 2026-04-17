---
name: gold-grid-arbitrage
description: |
  黄金网格套利交易策略Skill。专门针对XAU-USDT-SWAP（黄金合约）进行自动化网格交易和套利。
  适用于：用户要求做黄金交易、黄金网格交易、黄金套利、XAU-USDT交易、黄金量化策略等场景。
  包含完整的行情采集、市场情绪分析、AI综合判断、自动下单、止盈止损设置和风控规则。
---

# 黄金网格套利交易策略

## 策略名称

**黄金网格套利 v1.0** (Gold Grid Arbitrage)

核心逻辑：在黄金合约(XAU-USDT-SWAP)震荡行情中，通过在价格区间内设置多档网格委托，
低买高卖赚取波动收益。结合市场情绪分析和AI判断，在趋势明确时调整网格方向。

---

## 执行节奏

| 阶段 | 频率 | 说明 |
|---|---|---|
| 行情采集 | 每5分钟 | 获取XAU-USDT-SWAP实时行情 |
| 情绪分析 | 每15分钟 | 采集宏观情绪、机构动向 |
| AI判断 | 每15分钟 | 综合分析后输出交易决策 |
| 订单执行 | 触发式 | 仅当AI明确指示开仓时执行 |
| 风控检查 | 实时 | 止盈止损触发立即执行 |

---

## Step 1 · 行情数据采集

### 1.1 获取实时行情

```bash
okx market ticker XAU-USDT-SWAP
```

采集字段：
- `last` - 最新价
- `askPx` / `bidPx` - 卖一/买一价
- `open24h` - 24h开盘价
- `high24h` / `low24h` - 24h最高/最低
- `volCcy24h` - 24h成交量(USD)

### 1.2 获取K线数据

```bash
okx market candles XAU-USDT-SWAP --bar 15m --limit 50
```

分析：
- 布林带(BB)：判断超买超卖
- EMA(20,50)：判断趋势方向
- ATR：计算波动率，设置网格间距

### 1.3 计算关键指标

```python
# 网格间距 = ATR * 系数(默认0.5)
grid_size = atr * 0.5

# 震荡区间 = low24h ~ high24h
# 网格数量 = 区间 / grid_size (建议5-10档)
```

---

## Step 2 · 市场情绪采集

### 2.1 黄金关联市场

| 市场 | 数据源 | 指标 |
|---|---|---|
| 美元指数 | web_fetch DXY | DXY > 105 黄金承压 |
| 美债收益率 | web_fetch 10Y Treasury | 收益率上涨黄金承压 |
| VIX恐慌指数 | web_fetch VIX | VIX > 20 避险需求上升 |

### 2.2 宏观事件

使用 `news-briefing` skill 获取：
- 美联储政策动向
- 地缘政治事件
- 经济数据发布(非农/CPI/利率决议)

### 2.3 技术面情绪

- 成交量放大：volCcy24h > 过去7天平均1.5倍 = 情绪活跃
- 突破信号：价格突破high24h = 多头情绪强
- 支撑测试：价格触及low24h反弹 = 多头抵抗强

---

## Step 3 · AI 综合判断 (核心)

### 3.1 输入参数

| 参数 | 来源 | 权重 |
|---|---|---|
| 价格位置 | (last - low24h) / (high24h - low24h) | 30% |
| 趋势方向 | EMA20 vs EMA50 (多头/空头/震荡) | 25% |
| 波动率 | ATR相对历史 | 20% |
| 市场情绪 | 宏观 + 事件 | 15% |
| 成交量 | 放量/缩量 | 10% |

### 3.2 输出决策

| AI判断 | 代码 | 说明 |
|---|---|---|
| **强烈做多** | STRONG_BUY | 突破+放量+宏观利好 → 开启多头网格 |
| **轻微做多** | BUY | 震荡偏多 → 观望或轻仓 |
| **观望** | WAIT | 无明确方向 → 不开仓 |
| **轻微做空** | SELL | 震荡偏空 → 观望或轻仓 |
| **强烈做空** | STRONG_SELL | 破位+缩量+宏观利空 → 开启空头网格 |

### 3.3 判断逻辑伪代码

```
IF 价格位置 > 0.85 AND 放量 AND 多头趋势:
    RETURN STRONG_BUY
ELIF 价格位置 < 0.15 AND 放量 AND 空头趋势:
    RETURN STRONG_SELL
ELIF EMA20 > EMA50 AND 成交量放大:
    RETURN BUY
ELIF EMA20 < EMA50 AND 成交量缩小:
    RETURN SELL
ELSE:
    RETURN WAIT
```

---

## Step 4 · 执行下单 (仅当 AI 判断明确开仓时)

### 4.1 开仓条件

仅当AI判断为 `STRONG_BUY` 或 `STRONG_SELL` 时执行。

### 4.2 网格参数设置

| 参数 | 默认值 | 可调 |
|---|---|---|
| 交易对 | XAU-USDT-SWAP | 固定 |
| 杠杆 | 3x | 建议3-5x |
| 网格数量 | 6档 | 5-10档 |
| 网格间距 | 0.5% | 0.3%-1% |
| 每档数量 | 10张 | 根据仓位调整 |

### 4.3 开仓命令

```bash
# 做多网格 (STRONG_BUY)
okx swap place --instId XAU-USDT-SWAP --tdMode cross --side buy --posSide long --ordType market --sz 60 --lever 3

# 做空网格 (STRONG_SELL)
okx swap place --instId XAU-USDT-SWAP --tdMode cross --side sell --posSide short --ordType market --sz 60 --lever 3
```

### 4.4 网格委托设置

每一档设置限价买入/卖出：

```bash
# 做多网格 - 在各个价位设置卖出限价
okx swap algo place --instId XAU-USDT-SWAP --posSide long --side sell --ordType limit --sz 10 --px 4850
okx swap algo place --instId XAU-USDT-SWAP --posSide long --side sell --ordType limit --sz 10 --px 4900
# ... 依此类推
```

---

## Step 5 · 止盈止损设置

### 5.1 止盈规则

| 条件 | 止盈位置 |
|---|---|
| 震荡行情 | 网格顶部 + 1% |
| 趋势行情 | 移动止盈(追踪最高点-2%) |

```bash
# 固定止盈
okx swap algo place --instId XAU-USDT-SWAP --posSide long --side sell --ordType oco --sz 60 --tpTriggerPx 4950 --slTriggerPx 4680
```

### 5.2 止损规则

| 条件 | 止损位置 |
|---|---|
| 初始止损 | 入场价 - 2% |
| 追踪止损 | 最高盈利点回撤2% |

### 5.3 移动止盈(趋势延续)

当盈利超过3%后，启用移动止盈：
- 每上涨1%，将止损线上移0.5%
- 确保至少保留50%盈利

---

## 风控规则

### 6.1 仓位控制

| 规则 | 限制 |
|---|---|
| 单次最大仓位 | 100张 |
| 最大杠杆 | 5x |
| 最大持仓时间 | 72小时 |
| 日内最大交易次数 | 3次 |

### 6.2 资金控制

| 规则 | 限制 |
|---|---|
| 单日最大亏损 | 总资金5% |
| 最大回撤 | 总资金10% |
| 保留可用资金 | 至少20% |

### 6.3 熔断机制

| 触发条件 | 动作 |
|---|---|
| 连续3笔止损 | 暂停交易24小时 |
| mgnRatio < 30% | 强平警告，追加保证金 |
| mgnRatio < 15% | 强制平仓 |

### 6.4 禁止交易时段

- 非农/CPI发布前1小时
- 美联储利率决议前后2小时
- 周末(周五22:00 - 周日22:00 UTC+8)

### 6.5 异常处理

| 情况 | 处理 |
|---|---|
| 订单失败 | 重试3次，间隔10秒 |
| 网络断连 | 记录状态，恢复后检查仓位 |
| 极端行情(1分钟波动>2%) | 暂停新开仓，只处理止盈止损 |

---

## 配置文件模板

```json
{
  "strategy": "gold-grid-arbitrage",
  "symbol": "XAU-USDT-SWAP",
  "grid_count": 6,
  "grid_spacing": 0.005,
  "leverage": 3,
  "max_position": 100,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.03,
  "max_daily_loss": 0.05,
  "max_drawdown": 0.10,
  "halt_conditions": {
    "consecutive_losses": 3,
    "margin_ratio_warning": 0.30,
    "margin_ratio_force": 0.15
  }
}
```

---

## 使用流程

1. **加载Skill** → 本Skill自动触发
2. **执行Step 1** → 采集XAU-USDT-SWAP行情
3. **执行Step 2** → 采集宏观情绪
4. **执行Step 3** → AI综合判断
5. **若为STRONG_BUY/SELL** → 执行Step 4开仓
6. **开仓后** → 执行Step 5设置止盈止损
7. **持续监控** → 遵循风控规则

---

## 注意事项

- 本策略仅适用于XAU-USDT-SWAP(黄金合约)
- 网格交易适合震荡行情，单边趋势需调整策略
- 建议在实盘前使用模拟盘(OKX Demo)测试
- 遇到极端行情立即停止自动交易
