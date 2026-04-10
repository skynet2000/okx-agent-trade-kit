"""
feishu_notify.py — 飞书通知模块（含 ATR 动态止盈止损）
用法：
  from feishu_notify import send_trade_notification, send_scan_notification

v1.3 新增：ATR(14)、动态 TP/SL 价格（基于 ATR 倍数）、ATR 波动率
"""
import urllib.request, json
from datetime import datetime

# 唯一正确 webhook（2026-04-03 用户确认）
DEFAULT_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/b2aefdfe-a15d-481a-885b-5b5bb91d4be4"


def send_trade_notification(
    action: str,          # "entry" | "exit_tp" | "exit_sl" | "timeout" | "trailing" | "scan"
    symbol: str,
    profile: str,          # "demo" | "live"
    price: float,
    entry_price: float,
    rsi14: float,
    atr14: float,         # v1.3: ATR(14) 当前值
    pnl_pct: float,
    pnl_usdt: float,
    dist_to_liq: float,
    dist_to_sl: float,
    dist_to_tp: float,
    fr: float,
    trailing_active: bool,
    leverage: int,
    hold_hours: float = 0,
    tp_price: float = 0,  # v1.3: ATR 计算的止盈价
    sl_price: float = 0,  # v1.3: ATR 计算的止损价（追踪后可能变化）
    webhook: str = DEFAULT_WEBHOOK,
):
    """
    发送结构化飞书卡片通知
    v1.3 新增字段：ATR(14)、动态 TP/SL 价格、ATR 倍数标注

    实盘卡片头部红色，模拟盘紫色。
    """
    profile_tag = "[DEMO]" if profile == "demo" else "[LIVE]"
    emoji_map = {
        "entry":    "[BUY]",
        "exit_tp":  "[TP HIT]",
        "exit_sl":  "[SL HIT]",
        "timeout":  "[TIMEOUT]",
        "trailing": "[TRAILING]",
        "scan":     "[SCAN]",
    }
    emoji = emoji_map.get(action, "[SCAN]")

    # RSI 颜色
    rsi_color, rsi_label = (
        ("green", "OVERSOLD") if rsi14 < 30
        else ("red", "OVERBOUGHT") if rsi14 > 70
        else ("grey", "NEUTRAL")
    )

    # 强平距离颜色
    liq_color, liq_label = (
        ("red",    "DANGER")  if dist_to_liq < 5
        else ("orange", "WARNING") if dist_to_liq < 10
        else ("green", "SAFE")
    )

    # 浮盈颜色
    pnl_color = "green" if pnl_pct >= 0 else "red"

    # ATR 波动率标签（相对价格 %）
    if atr14 > 0 and price > 0:
        atr_pct = atr14 / price * 100
        atr_label = (
            "HIGH" if atr_pct > 3
            else "MED" if atr_pct > 1.5
            else "LOW"
        )
        atr_color = (
            "orange" if atr_pct > 3
            else "grey" if atr_pct > 1.5
            else "green"
        )
    else:
        atr_pct, atr_label, atr_color = 0, "N/A", "grey"

    # 追踪状态
    trailing_label = "ACTIVE" if trailing_active else "inactive"
    trailing_color = "green" if trailing_active else "grey"

    # 模板颜色
    template_color = "purple" if profile == "demo" else "red"

    # TP/SL 倍数还原（用于显示）
    if atr14 > 0 and tp_price > 0:
        tp_atr = (tp_price - entry_price) / atr14
        sl_atr = (entry_price - sl_price) / atr14 if sl_price > 0 else 0
    else:
        tp_atr = sl_atr = 0

    # ATR 追踪状态：如果追踪激活，SL 变为成本价（标注 COST）
    sl_label = f"{sl_price:.4f} (COST)" if trailing_active else f"{sl_price:.4f}"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{emoji} {symbol} {profile_tag}"
                },
                "template": template_color
            },
            "elements": [
                # ── 第一行：价格 / 成本 / 浮盈 / 杠杆 ──────────────
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Price**\n{price:.4f} USDT"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Entry**\n{entry_price:.4f}"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**PnL**\n<font color='{pnl_color}'>{pnl_pct:+.2f}% ({pnl_usdt:+.4f} U)"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Lev**\n{leverage}x"}},
                    ]
                },
                {"tag": "hr"},

                # ── 第二行：RSI / 资金费率 / 强平距离 / ATR 波动率 ──
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**RSI(14)**\n<font color='{rsi_color}'>{rsi14:.1f} [{rsi_label}]"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Funding**\n{fr*100:+.4f}%/8h ({fr*3*100:+.4f}%/day)"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Liq Dist**\n<font color='{liq_color}'>{dist_to_liq:.2f}% [{liq_label}]"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**ATR Vol**\n<font color='{atr_color}'>{atr14:.4f} ({atr_label})"}},
                    ]
                },
                {"tag": "hr"},

                # ── 第三行：ATR 止盈 / ATR 止损 / 距 TP / 距 SL ──
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**ATR-TP**\n{tp_price:.4f} ({tp_atr:.1f}x)"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**ATR-SL**\n{sl_label} ({sl_atr:.1f}x)"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**To TP**\n{dist_to_tp:+.2f}%"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**To SL**\n{dist_to_sl:+.2f}%"}},
                    ]
                },
                {"tag": "hr"},

                # ── 第四行：追踪状态 / 持仓时长 ────────────────────
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Trailing SL**\n<font color='{trailing_color}'>{trailing_label}</font>"}},
                        {"is_short": True,  "text": {"tag": "lark_md",
                            "content": f"**Hold Time**\n{hold_hours:.1f}h"}},
                        {"is_short": False, "text": {"tag": "lark_md",
                            "content": f"**Method**\nATR Dynamic (Wilder Smooth, Period=14)"}},
                    ]
                },

                # ── 时间戳 ───────────────────────────────────────
                {
                    "tag": "note",
                    "elements": [{
                        "tag": "plain_text",
                        "content": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ATR v1.3"
                    }]
                }
            ]
        }
    }

    try:
        body = json.dumps(card).encode("utf-8")
        req = urllib.request.Request(webhook, data=body,
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        print(f"[Feishu] code={result.get('code',-1)} {result.get('msg','')}")
        return result
    except Exception as e:
        print(f"[Feishu] Send failed: {e}")
        return None


def send_scan_notification(symbols: list, signals: list,
                           webhook: str = DEFAULT_WEBHOOK):
    """
    发送多币种扫描结果卡片（v1.3：含 ATR）
    """
    rows = []
    for s in sorted(signals, key=lambda x: x["rsi14"]):
        atr = s.get("atr14", 0)
        tp_p = s.get("tp_pct", 0)
        sl_p = s.get("sl_pct", 0)
        rows.append(
            f"<font color='red'>{s['coin']}</font> "
            f"RSI={s['rsi14']:.1f} | "
            f"ATR={atr:.4f} | "
            f"TP=+{tp_p:.2f}% | SL=-{sl_p:.2f}% | "
            f"FR={s['fr']*100:+.4f}%/8h | "
            f"Vol={s['vol24h']:,.0f} U"
        )

    content = "\n".join(rows) or "No oversold signals (RSI < 30)"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"[SCAN] Multi-coin RSI+ATR Report ({len(signals)}/{len(symbols)} signals)"
                },
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"Scanning **{len(symbols)}** coins, **{len(signals)}** in oversold territory"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "note", "elements": [
                    {"tag": "plain_text",
                     "content": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ATR Dynamic v1.3"}
                ]}
            ]
        }
    }

    try:
        body = json.dumps(card).encode("utf-8")
        req = urllib.request.Request(webhook, data=body,
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        print(f"[Feishu] Scan: code={result.get('code',-1)}")
        return result
    except Exception as e:
        print(f"[Feishu] Send failed: {e}")
        return None


if __name__ == "__main__":
    # 单元测试（v1.3 含 ATR）
    send_trade_notification(
        action="scan",
        symbol="CRCL-USDT-SWAP",
        profile="live",
        price=86.05, entry_price=85.7673,
        rsi14=34.0, atr14=3.5,
        pnl_pct=0.33, pnl_usdt=0.033,
        dist_to_liq=14.2, dist_to_sl=4.3, dist_to_tp=5.6,
        fr=0.0003, trailing_active=False,
        leverage=5, hold_hours=0.5,
        tp_price=85.7673 + 2.0 * 3.5,    # Entry + 2.0 * ATR
        sl_price=85.7673 - 1.5 * 3.5,    # Entry - 1.5 * ATR
    )
