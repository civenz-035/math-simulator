# ==============================================================================
# 💎 FUSION BOT v4.1 — Gambler.Bot / IronPython Edition
# Ported from DICE.lua (แบบ A: แยก Profit + Reset Balance)
# stake_api_key=522fe34470a71f0662cfc2ec39b887f54e34459125cdc8ed646b366f7a997635d9a75e03b162df944ceaa9cc644be544
# ==============================================================================
# Architecture: IronPython compatible (Gambler.Bot 5.35+)
#   - No argparse, no pathlib, no f-strings with complex expressions
#   - Uses Reset() + CalculateBet() callbacks (same as dice_script.py)
#   - Config loaded from config/dice.env (SSOT) via os.path
#   - CSV logged to simulator/logs/dice_session_latest.csv
# ==============================================================================

import os
import re
import csv
import math
import time

# ==============================================================================
# [1] SSOT CONFIG LOADER
# ==============================================================================
_base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

ENV_FILE_CANDIDATES = [
    os.path.normpath(os.path.join(_base_dir, "..", "config", "dice.env")),
    os.path.normpath(os.path.join(_base_dir, "..", "simulator", "config", "dice.env")),
    os.path.normpath(os.path.join(_base_dir, "config", "dice.env")),
    r"c:\Users\User\simulator\config\dice.env",
]

_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?}|\$(\w+)")

def load_dice_env():
    cfg = {}
    found_path = None
    for p in ENV_FILE_CANDIDATES:
        if os.path.isfile(p):
            found_path = p
            break

    if found_path:
        try:
            with open(found_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.split("#", 1)[0].strip().strip("\"'")
                        cfg[k.strip()] = v
        except Exception:
            pass

    # Expand ${VAR} references
    for _ in range(5):
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


def _get_val(cfg, key, default, cast_type=str):
    if key in cfg and cfg[key] != "":
        try:
            return cast_type(cfg[key])
        except (ValueError, TypeError):
            pass
    return default


# ==============================================================================
# [2] CSV LOGGER
# ==============================================================================
CSV_FILE_CANDIDATES = [
    os.path.normpath(os.path.join(_base_dir, "..", "logs", "dice_session_latest.csv")),
    os.path.normpath(os.path.join(_base_dir, "..", "simulator", "logs", "dice_session_latest.csv")),
    os.path.normpath(os.path.join(_base_dir, "logs", "dice_session_latest.csv")),
    r"c:\Users\User\simulator\logs\dice_session_latest.csv",
]

_csv_path = None

def _init_csv():
    global _csv_path
    # หา logs dir ที่มีอยู่จริง
    for p in CSV_FILE_CANDIDATES:
        d = os.path.dirname(p)
        if os.path.isdir(d):
            _csv_path = p
            break
    if _csv_path is None:
        _csv_path = CSV_FILE_CANDIDATES[-1]

    try:
        logs_dir = os.path.dirname(_csv_path)
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        with open(_csv_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Round", "Mode", "Result", "Bet", "RoundPnL",
                "NetPnL", "Balance", "LossStreak", "ProfitVault"
            ])
    except Exception:
        pass


def _log_csv(rnd, mode, result, bet, round_pnl, net_pnl, bal, streak, vault):
    if not _csv_path:
        return
    try:
        with open(_csv_path, "a") as f:
            writer = csv.writer(f)
            writer.writerow([
                rnd, mode, result,
                "{0:.8f}".format(bet),
                "{0:.8f}".format(round_pnl),
                "{0:.8f}".format(net_pnl),
                "{0:.8f}".format(bal),
                streak,
                "{0:.8f}".format(vault),
            ])
    except Exception:
        pass


# ==============================================================================
# [3] FUSION BOT MATH ENGINE
# ==============================================================================
def _random_chance(chance_min, chance_max):
    """IronPython-safe random using System.Random"""
    try:
        import System
        rng = System.Random()
        c = chance_min + rng.NextDouble() * (chance_max - chance_min)
    except Exception:
        import random as _r
        c = _r.uniform(chance_min, chance_max)
    if c < 0.01:
        c = 0.01
    if c > 99.0:
        c = 99.0
    return c


def _get_payout_and_multiplier(chance_pct, bonus_pct, use_house_edge, house_edge):
    """Matches Lua getAutoMultiplierByChance()"""
    cd = max(0.0001, min(0.9999, chance_pct / 100.0))
    if use_house_edge and house_edge > 0:
        payout = (1.0 - house_edge / 100.0) / cd
    else:
        payout = 0.99 / cd
    if payout <= 1.0:
        payout = 1.0001
    multiplier = 1.0 + (1.0 + bonus_pct / 100.0) / (payout - 1.0)
    return multiplier, payout


def _get_constant_divisor(chance_ref, bonus_pct, losses, use_house_edge, house_edge):
    """Geometric series: sum_{i=0}^{losses-1} mul^i"""
    mul, _ = _get_payout_and_multiplier(chance_ref, bonus_pct, use_house_edge, house_edge)
    total = 0.0
    for i in range(losses):
        total += math.pow(mul, i)
    return total


def _solve_base_bet(cycle_bal, chance_ref, bonus_pct, losses, min_bet, use_he, he):
    d = _get_constant_divisor(chance_ref, bonus_pct, losses, use_he, he)
    base = cycle_bal / d if d > 0 else min_bet
    return max(base, min_bet), d


# ==============================================================================
# [4] GLOBAL STATE
# ==============================================================================
_cfg = {}
_env_path = None

# ── Fusion config ──────────────────────────────────────────────────────────
_main_mode          = 1       # 1=WAGER FOCUS+RECOVERY  2=PROFIT FOCUS
_wager_chance       = 98.0
_wager_bet_percent  = 2.5
_loss_cut_percent   = 4.0
_recover_profit_pct = 1.0
_wager_target       = 100.0
_enable_wager_target= True
_auto_chance        = True
_chance_min         = 0.5
_chance_max         = 0.75
_chance_fixed       = 0.5
_random_on_win      = True
_random_on_lose     = False
_risk_bonus_pct     = 5.0
_house_edge         = 1.0
_allowed_losses     = 600
_min_bet            = 0.00000001
_stop_profit_ratio  = 0.2
_stop_loss_ratio    = 0.0
_stop_max_streak    = 0

# ── Runtime state ──────────────────────────────────────────────────────────
_session_start_balance  = 0.0
_start_time             = 0.0
_total_bets             = 0
_total_wagered          = 0.0
_win_count              = 0
_lose_count             = 0
_loss_streak            = 0
_max_loss_streak        = 0
_consecutive_losses     = 0

_mode                   = "WAGER"
_working_balance        = 0.0
_profit_vault           = 0.0
_cycle_start_balance    = 0.0
_original_cycle_balance = 0.0
_wager_cycle_start      = 0.0
_profit_cycle_start     = 0.0
_wager_loss_amount      = 0.0

_base_bet               = 0.0
_divisor                = 1.0
_wager_base_bet         = 0.0
_current_chance         = 98.0


# ==============================================================================
# [5] INTERNAL HELPERS
# ==============================================================================
def _update_base():
    global _base_bet, _divisor, _cycle_start_balance
    ref    = _chance_min if _auto_chance else _chance_fixed
    use_he = (_main_mode == 2)
    _base_bet, _divisor = _solve_base_bet(
        _cycle_start_balance, ref, _risk_bonus_pct,
        _allowed_losses, _min_bet, use_he, _house_edge
    )


def _separate_profit_reset():
    global _profit_vault, _working_balance, _cycle_start_balance
    global _original_cycle_balance

    cur_bal = float(Balance)
    cp = cur_bal - _original_cycle_balance

    if cp > 0:
        _profit_vault += cp
        Print("=" * 50)
        Print("✅ Cycle Complete! Profit: {0:.8f}".format(cp))
        Print("💎 Profit Vault: {0:.8f}".format(_profit_vault))
        Print("🔄 Reset to: {0:.8f}".format(_original_cycle_balance))
        Print("=" * 50)
        # Type A: reset balance back (simulation — on real bot cannot change balance)
        # We track working_balance as the "virtual" reset
        _working_balance        = _original_cycle_balance
        _cycle_start_balance    = _original_cycle_balance
    else:
        Print("⚠️  Cycle ended without profit ({0:.8f})".format(cp))
        _working_balance = cur_bal


def _switch_to_wager():
    global _mode, _loss_streak, _consecutive_losses
    global _wager_cycle_start, _wager_base_bet, _wager_loss_amount
    global _current_chance
    _mode             = "WAGER"
    _loss_streak      = 0
    _consecutive_losses = 0
    _wager_cycle_start  = float(Balance)
    _wager_base_bet     = _wager_cycle_start * (_wager_bet_percent / 100.0)
    _wager_loss_amount  = 0.0
    _current_chance     = _wager_chance

    NextBet.Chance = _wager_chance
    NextBet.Amount = max(_wager_base_bet, _min_bet)
    NextBet.High   = True

    Print("🟢 → WAGER MODE  base_bet={0:.8f}  chance={1:.2f}%".format(
        _wager_base_bet, _wager_chance))


def _switch_to_profit():
    global _mode, _loss_streak, _consecutive_losses
    global _profit_cycle_start, _cycle_start_balance
    global _base_bet, _divisor, _current_chance
    _mode             = "PROFIT"
    _loss_streak      = 0
    _consecutive_losses = 0
    _profit_cycle_start  = float(Balance)
    _cycle_start_balance = float(Balance)

    _update_base()

    if _auto_chance:
        _current_chance = _random_chance(_chance_min, _chance_max)
    else:
        _current_chance = _chance_fixed

    mul, payout = _get_payout_and_multiplier(
        _current_chance, _risk_bonus_pct, (_main_mode == 2), _house_edge
    )

    NextBet.Chance = _current_chance
    NextBet.Amount = max(_base_bet, _min_bet)
    NextBet.High   = True

    Print("🟡 → PROFIT MODE  base={0:.8f}  chance={1:.2f}%  mul={2:.4f}x".format(
        _base_bet, _current_chance, mul))


def _show_status():
    bal = float(Balance)
    runtime = time.time() - _start_time

    if _mode == "WAGER":
        cycle_pnl = bal - _wager_cycle_start
    else:
        cycle_pnl = bal - _profit_cycle_start

    total_pnl = _profit_vault + (bal - _original_cycle_balance)

    Print("┌──────────────────────────────────────────────┐")
    Print("⏱  {0:.0f}s | Strategy: {1} | Mode: {2}".format(
        runtime,
        "WAGER FOCUS+RECOVERY" if _main_mode == 1 else "PROFIT FOCUS",
        _mode
    ))
    Print("💰 Balance:      {0:.8f}".format(bal))
    Print("💎 Profit Vault: {0:.8f}".format(_profit_vault))
    Print("📊 Cycle P/L:    {0:+.8f}".format(cycle_pnl))
    Print("🎁 Total P/L:    {0:+.8f}  ROI: {1:+.2f}%".format(
        total_pnl, total_pnl / _session_start_balance * 100 if _session_start_balance > 0 else 0.0
    ))
    Print("🎲 Next Bet:     {0:.8f} | Chance: {1:.2f}%".format(
        float(NextBet.Amount), float(NextBet.Chance)
    ))
    Print("🏆 W/L: {0}/{1} | Streak: {2} (Max: {3})".format(
        _win_count, _lose_count, _loss_streak, _max_loss_streak
    ))
    Print("⚡ ConLoss/Cycle: {0}/{1}".format(_consecutive_losses, _allowed_losses))

    if _main_mode == 1:
        Print("📈 Wagered: {0:.2f} / {1:.2f}".format(_total_wagered, _wager_target))
        if _mode == "WAGER":
            wl = _wager_cycle_start - bal
            pct = wl / _wager_cycle_start * 100 if _wager_cycle_start > 0 else 0.0
            Print("📉 Wager Loss: {0:.2f}% / {1:.2f}%".format(pct, _loss_cut_percent))
        else:
            need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
            gain = bal - _profit_cycle_start
            need_pct = need / _profit_cycle_start * 100 if _profit_cycle_start > 0 else 0.0
            gain_pct = gain / _profit_cycle_start * 100 if _profit_cycle_start > 0 else 0.0
            Print("♻  Recovery: {0:.2f}% / {1:.2f}%".format(gain_pct, need_pct))

    Print("└──────────────────────────────────────────────┘")


# ==============================================================================
# [6] GAMBLER.BOT CALLBACKS
# ==============================================================================
def Reset():
    global _cfg, _env_path
    global _main_mode, _wager_chance, _wager_bet_percent, _loss_cut_percent
    global _recover_profit_pct, _wager_target, _enable_wager_target
    global _auto_chance, _chance_min, _chance_max, _chance_fixed
    global _random_on_win, _random_on_lose, _risk_bonus_pct, _house_edge
    global _allowed_losses, _min_bet, _stop_profit_ratio, _stop_loss_ratio
    global _stop_max_streak
    global _session_start_balance, _start_time, _total_bets, _total_wagered
    global _win_count, _lose_count, _loss_streak, _max_loss_streak, _consecutive_losses
    global _mode, _working_balance, _profit_vault
    global _cycle_start_balance, _original_cycle_balance
    global _wager_cycle_start, _profit_cycle_start, _wager_loss_amount
    global _base_bet, _divisor, _wager_base_bet, _current_chance

    # Load SSOT config
    _cfg, _env_path = load_dice_env()
    g = _cfg

    def gv(key, default, cast=str):
        return _get_val(g, key, default, cast)

    # ── Read FUSION_* keys (with GLOBAL_* fallback) ──
    _main_mode           = gv("FUSION_MAIN_MODE",        1,    int)
    _wager_chance        = gv("FUSION_WAGER_CHANCE",     98.0, float)
    _wager_bet_percent   = gv("FUSION_WAGER_BET_PCT",    2.5,  float)
    _loss_cut_percent    = gv("FUSION_LOSS_CUT_PCT",     4.0,  float)
    _recover_profit_pct  = gv("FUSION_RECOVER_PROFIT_PCT", 1.0, float)
    _wager_target        = gv("FUSION_WAGER_TARGET",     gv("WAGER_TARGET", 100.0, float), float)
    _enable_wager_target = gv("FUSION_ENABLE_WAGER_TARGET", 1, int) != 0
    _auto_chance         = gv("FUSION_AUTO_CHANCE",      1,    int) != 0
    _chance_min          = gv("FUSION_CHANCE_MIN",       0.5,  float)
    _chance_max          = gv("FUSION_CHANCE_MAX",       0.75, float)
    _chance_fixed        = gv("FUSION_CHANCE_FIXED",     0.5,  float)
    _random_on_win       = gv("FUSION_RANDOM_ON_WIN",    1,    int) != 0
    _random_on_lose      = gv("FUSION_RANDOM_ON_LOSE",   0,    int) != 0
    _risk_bonus_pct      = gv("FUSION_RISK_BONUS_PCT",   5.0,  float)
    _house_edge          = gv("HE",                      1.0,  float)
    _allowed_losses      = gv("FUSION_ALLOWED_LOSSES",   600,  int)
    _min_bet             = gv("FUSION_MIN_BET",          0.00000001, float)
    _stop_profit_ratio   = gv("FUSION_STOP_PROFIT",      0.2,  float)
    _stop_loss_ratio     = gv("FUSION_STOP_LOSS",        0.0,  float)
    _stop_max_streak     = gv("FUSION_STOP_LOSS_STREAK", 0,    int)

    # ── Reset state ────────────────────────────────────────────────
    _session_start_balance  = float(Balance)
    _start_time             = time.time()
    _total_bets             = 0
    _total_wagered          = 0.0
    _win_count              = 0
    _lose_count             = 0
    _loss_streak            = 0
    _max_loss_streak        = 0
    _consecutive_losses     = 0

    _mode                   = "WAGER"
    _working_balance        = _session_start_balance
    _profit_vault           = 0.0
    _cycle_start_balance    = _session_start_balance
    _original_cycle_balance = _session_start_balance
    _wager_cycle_start      = _session_start_balance
    _profit_cycle_start     = _session_start_balance
    _wager_loss_amount      = 0.0

    # Init CSV
    _init_csv()

    Print("=" * 60)
    Print("  💎 FUSION BOT v4.1 — Gambler.Bot Edition")
    Print("  SSOT: {0}".format(os.path.basename(_env_path) if _env_path else "defaults"))
    Print("  CSV: {0}".format(_csv_path or "N/A"))
    Print("=" * 60)
    Print("  Strategy: {0}".format(
        "WAGER FOCUS + RECOVERY" if _main_mode == 1 else "PROFIT FOCUS"
    ))
    Print("  Balance:  {0:.8f}".format(_session_start_balance))
    Print("  Loss Cut: {0:.2f}% | Recover: Loss + {1:.2f}%".format(
        _loss_cut_percent, _recover_profit_pct
    ))
    Print("  Allowed Losses: {0} | Stop Profit: {1:.0f}%".format(
        _allowed_losses, _stop_profit_ratio * 100
    ))
    Print("=" * 60)

    # ── Initialise first bet ───────────────────────────────────────
    _update_base()  # pre-calculate even for wager mode

    if _main_mode == 1:
        _switch_to_wager()
    else:
        _switch_to_profit()


def CalculateBet():
    global _total_bets, _total_wagered, _win_count, _lose_count
    global _loss_streak, _max_loss_streak, _consecutive_losses
    global _mode, _working_balance, _profit_vault
    global _wager_loss_amount, _current_chance
    global _base_bet, _divisor

    _total_bets += 1
    bet_amt  = float(PreviousBet.TotalAmount)
    round_pnl = float(PreviousBet.Profit)
    cur_bal  = float(Balance)
    net_pnl  = float(CurrentProfit)
    won      = bool(Win)

    _total_wagered += bet_amt
    _working_balance = cur_bal

    # ── WIN ──────────────────────────────────────────────────────────
    if won:
        _win_count += 1
        _loss_streak = 0
        _consecutive_losses = 0

        if _mode == "WAGER":
            NextBet.Amount = max(_wager_base_bet, _min_bet)
            NextBet.Chance = _wager_chance

            if _main_mode == 1 and _enable_wager_target and _total_wagered >= _wager_target:
                Print("🎯 Wager Target {0:.2f} reached!".format(_wager_target))
                _separate_profit_reset()
                _show_status()
                Stop()
                return

        else:  # PROFIT mode win
            if _auto_chance and _random_on_win:
                _current_chance = _random_chance(_chance_min, _chance_max)
            else:
                _current_chance = _chance_fixed

            NextBet.Chance = _current_chance
            NextBet.Amount = max(_base_bet, _min_bet)

            if _main_mode == 1:
                need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
                gain = cur_bal - _profit_cycle_start
                if gain >= need:
                    Print("✅ Recovery WIN  gain={0:+.8f}".format(gain))
                    _separate_profit_reset()
                    _switch_to_wager()
                    _log_csv(_total_bets, _mode, "win", bet_amt, round_pnl, net_pnl,
                             cur_bal, _loss_streak, _profit_vault)
                    return

    # ── LOSE ─────────────────────────────────────────────────────────
    else:
        _lose_count += 1
        _loss_streak += 1
        _consecutive_losses += 1
        if _loss_streak > _max_loss_streak:
            _max_loss_streak = _loss_streak

        if _mode == "WAGER":
            cycle_loss = _wager_cycle_start - cur_bal
            loss_pct   = cycle_loss / _wager_cycle_start * 100.0 if _wager_cycle_start > 0 else 0.0
            Print("   📉 Wager Loss: {0:.2f}% / {1:.2f}%".format(loss_pct, _loss_cut_percent))

            if _main_mode == 1 and loss_pct >= _loss_cut_percent:
                _wager_loss_amount = cycle_loss
                Print("⚠️  Loss cut {0:.2f}% | loss={1:.8f}".format(loss_pct, cycle_loss))
                _switch_to_profit()
            else:
                NextBet.Amount = max(_wager_base_bet, _min_bet)
                NextBet.Chance = _wager_chance

        else:  # PROFIT mode lose
            if _auto_chance and _random_on_lose:
                _current_chance = _random_chance(_chance_min, _chance_max)

            use_he = (_main_mode == 2)
            mul, _ = _get_payout_and_multiplier(
                _current_chance, _risk_bonus_pct, use_he, _house_edge
            )
            new_bet = float(PreviousBet.TotalAmount) * mul

            if new_bet > cur_bal:
                new_bet = cur_bal * 0.9

            NextBet.Amount = max(new_bet, _min_bet)
            NextBet.Chance = _current_chance

            Print("📈 Loss #{0} | Next: {1:.8f} (x{2:.4f})".format(
                _consecutive_losses, new_bet, mul
            ))

            if _consecutive_losses >= _allowed_losses:
                Print("⛔ {0} losses → reset base".format(_allowed_losses))
                _update_base()
                _consecutive_losses = 0
                NextBet.Amount = max(_base_bet, _min_bet)

            if _main_mode == 1:
                need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
                gain = cur_bal - _profit_cycle_start
                if gain >= need:
                    Print("✅ Recovery LOSE  gain={0:+.8f}".format(gain))
                    _separate_profit_reset()
                    _switch_to_wager()
                    _log_csv(_total_bets, _mode, "lose", bet_amt, round_pnl, net_pnl,
                             cur_bal, _loss_streak, _profit_vault)
                    return

    # ── ENFORCE MIN BET ───────────────────────────────────────────────
    if float(NextBet.Amount) < _min_bet:
        NextBet.Amount = _min_bet

    # ── STOP RULES ───────────────────────────────────────────────────
    total_pnl    = _profit_vault + (cur_bal - _original_cycle_balance)
    profit_ratio = total_pnl / _session_start_balance if _session_start_balance > 0 else 0.0

    if _stop_profit_ratio > 0 and profit_ratio >= _stop_profit_ratio:
        Print("🎉 Profit target {0:.0f}% reached!".format(_stop_profit_ratio * 100))
        _separate_profit_reset()
        _show_status()
        Stop()
        return

    if _stop_loss_ratio > 0 and profit_ratio <= -_stop_loss_ratio:
        Print("🚨 Loss limit {0:.0f}% hit!".format(_stop_loss_ratio * 100))
        _show_status()
        Stop()
        return

    if _stop_max_streak > 0 and _loss_streak >= _stop_max_streak:
        Print("🚨 Max streak {0} reached!".format(_stop_max_streak))
        _show_status()
        Stop()
        return

    if cur_bal < _min_bet * 2:
        Print("🚨 Balance too low!")
        _show_status()
        Stop()
        return

    # ── CSV LOG ───────────────────────────────────────────────────────
    total_pnl = _profit_vault + (cur_bal - _original_cycle_balance)
    _log_csv(_total_bets, _mode, "win" if won else "lose",
             bet_amt, round_pnl, total_pnl, cur_bal, _loss_streak, _profit_vault)

    # ── PERIODIC STATUS (every 50 bets) ──────────────────────────────
    if _total_bets % 50 == 0:
        _show_status()
