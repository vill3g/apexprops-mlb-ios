import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from backend.database.models import get_db_connection, is_manual_entry

logger = logging.getLogger(__name__)


def _trade_epoch(ts) -> float:
    """Trade timestamps are stored as epoch numbers, ISO strings or '... AM ET' strings."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str) and ts:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            if ts.endswith(" ET"):
                return datetime.strptime(ts, "%Y-%m-%d %I:%M:%S %p ET").replace(
                    tzinfo=ZoneInfo("America/New_York")).timestamp()
            d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=ZoneInfo("America/New_York"))
            return d.timestamp()
        except (ValueError, TypeError):
            try:
                return float(ts)
            except ValueError:
                pass
    return 0.0


def daily_limit_reason(user: dict, mode: str = None):
    """Why the bot must not open another trade today for this user, or None.
    A limit of 0 (or less) means no limit."""
    mode = mode or user.get("trading_mode", "PAPER")
    max_trades = int(float(user.get("max_daily_trades") or 0))
    max_risk = float(user.get("max_daily_risk") or 0)
    if max_trades <= 0 and max_risk <= 0:
        return None
    act = TradeStore.get_today_activity(user["id"], mode)
    if max_trades > 0 and act["entries"] >= max_trades:
        return f"Daily trade limit reached ({act['entries']}/{max_trades} today)"
    if max_risk > 0 and act["realized"] - act["open_cost"] <= -max_risk:
        return f"Daily risk limit reached (${-(act['realized'] - act['open_cost']):.2f} of ${max_risk:.2f})"
    return None

class TradeStore:
    @staticmethod
    def get_open_trades(user_id: int) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM trades WHERE user_id = ? AND status = 'OPEN' ORDER BY rowid DESC", (user_id,))
            return [json.loads(row[0]) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"TradeStore get_open_trades error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_recent_trades(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Sort by rowid (insertion order) — timestamp column stores mixed types
            # (ISO strings, ET strings, floats) that SQLite cannot sort reliably
            cursor.execute("SELECT raw_json FROM trades WHERE user_id = ? ORDER BY rowid DESC LIMIT ?", (user_id, limit))
            return [json.loads(row[0]) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"TradeStore get_recent_trades error: {e}")
            return []
        finally:
            conn.close()
            
    @staticmethod
    def get_closed_stats(user_id: int) -> Dict[str, Dict[str, float]]:
        """All-time closed-trade stats per mode, e.g.
        {"PAPER": {"closed": 12, "wins": 7, "losses": 5, "pnl": 3.2}, "LIVE": {...}}.
        Computed in SQL so totals are not limited to the most recent N trades."""
        empty = {"closed": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        stats = {"PAPER": dict(empty), "LIVE": dict(empty)}
        try:
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT UPPER(COALESCE(mode, 'PAPER')), COUNT(*), "
                "SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), "
                "COALESCE(SUM(pnl), 0) "
                "FROM trades WHERE user_id = ? AND status != 'OPEN' GROUP BY 1",
                (user_id,),
            ).fetchall()
            for mode, closed, wins, losses, pnl in rows:
                stats[mode] = {"closed": int(closed or 0), "wins": int(wins or 0),
                               "losses": int(losses or 0), "pnl": float(pnl or 0.0)}
        except Exception as e:
            logger.warning(f"TradeStore get_closed_stats error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
        return stats

    @staticmethod
    def get_strategy_performance(user_id: int) -> List[Dict[str, Any]]:
        """Returns strategy performance breakdown (total, wins, losses, win_rate, net_pnl, avg_pnl)
        for all closed trades of a user, ordered by net pnl descending."""
        stats = []
        try:
            conn = get_db_connection()
            rows = conn.execute(
                """
                SELECT 
                    UPPER(COALESCE(NULLIF(trading_style, ''), 'AUTO')) as style,
                    COUNT(*),
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END),
                    COALESCE(SUM(pnl), 0),
                    COALESCE(AVG(pnl), 0)
                FROM trades
                WHERE user_id = ? AND status != 'OPEN'
                GROUP BY 1
                ORDER BY 5 DESC, 2 DESC
                """,
                (user_id,)
            ).fetchall()
            for style, total, wins, losses, pnl, avg_pnl in rows:
                t = int(total or 0)
                w = int(wins or 0)
                l = int(losses or 0)
                wr = round(w / t * 100, 1) if t > 0 else 0.0
                stats.append({
                    "strategy": style,
                    "total_trades": t,
                    "wins": w,
                    "losses": l,
                    "win_rate": wr,
                    "net_pnl": round(float(pnl or 0.0), 2),
                    "avg_pnl": round(float(avg_pnl or 0.0), 2)
                })
        except Exception as e:
            logger.warning(f"TradeStore get_strategy_performance error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
        return stats

    @staticmethod
    def get_community_activity(limit: int = 25) -> List[Dict[str, Any]]:
        """Recent community trades across all active traders for the Battle Tape feed."""
        activity = []
        try:
            conn = get_db_connection()
            rows = conn.execute(
                """
                SELECT t.id, t.user_id, u.username, u.profile_pic, t.side, 
                       t.trading_style, t.pnl, t.status, t.mode, t.exit_reason,
                       t.timestamp, t.settled_at, t.entry_price, t.exit_price
                FROM trades t
                JOIN users u ON t.user_id = u.id
                WHERE t.status != 'OPEN' AND u.is_active = 1
                ORDER BY t.rowid DESC LIMIT ?
                """,
                (limit,)
            ).fetchall()
            for r in rows:
                tid, uid, uname, pic, side, style, pnl, status, mode, exit_r, ts, settled, entry_p, exit_p = r
                pnl_val = round(float(pnl or 0.0), 2)
                is_win = pnl_val > 0
                activity.append({
                    "trade_id": str(tid),
                    "user_id": uid,
                    "username": uname or "Trader",
                    "profile_pic": pic,
                    "side": side or "YES",
                    "trading_style": style or "AUTO",
                    "pnl": pnl_val,
                    "is_win": is_win,
                    "status": status,
                    "mode": mode or "PAPER",
                    "exit_reason": exit_r or "",
                    "timestamp": ts or settled or 0,
                    "entry_price": entry_p,
                    "exit_price": exit_p
                })
        except Exception as e:
            logger.warning(f"TradeStore get_community_activity error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
        return activity

    @staticmethod
    def get_equity_curve(user_id: int, limit: int = 150) -> Dict[str, Any]:
        """Calculates cumulative equity history, user vs bot breakdown, strategy matrix,
        and dynamic profit improvement recommendations."""
        points = []
        peak = 0.0
        drawdown = 0.0
        
        all_trades = []
        manual_trades = []
        bot_trades = []
        chart_points = []
        
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT pnl, side, trading_style, reason, exit_reason, signal_source,
                       entry_price, exit_price, mode, COALESCE(settled_at, timestamp, 0) as ts
                FROM trades
                WHERE user_id = ? AND status != 'OPEN'
                ORDER BY rowid ASC
                """,
                (user_id,)
            ).fetchall()
            
            cum_total = 0.0
            cum_manual = 0.0
            cum_bot = 0.0
            
            for row in rows:
                t = dict(row)
                val = float(t.get("pnl") or 0.0)
                is_man = is_manual_entry(t)
                
                cum_total += val
                if is_man:
                    cum_manual += val
                    manual_trades.append(t)
                else:
                    cum_bot += val
                    bot_trades.append(t)
                all_trades.append(t)
                
                if cum_total > peak:
                    peak = cum_total
                dd = peak - cum_total
                if dd > drawdown:
                    drawdown = dd
                    
                points.append({
                    "pnl": round(cum_total, 2),
                    "manual_pnl": round(cum_manual, 2),
                    "bot_pnl": round(cum_bot, 2),
                    "ts": t.get("ts", 0),
                    "is_manual": is_man
                })
                
            chart_points = points
            if len(points) > limit:
                step = len(points) / limit
                chart_points = [points[int(i * step)] for i in range(limit - 1)] + [points[-1]]
        except Exception as e:
            logger.warning(f"TradeStore get_equity_curve error: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

        def calc_stats(trades_list):
            if not trades_list:
                return {
                    "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                    "pnl": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 1.0,
                    "yes_count": 0, "yes_win_rate": 0.0, "no_count": 0, "no_win_rate": 0.0
                }
            wins = [t for t in trades_list if float(t.get("pnl") or 0) > 0]
            losses = [t for t in trades_list if float(t.get("pnl") or 0) < 0]
            net = sum(float(t.get("pnl") or 0) for t in trades_list)
            gross_win = sum(float(t.get("pnl") or 0) for t in wins)
            gross_loss = abs(sum(float(t.get("pnl") or 0) for t in losses))
            
            yes_trades = [t for t in trades_list if str(t.get("side") or "").upper() == "YES"]
            no_trades = [t for t in trades_list if str(t.get("side") or "").upper() == "NO"]
            yes_wins = sum(1 for t in yes_trades if float(t.get("pnl") or 0) > 0)
            no_wins = sum(1 for t in no_trades if float(t.get("pnl") or 0) > 0)
            
            pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 1.0)
            return {
                "total": len(trades_list),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(trades_list) * 100, 1),
                "pnl": round(net, 2),
                "avg_win": round(gross_win / len(wins), 2) if wins else 0.0,
                "avg_loss": round(gross_loss / len(losses), 2) if losses else 0.0,
                "profit_factor": round(pf, 2),
                "yes_count": len(yes_trades),
                "yes_win_rate": round(yes_wins / len(yes_trades) * 100, 1) if yes_trades else 0.0,
                "no_count": len(no_trades),
                "no_win_rate": round(no_wins / len(no_trades) * 100, 1) if no_trades else 0.0,
            }

        user_stats = calc_stats(manual_trades)
        bot_stats = calc_stats(bot_trades)

        # Style matrix for bot trades
        styles_map = {}
        for t in bot_trades:
            raw_s = str(t.get("trading_style") or "AUTO").upper().strip()
            clean_s = raw_s.replace("🤖", "").replace("🎯", "").replace("✂️", "").replace("🏄", "").replace("🪤", "").replace("🔮", "").strip()
            if not clean_s or clean_s == "?":
                clean_s = "AUTO"
            if clean_s not in styles_map:
                styles_map[clean_s] = []
            styles_map[clean_s].append(t)

        style_matrix = []
        for s_name, s_trades in styles_map.items():
            st = calc_stats(s_trades)
            style_matrix.append({
                "style": s_name,
                "total": st["total"],
                "wins": st["wins"],
                "win_rate": st["win_rate"],
                "pnl": st["pnl"],
                "avg_pnl": round(st["pnl"] / st["total"], 2) if st["total"] else 0.0
            })
        style_matrix.sort(key=lambda x: x["pnl"], reverse=True)

        # Generate Actionable Profit Improvement Recommendations
        recommendations = []
        
        worst_style = min(style_matrix, key=lambda x: x["pnl"]) if style_matrix else None
        best_style = max(style_matrix, key=lambda x: x["pnl"]) if style_matrix else None
        if worst_style and worst_style["pnl"] < -15.0 and worst_style["total"] >= 5:
            recommendations.append({
                "type": "danger",
                "icon": "⚠️",
                "title": f"Prune {worst_style['style']} Strategy",
                "badge": f"${worst_style['pnl']} Drag",
                "desc": f"The {worst_style['style']} strategy accounts for ${worst_style['pnl']} in losses across {worst_style['total']} executions ({worst_style['win_rate']}% WR). Deactivating {worst_style['style']} in settings will immediately prevent further portfolio drawdown.",
                "action": f"Switch to {best_style['style'] if best_style and best_style != worst_style else 'AUTO 2.0'}"
            })

        if user_stats["total"] >= 5 and user_stats["win_rate"] > bot_stats["win_rate"]:
            recommendations.append({
                "type": "success",
                "icon": "🎯",
                "title": "Capitalize on Discretionary Edge",
                "badge": f"{user_stats['win_rate']}% Win Rate",
                "desc": f"Your manual trading win rate ({user_stats['win_rate']}%, +${user_stats['pnl']}) significantly outpaces automated execution ({bot_stats['win_rate']}%, ${bot_stats['pnl']}). Use bot signals as setup alerts, but execute discretionary confirmations manually.",
                "action": "Favor Manual Entries"
            })
        elif bot_stats["total"] >= 10 and bot_stats["win_rate"] >= 55.0:
            recommendations.append({
                "type": "success",
                "icon": "🤖",
                "title": "Scale Winning Bot Strategies",
                "badge": f"{bot_stats['win_rate']}% Bot WR",
                "desc": f"The AI bot is operating at an above-average {bot_stats['win_rate']}% win rate with positive expectancy. Consider increasing automated position sizes incrementally.",
                "action": "Increase Auto Trade Size"
            })

        all_stats = calc_stats(all_trades)
        if all_stats["total"] >= 15:
            if all_stats["yes_win_rate"] - all_stats["no_win_rate"] >= 8.0:
                recommendations.append({
                    "type": "tip",
                    "icon": "📈",
                    "title": "Bullish Directional Asymmetry",
                    "badge": f"{all_stats['yes_win_rate']}% YES WR",
                    "desc": f"You win {all_stats['yes_win_rate']}% on YES positions vs {all_stats['no_win_rate']}% on NO positions. You possess a distinct bullish edge on Kalshi BTC contracts—tighten NO entry thresholds.",
                    "action": "Prioritize YES Setups"
                })
            elif all_stats["no_win_rate"] - all_stats["yes_win_rate"] >= 8.0:
                recommendations.append({
                    "type": "tip",
                    "icon": "📉",
                    "title": "Bearish Directional Asymmetry",
                    "badge": f"{all_stats['no_win_rate']}% NO WR",
                    "desc": f"You win {all_stats['no_win_rate']}% on NO positions vs {all_stats['yes_win_rate']}% on YES positions. Tighten criteria for YES entries and prioritize fade setups.",
                    "action": "Prioritize NO Setups"
                })

        if bot_stats["avg_loss"] > bot_stats["avg_win"] * 1.25 and bot_stats["total"] >= 10:
            recommendations.append({
                "type": "tip",
                "icon": "🛡️",
                "title": "Tighten Stop Loss Threshold",
                "badge": "Risk/Reward",
                "desc": f"Your average losing trade (-${bot_stats['avg_loss']}) is larger than your average winner (+${bot_stats['avg_win']}). Enabling a 40-50% Stop Loss or Trailing Stop caps asymmetric downside.",
                "action": "Enable Trailing Stop"
            })

        recommendations.append({
            "type": "info",
            "icon": "⚡",
            "title": "Fee Optimization & Edge Gate",
            "badge": "Save on Fees",
            "desc": "Kalshi exchange taker fees scale up near 50¢ contracts. Keep Edge Gate active with at least 1.5¢ expected edge to prevent fee drag on thin statistical edges.",
            "action": "Enable Edge Gate"
        })

        return {
            "points": chart_points,
            "current_pnl": points[-1]["pnl"] if points else 0.0,
            "peak_pnl": round(peak, 2),
            "max_drawdown": round(drawdown, 2),
            "total_trades": len(all_trades),
            "user_stats": user_stats,
            "bot_stats": bot_stats,
            "styles": style_matrix,
            "recommendations": recommendations
        }

    @staticmethod
    def get_user_quests_and_badges(user_id: int) -> Dict[str, Any]:
        """Calculates dynamic progressive daily quests, trader XP, and unlocked badges."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        today_start = datetime.now(et).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

        sniper_wins = 0
        big_wins = 0
        lifetime_big_wins = 0
        max_streak = 0
        current_streak = 0
        total_wins = 0
        today_wins = 0
        today_trades_count = 0
        today_current_streak = 0
        today_max_streak = 0
        today_net_pnl = 0.0

        try:
            conn = get_db_connection()
            rows = conn.execute(
                """
                SELECT trading_style, reason, pnl, entry_price, exit_price, count, COALESCE(settled_at, timestamp, 0)
                FROM trades
                WHERE user_id = ? AND status != 'OPEN'
                ORDER BY rowid ASC
                """,
                (user_id,)
            ).fetchall()

            for style, reason, pnl, entry_p, exit_p, count, ts in rows:
                p = float(pnl or 0.0)
                ep = float(entry_p or 0.0)
                xp_exit = float(exit_p or 0.0)
                c_cnt = int(count or 1)
                is_win = p > 0

                if is_win:
                    total_wins += 1
                    current_streak += 1
                    if current_streak > max_streak:
                        max_streak = current_streak
                elif p < 0:
                    current_streak = 0

                # Calculate ROI safely with zero division protection
                total_cost = ep * c_cnt if (ep > 0 and c_cnt > 0) else ep
                roi = (p / total_cost * 100.0) if total_cost > 0 else (((xp_exit - ep) / ep * 100.0) if ep > 0 else 0.0)
                
                is_big = is_win and (roi >= 30.0 or p >= 10.0 or (xp_exit > 0 and ep > 0 and (xp_exit - ep) / ep >= 0.30))
                if is_big:
                    lifetime_big_wins += 1

                epoch = _trade_epoch(ts)
                if epoch >= today_start:
                    today_trades_count += 1
                    today_net_pnl += p
                    if is_win:
                        today_wins += 1
                        today_current_streak += 1
                        if today_current_streak > today_max_streak:
                            today_max_streak = today_current_streak
                    elif p < 0:
                        today_current_streak = 0

                    is_sniper = "SNIPER" in str(style or "").upper() or "SNIPER" in str(reason or "").upper()
                    if is_win and is_sniper:
                        sniper_wins += 1
                    if is_big:
                        big_wins += 1

        except Exception as e:
            logger.warning(f"TradeStore get_user_quests error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

        today_streak = max(today_max_streak, today_current_streak)
        if current_streak >= 3 and today_wins > 0:
            today_streak = max(today_streak, min(current_streak, 10))

        # Progressive Quest Chains: automatically unlocks and generates the next tier when completed
        quest_chains = [
            {
                "category": "sniper",
                "icon": "🎯",
                "tiers": [
                    {"tier": 1, "title": "Sniper Specialist I", "desc": "Win 2 Sniper style trades today", "target": 2, "reward_xp": 50},
                    {"tier": 2, "title": "Sniper Veteran II", "desc": "Win 4 Sniper style trades today", "target": 4, "reward_xp": 75},
                    {"tier": 3, "title": "Sniper Elite III", "desc": "Win 7 Sniper style trades today", "target": 7, "reward_xp": 125},
                    {"tier": 4, "title": "Apex Marksman IV", "desc": "Win 10 Sniper style trades today", "target": 10, "reward_xp": 200},
                ],
                "metric": sniper_wins
            },
            {
                "category": "big_win",
                "icon": "🧊",
                "tiers": [
                    {"tier": 1, "title": "Cold Blooded I", "desc": "Lock in 1 trade at +30% ROI today", "target": 1, "reward_xp": 75},
                    {"tier": 2, "title": "Ice in the Veins II", "desc": "Lock in 3 trades at +30% ROI today", "target": 3, "reward_xp": 100},
                    {"tier": 3, "title": "Profit Monster III", "desc": "Lock in 6 trades at +30% ROI today", "target": 6, "reward_xp": 150},
                    {"tier": 4, "title": "Mega Scalper IV", "desc": "Lock in 10 trades at +30% ROI today", "target": 10, "reward_xp": 225},
                ],
                "metric": big_wins
            },
            {
                "category": "streak",
                "icon": "🎩",
                "tiers": [
                    {"tier": 1, "title": "Hat Trick I", "desc": "Achieve a 3-trade win streak today", "target": 3, "reward_xp": 100},
                    {"tier": 2, "title": "On Fire II", "desc": "Achieve a 5-trade win streak today", "target": 5, "reward_xp": 150},
                    {"tier": 3, "title": "Unstoppable III", "desc": "Achieve a 7-trade win streak today", "target": 7, "reward_xp": 250},
                    {"tier": 4, "title": "Legendary Run IV", "desc": "Achieve a 10-trade win streak today", "target": 10, "reward_xp": 400},
                ],
                "metric": today_streak
            },
            {
                "category": "activity",
                "icon": "⚡",
                "tiers": [
                    {"tier": 1, "title": "Active Trader I", "desc": "Execute 5 trades today", "target": 5, "reward_xp": 50},
                    {"tier": 2, "title": "Floor General II", "desc": "Execute 10 trades today", "target": 10, "reward_xp": 80},
                    {"tier": 3, "title": "Market Marathon III", "desc": "Execute 15 trades today", "target": 15, "reward_xp": 120},
                    {"tier": 4, "title": "Iron Trader IV", "desc": "Execute 20 trades today", "target": 20, "reward_xp": 180},
                ],
                "metric": today_trades_count
            },
            {
                "category": "profit",
                "icon": "💰",
                "tiers": [
                    {"tier": 1, "title": "In the Green I", "desc": "Achieve +$15 net profit today", "target": 15, "reward_xp": 60},
                    {"tier": 2, "title": "Bank Builder II", "desc": "Achieve +$30 net profit today", "target": 30, "reward_xp": 100},
                    {"tier": 3, "title": "Alpha Scalper III", "desc": "Achieve +$60 net profit today", "target": 60, "reward_xp": 160},
                    {"tier": 4, "title": "Apex Whale IV", "desc": "Achieve +$100 net profit today", "target": 100, "reward_xp": 250},
                ],
                "metric": max(0, int(today_net_pnl))
            }
        ]

        active_quests = []
        completed_quests = []
        total_quest_xp = 0

        for chain in quest_chains:
            metric = chain["metric"]
            icon = chain["icon"]
            tiers = chain["tiers"]
            
            for t in tiers:
                if metric >= t["target"]:
                    total_quest_xp += t["reward_xp"]
                    completed_quests.append({
                        "id": f"{chain['category']}_t{t['tier']}",
                        "title": t["title"],
                        "desc": t["desc"],
                        "icon": icon,
                        "current": t["target"],
                        "target": t["target"],
                        "completed": True,
                        "reward_xp": t["reward_xp"],
                        "tier": t["tier"]
                    })
                else:
                    # Brand new generated active quest for this category!
                    active_quests.append({
                        "id": f"{chain['category']}_t{t['tier']}",
                        "title": t["title"],
                        "desc": t["desc"],
                        "icon": icon,
                        "current": min(metric, t["target"]),
                        "target": t["target"],
                        "completed": False,
                        "reward_xp": t["reward_xp"],
                        "tier": t["tier"]
                    })
                    break

        # Display active quests first (fresh challenges to work on), followed by recently completed quests today
        display_quests = active_quests + completed_quests[-2:] if completed_quests else active_quests

        xp = (total_wins * 25) + total_quest_xp
        level = max(1, int(xp // 150) + 1)
        xp_current_level = xp % 150
        xp_next_level = 150

        badges = []
        if current_streak >= 3 or max_streak >= 3:
            badges.append({"id": "hot_streak", "name": "Hot Streak", "icon": "🔥", "desc": "Won 3+ trades in a row"})
        if total_wins >= 10:
            badges.append({"id": "sharpshooter", "name": "Sharpshooter", "icon": "🎯", "desc": "10+ lifetime wins"})
        if lifetime_big_wins >= 1 or big_wins >= 1:
            badges.append({"id": "cold_blooded", "name": "Cold Blooded", "icon": "🧊", "desc": "Locked in +30% profit trade"})
        if level >= 5:
            badges.append({"id": "apex_trader", "name": "Apex Predator", "icon": "👑", "desc": "Reached Level 5 Trader"})

        return {
            "level": level,
            "xp": xp,
            "xp_current_level": xp_current_level,
            "xp_next_level": xp_next_level,
            "streak": current_streak,
            "max_streak": max_streak,
            "today_streak": today_streak,
            "quests": display_quests,
            "badges": badges
        }


    @staticmethod
    def get_today_activity(user_id: int, mode: str) -> Dict[str, float]:
        """Trades OPENED today (US Eastern calendar day) in one mode, for daily limits:
        entries  = bot entries (manual entries and synced Kalshi positions excluded)
        realized = P&L of those trades that are already closed (all trades)
        open_cost = money still tied up in those that are open (all trades)"""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from backend.database.models import is_manual_entry
        et = ZoneInfo("America/New_York")
        day_start = datetime.now(et).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        out = {"entries": 0, "realized": 0.0, "open_cost": 0.0}
        try:
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT raw_json FROM trades WHERE user_id = ? AND UPPER(COALESCE(mode, 'PAPER')) = ? "
                "ORDER BY rowid DESC LIMIT 1000", (user_id, str(mode or "PAPER").upper())).fetchall()
        except Exception as e:
            logger.warning(f"TradeStore get_today_activity error: {e}")
            return out
        finally:
            if 'conn' in locals():
                conn.close()
        for (raw,) in rows:
            try:
                t = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if _trade_epoch(t.get("timestamp")) < day_start:
                continue
            if not is_manual_entry(t):
                out["entries"] += 1
            if t.get("status") == "OPEN":
                out["open_cost"] += float(t.get("entry_price") or 0) * float(t.get("count") or 0)
            else:
                out["realized"] += float(t.get("pnl") or 0)
        return out

    @staticmethod
    def get_trade_by_id(trade_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.warning(f"TradeStore get_trade_by_id error: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def insert_trade(user_id: int, trade: dict) -> str:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            trade_id = trade.get("id", "")
            
            # Initialize min_seen_bid for tracking max adverse excursion
            if "min_seen_bid" not in trade:
                trade["min_seen_bid"] = trade.get("entry_price")

            cursor.execute('''
                INSERT OR IGNORE INTO trades (
                    id, user_id, ticker, side, entry_price, exit_price, count, pnl,
                    status, mode, reason, exit_reason, trading_style, signal_source,
                    timestamp, settled_at, ml_reasoning, catalysts, raw_json, min_seen_bid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_id,
                user_id,
                trade.get("ticker"),
                trade.get("side"),
                trade.get("entry_price"),
                trade.get("exit_price"),
                trade.get("count"),
                trade.get("pnl"),
                trade.get("status", "OPEN"),
                trade.get("mode", "PAPER"),
                trade.get("reason"),
                trade.get("exit_reason"),
                trade.get("trading_style"),
                trade.get("signal_source"),
                trade.get("timestamp"),
                trade.get("settled_at"),
                trade.get("ml_reasoning"),
                json.dumps(trade.get("catalysts", [])),
                json.dumps(trade),
                trade.get("min_seen_bid")
            ))
            conn.commit()
            return trade_id
        except Exception as e:
            logger.warning(f"TradeStore insert_trade error: {e}")
            return ""
        finally:
            conn.close()

    @staticmethod
    def update_trade(trade_id: str, updates: dict, only_if_open: bool = False) -> bool:
        """Merge updates into a trade row. With only_if_open=True the write is
        skipped if the row is no longer OPEN (so a stale copy can never re-open
        a trade that was closed elsewhere)."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json, reason, trading_style, signal_source, user_id, status FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            trade = json.loads(row[0]) if row[0] else {}
            was_open = str(row[5] or trade.get("status") or "").upper() == "OPEN"
            orig_reason = trade.get("reason") or row[1]
            orig_style = trade.get("trading_style") or row[2]
            orig_source = trade.get("signal_source") or row[3]

            trade.update(updates)

            # If updates passed 'reason' as an exit reason (e.g. MANUAL_CLOSE, SETTLEMENT, STOP_LOSS), route to exit_reason
            r = str(updates.get("reason") or "")
            if any(k in r for k in ["CLOSE", "SETTLE", "STOP", "PROFIT", "TRAILING", "EXPIRE"]) and not updates.get("exit_reason"):
                trade["exit_reason"] = r
                if orig_reason and not any(k in str(orig_reason) for k in ["CLOSE", "SETTLE", "STOP", "PROFIT", "TRAILING", "EXPIRE"]):
                    trade["reason"] = orig_reason

            if orig_style and not updates.get("trading_style"):
                trade["trading_style"] = orig_style
            if orig_source and not updates.get("signal_source"):
                trade["signal_source"] = orig_source

            raw_json = json.dumps(trade)
            
            # Now update columns
            cursor.execute('''
                UPDATE trades SET 
                    exit_price = ?,
                    pnl = ?,
                    status = ?,
                    exit_reason = ?,
                    settled_at = ?,
                    raw_json = ?,
                    min_seen_bid = ?
                WHERE id = ?{guard}
            '''.format(guard=" AND status = 'OPEN'" if only_if_open else ""), (
                trade.get("exit_price"),
                trade.get("pnl"),
                trade.get("status"),
                trade.get("exit_reason"),
                trade.get("settled_at"),
                raw_json,
                trade.get("min_seen_bid"),
                trade_id
            ))
            changed = cursor.rowcount == 1
            conn.commit()
            # Push "Trade Won" once, on the OPEN -> closed transition (paper and live)
            if changed and was_open and str(trade.get("status") or "").upper() != "OPEN":
                try:
                    from backend.core.push_notifications import \
                        notify_trade_closed
                    notify_trade_closed(row[4], trade)
                except Exception as _pe:
                    logger.warning(f"TradeStore push notify error: {_pe}")
            return changed
        except Exception as e:
            logger.warning(f"TradeStore update_trade error: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def close_if_open(user_id: int, trade: dict, updates: dict) -> bool:
        """Atomically mark a trade CLOSED only if it is still OPEN.

        Returns True for exactly one caller per trade (across threads AND the
        separate web/worker processes, since the guard lives in SQLite), so the
        caller that gets True is the only one allowed to credit balances.
        If the row does not exist yet it is inserted already closed."""
        trade_id = trade.get("id")
        if not trade_id:
            return False
        if TradeStore.get_trade_by_id(trade_id) is None:
            # INSERT OR IGNORE as OPEN first so racing callers still meet the guard below
            opened = dict(trade)
            opened["status"] = "OPEN"
            TradeStore.insert_trade(user_id, opened)
        closed = dict(updates)
        closed["status"] = "CLOSED"
        return TradeStore.update_trade(trade_id, closed, only_if_open=True)

    @staticmethod
    def close_trade(trade_id: str, exit_price: float, pnl: float, reason: str, settled_at: float) -> bool:
        return TradeStore.update_trade(trade_id, {
            "exit_price": exit_price,
            "pnl": pnl,
            "status": "CLOSED",
            "exit_reason": reason,
            "settled_at": settled_at
        })
        
    @staticmethod
    def archive_old_trades(user_id: int, max_age_days: int = 30) -> int:
        # We can just keep them in SQLite, it scales better than JSON.
        # But if we want, we can DELETE FROM trades WHERE ...
        return 0
