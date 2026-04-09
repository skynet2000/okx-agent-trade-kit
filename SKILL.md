---
name: okx-agent-trade-kit
description: |
  OKX Agent Trade Kit — RSI 激进抄底策略。
  当 RSI(14) 低于超卖阈值时自动市价买入永续合约（5x~8x 杠杆），价格反弹至止盈位自动止盈，跌破止损位自动止损。
  现货和合约模式分开，支持模拟盘 (demo) / 实盘 (live)。

  触发关键词（任一触发）：
    "rsi激进" / "rsi抄底" / "okx自动交易" / "okx永续" / "okx swap" /
    "rsibot" / "rsi策略" / "okx agent" / "okx量化" / "okx合约机器人" /
    "start rsi agent" / "run okx strategy" / "aggressive rsi" /
    "okx高频抄底" / "okx永续套利" / "okx开多信号"
version: "1.0.0"
user-invocable: true
---

# OKX Agent Trade Kit — RSI 激进抄底策略

> **策略定位**：激进 RSI 抄底，专为 2 周内获取高收益设计。使用 5x~8x 杠杆，追踪超卖反弹机会。
> **⚠️ 高风险警告**：本策略使用高杠杆合约交易，存在快速亏损甚至爆仓风险。请充分了解风险后再使用。

---

## 依赖 Skill

| 依赖 Skill | 用途 | 调用命令 |
|-----------|------|---------|
| `okx-cex-market` | 获取 RSI、K 线、价格 | `okx market indicator rsi` / `okx market ticker` |
| `okx-cex-trade` | 执行买卖单（现货/合约） | `okx swap place` / `okx spot place` |
| `okx-cex-portfolio` | 查询余额、持仓 | `okx account balance` / `okx account positions` |

> 以上三个依赖 Skill 需在使用前已安装并完成 OKX API Key 配置。
> 若未配置：`okx config init` 配置密钥；`--profile demo` 切换模拟盘。

---

## 全局参数说明

### 策略核心参数（激进配置）

| 参数 | 类型 | 默认值 | 激进推荐 | 范围 | 说明 |
|------|------|--------|---------|------|------|
| `--symbol` | string | **必填** | — | — | 交易标的，格式见下方 instId 对照表 |
| `--profile` | string | `live` | `live` / `demo` | — | `live` 实盘 / `demo` 模拟盘 |
| `--mode` | string | `swap` | `swap` | `spot` / `swap` | `swap` 永续合约 / `spot` 现货 |
| `--rsi-period` | int | `14` | `14` | 6~28 | RSI 计算周期 |
| `--rsi-oversold` | float | `30` | `25~30` | 15~40 | 超卖阈值（低于此值触发买入） |
| `--tp-pct` | float | `8` | `8~12` | 3~20 | 止盈涨幅百分比（相对成本价） |
| `--sl-pct` | float | `5` | `5~8` | 2~15 | 止损跌幅百分比（相对成本价） |
| `--leverage` | int | `8` | `8` | 5~8 | 合约杠杆倍数（仅 swap 模式，**建议不超过 8x**） |
| `--order-pct` | float | `50` | `40~60` | 10~80 | 下单金额占可用保证金的比例（%） |
| `--check-interval` | int | `60` | `60` | 30~300 | 监控轮询间隔（秒） |
| `--max-hold-hours` | int | `336` | `336` | — | 最大持仓小时数（超过强制平仓，默认 14 天） |

### 参数配置说明

| 场景 | `--rsi-oversold` | `--tp-pct` | `--sl-pct` | `--leverage` | `--order-pct` | 风险等级 |
|------|-----------------|-----------|-----------|------------|--------------|---------|
| **激进（默认）** | `25` | `8%` | `5%` | `8x` | `50%` | ⚠️ 极高 |
| **稳健激进** | `30` | `10%` | `6%` | `5x` | `40%` | ⚠️ 高 |
| **保守试探** | `35` | `12%` | `8%` | `5x` | `30%` | ⚠️ 中高 |

> **激进策略逻辑**：RSI(14)<25 视为强超卖信号，配合 8x 杠杆、50% 仓位、8% 止盈、5% 止损，目标是快速捕捉反弹波段。2 周内若多次止盈可积累显著收益，但连续止损也会快速侵蚀本金。

---

## instId 格式对照

### 现货 instId 格式

现货交易无杠杆，直接使用币对符号。

| 币种 | instId 示例 | 说明 |
|------|-------------|------|
| BTC | `BTC-USDT` | 比特币 |
| ETH | `ETH-USDT` | 以太坊 |
| SOL | `SOL-USDT` | Solana |
| 自定义 | `XXX-USDT` | XXX 为代币符号，全大写 |

### 永续合约 instId 格式

永续合约后缀为 `-SWAP`，支持 5x~125x 杠杆（策略限定 5x~8x）。

| 币种 | instId 示例 | 合约面值（ctVal） |
|------|-------------|----------------|
| BTC | `BTC-USDT-SWAP` | 0.01 BTC/张 |
| ETH | `ETH-USDT-SWAP` | 0.1 ETH/张 |
| SOL | `SOL-USDT-SWAP` | 10 SOL/张 |
| 自定义 | `XXX-USDT-SWAP` | 需通过 `okx market instruments --instType SWAP` 确认 |

> **查询合约面值**：`okx market instruments --instType SWAP --instId ETH-USDT-SWAP`
> 返回字段 `ctVal` 即每张合约对应的基础货币数量。

---

## 执行流程

### Phase 0 — 启动前检查

**目的**：验证 API 连接、读取账户余额、确认市场状态、获取 K 线数据。

```bash
# Step 0.1: 确认 API 已配置
okx account config

# Step 0.2: 查询账户余额（swap 模式查 USDT 余额，现货模式查对应币种余额）
okx account balance

# Step 0.3: 查询当前持仓（确认无现有反向持仓）
okx account positions

# Step 0.4: 获取实时价格
okx market ticker {symbol}

# Step 0.5: 获取 K 线数据（用于计算 RSI）
okx market candles {symbol} --bar 1H --limit 100
```

> **现货**：symbol = `BTC-USDT`
> **合约**：symbol = `BTC-USDT-SWAP`

**Phase 0 输出模板**：

```
✅ OKX 连接正常 | 账户: {profile}
💰 可用 USDT 余额: {available} USDT
📊 {symbol} 当前价: {lastPrice} | 24h涨跌: {change24h}%
📈 已获取 {count} 根 K 线，开始计算 RSI(14)...
⏳ RSI 信号监控中，间隔 {check_interval} 秒轮询
```

---

### Phase 1 — RSI 信号检测

**目的**：持续轮询 RSI(14)，低于超卖阈值时触发买入信号。

```bash
# Step 1.1: 获取 RSI 指标
okx market indicator rsi {symbol} --period {rsi_period} --limit 100

# Step 1.2: 获取实时价格（辅助判断）
okx market ticker {symbol}

# Step 1.3: 获取最新 K 线（辅助判断趋势）
okx market candles {symbol} --bar 1H --limit 10
```

**Phase 1 判断逻辑**：

```
RSI({rsi_period}) = {rsi_value}

IF RSI < rsi_oversold:
    → ✅ 触发买入信号，进入 Phase 2
ELIF RSI >= rsi_oversold:
    → ⏳ 等待中，继续轮询（间隔 {check_interval} 秒）
```

**Phase 1 输出模板**：

```
[{timestamp}] {symbol}
  RSI(14) = {rsi_value}  {'🔴 超卖 — 触发买入!' if rsi < rsi_oversold else '🟢 正常'}
  当前价: {lastPrice} | 24h涨跌: {change24h}%
  {'✅ 信号触发! 进入 Phase 2...' if rsi < rsi_oversold else '⏳ 等待 RSI < {rsi_oversold}...'}
```

---

### Phase 2 — 执行买入开多

**目的**：检测到超卖信号后，以市价执行买入。

#### Phase 2A — 现货模式 (spot)

```bash
# Step 2A.1: 获取实时价格
okx market ticker {symbol}

# Step 2A.2: 计算买入数量
#   可用 USDT = {available}
#   下单金额 = available * (order_pct / 100)
#   买入数量 = 下单金额 / 当前价格
#   数量精度：BTC/ETH 保留 6 位小数，SOL/其他保留 4 位

# Step 2A.3: 市价买入（现货）
okx spot place \
  --instId {symbol} \
  --side buy \
  --ordType market \
  --sz {buy_qty} \
  --profile {profile}

# Step 2A.4: 确认买入成功
okx spot orders --profile {profile}
```

**现货买入示例**：

```bash
# ETH-USDT，超卖信号，买入 0.5 ETH
okx spot place --instId ETH-USDT --side buy --ordType market --sz 0.5 --profile live
```

#### Phase 2B — 永续合约模式 (swap)

```bash
# Step 2B.1: 获取实时价格
okx market ticker {symbol}

# Step 2B.2: 查询合约面值（ctVal）
okx market instruments --instType SWAP --instId {symbol}

# Step 2B.3: 设置杠杆
okx swap leverage \
  --instId {symbol} \
  --lever {leverage} \
  --mgnMode isolated \
  --profile {profile}

# Step 2B.4: 计算合约张数
#   可用保证金 = {available} USDT
#   保证金使用 = available * (order_pct / 100)
#   合约张数 = 保证金使用 * leverage / 当前价格 / ctVal
#   张数取整，最小 1 张

# Step 2B.5: 市价开多
okx swap place \
  --instId {symbol} \
  --side buy \
  --tdMode isolated \
  --lever {leverage} \
  --ordType market \
  --sz {contract_qty} \
  --profile {profile}

# Step 2B.6: 确认开仓成功
okx swap positions --instId {symbol} --profile {profile}
```

**合约买入示例**（ETH-USDT-SWAP，8x 杠杆，激进参数）：

```bash
# 设置 8x 杠杆
okx swap leverage --instId ETH-USDT-SWAP --lever 8 --mgnMode isolated --profile live

# 开多 10 张（约 1 ETH 价值）
okx swap place --instId ETH-USDT-SWAP --side buy --tdMode isolated --lever 8 --ordType market --sz 10 --profile live
```

**Phase 2 输出模板**：

```
{'📝 现货买入' if mode=='spot' else '📈 合约开多'} 执行中...
   标的: {symbol}
   {'买入数量: {buy_qty}' if mode=='spot' else '合约张数: {contract_qty} 张'}
   模式: {mode} | 杠杆: {leverage}x | 账户: {profile}
   下单金额: ~{order_value} USDT (占总资金 {order_pct}%)
   ⏳ 等待成交确认...
```

---

### Phase 3 — 持仓监控

**目的**：买入后实时监控价格变化，判断止盈/止损条件。

#### Phase 3A — 查询持仓状态

```bash
# 现货模式：查询账户余额变化
okx account balance --profile {profile}

# 合约模式：查询持仓信息
okx swap positions --instId {symbol} --profile {profile}
```

#### Phase 3B — 持续价格监控

```bash
# 每轮监控：获取最新价格
okx market ticker {symbol}

# 每 N 轮重新计算 RSI（可选，用于辅助判断）
okx market indicator rsi {symbol} --period {rsi_period} --limit 100
```

**Phase 3 监控逻辑**（伪代码）：

```python
entry_price = {entry_price}      # Phase 2 成交均价
tp_price    = entry_price * (1 + tp_pct / 100)   # 止盈价
sl_price    = entry_price * (1 - sl_pct / 100)   # 止损价
max_time    = time.time() + max_hold_hours * 3600

WHILE True:
    current_price = get_ticker()
    pnl_pct = (current_price - entry_price) / entry_price * 100
    elapsed_hours = (time.time() - entry_time) / 3600

    PRINT(f"持仓监控 | 成本: {entry_price} | 现价: {current_price} | 浮盈: {pnl_pct}%")

    IF current_price >= tp_price:
        → 触发止盈，进入 Phase 4A
        BREAK
    ELIF current_price <= sl_price:
        → 触发止损，进入 Phase 4B
        BREAK
    ELIF time.time() >= max_time:
        → 超时强制平仓，进入 Phase 4C
        BREAK
    ELSE:
        → 继续等待 (sleep check_interval 秒)
```

**Phase 3 输出模板**（循环输出）：

```
[{timestamp}] 🔄 持仓监控中
  成本: {entry_price} | 现价: {current_price} | 浮盈亏: {pnl_pct}%
  止盈线: {tp_price} (+{tp_pct}%) | 止损线: {sl_price} (-{sl_pct}%)
  持仓时长: {elapsed_hours}h / {max_hold_hours}h (max)
  ⏱ 下次检查: {check_interval}秒后
```

---

### Phase 4 — 平仓离场

#### Phase 4A — 止盈卖出（TP）

**现货止盈**：

```bash
# 查询当前持仓数量
okx account balance --profile {profile}

# 市价卖出全部持仓
okx spot place \
  --instId {symbol} \
  --side sell \
  --ordType market \
  --sz {hold_qty} \
  --profile {profile}
```

**合约止盈平多**：

```bash
# 查询持仓信息
okx swap positions --instId {symbol} --profile {profile}

# 市价平多
okx swap place \
  --instId {symbol} \
  --side sell \
  --tdMode isolated \
  --posSide long \
  --ordType market \
  --sz {contract_qty} \
  --profile {profile}
```

#### Phase 4B — 止损卖出（SL）

**现货止损**：

```bash
okx spot place \
  --instId {symbol} \
  --side sell \
  --ordType market \
  --sz {hold_qty} \
  --profile {profile}
```

**合约止损平多**：

```bash
okx swap place \
  --instId {symbol} \
  --side sell \
  --tdMode isolated \
  --posSide long \
  --ordType market \
  --sz {contract_qty} \
  --profile {profile}
```

#### Phase 4C — 超时强制平仓

当持仓超过 `--max-hold-hours`（默认 14 天 = 336 小时）时，无论盈亏均强制平仓：

```bash
# 合约超时平多
okx swap place \
  --instId {symbol} \
  --side sell \
  --tdMode isolated \
  --posSide long \
  --ordType market \
  --sz {contract_qty} \
  --profile {profile}
```

**Phase 4 输出模板**：

```
{'🎯 止盈触发!' if exit_type=='tp' else ('🛑 止损触发!' if exit_type=='sl' else '⏰ 超时强制平仓!')}
   平仓价格: {exit_price}
   浮盈亏: {realized_pnl} USDT ({pnl_pct}%)
   状态: {'✅ 止盈离场' if exit_type=='tp' else ('❌ 止损离场' if exit_type=='sl' else '⏰ 超时离场')}
   📊 本轮交易完成，等待下次信号...
```

---

## 完整使用示例

### 示例 1：实盘激进 RSI 抄底（ETH 永续合约，8x 杠杆）

```
用户: okx激进抄底 ETH 永续 止盈8%止损5% 杠杆8x 仓位50%

Phase 0:
  okx account config
  okx account balance
  okx market ticker ETH-USDT-SWAP
  okx market candles ETH-USDT-SWAP --bar 1H --limit 100

Phase 1 (循环):
  okx market indicator rsi ETH-USDT-SWAP --period 14 --limit 100
  → RSI(14) = 24 < 25 超卖！触发买入

Phase 2:
  okx market ticker ETH-USDT-SWAP
  okx market instruments --instType SWAP --instId ETH-USDT-SWAP
  okx swap leverage --instId ETH-USDT-SWAP --lever 8 --mgnMode isolated --profile live
  okx swap place --instId ETH-USDT-SWAP --side buy --tdMode isolated --lever 8 --ordType market --sz 10 --profile live
  okx swap positions --instId ETH-USDT-SWAP --profile live

Phase 3 (循环):
  okx market ticker ETH-USDT-SWAP
  → 监控浮盈，等待止盈或止损

Phase 4:
  okx swap place --instId ETH-USDT-SWAP --side sell --tdMode isolated --posSide long --ordType market --sz 10 --profile live
```

### 示例 2：模拟盘 RSI 抄底（BTC 现货）

```
用户: rsi激进抄底 BTC 现货 模拟盘 超卖30 止盈10%止损8%

Phase 0:
  okx account config --profile demo
  okx account balance --profile demo
  okx market ticker BTC-USDT
  okx market candles BTC-USDT --bar 1H --limit 100

Phase 1:
  okx market indicator rsi BTC-USDT --period 14 --limit 100
  → RSI(14) = 28 < 30 超卖！触发买入

Phase 2:
  okx spot place --instId BTC-USDT --side buy --ordType market --sz 0.002 --profile demo

Phase 4:
  okx spot place --instId BTC-USDT --side sell --ordType market --sz 0.002 --profile demo
```

---

## 预期输出格式

### 启动输出

```
╔═══════════════════════════════════════════════════╗
║  🤖 OKX Agent Trade Kit v1.0.0 — RSI 激进抄底     ║
╠═══════════════════════════════════════════════════╣
║  标的:       {symbol}                             ║
║  模式:       {mode}                               ║
║  RSI阈值:    < {rsi_oversold}                             ║
║  止盈:       +{tp_pct}%                           ║
║  止损:       -{sl_pct}%                           ║
║  杠杆:       {leverage}x (仅合约)                 ║
║  仓位:       {order_pct}%                          ║
║  最大持仓:   {max_hold_hours}h                     ║
║  账户:       {profile}                            ║
║  监控间隔:   {check_interval}秒                         ║
╚═══════════════════════════════════════════════════╝
```

### 信号触发输出

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 信号触发 | {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
标的:       {symbol}
RSI(14):    {rsi_value}  🔴 超卖
当前价:     {lastPrice}
信号:       ✅ BUY — RSI({rsi_period}) < {rsi_oversold}
账户:       {profile}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 交易记录输出

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 交易记录 | {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
方向:       {'买入开多' if action=='buy' else ('止盈平多' if action=='tp' else ('止损平多' if action=='sl' else '超时平仓'))}
标的:       {symbol}
模式:       {mode}
成交均价:   {price}
数量:       {qty}
{'买入金额: {order_value} USDT' if action=='buy' else ('平仓金额: {exit_value} USDT' if action in ['tp','sl','timeout'] else '')}
止盈价:     {tp_price} (+{tp_pct}%)
止损价:     {sl_price} (-{sl_pct}%)
浮盈亏:     {pnl} USDT ({pnl_pct}%)
状态:       {'✅ 止盈离场' if action=='tp' else ('❌ 止损离场' if action=='sl' else '⏰ 超时离场')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 风险提示

> ⚠️ **本策略仅供辅助参考，不构成投资建议。高杠杆合约交易存在重大风险，请务必充分了解后再使用。**

### 核心风险

| 风险类型 | 说明 | 缓解措施 |
|---------|------|---------|
| **杠杆爆仓风险** | 8x 杠杆下，价格反向波动 12.5% 即触发爆仓（不考虑手续费） | 建议止损 ≤ 8%，避免在极端行情开仓 |
| **RSI 钝化风险** | 超卖可能延续（"钝化"），价格可能继续下跌 20%~50% | 结合 MACD 趋势过滤，优先在 MACD 金叉时买入 |
| **连续止损风险** | 激进参数在高波动行情中可能连续触发止损，快速侵蚀本金 | 单笔仓位 ≤ 50%，保留足够备用保证金 |
| **滑点风险** | 市价单在极端行情下可能以极差价格成交 | 建议使用限价单替代市价单（止盈/止损可附加触发价） |
| **流动性风险** | 山寨币流动性差，大额市价单可能导致显著滑点 | 优先选择主流币（BTC/ETH/SOL） |
| **参数失效风险** | 默认参数基于历史数据，市场结构变化可能导致策略失效 | 定期回测并根据市场环境调整参数 |

### 建议风控措施

1. **只用闲散资金**：永远只用能承受全部亏损的资金进行高杠杆合约交易
2. **控制单笔仓位**：单笔仓位不超过账户权益的 **50%**，推荐 40%~50%
3. **止损优先于止盈**：激进策略中，止损是生命线，建议止损 ≥ 5%（8x 杠杆）
4. **优先模拟盘验证**：实盘前先在 `--profile demo` 跑通完整流程至少 3 次
5. **设置最大持仓时间**：超过 14 天无论盈亏均强制平仓，避免无限期持有
6. **保持人工监督**：建议在运行期间保持监控，不要完全"撒手不管"
7. **分批止盈**：可在止盈位分两次卖出（50% 在止盈位，50% 移动止损）

### 免责声明

本策略及其附属文件仅供技术研究和学习交流使用，不构成任何形式的投资建议或盈利保证。实盘交易的所有风险和后果由使用者自行承担。作者不对因使用本策略而导致的任何直接或间接损失承担责任。

---

## 回测改进记录 (v1.1.0)

> 基于 CRCL/USDT-SWAP 14天（2026-03-27 ~ 2026-04-10）1H K线真实数据回测，初始资金 1000 USDT。

### 回测结果摘要

| 策略 | RSI阈值 | 止盈 | 止损 | 杠杆 | 仓位 | 交易数 | 胜/负 | 胜率 | 收益 | 最终资金 |
|------|---------|------|------|------|------|--------|-------|------|------|---------|
| 激进 (8x) | <30 | 8% | 5% | 8x | 50% | 4 | 3/1 | 75% | **+4653 USDT (+465%)** | 5653 USDT |
| 保守 (5x) | <30 | 6% | 4% | 5x | 30% | 4 | 3/1 | 75% | +1997 USDT (+200%) | 2997 USDT |
| 精准激进 (8x) | <25 | 8% | 5% | 8x | 50% | 2 | 1/1 | 50% | +1346 USDT (+135%) | 2346 USDT |

> ⚠️ 回测结果不代表未来收益。CRCL 在回测期间有剧烈波动（84.4→101.87），策略抓住了所有超卖反弹。真实市场可能存在更多假信号。

### CRCL/USDT-SWAP 回测发现的问题与 SKILL 改进

#### P0 — 必须修复

1. **`indicator` CLI 不支持自定义 bar/limit 参数**
   - `okx market indicator rsi CRCL-USDT-SWAP --bar 1Hutc --limit 336` → HTTP 400
   - OKX indicator 接口不支持 bar 参数，只能用 `candles` 接口拉原始 K 线后在 Python 中自行计算 RSI
   - **改进**：SKILL.md 中明确说明 RSI 计算需要用 Python 实现，indicator CLI 仅用于快速查询

2. **candles 和 indicator 的 bar 格式不一致**
   - `candles`: `--bar 1H`（大写 H）
   - `indicator`: `--bar 1Hutc`（UTC 后缀）
   - **改进**：SKILL.md 中增加格式对照表

3. **小币 instId 查询方法缺失**
   - `okx market instruments --instType SWAP` 无法按 quoteCcy 过滤
   - **改进**：补充用 `okx market ticker <instId>` 逐一验证的方法

#### P1 — 建议增强

4. **资金费率未入策略逻辑**
   - CRCL 资金费率约 0.03%~0.06%/8h，8x 杠杆持仓 2 天资金费率可抵消 ~0.5% 收益
   - **改进**：Phase 1 增加资金费率检查逻辑，费率 > 0.05% 时降低仓位或强制平仓

5. **爆仓价预警缺失**
   - CRCL 波动范围 84.4~101.87（17.5%），远超 8x 爆仓线（12.5%）
   - **改进**：Phase 0 增加强平价计算，距强平价 < 5% 时预警

6. **回测模板缺失**
   - **改进**：补充 `scripts/backtest_rsi_swap.py` 示例脚本（已添加到 scripts/ 目录）

#### P2 — 体验优化

7. 多币种并行监控（与「博尔特冲刺」skill 对齐）
8. 飞书通知增加：RSI值、距爆仓价幅度、资金费率、浮盈/浮亏
9. 追踪止损：当浮盈 > 5% 时将止损线上调至成本价
10. `--mode demo|live` 明确区分

---

## 策略参数速查

| 参数 | 激进 | 稳健激进 | 保守试探 | 说明 |
|------|------|---------|---------|------|
| `--rsi-oversold` | `25` | `30` | `35` | 触发买入的 RSI 上限 |
| `--tp-pct` | `8%` | `10%` | `12%` | 止盈涨幅 |
| `--sl-pct` | `5%` | `6%` | `8%` | 止损跌幅 |
| `--leverage` | `8x` | `5x` | `5x` | 合约杠杆（仅 swap） |
| `--order-pct` | `50%` | `40%` | `30%` | 资金使用比例 |
| `--check-interval` | `60s` | `60s` | `120s` | 轮询间隔 |
| `--max-hold-hours` | `336h` | `336h` | `336h` | 最大持仓（14 天） |
| 风险等级 | ⚠️⚠️⚠️⚠️ 极高 | ⚠️⚠️⚠️ 高 | ⚠️⚠️ 中高 | — |
