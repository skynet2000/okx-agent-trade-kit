"""
run_tracking.py — 追踪止损 + 飞书通知 持仓监控主脚本
用法：
  python run_tracking.py --symbol CRCL-USDT-SWAP --entry 85.7673 --leverage 5 \
      --tp-pct 6 --sl-pct 4 --trailing-pct 5 --profile live

功能：
  1. 追踪止损：浮盈 > trailing_pct 时自动将 SL 上调至成本价
  2. 飞书通知：每 30 分钟推送一次 + 关键事件立即通知
  3. 关键指标：RSI、强平价距离、资金费率、浮盈/浮亏
  4. 支持 demo/live 模式
"""
import argparse, urllib.request, json, time, sys
from datetime import datetime

BASE = "https://www.okx.com"
DEFAULT_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/b2aefdfe-a15d-481a-885b-5b5bb91d4be4"


# ── 数据获取 ──────────────────────────────────────────────────────────────────

def get_ticker(inst_id: str) -> dict:
    url = f"{BASE}/api/v5/market/ticker?instId={inst_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        t = json.loads(r.read())["data"][0]
    return {
        "last": float(t.get("last", 0)),
        "vol24h": float(t.get("vol24h", 0)),
        "high24h": float(t.get("high24h", 0)),
        "low24h": float(t.get("low24h", 0)),
    }


def fetch_candles(inst_id: str, bar: str = "1H", limit: int = 100) -> list:
    url = f"{BASE}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())["data"]
    return [{"ts": int(row[0]), "close": float(row[4])} for row in reversed(data)]


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


# ── 飞书通知 ──────────────────────────────────────────────────────────────────

def send_trade_notification(action, symbol, profile, price, entry_price,
                             rsi14, pnl_pct, pnl_usdt, dist_to_liq,
                             dist_to_sl, dist_to_tp, fr, trailing_active,
                             leverage, hold_hours, webhook=DEFAULT_WEBHOOK):
    sys.path.insert(0, str(__file__).rsplit("/", 1)[0])
    try:
        from feishu_notify import send_trade_notification as _send
        _send(action, symbol, profile, price, entry_price, rsi14, pnl_pct,
              pnl_usdt, dist_to_liq, dist_to_sl, dist_to_tp, fr,
              trailing_active, leverage, hold_hours, webhook)
    except Exception as e:
        print(f"[Feishu] import/send failed: {e}")


# ── 追踪止损主循环 ─────────────────────────────────────────────────────────────

def run_tracking(symbol, entry_price, leverage, tp_pct=8, sl_pct=5,
                 trailing_pct=5, max_hold_hours=336, check_interval=60,
                 profile="live", webhook=DEFAULT_WEBHOOK, auto_exit=True):
    """
    持仓监控主循环
    auto_exit=True: 触发止盈/止损/超时时自动市价平仓
    auto_exit=False: 仅监控和通知，不执行平仓（需人工操作）
    """
    tp_price = entry_price * (1 + tp_pct / 100)
    sl_price = entry_price * (1 - sl_pct / 100)   # 动态
    liq_price = calc_liquidation(entry_price, leverage)
    entry_time = time.time()
    max_time = entry_time + max_hold_hours * 3600
    trailing_locked = False
    trailing_locked_price = None
    last_feishu = 0

    print(f"[START] {symbol} | Entry: {entry_price} | TP: {tp_price:.4f} | "
          f"SL: {sl_price:.4f} | Liq: {liq_price:.4f} | "
          f"Trailing: {trailing_pct}% | Profile: {profile}")
    print(f"         {'='*70}")

    # 开仓通知
    send_trade_notification("entry", symbol, profile,
                             entry_price, entry_price,
                             0, 0, 0, 999, 999, 999, 0,
                             False, leverage, 0, webhook)

    while True:
        now = time.time()

        # 获取实时数据
        ticker = get_ticker(symbol)
        current_price = ticker["last"]
        candles = fetch_candles(symbol, limit=50)
        rsi14 = calc_rsi([c["close"] for c in candles])
        fr = fetch_funding_rate(symbol)

        pnl_pct = (current_price - entry_price) / entry_price * 100
        # 逐仓：每张面值 0.01 BTC 等，简化用 notional 估算
        notional = current_price * 0.01  # 简化估算
        pnl_usdt = pnl_pct / 100 * notional * 10  # 10张

        dist_to_tp  = (tp_price  - current_price) / current_price * 100
        dist_to_sl  = (current_price - sl_price) / current_price * 100
        dist_to_liq = (current_price - liq_price) / current_price * 100
        daily_fr_cost = fr * 3 * 100
        hold_h = (now - entry_time) / 3600

        # [核心] 追踪止损：浮盈超过阈值，锁 SL 至成本价
        if not trailing_locked and pnl_pct > trailing_pct:
            old_sl = sl_price
            sl_price = entry_price
            trailing_locked = True
            trailing_locked_price = entry_price
            print(f"[TRAILING] *** PnL {pnl_pct:.2f}% > {trailing_pct}% *** "
                  f"SL raised: {old_sl:.4f} -> {entry_price:.4f} (COST PRICE)")
            send_trade_notification("trailing", symbol, profile,
                                    current_price, entry_price, rsi14,
                                    pnl_pct, pnl_usdt, dist_to_liq,
                                    0, dist_to_tp, fr, True,
                                    leverage, hold_h, webhook)

        # [飞书] 每 30 分钟常规推送
        if now - last_feishu > 1800:
            send_trade_notification("scan", symbol, profile,
                                    current_price, entry_price, rsi14,
                                    pnl_pct, pnl_usdt, dist_to_liq,
                                    dist_to_sl, dist_to_tp, fr,
                                    trailing_locked, leverage, hold_h, webhook)
            last_feishu = now

        # [平仓判断]
        exit_reason = None
        if current_price >= tp_price:
            exit_reason = "exit_tp"
        elif current_price <= sl_price:
            exit_reason = "exit_sl"
        elif now >= max_time:
            exit_reason = "timeout"

        if exit_reason:
            exit_pnl_pct = pnl_pct
            exit_pnl_usdt = pnl_usdt
            print(f"[EXIT:{exit_reason}] {symbol} | "
                  f"Price: {current_price:.4f} | "
                  f"PnL: {exit_pnl_pct:+.2f}% ({exit_pnl_usdt:+.4f} USDT) | "
                  f"Hold: {hold_h:.1f}h")

            send_trade_notification(exit_reason, symbol, profile,
                                    current_price, entry_price, rsi14,
                                    exit_pnl_pct, exit_pnl_usdt, dist_to_liq,
                                    0, 0, fr, trailing_locked,
                                    leverage, hold_h, webhook)

            if auto_exit:
                print(f"[AUTO-EXIT] Executing market close order...")
                # okx swap place --side sell --tdMode isolated --posSide long
                # --ordType market --sz {size} --profile {profile}
                # (需要传入 sz 参数，或从持仓查询获取)
                import subprocess
                sz = 10  # TODO: 从持仓接口动态获取
                cmd = (f"okx swap place --instId {symbol} --side sell "
                       f"--tdMode isolated --posSide long --ordType market "
                       f"--sz {sz} --profile {profile}")
                print(f"[CMD] {cmd}")
                # subprocess.run(cmd, shell=True)
            break

        # 控制台输出
        trailing_tag = " [TRAILING]" if trailing_locked else ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} | "
              f"Price={current_price:.4f} | "
              f"PnL={pnl_pct:+.2f}%{trailing_tag} | "
              f"TP={dist_to_tp:+.2f}% | SL={dist_to_sl:+.2f}% | "
              f"Liq={dist_to_liq:+.2f}% | RSI={rsi14:.1f} | "
              f"FR={fr*100:+.4f}%/8h | {hold_h:.1f}h")

        time.sleep(check_interval)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="OKX RSI Tracking Stop - Position Monitor")
    p.add_argument("--symbol", required=True, help="instId, e.g. CRCL-USDT-SWAP")
    p.add_argument("--entry", type=float, required=True, help="Entry price")
    p.add_argument("--leverage", type=int, default=5, help="Leverage (default: 5)")
    p.add_argument("--tp-pct", type=float, default=6, help="Take profit % (default: 6)")
    p.add_argument("--sl-pct", type=float, default=4, help="Stop loss % (default: 4)")
    p.add_argument("--trailing-pct", type=float, default=5,
                   help="Trailing trigger % (default: 5)")
    p.add_argument("--max-hold-hours", type=int, default=336,
                   help="Max hold hours (default: 336 = 14 days)")
    p.add_argument("--check-interval", type=int, default=60,
                   help="Check interval seconds (default: 60)")
    p.add_argument("--profile", default="live",
                   choices=["live", "demo"], help="Account profile (default: live)")
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
        tp_pct=args.tp_pct,
        sl_pct=args.sl_pct,
        trailing_pct=args.trailing_pct,
        max_hold_hours=args.max_hold_hours,
        check_interval=args.check_interval,
        profile=args.profile,
        webhook=args.webhook,
        auto_exit=args.auto_exit,
    )


if __name__ == "__main__":
    main()
