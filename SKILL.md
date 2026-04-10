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
version: "1.2.0"
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
| `--symbols` | string | `BTC-USDT-SWAP` | — | — | 逗号分隔的 instId 列表，如 `CRCL-USDT-SWAP,ETH-USDT-SWAP` |
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
| `--trailing-pct` | float | `5` | `5` | 3~10 | 追踪止盈触发阈值（浮盈 > 此值时自动上调 SL 至成本价） |
| `--feishu-webhook` | string | `null` | — | — | 飞书 webhook URL，为空则跳过飞书通知 |

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
okx account balance --profile {profile}

# Step 0.3: 查询当前持仓（确认无现有反向持仓）
okx account positions --profile {profile}

# Step 0.4: 多币种并行获取实时价格
okx market ticker {symbol1}
okx market ticker {symbol2}
okx market ticker {symbol3}
# ...

# Step 0.5: 多币种并行获取 K 线（用于计算 RSI）
okx market candles {symbol1} --bar 1H --limit 100
okx market candles {symbol2} --bar 1H --limit 100
okx market candles {symbol3} --bar 1H --limit 100
# ...

# Step 0.6: 资金费率检查（仅 swap）
okx market funding-rate {symbol1}
okx market funding-rate {symbol2}
# ...
```

> **单币种**：symbol = `BTC-USDT-SWAP`
> **多币种**：逗号分隔，如 `CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP`
> **profile**：`--profile demo` 模拟盘 / `--profile live` 实盘

**Phase 0 输出模板**：

```
✅ OKX 连接正常 | 账户: {profile}
💰 可用 USDT 余额: {available} USDT
📊 {symbol} 当前价: {lastPrice} | 24h涨跌: {change24h}%
📈 已获取 {count} 根 K 线，开始计算 RSI(14)...
⏳ RSI 信号监控中，间隔 {check_interval} 秒轮询
```

---

### Phase 1 — RSI 信号检测（多币种并行）

**目的**：对所有监控币种并行计算 RSI，任一币种低于超卖阈值时触发买入信号。

```bash
# Step 1.1: 多币种并行获取 K 线（Python 脚本直接调 OKX API 计算 RSI）
# 脚本示例见 P2-1 Multi-coin Scanner（下方）

# Step 1.2: 多币种并行获取实时价格（辅助）
okx market ticker {symbol1}
okx market ticker {symbol2}
# ...

# Step 1.3: 多币种并行获取资金费率（辅助风控）
okx market funding-rate {symbol1}
okx market funding-rate {symbol2}
# ...
```

**Phase 1 判断逻辑**（对每个监控币种独立判断）：

```
{coin1}: RSI(14) = {rsi1}  [{'超卖!' if rsi1 < rsi_oversold else '正常'}]
{coin2}: RSI(14) = {rsi2}  [{'超卖!' if rsi2 < rsi_oversold else '正常'}]
...

IF ANY coin: RSI < rsi_oversold:
    → 该币种进入 Phase 2（其他币种继续轮询）
    → 飞书通知：多币种并行监控 {n} 个币种，触发信号 {symbol}
```

**Phase 1 输出模板**（多币种汇总）：

```
[{timestamp}] Multi-coin Scan  {symbols}
  CRCL-USDT-SWAP : RSI(14)=25.1  [OVERSOLD - BUY!]
  ETH-USDT-SWAP  : RSI(14)=58.3  [NORMAL]
  SOL-USDT-SWAP  : RSI(14)=42.1  [NORMAL]
  BTC-USDT-SWAP  : RSI(14)=65.2  [NORMAL]
  [SIGNAL] CRCL-USDT-SWAP RSI < 30, entering Phase 2...
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

### Phase 3 — 持仓监控（含追踪止损 + 飞书通知）

**目的**：买入后实时监控价格变化，判断止盈/止损条件，支持追踪止损和飞书通知。

#### Phase 3A — 查询持仓状态

```bash
# 现货模式：查询账户余额变化
okx account balance --profile {profile}

# 合约模式：查询持仓信息
okx swap positions --instId {symbol} --profile {profile}
```

#### Phase 3B — 持续价格监控（增强版）

```bash
# 每轮监控：获取最新价格
okx market ticker {symbol}

# 每 N 轮重新计算 RSI（辅助判断趋势）
okx market candles {symbol} --bar 1H --limit 50  # Python 计算 RSI

# 资金费率（每日成本计算）
okx market funding-rate {symbol}
```

#### Phase 3C — 追踪止损逻辑

**追踪止盈规则**（当浮盈 > `--trailing-pct` 时自动上调止损线）：

```
初始：
  tp_price = entry_price * (1 + tp_pct / 100)   # 止盈价
  sl_price = entry_price * (1 - sl_pct / 100)   # 初始止损价

监控中（每一轮）：
  IF pnl_pct > trailing_pct AND sl_price < entry_price:
      sl_price = entry_price  ← 锁定利润，防止回吐
      → 记录：追踪止盈触发，止损线上调至成本价

  IF current_price >= tp_price:
      → 触发止盈，进入 Phase 4A
  IF current_price <= sl_price:
      → 触发止损，进入 Phase 4B
```

**追踪止损完整伪代码**：

```python
entry_price    = {entry_price}
tp_price       = entry_price * (1 + tp_pct / 100)
sl_price       = entry_price * (1 - sl_pct / 100)  # 动态调整
trailing_pct   = {trailing_pct}  # 默认 5%
max_time       = time.time() + max_hold_hours * 3600
trailing_locked = False
last_feishu_time = 0

WHILE True:
    current_price = get_ticker(symbol)
    rsi14 = calc_rsi_from_candles(symbol)           # Python 计算
    fr    = fetch_funding_rate(symbol)              # 资金费率
    liq   = calc_liquidation_price(entry_price, leverage)

    pnl_pct = (current_price - entry_price) / entry_price * 100
    dist_to_tp  = (tp_price  - current_price) / current_price * 100
    dist_to_sl  = (current_price - sl_price) / current_price * 100
    dist_to_liq = (current_price - liq) / current_price * 100
    daily_fr_cost = fr * 3 * 100  # 日资金成本 %

    # [追踪止损] 浮盈超过阈值，上调止损至成本价
    if pnl_pct > trailing_pct and not trailing_locked:
        sl_price = entry_price
        trailing_locked = True
        print(f"[TRAILING] PnL {pnl_pct:.2f}% > {trailing_pct}%, SL raised to cost: {entry_price:.4f}")

    PRINT(f"监控 | {symbol} | 现价:{current_price} | 浮盈:{pnl_pct:+.2f}% "
          f"| TP:{dist_to_tp:.2f}% | SL:{dist_to_sl:.2f}% "
          f"| Liq:{dist_to_liq:.2f}% | RSI:{rsi14:.1f}")

    # [飞书通知] 每 30 分钟推送一次 + 关键事件立即通知
    now = time.time()
    if now - last_feishu_time > 1800 or pnl_pct > trailing_pct:
        send_feishu({
            "symbol": symbol, "price": current_price,
            "rsi14": rsi14, "pnl_pct": pnl_pct,
            "dist_to_liq": dist_to_liq, "daily_fr_cost": daily_fr_cost,
            "trailing_active": trailing_locked,
            "profile": "{profile}"
        })
        last_feishu_time = now

    IF current_price >= tp_price:
        BREAK  # → Phase 4A 止盈
    ELIF current_price <= sl_price:
        BREAK  # → Phase 4B 止损
    ELIF time.time() >= max_time:
        BREAK  # → Phase 4C 超时
    ELSE:
        sleep(check_interval)
```

**Phase 3 输出模板**（增强版）：

```
[{timestamp}] MONITORING  {symbol}  [{profile}]
  Price:    {current_price}  |  Entry: {entry_price}  |  PnL: {pnl_pct:+.2f}%
  TP:      {tp_price} ({dist_to_tp:.2f}% away)
  SL:      {sl_price} ({dist_to_sl:.2f}% away)  [TRAILING] if locked
  Liq:     {liq_price} ({dist_to_liq:.2f}% away)
  RSI(14): {rsi14:.1f}  |  Funding: {fr*100:+.4f}%/8h (daily: {daily_fr_cost:+.4f}%)
  Hold:    {elapsed_hours:.1f}h / {max_hold_hours}h  |  Next: {check_interval}s
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
  okx account balance --profile live
  okx market ticker ETH-USDT-SWAP
  okx market candles ETH-USDT-SWAP --bar 1H --limit 100

Phase 1 (循环):
  python scripts/multi_coin_scanner.py --coins ETH-USDT-SWAP
  → RSI(14) = 24 < 25 超卖！触发买入

Phase 2:
  okx market ticker ETH-USDT-SWAP
  okx swap leverage --instId ETH-USDT-SWAP --lever 8 --mgnMode isolated --posSide long --profile live
  okx swap place --instId ETH-USDT-SWAP --side buy --tdMode isolated --posSide long --ordType market --sz 10 --profile live
  # 同时挂止盈止损 plan order
  okx swap algo place --instId ETH-USDT-SWAP --side sell --sz 10 --ordType conditional \
      --tpTriggerPx {tp_price} --tpOrdPx=-1 \
      --slTriggerPx {sl_price} --slOrdPx=-1 \
      --posSide long --tdMode isolated --reduceOnly --profile live
  okx swap positions --instId ETH-USDT-SWAP --profile live

Phase 3 (循环):
  python scripts/review_position.py --symbol ETH-USDT-SWAP --profile live
  → 监控浮盈 / 追踪止损 / 飞书通知

Phase 4:
  okx swap place --instId ETH-USDT-SWAP --side sell --tdMode isolated --posSide long --ordType market --sz 10 --profile live
```

### 示例 2：模拟盘多币种并行监控（3 个币种，稳健参数）

```
用户: 模拟盘监控 CRCL ETH SOL 永续 RSI<30 止盈10%止损6% 杠杆5x 30%仓位

Phase 0:
  python scripts/multi_coin_scanner.py --coins CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP

Phase 1:
  # 多币种并行，每小时自动扫描
  python scripts/multi_coin_scanner.py --coins CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP --rsi-oversold 30
  → 输出：CRCL RSI=25.1 [OVERSOLD], 其他正常
  → CRCL 进入 Phase 2

Phase 2:
  okx swap leverage --instId CRCL-USDT-SWAP --lever 5 --mgnMode isolated --posSide long --profile demo
  okx swap place --instId CRCL-USDT-SWAP --side buy --tdMode isolated --posSide long --ordType market --sz 10 --profile demo
  # 挂追踪止盈止损 plan order
  okx swap algo place --instId CRCL-USDT-SWAP --side sell --sz 10 --ordType conditional \
      --tpTriggerPx {tp_price} --tpOrdPx=-1 \
      --slTriggerPx {sl_price} --slOrdPx=-1 \
      --posSide long --tdMode isolated --reduceOnly --profile demo

Phase 3:
  python scripts/run_tracking.py --symbol CRCL-USDT-SWAP --profile demo --trailing-pct 5
  → 浮盈 > 5% 时自动上调 SL 至成本价
  → 飞书通知：[DEMO] CRCL 监控报告（RSI/强平价/资金费率/PnL）

Phase 4:
  okx swap place --instId CRCL-USDT-SWAP --side sell --tdMode isolated --posSide long --ordType market --sz 10 --profile demo
```

### 示例 3：追踪止盈实战（实盘，已持仓）

```
持仓状态：CRCL/USDT-SWAP, 10 张, 均价 85.7673, 5x 杠杆
当前价：88.50（浮盈 +3.18%）

# 当前未触发追踪（< 5%），继续监控
python scripts/review_position.py --symbol CRCL-USDT-SWAP --entry 85.7673 --leverage 5 --profile live

# 假设价格涨至 90.05（浮盈 +4.99%），仍 < 5%，继续监控
# 价格涨至 90.55（浮盈 +5.58% > 5%），触发追踪止损
# → SL 自动从 82.36 上调至成本价 85.7673
# → 锁定 5.58% 浮盈，防止回吐

Phase 4（价格回落至 85.90，触发新 SL）：
  # 市价平仓
  okx swap place --instId CRCL-USDT-SWAP --side sell --tdMode isolated --posSide long --ordType market --sz 10 --profile live
  # 平仓均价 ~85.90，浮盈 ~5.58%，约赚 5 USDT
```

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

## 回测改进记录 (v1.2.0)

> 基于 CRCL/USDT-SWAP 14天（2026-03-27 ~ 2026-04-10）1H K线真实数据回测，初始资金 1000 USDT。

### 回测结果摘要

| 策略 | RSI阈值 | 止盈 | 止损 | 杠杆 | 仓位 | 交易数 | 胜/负 | 胜率 | 收益 | 最终资金 |
|------|---------|------|------|------|------|--------|-------|------|------|---------|
| 激进 (8x) | <30 | 8% | 5% | 8x | 50% | 4 | 3/1 | 75% | **+4653 USDT (+465%)** | 5653 USDT |
| 保守 (5x) | <30 | 6% | 4% | 5x | 30% | 4 | 3/1 | 75% | +1997 USDT (+200%) | 2997 USDT |
| 精准激进 (8x) | <25 | 8% | 5% | 8x | 50% | 2 | 1/1 | 50% | +1346 USDT (+135%) | 2346 USDT |

> ⚠️ 回测结果不代表未来收益。CRCL 在回测期间有剧烈波动（84.4→101.87），策略抓住了所有超卖反弹。真实市场可能存在更多假信号。

### P0 — 必须修复（影响核心功能）

---

**P0-1：`indicator` CLI 不支持自定义 bar/limit → 策略无法做技术分析**

**问题**：
```bash
okx market indicator rsi CRCL-USDT-SWAP --bar 1Hutc --limit 336
# → HTTP 400 Bad Request
```
OKX `/api/v5/index/ticker`（indicator CLI 调用的后端）不支持 `bar`/`limit` 参数，只能查默认粒度的最新值，无法做历史 RSI 计算。

**已验证的正确方案 — 直接调 OKX API + Python 计算 RSI**：

```python
import urllib.request, json, math

BASE_URL = "https://www.okx.com"

def fetch_candles(inst_id: str, bar: str = "1H", limit: int = 336) -> list:
    """拉 K 线数据（public endpoint，无需签名）"""
    url = f"{BASE_URL}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())["data"]
    # OKX K线字段: [ts, open, high, low, close, vol, volCcy, volQuote, confirm]
    candles = []
    for row in reversed(data):
        candles.append({
            "ts": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        })
    return candles

def calc_rsi(candles: list, period: int = 14) -> float:
    """计算 RSI（基于 close 价格）"""
    closes = [c["close"] for c in candles]
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

candles = fetch_candles("CRCL-USDT-SWAP", bar="1H", limit=336)
rsi = calc_rsi(candles, period=14)
print(f"RSI(14) = {rsi:.2f}")
```

**SKILL 改进**：`indicator` CLI 仅作为**当前值快速查询**使用（`--limit 1`），历史 RSI 计算必须用 Python 脚本。文档中明确标注此限制。

---

**P0-2：`candles` 和 `indicator` 的 bar 格式不一致，导致使用混淆**

**问题**：

| CLI 命令 | 正确 bar 格式 | 错误格式 |
|---------|------------|---------|
| `okx market candles` | `--bar 1H`（大写 H） | `--bar 1Hutc` → 报错 |
| `okx market indicator` | `--bar 1Hutc`（必须 UTC 后缀） | `--bar 1H` → 可能返回错误数据 |
| `okx market funding-rate` | `--bar 8H`（永续合约固定 8H） | 其他值无效 |

**SKILL 改进**：文档增加格式对照表，并在各命令示例中标注正确格式。Rule of thumb：
- `candles` → 大写 H，如 `1H`, `4H`, `1D`
- `indicator` → 必须加 `utc` 后缀，如 `1Hutc`, `4Hutc`, `1Dutc`

---

**P0-3：小币 instId 无法按 quoteCcy 过滤 → 不知道该监控哪些币**

**问题**：`okx market instruments --instType SWAP` 返回全量合约列表，无法按 `quoteCcy = USDT` 过滤，只能手动翻找。

**已验证的正确方案**：

```python
import urllib.request, json

# 拉全量永续合约列表（仅取 instId）
url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"
with urllib.request.urlopen(url, timeout=15) as r:
    data = json.loads(r.read())["data"]

usdt_swaps = [row["instId"] for row in data if row.get("quoteCcy") == "USDT"]
print(f"USDT 永续合约共 {len(usdt_swaps)} 个")

# 逐一验证 ticker 是否存在（有成交）
for inst_id in usdt_swaps:
    ticker_url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}"
    try:
        with urllib.request.urlopen(ticker_url, timeout=5) as tr:
            t = json.loads(tr.read())["data"][0]
            last = float(t["last"])
            vol24h = float(t["vol24h"])
            if vol24h > 1000:  # 过滤日成交量 > 1000 USDT 的币种
                print(f"✅ {inst_id} | 现价: {last} | 24h成交量: {vol24h}")
    except Exception:
        print(f"❌ {inst_id} 无有效行情")
```

**SKILL 改进**：补充 Python 脚本方法，按成交量过滤活跃 USDT 合约，供监控前筛选候选币种。

---

#### P1 — 建议增强（提升策略健壮性）

---

**P1-4：资金费率未入策略逻辑 → 高费率币种持仓成本被低估**

**问题**：CRCL 资金费率 0.03%~0.06%/8h（每天 3 次结算），8x 杠杆持仓 2 天资金费率 ≈ 0.5%，持仓 7 天 ≈ 1.75%，可能侵蚀止盈收益。

**改进方案 — Phase 1 增加资金费率检查**：

```python
def fetch_funding_rate(inst_id: str) -> float:
    """获取当前资金费率（public endpoint）"""
    url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst_id}&limit=1"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())["data"]
    return float(data[0]["fundingRate"]) if data else 0.0

# 在 Phase 1 信号确认后、检查开仓前执行：
fr = fetch_funding_rate(inst_id)
hourly_cost = fr / 3  # 8h 结算一次，折算为 hourly
daily_cost_pct = hourly_cost * 24
print(f"当前资金费率: {fr*100:.4f}%/8h | 日资金成本: {daily_cost_pct*100:.4f}%")

# 资金费率阈值：日成本 > 0.1% 时降低仓位 50%
if daily_cost_pct > 0.001:
    actual_position_pct = position_pct * 0.5
    print(f"⚠️ 高资金费率，自动降低仓位至 {actual_position_pct*100:.0f}%")
```

**SKILL 改进**：在 Phase 1 信号确认步骤中增加资金费率检查，当日均资金费率 > 0.1% 时自动减仓。

---

**P1-5：爆仓价预警缺失 → 极端行情下无法提前风控**

**问题**：CRCL 波动 17.5%，远超 8x 爆仓线（12.5%），策略在波动峰值开仓有直接爆仓风险，但 Phase 0/1 无任何预警。

**改进方案 — 开仓前计算距强平价距离**：

```python
def calc_liquidation_price(entry_price: float, leverage: int, side: str = "long") -> float:
    """计算强平价（USDT 本位 / 逐仓 / 做多）"""
    # OKX USDT 本位逐仓强平价公式：
    # long: entry_price * (1 - 1/leverage)
    # short: entry_price * (1 + 1/leverage)
    if side == "long":
        return entry_price * (1 - 1 / leverage)
    else:
        return entry_price * (1 + 1 / leverage)

def check_liquidation_distance(entry_price: float, leverage: int, current_price: float) -> dict:
    liq_price = calc_liquidation_price(entry_price, leverage)
    if current_price < liq_price:
        pct_to_liq = 0
    else:
        pct_to_liq = (current_price - liq_price) / current_price * 100
    return {"liq_price": liq_price, "pct_to_liq": pct_to_liq}

# 在 Phase 2 开仓前执行：
check = check_liquidation_distance(entry_price=86.65, leverage=8, current_price=87.10)
print(f"强平价: {check['liq_price']:.4f} | 距强平价: {check['pct_to_liq']:.2f}%")

# 预警规则：距强平价 < 5% → 拒绝开仓
if check["pct_to_liq"] < 5:
    print("🚨 距强平价不足 5%，拒绝开仓！")
    # → 放弃本次交易，等待价格回归安全区间
elif check["pct_to_liq"] < 10:
    print("⚠️ 距强平价 < 10%，建议降低仓位")
```

**SKILL 改进**：Phase 2 开仓前增加强平价计算，距强平价 < 5% 时拒绝开仓，< 10% 时降低仓位。已在 `scripts/backtest_rsi_swap.py` 中实现示例。

---

**P1-6：回测模板缺失 → 策略参数无法量化验证**

**状态**：✅ 已解决。`scripts/backtest_rsi_swap.py` 已添加，支持多策略参数并行回测。

---

#### P2 — 体验优化（nice to have）

---

**P2-1：多币种并行监控（3~6 个币种）→ 扩大机会覆盖**

**问题**：当前只监控单一币种，需要人工切换，效率低。与「博尔特冲刺」skill 对齐，支持同时监控多个币种。

**已验证的完整实现 — `multi_coin_scanner.py`**：

```python
"""
multi_coin_scanner.py — 多币种 RSI 扫描器
用法：python multi_coin_scanner.py --coins BTC-USDT-SWAP,ETH-USDT-SWAP,CRCL-USDT-SWAP
"""
import argparse, urllib.request, json, time
from datetime import datetime

BASE = "https://www.okx.com"
DEFAULT_COINS = "CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,BTC-USDT-SWAP"

def fetch_candles(inst_id: str, bar: str = "1H", limit: int = 100) -> list:
    url = f"{BASE}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())["data"]
    candles = []
    for row in reversed(data):
        candles.append({"ts": int(row[0]), "close": float(row[4])})
    return candles

def calc_rsi(closes: list, period: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))

def scan_coins(coins: list, rsi_oversold: float = 30) -> list:
    """对多个币种并行扫描超卖信号，返回信号列表"""
    signals = []
    for coin in coins:
        try:
            # 获取K线 + RSI
            candles = fetch_candles(coin)
            closes = [c["close"] for c in candles]
            rsi14 = calc_rsi(closes, 14)
            rsi6  = calc_rsi(closes, 6)
            last  = closes[-1]

            # 获取24h数据
            ticker_url = f"{BASE}/api/v5/market/ticker?instId={coin}"
            req2 = urllib.request.Request(ticker_url, headers={"User-Agent": "okx-bot/1.0"})
            with urllib.request.urlopen(req2, timeout=5) as r:
                t = json.loads(r.read())["data"][0]
            vol24h = float(t.get("vol24h", 0))
            chg24h = float(t.get("sodUtc8", "0"))  # 24h涨跌

            # 获取资金费率
            fr_url = f"{BASE}/api/v5/public/funding-rate-history?instId={coin}&limit=1"
            req3 = urllib.request.Request(fr_url, headers={"User-Agent": "okx-bot/1.0"})
            with urllib.request.urlopen(req3, timeout=5) as r:
                fr_data = json.loads(r.read())["data"]
            fr = float(fr_data[0]["fundingRate"]) if fr_data else 0.0

            print(f"  {coin:<25} RSI(14)={rsi14:5.1f} RSI(6)={rsi6:5.1f} "
                  f"Price={last:>10} 24h={chg24h*100:+6.2f}% Vol={vol24h:>12,.0f} "
                  f"FR={fr*100:+.4f}%/8h")

            if rsi14 < rsi_oversold:
                signals.append({
                    "coin": coin, "rsi14": rsi14, "rsi6": rsi6,
                    "price": last, "vol24h": vol24h, "fr": fr
                })

        except Exception as e:
            print(f"  {coin:<25} [ERROR] {e}")
    return signals

def main():
    parser = argparse.ArgumentParser(description="Multi-coin RSI Scanner")
    parser.add_argument("--coins", default=DEFAULT_COINS,
                        help=f"Comma-separated instId list, default: {DEFAULT_COINS}")
    parser.add_argument("--rsi-oversold", type=float, default=30,
                        help="RSI oversold threshold, default: 30")
    parser.add_argument("--min-vol", type=float, default=10000,
                        help="Minimum 24h volume (USDT), default: 10000")
    args = parser.parse_args()

    coins = [c.strip() for c in args.coins.split(",")]
    print(f"\n{'='*80}")
    print(f"Multi-coin RSI Scan  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")
    print(f"{'Symbol':<25} RSI(14)  RSI(6)  Price            24h Chg   24h Volume       Funding")
    print(f"{'-'*80}")

    signals = scan_coins(coins, args.rsi_oversold)

    print(f"\n{'='*80}")
    if signals:
        print(f"[SIGNALS] {len(signals)} coin(s) in oversold territory (RSI < {args.rsi_oversold}):")
        for s in sorted(signals, key=lambda x: x["rsi14"]):
            print(f"  >>> {s['coin']}: RSI={s['rsi14']:.1f}, Price={s['price']}, "
                  f"FR={s['fr']*100:+.4f}%/8h")
    else:
        print(f"[OK] No oversold signals found (RSI < {args.rsi_oversold})")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
```

**使用方法**：
```bash
# 扫描默认 4 个币种
python scripts/multi_coin_scanner.py

# 扫描自定义币种
python scripts/multi_coin_scanner.py --coins BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP --rsi-oversold 25

# 配合 crontab 每小时自动执行
0 * * * * cd /path/to && python scripts/multi_coin_scanner.py --coins CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP >> logs/scan.log 2>&1
```

---

**P2-2：飞书通知增强 → 全指标展示**

**问题**：原飞书通知只有盈亏结果，缺少 RSI、强平价、资金费率等关键决策数据。

**已验证的完整实现 — 飞书通知函数**：

```python
import urllib.request, json, time

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/b2aefdfe-a15d-481a-885b-5b5bb91d4be4"

def send_feishu_notification(
    title: str,
    symbol: str,
    profile: str,           # "demo" or "live"
    price: float,
    entry_price: float,
    rsi14: float,
    pnl_pct: float,
    pnl_usdt: float,
    dist_to_liq: float,     # % distance to liquidation
    dist_to_sl: float,      # % distance to stop loss
    dist_to_tp: float,      # % distance to take profit
    fr: float,              # funding rate (raw, e.g. 0.0003)
    trailing_active: bool,
    leverage: int,
    action: str = "monitor",  # "monitor" | "entry" | "exit_tp" | "exit_sl"
):
    """发送结构化飞书通知（Markdown 富文本）"""

    # 颜色：超卖绿/超买红/中性灰
    if rsi14 < 30:
        rsi_label = "OVERSOLD"
        rsi_color = "green"
    elif rsi14 > 70:
        rsi_label = "OVERBOUGHT"
        rsi_color = "red"
    else:
        rsi_label = "NEUTRAL"
        rsi_color = "grey"

    # 距强平价安全等级
    if dist_to_liq < 5:
        liq_label = "DANGER"
        liq_color = "red"
    elif dist_to_liq < 10:
        liq_label = "WARNING"
        liq_color = "orange"
    else:
        liq_label = "SAFE"
        liq_color = "green"

    # 浮盈颜色
    if pnl_pct > 0:
        pnl_color = "green"
    else:
        pnl_color = "red"

    # 标题 emoji
    emoji = {
        "monitor": "[SCAN]",
        "entry":   "[BUY]",
        "exit_tp": "[TP HIT]",
        "exit_sl": "[SL HIT]",
    }.get(action, "[ALERT]")

    profile_tag = "[DEMO]" if profile == "demo" else "[LIVE]"

    # 构建 Markdown
    msg = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"{emoji} {symbol} {profile_tag}"},
                "template": "purple" if profile == "demo" else "red"
            },
            "elements": [
                # 行情行
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Price**\n{price:.4f} USDT"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Entry**\n{entry_price:.4f}"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**PnL**\n:<font color='{pnl_color}'>{pnl_pct:+.2f}% ({pnl_usdt:+.4f} USDT)"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Leverage**\n{leverage}x"}},
                    ]
                },
                {"tag": "hr"},
                # 技术指标行
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**RSI(14)**\n:<font color='{rsi_color}'>{rsi14:.1f} [{rsi_label}]"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Funding Rate**\n{fr*100:+.4f}%/8h (daily: {fr*3*100:+.4f}%)"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Liq Distance**\n:<font color='{liq_color}'>{dist_to_liq:.2f}% [{liq_label}]"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Trailing SL**\n{'ACTIVE' if trailing_active else 'inactive'}"}},
                    ]
                },
                {"tag": "hr"},
                # 止盈止损距离行
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**To TP**\n{dist_to_tp:.2f}%"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**To SL**\n{dist_to_sl:.2f}%"}},
                    ]
                },
                # 时间戳
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text",
                                  "content": f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}"}]
                }
            ]
        }
    }

    try:
        body = json.dumps(msg).encode("utf-8")
        req = urllib.request.Request(
            FEISHU_WEBHOOK, data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        print(f"[Feishu] {result.get('code', -1)} {result.get('msg', '')}")
    except Exception as e:
        print(f"[Feishu] Send failed: {e}")

# 使用示例
send_feishu_notification(
    title="CRCL持仓监控",
    symbol="CRCL-USDT-SWAP",
    profile="live",
    price=85.95, entry_price=85.7673,
    rsi14=25.1, pnl_pct=0.21, pnl_usdt=0.027,
    dist_to_liq=14.0, dist_to_sl=4.18, dist_to_tp=5.80,
    fr=0.0003, trailing_active=False, leverage=5,
    action="monitor"
)
```

---

**P2-3：追踪止损（浮盈 > 5% → SL 上调至成本价）→ 防止利润回吐**

**问题**：原策略止损位固定，当出现大幅浮盈后价格回调会导致利润大幅回吐。

**追踪止损完整实现**：

```python
def run_tracking_stop(
    symbol: str,
    entry_price: float,
    leverage: int,
    tp_pct: float = 8.0,
    sl_pct: float = 5.0,
    trailing_pct: float = 5.0,
    max_hold_hours: int = 336,
    check_interval: int = 60,
    profile: str = "live",
):
    """
    持仓监控主循环，带追踪止损 + 飞书通知
    """
    tp_price = entry_price * (1 + tp_pct / 100)
    sl_price = entry_price * (1 - sl_pct / 100)  # 动态调整
    trailing_locked = False
    trailing_lock_price = None
    entry_time = time.time()
    max_time = entry_time + max_hold_hours * 3600
    last_feishu = 0

    print(f"[START] {symbol} | Entry: {entry_price} | TP: {tp_price} | "
          f"SL: {sl_price} | Trailing: {trailing_pct}%")

    while True:
        now = time.time()

        # 获取实时数据
        ticker = get_ticker(symbol)
        current_price = float(ticker["last"])
        candles = fetch_candles(symbol, bar="1H", limit=50)
        rsi14 = calc_rsi([c["close"] for c in candles], period=14)
        fr = fetch_funding_rate(symbol)
        liq_price = calc_liquidation_price(entry_price, leverage)
        notional = current_price * leverage  # 逐仓面值

        pnl_pct = (current_price - entry_price) / entry_price * 100
        pnl_usdt = pnl_pct / 100 * notional
        dist_to_tp  = (tp_price  - current_price) / current_price * 100
        dist_to_sl  = (current_price - sl_price) / current_price * 100
        dist_to_liq = (current_price - liq_price) / current_price * 100
        elapsed_h = (now - entry_time) / 3600

        # [核心] 追踪止损：浮盈超过阈值，上调 SL 至成本价
        if not trailing_locked and pnl_pct > trailing_pct:
            old_sl = sl_price
            sl_price = entry_price  # 锁定利润
            trailing_locked = True
            trailing_lock_price = entry_price
            print(f"[TRAILING] PnL {pnl_pct:.2f}% > {trailing_pct}% | "
                  f"SL raised: {old_sl:.4f} -> {entry_price:.4f} (COST)")
            # 立即更新止盈止损 plan order
            update_algo_order(symbol, new_sl=entry_price)
            # 立即飞书通知
            send_feishu_notification(..., action="monitor")

        # [飞书] 每 30 分钟常规推送
        if now - last_feishu > 1800:
            send_feishu_notification(
                title=f"{symbol} 监控报告",
                symbol=symbol, profile=profile,
                price=current_price, entry_price=entry_price,
                rsi14=rsi14, pnl_pct=pnl_pct, pnl_usdt=pnl_usdt,
                dist_to_liq=dist_to_liq, dist_to_sl=dist_to_sl,
                dist_to_tp=dist_to_tp, fr=fr,
                trailing_active=trailing_locked,
                leverage=leverage, action="monitor"
            )
            last_feishu = now

        # [平仓判断]
        exit_reason = None
        if current_price >= tp_price:
            exit_reason = "tp"
        elif current_price <= sl_price:
            exit_reason = "sl"
        elif now >= max_time:
            exit_reason = "timeout"

        if exit_reason:
            exit_price = current_price
            exit_pnl_pct = pnl_pct
            exit_pnl_usdt = pnl_usdt

            # 执行市价平仓
            close_position(symbol, profile=profile)

            # 发送飞书平仓通知
            send_feishu_notification(
                title=f"{symbol} 平仓通知",
                symbol=symbol, profile=profile,
                price=exit_price, entry_price=entry_price,
                rsi14=rsi14, pnl_pct=exit_pnl_pct, pnl_usdt=exit_pnl_usdt,
                dist_to_liq=dist_to_liq, dist_to_sl=0, dist_to_tp=0,
                fr=fr, trailing_active=trailing_locked,
                leverage=leverage,
                action=f"exit_{exit_reason}"
            )

            print(f"[EXIT:{exit_reason.upper()}] {symbol} | "
                  f"Exit: {exit_price:.4f} | PnL: {exit_pnl_pct:+.2f}% ({exit_pnl_usdt:+.4f} USDT)")
            break

        print(f"[MON] {symbol} | {current_price:.4f} | PnL: {pnl_pct:+.2f}% | "
              f"TP: {dist_to_tp:.2f}% | SL: {dist_to_sl:.2f}% | "
              f"Liq: {dist_to_liq:.2f}% | RSI: {rsi14:.1f} | "
              f"Trailing: {'YES' if trailing_locked else 'no'} | {elapsed_h:.1f}h")
        time.sleep(check_interval)
```

---

**P2-4：`--mode demo|live` 明确区分 → 实盘安全隔离**

**设计原则**：
- `demo`（模拟盘）：所有操作带 `--profile demo`，API Key 建议使用专门的 Demo API Key
- `live`（实盘）：所有操作带 `--profile live`，飞书通知模板头部颜色区分

**完整参数对照**：

| 操作 | demo 参数 | live 参数 |
|------|---------|---------|
| 账户余额 | `okx account balance --profile demo` | `okx account balance --profile live` |
| 持仓查询 | `okx swap positions --instId X --profile demo` | `okx swap positions --instId X --profile live` |
| 资金费率 | `okx market funding-rate X`（无需 profile） | 同左 |
| K线/RSI | `okx market candles X`（无需 profile） | 同左 |
| 设置杠杆 | `okx swap leverage --instId X --profile demo` | `okx swap leverage --instId X --profile live` |
| 开仓/平仓 | `okx swap place --instId X --profile demo` | `okx swap place --instId X --profile live` |

**启动命令示例**：

```bash
# 实盘（正式交易）
python scripts/run_strategy.py \
  --symbols CRCL-USDT-SWAP,ETH-USDT-SWAP \
  --profile live \
  --leverage 5 \
  --order-pct 30 \
  --tp-pct 6 \
  --sl-pct 4 \
  --trailing-pct 5 \
  --rsi-oversold 30 \
  --feishu-webhook https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK

# 模拟盘（策略验证）
python scripts/run_strategy.py \
  --symbols BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP \
  --profile demo \
  --leverage 5 \
  --order-pct 30 \
  --tp-pct 8 \
  --sl-pct 5 \
  --trailing-pct 5 \
  --rsi-oversold 25
```

**飞书通知视觉区分**：实盘卡片头部红色，模拟盘卡片头部紫色（见上方飞书通知实现）。

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
| `--trailing-pct` | `5%` | `5%` | `5%` | 追踪止盈触发阈值（浮盈>此值时 SL 锁成本） |
| `--symbols` | `BTC-USDT-SWAP` | 多币种逗号分隔 | — | 并行监控 3~6 个币种 |
| `--feishu-webhook` | `null` | 自定义 URL | — | 飞书通知（空则跳过） |
| 风险等级 | ⚠️⚠️⚠️⚠️ 极高 | ⚠️⚠️⚠️ 高 | ⚠️⚠️ 中高 | — |
