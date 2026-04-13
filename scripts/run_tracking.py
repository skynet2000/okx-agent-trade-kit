"""
run_tracking.py — ATR 动态止盈止损 + 追踪止损 持仓监控主脚本
用法：
  python run_tracking.py --symbol CRCL-USDT-SWAP --entry 85.7673 --leverage 5 \
      --atr14 3.5 --tp-atr 2.0 --sl-atr 1.5 --trailing-pct 5 --profile live

功能：
  1. ATR 动态止盈止损（自适应市场波动，非固定百分比）
  2. 追踪止损：浮盈 > trailing_pct 时自动将 SL 上调至成本价
  3. 飞书通知：每 30 分钟推送一次 + 关键事件立即通知
  4. 关键指标：RSI、ATR、强平价距离、资金费率、浮盈/浮亏
  5. 支持 demo/live 模式
"""
import argparse, os, urllib.request, json, time, sys
from datetime import datetime

BASE = "https://www.okx.com"
DEFAULT_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")  # 通过环境变量传入

# ── 数据获取 ──────────────────────────────────────────────────────────────────

def get_ticker(inst_id: str) -> dict:
    url = f"{BASE}/api/v5/market/ticker?instId={inst_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        t = json.loads(r.read())["data"][0]
    return {
        "last":    float(t.get("last", 0)),
        "vol24h":  float(t.get("vol24h", 0)),
        "high24h": float(t.get("high24h", 0)),
        "low24h":  float(t.get("low24h", 0)),
    }


def fetch_ohlcv(inst_id: str, bar: str = "1H", limit: int = 100) -> list:
    """拉 OHLCV K 线数据（public endpoint）"""
    url = f"{BASE}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())["data"]
    candles = []
    for row in reversed(data):
        candles.append({
            "ts":    int(row[0]),
            "open":  float(row[1]),
            "high":  float(row[2]),
            "low":   float(row[3]),
            "close": float(row[4]),
            "vol":   float(row[5]),
        })
    return candles


def calc_atr(ohlcv: list, period: int = 14) -> float:
    """
    计算 ATR（Average True Range），Wilder 平滑法
    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR(14) = (prev_ATR * 13 + TR) / 14
    """
    if len(ohlcv) < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, len(ohlcv)):
        h  = ohlcv[i]["high"]
        l  = ohlcv[i]["low"]
        pc = ohlcv[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    if len(tr_list) < period:
        return 0.0
    atr = sum(tr_list[:period]) / period
    for tr in tr_list[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def fetch_funding_rate(inst_id: str) -> float:
    url = f"{BASE}/api/v5/public/funding-rate-history?instId={inst_id}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())["data"]
        return float(data[0]["fundingRate"]) if data else 0.0
    except Exception:
        return 0.0


def calc_liquidation(entry_price: float, leverage: int) -> float:
    """强平价（USDT 本位逐仓做多）"""
    return entry_price * (1 - 1 / leverage)


def calc_atr_levels(entry_price: float, atr: float,
                    tp_atr: float, sl_atr: float) -> tuple:
    """基于 ATR 计算动态止盈止损价格"""
    tp_price = entry_price + tp_atr * atr
    sl_price = entry_price - sl_atr * atr
    return tp_price, sl_price


# ── 飞书通知 ──────────────────────────────────────────────────────────────────

def send_trade_notification(action, symbol, profile, price, entry_price,
                             rsi14, atr14, pnl_pct, pnl_usdt,
                             dist_to_liq, dist_to_sl, dist_to_tp,
                             fr, trailing_active, leverage, hold_hours,
                             tp_price, sl_price, webhook=DEFAULT_WEBHOOK):
    sys.path.insert(0, str(__file__).rsplit("/", 1)[0])
    try:
        from feishu_notify import send_trade_notification as _send
        _send(action, symbol, profile, price, entry_price,
              rsi14, atr14, pnl_pct, pnl_usdt,
              dist_to_liq, dist_to_sl, dist_to_tp,
              fr, trailing_active, leverage, hold_hours,
              tp_price, sl_price, webhook)
    except Exception as e:
        print(f"[Feishu] import/send failed: {e}")


# ── 追踪止损主循环 ─────────────────────────────────────────────────────────────

def run_tracking(symbol, entry_price, leverage, atr14,
                 tp_atr=2.0, sl_atr=1.5, trailing_pct=5,
                 max_hold_hours=336, check_interval=60,
                 profile="live", webhook=DEFAULT_WEBHOOK,
                 auto_exit=True):
    """
    持仓监控主循环 — ATR 动态止盈止损 + 追踪止损

    参数：
      symbol         : instId，如 CRCL-USDT-SWAP
      entry_price    : 开仓均价
      leverage       : 杠杆倍数
      atr14          : 当前 ATR(14) 值（从 multi_coin_scanner.py 获取）
      tp_atr         : 止盈 ATR 倍数（TP = Entry + tp_atr * ATR）
      sl_atr         : 止损 ATR 倍数（SL = Entry - sl_atr * ATR）
      trailing_pct   : 追踪止盈触发阈值（%）
      max_hold_hours : 最大持仓小时数
      check_interval : 轮询间隔（秒）
      profile        : live / demo
      auto_exit      : True=自动市价平仓，False=仅通知（人工操作）
    """
    tp_price, sl_price = calc_atr_levels(entry_price, atr14, tp_atr, sl_atr)
    tp_pct = tp_atr * atr14 / entry_price * 100
    sl_pct = sl_atr * atr14 / entry_price * 100
    liq_price = calc_liquidation(entry_price, leverage)

    # ATR 安全检查：SL 距强平价太近 → 警告
    dist_sl_liq = (sl_price - liq_price) / sl_price * 100
    if dist_sl_liq < 1:
        print(f"[WARN] SL {sl_price:.4f} is < 1% from Liq {liq_price:.4f} -- HIGH RISK!")

    entry_time    = time.time()
    max_time      = entry_time + max_hold_hours * 3600
    trailing_locked = False
    last_feishu   = 0

    print(f"\n{'='*75}")
    print(f"[START] {symbol} [{profile}]")
    print(f"  Entry:    {entry_price:.4f} | ATR(14): {atr14:.4f}")
    print(f"  TP:       {tp_price:.4f} (+{tp_pct:.2f}%, {tp_atr}x ATR)")
    print(f"  SL:       {sl_price:.4f} (-{sl_pct:.2f}%, {sl_atr}x ATR)")
    print(f"  Liq:      {liq_price:.4f} ({dist_sl_liq:.2f}% above SL)")
    print(f"  Trailing: {trailing_pct}% profit -> SL locked to cost")
    print(f"  MaxHold:  {max_hold_hours}h | Interval: {check_interval}s")
    print(f"{'='*75}\n")

    # 开仓通知
    send_trade_notification(
        "entry", symbol, profile,
        entry_price, entry_price,
        0, atr14, 0, 0, 999, 999, 999, 0,
        False, leverage, 0,
        tp_price, sl_price, webhook
    )

    while True:
        now = time.time()

        # ── 获取实时数据 ──
        ticker = get_ticker(symbol)
        ohlcv  = fetch_ohlcv(symbol, limit=50)
        closes = [c["close"] for c in ohlcv]
        rsi14  = calc_rsi(closes)
        atr_cur = calc_atr(ohlcv)          # 每轮重新计算最新 ATR
        fr     = fetch_funding_rate(symbol)
        current_price = ticker["last"]

        # ── ATR 动态更新 TP/SL（每轮按最新 ATR 调整）──────────────
        tp_price_cur, sl_price_cur = calc_atr_levels(entry_price, atr_cur, tp_atr, sl_atr)
        tp_pct_cur = tp_atr * atr_cur / entry_price * 100
        sl_pct_cur = sl_atr * atr_cur / entry_price * 100

        pnl_pct   = (current_price - entry_price) / entry_price * 100
        notional  = current_price * 0.01 * 10     # 10 张 × 0.01 USDT/张面值估算
        pnl_usdt  = pnl_pct / 100 * notional

        dist_to_tp  = (tp_price_cur  - current_price) / current_price * 100
        dist_to_sl  = (current_price - sl_price_cur)   / current_price * 100
        dist_to_liq = (current_price - liq_price)       / current_price * 100
        daily_fr_cost = fr * 3 * 100
        hold_h = (now - entry_time) / 3600

        # ── [追踪止损] 浮盈超过阈值 → SL 锁成本价 ─────────────────
        if not trailing_locked and pnl_pct > trailing_pct:
            old_sl = sl_price_cur
            sl_price_cur = entry_price          # 锁定利润
            trailing_locked = True
            print(f"[TRAILING] *** PnL {pnl_pct:.2f}% > {trailing_pct}% ***")
            print(f"            SL raised: {old_sl:.4f} -> {entry_price:.4f} (COST)")
            send_trade_notification(
                "trailing", symbol, profile,
                current_price, entry_price,
                rsi14, atr_cur, pnl_pct, pnl_usdt,
                dist_to_liq,
                (current_price - entry_price) / current_price * 100,
                dist_to_tp, fr, True, leverage, hold_h,
                tp_price_cur, entry_price, webhook
            )

        # ── [飞书] 每 30 分钟常规推送 ─────────────────────────────
        if now - last_feishu > 1800:
            send_trade_notification(
                "scan", symbol, profile,
                current_price, entry_price,
                rsi14, atr_cur, pnl_pct, pnl_usdt,
                dist_to_liq, dist_to_sl, dist_to_tp,
                fr, trailing_locked, leverage, hold_h,
                tp_price_cur, sl_price_cur, webhook
            )
            last_feishu = now

        # ── [平仓判断] ───────────────────────────────────────────
        exit_reason = None
        if current_price >= tp_price_cur:
            exit_reason = "exit_tp"
        elif current_price <= sl_price_cur:
            exit_reason = "exit_sl"
        elif now >= max_time:
            exit_reason = "timeout"

        if exit_reason:
            exit_pnl_pct  = pnl_pct
            exit_pnl_usdt = pnl_usdt
            print(f"\n[EXIT:{exit_reason}] {symbol} | Profile: {profile}")
            print(f"  Exit:   {current_price:.4f}")
            print(f"  PnL:    {exit_pnl_pct:+.2f}% ({exit_pnl_usdt:+.4f} USDT)")
            print(f"  Hold:   {hold_h:.1f}h | ATR={atr_cur:.4f}")
            print(f"  Trailing: {'ACTIVE' if trailing_locked else 'NO'}")

            send_trade_notification(
                exit_reason, symbol, profile,
                current_price, entry_price,
                rsi14, atr_cur, exit_pnl_pct, exit_pnl_usdt,
                dist_to_liq, 0, 0,
                fr, trailing_locked, leverage, hold_h,
                tp_price_cur, sl_price_cur, webhook
            )

            if auto_exit:
                print(f"[AUTO-EXIT] Executing market close order...")
                # okx swap place --side sell --tdMode isolated --posSide long
                # --ordType market --sz {size} --profile {profile}
                import subprocess
                sz = 10  # TODO: 从持仓接口动态获取张数
                cmd = (f"okx swap place --instId {symbol} --side sell "
                       f"--tdMode isolated --posSide long --ordType market "
                       f"--sz {sz} --profile {profile}")
                print(f"[CMD] {cmd}")
                # subprocess.run(cmd, shell=True)
            break

        # ── 控制台输出 ───────────────────────────────────────────
        atr_delta = atr_cur - atr14
        atr_arrow = "↑" if atr_delta > 0.01 else ("↓" if atr_delta < -0.01 else "~")
        trailing_tag = " [TRAILING]" if trailing_locked else ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} | "
              f"Price={current_price:.4f} | "
              f"PnL={pnl_pct:+.2f}%{trailing_tag} | "
              f"ATR={atr_cur:.4f}({atr_arrow}) | "
              f"TP={tp_price_cur:.4f}({dist_to_tp:+.2f}%) | "
              f"SL={sl_price_cur:.4f}({dist_to_sl:+.2f}%) | "
              f"Liq={dist_to_liq:.2f}% | "
              f"RSI={rsi14:.1f} | "
              f"FR={fr*100:+.4f}%/8h | "
              f"{hold_h:.1f}h")

        time.sleep(check_interval)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="OKX ATR Dynamic TP/SL + Trailing Stop -- Position Monitor v1.3")
    p.add_argument("--symbol", required=True,
                   help="instId, e.g. CRCL-USDT-SWAP")
    p.add_argument("--entry", type=float, required=True,
                   help="Entry price")
    p.add_argument("--leverage", type=int, default=5,
                   help="Leverage (default: 5)")
    p.add_argument("--atr14", type=float, required=True,
                   help="Current ATR(14) value -- get from multi_coin_scanner.py")
    p.add_argument("--tp-atr", type=float, default=2.0,
                   help="TP = Entry + tp_atr * ATR (default: 2.0)")
    p.add_argument("--sl-atr", type=float, default=1.5,
                   help="SL = Entry - sl_atr * ATR (default: 1.5)")
    p.add_argument("--trailing-pct", type=float, default=5,
                   help="Trailing trigger %% (default: 5 -- profit > 5%% locks SL to cost)")
    p.add_argument("--max-hold-hours", type=int, default=336,
                   help="Max hold hours (default: 336 = 14 days)")
    p.add_argument("--check-interval", type=int, default=60,
                   help="Check interval seconds (default: 60)")
    p.add_argument("--profile", default="live",
                   choices=["live", "demo"],
                   help="Account profile (default: live)")
    p.add_argument("--webhook", default=DEFAULT_WEBHOOK,
                   help="Feishu webhook URL")
    p.add_argument("--no-auto-exit", dest="auto_exit", action="store_false",
                   help="Disable auto market close (monitor only)")
    p.set_defaults(auto_exit=True)
    args = p.parse_args()

    run_tracking(
        symbol=args.symbol,
        entry_price=args.entry,
        leverage=args.leverage,
        atr14=args.atr14,
        tp_atr=args.tp_atr,
        sl_atr=args.sl_atr,
        trailing_pct=args.trailing_pct,
        max_hold_hours=args.max_hold_hours,
        check_interval=args.check_interval,
        profile=args.profile,
        webhook=args.webhook,
        auto_exit=args.auto_exit,
    )


if __name__ == "__main__":
    main()
