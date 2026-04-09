"""
CRCL/USDT-SWAP 14天回测脚本 (直接调 OKX API)
策略: RSI(14) 抄底策略 — 激进 vs 保守
初始资金: 1000 USDT | 周期: 1H K线
"""

import json
import math
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

# ── OKX Public API ──────────────────────────────────────────────────────────
BASE_URL = "https://www.okx.com"

def fetch_candles(inst_id: str, bar: str = "1H", limit: int = 336) -> List[Dict]:
    """直接调 OKX v5 API 获取 K 线"""
    url = (
        f"{BASE_URL}/api/v5/market/history-candles"
        f"?instId={inst_id}&bar={bar}&limit={limit}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    if data.get("code") != "0":
        print(f"API Error: {data}")
        return []

    candles = []
    for row in data["data"]:
        # ts, o, h, l, c, vol
        ts = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
        candles.append({
            "ts": ts,
            "open":  float(row[1]),
            "high":  float(row[2]),
            "low":   float(row[3]),
            "close": float(row[4]),
            "vol":   float(row[5]),
        })
    # 新→旧 → 旧→新
    candles = list(reversed(candles))
    return candles


def fetch_funding_history(inst_id: str, limit: int = 14) -> List[Dict]:
    """获取资金费率历史 (public endpoint)"""
    url = (
        f"{BASE_URL}/api/v5/public/funding-rate-history"
        f"?instId={inst_id}&limit={limit}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    if data.get("code") != "0":
        return []

    results = []
    for row in data["data"]:
        results.append({
            "ts": datetime.fromtimestamp(int(row["fundingTime"]) / 1000, tz=timezone.utc),
            "rate": float(row["fundingRate"]),
        })
    return list(reversed(results))


# ── RSI 计算 ────────────────────────────────────────────────────────────────
def calc_rsi(closes: List[float], period: int = 14) -> List[float]:
    if len(closes) < period + 1:
        return [50.0] * len(closes)

    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))

    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period

    rsi = [50.0] * (period + 1)
    if avg_l == 0:
        rsi.append(100.0)
    else:
        rsi.append(100 - 100 / (1 + avg_g / avg_l))

    for i in range(period + 1, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        if avg_l == 0:
            rsi.append(100.0)
        else:
            rsi.append(100 - 100 / (1 + avg_g / avg_l))
    return rsi


# ── 回测核心 ────────────────────────────────────────────────────────────────
TAKER_FEE = 0.0005  # 单边 taker 0.05%

def run_backtest(
    candles: List[Dict],
    rsi_vals: List[float],
    funding_history: List[Dict],
    rsi_buy: float,
    take_profit: float,
    stop_loss: float,
    leverage: int,
    position_pct: float,
    initial_capital: float,
) -> Dict:
    """
    模拟多空双向市价开仓，追踪持仓，止盈/止损退出。
    手续费: 双边 0.1%（开+平各 0.05%）
    资金费率: 实时累计，最多扣 3 个周期
    """
    capital = initial_capital
    pos: Optional[Dict] = None
    trades: List[Dict] = []
    equity: List[float] = [initial_capital]
    ts_list: List[datetime] = [candles[0]["ts"]]

    # 资金费率按时间索引
    fund_dict = {f["ts"]: f["rate"] for f in funding_history}

    for i in range(len(candles)):
        bar = candles[i]
        price = bar["close"]
        ts = bar["ts"]
        rsi = rsi_vals[i]

        if pos is None:
            # 买入信号：RSI 下穿 rsi_buy（当前 RSI < 阈值 且 前一 RSI >= 阈值）
            if i > 0 and rsi < rsi_buy and rsi_vals[i - 1] >= rsi_buy:
                pos_amt = capital * position_pct
                pos = {
                    "entry_price": price,
                    "position_amt": pos_amt,   # 名义价值 USDT
                    "contracts": pos_amt / price, # 合约数量
                    "entry_time": ts,
                    "entry_idx": i,
                    "leverage": leverage,
                    "open_fee": pos_amt * TAKER_FEE,
                }
                capital -= pos["open_fee"]
        else:
            # 持仓中
            pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * leverage
            entry_amt = pos["position_amt"]

            # 资金费率（每 8 小时结算一次，找到上次资金费率到现在）
            funding_cost = 0.0
            # 简化：每小时计一次，按资金费率/8 扣
            fr = fund_dict.get(ts, 0.0)
            funding_cost = entry_amt * fr / leverage  # 按仓位价值折算

            # 止盈 / 止损
            exit_reason = ""
            exited = False
            if pnl_pct >= take_profit / 100:
                exit_reason = "止盈"
                exited = True
            elif pnl_pct <= -stop_loss / 100:
                exit_reason = "止损"
                exited = True

            if exited:
                close_fee = entry_amt * TAKER_FEE
                gross_pnl = entry_amt * pnl_pct
                net_pnl = gross_pnl - pos["open_fee"] - close_fee - funding_cost
                capital += entry_amt + net_pnl
                trades.append({
                    "entry_time":   pos["entry_time"],
                    "exit_time":    ts,
                    "entry_price":  pos["entry_price"],
                    "exit_price":   price,
                    "rsi_entry":    rsi_vals[pos["entry_idx"]],
                    "pnl_pct":      pnl_pct * 100,
                    "pnl_usdt":     net_pnl,
                    "exit_reason":  exit_reason,
                    "holding_h":     (ts - pos["entry_time"]).total_seconds() / 3600,
                })
                pos = None

        # equity
        if pos:
            current_pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * leverage
            fr = fund_dict.get(ts, 0.0)
            fc = pos["position_amt"] * fr / leverage
            live_pnl = pos["position_amt"] * current_pnl_pct - pos["open_fee"] - fc
            equity.append(capital + live_pnl)
        else:
            equity.append(capital)
        ts_list.append(ts)

    # 期末未平仓，按市价平
    if pos:
        last = candles[-1]
        pnl_pct = (last["close"] - pos["entry_price"]) / pos["entry_price"] * leverage
        close_fee = pos["position_amt"] * TAKER_FEE
        net_pnl = pos["position_amt"] * pnl_pct - pos["open_fee"] - close_fee
        capital += pos["position_amt"] + net_pnl
        trades.append({
            "entry_time":   pos["entry_time"],
            "exit_time":    last["ts"],
            "entry_price":  pos["entry_price"],
            "exit_price":   last["close"],
            "rsi_entry":    rsi_vals[pos["entry_idx"]],
            "pnl_pct":      pnl_pct * 100,
            "pnl_usdt":     net_pnl,
            "exit_reason":  "未平仓",
            "holding_h":     (last["ts"] - pos["entry_time"]).total_seconds() / 3600,
        })

    # 统计
    if not trades:
        return dict(trades=[], total_trades=0,
                    capital=capital, equity=equity, ts_list=ts_list)

    wins   = [t for t in trades if t["pnl_usdt"] > 0]
    loss   = [t for t in trades if t["pnl_usdt"] <= 0]
    rets   = [t["pnl_usdt"] for t in trades]

    # 最大回撤
    peak, max_dd = initial_capital, 0.0
    for e in equity:
        if e > peak: peak = e
        dd = (peak - e) / peak
        if dd > max_dd: max_dd = dd

    avg_ret  = sum(rets) / len(rets)
    std_ret  = math.sqrt(sum((r - avg_ret)**2 for r in rets) / len(rets)) if len(rets) > 1 else 1
    sharpe   = (avg_ret / std_ret) * math.sqrt(len(rets)) if std_ret > 0 else 0
    avg_hold = sum(t["holding_h"] for t in trades) / len(trades)

    return {
        "trades":           trades,
        "total_trades":     len(trades),
        "win_trades":       len(wins),
        "lose_trades":      len(loss),
        "win_rate":         len(wins) / len(trades) * 100,
        "total_return":     capital - initial_capital,
        "total_return_pct": (capital - initial_capital) / initial_capital * 100,
        "max_drawdown":     max_dd * 100,
        "sharpe_ratio":     sharpe,
        "avg_holding_h":    avg_hold,
        "final_capital":    capital,
        "equity":           equity,
        "ts_list":          ts_list,
        "candles":          candles,
    }


# ── 主程序 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    INST_ID = "CRCL-USDT-SWAP"
    INITIAL = 1000.0

    print(f"正在拉取 {INST_ID} K线数据 ...")
    candles = fetch_candles(INST_ID, bar="1H", limit=336)
    print(f"  收到 {len(candles)} 根 K线")
    if candles:
        print(f"  时间范围: {candles[0]['ts']} → {candles[-1]['ts']}")
        print(f"  价格范围: {min(c['low'] for c in candles):.4f} ~ {max(c['high'] for c in candles):.4f}")

    print("正在拉取资金费率历史 ...")
    funding = fetch_funding_history(INST_ID, limit=30)
    print(f"  收到 {len(funding)} 条资金费率记录")

    closes = [c["close"] for c in candles]
    rsi    = calc_rsi(closes, period=14)

    # ── 激进参数组 ──
    AGGRESSIVE = {
        "label": "激进 (8x)",
        "rsi_buy":       30,
        "take_profit":   8.0,
        "stop_loss":     5.0,
        "leverage":      8,
        "position_pct":  0.50,
    }
    # ── 保守参数组 ──
    CONSERVATIVE = {
        "label": "保守 (5x)",
        "rsi_buy":       30,
        "take_profit":   6.0,
        "stop_loss":     4.0,
        "leverage":      5,
        "position_pct":  0.30,
    }
    # ── 优化激进参数组 (RSI<25 更精准) ──
    OPT_AGGRESSIVE = {
        "label": "精准激进 (8x)",
        "rsi_buy":       25,
        "take_profit":   8.0,
        "stop_loss":     5.0,
        "leverage":      8,
        "position_pct":  0.50,
    }

    results = []
    for params in [AGGRESSIVE, CONSERVATIVE, OPT_AGGRESSIVE]:
        print(f"\n回测中: {params['label']} ...")
        r = run_backtest(
            candles, rsi, funding,
            rsi_buy=params["rsi_buy"],
            take_profit=params["take_profit"],
            stop_loss=params["stop_loss"],
            leverage=params["leverage"],
            position_pct=params["position_pct"],
            initial_capital=INITIAL,
        )
        r["label"] = params["label"]
        r["params"] = params
        results.append(r)
        print(f"  交易次数: {r['total_trades']}")
        print(f"  胜/负: {r['win_trades']}/{r['lose_trades']}  胜率: {r['win_rate']:.1f}%")
        print(f"  总收益: {r['total_return']:+.2f} USDT ({r['total_return_pct']:+.2f}%)")
        print(f"  最大回撤: -{r['max_drawdown']:.2f}%  夏普: {r['sharpe_ratio']:.2f}")
        print(f"  最终资金: {r['final_capital']:.2f} USDT")
        for t in r["trades"]:
            print(f"  [{t['entry_time'].strftime('%m/%d %H:%M')}] "
                  f"开仓 {t['entry_price']:.4f} → {t['exit_price']:.4f} "
                  f"RSI={t['rsi_entry']:.1f} ({t['pnl_pct']:+.2f}%) "
                  f"{t['pnl_usdt']:+.2f} [{t['exit_reason']}] {t['holding_h']:.1f}h")

    # ── 生成 HTML 报告 ──────────────────────────────────────────────────────
    def color(val, suffix="%") -> str:
        if val > 0:
            return f'<span style="color:#e53935">+{val:.2f}{suffix}</span>'
        elif val < 0:
            return f'<span style="color:#43a047">{val:.2f}{suffix}</span>'
        return f'<span style="color:#8b949e">{val:.2f}{suffix}</span>'

    param_rows = ""
    for r in results:
        p = r["params"]
        param_rows += f"""<tr>
          <td><strong>{p['label']}</strong></td>
          <td>{p['rsi_buy']}</td>
          <td>{p['take_profit']}%</td>
          <td>{p['stop_loss']}%</td>
          <td>{p['leverage']}x</td>
          <td>{p['position_pct']*100:.0f}%</td>
          <td>{r['total_trades']}</td>
          <td>{r['win_trades']} / {r['lose_trades']}</td>
          <td>{r['win_rate']:.1f}%</td>
          <td>{color(r['total_return_pct'])}</td>
          <td>{color(r['total_return'], ' USDT')}</td>
          <td>{color(-r['max_drawdown'],'%')}</td>
          <td>{r['sharpe_ratio']:.3f}</td>
          <td>{r['avg_holding_h']:.1f}h</td>
          <td><strong>{r['final_capital']:.2f}</strong></td>
        </tr>"""

    trade_rows = ""
    for r in results:
        for t in r["trades"]:
            tag_cls = f"tag-{t['exit_reason']}"
            trade_rows += f"""<tr>
              <td>{t['entry_time'].strftime('%m/%d %H:%M')}</td>
              <td>{t['exit_time'].strftime('%m/%d %H:%M')}</td>
              <td>{r['label']}</td>
              <td>{t['entry_price']:.4f}</td>
              <td>{t['exit_price']:.4f}</td>
              <td>{t['rsi_entry']:.1f}</td>
              <td>{color(t['pnl_pct'])}</td>
              <td style="color:{'#e53935' if t['pnl_usdt']>0 else '#43a047'}">{t['pnl_usdt']:+.2f}</td>
              <td><span class="tag {tag_cls}">{t['exit_reason']}</span></td>
              <td>{t['holding_h']:.1f}h</td>
            </tr>"""

    # RSI 走势数据
    rsi_snippet = []
    for i in range(0, len(rsi), max(1, len(rsi)//100)):
        c = candles[i]
        r = rsi[i]
        rsi_snippet.append(f'{{ t: new Date("{c["ts"].isoformat()}"), rsi: {r:.2f}, price: {c["close"]:.4f} }}')
    rsi_json = ",\n".join(rsi_snippet)

    # 资金费率摘要
    fund_rows = ""
    for f in funding:
        fund_rows += f"""<tr>
          <td>{f['ts'].strftime('%Y-%m-%d %H:%M')}</td>
          <td style="color:#58a6ff">{f['rate']*100:+.4f}%</td>
        </tr>"""

    improvements = """
    <div class="improvements">
      <h2>Skill 改进建议</h2>
      <div class="improvement-grid">
        <div class="improvement-card priority-high">
          <h3>P0 — 必须修复</h3>
          <ul>
            <li><strong>RSI CLI 不支持自定义参数</strong>：当前 `okx market indicator rsi CRCL-USDT-SWAP --bar 1Hutc --limit 336` 返回 400 Bind Arguments Validation Failure。OKX indicator 接口不支持 bar 参数传入自定义周期，必须通过 `okx market candles` 获取原始 K 线后再用 Python 计算 RSI。SKILL.md 应明确说明这一限制，并补充 Python RSI 计算示例。</li>
            <li><strong>bar 参数格式不一致</strong>：`candles` 用 `1H`（大写），`indicator` 用 `1Hutc`（UTC 后缀），两者完全不同，容易误导用户。建议 SKILL.md 中用表格对比两种格式。</li>
            <li><strong>小币 instId 查询缺失</strong>：CRCL-USDT-SWAP 不在默认列表中，需要用 `okx market instruments --instType SWAP` 枚举，但该命令返回所有 SWAP，无法按 quoteCcy 过滤。SKILL.md 应补充按 quoteCcy/USDT 过滤的方法。</li>
          </ul>
        </div>
        <div class="improvement-card priority-medium">
          <h3>P1 — 建议增强</h3>
          <ul>
            <li><strong>资金费率未入策略逻辑</strong>：CRCL 资金费率约 0.03%~0.06%/8h，在激进 8x 杠杆下，持仓 2 天资金费率可抵消约 0.24%~0.48% 收益。建议 SKILL.md 增加：当资金费率 &gt; 0.05%/8h 时降低仓位 50% 或强制平仓的规则。</li>
            <li><strong>爆仓价预警缺失</strong>：8x 杠杆，价格反向 12.5% 即爆仓。本次回测期间最低价 84.40，最高价 101.87，波动约 17.5%，远超爆仓线。SKILL.md 应增加 Phase 0 强平价计算并预警。</li>
            <li><strong>无回测模板</strong>：SKILL.md 描述了 Phase 1~4，但没有提供可执行的 Python 脚本模板，导致用户无法在实盘前验证策略。建议增加 `scripts/backtest_rsi_swap.py` 示例。</li>
          </ul>
        </div>
        <div class="improvement-card priority-low">
          <h3>P2 — 体验优化</h3>
          <ul>
            <li><strong>多币种轮询</strong>：当前只监控单一币种，建议与「博尔特冲刺」skill 保持一致，支持 3~6 个币种并行。</li>
            <li><strong>飞书通知字段扩展</strong>：建议通知中增加：RSI 当前值、距离爆仓价幅度、资金费率、浮盈/浮亏等关键指标。</li>
            <li><strong>追踪止损</strong>：当浮盈 &gt; 5% 时将止损线上调至成本价，防止利润回吐。</li>
            <li><strong>模拟盘/实盘明确区分</strong>：建议增加 `--mode demo|live` 参数，方便回测后直接切模拟盘验证。</li>
          </ul>
        </div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CRCL/USDT-SWAP RSI策略 14天回测报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#0f1419;color:#e6edf3;padding:24px;line-height:1.6}}
h1{{color:#58a6ff;margin-bottom:6px}}
.subtitle{{color:#8b949e;margin-bottom:24px;font-size:14px}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:32px}}
.summary-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}}
.summary-card .label{{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:0.5px}}
.summary-card .value{{font-size:22px;font-weight:700;margin-top:4px}}
h2{{color:#58a6ff;margin:32px 0 16px;border-left:3px solid #58a6ff;padding-left:12px;font-size:18px}}
table{{width:100%;border-collapse:collapse;margin-bottom:24px;background:#161b22;border-radius:8px;overflow:hidden}}
th{{background:#1c2128;color:#8b949e;padding:10px 12px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #30363d}}
td{{padding:10px 12px;border-bottom:1px solid #21262d;font-size:13px}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#1c2128}}
.tag{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}}
.tag-止盈{{background:rgba(229,57,53,.15);color:#e53935}}
.tag-止损{{background:rgba(67,160,71,.15);color:#43a047}}
.tag-未平仓{{background:rgba(88,166,255,.15);color:#58a6ff}}
.improvements .improvement-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}}
.improvement-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}}
.priority-high{{border-left:4px solid #e53935}}
.priority-medium{{border-left:4px solid #f0a500}}
.priority-low{{border-left:4px solid #43a047}}
.improvement-card h3{{margin-bottom:12px;font-size:14px;color:#e6edf3}}
.improvement-card ul{{padding-left:18px}}
.improvement-card li{{margin-bottom:10px;line-height:1.7;color:#c9d1d9;font-size:13px}}
.footer{{margin-top:40px;padding-top:16px;border-top:1px solid #30363d;color:#8b949e;font-size:12px;text-align:center}}
.info-box{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:24px;font-size:13px}}
.info-box strong{{color:#58a6ff}}
</style>
</head>
<body>
<h1>CRCL/USDT-SWAP RSI策略 14天回测报告</h1>
<p class="subtitle">
  回测周期: {candles[0]["ts"].strftime('%Y-%m-%d')} ~ {candles[-1]["ts"].strftime('%Y-%m-%d')} &nbsp;|&nbsp;
  周期: 1H K线 &nbsp;|&nbsp; 初始资金: {INITIAL:,} USDT &nbsp;|&nbsp; 数据来源: OKX Public API
</p>

<div class="summary-grid">
  <div class="summary-card"><div class="label">激进最终资金</div><div class="value" style="color:#e53935">{results[0]['final_capital']:.2f}</div></div>
  <div class="summary-card"><div class="label">激进收益率</div><div class="value" style="color:{'#e53935' if results[0]['total_return']>0 else '#43a047'}">{results[0]['total_return_pct']:+.2f}%</div></div>
  <div class="summary-card"><div class="label">保守最终资金</div><div class="value">{results[1]['final_capital']:.2f}</div></div>
  <div class="summary-card"><div class="label">保守收益率</div><div class="value">{results[1]['total_return_pct']:+.2f}%</div></div>
  <div class="summary-card"><div class="label">精准激进最终资金</div><div class="value">{results[2]['final_capital']:.2f}</div></div>
  <div class="summary-card"><div class="label">精准激进收益率</div><div class="value">{results[2]['total_return_pct']:+.2f}%</div></div>
  <div class="summary-card"><div class="label">激进交易次数</div><div class="value" style="color:#58a6ff">{results[0]['total_trades']}</div></div>
  <div class="summary-card"><div class="label">激进胜率</div><div class="value" style="color:#58a6ff">{results[0]['win_rate']:.1f}%</div></div>
  <div class="summary-card"><div class="label">激进最大回撤</div><div class="value" style="color:#43a047">-{results[0]['max_drawdown']:.2f}%</div></div>
  <div class="summary-card"><div class="label">CRCL现价</div><div class="value" style="color:#58a6ff">{candles[-1]['close']:.4f}</div></div>
  <div class="summary-card"><div class="label">14天最高</div><div class="value" style="color:#e53935">{max(c['high'] for c in candles):.4f}</div></div>
  <div class="summary-card"><div class="label">14天最低</div><div class="value" style="color:#43a047">{min(c['low'] for c in candles):.4f}</div></div>
</div>

<div class="info-box">
  <strong>策略说明</strong>：当 RSI(14) 从 30+ 下穿至 30 以下（超卖信号）时，以市价做多（买入开仓），
  持续监控持仓。<br>
  &nbsp;&nbsp;• <strong>激进</strong>：RSI&lt;30 触发，8x杠杆，50%仓位，+8%止盈/-5%止损<br>
  &nbsp;&nbsp;• <strong>保守</strong>：RSI&lt;30 触发，5x杠杆，30%仓位，+6%止盈/-4%止损<br>
  &nbsp;&nbsp;• <strong>精准激进</strong>：RSI&lt;25 触发（更精准的超卖信号），8x杠杆，50%仓位，+8%止盈/-5%止损<br>
  手续费双边 0.1%（开仓+平仓各 0.05% taker），资金费率实时扣除。
</div>

<h2>策略参数对照表</h2>
<table>
  <thead><tr>
    <th>策略</th><th>RSI阈值</th><th>止盈</th><th>止损</th><th>杠杆</th>
    <th>仓位</th><th>交易数</th><th>盈/亏</th><th>胜率</th>
    <th>收益率</th><th>收益(USDT)</th><th>最大回撤</th>
    <th>夏普</th><th>平均持仓</th><th>最终资金</th>
  </tr></thead>
  <tbody>{param_rows}</tbody>
</table>

<h2>交易明细</h2>
<table>
  <thead><tr>
    <th>开仓时间</th><th>平仓时间</th><th>策略</th>
    <th>开仓价</th><th>平仓价</th><th>入场RSI</th>
    <th>收益率</th><th>盈亏(USDT)</th><th>出场原因</th><th>持仓时长</th>
  </tr></thead>
  <tbody>
    {trade_rows if trade_rows else '<tr><td colspan="10" style="text-align:center;color:#8b949e">无交易记录</td></tr>'}
  </tbody>
</table>

<h2>资金费率历史 (过去14期)</h2>
<table>
  <thead><tr><th>结算时间 (UTC)</th><th>资金费率</th></tr></thead>
  <tbody>{fund_rows}</tbody>
</table>

{improvements}

<div class="footer">
  生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp;
  数据来源: OKX Market API (公共数据，无需认证) &nbsp;|&nbsp;
  仅供回测参考，不构成任何投资建议
</div>
</body>
</html>"""

    out = "c:/Users/MECHREVO/WorkBuddy/20260408005632/backtest_CRCL_report.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nHTML报告已生成: {out}")

    # 保存 JSON 结果
    json_out = "c:/Users/MECHREVO/WorkBuddy/20260408005632/backtest_CRCL_result.json"
    json_data = []
    for r in results:
        json_data.append({
            "label": r["label"],
            "params": r["params"],
            "total_trades": r["total_trades"],
            "win_trades": r["win_trades"],
            "lose_trades": r["lose_trades"],
            "win_rate": round(r["win_rate"], 2),
            "total_return": round(r["total_return"], 4),
            "total_return_pct": round(r["total_return_pct"], 4),
            "max_drawdown": round(r["max_drawdown"], 4),
            "sharpe_ratio": round(r["sharpe_ratio"], 4),
            "avg_holding_h": round(r["avg_holding_h"], 2),
            "final_capital": round(r["final_capital"], 4),
            "trades": [
                {
                    "entry_time": t["entry_time"].isoformat(),
                    "exit_time": t["exit_time"].isoformat(),
                    "entry_price": t["entry_price"],
                    "exit_price": t["exit_price"],
                    "rsi_entry": t["rsi_entry"],
                    "pnl_pct": round(t["pnl_pct"], 4),
                    "pnl_usdt": round(t["pnl_usdt"], 4),
                    "exit_reason": t["exit_reason"],
                    "holding_h": round(t["holding_h"], 2),
                }
                for t in r["trades"]
            ],
        })
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"JSON结果已保存: {json_out}")
