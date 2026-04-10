"""
feishu_notify.py — 飞书通知模块
用法：
  from feishu_notify import send_trade_notification, send_scan_notification
"""
import urllib.request, json
from datetime import datetime

# 唯一正确 webhook（2026-04-03 用户确认）
DEFAULT_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/b2aefdfe-a15d-481a-885b-5b5bb91d4be4"


def send_trade_notification(
    action: str,       # "entry" | "exit_tp" | "exit_sl" | "timeout" | "trailing"
    symbol: str,
    profile: str,       # "demo" | "live"
    price: float,
    entry_price: float,
    rsi14: float,
    pnl_pct: float,
    pnl_usdt: float,
    dist_to_liq: float,
    dist_to_sl: float,
    dist_to_tp: float,
    fr: float,
    trailing_active: bool,
    leverage: int,
    hold_hours: float = 0,
    webhook: str = DEFAULT_WEBHOOK,
):
    """
    发送结构化飞书卡片通知（含 RSI、强平价、资金费率、浮盈/浮亏、追踪止损状态）
    实盘卡片头部红色，模拟盘紫色。
    """
    profile_tag = "[DEMO]" if profile == "demo" else "[LIVE]"
    emoji_map = {
        "entry":    "[BUY]",
        "exit_tp":  "[TP]",
        "exit_sl":  "[SL]",
        "timeout":  "[TIMEOUT]",
        "trailing": "[TRAILING]",
    }
    emoji = emoji_map.get(action, "[SCAN]")

    rsi_color, rsi_label = (
        ("green", "OVERSOLD") if rsi14 < 30
        else ("red", "OVERBOUGHT") if rsi14 > 70
        else ("grey", "NEUTRAL")
    )
    liq_color, liq_label = (
        ("red", "DANGER") if dist_to_liq < 5
        else ("orange", "WARNING") if dist_to_liq < 10
        else ("green", "SAFE")
    )
    pnl_color = "green" if pnl_pct >= 0 else "red"
    template_color = "purple" if profile == "demo" else "red"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"{emoji} {symbol} {profile_tag}"},
                "template": template_color
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Price**\n{price:.4f} USDT"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Entry**\n{entry_price:.4f}"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**PnL**\n<font color='{pnl_color}'>{pnl_pct:+.2f}% ({pnl_usdt:+.4f} USDT)"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Leverage**\n{leverage}x"}},
                    ]
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**RSI(14)**\n<font color='{rsi_color}'>{rsi14:.1f} [{rsi_label}]"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Funding**\n{fr*100:+.4f}%/8h (daily:{fr*3*100:+.4f}%)"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Liq Dist**\n<font color='{liq_color}'>{dist_to_liq:.2f}% [{liq_label}]"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Trailing SL**\n{'ACTIVE' if trailing_active else 'inactive'}"}},
                    ]
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**To TP**\n{dist_to_tp:.2f}%"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**To SL**\n{dist_to_sl:.2f}%"}},
                        {"is_short": True, "text": {"tag": "lark_md",
                            "content": f"**Hold**\n{hold_hours:.1f}h"}},
                    ]
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text",
                                  "content": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}]
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


def send_scan_notification(symbols: list, signals: list, webhook: str = DEFAULT_WEBHOOK):
    """发送多币种扫描结果"""
    rows = "\n".join(
        f"<font color='red'>{s['coin']}</font> RSI={s['rsi14']:.1f} "
        f"Price={s['price']:.4f} FR={s['fr']*100:+.4f}%/8h"
        for s in sorted(signals, key=lambda x: x["rsi14"])
    ) or "No oversold signals (RSI < 30)"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"[SCAN] Multi-coin RSI Report ({len(signals)}/{len(symbols)} signals)"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"Scanning {len(symbols)} coins, {len(signals)} in oversold territory"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": rows}},
                {"tag": "note", "elements": [
                    {"tag": "plain_text",
                     "content": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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
    # 单元测试
    send_trade_notification(
        action="entry",
        symbol="CRCL-USDT-SWAP",
        profile="live",
        price=85.79, entry_price=85.7673,
        rsi14=25.1,
        pnl_pct=0.03, pnl_usdt=0.003,
        dist_to_liq=14.0, dist_to_sl=4.18, dist_to_tp=5.80,
        fr=0.0003, trailing_active=False,
        leverage=5, hold_hours=0.0,
    )
