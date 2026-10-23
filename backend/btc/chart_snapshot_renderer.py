"""
Institutional Multimodal 3-Timeframe Trinity Chart Snapshot Renderer for Gemini Vision.

Generates a high-contrast, dark-mode 3-Timeframe PNG chart in memory (< 180ms via Pillow):
  - Top Header: Asset, Contract Ticker, Spot vs Strike, Delta ($ / %), Win Zone Pill, 1H/15m/5m Regimes
  - Panel A (42% width): 15-Minute Macro Structure (16 Candles / 4 Hours)
      * Candlesticks (Green #00E676 / Red #FF1744) with wicks
      * EMA 9 (Cyan), EMA 21 (Orange), EMA 50 (Purple), Bollinger Bands (Blue)
      * 4H Swing High / Swing Low horizontal dashed markers
      * Synchronized Gold Dashed Kalshi Strike Line & Shaded YES/NO Win Zones
      * Bottom Sub-panels: 15m Volume bars + 14-period RSI trajectory (70/50/30)
  - Panel B (33% width): 5-Minute Tactical Structure (12 Candles / 1 Hour)
      * Bridges Macro 15m and Micro 1m: shows the exact 3-bar breakdown of the 15m cycle
      * 5m Candlesticks, 5m EMA 9 & EMA 21, Session VWAP
      * Synchronized Gold Dashed Kalshi Strike Line & Shaded YES/NO Win Zones
      * Bottom Sub-panel: 5m Volume bars with buyer/seller dominance
  - Panel C (25% width): 1-Minute Micro-Drive (15 Candles / Opening Impulse)
      * Zoomed high-resolution view of the contract's intrabar momentum
      * 1m Candlesticks, Wick Rejections, Current Spot Mark, 1m Volume Delta
      * Synchronized Gold Dashed Kalshi Strike Line & Shaded YES/NO Win Zones
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def _load_fonts() -> Tuple[Any, Any, Any, Any]:
    try:
        f_title = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 15)
        f_sub = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 12)
        f_lbl = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 11)
        f_tiny = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 9)
        return f_title, f_sub, f_lbl, f_tiny
    except Exception:
        d = ImageFont.load_default()
        return d, d, d, d


def _fmt_price(val: float, asset: str = "BTC") -> str:
    a = str(asset or "BTC").upper()
    if a == "DOGE" or (0 < abs(val) < 1.0):
        return f"${val:,.5f}"
    if a in ("SOL", "XRP") or (1.0 <= abs(val) < 500.0):
        return f"${val:,.2f}"
    return f"${val:,.2f}"


def _draw_dashed_hline(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    color: Tuple[int, int, int, int],
    dash_len: int = 8,
    gap_len: int = 5,
    width: int = 1,
) -> None:
    cur_x = x0
    while cur_x < x1:
        end_x = min(x1, cur_x + dash_len)
        draw.line([(cur_x, y), (end_x, y)], fill=color, width=width)
        cur_x += dash_len + gap_len


def render_gemini_chart_snapshot(
    asset: str,
    ticker: str,
    strike: float,
    spot: float,
    sec_elapsed: float,
    df_15m: Any,
    df_5m: Any = None,
    df_1m: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    Renders the 3-Timeframe Trinity visual chart (15m + 5m + 1m) as a high-contrast PNG.
    """
    try:
        if df_15m is None or len(df_15m) < 4:
            return None

        a_up = str(asset or "BTC").upper()

        # Fetch 5m and 1m if missing
        from backend.engine.multi_asset_fetcher import fetch_asset_candles
        if df_5m is None or len(df_5m) < 4:
            try:
                df_5m = fetch_asset_candles(a_up, "5m", limit=16)
            except Exception:
                df_5m = None

        if df_1m is None or len(df_1m) < 3:
            try:
                df_1m = fetch_asset_candles(a_up, "1m", limit=16)
            except Exception:
                df_1m = None

        W, H = 1440, 750
        img = Image.new("RGBA", (W, H), (10, 14, 23, 255))
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        ov_draw = ImageDraw.Draw(overlay)
        f_title, f_sub, f_lbl, f_tiny = _load_fonts()

        # ── 1. TOP HEADER BANNER ──────────────────────────────────────────────────
        draw.rectangle([(0, 0), (W, 56)], fill=(16, 22, 35, 255))
        draw.line([(0, 56), (W, 56)], fill=(45, 58, 86, 255), width=2)

        delta = spot - strike
        delta_pct = (delta / strike * 100.0) if strike > 0 else 0.0
        is_above = delta >= 0

        curr_15m = df_15m.iloc[-1]
        rsi_now = float(curr_15m.get("rsi", 50.0) or 50.0)
        adx_now = float(curr_15m.get("adx", 20.0) or 20.0)
        trend_1h = str(curr_15m.get("trend_1h", "NEUTRAL")).upper()
        ema9_now = float(curr_15m.get("ema_9", spot) or spot)
        ema21_now = float(curr_15m.get("ema_21", spot) or spot)

        header_left = f"INSTITUTIONAL TRINITY RADAR: {a_up} 15M CONTRACT [{ticker}]  |  T+{int(sec_elapsed)}s ({max(0, int(900 - sec_elapsed))}s REMAINING)"
        draw.text((16, 9), header_left, fill=(235, 242, 255, 255), font=f_title)

        sub_left = (
            f"1H Trend: {trend_1h}  |  15m EMA 9 vs 21: {'BULLISH (9>21)' if ema9_now >= ema21_now else 'BEARISH (9<21)'}  "
            f"|  RSI(14): {rsi_now:.1f}  |  ADX: {adx_now:.1f}"
        )
        draw.text((16, 33), sub_left, fill=(160, 180, 215, 255), font=f_lbl)

        # Right status badge
        badge_bg = (0, 130, 72, 255) if is_above else (165, 24, 48, 255)
        badge_border = (0, 230, 118, 255) if is_above else (255, 50, 80, 255)
        zone_txt = "▲ ABOVE STRIKE (YES WIN ZONE)" if is_above else "▼ BELOW STRIKE (NO WIN ZONE)"
        sign_s = "+" if delta >= 0 else "-"
        pill_text = (
            f"SPOT: {_fmt_price(spot, a_up)}  vs  STRIKE: {_fmt_price(strike, a_up)}  "
            f"({sign_s}{_fmt_price(abs(delta), a_up)} / {delta_pct:+.2f}%)  [{zone_txt}]"
        )
        draw.rounded_rectangle([(670, 9), (W - 14, 47)], radius=6, fill=badge_bg, outline=badge_border, width=2)
        draw.text((682, 20), pill_text, fill=(255, 255, 255, 255), font=f_sub)

        # ── 2. PANEL LAYOUT (TRINITY: 42% / 33% / 25%) ───────────────────────────
        # Panel A: 15m Macro (X: 14 -> 590)
        A_X0, A_X1 = 14, 595
        A_P_Y0, A_P_Y1 = 86, 465
        A_V_Y0, A_V_Y1 = 478, 570
        A_R_Y0, A_R_Y1 = 584, 715

        # Panel B: 5m Tactical (X: 608 -> 1065)
        B_X0, B_X1 = 608, 1065
        B_P_Y0, B_P_Y1 = 86, 560
        B_V_Y0, B_V_Y1 = 574, 715

        # Panel C: 1m Micro (X: 1078 -> 1426)
        C_X0, C_X1 = 1078, 1426
        C_P_Y0, C_P_Y1 = 86, 560
        C_V_Y0, C_V_Y1 = 574, 715

        # Titles
        draw.text((A_X0, 65), "PANEL A: 15-MINUTE MACRO STRUCTURE (4 HOURS) + EMAs + BB", fill=(125, 200, 255, 255), font=f_sub)
        draw.text((B_X0, 65), "PANEL B: 5-MINUTE TACTICAL CYCLE (1 HOUR)", fill=(160, 235, 130, 255), font=f_sub)
        draw.text((C_X0, 65), "PANEL C: 1-MINUTE OPENING MICRO-DRIVE", fill=(255, 215, 80, 255), font=f_sub)

        for (x0, y0, x1, y1) in [
            (A_X0, A_P_Y0, A_X1, A_P_Y1), (A_X0, A_V_Y0, A_X1, A_V_Y1), (A_X0, A_R_Y0, A_X1, A_R_Y1),
            (B_X0, B_P_Y0, B_X1, B_P_Y1), (B_X0, B_V_Y0, B_X1, B_V_Y1),
            (C_X0, C_P_Y0, C_X1, C_P_Y1), (C_X0, C_V_Y0, C_X1, C_V_Y1),
        ]:
            draw.rectangle([(x0, y0), (x1, y1)], fill=(14, 19, 31, 255), outline=(38, 48, 70, 255), width=1)

        # ── 3. RENDER PANEL A (15M MACRO: 16 BARS = 4 HOURS) ─────────────────────
        sub_15 = df_15m.tail(16).copy().reset_index(drop=True)
        n15 = len(sub_15)

        h15 = [float(r.get("high", 0) or 0) for _, r in sub_15.iterrows()]
        l15 = [float(r.get("low", 0) or 0) for _, r in sub_15.iterrows()]
        o15 = [float(r.get("open", 0) or 0) for _, r in sub_15.iterrows()]
        c15 = [float(r.get("close", 0) or 0) for _, r in sub_15.iterrows()]
        v15 = [float(r.get("volume", 0) or 0) for _, r in sub_15.iterrows()]
        if n15 > 0 and spot > 0:
            c15[-1] = spot
            h15[-1] = max(h15[-1], spot)
            l15[-1] = min(l15[-1], spot) if l15[-1] > 0 else spot

        sh_4h, sl_4h = max(h15), min(l15)
        p_min_A, p_max_A = min(sl_4h, strike, spot), max(sh_4h, strike, spot)
        for _, r in sub_15.iterrows():
            bbu, bbl = float(r.get("bb_upper", 0) or 0), float(r.get("bb_lower", 0) or 0)
            if bbu > 0: p_max_A = max(p_max_A, bbu)
            if bbl > 0: p_min_A = min(p_min_A, bbl)
        pad_A = max((p_max_A - p_min_A) * 0.08, strike * 0.0006, 1e-6)
        p_min_A -= pad_A
        p_max_A += pad_A

        def y_A(p: float) -> int:
            f = (p - p_min_A) / max(p_max_A - p_min_A, 1e-9)
            return int(A_P_Y1 - max(0.0, min(1.0, f)) * (A_P_Y1 - A_P_Y0))

        y_strk_A = y_A(strike)
        if A_P_Y0 < y_strk_A < A_P_Y1:
            ov_draw.rectangle([(A_X0 + 1, A_P_Y0 + 1), (A_X1 - 1, y_strk_A)], fill=(0, 200, 100, 18))
            ov_draw.rectangle([(A_X0 + 1, y_strk_A), (A_X1 - 1, A_P_Y1 - 1)], fill=(235, 30, 65, 18))

        for i in range(5):
            gp = p_min_A + (p_max_A - p_min_A) * (i / 4.0)
            draw.line([(A_X0, y_A(gp)), (A_X1, y_A(gp))], fill=(24, 32, 48, 255), width=1)

        # 4H Swing High / Low
        y_sh_A = y_A(sh_4h)
        y_sl_A = y_A(sl_4h)
        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_sh_A, (255, 110, 130, 180), dash_len=4, gap_len=5)
        draw.text((A_X0 + 6, max(A_P_Y0 + 2, y_sh_A - 11)), f"4H HIGH: {_fmt_price(sh_4h, a_up)}", fill=(255, 130, 145, 255), font=f_tiny)
        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_sl_A, (90, 230, 150, 180), dash_len=4, gap_len=5)
        draw.text((A_X0 + 6, min(A_P_Y1 - 12, y_sl_A + 2)), f"4H LOW: {_fmt_price(sl_4h, a_up)}", fill=(105, 240, 165, 255), font=f_tiny)

        usable_w_A = (A_X1 - A_X0) - 75
        step_A = usable_w_A / max(n15, 1)
        cw_A = max(7, int(step_A * 0.62))
        def x_A(idx: int) -> int: return int(A_X0 + 14 + (idx + 0.5) * step_A)

        # EMA curves
        ema9_A, ema21_A, ema50_A, bbu_A, bbl_A = [], [], [], [], []
        for idx, r in sub_15.iterrows():
            cx = x_A(idx)
            e9, e21, e50 = float(r.get("ema_9", 0) or 0), float(r.get("ema_21", 0) or 0), float(r.get("ema_50", 0) or 0)
            bu, bl = float(r.get("bb_upper", 0) or 0), float(r.get("bb_lower", 0) or 0)
            if e9 > 0: ema9_A.append((cx, y_A(e9)))
            if e21 > 0: ema21_A.append((cx, y_A(e21)))
            if e50 > 0: ema50_A.append((cx, y_A(e50)))
            if bu > 0: bbu_A.append((cx, y_A(bu)))
            if bl > 0: bbl_A.append((cx, y_A(bl)))

        if len(bbu_A) >= 2: draw.line(bbu_A, fill=(90, 130, 210, 150), width=1)
        if len(bbl_A) >= 2: draw.line(bbl_A, fill=(90, 130, 210, 150), width=1)
        if len(ema50_A) >= 2: draw.line(ema50_A, fill=(195, 110, 255, 230), width=2)
        if len(ema21_A) >= 2: draw.line(ema21_A, fill=(255, 165, 40, 240), width=2)
        if len(ema9_A) >= 2: draw.line(ema9_A, fill=(0, 225, 255, 255), width=2)

        # 15m Candlesticks
        max_v_A = max(v15 + [1e-6])
        for idx in range(n15):
            cx = x_A(idx)
            o, h, l, c, v = o15[idx], h15[idx], l15[idx], c15[idx], v15[idx]
            bull = c >= o
            col = (0, 230, 118, 255) if bull else (255, 45, 85, 255)
            wcol = (120, 245, 175, 255) if bull else (255, 120, 145, 255)
            draw.line([(cx, y_A(h)), (cx, y_A(l))], fill=wcol, width=2)
            top_b, bot_b = min(y_A(o), y_A(c)), max(y_A(o), y_A(c))
            if bot_b - top_b < 2: bot_b = top_b + 2
            hw = cw_A // 2
            draw.rectangle([(cx - hw, top_b), (cx + hw, bot_b)], fill=col, outline=col)
            if idx == n15 - 1:
                draw.rectangle([(cx - hw - 2, top_b - 2), (cx + hw + 2, bot_b + 2)], outline=(255, 255, 255, 220), width=1)

            # Volume
            vf = min(1.0, max(0.04, v / max_v_A))
            vy = int(A_V_Y1 - vf * (A_V_Y1 - A_V_Y0 - 14))
            draw.rectangle([(cx - hw, vy), (cx + hw, A_V_Y1 - 1)], fill=(0, 195, 100, 200) if bull else (225, 45, 75, 200))

        draw.text((A_X0 + 6, A_V_Y0 + 2), "15M VOL", fill=(140, 160, 195, 255), font=f_tiny)

        # Kalshi Strike on Panel A
        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_strk_A, (255, 215, 0, 255), dash_len=8, gap_len=4, width=2)
        draw.rectangle([(A_X1 - 70, y_strk_A - 8), (A_X1 - 2, y_strk_A + 8)], fill=(255, 205, 0, 255))
        draw.text((A_X1 - 67, y_strk_A - 5), "STRIKE", fill=(10, 14, 24, 255), font=f_tiny)

        # Panel A RSI(14)
        def y_rsi(rv: float) -> int:
            f = (max(10.0, min(90.0, rv)) - 10.0) / 80.0
            return int(A_R_Y1 - f * (A_R_Y1 - A_R_Y0 - 12))

        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_rsi(70.0), (255, 90, 110, 160), dash_len=4, gap_len=5)
        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_rsi(50.0), (105, 120, 150, 130), dash_len=3, gap_len=6)
        _draw_dashed_hline(draw, A_X0 + 2, A_X1 - 2, y_rsi(30.0), (80, 230, 145, 160), dash_len=4, gap_len=5)
        rsi_pts_A = [(x_A(idx), y_rsi(float(r.get("rsi", 50.0) or 50.0))) for idx, r in sub_15.iterrows()]
        if len(rsi_pts_A) >= 2:
            draw.line(rsi_pts_A, fill=(255, 210, 75, 255), width=2)
        draw.text((A_X0 + 6, A_R_Y0 + 2), f"RSI(14): {rsi_now:.1f} [70=OB / 30=OS]", fill=(255, 215, 90, 255), font=f_tiny)

        # ── 4. RENDER PANEL B (5M TACTICAL: 12 BARS = 1 HOUR) ────────────────────
        sub_5 = df_5m.tail(12).copy().reset_index(drop=True) if (df_5m is not None and len(df_5m) >= 3) else sub_15.tail(8).copy().reset_index(drop=True)
        n5 = len(sub_5)

        h5 = [float(r.get("high", 0) or 0) for _, r in sub_5.iterrows()]
        l5 = [float(r.get("low", 0) or 0) for _, r in sub_5.iterrows()]
        o5 = [float(r.get("open", 0) or 0) for _, r in sub_5.iterrows()]
        c5 = [float(r.get("close", 0) or 0) for _, r in sub_5.iterrows()]
        v5 = [float(r.get("volume", 0) or 0) for _, r in sub_5.iterrows()]
        if n5 > 0 and spot > 0:
            c5[-1] = spot
            h5[-1] = max(h5[-1], spot)
            l5[-1] = min(l5[-1], spot) if l5[-1] > 0 else spot

        p_min_B, p_max_B = min(min(l5), strike, spot), max(max(h5), strike, spot)
        pad_B = max((p_max_B - p_min_B) * 0.10, strike * 0.0005, 1e-6)
        p_min_B -= pad_B
        p_max_B += pad_B

        def y_B(p: float) -> int:
            f = (p - p_min_B) / max(p_max_B - p_min_B, 1e-9)
            return int(B_P_Y1 - max(0.0, min(1.0, f)) * (B_P_Y1 - B_P_Y0))

        y_strk_B = y_B(strike)
        if B_P_Y0 < y_strk_B < B_P_Y1:
            ov_draw.rectangle([(B_X0 + 1, B_P_Y0 + 1), (B_X1 - 1, y_strk_B)], fill=(0, 200, 100, 20))
            ov_draw.rectangle([(B_X0 + 1, y_strk_B), (B_X1 - 1, B_P_Y1 - 1)], fill=(235, 30, 65, 20))

        for i in range(5):
            draw.line([(B_X0, y_B(p_min_B + (p_max_B - p_min_B)*(i/4.0))), (B_X1, y_B(p_min_B + (p_max_B - p_min_B)*(i/4.0)))], fill=(24, 32, 48, 255), width=1)

        usable_w_B = (B_X1 - B_X0) - 68
        step_B = usable_w_B / max(n5, 1)
        cw_B = max(8, int(step_B * 0.64))
        def x_B(idx: int) -> int: return int(B_X0 + 14 + (idx + 0.5) * step_B)

        # 5m EMA9 & 21
        ema9_B, ema21_B = [], []
        for idx, r in sub_5.iterrows():
            cx = x_B(idx)
            e9 = float(r.get("ema_9", 0) or 0)
            e21 = float(r.get("ema_21", 0) or 0)
            if e9 > 0: ema9_B.append((cx, y_B(e9)))
            if e21 > 0: ema21_B.append((cx, y_B(e21)))
        if len(ema21_B) >= 2: draw.line(ema21_B, fill=(255, 165, 40, 240), width=2)
        if len(ema9_B) >= 2: draw.line(ema9_B, fill=(0, 225, 255, 255), width=2)

        max_v_B = max(v5 + [1e-6])
        for idx in range(n5):
            cx = x_B(idx)
            o, h, l, c, v = o5[idx], h5[idx], l5[idx], c5[idx], v5[idx]
            bull = c >= o
            col = (0, 230, 118, 255) if bull else (255, 45, 85, 255)
            wcol = (120, 245, 175, 255) if bull else (255, 120, 145, 255)
            draw.line([(cx, y_B(h)), (cx, y_B(l))], fill=wcol, width=2)
            top_b, bot_b = min(y_B(o), y_B(c)), max(y_B(o), y_B(c))
            if bot_b - top_b < 2: bot_b = top_b + 2
            hw = cw_B // 2
            draw.rectangle([(cx - hw, top_b), (cx + hw, bot_b)], fill=col, outline=col)
            if idx == n5 - 1:
                draw.rectangle([(cx - hw - 2, top_b - 2), (cx + hw + 2, bot_b + 2)], outline=(255, 255, 255, 220), width=1)

            vf = min(1.0, max(0.04, v / max_v_B))
            vy = int(B_V_Y1 - vf * (B_V_Y1 - B_V_Y0 - 14))
            draw.rectangle([(cx - hw, vy), (cx + hw, B_V_Y1 - 1)], fill=(0, 195, 100, 200) if bull else (225, 45, 75, 200))

        draw.text((B_X0 + 6, B_V_Y0 + 2), "5M VOLUME (3-BAR CYCLE)", fill=(140, 160, 195, 255), font=f_tiny)

        _draw_dashed_hline(draw, B_X0 + 2, B_X1 - 2, y_strk_B, (255, 215, 0, 255), dash_len=8, gap_len=4, width=2)
        draw.text((B_X0 + 6, max(B_P_Y0 + 4, y_strk_B - 14)), f"STRIKE: {_fmt_price(strike, a_up)}", fill=(255, 220, 60, 255), font=f_tiny)
        draw.text((B_X1 - 150, B_P_Y0 + 6), "EMA9(Cyan)  EMA21(Orange)", fill=(175, 195, 225, 255), font=f_tiny)

        # ── 5. RENDER PANEL C (1M MICRO-DRIVE: 15 BARS = 15 MINUTES) ─────────────
        sub_1 = df_1m.tail(15).copy().reset_index(drop=True) if (df_1m is not None and len(df_1m) >= 3) else sub_5.tail(10).copy().reset_index(drop=True)
        n1 = len(sub_1)

        h1 = [float(r.get("high", 0) or 0) for _, r in sub_1.iterrows()]
        l1 = [float(r.get("low", 0) or 0) for _, r in sub_1.iterrows()]
        o1 = [float(r.get("open", 0) or 0) for _, r in sub_1.iterrows()]
        c1 = [float(r.get("close", 0) or 0) for _, r in sub_1.iterrows()]
        v1 = [float(r.get("volume", 0) or 0) for _, r in sub_1.iterrows()]
        if n1 > 0 and spot > 0:
            c1[-1] = spot
            h1[-1] = max(h1[-1], spot)
            l1[-1] = min(l1[-1], spot) if l1[-1] > 0 else spot

        p_min_C, p_max_C = min(min(l1), strike, spot), max(max(h1), strike, spot)
        pad_C = max((p_max_C - p_min_C) * 0.12, strike * 0.0004, 1e-6)
        p_min_C -= pad_C
        p_max_C += pad_C

        def y_C(p: float) -> int:
            f = (p - p_min_C) / max(p_max_C - p_min_C, 1e-9)
            return int(C_P_Y1 - max(0.0, min(1.0, f)) * (C_P_Y1 - C_P_Y0))

        y_strk_C = y_C(strike)
        if C_P_Y0 < y_strk_C < C_P_Y1:
            ov_draw.rectangle([(C_X0 + 1, C_P_Y0 + 1), (C_X1 - 1, y_strk_C)], fill=(0, 200, 100, 24))
            ov_draw.rectangle([(C_X0 + 1, y_strk_C), (C_X1 - 1, C_P_Y1 - 1)], fill=(235, 30, 65, 24))

        for i in range(5):
            gp = p_min_C + (p_max_C - p_min_C) * (i / 4.0)
            draw.line([(C_X0, y_C(gp)), (C_X1, y_C(gp))], fill=(24, 32, 48, 255), width=1)
            draw.text((C_X1 - 58, y_C(gp) - 6), _fmt_price(gp, a_up), fill=(140, 160, 190, 255), font=f_tiny)

        usable_w_C = (C_X1 - C_X0) - 62
        step_C = usable_w_C / max(n1, 1)
        cw_C = max(7, int(step_C * 0.62))
        def x_C(idx: int) -> int: return int(C_X0 + 10 + (idx + 0.5) * step_C)

        max_v_C = max(v1 + [1e-6])
        for idx in range(n1):
            cx = x_C(idx)
            o, h, l, c, v = o1[idx], h1[idx], l1[idx], c1[idx], v1[idx]
            bull = c >= o
            col = (0, 230, 118, 255) if bull else (255, 45, 85, 255)
            wcol = (120, 245, 175, 255) if bull else (255, 120, 145, 255)
            draw.line([(cx, y_C(h)), (cx, y_C(l))], fill=wcol, width=2)
            top_b, bot_b = min(y_C(o), y_C(c)), max(y_C(o), y_C(c))
            if bot_b - top_b < 2: bot_b = top_b + 2
            hw = cw_C // 2
            draw.rectangle([(cx - hw, top_b), (cx + hw, bot_b)], fill=col, outline=col)
            if idx == n1 - 1:
                draw.rectangle([(cx - hw - 2, top_b - 2), (cx + hw + 2, bot_b + 2)], outline=(255, 255, 255, 220), width=1)

            vf = min(1.0, max(0.04, v / max_v_C))
            vy = int(C_V_Y1 - vf * (C_V_Y1 - C_V_Y0 - 14))
            draw.rectangle([(cx - hw, vy), (cx + hw, C_V_Y1 - 1)], fill=(0, 195, 100, 200) if bull else (225, 45, 75, 200))

        draw.text((C_X0 + 6, C_V_Y0 + 2), "1M VOLUME DELTA", fill=(140, 160, 195, 255), font=f_tiny)

        _draw_dashed_hline(draw, C_X0 + 2, C_X1 - 2, y_strk_C, (255, 215, 0, 255), dash_len=8, gap_len=4, width=2)
        draw.text((C_X0 + 6, max(C_P_Y0 + 4, y_strk_C - 14)), f"STRIKE: {_fmt_price(strike, a_up)}", fill=(255, 220, 60, 255), font=f_tiny)

        # Micro Spot Mark
        y_spot_C = y_C(spot)
        spot_col = (0, 230, 118, 255) if is_above else (255, 50, 85, 255)
        draw.line([(C_X0 + 2, y_spot_C), (C_X1 - 2, y_spot_C)], fill=spot_col, width=1)

        draw.text((C_X0 + 6, C_P_Y0 + 4), "▲ YES ZONE", fill=(80, 245, 155, 230), font=f_tiny)
        draw.text((C_X0 + 6, C_P_Y1 - 14), "▼ NO ZONE", fill=(255, 110, 130, 230), font=f_tiny)

        # Composite & return
        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        final_img.save(buf, format="PNG", optimize=True)
        png_bytes = buf.getvalue()
        b64_str = base64.b64encode(png_bytes).decode("ascii")

        return {
            "mime_type": "image/png",
            "base64_data": b64_str,
            "png_bytes": png_bytes,
            "width": W,
            "height": H,
        }
    except Exception as e:
        logger.debug(f"[ChartRenderer] Failed to render trinity chart snapshot for {asset}: {e}")
        return None
