"""
multi_coin_scanner.py — 多币种 RSI + ATR 并行扫描器
用法：
  python multi_coin_scanner.py                              # 默认 4 币种
  python multi_coin_scanner.py --coins BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP
  python multi_coin_scanner.py --rsi-oversold 25 --min-vol 50000

功能：
  1. 多币种并行扫描（3~6 个币种）
  2. RSI(14) / RSI(6) 超卖检测
  3. ATR(14) 动态止盈止损计算
  4. 每币种显示：RSI、ATR、动态 TP/SL（基于 ATR 倍数）、资金费率、24h 成交量

配合 crontab 每小时自动执行：
  0 * * * * cd /path/to && python scripts/multi_coin_scanner.py >> logs/scan.log 2>&1
"""
import argparse, urllib.request, json, time
from datetime import datetime

BASE = "https://www.okx.com"
DEFAULT_COINS = "CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,BTC-USDT-SWAP"

# ── ATR 参数 ──────────────────────────────────────────────────────────────────
# ATR 止盈止损倍数（可覆盖）
DEFAULT_TP_ATR = 2.0    # 止盈：Entry + TP_ATR * ATR
DEFAULT_SL_ATR = 1.5   # 止损：Entry - SL_ATR * ATR


# ── 数据获取 ──────────────────────────────────────────────────────────────────

def fetch_ohlcv(inst_id: str, bar: str = "1H", limit: int = 100) -> list:
    """
    拉 OHLCV K 线数据（public endpoint，无需签名）
    返回字段顺序：ts, open, high, low, close, vol
    OKX K线 API: [ts, open, high, low, close, vol]
    """
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
    计算 ATR（Average True Range）
    使用 Wilder 平滑法（等同于 TradingView 默认的 EMA 模式）

    True Range = max(
        high_t - low_t,
        |high_t - close_{t-1}|,
        |low_t  - close_{t-1}|
    )
    ATR(14) = (prev_ATR * 13 + TR_t) / 14
    """
    if len(ohlcv) < period + 1:
        return 0.0

    # Step 1: 计算前 (period-1) 个 TR，用 SMA 初始化 ATR
    tr_list = []
    for i in range(1, len(ohlcv)):
        h = ohlcv[i]["high"]
        l = ohlcv[i]["low"]
        pc = ohlcv[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)

    if len(tr_list) < period:
        return 0.0

    # Step 2: 前 period 个 TR 的 SMA 作为初始 ATR
    atr = sum(tr_list[:period]) / period

    # Step 3: Wilder 平滑
    for tr in tr_list[period:]:
        atr = (atr * (period - 1) + tr) / period

    return atr


def calc_rsi(closes: list, period: int = 14) -> float:
    """计算 RSI（标准版）"""
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


def fetch_ticker(inst_id: str) -> dict:
    """获取 Ticker 数据"""
    url = f"{BASE}/api/v5/market/ticker?instId={inst_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        t = json.loads(r.read())["data"][0]
    return {
        "last":   float(t.get("last", 0)),
        "vol24h": float(t.get("vol24h", 0)),
        "chg24h": float(t.get("sodUtc8", 0)),   # 24h 涨跌（分数）
    }


def fetch_funding_rate(inst_id: str) -> float:
    """获取最新资金费率"""
    url = f"{BASE}/api/v5/public/funding-rate-history?instId={inst_id}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())["data"]
        return float(data[0]["fundingRate"]) if data else 0.0
    except Exception:
        return 0.0


def calc_liquidation(entry_price: float, leverage: int) -> float:
    """强平价（逐仓做多）"""
    return entry_price * (1 - 1 / leverage)


def calc_atr_tp_sl(price: float, atr: float, tp_atr: float = DEFAULT_TP_ATR,
                   sl_atr: float = DEFAULT_SL_ATR) -> tuple:
    """基于 ATR 计算动态止盈止损价"""
    tp_price = price + tp_atr * atr
    sl_price = price - sl_atr * atr
    tp_pct = tp_atr * atr / price * 100
    sl_pct = sl_atr * atr / price * 100
    return tp_price, sl_price, tp_pct, sl_pct


# ── 扫描 ──────────────────────────────────────────────────────────────────────

def scan_coins(coins: list, rsi_oversold: float = 30, min_vol: float = 10000,
               tp_atr: float = DEFAULT_TP_ATR, sl_atr: float = DEFAULT_SL_ATR,
               leverage: int = 5) -> list:
    """对多个币种扫描，返回超卖信号列表"""
    signals = []
    print(f"\n{'='*105}")
    print(f"Multi-coin RSI+ATR Scan  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
          f"  [TP=Entry+{tp_atr}xATR, SL=Entry-{sl_atr}xATR, Lev={leverage}x]")
    print(f"{'='*105}")
    hdr = (f"{'Symbol':<28} {'RSI14':>7} {'RSI6':>7} {'Price':>12} "
           f"{'ATR(14)':>9} {'ATR/TP':>9} {'ATR/SL':>9} "
           f"{'24h Chg':>8} {'24h Vol':>14} {'FR/8h':>8}")
    print(hdr)
    print(f"{'-'*105}")

    for coin in coins:
        try:
            # 并行请求：K线 + Ticker + 资金费率
            ohlcv   = fetch_ohlcv(coin)
            ticker  = fetch_ticker(coin)
            fr      = fetch_funding_rate(coin)

            closes  = [c["close"] for c in ohlcv]
            rsi14   = calc_rsi(closes, 14)
            rsi6    = calc_rsi(closes, 6)
            atr14   = calc_atr(ohlcv, 14)
            last    = closes[-1]
            vol24h  = ticker["vol24h"]
            chg24h  = ticker["chg24h"]

            # 动态 TP/SL
            tp_price, sl_price, tp_pct, sl_pct = calc_atr_tp_sl(last, atr14, tp_atr, sl_atr)
            liq_price = calc_liquidation(last, leverage)
            dist_liq  = (last - liq_price) / last * 100 if liq_price > 0 else 999

            print(f"  {coin:<26} {rsi14:6.1f} {rsi6:6.1f} {last:>12.4f} "
                  f"{atr14:>9.4f} {tp_pct:>8.2f}% {sl_pct:>8.2f}% "
                  f"{chg24h*100:+7.2f}% {vol24h:>13,.0f} {fr*100:+7.4f}%")

            # ATR 安全过滤：SL 距强平价 < 1% → 风险过高
            dist_sl_liq = (sl_price - liq_price) / sl_price * 100 if sl_price > liq_price else 0
            if dist_sl_liq < 1:
                print(f"    [WARN] ATR-SL {sl_price:.4f} too close to Liq {liq_price:.4f} "
                      f"(gap={dist_sl_liq:.2f}%) — risky!")

            # 过滤低流动性
            if vol24h < min_vol:
                print(f"    [SKIP] vol {vol24h:,.0f} < {min_vol:,.0f} (min_vol)")
                continue

            if rsi14 < rsi_oversold:
                signals.append({
                    "coin":      coin,
                    "rsi14":     rsi14,
                    "rsi6":      rsi6,
                    "price":     last,
                    "atr14":     atr14,
                    "tp_price":  tp_price,
                    "sl_price":  sl_price,
                    "tp_pct":    tp_pct,
                    "sl_pct":    sl_pct,
                    "vol24h":    vol24h,
                    "fr":        fr,
                    "chg24h":    chg24h,
                    "liq_price": liq_price,
                    "dist_liq":  dist_liq,
                    "tp_atr":    tp_atr,
                    "sl_atr":    sl_atr,
                    "leverage":  leverage,
                    "dist_sl_liq": dist_sl_liq,
                })

        except Exception as e:
            print(f"  {coin:<26} [ERROR] {e}")

    print(f"{'='*105}")
    return signals


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-coin RSI+ATR Scanner for OKX — RSI oversold + ATR-based TP/SL")
    parser.add_argument("--coins", default=DEFAULT_COINS,
                        help=f"Comma-separated instId list. Default: {DEFAULT_COINS}")
    parser.add_argument("--rsi-oversold", type=float, default=30,
                        help="RSI oversold threshold. Default: 30")
    parser.add_argument("--min-vol", type=float, default=10000,
                        help="Minimum 24h volume (USDT). Default: 10000")
    parser.add_argument("--tp-atr", type=float, default=DEFAULT_TP_ATR,
                        help=f"TP multiplier × ATR. Default: {DEFAULT_TP_ATR}")
    parser.add_argument("--sl-atr", type=float, default=DEFAULT_SL_ATR,
                        help=f"SL multiplier × ATR. Default: {DEFAULT_SL_ATR}")
    parser.add_argument("--leverage", type=int, default=5,
                        help="Leverage for liq calculation. Default: 5")
    args = parser.parse_args()

    coins = [c.strip() for c in args.coins.split(",")]

    signals = scan_coins(
        coins,
        rsi_oversold=args.rsi_oversold,
        min_vol=args.min_vol,
        tp_atr=args.tp_atr,
        sl_atr=args.sl_atr,
        leverage=args.leverage,
    )

    if signals:
        print(f"\n[SIGNALS] {len(signals)} coin(s) oversold (RSI < {args.rsi_oversold}):")
        for s in sorted(signals, key=lambda x: x["rsi14"]):
            print(f"  >>> {s['coin']}")
            print(f"      Price={s['price']:.4f} | ATR(14)={s['atr14']:.4f}")
            print(f"      TP={s['tp_price']:.4f} (+{s['tp_pct']:.2f}%) | "
                  f"SL={s['sl_price']:.4f} (-{s['sl_pct']:.2f}%)")
            print(f"      Liq={s['liq_price']:.4f} ({s['dist_liq']:.2f}% above liq) | "
                  f"SL-Liq gap={s['dist_sl_liq']:.2f}%")
            print(f"      RSI(14)={s['rsi14']:.1f} | RSI(6)={s['rsi6']:.1f} | "
                  f"FR={s['fr']*100:+.4f}%/8h | Vol={s['vol24h']:,.0f} USDT")

        print(f"\n[RUN] Example command:")
        s0 = signals[0]
        print(f"  python scripts/run_tracking.py "
              f"--symbol {s0['coin']} --entry {s0['price']:.4f} "
              f"--atr14 {s0['atr14']:.4f} --tp-atr {s0['tp_atr']} --sl-atr {s0['sl_atr']} "
              f"--leverage {s0['leverage']} --profile live")
    else:
        print(f"\n[OK] No oversold signals (RSI < {args.rsi_oversold})")
    print()


if __name__ == "__main__":
    main()
