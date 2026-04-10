"""
multi_coin_scanner.py — 多币种 RSI 并行扫描器
用法：
  python multi_coin_scanner.py                              # 默认 4 币种
  python multi_coin_scanner.py --coins BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP
  python multi_coin_scanner.py --rsi-oversold 25 --min-vol 50000

配合 crontab 每小时自动执行：
  0 * * * * cd /path/to && python scripts/multi_coin_scanner.py >> logs/scan.log 2>&1
"""
import argparse, urllib.request, json, time
from datetime import datetime

BASE = "https://www.okx.com"
DEFAULT_COINS = "CRCL-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,BTC-USDT-SWAP"


def fetch_candles(inst_id: str, bar: str = "1H", limit: int = 100) -> list:
    """拉 K 线数据（public endpoint，无需签名）"""
    url = f"{BASE}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "okx-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())["data"]
    candles = []
    for row in reversed(data):
        candles.append({"ts": int(row[0]), "close": float(row[4])})
    return candles


def calc_rsi(closes: list, period: int = 14) -> float:
    """计算 RSI"""
    if len(closes) < period + 1:
        return 50.0  # 数据不足返回中性
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
        "last": float(t.get("last", 0)),
        "vol24h": float(t.get("vol24h", 0)),
        "chg24h": float(t.get("sodUtc8", 0)),  # 24h 涨跌 (fractional)
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
    """计算强平价（逐仓做多）"""
    return entry_price * (1 - 1 / leverage)


def scan_coins(coins: list, rsi_oversold: float = 30, min_vol: float = 10000) -> list:
    """对多个币种扫描超卖信号，返回信号列表（按 RSI 从低到高排序）"""
    signals = []
    print(f"{'='*85}")
    print(f"Multi-coin RSI Scan  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*85}")
    print(f"{'Symbol':<28} {'RSI(14)':>7} {'RSI(6)':>7} {'Price':>12} {'24h Chg':>8} {'24h Vol':>14} {'FR/8h':>8}")
    print(f"{'-'*85}")

    for coin in coins:
        try:
            # K线 + RSI
            candles = fetch_candles(coin)
            closes = [c["close"] for c in candles]
            rsi14 = calc_rsi(closes, 14)
            rsi6  = calc_rsi(closes, 6)
            last  = closes[-1]

            # Ticker
            ticker = fetch_ticker(coin)
            vol24h = ticker["vol24h"]
            chg24h = ticker["chg24h"]

            # 资金费率
            fr = fetch_funding_rate(coin)

            print(f"  {coin:<26} {rsi14:6.1f} {rsi6:6.1f} {last:>12.4f} {chg24h*100:+7.2f}% {vol24h:>13,.0f} {fr*100:+7.4f}%")

            # 过滤低流动性
            if vol24h < min_vol:
                print(f"    [SKIP] 24h vol {vol24h:,.0f} < {min_vol:,.0f} (min_vol filter)")
                continue

            if rsi14 < rsi_oversold:
                signals.append({
                    "coin": coin, "rsi14": rsi14, "rsi6": rsi6,
                    "price": last, "vol24h": vol24h, "fr": fr,
                    "chg24h": chg24h,
                })

        except Exception as e:
            print(f"  {coin:<26} [ERROR] {e}")

    print(f"{'='*85}")
    return signals


def main():
    parser = argparse.ArgumentParser(description="Multi-coin RSI Scanner for OKX")
    parser.add_argument("--coins", default=DEFAULT_COINS,
                        help=f"Comma-separated instId list. Default: {DEFAULT_COINS}")
    parser.add_argument("--rsi-oversold", type=float, default=30,
                        help="RSI oversold threshold. Default: 30")
    parser.add_argument("--min-vol", type=float, default=10000,
                        help="Minimum 24h volume (USDT). Default: 10000")
    args = parser.parse_args()

    coins = [c.strip() for c in args.coins.split(",")]

    signals = scan_coins(coins, args.rsi_oversold, args.min_vol)

    if signals:
        print(f"\n[SIGNALS] {len(signals)} coin(s) oversold (RSI < {args.rsi_oversold}):")
        for s in sorted(signals, key=lambda x: x["rsi14"]):
            print(f"  >>> {s['coin']}: RSI={s['rsi14']:.1f}, "
                  f"Price={s['price']:.4f}, "
                  f"24h={s['chg24h']*100:+.2f}%, "
                  f"FR={s['fr']*100:+.4f}%/8h, "
                  f"Vol={s['vol24h']:,.0f} USDT")
    else:
        print(f"\n[OK] No oversold signals (RSI < {args.rsi_oversold})")
    print()


if __name__ == "__main__":
    main()
