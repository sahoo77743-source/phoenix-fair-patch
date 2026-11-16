#!/usr/bin/env python3
"""No market-close at entry. $0.25 stop only if it is at least 3 ticks away.
A forced loss close blocks that symbol for 45 minutes."""
import os
import shutil
import py_compile

TARGET = "main.py"
BACKUP = "main.py.bak_fair"

SL_NEW = """            # ===== Exchange SL: $0.25 only when the coin can hold it =====
            wide_dist = stop_dist * 1.05
            sl_dist = wide_dist
            cut_usd = float(getattr(config, "LOSS_CUT_USD", 0.25))
            tick = 0.0
            try:
                tick = float((await get_symbol_precision(symbol)).get("tick_size") or 0)
            except Exception:
                tick = 0.0
            if qty > 0 and cut_usd > 0:
                dollar_dist = cut_usd / float(qty)
                if tick <= 0 or dollar_dist >= tick * 3.0:
                    sl_dist = min(wide_dist, dollar_dist)
                else:
                    logger.info(
                        f"📏 $0.25 under 3 ticks {symbol} | dollar={dollar_dist:.8g} tick={tick:.8g} → wide stop"
                    )
            emergency_sl_price = await adjust_price(
                entry_price - sl_dist if side == "BUY" else entry_price + sl_dist, symbol
            )
            on_loss_side = (
                (side == "BUY" and float(emergency_sl_price) < float(entry_price))
                or (side == "SELL" and float(emergency_sl_price) > float(entry_price))
            )
            if not on_loss_side:
                sl_dist = wide_dist
                emergency_sl_price = await adjust_price(
                    entry_price - sl_dist if side == "BUY" else entry_price + sl_dist, symbol
                )
                logger.info(f"📏 rounded stop sat on entry {symbol} → wide stop @ {emergency_sl_price}")
            logger.info(f"📏 Exchange SL {symbol} | ${cut_usd:.2f} cap | dist={sl_dist:.8g} wide={wide_dist:.8g}")

            await cancel_existing_exit_orders(symbol)
            sl_order = None
            for attempt in range(2):
                try:
                    sl_order = await safe_place_order(
                        symbol,
                        "SELL" if side == "BUY" else "BUY",
                        "STOP_MARKET",
                        stopPrice=emergency_sl_price,
                        closePosition=True
                    )
                    if sl_order:
                        break
                except Exception as e:
                    logger.warning(f"SL attempt {attempt+1} failed {symbol}: {e}")
                await cancel_existing_exit_orders(symbol)
            if not sl_order and sl_dist + 1e-12 < wide_dist:
                emergency_sl_price = await adjust_price(
                    entry_price - wide_dist if side == "BUY" else entry_price + wide_dist, symbol
                )
                logger.info(f"📏 tight stop rejected {symbol} → wide stop @ {emergency_sl_price}")
                try:
                    sl_order = await safe_place_order(
                        symbol,
                        "SELL" if side == "BUY" else "BUY",
                        "STOP_MARKET",
                        stopPrice=emergency_sl_price,
                        closePosition=True
                    )
                except Exception as e:
                    logger.warning(f"Wide SL failed {symbol}: {e}")
"""

SL_NOW = """            # ===== Immediate Emergency SL: $0.25 cap, no wait =====
            wide_dist = stop_dist * 1.05
            sl_dist = wide_dist
            cut_usd = float(getattr(config, "LOSS_CUT_USD", 0.25))
            if qty > 0 and cut_usd > 0:
                sl_dist = min(wide_dist, cut_usd / qty)
            emergency_sl_price = await adjust_price(
                entry_price - sl_dist if side == "BUY" else entry_price + sl_dist, symbol
            )
            logger.info(f"📏 Exchange SL {symbol} | ${cut_usd:.2f} cap | dist={sl_dist:.8g} wide={wide_dist:.8g}")

            async def _cap_already_crossed() -> bool:
                try:
                    last_px = float((await client.futures_ticker(symbol=symbol))["lastPrice"])
                except Exception:
                    return False
                if last_px <= 0:
                    return False
                stop_px = float(emergency_sl_price)
                if side == "BUY":
                    return last_px <= stop_px
                return last_px >= stop_px

            async def _close_cap_now(why: str) -> None:
                logger.critical(f"🚨 {why} {symbol} → market close")
                live_qty_check = await get_current_position_qty(symbol)
                if live_qty_check > 0.0001:
                    await safe_place_order(
                        symbol, "SELL" if side == "BUY" else "BUY", "MARKET",
                        quantity=live_qty_check, reduceOnly=True,
                    )
                active_trades[strategy_name].pop(symbol, None)
                occupied_symbols[symbol] = {"strategy": "FORCE_CLOSED", "side": None, "ts": now_utc()}
                await send_telegram(f"🚨 ${cut_usd:.2f} already lost on {symbol} → market close")

            if await _cap_already_crossed():
                await _close_cap_now("stop already crossed before send")
                return False

            await cancel_existing_exit_orders(symbol)
            sl_order = None
            for attempt in range(2):
                try:
                    sl_order = await safe_place_order(
                        symbol,
                        "SELL" if side == "BUY" else "BUY",
                        "STOP_MARKET",
                        stopPrice=emergency_sl_price,
                        closePosition=True
                    )
                    if sl_order:
                        break
                except Exception as e:
                    logger.warning(f"SL attempt {attempt+1} failed {symbol}: {e}")
                if await _cap_already_crossed():
                    await _close_cap_now("stop rejected, price already through $ cap")
                    return False
                await cancel_existing_exit_orders(symbol)
"""

SL_TRUTH = """            # ===== Immediate Emergency SL: $0.25 cap, no wait =====
            wide_dist = stop_dist * 1.05
            sl_dist = wide_dist
            cut_usd = float(getattr(config, "LOSS_CUT_USD", 0.25))
            tick = 0.0
            try:
                tick = float((await get_symbol_precision(symbol)).get("tick_size") or 0)
            except Exception:
                tick = 0.0
            if qty > 0 and cut_usd > 0:
                dollar_dist = cut_usd / float(qty)
                if tick <= 0 or dollar_dist >= tick:
                    sl_dist = min(wide_dist, dollar_dist)
                else:
                    logger.info(
                        f"📏 $0.25 inside one tick {symbol} | dollar={dollar_dist:.8g} tick={tick:.8g} → wide stop"
                    )
            emergency_sl_price = await adjust_price(
                entry_price - sl_dist if side == "BUY" else entry_price + sl_dist, symbol
            )
            on_loss_side = (
                (side == "BUY" and float(emergency_sl_price) < float(entry_price))
                or (side == "SELL" and float(emergency_sl_price) > float(entry_price))
            )
            if not on_loss_side:
                sl_dist = wide_dist
                emergency_sl_price = await adjust_price(
                    entry_price - sl_dist if side == "BUY" else entry_price + sl_dist, symbol
                )
                logger.info(f"📏 rounded stop sat on entry {symbol} → wide stop @ {emergency_sl_price}")
            logger.info(f"📏 Exchange SL {symbol} | ${cut_usd:.2f} cap | dist={sl_dist:.8g} wide={wide_dist:.8g}")

            async def _cap_already_crossed() -> bool:
                # Close only when the exchange itself shows an open loss of $0.25.
                # A last-price touch is not enough: a rounded stop can sit on the entry.
                try:
                    rows = await client.futures_position_information(symbol=symbol)
                except Exception:
                    return False
                for row in rows or []:
                    if row.get("symbol") != symbol:
                        continue
                    if abs(float(row.get("positionAmt") or 0)) <= 0.0001:
                        continue
                    try:
                        upnl = float(row.get("unRealizedProfit") or 0)
                    except Exception:
                        return False
                    return upnl <= -float(cut_usd)
                return False

            async def _close_cap_now(why: str) -> None:
                logger.critical(f"🚨 {why} {symbol} → market close")
                live_qty_check = await get_current_position_qty(symbol)
                if live_qty_check > 0.0001:
                    await safe_place_order(
                        symbol, "SELL" if side == "BUY" else "BUY", "MARKET",
                        quantity=live_qty_check, reduceOnly=True,
                    )
                active_trades[strategy_name].pop(symbol, None)
                occupied_symbols[symbol] = {"strategy": "FORCE_CLOSED", "side": None, "ts": now_utc()}
                await send_telegram(f"🚨 ${cut_usd:.2f} already lost on {symbol} → market close")

            if await _cap_already_crossed():
                await _close_cap_now("stop already crossed before send")
                return False

            await cancel_existing_exit_orders(symbol)
            sl_order = None
            for attempt in range(2):
                try:
                    sl_order = await safe_place_order(
                        symbol,
                        "SELL" if side == "BUY" else "BUY",
                        "STOP_MARKET",
                        stopPrice=emergency_sl_price,
                        closePosition=True
                    )
                    if sl_order:
                        break
                except Exception as e:
                    logger.warning(f"SL attempt {attempt+1} failed {symbol}: {e}")
                if await _cap_already_crossed():
                    await _close_cap_now("stop rejected, price already through $ cap")
                    return False
                await cancel_existing_exit_orders(symbol)
"""

REPLACEMENTS = [
(
"""SYMBOL_REENTRY_COOLDOWN_SEC = 5400       # 90 min after a clean close — no same-symbol chase
""",
"""SYMBOL_REENTRY_COOLDOWN_SEC = 5400       # 90 min after a clean close — no same-symbol chase
LOSS_REENTRY_SEC = 2700                     # 45 min after a forced loss close
"""
),
(
"""            if occ.get("strategy") == "CLOSED" and age < SYMBOL_REENTRY_COOLDOWN_SEC:
                continue
""",
"""            if occ.get("strategy") == "CLOSED" and age < SYMBOL_REENTRY_COOLDOWN_SEC:
                continue
            if occ.get("strategy") == "FORCE_CLOSED" and age < LOSS_REENTRY_SEC:
                continue
"""
),
(
"""                elif occ.get("strategy") == "FORCE_CLOSED":
                    block_sec = 180
""",
"""                elif occ.get("strategy") == "FORCE_CLOSED":
                    block_sec = LOSS_REENTRY_SEC
"""
),
(
"""                block_sec = 180 if occ.get("strategy") == "FORCE_CLOSED" else SYMBOL_ENTRY_COOLDOWN_SEC
""",
"""                block_sec = LOSS_REENTRY_SEC if occ.get("strategy") == "FORCE_CLOSED" else SYMBOL_ENTRY_COOLDOWN_SEC
"""
),
]


def main():
    if not os.path.exists(TARGET):
        print(f"STOPPED missing {TARGET}")
        return
    shutil.copy2(TARGET, BACKUP)
    text = open(TARGET, encoding="utf-8").read()
    now_n = text.count(SL_NOW)
    truth_n = text.count(SL_TRUTH)
    if now_n + truth_n != 1:
        shutil.copy2(BACKUP, TARGET)
        print(f"STOPPED stop-block now={now_n} truth={truth_n}")
        print(f"restored from {BACKUP} — bot file was not changed")
        return
    text = text.replace(SL_TRUTH if truth_n == 1 else SL_NOW, SL_NEW, 1)
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        n = text.count(old)
        if n != 1:
            shutil.copy2(BACKUP, TARGET)
            print(f"STOPPED piece {i} count={n}")
            print(f"restored from {BACKUP} — bot file was not changed")
            return
        text = text.replace(old, new, 1)
    if "_close_cap_now(" in text:
        shutil.copy2(BACKUP, TARGET)
        print("STOPPED instant-close text still present")
        print(f"restored from {BACKUP} — bot file was not changed")
        return
    open(TARGET, "w", encoding="utf-8").write(text)
    try:
        py_compile.compile(TARGET, doraise=True)
    except Exception as e:
        shutil.copy2(BACKUP, TARGET)
        print(f"STOPPED compile: {e}")
        print(f"restored from {BACKUP} — bot file was not changed")
        return
    print("DONE pieces=5")
    print(f"backup={BACKUP}")


if __name__ == "__main__":
    main()
