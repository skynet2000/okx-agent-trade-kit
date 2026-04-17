---
name: gold-grid-arbitrage
description: |
  黄金网格套利交易策略Skill。专门针对XAU-USDT-SWAP（黄金合约）进行自动化网格交易和套利。
  适用于：用户要求做黄金交易、黄金网格交易、黄金套利、XAU-USDT交易、黄金量化策略等场景。
  包含完整的行情采集、市场情绪分析、AI综合判断、自动下单、止盈止损设置和风控规则。
  v1.1新增：资金费率过滤、ATR动态止损、5x杠杆高频模式。
---

# 黄金网格套利交易策略 v1.1

## 策略名称

**黄金网格套利 v1.1** (Gold Grid Arbitrage - High Frequency)

核心变更(v1.1 vs v1.0)：
- 杠杆 3x → **5x**（提高资金利用率）
- AI信号阈值 2.5 → **1.8**（提高交易频率）
- 固定止损 → **ATR动态止损**（更科学）
- 新增 **资金费率过滤**（空头付费时做多占优）
- 日限交易 2笔 → **3笔**

---

## 执行节奏

| 阶段 | 频率 | 说明 |
|---|---|---|
| 行情采集 | 每5分钟 | 获取XAU-USDT-SWAP实时行情 |
| 资金费率 | 每8小时 | 获取funding rate，判断多空付费方向 |
| 情绪分析 | 每15分钟 | 采集宏观情绪、机构动向 |
| AI判断 | 每15分钟 | 综合分析后输出交易决策 |
| 订单执行 | 触发式 | 仅当AI明确指示开仓时执行 |
| 风控检查 | 实时 | ATR动态止损触发立即执行 |

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
- ATR：计算波动率，**动态设置止损止盈**

### 1.3 计算关键指标

```python
# ATR动态止损
atr = calc_atr(highs, lows, closes, period=14)

# 止损 = 入场价 - ATR * 1.5
sl_price = entry_price - atr * 1.5

# 止盈 = 入场价 + ATR * 2.0
tp_price = entry_price + atr * 2.0

# R:R = 2.0 / 1.5 = 1.33:1
```

### 1.4 获取资金费率（新增）

```bash
okx market funding-rate XAU-USDT-SWAP
```

关键字段：
- `fundingRate` - 当前资金费率
- `nextFundingTime` - 下次结算时间
- `predictedFundingRate` - 预测费率

**资金费率过滤规则：**
| 费率 | 含义 | 操作倾向 |
|---|---|---|
| < -0.01% | 空头付费多头 | ✅ 做多有利，信号+0.5 |
| -0.01% ~ 0.01% | 中性 | 正常交易 |
| 0.01% ~ 0.05% | 多头付费空头 | ⚠️ 做多谨慎，信号-0.3 |
| > 0.05% | 多头大量付费 | ❌ 不做多，可考虑做空 |

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
| 价格位置 | (last - low24h) / (high24h - low24h) | 25% |
| 趋势方向 | EMA20 vs EMA50 (多头/空头/震荡) | 20% |
| 波动率/ATR | ATR相对历史 | 15% |
| **资金费率** | **funding rate方向** | **15%** |
| 市场情绪 | 宏观 + 事件 | 15% |
| 成交量 | 放量/缩量 | 10% |

### 3.2 输出决策

| AI判断 | 代码 | 信号分 | 说明 |
|---|---|---|---|
| **强烈做多** | STRONG_BUY | ≥3.5 | 突破+放量+费率有利 → 全仓网格 |
| **做多** | BUY | 1.8~3.5 | 震荡偏多+费率中性 → 轻仓网格 |
| **观望** | WAIT | -1.0~1.8 | 无明确方向 → 不开仓 |
| **做空** | SELL | -3.5~-1.0 | 震荡偏空+费率不利 → 轻仓空 |
| **强烈做空** | STRONG_SELL | ≤-3.5 | 破位+缩量+费率极端 → 全仓空 |

### 3.3 判断逻辑伪代码

```
score = price_position(25%) + trend(20%) + atr(15%) + funding(15%) + sentiment(15%) + volume(10%)

# 资金费率过滤 (v1.1新增)
IF funding_rate < -0.0001:   # 空头付费
    score += 0.5
ELIF funding_rate > 0.0005:  # 多头大量付费
    score -= 0.5

# ATR动态调整
atr = calc_atr(14)
sl_distance = atr * 1.5
tp_distance = atr * 2.0

# 开仓判断
IF score >= 3.5 AND price_pos < 0.7:
    RETURN STRONG_BUY, sl=entry-atr*1.5, tp=entry+atr*2.0
ELIF score >= 1.8:
    RETURN BUY, sl=entry-atr*1.5, tp=entry+atr*2.0
ELIF score <= -3.5 AND price_pos > 0.3:
    RETURN STRONG_SELL, sl=entry+atr*1.5, tp=entry-atr*2.0
ELIF score <= -1.0:
    RETURN SELL, sl=entry+atr*1.5, tp=entry-atr*2.0
ELSE:
    RETURN WAIT
```

---

## Step 4 · 执行下单 (仅当 AI 判断明确开仓时)

### 4.1 开仓条件

仅当AI判断为 `STRONG_BUY`/`BUY` 或 `STRONG_SELL`/`SELL` 时执行。

### 4.2 网格参数设置

| 参数 | 默认值 | 可调 |
|---|---|---|
| 交易对 | XAU-USDT-SWAP | 固定 |
| 杠杆 | **5x** | 建议3-5x |
| 网格数量 | **5档** | 5-10档 |
| 网格间距 | ATR*0.5 | 0.3%-1% |
| 每档数量 | 10张 | 根据仓位调整 |
| 最大日交易 | **3笔** | 2-5笔 |

### 4.3 开仓命令

```bash
# 做多网格 (BUY/STRONG_BUY)
okx swap place --instId XAU-USDT-SWAP --tdMode cross --side buy --posSide long --ordType market --sz 50 --lever 5

# 做空网格 (SELL/STRONG_SELL)
okx swap place --instId XAU-USDT-SWAP --tdMode cross --side sell --posSide short --ordType market --sz 50 --lever 5
```

---

## Step 5 · 止盈止损设置

### 5.1 ATR动态止损（核心变更）

```python
atr = calc_atr(highs, lows, closes, period=14)

# 做多止损
sl_price = entry_price - atr * 1.5

# 做多止盈
tp_price = entry_price + atr * 2.0

# 做空止损
sl_price = entry_price + atr * 1.5

# 做空止盈
tp_price = entry_price - atr * 2.0
```

**ATR止损的优势：**
- 高波动时止损更宽，避免被震出
- 低波动时止损更紧，保护利润
- R:R固定在1.33:1，长期正期望

### 5.2 移动止盈（趋势延续）

当盈利超过ATR*1.0后，启用追踪止损：
- 止损线 = 最高价 - ATR * 1.0
- 确保至少保留50%盈利

### 5.3 资金费率过滤止损

| 条件 | 动作 |
|---|---|
| fundingRate从负转正 | 多单考虑减仓 |
| fundingRate > 0.05% | 多单强制止损 |
| fundingRate从正转负 | 空单考虑减仓 |

---

## 风控规则

### 6.1 仓位控制

| 规则 | 限制 |
|---|---|
| 单次最大仓位 | 100张 |
| 最大杠杆 | **5x** |
| 最大持仓时间 | 48小时 |
| 日内最大交易次数 | **3次** |
| 单仓上限 | 总资金**40%** |

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
| **fundingRate极端** | **>0.1%禁止做多，<-0.1%禁止做空** |

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
  "version": "1.1",
  "symbol": "XAU-USDT-SWAP",
  "grid_count": 5,
  "leverage": 5,
  "signal_threshold": 1.8,
  "atr_sl_multiplier": 1.5,
  "atr_tp_multiplier": 2.0,
  "atr_period": 14,
  "max_daily_trades": 3,
  "max_position": 100,
  "max_daily_loss": 0.05,
  "max_drawdown": 0.10,
  "funding_filter": {
    "long_favorable": -0.0001,
    "long_caution": 0.0005,
    "long_forbidden": 0.001
  },
  "halt_conditions": {
    "consecutive_losses": 3,
    "margin_ratio_warning": 0.30,
    "margin_ratio_force": 0.15
  }
}
```

---

## v1.0 → v1.1 变更日志

| 项目 | v1.0 | v1.1 |
|---|---|---|
| 杠杆 | 3x | **5x** |
| 信号阈值 | 2.5 | **1.8** |
| 止损方式 | 固定1%/2% | **ATR*1.5动态** |
| 止盈方式 | 固定1.5%/3% | **ATR*2.0动态** |
| 资金费率 | 无 | **✅ 新增过滤** |
| 日限交易 | 2笔 | **3笔** |
| 网格档数 | 6档 | **5档** |
| 单仓上限 | 30% | **40%** |
| R:R | 1.5:1 | **1.33:1(ATR)** |
