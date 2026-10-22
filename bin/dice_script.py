# ==============================================================================
# DICEBOT MULTI-MODE STRATEGY SCRIPT (Gambler.Bot 5.35 / IronPython Compatible)
# Architecture: Single Source of Truth (SSOT) + Live CSV Stream Engine
# stake_api_key=522fe34470a71f0662cfc2ec39b887f54e34459125cdc8ed646b366f7a997635d9a75e03b162df944ceaa9cc644be544
# ==============================================================================

import os
import re
import csv
import math

# ==============================================================================
# [1] SSOT CONFIG LOADER & CSV LOGGER
# ==============================================================================
_base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
ENV_FILE_CANDIDATES = [
    os.path.join(_base_dir, "..", "simulator", "config", "dice.env"),
    os.path.join(_base_dir, "simulator", "config", "dice.env"),
    os.path.join(_base_dir, "config", "dice.env"),
    r"c:\Users\User\Desktop\dicebot5.35\simulator\config\dice.env",
]

_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?\}|\$(\w+)")

def load_dice_env():
    """โหลด configuration จาก dice.env ตามมาตรฐาน SSOT"""
    cfg = {}
    found_path = None
    for p in ENV_FILE_CANDIDATES:
        norm_p = os.path.normpath(p)
        if os.path.isfile(norm_p):
            found_path = norm_p
            break

    if found_path and os.path.isfile(found_path):
        try:
            with open(found_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.split("#", 1)[0].strip().strip("\"'")
                        cfg[k.strip()] = v
        except Exception:
            pass

    for _ in range(3):
        changed = False
        for k in list(cfg):
            v = cfg[k]
            new_v = _ENV_REF_RE.sub(
                lambda m: cfg.get(m.group(1) or m.group(2), ""),
                v
            )
            if new_v != v:
                cfg[k] = new_v
                changed = True
        if not changed:
            break

    return cfg, found_path


def _get_csv_path():
    """หา path สำหรับเขียน logs/dice_session_latest.csv"""
    candidates = [
        os.path.join(_base_dir, "..", "simulator", "logs"),
        os.path.join(_base_dir, "simulator", "logs"),
        os.path.join(_base_dir, "logs"),
        r"c:\Users\User\Desktop\dicebot5.35\simulator\logs",
    ]
    for d in candidates:
        norm_d = os.path.normpath(d)
        if os.path.isdir(norm_d):
            return os.path.join(norm_d, "dice_session_latest.csv")
    
    fallback = os.path.join(os.getcwd(), "dice_session_latest.csv")
    return fallback


# ==============================================================================
# [2] INTERNAL STATE VARIABLES
# ==============================================================================
_session_start_balance = 0.0
_profit_vault = 0.0
_current_hybrid_mode = "WAGER"
_hybrid_trigger_balance = 0.0
_hybrid_trigger_profit = 0.0

_loss_streak = 0
_win_streak = 0
_total_bets = 0
_total_wagered = 0.0
_max_loss_streak = 0

_active_game_mode = 5
_active_house_edge = 1.0
_active_hunt_rare = True

_p_base_bet = 0.00001
_p_win_chance = 3.96
_p_target_high = True
_p_stop_target = 0.0
_p_max_loss = 0

_w_base_bet = 0.0001
_w_win_chance = 98.0
_w_target_high = True
_w_stop_volume = 0.0

_h_loss_trigger_pct = 2.0
_h_profit_trigger_pct = 1.0

_c_base_bet = 0.00001
_c_win_chance = 3.96
_c_target_high = True
_c_loss_mul = 1.06
_c_loss_mul_every = 1
_c_loss_reset_first = 0
_c_loss_chg_bet_streak = 0
_c_loss_chg_bet_val = 0.0
_c_loss_chg_chance_streak = 0
_c_loss_chg_chance_val = 0.0
_c_win_mul = 1.0
_c_win_reset_base = 1
_c_rst_after_bets = 0
_c_rst_loss_streak = 0
_c_rst_win_streak = 1
_c_min_bet = 0.0
_c_max_bet = 0.0
_c_zigzag_every = 0
_c_stop_loss_streak = 0
_c_stop_profit = 0.0
_c_stop_max_bets = 0

_c_current_chance = 3.96
_c_current_target = True
_c_zigzag_counter = 0
_c_loss_since_mul = 0

_b_losses_allowed = 50
_b_loss_mul = 1.06
_b_win_chance = 3.96
_b_target_high = True
_b_stop_profit = 0.0
_b_win_reset_base = 1

_csv_file_path = None


# ==============================================================================
# [3] HELPER FUNCTIONS
# ==============================================================================
def _calc_payout(chance_pct, house_edge):
    if chance_pct <= 0:
        return 0.0
    return (1.0 - (house_edge / 100.0)) / (chance_pct / 100.0)

def _calc_martingale_multiplier(chance_pct, house_edge):
    payout = _calc_payout(chance_pct, house_edge)
    if payout > 1.0:
        return 1.0 + (1.0 / (payout - 1.0)) + (0.05 / payout)
    return 2.0

def _solve_brave_base_bet(bal, n_losses, mul):
    if n_losses <= 0:
        return 0.00000001
    if mul == 1.0:
        return float(bal) / float(n_losses)
    try:
        denom = math.pow(mul, n_losses) - 1.0
        if denom <= 0:
            return 0.00000001
        return (float(bal) * (mul - 1.0)) / denom
    except Exception:
        return 0.00000001

def _check_rare_roll(roll_val):
    if roll_val in (9999, 0): return "9900x"
    if roll_val in (9998, 1): return "4950x"
    if roll_val in (9997, 2): return "3300x"
    if roll_val in (9996, 3): return "2475x"
    if roll_val in (9995, 4): return "1980x"
    if roll_val in (9994, 5): return "1650x"
    if roll_val in (9993, 6): return "1414x"
    if roll_val in (9992, 7): return "1237x"
    if roll_val in (9991, 8): return "1100x"
    if roll_val in (9990, 9): return "990x"
    return None

def _log_round_to_csv(round_n, mode_name, roll_val, res_str, bet_amt, pnl_amt, net_pnl, bal_amt, streak, rare_tag, won_amt):
    """บันทึกบิลเข้า CSV เพื่อให้ Live Terminal HUD และ Web Lab อ่านได้แบบ Real-Time"""
    global _csv_file_path
    if not _csv_file_path:
        return
    try:
        with open(_csv_file_path, "a", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                round_n, mode_name, int(roll_val), res_str,
                "{0:.8f}".format(bet_amt),
                "{0:.8f}".format(pnl_amt),
                "{0:.8f}".format(net_pnl),
                "{0:.8f}".format(bal_amt),
                streak,
                rare_tag or "",
                "{0:.8f}".format(won_amt)
            ])
    except Exception:
        pass


# ==============================================================================
# [4] DICEBOT CALLBACK: Reset()
# ==============================================================================
def Reset():
    global _session_start_balance, _profit_vault, _current_hybrid_mode
    global _hybrid_trigger_balance, _hybrid_trigger_profit
    global _loss_streak, _win_streak, _total_bets, _total_wagered
    global _max_loss_streak, _active_game_mode, _active_house_edge, _active_hunt_rare
    global _p_base_bet, _p_win_chance, _p_target_high, _p_stop_target, _p_max_loss
    global _w_base_bet, _w_win_chance, _w_target_high, _w_stop_volume
    global _h_loss_trigger_pct, _h_profit_trigger_pct
    global _c_base_bet, _c_win_chance, _c_target_high, _c_loss_mul, _c_loss_mul_every
    global _c_loss_reset_first, _c_loss_chg_bet_streak, _c_loss_chg_bet_val
    global _c_loss_chg_chance_streak, _c_loss_chg_chance_val, _c_win_mul, _c_win_reset_base
    global _c_rst_after_bets, _c_rst_loss_streak, _c_rst_win_streak, _c_min_bet, _c_max_bet
    global _c_zigzag_every, _c_stop_loss_streak, _c_stop_profit, _c_stop_max_bets
    global _c_current_chance, _c_current_target, _c_zigzag_counter, _c_loss_since_mul
    global _b_losses_allowed, _b_loss_mul, _b_win_chance, _b_target_high, _b_stop_profit, _b_win_reset_base
    global _csv_file_path

    env_cfg, env_path = load_dice_env()

    def get_val(key, default, cast_type=str):
        if key in env_cfg and env_cfg[key] != "":
            try:
                return cast_type(env_cfg[key])
            except (ValueError, TypeError):
                pass
        return default

    _active_game_mode = get_val("GAME_MODE", 4, int)
    _active_house_edge = get_val("HE", 1.0, float)
    _active_hunt_rare = bool(get_val("HUNT_RARE", 0, int))
    g_base_bet = get_val("GLOBAL_BASE_BET", 0.01487629, float)
    g_win_chance = get_val("GLOBAL_WIN_CHANCE", 3.96, float)
    g_bet_target = str(get_val("GLOBAL_BET_TARGET", "high")).strip().lower() == "high"

    round_delay = get_val("GLOBAL_ROUND_DELAY", 0.0, float)
    if round_delay > 0:
        NextBet.BetDelay = round_delay

    _session_start_balance = float(Balance)
    _profit_vault = 0.0
    _loss_streak = 0
    _win_streak = 0
    _total_bets = 0
    _total_wagered = 0.0
    _max_loss_streak = 0

    _p_base_bet = get_val("PROFIT_BASE_BET", g_base_bet, float)
    _p_win_chance = get_val("PROFIT_WIN_CHANCE", g_win_chance, float)
    _p_target_high = str(get_val("PROFIT_BET_TARGET", "high")).strip().lower() == "high"
    _p_stop_target = get_val("PROFIT_STOP_TARGET", get_val("GLOBAL_STOP_PROFIT", 0.0, float), float)
    _p_max_loss = get_val("PROFIT_MAX_LOSS_STREAK", 0, int)

    _w_win_chance = get_val("WAGER_WIN_CHANCE", 98.0, float)
    wager_pct = get_val("WAGER_BET_PCT", 2.5, float)
    _w_base_bet = get_val("WAGER_BASE_BET", (wager_pct / 100.0) * _session_start_balance, float)
    _w_target_high = str(get_val("WAGER_BET_TARGET", "high")).strip().lower() == "high"
    _w_stop_volume = get_val("WAGER_TARGET", 1000.0, float)

    _h_loss_trigger_pct = get_val("HYBRID_LOSS_TRIGGER", 2.0, float)
    _h_profit_trigger_pct = get_val("HYBRID_PROFIT_TRIGGER", 1.0, float)
    _hybrid_trigger_balance = (1.0 - (_h_loss_trigger_pct / 100.0)) * _session_start_balance
    _hybrid_trigger_profit = _session_start_balance * (1.0 + (_h_profit_trigger_pct / 100.0))
    _current_hybrid_mode = "WAGER"

    _c_base_bet = get_val("CUSTOM_BASE_BET", g_base_bet, float)
    _c_win_chance = get_val("CUSTOM_WIN_CHANCE", g_win_chance, float)
    _c_target_high = str(get_val("CUSTOM_BET_TARGET", "high")).strip().lower() == "high"
    _c_loss_mul = get_val("CUSTOM_LOSS_MUL", 1.06, float)
    _c_loss_mul_every = get_val("CUSTOM_LOSS_MUL_EVERY", 1, int)
    _c_loss_reset_first = get_val("CUSTOM_LOSS_RESET_FIRST", 0, int)
    _c_loss_chg_bet_streak = get_val("CUSTOM_LOSS_CHANGE_BET_STREAK", 0, int)
    _c_loss_chg_bet_val = get_val("CUSTOM_LOSS_CHANGE_BET_VALUE", 0.0, float)
    _c_loss_chg_chance_streak = get_val("CUSTOM_LOSS_CHANGE_CHANCE_STREAK", 0, int)
    _c_loss_chg_chance_val = get_val("CUSTOM_LOSS_CHANGE_CHANCE_VALUE", 0.0, float)
    _c_win_mul = get_val("CUSTOM_WIN_MUL", 1.0, float)
    _c_win_reset_base = get_val("CUSTOM_WIN_RESET_BASE", 1, int)
    _c_rst_after_bets = get_val("CUSTOM_RESET_AFTER_BETS", 0, int)
    _c_rst_loss_streak = get_val("CUSTOM_RESET_ON_LOSS_STREAK", 0, int)
    _c_rst_win_streak = get_val("CUSTOM_RESET_ON_WIN_STREAK", 1, int)
    _c_min_bet = get_val("CUSTOM_MIN_BET", 0.0, float)
    _c_max_bet = get_val("CUSTOM_MAX_BET", 0.0, float)
    _c_zigzag_every = get_val("CUSTOM_ZIGZAG_EVERY", 0, int)
    _c_stop_loss_streak = get_val("CUSTOM_STOP_ON_LOSS_STREAK", 0, int)
    _c_stop_profit = get_val("CUSTOM_STOP_ON_WIN_VALUE_TOTAL", get_val("GLOBAL_STOP_PROFIT", 0.0, float), float)
    _c_stop_max_bets = get_val("CUSTOM_STOP_AFTER_BETS", 0, int)

    _c_current_chance = _c_win_chance
    _c_current_target = _c_target_high
    _c_zigzag_counter = 0
    _c_loss_since_mul = 0

    _b_losses_allowed = get_val("BRAVE_LOSSES_ALLOWED", 50, int)
    _b_loss_mul = get_val("BRAVE_LOSS_MUL", 1.06, float)
    _b_win_chance = get_val("BRAVE_WIN_CHANCE", g_win_chance, float)
    _b_target_high = str(get_val("BRAVE_BET_TARGET", "high")).strip().lower() == "high"
    _b_stop_profit = get_val("BRAVE_STOP_PROFIT", 500.0, float)
    _b_win_reset_base = get_val("BRAVE_WIN_RESET_BASE", 1, int)

    # เตรียมไฟล์ CSV
    _csv_file_path = _get_csv_path()
    try:
        csv_dir = os.path.dirname(_csv_file_path)
        if not os.path.exists(csv_dir):
            os.makedirs(csv_dir)
        with open(_csv_file_path, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Round", "Mode", "Roll", "Result", "Bet", "RoundPnL", "NetPnL",
                "Balance", "LossStreak", "RareHit", "WonAmount"
            ])
    except Exception:
        pass

    Print("==========================================================================")
    Print("  DICEBOT SIMULATOR ENGINE (SSOT: {0})".format(os.path.basename(env_path or "defaults")))
    Print("  Live Monitor Path: {0}".format(_csv_file_path))
    Print("==========================================================================")

    if _active_game_mode == 1:
        NextBet.Amount = _p_base_bet
        NextBet.Chance = _p_win_chance
        NextBet.High = _p_target_high
        Print("[MODE 1: PROFIT] BaseBet: {0:.8f} | Chance: {1:.2f}%".format(_p_base_bet, _p_win_chance))
    elif _active_game_mode == 2:
        NextBet.Amount = _w_base_bet
        NextBet.Chance = _w_win_chance
        NextBet.High = _w_target_high
        Print("[MODE 2: WAGER] FlatBet: {0:.8f} | Chance: {1:.2f}%".format(_w_base_bet, _w_win_chance))
    elif _active_game_mode == 3:
        NextBet.Amount = _w_base_bet
        NextBet.Chance = _w_win_chance
        NextBet.High = _w_target_high
        Print("[MODE 3: HYBRID] Normal: Wager | Dip Trigger: {0:.8f}".format(_hybrid_trigger_balance))
    elif _active_game_mode == 4:
        NextBet.Amount = _c_base_bet
        NextBet.Chance = _c_win_chance
        NextBet.High = _c_target_high
        Print("[MODE 4: CUSTOM] BaseBet: {0:.8f} | Chance: {1:.2f}% | Mul: {2:.2f}x".format(
            _c_base_bet, _c_win_chance, _c_loss_mul
        ))
    else:
        solved_base = _solve_brave_base_bet(_session_start_balance, _b_losses_allowed, _b_loss_mul)
        NextBet.Amount = solved_base
        NextBet.Chance = _b_win_chance
        NextBet.High = _b_target_high
        Print("[MODE 5: BRAVE] N={0} Losses | Solved Base: {1:.8f} | Mul: {2:.4f}x".format(
            _b_losses_allowed, solved_base, _b_loss_mul
        ))


# ==============================================================================
# [5] DICEBOT CALLBACK: CalculateBet()
# ==============================================================================
def CalculateBet():
    global _session_start_balance, _profit_vault, _current_hybrid_mode
    global _hybrid_trigger_balance, _hybrid_trigger_profit
    global _loss_streak, _win_streak, _total_bets, _total_wagered, _max_loss_streak
    global _c_current_chance, _c_current_target, _c_zigzag_counter, _c_loss_since_mul

    _total_bets += 1
    current_bet_amt = float(PreviousBet.TotalAmount)
    _total_wagered += current_bet_amt
    roll_result = float(PreviousBet.Roll)
    won_amount = float(PreviousBet.Profit) if Win else 0.0
    round_pnl = float(PreviousBet.Profit)
    net_pnl = float(CurrentProfit)
    cur_bal = float(Balance)

    if Win:
        _win_streak += 1
        _loss_streak = 0
    else:
        _loss_streak += 1
        _win_streak = 0
        if _loss_streak > _max_loss_streak:
            _max_loss_streak = _loss_streak

    rare_tag = None
    if _active_hunt_rare and Win:
        rare_tag = _check_rare_roll(int(roll_result))

    mode_name = "BRAVE" if _active_game_mode == 5 else ("CUSTOM" if _active_game_mode == 4 else ("HYBRID" if _active_game_mode == 3 else ("WAGER" if _active_game_mode == 2 else "PROFIT")))

    # 1. เขียนลง CSV เพื่อให้ Live Terminal HUD อัปเดต In-Place
    _log_round_to_csv(
        _total_bets, mode_name, roll_result, "win" if Win else "lose",
        current_bet_amt, round_pnl, net_pnl, cur_bal, _loss_streak, rare_tag, won_amount
    )

    # 2. พิมพ์ Event Feed ใน Console ของ DiceBot สไตล์ Simulator
    if rare_tag:
        Print("[#{0:6d}] 🎯 {1:5s} │ Roll: {2:4d} │ Bet: {3:12.8f} │ Won: +{4:.8f}".format(
            _total_bets, rare_tag, int(roll_result), current_bet_amt, won_amount
        ))
    elif Win:
        Print("[#{0:6d}] 🏆 WIN   │ Roll: {1:4d} │ Bet: {2:12.8f} │ Won: +{3:.8f}".format(
            _total_bets, int(roll_result), current_bet_amt, won_amount
        ))
    else:
        Print("[#{0:6d}] 💀 LOSS  │ Roll: {1:4d} │ Bet: {2:12.8f} │ PnL: {3:.8f}".format(
            _total_bets, int(roll_result), current_bet_amt, round_pnl
        ))

    # ทุกๆ 10 ไม้ พิมพ์ Status Box ย่อใน Console
    if _total_bets % 10 == 0:
        quota_str = ""
        if _active_game_mode == 5:
            rem = max(0, _b_losses_allowed - _loss_streak)
            quota_str = " | Quota: {0}/{1}".format(rem, _b_losses_allowed)
        Print("   [STATUS #{0}] Balance: {1:.8f} | Net PnL: {2:+.8f} | Streak: {3}{4}".format(
            _total_bets, cur_bal, net_pnl, _loss_streak, quota_str
        ))

    # ── M1: PROFIT MODE ──
    if _active_game_mode == 1:
        lose_mul = _calc_martingale_multiplier(_p_win_chance, _active_house_edge)
        NextBet.Amount = _p_base_bet if Win else (current_bet_amt * lose_mul)
        NextBet.Chance = _p_win_chance
        NextBet.High = _p_target_high

        if _p_stop_target > 0 and net_pnl >= _p_stop_target:
            Print("[STOP] Target Profit Reached (+{0:.8f})".format(net_pnl))
            Stop()
        if _p_max_loss > 0 and _loss_streak >= _p_max_loss:
            Print("[STOP] Max Loss Streak Reached ({0})".format(_loss_streak))
            Stop()

    # ── M2: WAGER MODE ──
    elif _active_game_mode == 2:
        NextBet.Amount = _w_base_bet
        NextBet.Chance = _w_win_chance
        NextBet.High = _w_target_high

        if _w_stop_volume > 0 and _total_wagered >= _w_stop_volume:
            Print("[STOP] Wager Target Reached ({0:.2f})".format(_total_wagered))
            Stop()

    # ── M3: HYBRID MODE ──
    elif _active_game_mode == 3:
        if _current_hybrid_mode == "WAGER":
            if cur_bal <= _hybrid_trigger_balance:
                Print("[🚨 SWITCH] Balance dipped -> RECOVERY MODE")
                _current_hybrid_mode = "PROFIT"
                _loss_streak = 0
                NextBet.Amount = _p_base_bet
                NextBet.Chance = _p_win_chance
                NextBet.High = _p_target_high
            else:
                NextBet.Amount = _w_base_bet
                NextBet.Chance = _w_win_chance
                NextBet.High = _w_target_high
        else: # PROFIT Mode
            rec_mul = _calc_martingale_multiplier(_p_win_chance, _active_house_edge)
            if Win:
                if cur_bal >= _session_start_balance:
                    surplus = cur_bal - _session_start_balance
                    _profit_vault += surplus
                    Print("[🎯 RECOVERED] Secured +{0:.8f} to Vault -> RESUME WAGER".format(surplus))
                    _current_hybrid_mode = "WAGER"
                    _loss_streak = 0
                    NextBet.Amount = _w_base_bet
                    NextBet.Chance = _w_win_chance
                    NextBet.High = _w_target_high
                else:
                    NextBet.Amount = _p_base_bet
                    NextBet.Chance = _p_win_chance
                    NextBet.High = _p_target_high
            else:
                NextBet.Amount = current_bet_amt * rec_mul
                NextBet.Chance = _p_win_chance
                NextBet.High = _p_target_high

    # ── M4: CUSTOM MODE ──
    elif _active_game_mode == 4:
        calc_bet = current_bet_amt
        if Win:
            _c_current_chance = _c_win_chance
            _c_loss_since_mul = 0
            calc_bet = _c_base_bet if _c_win_reset_base == 1 else (current_bet_amt * _c_win_mul)
            if _c_rst_win_streak > 0 and (_win_streak % _c_rst_win_streak == 0):
                calc_bet = _c_base_bet
        else:
            _c_loss_since_mul += 1
            if _c_loss_reset_first == 1 and _loss_streak == 1:
                calc_bet = _c_base_bet
            elif _c_loss_since_mul >= _c_loss_mul_every:
                calc_bet = current_bet_amt * _c_loss_mul
                _c_loss_since_mul = 0
            else:
                calc_bet = current_bet_amt

            if _c_loss_chg_bet_streak > 0 and _loss_streak >= _c_loss_chg_bet_streak:
                calc_bet = _c_loss_chg_bet_val
            if _c_loss_chg_chance_streak > 0 and _loss_streak >= _c_loss_chg_chance_streak:
                _c_current_chance = _c_loss_chg_chance_val
            if _c_rst_loss_streak > 0 and (_loss_streak % _c_rst_loss_streak == 0):
                calc_bet = _c_base_bet

        if _c_rst_after_bets > 0 and (_total_bets % _c_rst_after_bets == 0):
            calc_bet = _c_base_bet

        if _c_min_bet > 0 and calc_bet < _c_min_bet:
            calc_bet = _c_min_bet
        if _c_max_bet > 0 and calc_bet > _c_max_bet:
            calc_bet = _c_max_bet

        if _c_zigzag_every > 0:
            _c_zigzag_counter += 1
            if _c_zigzag_counter >= _c_zigzag_every:
                _c_current_target = not _c_current_target
                _c_zigzag_counter = 0

        NextBet.Amount = calc_bet
        NextBet.Chance = _c_current_chance
        NextBet.High = _c_current_target

        if _c_stop_loss_streak > 0 and _loss_streak >= _c_stop_loss_streak:
            Print("[STOP] Reached Custom Loss Streak ({0})".format(_loss_streak))
            Stop()
        if _c_stop_profit > 0 and net_pnl >= _c_stop_profit:
            Print("[STOP] Reached Custom Profit (+{0:.8f})".format(net_pnl))
            Stop()
        if _c_stop_max_bets > 0 and _total_bets >= _c_stop_max_bets:
            Print("[STOP] Reached Max Bets ({0})".format(_total_bets))
            Stop()

    # ── M5: BRAVE MODE ──
    else:
        if Win:
            if _b_win_reset_base == 1:
                NextBet.Amount = _solve_brave_base_bet(cur_bal, _b_losses_allowed, _b_loss_mul)
            else:
                NextBet.Amount = current_bet_amt
        else:
            NextBet.Amount = current_bet_amt * _b_loss_mul

        NextBet.Chance = _b_win_chance
        NextBet.High = _b_target_high

        if _loss_streak >= _b_losses_allowed:
            Print("[STOP] Death Point Reached ({0} losses)".format(_loss_streak))
            Stop()
        if _b_stop_profit > 0 and net_pnl >= _b_stop_profit:
            Print("[STOP] Goal Reached (+{0:.8f})".format(net_pnl))
            Stop()
