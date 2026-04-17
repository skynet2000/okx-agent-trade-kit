# 黄金网格套利策略 - 使用指南

## 快速开始

### 1. 加载策略

当您说以下内容时，策略自动加载：
- "做黄金交易"
- "黄金网格"
- "XAU交易"
- "黄金套利"

### 2. 策略参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| symbol | XAU-USDT-SWAP | 交易对 |
| grid_count | 6 | 网格档数 |
| grid_spacing | 0.5% | 网格间距 |
| leverage | 3x | 杠杆倍数 |
| max_position | 100张 | 最大仓位 |
| stop_loss | 2% | 止损比例 |

### 3. 执行示例

#### 获取黄金行情
```bash
okx market ticker XAU-USDT-SWAP
```

#### AI判断流程
1. 采集15分钟K线数据
2. 计算布林带、EMA、ATR指标
3. 采集宏观情绪(DXY、VIX)
4. 输出交易决策

#### 开仓示例
```bash
# 做多入场
okx swap place --instId XAU-USDT-SWAP --tdMode cross --side buy --posSide long --ordType market --sz 60 --lever 3

# 设置止盈止损
okx swap algo place --instId XAU-USDT-SWAP --posSide long --side sell --ordType oco --sz 60 --tpTriggerPx 4950 --slTriggerPx 4680
```

---

## 策略详解

### AI判断逻辑

```
分数 = 价格位置(30%) + 趋势(25%) + 波动率(20%) + 情绪(15%) + 成交量(10%)

IF 分数 > 0.8 AND 放量: STRONG_BUY
ELIF 分数 > 0.6: BUY  
ELIF 分数 < 0.2 AND 缩量: STRONG_SELL
ELIF 分数 < 0.4: SELL
ELSE: WAIT
```

### 风控规则

| 规则 | 限制 |
|---|---|
| 日内最大亏损 | 5% |
| 最大回撤 | 10% |
| 连续3笔止损 | 暂停24小时 |
| mgnRatio < 15% | 强制平仓 |

---

## 注意事项

- 建议使用模拟盘测试
- 极端行情暂停交易
- 周末不交易
- 美联储决议前后2小时不交易
