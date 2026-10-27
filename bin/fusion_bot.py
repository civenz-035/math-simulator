#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  💎 FUSION BOT v4.1 — Python Port (แบบ A: แยก Profit + Reset)  ║
║  Ported from DICE.lua by FUSION BOT engine                      ║
║  Live ANSI Dashboard · CSV Log · SSOT config/dice.env           ║
╚══════════════════════════════════════════════════════════════════╝

Strategies:
  --mode 1  WAGER FOCUS + RECOVERY  (default)
  --mode 2  PROFIT FOCUS (pure Martingale)

Usage:
  python bin/fusion_bot.py                         # defaults from dice.env
  python bin/fusion_bot.py --mode 2 --rounds 5000
  python bin/fusion_bot.py --balance 10000 --rounds 2000 --delay 0.05
  python bin/fusion_bot.py --seed 42 --quiet
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import random
import re
import signal
import sys
import time
import unicodedata

# ── UTF-8 stdout/stderr (Windows box-drawing fix) ──────────────────────────
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ── Graceful stop ───────────────────────────────────────────────────────────
_user_stop: bool = False

def _handle_sigint(sig, frame):
    global _user_stop
    _user_stop = True

signal.signal(signal.SIGINT, _handle_sigint)

# ══════════════════════════════════════════════════════════════════
# [0]  ANSI / TUI HELPERS  (identical style to roll.py)
# ══════════════════════════════════════════════════════════════════
def cn(code: int, text: str, bold: bool = False) -> str:
    style = "1;" if bold else ""
    return f"\033[{style}38;5;{code}m{text}\033[0m"

def _wc(t):   return cn(255, str(t), True)
def _gr(t):   return cn(240, str(t))
def _dim(t):  return cn(238, str(t))
def pos_c(t): return cn(82,  str(t), True)
def neg_c(t): return cn(196, str(t), True)
def yel_c(t): return cn(220, str(t), True)
def cya_c(t): return cn(51,  str(t), True)
def pur_c(t): return cn(171, str(t), True)
def blu_c(t): return cn(75,  str(t), True)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def visual_len(s: str) -> int:
    clean = _ANSI_RE.sub("", s)
    w = 0
    for c in clean:
        w += 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
    return w


def pad_line(content: str, target_w: int = 70) -> str:
    pad = max(0, target_w - visual_len(content))
    return f"│ {content}{' ' * pad} │"


def col_row(left: str, right: str, lw: int = 34, total: int = 70) -> str:
    l_pad = max(0, lw - visual_len(left))
    r_pad = max(0, (total - lw) - visual_len(right))
    return pad_line(f"{left}{' ' * l_pad}{right}{' ' * r_pad}", total)


def header_line(title: str, width: int = 72) -> str:
    tl = visual_len(title)
    inner = max(0, width - tl - 2)
    l = inner // 2; r = inner - l
    return f"┌{'─' * l} {title} {'─' * r}┐"


def footer_line(width: int = 72) -> str:
    return "└" + "─" * (width - 2) + "┘"


def progress_bar(val: float, total: float, width: int = 18) -> str:
    pct = max(0.0, min(1.0, val / total)) if total > 0 else 0.0
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:5.1f}%"


# ══════════════════════════════════════════════════════════════════
# [1]  CONFIG LOADER  (SSOT: config/dice.env)
# ══════════════════════════════════════════════════════════════════
_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?}|\$(\w+)")


def load_env_config() -> dict[str, str]:
    cfg: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parent.parent
    env_override = os.environ.get("DICE_CONFIG")
    env_path = Path(env_override) if env_override else repo_root / "config" / "dice.env"

    if env_path.is_file():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.split("#", 1)[0].strip().strip("\"'")
                    cfg[k.strip()] = v

    for k, v in os.environ.items():
        if k in cfg or any(k.startswith(p) for p in (
                "FUSION_", "WAGER_", "PROFIT_", "BRAVE_", "GLOBAL_", "CUSTOM_")):
            cfg[k] = v

    for _ in range(5):
        changed = False
        for key in list(cfg):
            val = cfg[key]
            new = _ENV_REF_RE.sub(
                lambda m: cfg.get(m.group(1) or m.group(2), "")
                          or os.environ.get(m.group(1) or m.group(2), ""),
                val,
            )
            if new != val:
                cfg[key] = new; changed = True
        if not changed:
            break
    return cfg


def _cv(cfg: dict[str, str], key: str, default, cast=str):
    if key in cfg and cfg[key] != "":
        try:
            return cast(cfg[key])
        except (ValueError, TypeError):
            pass
    return default


# ══════════════════════════════════════════════════════════════════
# [2]  ARGUMENT PARSER
# ══════════════════════════════════════════════════════════════════
def parse_args(cfg: dict[str, str]):
    p = argparse.ArgumentParser(
        description="💎 FUSION BOT v4.1 — Python Simulator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode",    "-m", type=int, choices=[1, 2],
                   default=_cv(cfg, "FUSION_MAIN_MODE", 1, int),
                   help="1=WAGER FOCUS+RECOVERY  2=PROFIT FOCUS")
    p.add_argument("--balance", "-b", type=float,
                   default=_cv(cfg, "START_BALANCE", 10_000.0, float),
                   help="Starting balance")
    p.add_argument("--rounds",  "-r", type=int,
                   default=_cv(cfg, "GLOBAL_MAX_ROUNDS", 100_000, int),
                   help="Maximum rounds to simulate")
    p.add_argument("--delay",   "-d", type=float,
                   default=_cv(cfg, "GLOBAL_ROUND_DELAY", 0.0, float),
                   help="Delay in seconds between rounds")
    p.add_argument("--seed",          type=int, default=None,
                   help="RNG seed for reproducible runs")
    p.add_argument("--quiet",   "-q", action="store_true",
                   help="Headless mode — emit __RESULT_JSON__ at end")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════
# [3]  FUSION BOT MATH ENGINE
# ══════════════════════════════════════════════════════════════════
def random_chance(chance_min: float, chance_max: float) -> float:
    c = random.uniform(chance_min, chance_max)
    return max(0.01, min(99.0, c))


def get_payout_and_multiplier(
    chance_pct: float,
    bonus_pct: float,
    use_house_edge: bool,
    house_edge: float = 1.0,
) -> tuple[float, float]:
    """(multiplier, payout_ratio) — matches Lua getAutoMultiplierByChance()."""
    cd = max(0.0001, min(0.9999, chance_pct / 100.0))
    if use_house_edge and house_edge > 0:
        payout = (1.0 - house_edge / 100.0) / cd
    else:
        payout = 0.99 / cd
    if payout <= 1.0:
        payout = 1.0001
    multiplier = 1.0 + (1.0 + bonus_pct / 100.0) / (payout - 1.0)
    return multiplier, payout


def get_constant_divisor(
    chance_ref: float, bonus_pct: float, losses: int,
    use_house_edge: bool, house_edge: float = 1.0,
) -> float:
    mul, _ = get_payout_and_multiplier(chance_ref, bonus_pct, use_house_edge, house_edge)
    total = 0.0
    for i in range(losses):
        total += mul ** i
    return total


def solve_base_bet(
    cycle_start_balance: float, chance_ref: float, bonus_pct: float,
    losses: int, min_bet: float, use_house_edge: bool, house_edge: float = 1.0,
) -> tuple[float, float]:
    d = get_constant_divisor(chance_ref, bonus_pct, losses, use_house_edge, house_edge)
    base = cycle_start_balance / d if d > 0 else min_bet
    base = max(base, min_bet)
    return base, d


# ══════════════════════════════════════════════════════════════════
# [4]  CSV LOGGER
# ══════════════════════════════════════════════════════════════════
def _get_csv_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "dice_session_latest.csv"


def _init_csv(path: Path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "Round", "Mode", "Result", "Bet", "RoundPnL",
            "NetPnL", "Balance", "LossStreak", "ProfitVault",
        ])


def _log_csv(
    path: Path, rnd: int, mode: str, result: str,
    bet: float, round_pnl: float, net_pnl: float,
    balance: float, streak: int, vault: float,
):
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                rnd, mode, result,
                f"{bet:.8f}", f"{round_pnl:.8f}", f"{net_pnl:.8f}",
                f"{balance:.8f}", streak, f"{vault:.8f}",
            ])
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════════
# [5]  LIVE HUD RENDERER
# ══════════════════════════════════════════════════════════════════
def render_hud(
    *,
    rnd: int, max_rnd: int, mode: str, main_mode: int,
    balance: float, start_balance: float, working_balance: float,
    profit_vault: float, cycle_profit: float, total_profit: float,
    next_bet: float, chance: float,
    win_count: int, lose_count: int, loss_streak: int, max_loss_streak: int,
    total_wagered: float, wager_target: float,
    wager_cycle_start: float, profit_cycle_start: float,
    wager_loss_amount: float, recover_needed: float, current_gain: float,
    allowed_losses: int, consecutive_losses: int,
    loss_cut_pct: float, current_loss_pct: float,
    runtime: float, base_bet: float, divisor: float,
    recover_profit_pct: float, original_cycle_balance: float,
) -> list[str]:
    W = 70

    strat_str = (
        cn(82, "WAGER FOCUS+RECOVERY", True) if main_mode == 1
        else cn(220, "PROFIT FOCUS", True)
    )
    mode_col = cn(82, mode, True) if mode == "WAGER" else cn(220, mode, True)
    pnl_c    = pos_c if total_profit >= 0 else neg_c
    vault_c  = pos_c if profit_vault > 0 else _gr

    round_pb = progress_bar(rnd, max_rnd, 16)
    wager_pb = progress_bar(min(total_wagered, wager_target), wager_target, 16) if wager_target > 0 else "N/A"

    lines: list[str] = [
        header_line(f"💎 FUSION BOT v4.1  #{cn(255,str(rnd),True)}/{cn(240,str(max_rnd))}", W + 2),
        col_row(
            f"⏱  {_wc(f'{runtime:.0f}s')}  {strat_str}",
            f"Mode: {mode_col}", 38, W,
        ),
        pad_line("─" * W, W),
        col_row(
            f"💰 Working: {_wc(f'{working_balance:.8f}')}",
            f"Start: {_gr(f'{start_balance:.4f}')}", 38, W,
        ),
        col_row(
            f"💎 Vault:   {vault_c(f'{profit_vault:.8f}')}",
            f"Cycle Δ: {pnl_c(f'{cycle_profit:+.8f}')}", 38, W,
        ),
        col_row(
            f"🎁 Total P/L: {pnl_c(f'{total_profit:+.8f}')}",
            f"ROI: {pnl_c(f'{total_profit/start_balance*100:+.2f}%')}", 38, W,
        ),
        pad_line("─" * W, W),
        col_row(
            f"🎲 Next Bet: {yel_c(f'{next_bet:.8f}')}",
            f"Chance: {cya_c(f'{chance:.2f}%')}", 38, W,
        ),
        col_row(
            f"📊 Base:     {_gr(f'{base_bet:.8f}')}",
            f"Divisor: {_gr(f'{divisor:.2f}')}", 38, W,
        ),
        pad_line("─" * W, W),
        col_row(
            f"🏆 W/L: {pos_c(str(win_count))}/{neg_c(str(lose_count))}",
            f"Streak: {neg_c(str(loss_streak))} max:{_gr(str(max_loss_streak))}", 38, W,
        ),
        col_row(
            f"⚡ Con.Loss: {neg_c(str(consecutive_losses))}/{_gr(str(allowed_losses))}",
            progress_bar(consecutive_losses, allowed_losses, 14), 38, W,
        ),
        pad_line("─" * W, W),
    ]

    # Mode-specific panel
    if main_mode == 1:
        if mode == "WAGER":
            lines += [
                col_row(
                    f"📈 Wagered: {cya_c(f'{total_wagered:.2f}')}/{_gr(f'{wager_target:.2f}')}",
                    wager_pb, 38, W,
                ),
                col_row(
                    f"📉 Loss%: {neg_c(f'{current_loss_pct:.2f}%')}/{_gr(f'{loss_cut_pct:.2f}%')}",
                    progress_bar(current_loss_pct, loss_cut_pct, 14), 38, W,
                ),
                pad_line("─" * W, W),
            ]
        else:
            need_pct = recover_needed / profit_cycle_start * 100 if profit_cycle_start > 0 else 0.0
            gain_pct = current_gain  / profit_cycle_start * 100 if profit_cycle_start > 0 else 0.0
            lines += [
                col_row(
                    f"♻  Recovery: {pos_c(f'{gain_pct:.2f}%')}/{yel_c(f'{need_pct:.2f}%')}",
                    progress_bar(max(0, current_gain), max(0.0001, recover_needed), 14), 38, W,
                ),
                col_row(
                    f"   WagerLoss: {neg_c(f'{wager_loss_amount:.8f}')}",
                    f"Target+: {yel_c(f'{original_cycle_balance*recover_profit_pct/100:.8f}')}", 38, W,
                ),
                pad_line("─" * W, W),
            ]
    else:
        lines += [
            col_row(
                f"📈 Wagered: {cya_c(f'{total_wagered:.4f}')}",
                f"Bets: {_wc(str(rnd))}", 38, W,
            ),
            pad_line("─" * W, W),
            pad_line("─" * W, W),
        ]

    lines += [
        col_row(f"🔢 Rounds: {_wc(str(rnd))}/{_gr(str(max_rnd))}", round_pb, 38, W),
        footer_line(W + 2),
    ]
    return lines


def _clear_hud(n: int):
    if n > 0:
        sys.stdout.write(f"\033[{n}A\033[J")


def print_hud(lines: list[str]):
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


# ══════════════════════════════════════════════════════════════════
# [6]  MILESTONE EVENT FEED
# ══════════════════════════════════════════════════════════════════
_MILESTONE_BUF: list[str] = []
_MAX_MILESTONES = 8


def milestone(msg: str):
    global _MILESTONE_BUF
    ts = time.strftime("%H:%M:%S")
    _MILESTONE_BUF.append(f"  {_gr(ts)} {msg}")
    if len(_MILESTONE_BUF) > _MAX_MILESTONES:
        _MILESTONE_BUF = _MILESTONE_BUF[-_MAX_MILESTONES:]


def print_milestones():
    for m in _MILESTONE_BUF:
        print(m)


# ══════════════════════════════════════════════════════════════════
# [7]  MAIN SIMULATION
# ══════════════════════════════════════════════════════════════════
def run_simulation():
    global _user_stop

    cfg  = load_env_config()
    args = parse_args(cfg)

    if args.seed is not None:
        random.seed(args.seed)

    quiet       = args.quiet
    round_delay = 0.0 if quiet else args.delay
    max_rounds  = args.rounds
    main_mode   = args.mode

    def cv(key, default, cast=str):
        return _cv(cfg, key, default, cast)

    # ── CONFIG VALUES ─────────────────────────────────────────────
    balance             = float(args.balance)
    wager_chance        = cv("FUSION_WAGER_CHANCE",       98.0,  float)
    wager_bet_percent   = cv("FUSION_WAGER_BET_PCT",      2.5,   float)
    loss_cut_percent    = cv("FUSION_LOSS_CUT_PCT",       4.0,   float)
    recover_profit_pct  = cv("FUSION_RECOVER_PROFIT_PCT", 1.0,   float)
    wager_target        = cv("FUSION_WAGER_TARGET",       100.0, float)
    enable_wager_target = cv("FUSION_ENABLE_WAGER_TARGET",1,     int) != 0

    auto_chance         = cv("FUSION_AUTO_CHANCE",        1,     int) != 0
    chance_min          = cv("FUSION_CHANCE_MIN",         0.5,   float)
    chance_max          = cv("FUSION_CHANCE_MAX",         0.75,  float)
    chance_fixed        = cv("FUSION_CHANCE_FIXED",       0.5,   float)
    random_on_win       = cv("FUSION_RANDOM_ON_WIN",      1,     int) != 0
    random_on_lose      = cv("FUSION_RANDOM_ON_LOSE",     0,     int) != 0

    risk_bonus_percent  = cv("FUSION_RISK_BONUS_PCT",     5.0,   float)
    house_edge          = cv("HE",                        1.0,   float)
    allowed_losses      = cv("FUSION_ALLOWED_LOSSES",     600,   int)
    min_bet_size        = cv("FUSION_MIN_BET",            0.00000001, float)
    stop_profit_target  = cv("FUSION_STOP_PROFIT",        0.2,   float)   # ratio
    stop_loss_limit     = cv("FUSION_STOP_LOSS",          0.0,   float)   # ratio
    stop_max_loss_streak= cv("FUSION_STOP_LOSS_STREAK",   0,     int)

    auto_switch         = cv("FUSION_AUTO_SWITCH",        0,     int) != 0
    switch_on_win       = cv("FUSION_SWITCH_ON_WIN",      0,     int) != 0
    switch_on_lose      = cv("FUSION_SWITCH_ON_LOSE",     0,     int) != 0

    # ── STATE ─────────────────────────────────────────────────────
    start_balance   = balance
    session_start   = time.time()
    total_wagered   = 0.0
    win_count       = 0
    lose_count      = 0
    loss_streak     = 0
    max_loss_streak = 0
    base_bet        = 0.0
    divisor         = 1.0
    wager_base_bet  = 0.0
    consecutive_losses_in_cycle = 0

    working_balance         = balance
    profit_vault            = 0.0
    cycle_start_balance     = balance
    original_cycle_balance  = balance
    wager_cycle_start       = balance
    profit_cycle_start      = balance
    wager_loss_amount       = 0.0
    bethigh                 = True

    nextbet = 0.0
    chance  = wager_chance
    mode    = "WAGER"

    csv_path = _get_csv_path()
    _init_csv(csv_path)

    hud_rendered    = False
    hud_line_count  = 0
    stop_reason     = "max_rounds"

    # ── INNER HELPERS ─────────────────────────────────────────────
    def do_roll(bet_amt: float, win_chance: float) -> tuple[bool, float]:
        roll = random.uniform(0.0, 100.0)
        won  = roll < win_chance
        if won:
            _, payout = get_payout_and_multiplier(win_chance, 0.0, True, house_edge)
            profit = bet_amt * (payout - 1.0)
        else:
            profit = -bet_amt
        return won, profit

    def _update_base() -> tuple[float, float]:
        ref = chance_min if auto_chance else chance_fixed
        use_he = (main_mode == 2)
        return solve_base_bet(
            cycle_start_balance, ref, risk_bonus_percent,
            allowed_losses, min_bet_size, use_he, house_edge,
        )

    def separate_profit_reset() -> None:
        nonlocal profit_vault, balance, working_balance
        nonlocal cycle_start_balance, original_cycle_balance
        cp = balance - original_cycle_balance
        if cp > 0:
            profit_vault += cp
            milestone(
                f"✅ Cycle +{pos_c(f'{cp:.8f}')} | Vault → {pos_c(f'{profit_vault:.8f}')}"
            )
            balance = original_cycle_balance
            working_balance = balance
            cycle_start_balance = balance
        else:
            milestone(f"⚠️  Cycle no profit ({cp:.8f})")
            working_balance = balance

    def to_wager() -> None:
        nonlocal mode, loss_streak, consecutive_losses_in_cycle
        nonlocal wager_cycle_start, wager_base_bet, wager_loss_amount
        nonlocal chance, nextbet
        mode = "WAGER"
        loss_streak = 0; consecutive_losses_in_cycle = 0
        wager_cycle_start = balance
        wager_base_bet    = wager_cycle_start * (wager_bet_percent / 100.0)
        wager_loss_amount = 0.0
        chance  = wager_chance
        nextbet = max(wager_base_bet, min_bet_size)
        milestone(f"🟢 → WAGER  bet={yel_c(f'{wager_base_bet:.8f}')}")

    def to_profit() -> None:
        nonlocal mode, loss_streak, consecutive_losses_in_cycle
        nonlocal profit_cycle_start, cycle_start_balance
        nonlocal base_bet, divisor, chance, nextbet
        mode = "PROFIT"
        loss_streak = 0; consecutive_losses_in_cycle = 0
        profit_cycle_start  = balance
        cycle_start_balance = balance
        base_bet, divisor   = _update_base()
        chance  = random_chance(chance_min, chance_max) if auto_chance else chance_fixed
        nextbet = max(base_bet, min_bet_size)
        milestone(
            f"🟡 → PROFIT  base={yel_c(f'{base_bet:.8f}')} chance={cya_c(f'{chance:.2f}%')}"
        )

    # ── INIT ──────────────────────────────────────────────────────
    base_bet, divisor = _update_base()
    if main_mode == 1:
        to_wager()
    else:
        to_profit()

    milestone(f"🎬 FUSION BOT start  balance={_wc(f'{balance:.4f}')}")

    # HUD refresh interval (show at most 200 renders total)
    hud_interval = max(1, min(50, max_rounds // 200))

    # ─────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────────────────────
    rnd = 0
    for rnd in range(1, max_rounds + 1):
        if _user_stop:
            stop_reason = "user_quit"; break

        previous_bet = nextbet
        total_wagered += previous_bet

        won, round_pnl = do_roll(previous_bet, chance)
        balance        += round_pnl
        working_balance = balance

        # ── WIN ──────────────────────────────────────────────────
        if won:
            win_count  += 1
            loss_streak = 0
            consecutive_losses_in_cycle = 0

            if mode == "WAGER":
                nextbet = wager_base_bet
                if main_mode == 1 and enable_wager_target and total_wagered >= wager_target:
                    milestone(f"🎯 Wager target {wager_target:.2f} reached!")
                    separate_profit_reset()
                    stop_reason = "wager_target"; break
            else:
                if auto_chance and random_on_win:
                    chance = random_chance(chance_min, chance_max)
                else:
                    chance = chance_fixed
                nextbet = base_bet
                if main_mode == 1:
                    need = wager_loss_amount + original_cycle_balance * recover_profit_pct / 100.0
                    gain = working_balance - profit_cycle_start
                    if gain >= need:
                        milestone(f"✅ Recovery WIN  gain={pos_c(f'{gain:+.8f}')}")
                        separate_profit_reset(); to_wager()

            if auto_switch and switch_on_win:
                bethigh = not bethigh

        # ── LOSE ─────────────────────────────────────────────────
        else:
            lose_count  += 1
            loss_streak += 1
            consecutive_losses_in_cycle += 1
            if loss_streak > max_loss_streak:
                max_loss_streak = loss_streak

            if mode == "WAGER":
                cycle_loss = wager_cycle_start - working_balance
                loss_pct   = cycle_loss / wager_cycle_start * 100.0 if wager_cycle_start > 0 else 0.0
                if main_mode == 1 and loss_pct >= loss_cut_percent:
                    wager_loss_amount = cycle_loss
                    milestone(f"⚠️  Loss cut {loss_pct:.2f}% | wager_loss={neg_c(f'{cycle_loss:.8f}')}")
                    to_profit()
                else:
                    nextbet = wager_base_bet
            else:
                if auto_chance and random_on_lose:
                    chance = random_chance(chance_min, chance_max)
                use_he = (main_mode == 2)
                mul, _ = get_payout_and_multiplier(chance, risk_bonus_percent, use_he, house_edge)
                nextbet = nextbet * mul
                if nextbet > working_balance:
                    nextbet = working_balance * 0.9
                if consecutive_losses_in_cycle >= allowed_losses:
                    milestone(f"⛔ {allowed_losses} losses → reset base")
                    base_bet, divisor = _update_base()
                    consecutive_losses_in_cycle = 0
                if main_mode == 1:
                    need = wager_loss_amount + original_cycle_balance * recover_profit_pct / 100.0
                    gain = working_balance - profit_cycle_start
                    if gain >= need:
                        milestone(f"✅ Recovery LOSE  gain={pos_c(f'{gain:+.8f}')}")
                        separate_profit_reset(); to_wager()

            if auto_switch and switch_on_lose:
                bethigh = not bethigh

        if nextbet < min_bet_size:
            nextbet = min_bet_size

        # ── STOP RULES ────────────────────────────────────────────
        total_pnl    = profit_vault + (working_balance - original_cycle_balance)
        profit_ratio = total_pnl / start_balance

        if stop_profit_target > 0 and profit_ratio >= stop_profit_target:
            milestone(f"🎉 Profit target {stop_profit_target*100:.2f}% hit!")
            separate_profit_reset(); stop_reason = "profit_target"; break

        if stop_loss_limit > 0 and profit_ratio <= -stop_loss_limit:
            milestone(f"🚨 Loss limit {stop_loss_limit*100:.2f}% hit!")
            stop_reason = "loss_limit"; break

        if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak:
            milestone(f"🚨 Max streak {stop_max_loss_streak} reached!")
            stop_reason = "max_streak"; break

        if working_balance < min_bet_size * 2:
            milestone("🚨 Balance too low"); stop_reason = "busted"; break

        # ── CSV ───────────────────────────────────────────────────
        total_pnl = profit_vault + (working_balance - original_cycle_balance)
        _log_csv(csv_path, rnd, mode, "win" if won else "lose",
                 previous_bet, round_pnl, total_pnl,
                 balance, loss_streak, profit_vault)

        # ── HUD ───────────────────────────────────────────────────
        if not quiet and (rnd % hud_interval == 0 or rnd <= 5):
            rt = time.time() - session_start
            total_pnl = profit_vault + (working_balance - original_cycle_balance)

            if mode == "WAGER":
                cyc_pnl  = working_balance - wager_cycle_start
                cur_lpct = max(0.0, (wager_cycle_start - working_balance) / wager_cycle_start * 100.0) if wager_cycle_start > 0 else 0.0
            else:
                cyc_pnl  = working_balance - profit_cycle_start
                cur_lpct = 0.0

            need_r = wager_loss_amount + original_cycle_balance * recover_profit_pct / 100.0
            gain_r = working_balance - profit_cycle_start

            hud = render_hud(
                rnd=rnd, max_rnd=max_rounds, mode=mode, main_mode=main_mode,
                balance=balance, start_balance=start_balance,
                working_balance=working_balance, profit_vault=profit_vault,
                cycle_profit=cyc_pnl, total_profit=total_pnl,
                next_bet=nextbet, chance=chance,
                win_count=win_count, lose_count=lose_count,
                loss_streak=loss_streak, max_loss_streak=max_loss_streak,
                total_wagered=total_wagered, wager_target=wager_target,
                wager_cycle_start=wager_cycle_start,
                profit_cycle_start=profit_cycle_start,
                wager_loss_amount=wager_loss_amount,
                recover_needed=need_r, current_gain=gain_r,
                allowed_losses=allowed_losses,
                consecutive_losses=consecutive_losses_in_cycle,
                loss_cut_pct=loss_cut_percent, current_loss_pct=cur_lpct,
                runtime=rt, base_bet=base_bet, divisor=divisor,
                recover_profit_pct=recover_profit_pct,
                original_cycle_balance=original_cycle_balance,
            )

            if hud_rendered:
                _clear_hud(_MAX_MILESTONES + 2 + hud_line_count)
            else:
                hud_rendered = True

            print_milestones()
            print()
            print_hud(hud)
            hud_line_count = len(hud)

        if round_delay > 0:
            time.sleep(round_delay)

    # ─────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────
    runtime = time.time() - session_start
    total_pnl_final = profit_vault + (working_balance - original_cycle_balance)

    if quiet:
        import json
        print(f"__RESULT_JSON__{json.dumps({'rounds': rnd, 'stop_reason': stop_reason, 'start_balance': start_balance, 'final_balance': working_balance, 'profit_vault': profit_vault, 'total_profit': total_pnl_final, 'win_count': win_count, 'lose_count': lose_count, 'max_loss_streak': max_loss_streak, 'total_wagered': total_wagered, 'runtime_s': runtime})}__RESULT_JSON__")
        return

    W = 72
    pc = pos_c if total_pnl_final >= 0 else neg_c
    print()
    print("═" * W)
    print(f"  💎 FUSION BOT v4.1 — FINAL SUMMARY  [{stop_reason.upper()}]")
    print("═" * W)
    print(f"  Strategy    : {'WAGER FOCUS+RECOVERY' if main_mode==1 else 'PROFIT FOCUS'}")
    print(f"  Rounds      : {rnd:,} / {max_rounds:,}")
    print(f"  Runtime     : {runtime:.1f}s")
    print(f"  Start Bal   : {start_balance:.8f}")
    print(f"  Final Bal   : {working_balance:.8f}")
    print(f"  Total P/L   : {pc(f'{total_pnl_final:+.8f}')}")
    print(f"  Profit Vault: {pos_c(f'{profit_vault:.8f}')}")
    print(f"  ROI         : {pc(f'{total_pnl_final/start_balance*100:+.2f}%')}")
    print(f"  W/L         : {win_count} / {lose_count}")
    print(f"  Max Streak  : {max_loss_streak}")
    print(f"  Total Wager : {total_wagered:.4f}")
    print(f"  CSV Log     : {csv_path}")
    print("═" * W)


if __name__ == "__main__":
    run_simulation()
