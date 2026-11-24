#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  💎 FUSION BOT NATIVE v1.0 — Standalone Casino Execution Engine  ║
║  Independent Stake Direct-API Engine (No Gambler.Bot Needed!)    ║
║  Exact Strategy Match with fusion_bot.py · SSOT fusion.env       ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
  # 1. Mock Sandbox Mode (100% mirrors fusion_bot.py logic with simulated rolls)
  python bin/fusion_native.py --mock
  python bin/fusion_native.py --mock -m 2 -r 500

  # 2. Live Casino Mode (Direct Stake GraphQL API with real balance & real rolls)
  python bin/fusion_native.py --live --currency trx
  python bin/fusion_native.py --live --currency usdt --url https://stake.bz

  # 3. Live HUD Projection in another terminal:
  python bin/fusion_live_hud.py real
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
import threading
import time
import unicodedata

# ── Force UTF-8 on Windows Consoles ─────────────────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Add repo root to sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.stake_api import (
    StakeClient, StakeAPIError, StakeAuthError, StakeBetError
)

# ── Graceful Stop Handler ───────────────────────────────────────────────────
_user_stop: bool = False

def _handle_sigint(sig, frame):
    global _user_stop
    _user_stop = True

signal.signal(signal.SIGINT, _handle_sigint)

def _stdin_watcher():
    """Background thread watching for 'q' to stop gracefully."""
    global _user_stop
    try:
        while not _user_stop:
            line = sys.stdin.readline()
            if not line:
                break
            if line.strip().lower() == "q":
                _user_stop = True
                break
    except Exception:
        pass

# ── ANSI Color Helpers ───────────────────────────────────────────────────────
def cn(code: int, text: str, bold: bool = False) -> str:
    style = "1;" if bold else ""
    return f"\033[{style}38;5;{code}m{text}\033[0m"

def _wc(t: object) -> str:  return cn(255, str(t), True)
def _gr(t: object) -> str:  return cn(240, str(t), False)
def _dim(t: object) -> str: return cn(238, str(t), False)
def pos_c(t: object) -> str: return cn(82,  str(t), True)
def neg_c(t: object) -> str: return cn(196, str(t), True)
def yel_c(t: object) -> str: return cn(220, str(t), True)
def cya_c(t: object) -> str: return cn(51,  str(t), True)
def pur_c(t: object) -> str: return cn(171, str(t), True)

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
    l = inner // 2
    r = inner - l
    return f"┌{'─' * l} {title} {'─' * r}┐"

def footer_line(width: int = 72) -> str:
    return "└" + "─" * (width - 2) + "┘"

def progress_bar(val: float, total: float, width: int = 16) -> str:
    pct = max(0.0, min(1.0, val / total)) if total > 0 else 0.0
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:5.1f}%"

# ── SSOT Config Loader ───────────────────────────────────────────────────────
_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?\}|\$(\w+)")

def load_env_config() -> tuple[dict[str, str], Path]:
    cfg: dict[str, str] = {}
    repo_root = _REPO_ROOT
    env_override = os.environ.get("FUSION_CONFIG") or os.environ.get("DICE_CONFIG")
    candidates = [
        Path(env_override) if env_override else None,
        repo_root / "config" / "fusion.env",
        repo_root / "fusion.env",
        Path.cwd() / "config" / "fusion.env",
        Path(r"c:\Users\User\simulator\config\fusion.env"),
        repo_root / "config" / "dice.env",
        repo_root / "dice.env",
    ]
    env_path = None
    for p in candidates:
        if p and p.is_file():
            env_path = p
            break

    if env_path and env_path.is_file():
        try:
            with open(env_path, encoding="utf-8", errors="replace") as f:
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
            new_v = _ENV_REF_RE.sub(lambda m: cfg.get(m.group(1) or m.group(2), ""), v)
            if new_v != v:
                cfg[k] = new_v
                changed = True
        if not changed:
            break

    return cfg, (env_path or repo_root / "config" / "fusion.env")

def _cv(cfg: dict[str, str], key: str, default, cast=str):
    v = cfg.get(key, "").strip()
    if not v:
        return default
    try:
        return cast(v)
    except (ValueError, TypeError):
        return default

# ── CSV Logging (Logs to dice_session_real.csv & mirrors to dice_session_latest.csv) ──
def get_csv_paths(custom_path: str | None = None) -> list[Path]:
    logs_dir = _REPO_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if custom_path:
        return [Path(custom_path)]
    real_path = logs_dir / "dice_session_real.csv"
    latest_path = logs_dir / "dice_session_latest.csv"
    return [real_path, latest_path]

def init_csv(paths: list[Path]) -> None:
    for p in paths:
        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Round", "Mode", "Result", "Roll", "Bet", "RoundPnL",
                    "NetPnL", "Balance", "LossStreak", "ProfitVault",
                    "ConsecutiveLosses", "Chance", "Payout", "LossMul"
                ])
        except Exception:
            pass

def log_csv_row(
    paths: list[Path], rnd: int, mode: str, result: str, roll_val: float,
    bet_amt: float, round_pnl: float, net_pnl: float, bal: float,
    streak: int, vault: float, con_losses: int,
    chance: float = 0.0, payout: float = 0.0, loss_mul: float = 0.0
) -> None:
    row = [
        rnd, mode, result,
        f"{roll_val:.2f}",
        f"{bet_amt:.8f}",
        f"{round_pnl:.8f}",
        f"{net_pnl:.8f}",
        f"{bal:.8f}",
        streak,
        f"{vault:.8f}",
        con_losses,
        f"{chance:.2f}",
        f"{payout:.4f}",
        f"{loss_mul:.4f}",
    ]
    for p in paths:
        try:
            with open(p, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
        except OSError:
            pass

# ── Math Engine (100% Identical to fusion_bot.py & gamblerbot) ───────────────
def random_chance(chance_min: float, chance_max: float) -> float:
    c = random.uniform(chance_min, chance_max)
    return max(0.01, min(98.0, c))

def get_payout_and_multiplier(
    chance_pct: float,
    bonus_pct: float,
    use_house_edge: bool,
    house_edge: float = 1.0,
) -> tuple[float, float]:
    cd = max(0.0001, min(0.9999, chance_pct / 100.0))
    payout = (1.0 - house_edge / 100.0) / cd if use_house_edge and house_edge > 0 else 1.0 / cd
    mult = 1.0 + (payout - 1.0) * (1.0 + bonus_pct / 100.0)
    return mult, payout

def get_constant_divisor_by_mul(mul: float, losses: int) -> float:
    if mul <= 1.0:
        return float(max(1, losses))
    try:
        if (losses - 1) * math.log(mul) > 700.0:
            return float("inf")
        return (mul ** losses - 1.0) / (mul - 1.0)
    except OverflowError:
        return float("inf")

def solve_base_bet_with_mul(cycle_bal: float, mul: float, losses: int, min_bet: float) -> tuple[float, float]:
    d = get_constant_divisor_by_mul(mul, losses)
    if math.isinf(d) or d <= 0:
        return min_bet, d
    base = cycle_bal / d
    return max(base, min_bet), d

def solve_dynamic_allowed_losses(chance_pct: float, risk_alpha: float = 0.001) -> int:
    p = max(0.0001, min(0.9999, chance_pct / 100.0))
    q = 1.0 - p
    if q >= 1.0:
        return 999
    n = math.ceil(math.log(risk_alpha) / math.log(q))
    return max(3, int(n))

# ── Stake Dice Roll Simulator (Mock Mode) ────────────────────────────────────
def roll_stake_dice_mock(chance_pct: float, high: bool = True, house_edge: float = 1.0) -> tuple[float, bool, float]:
    roll = round(random.uniform(0.00, 99.99), 2)
    target = round(100.0 - chance_pct, 2) if high else round(chance_pct, 2)
    won = (roll >= target) if high else (roll < target)
    cd = max(0.0001, min(0.9999, chance_pct / 100.0))
    payout = (1.0 - house_edge / 100.0) / cd
    if payout <= 1.0:
        payout = 1.0001
    return roll, won, payout

# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global _user_stop
    cfg, env_file_path = load_env_config()

    parser = argparse.ArgumentParser(
        description="💎 FUSION BOT NATIVE — Standalone Casino Execution Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--live", action="store_true", help="Live casino real-money betting via Stake API")
    parser.add_argument("--mock", action="store_true", help="Mock dry-run simulation mode")
    parser.add_argument("--currency", "-c", type=str, default="trx", help="Crypto currency symbol (trx, usdt, etc.)")
    parser.add_argument("--api-key", "-k", type=str, default=None, help="Stake API Access Token")
    parser.add_argument("--url", type=str, default="https://stake.bz", help="Stake Base URL")
    parser.add_argument("--mode", "-m", type=int, default=_cv(cfg, "FUSION_MAIN_MODE", 2, int),
                        help="1=WAGER FOCUS+RECOVERY, 2=PROFIT FOCUS")
    parser.add_argument("--balance", "-b", type=float, default=_cv(cfg, "START_BALANCE", 25.0, float),
                        help="Starting balance (used in Mock mode)")
    parser.add_argument("--rounds", "-r", type=int, default=_cv(cfg, "GLOBAL_MAX_ROUNDS", 200000, int),
                        help="Maximum rounds cap")
    parser.add_argument("--delay", "-d", type=float, default=_cv(cfg, "GLOBAL_ROUND_DELAY", 0.05, float),
                        help="Delay in seconds between rolls")
    parser.add_argument("--vault", type=int, default=None,
                        help="1=Vault (skim profit), 0=Compound. Overrides env.")
    args = parser.parse_args()

    # Determine execution mode
    is_live = args.live
    if not is_live and not args.mock:
        print(header_line(cn(51, "💎 FUSION BOT NATIVE — Select Execution Mode", True), 72))
        print(pad_line("Choose mode:", 70))
        print(pad_line(f"  {yel_c('[1]')} {pos_c('🎲 Mock Dry-Run (Offline Test, Zero Risk)')}", 70))
        print(pad_line(f"  {yel_c('[2]')} {neg_c('🔥 LIVE REAL MONEY (Stake Direct API)')}", 70))
        print(footer_line(72))
        try:
            choice = input(cn(51, "\n  Select [1/2] (Default: 1 Mock): ", True)).strip()
        except (KeyboardInterrupt, EOFError):
            return
        is_live = (choice == "2")

    # API Setup
    api_key = args.api_key or os.environ.get("STAKE_API_KEY") or _cv(cfg, "STAKE_API_KEY", "")
    if not api_key:
        api_key = "522fe34470a71f0662cfc2ec39b887f54e34459125cdc8ed646b366f7a997635d9a75e03b162df944ceaa9cc644be544"

    client: StakeClient | None = None
    currency = args.currency.lower()
    balance = float(args.balance)

    if is_live:
        print(cn(220, f"\n  Connecting to Stake API ({args.url}) with currency '{currency.upper()}'..."))
        client = StakeClient(api_key=api_key, base_url=args.url)
        try:
            live_bal = client.get_currency_balance(currency)
            print(pos_c(f"  ✅ Connected successfully! Account Balance: {live_bal:.8f} {currency.upper()}"))
            if live_bal <= 0:
                print(neg_c(f"  ❌ Available {currency.upper()} balance is 0.00000000. Please deposit or choose another currency."))
                return
            balance = live_bal
        except Exception as e:
            print(neg_c(f"  ❌ Connection failed: {e}"))
            print(yel_c("  Tip: Make sure Cloudflare cookies are updated in .bypass_cache.json or run with --mock"))
            return

    # ── Strategy Parameters (100% Alignment with fusion_bot.py) ───────────────
    main_mode             = args.mode
    auto_cal_base_bet     = _cv(cfg, "AUTO_CAL_BASE_BET", 1, int) != 0
    manual_base_bet       = _cv(cfg, "FUSION_MANUAL_BASE_BET", 0.0001, float)
    auto_cal_loss_mul     = _cv(cfg, "AUTO_CAL_LOSS_MUL", 1, int) != 0
    manual_loss_mul       = _cv(cfg, "FUSION_MANUAL_LOSS_MUL", 1.05, float)
    wager_chance          = _cv(cfg, "FUSION_WAGER_CHANCE", 98.0, float)
    wager_bet_percent     = _cv(cfg, "FUSION_WAGER_BET_PCT", 2.5, float)
    loss_cut_percent      = _cv(cfg, "FUSION_LOSS_CUT_PCT", 4.0, float)
    recover_profit_pct    = _cv(cfg, "FUSION_RECOVER_PROFIT_PCT", 1.0, float)
    wager_target          = _cv(cfg, "FUSION_WAGER_TARGET", 500.0, float)
    enable_wager_target   = _cv(cfg, "FUSION_ENABLE_WAGER_TARGET", 1, int) != 0

    auto_chance           = _cv(cfg, "FUSION_AUTO_CHANCE", 1, int) != 0
    chance_min            = _cv(cfg, "FUSION_CHANCE_MIN", 0.5, float)
    chance_max            = _cv(cfg, "FUSION_CHANCE_MAX", 18.0, float)
    chance_fixed          = _cv(cfg, "FUSION_CHANCE_FIXED", 0.5, float)
    random_on_win         = _cv(cfg, "FUSION_RANDOM_ON_WIN", 1, int) != 0
    random_on_lose        = _cv(cfg, "FUSION_RANDOM_ON_LOSE", 0, int) != 0

    risk_bonus_pct        = _cv(cfg, "FUSION_RISK_BONUS_PCT", 10.0, float)
    house_edge            = _cv(cfg, "HE", 1.0, float)
    auto_cal_allowed_loss = _cv(cfg, "AUTO_CAL_ALLOWED_LOSS", 1, int) != 0
    risk_alpha            = _cv(cfg, "FUSION_RISK_ALPHA", 0.01, float)
    manual_allowed_losses = _cv(cfg, "FUSION_ALLOWED_LOSSES", 700, int)
    allowed_losses        = manual_allowed_losses
    min_bet               = _cv(cfg, "FUSION_MIN_BET", 0.0001, float)
    _vault_env            = _cv(cfg, "FUSION_ENABLE_VAULT", 0, int) != 0
    enable_vault          = _vault_env if args.vault is None else (args.vault != 0)
    stop_profit_ratio     = _cv(cfg, "FUSION_STOP_PROFIT", 1.0, float)
    stop_loss_ratio       = _cv(cfg, "FUSION_STOP_LOSS", 0.0, float)
    stop_max_streak       = _cv(cfg, "FUSION_STOP_LOSS_STREAK", 0, int)

    # ── Runtime State ─────────────────────────────────────────────────────────
    session_start_balance   = balance
    session_start_time      = time.time()
    total_bets              = 0
    total_wagered           = 0.0
    win_count               = 0
    lose_count              = 0
    loss_streak             = 0
    max_loss_streak         = 0
    consecutive_losses      = 0

    mode                    = "WAGER" if main_mode == 1 else "PROFIT"
    working_balance         = balance
    profit_vault            = 0.0
    cycle_start_balance     = balance
    original_cycle_balance  = balance
    wager_cycle_start       = balance
    profit_cycle_start      = balance
    wager_loss_amount       = 0.0

    base_bet                = 0.0
    divisor                 = 1.0
    wager_base_bet          = 0.0
    current_chance          = wager_chance if main_mode == 1 else (
        random_chance(chance_min, chance_max) if auto_chance else chance_fixed
    )

    nextbet                 = 0.0
    bethigh                 = True
    stop_reason             = "max_rounds"

    csv_paths = get_csv_paths()
    init_csv(csv_paths)

    # ── State Transition Functions ────────────────────────────────────────────
    def update_base(active_chance: float | None = None):
        nonlocal base_bet, divisor, allowed_losses
        ref = active_chance if active_chance is not None else (chance_min if auto_chance else chance_fixed)

        if auto_cal_allowed_loss:
            allowed_losses = solve_dynamic_allowed_losses(ref, risk_alpha)
        else:
            allowed_losses = manual_allowed_losses

        use_he = (main_mode == 2)
        if auto_cal_loss_mul:
            eff_mul, _ = get_payout_and_multiplier(ref, risk_bonus_pct, use_he, house_edge)
        else:
            eff_mul = manual_loss_mul

        if auto_cal_base_bet:
            base_bet, divisor = solve_base_bet_with_mul(
                cycle_start_balance, eff_mul, allowed_losses, min_bet
            )
        else:
            base_bet = max(manual_base_bet, min_bet)
            divisor = 1.0
        if base_bet < min_bet:
            base_bet = min_bet

    def separate_profit_reset():
        nonlocal profit_vault, working_balance, cycle_start_balance
        nonlocal original_cycle_balance, balance
        cp = balance - original_cycle_balance
        if cp > 0:
            if enable_vault:
                profit_vault += cp
                balance = original_cycle_balance
                working_balance = balance
                cycle_start_balance = original_cycle_balance
            else:
                original_cycle_balance = balance
                cycle_start_balance = balance
                working_balance = balance

    def switch_to_wager():
        nonlocal mode, loss_streak, consecutive_losses
        nonlocal wager_cycle_start, wager_base_bet, wager_loss_amount
        nonlocal current_chance, nextbet, bethigh
        mode = "WAGER"
        loss_streak = 0
        consecutive_losses = 0
        wager_cycle_start = balance
        if auto_cal_base_bet:
            wager_base_bet = max(wager_cycle_start * (wager_bet_percent / 100.0), min_bet)
        else:
            wager_base_bet = max(manual_base_bet, min_bet)
        wager_loss_amount = 0.0
        current_chance = wager_chance
        bethigh = True
        nextbet = max(wager_base_bet, min_bet)

    def switch_to_profit():
        nonlocal mode, loss_streak, consecutive_losses
        nonlocal profit_cycle_start, cycle_start_balance
        nonlocal current_chance, nextbet, bethigh
        mode = "PROFIT"
        loss_streak = 0
        consecutive_losses = 0
        profit_cycle_start = balance
        cycle_start_balance = balance

        if auto_chance:
            current_chance = random_chance(chance_min, chance_max)
        else:
            current_chance = chance_fixed

        update_base(current_chance)
        bethigh = True
        nextbet = max(base_bet, min_bet)

    # ── Initialize State ──────────────────────────────────────────────────────
    update_base()
    if main_mode == 1:
        switch_to_wager()
    else:
        switch_to_profit()

    # ── Startup Banner ────────────────────────────────────────────────────────
    W = 74
    print(cn(51, "═" * W, True))
    print(cn(255, f"  💎 FUSION BOT NATIVE — {'🔥 LIVE REAL-MONEY' if is_live else '🎲 MOCK DRY-RUN'} ENGINE", True))
    print(cn(51, "═" * W, True))
    print(f"  Config Path    : {_wc(str(env_file_path))} {_gr('(SSOT)')}")
    print(f"  Target         : {_wc('STAKE DIRECT API' if is_live else 'LOCAL SIMULATOR')}  │  Currency: {_wc(currency.upper())}")
    print(f"  Strategy       : {pos_c('WAGER FOCUS + RECOVERY') if main_mode == 1 else yel_c('PROFIT FOCUS')}")
    vault_desc = "Enabled (Vault & Reset)" if enable_vault else "Disabled (Compound All Bal)"
    print(f"  Starting Bal   : {_wc(f'{session_start_balance:.8f}')}  │  Vault: {_wc(vault_desc)}")
    base_desc = "Auto (Dynamic)" if auto_cal_base_bet else f"Manual ({manual_base_bet:.8f})"
    mul_desc = f"Auto (Bonus {risk_bonus_pct:.1f}%)" if auto_cal_loss_mul else f"Manual ({manual_loss_mul:.4f}x)"
    print(f"  Base Bet Mode  : {_wc(base_desc)}  │  Multiplier: {_wc(mul_desc)}")
    loss_info = f"Auto (Risk {risk_alpha*100:.2f}%)" if auto_cal_allowed_loss else f"Fixed ({allowed_losses})"
    print(f"  Allowed Losses : {_wc(loss_info)}  │  Stop Profit: {pos_c(f'{stop_profit_ratio*100:.1f}%')}")
    print(f"  Chance Range   : {_wc(f'{chance_min:.2f}% - {chance_max:.2f}%')}  │  Min Bet: {_wc(f'{min_bet:.8f}')}")
    print(f"  Live Log File  : {_gr('logs/dice_session_real.csv')} {_cya('(Projectable by Live HUD)') if False else ''}")
    print(cn(240, "  💡 Press Ctrl+C or type 'q' + Enter at any time to stop"))
    print(cn(51, "═" * W, True))
    print()

    # Stdin listener thread
    threading.Thread(target=_stdin_watcher, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # BETTING ENGINE LOOP
    # ─────────────────────────────────────────────────────────────────────────
    try:
        while total_bets < args.rounds and not _user_stop:
            total_bets += 1
            current_bet = nextbet
            current_roll_chance = current_chance
            current_high = bethigh
            total_wagered += current_bet

            # Execute Roll
            if is_live and client:
                res = client.place_dice_bet(
                    amount=current_bet,
                    chance=current_roll_chance,
                    high=current_high,
                    currency=currency,
                )
                roll_val = res["roll_val"]
                won = res["won"]
                round_pnl = res["round_pnl"]
                balance = res["balance"]
                payout = res["payout"] / current_bet if current_bet > 0 else 0.0
            else:
                roll_val, won, payout = roll_stake_dice_mock(current_roll_chance, current_high, house_edge)
                if won:
                    round_pnl = current_bet * (payout - 1.0)
                else:
                    round_pnl = -current_bet
                balance += round_pnl

            # Calculate logs
            use_he = (main_mode == 2)
            if auto_cal_loss_mul:
                mul_log, payout_log = get_payout_and_multiplier(
                    current_roll_chance, risk_bonus_pct, use_he, house_edge
                )
            else:
                mul_log = manual_loss_mul
                payout_log = (1.0 - house_edge / 100.0) / (current_roll_chance / 100.0)

            total_pnl = (balance + profit_vault) - session_start_balance

            # State Updates
            if won:
                win_count += 1
                loss_streak = 0
                consecutive_losses = 0

                if mode == "WAGER":
                    nextbet = max(wager_base_bet, min_bet)
                else:
                    # Profit Mode Win: check cycle completion
                    cp = balance - original_cycle_balance
                    if cp > 0:
                        separate_profit_reset()
                        if main_mode == 1:
                            switch_to_wager()
                        else:
                            switch_to_profit()
                    else:
                        nextbet = max(base_bet, min_bet)

                    if auto_chance and random_on_win:
                        current_chance = random_chance(chance_min, chance_max)
                        update_base(current_chance)
                        nextbet = max(base_bet, min_bet)

            else:  # Lose
                lose_count += 1
                loss_streak += 1
                consecutive_losses += 1
                if loss_streak > max_loss_streak:
                    max_loss_streak = loss_streak

                if mode == "WAGER":
                    wager_loss_amount += current_bet
                    cum_loss_pct = (wager_loss_amount / wager_cycle_start * 100.0) if wager_cycle_start > 0 else 0.0
                    if cum_loss_pct >= loss_cut_percent:
                        switch_to_profit()
                    else:
                        nextbet = max(wager_base_bet, min_bet)
                else:
                    # Profit Mode Lose: Martingale multiplication
                    if auto_chance and random_on_lose:
                        current_chance = random_chance(chance_min, chance_max)

                    if auto_cal_loss_mul:
                        eff_mul, _ = get_payout_and_multiplier(
                            current_chance, risk_bonus_pct, use_he, house_edge
                        )
                    else:
                        eff_mul = manual_loss_mul

                    nextbet = max(current_bet * eff_mul, min_bet)

            # Safety Stop Checks
            roi_pct = (total_pnl / session_start_balance) if session_start_balance > 0 else 0.0
            if stop_profit_ratio > 0 and roi_pct >= stop_profit_ratio:
                stop_reason = "STOP_PROFIT"
                break
            if stop_loss_ratio > 0 and roi_pct <= -stop_loss_ratio:
                stop_reason = "STOP_LOSS"
                break
            if stop_max_streak > 0 and loss_streak >= stop_max_streak:
                stop_reason = "STOP_MAX_STREAK"
                break
            if nextbet > balance:
                stop_reason = "INSUFFICIENT_BALANCE"
                break

            # CSV Stream (Real-Time HUD feed)
            log_csv_row(
                csv_paths, total_bets, mode, "win" if won else "lose",
                roll_val, current_bet, round_pnl, total_pnl, balance,
                loss_streak, profit_vault, consecutive_losses,
                current_roll_chance, payout_log, mul_log
            )

            # Terminal Roll Output
            tag = pos_c("🏆 WIN ") if won else neg_c("💀 LOSE")
            pnl_disp = pos_c(f"+{round_pnl:11.8f}") if round_pnl >= 0 else neg_c(f"{round_pnl:11.8f}")
            mode_tag = yel_c("[P]") if mode == "PROFIT" else pos_c("[W]")
            ts = time.strftime("%H:%M:%S")
            print(f"{_gr(ts)} {mode_tag} #{total_bets:<5d} {tag} Roll: {roll_val:5.2f} │ Bet: {current_bet:11.8f} │ PnL: {pnl_disp} │ Bal: {_wc(f'{balance:11.8f}')}")

            if args.delay > 0:
                time.sleep(args.delay)

    except KeyboardInterrupt:
        stop_reason = "USER_INTERRUPT"
    finally:
        print(cn(51, "\n" + "═" * W, True))
        print(cn(255, f"  💎 FUSION NATIVE — SESSION COMPLETE [{stop_reason.upper()}]", True))
        print(cn(51, "═" * W, True))
        print(f"  Final Balance : {_wc(f'{balance:14.8f}')} {currency.upper()}")
        print(f"  Profit Vault  : {pos_c(f'{profit_vault:+14.8f}')}")
        tot_final_pnl = (balance + profit_vault) - session_start_balance
        pnl_fn = pos_c if tot_final_pnl >= 0 else neg_c
        print(f"  Net Total PnL : {pnl_fn(f'{tot_final_pnl:+14.8f}')} (ROI: {pnl_fn(f'{tot_final_pnl/session_start_balance*100:+.2f}%')})")
        print(f"  Win / Loss    : {pos_c(str(win_count))} W  /  {neg_c(str(lose_count))} L  ({win_count/max(1, total_bets)*100:.2f}%)")
        print(f"  Max Streak    : {neg_c(str(max_loss_streak))} consecutive losses")
        print(f"  Logged to     : {_gr('logs/dice_session_real.csv')}")
        print(cn(51, "═" * W, True))

if __name__ == "__main__":
    main()
