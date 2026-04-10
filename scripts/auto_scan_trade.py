"""
OKX Agent Trade Kit - 市场扫描脚本
功能：扫描主流USDT永续合约，RSI超卖时自动开仓（40%仓位，5x杠杆）
参数：止盈8% / 止损5%
"""
import json, time, urllib.request, hmac, hashlib, base64, sys

# ============ 配置 ============
API_KEY    = "965f3977-59e7-47fc-bc19-75abb7caa424"
SECRET_KEY = "37D24B51600BD291E9EFF3D58963A87E"
PASSPHRASE = "@102415Mjh"
BASE_URL   = "https://www.okx.com"

RSI_PERIOD     = 14
RSI_OVERSOLD   = 25
TP_PCT         = 8.0
SL_PCT         = 5.0
LEVERAGE       = 5
POSITION_PCT    = 40
MAX_CONTRACTS  = 20  # 最多扫描20个候选币

# ============ 工具函数 ============
def sign(ts, method, path, body, secret_key):
    message = ts + method + path + (body or '')
    mac = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def http_request(method, path, body=''):
    ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    signature = sign(ts, method, path, body, SECRET_KEY)
    headers = {
        'Content-Type': 'application/json',
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
    }
    url = f'{BASE_URL}{path}'
    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def calc_rsi(closes, period=14):
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

def fetch_candles(inst_id, bar="1H", limit=100):
    url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
    data = fetch(url).get("data", [])
    candles = []
    for row in reversed(data):
        candles.append({"close": float(row[4])})
    return candles

def calc_liquidation(entry_price, leverage, side="long"):
    if side == "long":
        return entry_price * (1 - 1 / leverage)
    return entry_price * (1 + 1 / leverage)

# ============ 主流程 ============
print("=" * 60)
print("OKX Agent Trade Kit - 市场扫描 v1.0")
print("=" * 60)

# Phase 0: 检查持仓
print("\n[Phase 0] 检查当前持仓...")
positions = http_request('GET', '/api/v5/account/positions')
open_positions = [p for p in positions.get('data', []) if float(p.get('imizedPos', '0') or '0') != 0]
if open_positions:
    print(f"  ⚠️ 已有持仓 {len(open_positions)} 个，等待手动平仓后重启")
    for p in open_positions:
        print(f"    {p['instId']} {p['side']} {p['availPos']}张")
    sys.exit(0)

# 查询余额
balance_data = http_request('GET', '/api/v5/account/balance')
balances = balance_data.get('data', [{}])[0].get('details', [])
usdt_balance = 0.0
for b in balances:
    if b.get('ccy') == 'USDT':
        usdt_balance = float(b.get('availBal', '0'))
        break
print(f"  ✅ 可用 USDT: ${usdt_balance:.2f}")

# Phase 1: 市场扫描
print("\n[Phase 1] 扫描主流USDT永续合约...")

# 优先扫描主流币 + 热门币
candidates = [
    "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP",
    "BNB-USDT-SWAP", "DOGE-USDT-SWAP", "XRP-USDT-SWAP",
    "ADA-USDT-SWAP", "AVAX-USDT-SWAP", "DOT-USDT-SWAP",
    "LINK-USDT-SWAP", "MATIC-USDT-SWAP", "LTC-USDT-SWAP",
    "SHIB-USDT-SWAP", "UNI-USDT-SWAP", "ATOM-USDT-SWAP",
    "APT-USDT-SWAP", "ARBUDSWAP", "OP-USDT-SWAP",
    "PEPEUSDT-SWAP", "WIFUSDT-SWAP",
]

# 过滤有行情的币
print("  1. 获取有效行情...")
valid = []
for inst_id in candidates[:MAX_CONTRACTS]:
    try:
        ticker_data = fetch(f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}")
        if ticker_data.get('data'):
            t = ticker_data['data'][0]
            last = float(t.get('last', 0))
            vol24h = float(t.get('vol24h', 0))
            if last > 0 and vol24h > 10000:  # 24h成交量>1万U
                valid.append(inst_id)
    except:
        pass
print(f"  ✅ 有效交易对: {len(valid)} 个")

# 计算RSI
print("  2. 计算RSI(14)...")
results = []
for inst_id in valid:
    try:
        candles = fetch_candles(inst_id, bar="1H", limit=100)
        if len(candles) < RSI_PERIOD + 1:
            continue
        closes = [c['close'] for c in candles]
        rsi = calc_rsi(closes, RSI_PERIOD)
        ticker_data = fetch(f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}")
        last = float(ticker_data['data'][0]['last'])
        change24h = float(ticker_data['data'][0].get('sodUtc8', 0))
        results.append({
            'instId': inst_id,
            'rsi': rsi,
            'last': last,
            'change24h': change24h,
        })
    except Exception as e:
        pass

# 按RSI排序
results.sort(key=lambda x: x['rsi'])
print(f"\n  📊 RSI扫描结果（前10）:")
print(f"  {'币种':<20} {'RSI':>6} {'现价':>12} {'24h涨跌':>8}")
print(f"  {'-'*48}")
for r in results[:10]:
    emoji = "🔴" if r['rsi'] < RSI_OVERSOLD else ("🟡" if r['rsi'] < 40 else "🟢")
    print(f"  {emoji} {r['instId'].replace('-USDT-SWAP',''):<18} {r['rsi']:>6.1f} {r['last']:>12.4f} {r['change24h']:>+7.2f}%")

# Phase 2: 选最超卖的候选币开仓
oversold = [r for r in results if r['rsi'] < RSI_OVERSOLD]
if not oversold:
    print("\n⏳ 没有任何币RSI<25，继续空仓等待下次扫描")
    sys.exit(0)

best = oversold[0]
inst_id = best['inst_id'] = best['instId']
entry_price = best['last']
print(f"\n[Phase 2] ✅ 信号触发！")
print(f"  标的: {inst_id}")
print(f"  RSI: {best['rsi']:.1f}")
print(f"  现价: ${entry_price:.4f}")

# 计算开仓参数
position_value = usdt_balance * POSITION_PCT / 100
margin_needed = position_value / LEVERAGE
contract_qty = int(margin_needed / entry_price / 0.01)  # 按BTC合约面值估算
if 'ETH' in inst_id:
    contract_qty = int(margin_needed / entry_price / 0.1)
elif 'SOL' in inst_id:
    contract_qty = int(margin_needed / entry_price / 10)
else:
    contract_qty = int(margin_needed / entry_price / 0.01)
contract_qty = max(1, contract_qty)

tp_price = entry_price * (1 + TP_PCT / 100)
sl_price = entry_price * (1 - SL_PCT / 100)
liq_price = calc_liquidation(entry_price, LEVERAGE, 'long')
safety_margin = (entry_price - liq_price) / entry_price * 100

print(f"\n  开仓计划:")
print(f"  仓位: {POSITION_PCT}% (${position_value:.2f})")
print(f"  杠杆: {LEVERAGE}x")
print(f"  合约张数: {contract_qty}")
print(f"  止盈: ${tp_price:.4f} (+{TP_PCT}%)")
print(f"  止损: ${sl_price:.4f} (-{SL_PCT}%)")
print(f"  强平价: ${liq_price:.4f} (距现价 {safety_margin:.1f}%)")

if safety_margin < 5:
    print(f"  🚨 距强平价不足5%，拒绝开仓！")
    sys.exit(0)

# 设置杠杆
print(f"\n  设置{LEVERAGE}x杠杆...")
leverage_data = http_request('POST', '/api/v5/account/set-leverage', json.dumps({
    "instId": inst_id, "lever": str(LEVERAGE),
    "mgnMode": "isolated", "posSide": "long"
}))
print(f"  杠杆设置结果: {leverage_data.get('msg', 'OK')}")

# 开多
print(f"\n  市价开多...")
order_body = json.dumps({
    "instId": inst_id, "tdMode": "isolated", "side": "buy",
    "ordType": "market", "sz": str(contract_qty), "posSide": "long"
})
order_result = http_request('POST', '/api/v5/trade/order', order_body)
print(f"  开仓结果: {json.dumps(order_result, indent=2, ensure_ascii=False)}")

if order_result.get('code') == '0':
    fills = order_result.get('data', [{}])[0].get('fills', [])
    if fills:
        actual_price = float(fills[0].get('fillPx', entry_price))
        print(f"  ✅ 开仓成功！成交价: ${actual_price:.4f}")
        tp_price = actual_price * (1 + TP_PCT / 100)
        sl_price = actual_price * (1 - SL_PCT / 100)
        print(f"  更新止盈: ${tp_price:.4f} | 止损: ${sl_price:.4f}")

        # 设置止盈止损
        print(f"\n  设置止盈止损...")
        algo_body = json.dumps({
            "instId": inst_id, "side": "sell", "sz": str(contract_qty),
            "ordType": "conditional",
            "tpTriggerPx": str(tp_price), "tpOrdPx": str(tp_price),
            "slTriggerPx": str(sl_price), "slOrdPx": str(sl_price),
            "posSide": "long", "tdMode": "isolated"
        })
        tp_result = http_request('POST', '/api/v5/trade/order-algo', algo_body)
        print(f"  止盈止损设置: {tp_result.get('msg', 'OK')}")
    else:
        print(f"  ⚠️ 订单已下但无成交数据")
else:
    print(f"  ❌ 开仓失败: {order_result.get('msg')}")
    print(f"  错误码: {order_result.get('code')}")

print("\n" + "=" * 60)
print("扫描完成")
print("=" * 60)
