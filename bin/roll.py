#!/usr/bin/env python3
"""
DICE SIMULATOR - MULTI MODE ENGINE (Python Port)
============================================================
Supports:
  - Mode 1: Profit Mode (Martingale recovery with low win chance)
  - Mode 2: Wager Mode (High win chance, flat bet to build wager volume)
  - Mode 3: Hybrid Mode (Wager mode that switches to Profit recovery when dropped)
  - Mode 4: Custom Mode (Complex rules, multiplier cycles, zigzag, rare hunting)
  - Mode 5: Brave Mode (Survival risk-budget engine, solved basebet, death gauge)
  - Live HUD: In-place real-time terminal dashboard block for all 5 modes
  - Milestone Event Feed: Significant events (Wins, Rare Hits, Mode Switches)
    are printed permanently to scrollback history for full trace.
  - Rare Tracker & CSV Log: Automatic recording of all rounds and rare numbers.
============================================================
"""

import argparse
import csv
import math
import os
from pathlib import Path
import random
import re
import sys
import time
import unicodedata

# Windows consoles default to a legacy code page (cp1252/cp437) and raise
# UnicodeEncodeError on the box-drawing and emoji used in the banners below.
# Force UTF-8 with replacement so the simulator runs unmodified everywhere.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ─────────────────────────────────────────
# [0] HELPER COLOR & TUI ENGINE
# ─────────────────────────────────────────
def cn(code: int, text: str, bold: bool = False) -> str:
    """Helper formatting text with ANSI 256 color code."""
    style = "1;" if bold else ""
    return f"\033[{style}38;5;{code}m{text}\033[0m"

def _wc(text: str) -> str:
    return cn(255, str(text), True)

def _gr(text: str) -> str:
    return cn(235, str(text), False)

def pos_c(text: str) -> str:
    return cn(82, str(text), True)

def neg_c(text: str) -> str:
    return cn(124, str(text), True)

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def char_width(ch: str) -> int:
    """Calculate terminal display width for wide/Asian characters & emojis."""
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1

def visual_len(s: str) -> int:
    """Return visible width of string on terminal ignoring ANSI escape sequences."""
    clean = _ANSI_REGEX.sub("", s)
    return sum(char_width(c) for c in clean)

def pad_line(content: str, target_width: int = 70) -> str:
    """Pad content with trailing spaces to target_width and enclose in box borders."""
    v_len = visual_len(content)
    pad = max(0, target_width - v_len)
    return f"│ {content}{' ' * pad} │"

def make_fixed_row(left: str, right: str, left_w: int = 34, total_w: int = 70) -> str:
    """Compose a 2-column row with fixed column boundary to prevent layout jitter."""
    l_v = visual_len(left)
    l_pad = max(0, left_w - l_v)
    r_v = visual_len(right)
    r_pad = max(0, (total_w - left_w) - r_v)
    return pad_line(f"{left}{' ' * l_pad}{right}{' ' * r_pad}", total_w)

def make_header_border(title: str, total_width: int = 72) -> str:
    """Generate top border box with centered title."""
    t_len = visual_len(title)
    tot = max(0, total_width - t_len - 2)
    l_d = tot // 2
    r_d = tot - l_d
    return f"┌{'─' * l_d} {title} {'─' * r_d}┐"

def progress_bar(val: float, total: float, width: int = 16) -> str:
    """Render a smooth ASCII progress bar."""
    if total <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, val / total))
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"

# ─────────────────────────────────────────
# [0.1] LOAD CENTRAL CONFIG (config/dice.env)
# ─────────────────────────────────────────
def load_env_config() -> dict[str, str]:
    """Load configuration from config/dice.env (override with DICE_CONFIG)."""
    config: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parent.parent
    env_override = os.environ.get("DICE_CONFIG")
    env_path = Path(env_override) if env_override else repo_root / "config" / "dice.env"

    if env_path.is_file():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.split("#", 1)[0].strip().strip("\"'")
                    config[key.strip()] = val
    # Allow OS environment variables to override
    for k, v in os.environ.items():
        if k in config or k.startswith("CUSTOM_") or k.startswith("BRAVE_") or k.startswith("GLOBAL_"):
            config[k] = v
    return config

# ─────────────────────────────────────────
# [1] ARGUMENT PARSER
# ─────────────────────────────────────────
def parse_arguments(env_cfg: dict[str, str]):
    def cfg_get(key: str, default, cast_type=str):
        if key in env_cfg and env_cfg[key] != "":
            try:
                return cast_type(env_cfg[key])
            except (ValueError, TypeError):
                pass
        return default

    # SSOT Global Defaults
    default_game_mode = cfg_get("GAME_MODE", 4, int)
    default_base_bet = cfg_get("GLOBAL_BASE_BET", cfg_get("BASE_BET", 0.01487629, float), float)
    default_win_chance = cfg_get("GLOBAL_WIN_CHANCE", cfg_get("WIN_CHANCE", 3.96, float), float)
    default_bet_target = cfg_get("GLOBAL_BET_TARGET", cfg_get("BET_STRATEGY", "high", str), str)
    default_max_rounds = cfg_get("GLOBAL_MAX_ROUNDS", cfg_get("MAX_ROUNDS", 200000, int), int)
    default_round_delay = cfg_get("GLOBAL_ROUND_DELAY", 0.0, float)
    default_stop_profit = cfg_get("GLOBAL_STOP_PROFIT", 0.0, float)
    default_stop_loss = cfg_get("GLOBAL_STOP_LOSS", 0.0, float)
    default_stop_on_win = cfg_get("GLOBAL_STOP_ON_WIN", 0, int)
    default_max_loss = cfg_get("GLOBAL_MAX_LOSS_STREAK", 0, int)
    default_rare = bool(int(cfg_get("HUNT_RARE", 0, int)))

    parser = argparse.ArgumentParser(
        description="Multi-Mode Dice Simulator (Martingale / Wager / Hybrid / Custom / Brave)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-m", "--mode", type=int, choices=[1, 2, 3, 4, 5],
        default=default_game_mode,
        help="Game mode: 1(profit), 2(wager), 3(hybrid), 4(custom), 5(brave)"
    )
    parser.add_argument(
        "-b", "--basebet", type=float, default=None,
        help="Override base bet amount"
    )
    parser.add_argument(
        "-c", "--chance", type=float, default=None,
        help="Override win chance %%"
    )
    parser.add_argument(
        "-wc", "--wager-chance", type=float,
        default=cfg_get("WAGER_WIN_CHANCE", 98.0, float),
        help="Win chance %% (Wager Mode)"
    )
    parser.add_argument(
        "-sb", "--startbalance", type=float,
        default=cfg_get("START_BALANCE", 10000.0, float),
        help="Starting balance"
    )
    parser.add_argument(
        "-r", "--rounds", type=int,
        default=default_max_rounds,
        help="Max rounds"
    )
    parser.add_argument(
        "-ml", "--maxloss", type=int, default=None,
        help="Override max loss streak limit"
    )
    parser.add_argument(
        "-sw", "--stop-win", type=float, default=None,
        help="Stop profit target (amount)"
    )
    parser.add_argument(
        "-sl", "--stop-wagered", type=float,
        default=cfg_get("WAGER_TARGET", 1000000.0, float),
        help="Wager target limit (Mode 2/3)"
    )
    parser.add_argument(
        "-ow", "--on-win", type=int,
        default=default_stop_on_win,
        help="Stop after N wins (0 = unlimited)"
    )
    parser.add_argument(
        "-s", "--strategy", type=str, choices=["low", "high"], default=None,
        help="Bet strategy low|high"
    )
    parser.add_argument(
        "-d", "--delay", type=float,
        default=default_round_delay,
        help="Delay (seconds) between rounds"
    )
    parser.add_argument(
        "--rare", "--hunt-rare", action="store_true",
        default=default_rare,
        help="Enable rare number hunting tracker (990x - 9900x)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for reproducible runs (web lab uses this)"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Headless mode for the web lab: no HUD animation, emits __RESULT_JSON__"
    )
    return parser.parse_args()

# ─────────────────────────────────────────
# [2] MAIN SIMULATION LOGIC
# ─────────────────────────────────────────
def run_simulation():
    env_cfg = load_env_config()
    args = parse_arguments(env_cfg)
    round_delay = args.delay
    game_mode = args.mode

    # Headless mode for the web lab (POST /run): deterministic seed,
    # no per-round terminal I/O. Default terminal behaviour is unchanged.
    quiet = bool(getattr(args, "quiet", False))
    if getattr(args, "seed", None) is not None:
        random.seed(args.seed)
    if quiet:
        round_delay = 0.0
    milestones: list[str] = []

    def cfg_val(key: str, default, cast_type=str):
        if key in env_cfg and env_cfg[key] != "":
            try:
                return cast_type(env_cfg[key])
            except (ValueError, TypeError):
                pass
        return default

    # Global Core Fallbacks
    start_balance = args.startbalance
    house_edge = float(cfg_val("HE", 1.0, float))
    max_rounds = args.rounds
    stop_on_win = args.on_win

    g_base_bet = cfg_val("GLOBAL_BASE_BET", cfg_val("BASE_BET", 0.01487629, float), float)
    g_win_chance = cfg_val("GLOBAL_WIN_CHANCE", cfg_val("WIN_CHANCE", 3.96, float), float)
    g_bet_target = str(cfg_val("GLOBAL_BET_TARGET", cfg_val("BET_STRATEGY", "high", str))).strip().lower()

    # Mode 1: PROFIT MODE (Martingale)
    profit_base_bet = args.basebet if args.basebet is not None else cfg_val("PROFIT_BASE_BET", g_base_bet, float)
    profit_win_chance = args.chance if args.chance is not None else cfg_val("PROFIT_WIN_CHANCE", g_win_chance, float)
    profit_bet_target = args.strategy if args.strategy is not None else str(cfg_val("PROFIT_BET_TARGET", g_bet_target, str)).strip().lower()
    profit_stop_target = args.stop_win if args.stop_win is not None else cfg_val("PROFIT_STOP_TARGET", cfg_val("GLOBAL_STOP_PROFIT", 0.0, float), float)
    profit_max_loss = args.maxloss if args.maxloss is not None else cfg_val("PROFIT_MAX_LOSS_STREAK", 500, int)
    profit_stop_win_count = cfg_val("PROFIT_STOP_ON_WIN", 50000, int)

    profit_payout = (1.0 - (house_edge / 100.0)) / (profit_win_chance / 100.0)
    profit_win_mul = profit_payout - 1.0
    profit_lose_mul = (1.0 + (1.0 / (profit_payout - 1.0)) + (0.05 / profit_payout)) if (profit_payout > 1.0) else 2.0
    profit_t_low = int(profit_win_chance * 100)
    profit_t_high = int((100 - profit_win_chance) * 100)

    # Mode 2: WAGER MODE
    wager_win_chance = args.wager_chance if args.wager_chance is not None else cfg_val("WAGER_WIN_CHANCE", 98.0, float)
    wager_bet_pct = cfg_val("WAGER_BET_PCT", cfg_val("WAGER_BET", 2.5, float), float)
    wager_base_bet = args.basebet if args.basebet is not None else cfg_val("WAGER_BASE_BET", (wager_bet_pct / 100.0) * start_balance, float)
    wager_bet_target = args.strategy if args.strategy is not None else str(cfg_val("WAGER_BET_TARGET", g_bet_target, str)).strip().lower()
    wager_target = args.stop_wagered
    wager_payout = (1.0 - (house_edge / 100.0)) / (wager_win_chance / 100.0)
    wager_win_mul = wager_payout - 1.0
    wager_t_low = int(wager_win_chance * 100)
    wager_t_high = int((100 - wager_win_chance) * 100)

    # Mode 3: HYBRID MODE
    loss_trigger_pct = cfg_val("HYBRID_LOSS_TRIGGER", cfg_val("LOSS_TRIGGER", 2.0, float), float)
    profit_trigger_pct = cfg_val("HYBRID_PROFIT_TRIGGER", cfg_val("PROFIT_TRIGGER", 1.0, float), float)
    trigger_balance = (1.0 - (loss_trigger_pct / 100.0)) * start_balance
    trigger_balance_profit = start_balance + ((profit_trigger_pct / 100.0) * start_balance)

    # Mode 4: CUSTOM MODE
    c_base_bet = args.basebet if args.basebet is not None else cfg_val("CUSTOM_BASE_BET", g_base_bet, float)
    c_win_chance = args.chance if args.chance is not None else cfg_val("CUSTOM_WIN_CHANCE", g_win_chance, float)
    c_bet_target = args.strategy if args.strategy is not None else str(cfg_val("CUSTOM_BET_TARGET", g_bet_target, str)).strip().lower()

    c_loss_mul = cfg_val("CUSTOM_LOSS_MUL", 1.06, float)
    c_loss_mul_every = cfg_val("CUSTOM_LOSS_MUL_EVERY", 1, int)
    c_loss_reset_first = cfg_val("CUSTOM_LOSS_RESET_FIRST", 0, int)
    c_loss_chg_bet_streak = cfg_val("CUSTOM_LOSS_CHANGE_BET_STREAK", 0, int)
    c_loss_chg_bet_val = cfg_val("CUSTOM_LOSS_CHANGE_BET_VALUE", 0.0, float)
    c_loss_chg_chance_streak = cfg_val("CUSTOM_LOSS_CHANGE_CHANCE_STREAK", 0, int)
    c_loss_chg_chance_val = cfg_val("CUSTOM_LOSS_CHANGE_CHANCE_VALUE", 0.0, float)

    c_win_mul = cfg_val("CUSTOM_WIN_MUL", 1.0, float)
    c_win_reset_base = cfg_val("CUSTOM_WIN_RESET_BASE", 1, int)

    c_rst_after_bets = cfg_val("CUSTOM_RESET_AFTER_BETS", 0, int)
    c_rst_loss_streak = cfg_val("CUSTOM_RESET_ON_LOSS_STREAK", 0, int)
    c_rst_loss_tot_every = cfg_val("CUSTOM_RESET_ON_LOSS_TOTAL_EVERY", 0, int)
    c_rst_loss_val_row = cfg_val("CUSTOM_RESET_ON_LOSS_VALUE_ROW", 0.0, float)
    c_rst_loss_val_tot_every = cfg_val("CUSTOM_RESET_ON_LOSS_VALUE_TOTAL_EVERY", 0.0, float)
    c_rst_loss_since_max_p = cfg_val("CUSTOM_RESET_ON_LOSS_SINCE_MAX_PROFIT", 0.0, float)

    c_rst_win_streak = cfg_val("CUSTOM_RESET_ON_WIN_STREAK", 1, int)
    c_rst_win_tot_every = cfg_val("CUSTOM_RESET_ON_WIN_TOTAL_EVERY", 0, int)
    c_rst_win_val_row = cfg_val("CUSTOM_RESET_ON_WIN_VALUE_ROW", 0.0, float)
    c_rst_win_val_tot_every = cfg_val("CUSTOM_RESET_ON_WIN_VALUE_TOTAL_EVERY", 0.0, float)
    c_rst_win_since_min_p = cfg_val("CUSTOM_RESET_ON_WIN_SINCE_MIN_PROFIT", 0.0, float)

    c_stp_after_bets = cfg_val("CUSTOM_STOP_AFTER_BETS", 0, int)
    c_stp_loss_streak = args.maxloss if args.maxloss is not None else cfg_val("CUSTOM_STOP_ON_LOSS_STREAK", 0, int)
    c_stp_loss_tot = cfg_val("CUSTOM_STOP_ON_LOSS_TOTAL", 0, int)
    c_stp_loss_val_row = cfg_val("CUSTOM_STOP_ON_LOSS_VALUE_ROW", 0.0, float)
    c_stp_loss_val_tot = cfg_val("CUSTOM_STOP_ON_LOSS_VALUE_TOTAL", 0.0, float)
    c_stp_loss_since_max_p = cfg_val("CUSTOM_STOP_ON_LOSS_SINCE_MAX_PROFIT", 0.0, float)

    c_stp_win_streak = cfg_val("CUSTOM_STOP_ON_WIN_STREAK", 0, int)
    c_stp_win_tot = cfg_val("CUSTOM_STOP_ON_WIN_TOTAL", 0, int)
    c_stp_win_val_row = cfg_val("CUSTOM_STOP_ON_WIN_VALUE_ROW", 0.0, float)
    c_stp_win_val_tot = cfg_val("CUSTOM_STOP_ON_WIN_VALUE_TOTAL", 0.0, float)
    c_stp_win_since_min_p = cfg_val("CUSTOM_STOP_ON_WIN_SINCE_MIN_PROFIT", 0.0, float)

    c_upper_limit_bal = cfg_val("CUSTOM_UPPER_LIMIT_BALANCE", 0.0, float)
    c_lower_limit_bal = cfg_val("CUSTOM_LOWER_LIMIT_BALANCE", 0.0, float)
    c_min_bet = cfg_val("CUSTOM_MIN_BET", 0.0, float)
    c_max_bet = cfg_val("CUSTOM_MAX_BET", 0.0, float)
    c_zigzag_every = cfg_val("CUSTOM_ZIGZAG_EVERY", 0, int)
    c_bets_per_sec = cfg_val("CUSTOM_BETS_PER_SEC", 0.0, float)
    if round_delay == 0.0 and c_bets_per_sec > 0:
        round_delay = 1.0 / c_bets_per_sec

    # Mode 5: BRAVE MODE (Survivor Risk-Budget Engine)
    brave_losses_allowed = args.maxloss if args.maxloss is not None else cfg_val("BRAVE_LOSSES_ALLOWED", 50, int)
    brave_loss_mul = cfg_val("BRAVE_LOSS_MUL", 1.06, float)
    brave_win_chance = args.chance if args.chance is not None else cfg_val("BRAVE_WIN_CHANCE", g_win_chance, float)
    brave_bet_target = args.strategy if args.strategy is not None else str(cfg_val("BRAVE_BET_TARGET", g_bet_target, str)).strip().lower()
    brave_stop_profit = args.stop_win if args.stop_win is not None else cfg_val("BRAVE_STOP_PROFIT", 500.0, float)
    brave_win_reset_base = cfg_val("BRAVE_WIN_RESET_BASE", 1, int)

    # Solve exact BaseBet for Brave Mode: Exposure == Balance at N losses
    if brave_loss_mul == 1.0:
        brave_base_bet = start_balance / brave_losses_allowed
    else:
        try:
            brave_base_bet = start_balance * (brave_loss_mul - 1.0) / (math.pow(brave_loss_mul, brave_losses_allowed) - 1.0)
        except (OverflowError, ZeroDivisionError):
            brave_base_bet = 0.0

    brave_payout = (1.0 - (house_edge / 100.0)) / (brave_win_chance / 100.0)
    brave_t_low = int(brave_win_chance * 100)
    brave_t_high = int((100 - brave_win_chance) * 100)

    # Strategy / Rare Hunting Mode Evaluation
    active_chance = c_win_chance if game_mode == 4 else (brave_win_chance if game_mode == 5 else profit_win_chance)
    is_hunting_rare = bool(args.rare or (game_mode in (4, 5) and (active_chance <= 0.10 or ((100.0 - house_edge) / active_chance) >= 990.0)))

    # State variables
    balance = start_balance
    profit_vault = 0.0
    wagered = 0.0
    total_profit = 0.0
    round_num = 0
    win_count = 0
    win_streak = 0
    max_win_streak = 0
    lose_count = 0
    loss_streak = 0
    max_loss_streak = 0
    wrong_side = 0
    win_history: list[tuple[float, int, str]] = []
    rare_hits_history: list[tuple[int, int, str, float, float, float]] = []

    # Runtime state per mode
    custom_current_chance = c_win_chance
    active_bet_target = c_bet_target if game_mode == 4 else (brave_bet_target if game_mode == 5 else (wager_bet_target if game_mode == 2 else profit_bet_target))
    max_profit = 0.0
    min_profit = 0.0
    loss_value_streak = 0.0
    total_loss_value = 0.0
    win_value_streak = 0.0
    total_win_value = 0.0
    zigzag_count = 0
    loss_since_last_mul = 0

    if game_mode == 1:
        current_mode = "PROFIT"
        nextbet = profit_base_bet
    elif game_mode == 2:
        current_mode = "WAGER"
        nextbet = wager_base_bet
    elif game_mode == 3:
        current_mode = "WAGER"
        nextbet = wager_base_bet
    elif game_mode == 4:
        current_mode = "CUSTOM"
        nextbet = c_base_bet
    else:  # game_mode == 5
        current_mode = "BRAVE"
        nextbet = brave_base_bet

    rare_counts = {
        "9900x": 0, "4950x": 0, "3300x": 0, "2475x": 0, "1980x": 0,
        "1650x": 0, "1414x": 0, "1237x": 0, "1100x": 0, "990x": 0
    }

    # Setup CSV Auto-Logging
    repo_root = Path(__file__).resolve().parent.parent
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    csv_file_path = logs_dir / "dice_session_latest.csv"
    csv_fp = open(csv_file_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_fp)
    csv_writer.writerow([
        "Round", "Mode", "Roll", "Result", "Bet", "RoundPnL", "NetPnL",
        "Balance", "LossStreak", "RareHit", "WonAmount"
    ])

    def check_rare_number(roll: int, r_num: int, cur_bet: float, win_amt: float, res: str) -> str | None:
        if not is_hunting_rare:
            return None

        rare_tag = None
        if roll in (9999, 0): rare_tag = "9900x"
        elif roll in (9998, 1): rare_tag = "4950x"
        elif roll in (9997, 2): rare_tag = "3300x"
        elif roll in (9996, 3): rare_tag = "2475x"
        elif roll in (9995, 4): rare_tag = "1980x"
        elif roll in (9994, 5): rare_tag = "1650x"
        elif roll in (9993, 6): rare_tag = "1414x"
        elif roll in (9992, 7): rare_tag = "1237x"
        elif roll in (9991, 8): rare_tag = "1100x"
        elif roll in (9990, 9): rare_tag = "990x"

        # Count as rare hit only on genuine win!
        if rare_tag and res == "win":
            rare_counts[rare_tag] += 1
            rare_hits_history.append((r_num, roll, rare_tag, cur_bet, win_amt, balance))
            return rare_tag
        return None

    def roll_dice(mode: str):
        nonlocal wrong_side
        roll = random.randint(0, 9999)

        if mode == "CUSTOM":
            t_low = int(custom_current_chance * 100)
            t_high = int((100.0 - custom_current_chance) * 100)
            cur_target = active_bet_target
        elif mode == "BRAVE":
            t_low, t_high = brave_t_low, brave_t_high
            cur_target = active_bet_target
        elif mode == "WAGER":
            t_low, t_high = wager_t_low, wager_t_high
            cur_target = wager_bet_target
        else:
            t_low, t_high = profit_t_low, profit_t_high
            cur_target = profit_bet_target

        if cur_target == "low":
            if roll < t_low:
                result = "win"
            else:
                result = "lose"
                if roll >= t_high:
                    wrong_side += 1
        else:  # cur_target == "high"
            if roll >= t_high:
                result = "win"
            else:
                result = "lose"
                if roll < t_low:
                    wrong_side += 1

        return roll, result

    def check_stop_condition(current_nextbet: float) -> str:
        if balance <= 0:
            return "BUST: balance depleted"
        if current_nextbet > balance:
            return f"BET_GT_BAL: bet={current_nextbet:.8f} > balance={balance:.8f}"

        # Mode Specific Stop Checks
        if game_mode == 5:
            # Mode 5 (Brave) strict death & profit checks
            if loss_streak >= brave_losses_allowed:
                return f"BUSTED AT BRINK: Reached death point ({brave_losses_allowed} consecutive losses)"
            if brave_stop_profit > 0 and total_profit >= brave_stop_profit:
                return f"SURVIVED & GOAL HIT: Profit reached +{brave_stop_profit:.8f}"
            return ""

        if game_mode == 4:
            # Mode 4 (Custom) isolated checks (No bleeding from Martingale!)
            if c_upper_limit_bal > 0 and balance >= c_upper_limit_bal:
                return f"UPPER LIMIT: balance={balance:.8f} >= {c_upper_limit_bal:.8f}"
            if c_lower_limit_bal > 0 and balance <= c_lower_limit_bal:
                return f"LOWER LIMIT: balance={balance:.8f} <= {c_lower_limit_bal:.8f}"
            if c_stp_after_bets > 0 and round_num >= c_stp_after_bets:
                return f"STOP AFTER BETS: reached {c_stp_after_bets} bets"
            if c_stp_loss_streak > 0 and loss_streak >= c_stp_loss_streak:
                return f"STOP ON LOSS STREAK: {loss_streak} losses in a row"
            if c_stp_loss_tot > 0 and lose_count >= c_stp_loss_tot:
                return f"STOP ON TOTAL LOSSES: {lose_count} losses"
            if c_stp_loss_val_row > 0 and loss_value_streak >= c_stp_loss_val_row:
                return f"STOP ON VALUE LOST IN A ROW: {loss_value_streak:.8f}"
            if c_stp_loss_val_tot > 0 and total_loss_value >= c_stp_loss_val_tot:
                return f"STOP ON TOTAL VALUE LOST: {total_loss_value:.8f}"
            if c_stp_loss_since_max_p > 0 and (max_profit - total_profit) >= c_stp_loss_since_max_p:
                return f"STOP ON LOSS SINCE MAX PROFIT: {(max_profit - total_profit):.8f}"
            if c_stp_win_streak > 0 and win_streak >= c_stp_win_streak:
                return f"STOP ON WIN STREAK: {win_streak} wins in a row"
            if c_stp_win_tot > 0 and win_count >= c_stp_win_tot:
                return f"STOP ON TOTAL WINS: {win_count} wins"
            if c_stp_win_val_row > 0 and win_value_streak >= c_stp_win_val_row:
                return f"STOP ON VALUE WON IN A ROW: {win_value_streak:.8f}"
            if c_stp_win_val_tot > 0 and total_win_value >= c_stp_win_val_tot:
                return f"STOP ON TOTAL VALUE WON: {total_win_value:.8f}"
            if c_stp_win_since_min_p > 0 and (total_profit - min_profit) >= c_stp_win_since_min_p:
                return f"STOP ON WIN SINCE MIN PROFIT: {(total_profit - min_profit):.8f}"
            return ""

        # Mode 1, 2, 3 Checks
        if game_mode == 1:
            if profit_max_loss > 0 and loss_streak >= profit_max_loss:
                return f"MAX_STREAK: {loss_streak} consecutive losses"
            if profit_stop_target > 0 and total_profit >= profit_stop_target:
                return f"PROFIT REACHED: +{profit_stop_target:.8f}"
        elif game_mode in (2, 3):
            if wager_target > 0 and wagered >= wager_target:
                return f"WAGER REACHED: {wager_target:.2f}"

        return ""

    # Live HUD TUI Manager
    hud_rendered_lines = 0

    def print_milestone(msg: str):
        """Emit permanent event line into terminal history, scrolling HUD down."""
        nonlocal hud_rendered_lines
        if quiet:
            milestones.append(_ANSI_REGEX.sub("", msg).strip())
            return
        if hud_rendered_lines > 0:
            sys.stdout.write(f"\033[{hud_rendered_lines}A")
            sys.stdout.write("\033[J")
            hud_rendered_lines = 0
        sys.stdout.write(f"{msg}\n")
        sys.stdout.flush()

    def render_hud(r_num: int, roll: int, result: str, bet: float, mode_played: str, win_amt: float):
        """Render the clean 8-line live HUD in-place."""
        nonlocal hud_rendered_lines
        if quiet:
            return

        bal_fmt = f"{balance:13.8f}"
        bal_c = neg_c(bal_fmt) if start_balance > balance else cn(28, bal_fmt, True)
        icon = pos_c("WIN ") if result == "win" else neg_c("LOSS")
        round_pnl = win_amt if result == "win" else -bet
        round_pnl_c = pos_c(f"+{round_pnl:11.8f}") if round_pnl > 0 else (neg_c(f"{round_pnl:11.8f}") if round_pnl < 0 else _gr(f"{round_pnl:11.8f}"))
        pnl_c = pos_c(f"+{total_profit:11.8f}") if total_profit > 0 else (neg_c(f"{total_profit:11.8f}") if total_profit < 0 else _gr(f"{total_profit:11.8f}"))

        # Roll highlight
        if mode_played == "CUSTOM":
            active_high = int((100.0 - custom_current_chance) * 100)
            active_low = int(custom_current_chance * 100)
            cur_target = active_bet_target
        elif mode_played == "BRAVE":
            active_high, active_low = brave_t_high, brave_t_low
            cur_target = active_bet_target
        elif mode_played == "WAGER":
            active_high, active_low = wager_t_high, wager_t_low
            cur_target = wager_bet_target
        else:
            active_high, active_low = profit_t_high, profit_t_low
            cur_target = profit_bet_target

        if (cur_target == "low" and roll >= active_high) or (cur_target == "high" and roll < active_low):
            roll_c = cn(45, f"{roll:4d}", True)
        else:
            roll_c = cn(245, f"{roll:4d}", False)

        lines: list[str] = []

        if game_mode == 1:
            # Mode 1: PROFIT MODE
            lines.append(make_header_border(cn(208, "PROFIT CHASER HUD", True)))
            r_pct = (r_num / max_rounds) * 100.0 if max_rounds > 0 else 0.0
            l1 = f"{_wc('ROUND')} : {r_num} / {max_rounds} ({r_pct:.1f}%)"
            r1 = f"{_wc('MODE')}   : {cn(208, 'PROFIT', True)} ({profit_win_chance:.2f}% / {profit_payout:.2f}x)"
            lines.append(pad_line(f"{l1}{' ' * max(2, 68 - visual_len(l1) - visual_len(r1))}{r1}"))

            l2 = f"{_wc('ROLL')}  : {roll_c}  [{icon}]"
            r2 = f"{_wc('STREAK')} : {loss_streak} (Max Limit: {profit_max_loss})"
            lines.append(pad_line(f"{l2}{' ' * max(2, 68 - visual_len(l2) - visual_len(r2))}{r2}"))

            lines.append("├" + "─" * 72 + "┤")

            l3 = f"{_wc('CURRENT BET')} : {bet:12.8f}"
            r3 = f"{_wc('BALANCE')} : {bal_c}"
            lines.append(pad_line(f"{l3}{' ' * max(2, 68 - visual_len(l3) - visual_len(r3))}{r3}"))

            l4 = f"{_wc('ROUND PnL')}   : {round_pnl_c}"
            r4 = f"{_wc('NET PnL')} : {pnl_c}"
            lines.append(pad_line(f"{l4}{' ' * max(2, 68 - visual_len(l4) - visual_len(r4))}{r4}"))

            bar = progress_bar(total_profit, profit_stop_target, 16)
            lines.append(pad_line(f"{_wc('TARGET PnL')}  : {total_profit:+.4f} / +{profit_stop_target:.4f} {bar}"))
            lines.append("└" + "─" * 72 + "┘")

        elif game_mode == 2:
            # Mode 2: WAGER MODE
            lines.append(make_header_border(cn(75, "WAGER FARMER HUD", True)))
            r_pct = (r_num / max_rounds) * 100.0 if max_rounds > 0 else 0.0
            l1 = f"{_wc('ROUND')} : {r_num} / {max_rounds} ({r_pct:.1f}%)"
            r1 = f"{_wc('MODE')}   : {cn(75, 'WAGER', True)} ({wager_win_chance:.2f}% / {wager_payout:.2f}x)"
            lines.append(pad_line(f"{l1}{' ' * max(2, 68 - visual_len(l1) - visual_len(r1))}{r1}"))

            w_pct = (win_count / r_num) * 100.0 if r_num > 0 else 0.0
            l2 = f"{_wc('ROLL')}  : {roll_c}  [{icon}]"
            r2 = f"{_wc('W/L')}    : {win_count}W - {lose_count}L ({w_pct:.1f}%)"
            lines.append(pad_line(f"{l2}{' ' * max(2, 68 - visual_len(l2) - visual_len(r2))}{r2}"))

            lines.append("├" + "─" * 72 + "┤")

            l3 = f"{_wc('CURRENT BET')} : {bet:12.8f}"
            r3 = f"{_wc('BALANCE')} : {bal_c}"
            lines.append(pad_line(f"{l3}{' ' * max(2, 68 - visual_len(l3) - visual_len(r3))}{r3}"))

            burn = start_balance - balance
            burn_pct = (burn / start_balance) * 100.0 if start_balance > 0 else 0.0
            burn_str = neg_c(f"-{burn:10.4f} ({burn_pct:.2f}%)") if burn > 0 else pos_c(f"+{-burn:10.4f}")
            l4 = f"{_wc('BURN COST')}   : {burn_str}"
            r4 = f"{_wc('NET PnL')} : {pnl_c}"
            lines.append(pad_line(f"{l4}{' ' * max(2, 68 - visual_len(l4) - visual_len(r4))}{r4}"))

            bar = progress_bar(wagered, wager_target, 16)
            lines.append(pad_line(f"{_wc('WAGER TARGET')}: {wagered:.2f} / {wager_target:.2f} {bar}"))
            lines.append("└" + "─" * 72 + "┘")

        elif game_mode == 3:
            # Mode 3: HYBRID DUAL-ENGINE
            lines.append(make_header_border(cn(46, "HYBRID DUAL-ENGINE", True)))
            if current_mode == "WAGER":
                l1 = f"{_wc('STATE')} : {cn(46, '🟢 WAGERING (Normal)', True)}"
                r1 = f"{_wc('ROUND')}  : {r_num} / {max_rounds}"
                lines.append(pad_line(f"{l1}{' ' * max(2, 68 - visual_len(l1) - visual_len(r1))}{r1}"))

                l2 = f"{_wc('ROLL')}  : {roll_c}  [{icon}]"
                r2 = f"{_wc('STREAK')} : {loss_streak} (W/L: {win_count}W - {lose_count}L)"
                lines.append(pad_line(f"{l2}{' ' * max(2, 68 - visual_len(l2) - visual_len(r2))}{r2}"))

                lines.append("├" + "─" * 72 + "┤")

                vault_s = pos_c(f"+{profit_vault:.8f}") if profit_vault > 0 else _gr(f"{profit_vault:.8f}")
                l3 = f"{_wc('MAIN BAL')}    : {bal_c}"
                r3 = f"{_wc('PROFIT VAULT')} : {vault_s} 🔒"
                lines.append(pad_line(f"{l3}{' ' * max(2, 68 - visual_len(l3) - visual_len(r3))}{r3}"))

                dist = balance - trigger_balance
                dist_s = pos_c(f"+{dist:.4f} (Safe)") if dist > 0 else neg_c(f"{dist:.4f} (Danger)")
                l4 = f"{_wc('TRIGGER LINE')}: {trigger_balance:10.2f} (-{loss_trigger_pct:.1f}%)"
                r4 = f"{_wc('DISTANCE')}     : {dist_s}"
                lines.append(pad_line(f"{l4}{' ' * max(2, 68 - visual_len(l4) - visual_len(r4))}{r4}"))

                bar = progress_bar(wagered, wager_target, 16)
                lines.append(pad_line(f"{_wc('WAGER PROG')}  : {wagered:.2f} / {wager_target:.2f} {bar}"))
            else:
                # Recovery Mode
                l1 = f"{_wc('STATE')} : {cn(196, '🔴 RECOVERING (Profit)', True)}"
                r1 = f"{_wc('ROUND')}  : {r_num} / {max_rounds}"
                lines.append(pad_line(f"{l1}{' ' * max(2, 68 - visual_len(l1) - visual_len(r1))}{r1}"))

                l2 = f"{_wc('ROLL')}  : {roll_c}  [{icon}]"
                r2 = f"{_wc('STREAK')} : {loss_streak} (Martingale)"
                lines.append(pad_line(f"{l2}{' ' * max(2, 68 - visual_len(l2) - visual_len(r2))}{r2}"))

                lines.append("├" + "─" * 72 + "┤")

                vault_s = pos_c(f"+{profit_vault:.8f}") if profit_vault > 0 else _gr(f"{profit_vault:.8f}")
                l3 = f"{_wc('CURRENT BAL')} : {bal_c}"
                r3 = f"{_wc('RECOVERY GOAL')}: {start_balance:.8f}"
                lines.append(pad_line(f"{l3}{' ' * max(2, 68 - visual_len(l3) - visual_len(r3))}{r3}"))

                deficit = start_balance - balance
                l4 = f"{_wc('DEFICIT')}     : {neg_c(f'-{deficit:.8f}')}"
                r4 = f"{_wc('VAULT LOCKED')} : {vault_s} 🔒"
                lines.append(pad_line(f"{l4}{' ' * max(2, 68 - visual_len(l4) - visual_len(r4))}{r4}"))

                needed = max(1e-8, start_balance - trigger_balance)
                recovered_amt = max(0.0, balance - trigger_balance)
                bar = progress_bar(recovered_amt, needed, 16)
                lines.append(pad_line(f"{_wc('RECOVERY')}    : {bar} to Resume Wager"))
            lines.append("└" + "─" * 72 + "┘")

        elif game_mode == 4:
            # Mode 4: CUSTOM MODE
            lines.append(make_header_border(cn(39, "CUSTOM HUNTER HUD", True)))
            len_m = max(1, len(str(max_rounds)))
            r_pct = (r_num / max_rounds) * 100.0 if max_rounds > 0 else 0.0
            l1 = f"{_wc('ROUND')} : {r_num:>{len_m}} / {max_rounds} ({r_pct:5.1f}%)"
            c_payout = (1.0 - (house_edge / 100.0)) / (custom_current_chance / 100.0)
            payout_r = round(c_payout, 2)
            c_payout_s = f"{int(payout_r)}x" if payout_r.is_integer() else f"{payout_r:.2f}x"
            r1 = f"{_wc('MODE')}   : {cn(39, 'CUSTOM', True)} (BET:{active_bet_target.upper():<4} P:{c_payout_s:>4})"
            lines.append(make_fixed_row(l1, r1, 34, 70))

            cur_streak = win_streak if result == "win" else loss_streak
            cur_streak_c = pos_c(f"{cur_streak:>5}") if result == "win" else neg_c(f"{cur_streak:>5}")
            tag_wl = pos_c("[WIN ]") if result == "win" else neg_c("[LOSS]")
            l2 = f" {tag_wl} {_wc('highest STREAK')}: {_wc('WIN')} {pos_c(f'{max_win_streak:>4}')}, {_wc('LOSS')} {neg_c(f'{max_loss_streak:>5}')} │ {_wc('current streak')}: {cur_streak_c}"
            lines.append(pad_line(l2, 70))

            lines.append("├" + "─" * 72 + "┤")

            m4_bal_fmt = f"{balance:>15.8f}"
            m4_bal_c = neg_c(m4_bal_fmt) if start_balance > balance else cn(28, m4_bal_fmt, True)
            m4_pnl_c = pos_c(f"+{total_profit:>14.8f}") if total_profit > 0 else (neg_c(f"{total_profit:>15.8f}") if total_profit < 0 else _gr(f"{total_profit:>15.8f}"))

            l3 = f"{_wc('BET')}   : {bet:14.8f}"
            r3 = f"{_wc('BALANCE')}: {m4_bal_c}"
            lines.append(make_fixed_row(l3, r3, 34, 70))

            chance_r = round(custom_current_chance, 2)
            chance_s = f"{int(chance_r)}%" if chance_r.is_integer() else f"{chance_r:.2f}%"
            l4 = f"{_wc('WINCHANCE')}: {chance_s:>5} , {_wc('Payout')}: {c_payout_s:>4}"
            r4 = f"{_wc('NET PnL')}: {m4_pnl_c}"
            lines.append(make_fixed_row(l4, r4, 34, 70))

            if c_zigzag_every > 0:
                zigzag_s = f"({active_bet_target.upper()} {zigzag_count}/{c_zigzag_every})"
                l5 = f"{_wc('TARGET')}  : {active_bet_target.upper():<4} {zigzag_s}"
            else:
                l5 = f"{_wc('TARGET')}  : {active_bet_target.upper():<4}"
            r5 = f"{_wc('WAGERED')}: {wagered:15.8f}"
            lines.append(make_fixed_row(l5, r5, 34, 70))
            lines.append("└" + "─" * 72 + "┘")

        else:
            # Mode 5: BRAVE MODE (SURVIVOR ENGINE)
            lines.append(make_header_border(cn(196, "BRAVE SURVIVOR HUD", True)))
            r_pct = (r_num / max_rounds) * 100.0 if max_rounds > 0 else 0.0
            l1 = f"{_wc('ROUND')} : {r_num} / {max_rounds} ({r_pct:.1f}%)"
            r1 = f"{_wc('MODE')}   : {cn(196, 'BRAVE', True)} ({brave_win_chance:.2f}% / {brave_payout:.2f}x)"
            lines.append(pad_line(f"{l1}{' ' * max(2, 68 - visual_len(l1) - visual_len(r1))}{r1}"))

            rem_quota = max(0, brave_losses_allowed - loss_streak)
            l2 = f"{_wc('ROLL')}  : {roll_c}  [{icon}]"
            r2 = f"{_wc('STREAK')} : {loss_streak} (Death: ไม้ {brave_losses_allowed})"
            lines.append(pad_line(f"{l2}{' ' * max(2, 68 - visual_len(l2) - visual_len(r2))}{r2}"))

            lines.append("├" + "─" * 72 + "┤")

            l3 = f"{_wc('CURRENT BET')} : {bet:12.8f}"
            r3 = f"{_wc('BALANCE')} : {bal_c}"
            lines.append(pad_line(f"{l3}{' ' * max(2, 68 - visual_len(l3) - visual_len(r3))}{r3}"))

            l4 = f"{_wc('ROUND PnL')}   : {round_pnl_c}"
            r4 = f"{_wc('NET PnL')} : {pnl_c}"
            lines.append(pad_line(f"{l4}{' ' * max(2, 68 - visual_len(l4) - visual_len(r4))}{r4}"))

            gauge_bar = progress_bar(rem_quota, brave_losses_allowed, 16)
            quota_msg = neg_c(f"เหลือโควต้าพลาดอีก {rem_quota:2d} ไม้ ⚠️") if rem_quota <= 5 else pos_c(f"เหลือโควต้าพลาดอีก {rem_quota:2d} ไม้")
            lines.append(pad_line(f"{_wc('SURVIVAL')}    : {gauge_bar} {quota_msg}"))
            lines.append("└" + "─" * 72 + "┘")

        # Reposition and render in-place
        if hud_rendered_lines > 0:
            sys.stdout.write(f"\033[{hud_rendered_lines}A")

        for line in lines:
            sys.stdout.write(f"\r\033[2K{line}\n")
        sys.stdout.flush()
        hud_rendered_lines = len(lines)

    # Print Engine Header (skipped in web-lab headless mode)
    if not quiet:
        print(cn(136, "=" * 74))
        print(cn(255, "  DICE SIMULATOR - MULTI MODE ENGINE (Python)"))
        print(cn(136, "=" * 74))
        if current_mode == "BRAVE":
            print(cn(196, f"  🔥 [BRAVE MODE ACTIVE] Death Point: {brave_losses_allowed} Losses | Mul: {brave_loss_mul:.2f}x", True))
            print(f"  Solved BaseBet: {brave_base_bet:.8f} (Exact Exposure = {start_balance:.8f})")
            print(f"  Win Chance: {brave_win_chance:.2f}% ({brave_payout:.2f}x) | Target: {active_bet_target.upper()} | Goal: +{brave_stop_profit:.8f}")
        elif current_mode == "CUSTOM":
            hunt_mode_badge = cn(226, " [RARE HUNT ON]", True) if is_hunting_rare else ""
            print(f" Mode: CUSTOM{hunt_mode_badge} | Bal: {start_balance:.8f} | Base: {c_base_bet:.8f} | Chance: {c_win_chance:.2f}% | Target: {active_bet_target.upper()}")
            print(f" LossMul: {c_loss_mul:.2f}x (every {c_loss_mul_every}) | WinMul: {c_win_mul:.2f}x (resetBase={bool(c_win_reset_base)})")
            print(f" ZigZag: every {c_zigzag_every} bets | Limits: MinBet={c_min_bet:.8f} MaxBet={c_max_bet:.8f}")
        else:
            print(f" Mode: {current_mode} | Bal: {start_balance:.8f} | Base: {profit_base_bet if current_mode=='PROFIT' else wager_base_bet:.8f}")
            print(f" ProfitWC: {profit_win_chance:.2f}% ({profit_payout:.4f}x) | WagerWC: {wager_win_chance:.2f}% ({wager_payout:.4f}x)")
            print(f" StopProfit: +{profit_stop_target:.8f} | WagerTarget: {wager_target:.2f} | LossTrigger: -{loss_trigger_pct:.1f}%")
        print(cn(136, "=" * 74))

        # Hide cursor during simulation for butter-smooth animation
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    stop_reason = ""
    last_wager_milestone = 0

    try:
        # Main Loop
        while round_num < max_rounds:
            if stop_on_win > 0 and win_count >= stop_on_win:
                stop_reason = f"WIN LIMIT: reached {stop_on_win} wins"
                break

            stop_reason = check_stop_condition(nextbet)
            if stop_reason:
                break

            round_num += 1
            current_bet = nextbet
            round_mode = current_mode

            wagered += current_bet
            last_roll, result = roll_dice(round_mode)

            # Settle Math
            win_amount = 0.0
            round_payout = 0.0

            if round_mode == "BRAVE":
                round_payout = brave_payout
                b_win_multiplier = brave_payout - 1.0
                if result == "win":
                    win_amount = current_bet * b_win_multiplier
                    balance += win_amount
                    total_profit = balance - start_balance
                    win_count += 1
                    win_streak += 1
                    if win_streak > max_win_streak:
                        max_win_streak = win_streak
                    loss_streak = 0
                    if brave_win_reset_base == 1:
                        nextbet = brave_base_bet
                    else:
                        nextbet = current_bet
                else:
                    balance -= current_bet
                    total_profit = balance - start_balance
                    win_streak = 0
                    loss_streak += 1
                    lose_count += 1
                    if loss_streak > max_loss_streak:
                        max_loss_streak = loss_streak
                    nextbet = current_bet * brave_loss_mul

            elif round_mode == "CUSTOM":
                c_payout = (1.0 - (house_edge / 100.0)) / (custom_current_chance / 100.0)
                round_payout = c_payout
                c_win_multiplier = c_payout - 1.0
                if result == "win":
                    win_amount = current_bet * c_win_multiplier
                    balance += win_amount
                    total_profit = balance - start_balance
                    max_profit = max(max_profit, total_profit)
                    min_profit = min(min_profit, total_profit)

                    win_count += 1
                    win_streak += 1
                    if win_streak > max_win_streak:
                        max_win_streak = win_streak
                    loss_streak = 0
                    loss_value_streak = 0.0
                    win_value_streak += win_amount
                    total_win_value += win_amount
                    loss_since_last_mul = 0
                    custom_current_chance = c_win_chance

                    if c_win_reset_base == 1:
                        nextbet = c_base_bet
                    else:
                        nextbet = current_bet * c_win_mul

                    # On Win Reset Triggers
                    if c_rst_win_streak > 0 and win_streak % c_rst_win_streak == 0:
                        nextbet = c_base_bet
                    if c_rst_win_tot_every > 0 and win_count % c_rst_win_tot_every == 0:
                        nextbet = c_base_bet
                    if c_rst_win_val_row > 0 and win_value_streak >= c_rst_win_val_row:
                        nextbet = c_base_bet
                        win_value_streak = 0.0
                    if c_rst_win_val_tot_every > 0 and total_win_value >= c_rst_win_val_tot_every:
                        nextbet = c_base_bet
                    if c_rst_win_since_min_p > 0 and (total_profit - min_profit) >= c_rst_win_since_min_p:
                        nextbet = c_base_bet
                else:
                    balance -= current_bet
                    total_profit = balance - start_balance
                    max_profit = max(max_profit, total_profit)
                    min_profit = min(min_profit, total_profit)

                    win_streak = 0
                    win_value_streak = 0.0
                    loss_streak += 1
                    lose_count += 1
                    loss_value_streak += current_bet
                    total_loss_value += current_bet
                    loss_since_last_mul += 1
                    if loss_streak > max_loss_streak:
                        max_loss_streak = loss_streak

                    # Multiplier calculation
                    if c_loss_reset_first == 1 and loss_streak == 1:
                        nextbet = c_base_bet
                    elif loss_since_last_mul >= c_loss_mul_every:
                        nextbet = current_bet * c_loss_mul
                        loss_since_last_mul = 0
                    else:
                        nextbet = current_bet

                    # Dynamic changes after streak
                    if c_loss_chg_bet_streak > 0 and loss_streak >= c_loss_chg_bet_streak:
                        nextbet = c_loss_chg_bet_val
                    if c_loss_chg_chance_streak > 0 and loss_streak >= c_loss_chg_chance_streak:
                        custom_current_chance = c_loss_chg_chance_val

                    # On Loss Reset Triggers
                    if c_rst_loss_streak > 0 and loss_streak % c_rst_loss_streak == 0:
                        nextbet = c_base_bet
                    if c_rst_loss_tot_every > 0 and lose_count % c_rst_loss_tot_every == 0:
                        nextbet = c_base_bet
                    if c_rst_loss_val_row > 0 and loss_value_streak >= c_rst_loss_val_row:
                        nextbet = c_base_bet
                        loss_value_streak = 0.0
                    if c_rst_loss_val_tot_every > 0 and total_loss_value >= c_rst_loss_val_tot_every:
                        nextbet = c_base_bet
                    if c_rst_loss_since_max_p > 0 and (max_profit - total_profit) >= c_rst_loss_since_max_p:
                        nextbet = c_base_bet

                # General Reset Triggers
                if c_rst_after_bets > 0 and round_num % c_rst_after_bets == 0:
                    nextbet = c_base_bet

                # Min / Max Bet Cap
                if c_min_bet > 0 and nextbet < c_min_bet:
                    nextbet = c_min_bet
                if c_max_bet > 0 and nextbet > c_max_bet:
                    nextbet = c_max_bet

                # Zig-Zag Toggle
                if c_zigzag_every > 0:
                    zigzag_count += 1
                    if zigzag_count >= c_zigzag_every:
                        active_bet_target = "low" if active_bet_target == "high" else "high"
                        zigzag_count = 0

            elif round_mode == "WAGER":
                round_payout = wager_payout
                if result == "win":
                    win_amount = current_bet * wager_win_mul
                    balance += win_amount
                    total_profit = (balance - start_balance) + profit_vault
                    nextbet = wager_base_bet
                    loss_streak = 0
                    win_count += 1
                    win_streak += 1
                    if win_streak > max_win_streak:
                        max_win_streak = win_streak
                else:
                    balance -= current_bet
                    nextbet = wager_base_bet
                    total_profit = (balance - start_balance) + profit_vault
                    win_streak = 0
                    loss_streak += 1
                    lose_count += 1
                    if loss_streak > max_loss_streak:
                        max_loss_streak = loss_streak
            else:  # PROFIT Mode (Martingale)
                round_payout = profit_payout
                if result == "win":
                    win_amount = current_bet * profit_win_mul
                    balance += win_amount
                    total_profit = (balance - start_balance) + profit_vault
                    nextbet = profit_base_bet
                    loss_streak = 0
                    win_count += 1
                    win_streak += 1
                    if win_streak > max_win_streak:
                        max_win_streak = win_streak
                else:
                    balance -= current_bet
                    nextbet = current_bet * profit_lose_mul
                    total_profit = (balance - start_balance) + profit_vault
                    win_streak = 0
                    loss_streak += 1
                    lose_count += 1
                    if loss_streak > max_loss_streak:
                        max_loss_streak = loss_streak

            if result == "win":
                win_history.append((win_amount, round_num, round_mode))

            # Mode Transition Check with Profit Vault Skimming (Hybrid Mode 3)
            if game_mode == 3:
                if current_mode == "WAGER":
                    if balance <= trigger_balance:
                        print_milestone(cn(196, f"  [EVENT #{round_num:>4d}] 🚨 [MODE SWITCH] Dropped below trigger -> RECOVERY", True))
                        current_mode = "PROFIT"
                        nextbet = profit_base_bet
                        loss_streak = 0
                elif current_mode == "PROFIT":
                    recovered = False
                    if result == "win" and balance >= start_balance:
                        recovered = True
                    elif balance >= trigger_balance_profit:
                        recovered = True

                    if recovered:
                        surplus = balance - start_balance
                        profit_vault += surplus
                        balance = start_balance
                        total_profit = profit_vault

                        print_milestone(cn(46, f"  [EVENT #{round_num:>4d}] 🎯 [CAPITAL RECOVERED] Secured +{surplus:.8f} to Vault", True))
                        current_mode = "WAGER"
                        nextbet = wager_base_bet
                        loss_streak = 0

            # Check Rare Number Hit
            rare_hit_tag = check_rare_number(last_roll, round_num, current_bet, win_amount, result)

            # Record to CSV
            rnd_pnl = win_amount if result == "win" else -current_bet
            csv_writer.writerow([
                round_num, round_mode, last_roll, result,
                f"{current_bet:.8f}", f"{rnd_pnl:.8f}", f"{total_profit:.8f}",
                f"{balance:.8f}", loss_streak, rare_hit_tag or "", f"{win_amount:.8f}"
            ])
            csv_fp.flush()

            # Bet History Feed Emits (Strictly <= 74 chars: Round, Roll Result, Bet Amount, Win/Lose Amount)
            if rare_hit_tag:
                win_s = f"+{win_amount:.8f}"
                print_milestone(cn(226, f"  [#{round_num:>6d}] 🎯 {rare_hit_tag:<4s} │ Roll: {last_roll:>4d} │ Bet: {current_bet:>12.8f} │ Win:  {win_s:>13s}", True))
            elif result == "win":
                win_s = f"+{win_amount:.8f}"
                print_milestone(pos_c(f"  [#{round_num:>6d}] 🏆 WIN  │ Roll: {last_roll:>4d} │ Bet: {current_bet:>12.8f} │ Win:  {win_s:>13s}"))
            else:
                loss_s = f"-{current_bet:.8f}"
                print_milestone(neg_c(f"  [#{round_num:>6d}] 💀 LOSS │ Roll: {last_roll:>4d} │ Bet: {current_bet:>12.8f} │ Lose: {loss_s:>13s}"))

            if game_mode == 2 and wager_target > 0:
                current_wager_pct = int((wagered / wager_target) * 100)
                if current_wager_pct >= last_wager_milestone + 25:
                    last_wager_milestone = (current_wager_pct // 25) * 25
                    print_milestone(cn(141, f"  [MILESTONE #{round_num:>6d}] 🏁 Wager reached {last_wager_milestone}% ({wagered:.2f} / {wager_target:.2f})", True))
            elif loss_streak > 0 and loss_streak % 25 == 0:
                print_milestone(cn(208, f"  [ALERT #{round_num:>6d}] ⚠️  Streak Alert: {loss_streak} consecutive losses", True))

            # Update Live HUD
            render_hud(round_num, last_roll, result, current_bet, round_mode, win_amount)

            if round_delay > 0:
                time.sleep(round_delay)

    finally:
        # Restore terminal cursor & flush CSV
        if not quiet:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        try:
            csv_fp.close()
        except Exception:
            pass

    # Headless summary for the web lab: one machine-readable line.
    if quiet:
        import json as _json
        top5 = [
            {"amount": amt, "round": r_num, "mode": r_mode}
            for amt, r_num, r_mode in sorted(win_history, key=lambda x: x[0], reverse=True)[:5]
        ]
        result = {
            "mode": game_mode,
            "engine_mode": current_mode,
            "rounds": round_num,
            "wins": win_count,
            "losses": lose_count,
            "max_loss_streak": max_loss_streak,
            "max_win_streak": max_win_streak,
            "start_balance": start_balance,
            "balance": balance,
            "profit_vault": profit_vault,
            "net_pnl": total_profit,
            "wagered": wagered,
            "stop_reason": stop_reason,
            "seed": getattr(args, "seed", None),
            "top_wins": top5,
            "rare_hits": [
                {"round": r[0], "roll": r[1], "tag": r[2], "bet": r[3], "won": r[4]}
                for r in rare_hits_history
            ],
            "rare_counts": rare_counts,
            "events": milestones[-40:],
        }
        print("__RESULT_JSON__" + _json.dumps(result))
        return

    # Summary
    if total_profit > 0:
        profit_c = pos_c(f"+{total_profit:.8f}")
        bal_c = pos_c(f"{balance:.8f}")
    elif total_profit < 0:
        profit_c = neg_c(f"{total_profit:.8f}")
        bal_c = neg_c(f"{balance:.8f}")
    else:
        profit_c = _gr(f"{total_profit:.8f}")
        bal_c = _gr(f"{balance:.8f}")

    wagered_c = cn(245, f"{wagered:.8f}", True)
    vault_c = pos_c(f"+{profit_vault:.8f}")

    print()
    print(cn(136, "=" * 74))
    print(cn(255, "  SESSION SUMMARY"))
    print(cn(136, "=" * 74))
    print(
        f"  {_wc('Rounds')}: {round_num}  {pos_c('W')}: {win_count}  "
        f"{neg_c('L')}: {lose_count}  {_wc('MaxLossStreak')}: {max_loss_streak}  "
        f"{_wc('MaxWinStreak')}: {max_win_streak}"
    )
    print(f"  {_wc('Active Balance')}: {bal_c}")
    print(f"  {_wc('Profit Vault')}:   {vault_c}")
    print(f"  {_wc('Net Total PnL')}:  {profit_c}")

    if game_mode in (2, 3) and wager_target > 0:
        print(f"  {_wc('Wagered')}:        {wagered_c} / {wager_target:.2f}")
    else:
        print(f"  {_wc('Wagered')}:        {wagered_c}")

    if total_profit > 0:
        print(pos_c("  Result: PROFIT"))
    elif total_profit < 0:
        print(neg_c("  Result: LOSS"))
    else:
        print(_gr("  Result: BREAK EVEN"))

    if stop_reason:
        print(cn(45, f"  Stop Reason: {stop_reason}"))

    print(cn(136, "=" * 74))
    print(f"  {pos_c('TOP 5 BIGGEST WINS')}")
    print(cn(136, "=" * 74))
    if win_history:
        top5 = sorted(win_history, key=lambda x: x[0], reverse=True)[:5]
        for rank, (amt, r_num, r_mode) in enumerate(top5, 1):
            if r_mode == "BRAVE":
                w_mode_c = cn(196, r_mode, True)
            elif r_mode == "CUSTOM":
                w_mode_c = cn(39, r_mode, True)
            elif r_mode == "PROFIT":
                w_mode_c = cn(208, r_mode, True)
            else:
                w_mode_c = cn(75, r_mode, True)
            print(f"  #{rank}. {pos_c(f'+{amt:12.8f}')} | {_wc(f'Round {r_num}')} | {w_mode_c}")
    else:
        print(f"  {_gr('No wins recorded.')}")

    # Rare Numbers Detailed Log (ONLY displayed if hunting rare mode is enabled)
    if is_hunting_rare:
        print(cn(136, "=" * 74))
        print(f"  {pos_c('🎯 RARE NUMBER HITS DETAIL')}")
        print(cn(136, "=" * 74))
        if rare_hits_history:
            for idx, rh in enumerate(rare_hits_history, 1):
                r_num_h, roll_h, tag_h, bet_h, win_h, bal_h = rh
                print(f"  #{idx:>2d}. {cn(226, tag_h, True):<8s} │ Rnd:{r_num_h:>4d} │ Roll:{roll_h:>4d} │ Bet:{bet_h:11.8f} │ Won:{pos_c(f'+{win_h:10.8f}')}")
        else:
            print(f"  {_gr('No rare number hits recorded this session.')}")

        print(cn(136, "=" * 74))
        print(f"  {pos_c('Rare Number Counts')}")
        print(cn(136, "=" * 74))
        for key, val in rare_counts.items():
            print(f"  {_wc(key)}: {val}")
        print(f"  {pos_c('wrong_side')}: {wrong_side}")

    print(cn(136, "=" * 74))
    print(cn(39, f"  📁 Full session history saved to: logs/dice_session_latest.csv"))
    print(cn(136, "=" * 74))


# ─────────────────────────────────────────
# [CALC] BASEBET CALCULATOR
# ─────────────────────────────────────────
def calc_basebet():
    """
    Optimal BaseBet Calculator.
    Formula: BaseBet = Balance * (mul - 1) / (mul^N - 1)
    Default N is derived from: P(N consecutive losses) < risk_threshold
    => N = ceil(log(risk) / log(1 - win_chance))
    """
    env_cfg = load_env_config()
    def cfg_val(key: str, default, cast_type=str):
        if key in env_cfg and env_cfg[key] != "":
            try:
                return cast_type(env_cfg[key])
            except (ValueError, TypeError):
                pass
        return default

    def_bal = cfg_val("START_BALANCE", 10000.0, float)
    def_mul = cfg_val("BRAVE_LOSS_MUL", cfg_val("CUSTOM_LOSS_MUL", 1.06, float), float)
    def_chance = cfg_val("BRAVE_WIN_CHANCE", cfg_val("GLOBAL_WIN_CHANCE", 3.96, float), float)

    parser = argparse.ArgumentParser(
        description="BaseBet Calculator — find the safe bet size to survive N losses",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n"
               "  Auto N by Risk:    roll.py calc -b 10000 -m 2.0 -c 49.5 --risk 0.0001\n"
               "  Manual Target N:   roll.py calc -b 10000 -m 1.06 -c 3.96 -n 50\n"
               "  Save to dice.env:  roll.py calc -b 10000 -m 1.06 -c 3.96 -n 50 --save\n"
    )
    parser.add_argument("--balance",     "-b",  type=float, default=def_bal,
                        help="Starting balance")
    parser.add_argument("--mul",         "-m",  type=float, default=def_mul,
                        help="Loss multiplier (e.g. 1.06 for Brave, 2.0 for Martingale)")
    parser.add_argument("--chance",      "-c",  type=float, default=def_chance,
                        help="Win chance %% (e.g. 49.5 for 49.5%%, 3.96 for 3.96%%)")
    parser.add_argument("--max-loss-n",  "-n",  type=int,   default=None,
                        help="Manual max consecutive losses (จุดพัง N). If omitted, N is auto-solved from --risk")
    parser.add_argument("--risk",        "-r",  type=float, default=0.001,
                        help="Acceptable streak risk prob for auto N (default: 0.001 = 0.1%%, e.g. 0.0001 = 0.01%%)")
    parser.add_argument("--coverage",    "-cov", type=float, default=1.0,
                        help="Fraction of balance to use as coverage (default: 1.0 = 100%%, 0.8 = 80%%)")
    parser.add_argument("--save",        action="store_true",
                        help="Save calculated basebet into config/dice.env")
    args = parser.parse_args()

    balance      = args.balance
    mul          = args.mul
    win_chance_p = args.chance / 100.0
    loss_p       = 1.0 - win_chance_p
    risk         = args.risk
    coverage     = args.coverage

    if args.max_loss_n is not None:
        n_user = args.max_loss_n
        n_auto = None
    else:
        if loss_p >= 1.0:
            n_auto = 999
        else:
            n_auto = math.ceil(math.log(risk) / math.log(loss_p))
        n_user = None

    n_cover = n_user if n_user is not None else n_auto

    def basebet_for(n: int, bal: float, m: float) -> float:
        if m == 1.0:
            return (bal * coverage) / n
        try:
            log_mn = n * math.log(m)
            if log_mn > 700:
                log_basebet = math.log(bal * coverage * (m - 1.0)) - log_mn
                return math.exp(log_basebet)
            denom = math.exp(log_mn) - 1.0
            if denom <= 0:
                return 0.0
            return (bal * coverage * (m - 1.0)) / denom
        except (OverflowError, ValueError):
            return 0.0

    def total_exposure(n: int, base: float, m: float) -> float:
        if m == 1.0:
            return base * n
        try:
            mn = math.exp(n * math.log(m)) if n * math.log(m) < 700 else float("inf")
            return base * (mn - 1.0) / (m - 1.0)
        except (OverflowError, ValueError):
            return float("inf")

    sep = cn(136, "=" * 74)

    print()
    print(sep)
    print(cn(255, "  BASEBET CALCULATOR (Risk & Survival Solver)", True))
    print(sep)
    print(f"  {_wc('Balance')}:       {pos_c(f'{balance:.8f}')}"
          f"  {_wc('Coverage')}:    {cn(220, f'{coverage*100:.1f}%', True)}")
    print(f"  {_wc('Multiplier')}:    {cn(220, f'{mul:.5f}x', True)}"
          f"  {_wc('Win Chance')}: {cn(220, f'{args.chance:.4f}%', True)}")
    print(f"  {_wc('Loss Prob')}:     {cn(220, f'{loss_p*100:.4f}%', True)}")
    print(sep)

    # Auto N info
    if n_auto is not None:
        streak_prob = loss_p ** n_auto
        print(f"  {_wc('Risk Threshold')}:    {cn(208, f'{risk*100:.3f}%', True)}"
              f"  (1 in {cn(220, f'{1/risk:,.0f}', True)} sessions)")
        print(f"  {_wc('Auto N (math)')}:     {cn(46, str(n_auto), True)}"
              f"  {_gr(f'(actual streak prob = {streak_prob:.6%})')}")
    else:
        streak_prob = loss_p ** n_user
        print(f"  {_wc('Target N (จุดพัง)')}:  {cn(46, str(n_user), True)} ไม้"
              f"  {_gr(f'(streak prob = {streak_prob:.6%})')}")

    print(sep)

    def fmt_val(v: float, width: int = 18) -> str:
        if v == 0.0:
            return f"{'0.00000000':>{width}}"
        if v != float("inf") and (abs(v) < 1e-7 or abs(v) > 1e15):
            return f"{v:>{width}.6e}"
        return f"{v:>{width}.8f}"

    MIN_PRACTICAL_BET = 1e-8

    if mul == 1.0:
        max_coverable_n = int(balance * coverage / MIN_PRACTICAL_BET)
    else:
        try:
            max_n_float = math.log(balance * coverage * (mul - 1.0) / MIN_PRACTICAL_BET + 1.0) / math.log(mul)
            max_coverable_n = int(max_n_float)
        except (ValueError, ZeroDivisionError):
            max_coverable_n = 0

    base = basebet_for(n_cover, balance, mul)
    exposure = total_exposure(n_cover, base, mul)
    exp_pct = f"{(exposure/balance)*100:.2f}%" if exposure != float("inf") else "∞"
    is_feasible = base >= MIN_PRACTICAL_BET

    if not is_feasible:
        print(cn(196, "  ╔══════════════════════════════════════════════════════════════════╗", True))
        print(cn(196, f"  ║  ⛔  BALANCE INSUFFICIENT TO COVER THIS STRATEGY               ║", True))
        print(cn(196, "  ╚══════════════════════════════════════════════════════════════════╝", True))
        print()
        print(f"  {_wc('Requested N')}:         {cn(196, str(n_cover), True)}"
              f"  {_gr(f'(requires BaseBet = {fmt_val(base).strip()})')}")
        print(f"  {_wc('Min Practical Bet')}:  {cn(220, f'{MIN_PRACTICAL_BET:.8f}', True)}")
        print()
        print(cn(208, f"  ⚠  Your balance of {balance:.8f} can only support up to:", True))
        print()
        rec_base = basebet_for(max_coverable_n, balance, mul)
        print(f"  {pos_c('>>> Max Coverable N')}:  {cn(46, str(max_coverable_n), True)}"
              f"  {_gr(f'(streak prob = {loss_p**max_coverable_n:.6%})')}")
        print(f"  {pos_c('>>> Recommended BaseBet')}: {cn(226, fmt_val(rec_base).strip(), True)}")
        print()
        print(cn(245, "  Tip: Lower the multiplier, reduce N, or increase your balance.", False))
        print()
        n_cover = max_coverable_n
        base = rec_base
        exposure = total_exposure(n_cover, base, mul)
        exp_pct = f"{(exposure/balance)*100:.2f}%" if exposure != float("inf") else "∞"
    else:
        print(f"  {_wc('Cover N Losses')}:   {cn(46, str(n_cover), True)} ไม้")
        print(f"  {pos_c('>>> Solved BaseBet')}:   {cn(226, fmt_val(base).strip(), True)}")
        print(f"  {_wc('Max Exposure')}:     {cn(208, fmt_val(exposure).strip(), True)}"
              f"  {_gr(f'({exp_pct} of balance)')}")

    # Save flag option
    if args.save:
        repo_root = Path(__file__).resolve().parent.parent
        env_p = repo_root / "config" / "dice.env"
        if env_p.is_file():
            content = env_p.read_text(encoding="utf-8")
            content = re.sub(r"GLOBAL_BASE_BET=[0-9.]*", f"GLOBAL_BASE_BET={base:.8f}", content)
            content = re.sub(r"CUSTOM_BASE_BET=[0-9.]*", f"CUSTOM_BASE_BET={base:.8f}", content)
            content = re.sub(r"BRAVE_LOSSES_ALLOWED=[0-9]*", f"BRAVE_LOSSES_ALLOWED={n_cover}", content)
            content = re.sub(r"BRAVE_LOSS_MUL=[0-9.]*", f"BRAVE_LOSS_MUL={mul:.4f}", content)
            content = re.sub(r"BRAVE_WIN_CHANCE=[0-9.]*", f"BRAVE_WIN_CHANCE={args.chance:.2f}", content)
            env_p.write_text(content, encoding="utf-8")
            print(pos_c(f"\n  💾 Auto-saved Solved BaseBet ({base:.8f}) & N ({n_cover}) to config/dice.env!"))

    # Bet progression table for N_cover
    print(sep)
    print(f"  {_wc('Bet Progression (consecutive losses)')}"
          f"  {_gr(f'[BaseBet={fmt_val(base).strip()} | Mul={mul}x]')}")
    print(sep)
    acc = 0.0
    b = base
    limit = min(n_cover, 20)
    for i in range(1, limit + 1):
        acc += b
        b_c = neg_c(fmt_val(b)) if b > balance * 0.1 else cn(245, fmt_val(b), False)
        acc_c = neg_c(fmt_val(acc)) if acc >= balance else cn(220, fmt_val(acc), False)
        print(f"  Loss #{i:>3d}: Bet = {b_c} | Cumulative = {acc_c}")
        b *= mul
    if n_cover > 20:
        print(f"  {_gr(f'  ... ({n_cover - 20} more levels, showing first 20 only)')}")

    print(sep)
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "calc":
        sys.argv.pop(1)
        calc_basebet()
    else:
        run_simulation()