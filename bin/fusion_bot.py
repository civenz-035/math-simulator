#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  💎 FUSION BOT v4.1 — Real Simulation Engine (Pure Python)       ║
║  Accurate Simulation of fusion_bot_gamblerbot.py (Stake / GB)    ║
║  Live Roll Stream + Pinned Bottom HUD Box · SSOT fusion.env     ║
╚══════════════════════════════════════════════════════════════════╝

Features:
  - 100% logic alignment with fusion_bot_gamblerbot.py (Gambler.Bot IronPython)
  - Stake Dice Mechanics: Roll 0.00-99.99, High=True (Roll Over Target 100-Chance)
  - Mode 1: WAGER FOCUS + RECOVERY (Flat wager bet -> Loss cut -> Profit recovery -> Vault & Reset)
  - Mode 2: PROFIT FOCUS (Dynamic Martingale with Auto-Chance and Risk Bonus)
  - Dual-layer Output (rock solid, zero jitter):
      * Rolls stream & scroll upwards in terminal history (strictly <= 70 chars)
      * Real-time Summary Box is pinned at the bottom and updates every roll in-place
  - Full CSV logging matching dice_session_latest.csv schema (11 columns)

Usage:
  python bin/fusion_bot.py                         # defaults from config/fusion.env
  python bin/fusion_bot.py -m 1 -r 500 -d 0.02     # Mode 1, 500 rounds, 20ms delay
  python bin/fusion_bot.py -m 2 -r 1000 -d 0       # Mode 2, max speed
  python bin/fusion_bot.py -q                      # Headless (JSON summary)
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
            if line.strip().lower() == "q":
                _user_stop = True
                break
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# [0] ANSI COLOR & TUI HELPERS
# ══════════════════════════════════════════════════════════════════
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
def blu_c(t: object) -> str: return cn(75,  str(t), True)
def ora_c(t: object) -> str: return cn(208, str(t), True)

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

def progress_bar(val: float, total: float, width: int = 14) -> str:
    pct = max(0.0, min(1.0, val / total)) if total > 0 else 0.0
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"


# ══════════════════════════════════════════════════════════════════
# [1] SSOT CONFIG LOADER (config/fusion.env > config/dice.env)
# ══════════════════════════════════════════════════════════════════
_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?\}|\$(\w+)")

def load_env_config() -> dict[str, str]:
    cfg: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parent.parent
    env_override = os.environ.get("FUSION_CONFIG") or os.environ.get("DICE_CONFIG")
    candidates = [
        Path(env_override) if env_override else None,
        repo_root / "config" / "fusion.env",
        repo_root / "fusion.env",
        Path.cwd() / "config" / "fusion.env",
        Path(r"c:\Users\User\simulator\config\fusion.env"),
        repo_root / "config" / "dice.env",
        repo_root / "dice.env",
        Path.cwd() / "config" / "dice.env",
        Path(r"c:\Users\User\simulator\config\dice.env"),
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

    # Process Environment Overrides
    for k, v in os.environ.items():
        if k in cfg or any(k.startswith(p) for p in (
            "FUSION_", "WAGER_", "PROFIT_", "BRAVE_", "GLOBAL_", "CUSTOM_"
        )):
            cfg[k] = v

    # Expand variable references
    for _ in range(5):
        changed = False
        for k in list(cfg):
            v = cfg[k]
            new_v = _ENV_REF_RE.sub(
                lambda m: cfg.get(m.group(1) or m.group(2), "") or os.environ.get(m.group(1) or m.group(2), ""),
                v
            )
            if new_v != v:
                cfg[k] = new_v
                changed = True
        if not changed:
            break

    return cfg

def _cv(cfg: dict[str, str], key: str, default, cast=str):
    v = cfg.get(key, "").strip()
    if not v:
        return default
    try:
        return cast(v)
    except (ValueError, TypeError):
        return default


# ══════════════════════════════════════════════════════════════════
# [2] CSV LOGGER (Matches fusion_bot_gamblerbot.py 11 columns)
# ══════════════════════════════════════════════════════════════════
def get_csv_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "dice_session_latest.csv"

def init_csv(path: Path) -> None:
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Round", "Mode", "Result", "Roll", "Bet", "RoundPnL",
                "NetPnL", "Balance", "LossStreak", "ProfitVault",
                "ConsecutiveLosses"
            ])
    except Exception:
        pass

def log_csv_row(
    path: Path, rnd: int, mode: str, result: str, roll_val: float,
    bet_amt: float, round_pnl: float, net_pnl: float, bal: float,
    streak: int, vault: float, con_losses: int
) -> None:
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                rnd, mode, result,
                f"{roll_val:.2f}",
                f"{bet_amt:.8f}",
                f"{round_pnl:.8f}",
                f"{net_pnl:.8f}",
                f"{bal:.8f}",
                streak,
                f"{vault:.8f}",
                con_losses,
            ])
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════════
# [3] FUSION MATH ENGINE (Exact Port from fusion_bot_gamblerbot.py)
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
    """Matches Gambler.Bot / Lua getAutoMultiplierByChance()"""
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
    chance_ref: float,
    bonus_pct: float,
    losses: int,
    use_house_edge: bool,
    house_edge: float = 1.0,
) -> float:
    """Geometric series: sum_{i=0}^{losses-1} mul^i"""
    mul, _ = get_payout_and_multiplier(chance_ref, bonus_pct, use_house_edge, house_edge)
    total = 0.0
    for i in range(losses):
        total += math.pow(mul, i)
    return total

def solve_base_bet(
    cycle_bal: float,
    chance_ref: float,
    bonus_pct: float,
    losses: int,
    min_bet: float,
    use_he: bool,
    house_edge: float = 1.0,
) -> tuple[float, float]:
    d = get_constant_divisor(chance_ref, bonus_pct, losses, use_he, house_edge)
    base = cycle_bal / d if d > 0 else min_bet
    return max(base, min_bet), d

def solve_dynamic_allowed_losses(chance_pct: float, risk_alpha: float = 0.001) -> int:
    """Calculate maximum consecutive losses (N) allowed to keep streak ruin probability <= risk_alpha.
    Formula: P(Lose N in a row) = q^N <= alpha  =>  N = ceil(ln(alpha) / ln(1 - p))
    """
    p = max(0.0001, min(0.9999, chance_pct / 100.0))
    q = 1.0 - p
    if q >= 1.0:
        return 999
    n = math.ceil(math.log(risk_alpha) / math.log(q))
    return max(3, int(n))


# ══════════════════════════════════════════════════════════════════
# [4] ARGUMENT PARSER
# ══════════════════════════════════════════════════════════════════
def parse_args(cfg: dict[str, str]):
    p = argparse.ArgumentParser(
        description="💎 FUSION BOT v4.1 — Real Simulation Engine (fusion_bot_gamblerbot.py simulator)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", "-m", type=int, choices=[1, 2],
                   default=_cv(cfg, "FUSION_MAIN_MODE", 1, int),
                   help="1=WAGER FOCUS+RECOVERY, 2=PROFIT FOCUS")
    p.add_argument("--balance", "-b", type=float,
                   default=_cv(cfg, "START_BALANCE", 10_000.0, float),
                   help="Starting bankroll balance")
    p.add_argument("--rounds", "-r", type=int,
                   default=_cv(cfg, "GLOBAL_MAX_ROUNDS", 1000, int),
                   help="Maximum rounds to simulate")
    p.add_argument("--delay", "-d", type=float,
                   default=_cv(cfg, "GLOBAL_ROUND_DELAY", 0.02, float),
                   help="Delay in seconds between rolls for visual inspection")
    p.add_argument("--seed", type=int, default=None,
                   help="RNG seed for reproducible simulation")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="Headless mode — emit __RESULT_JSON__ at end")
    p.add_argument("--monitor", action="store_true",
                   help="Launch Live ANSI HUD Monitor (tails Gambler.Bot CSV)")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════
# [5] PINNED SUMMARY BOX BUILDER (Fixed 11 lines, strictly <= 72 w)
# ══════════════════════════════════════════════════════════════════
def build_pinned_hud(
    *,
    rnd: int, max_rnd: int, mode: str, main_mode: int,
    balance: float, start_balance: float,
    profit_vault: float, total_profit: float,
    next_bet: float, next_chance: float,
    win_count: int, lose_count: int, loss_streak: int, max_loss_streak: int,
    total_wagered: float, wager_target: float,
    allowed_losses: int, consecutive_losses: int,
    loss_cut_pct: float, current_loss_pct: float,
    runtime: float, recover_needed: float, current_gain: float,
) -> list[str]:
    W = 70
    strat_tag = pos_c("WAGER FOCUS+RECOVERY") if main_mode == 1 else yel_c("PROFIT FOCUS")
    mode_badge = pos_c("● WAGER") if mode == "WAGER" else yel_c("▲ PROFIT")
    pnl_c = pos_c if total_profit >= 0 else neg_c
    vault_c = pos_c if profit_vault > 0 else _gr

    round_pb = progress_bar(rnd, max_rnd, 14)
    w_pct = (win_count / rnd * 100.0) if rnd > 0 else 0.0

    # Exactly 11 lines in both modes (Rock Solid, Zero Height Jitter)
    lines: list[str] = [
        header_line(f"💎 FUSION BOT v4.1  #{_wc(str(rnd))}/{_gr(str(max_rnd))}", W + 2),
        col_row(f"⏱  {_wc(f'{runtime:.0f}s')} │ {strat_tag}", f"Mode: {mode_badge}", 42, W),
        pad_line("─" * W, W),
        col_row(
            f"💰 Balance: {_wc(f'{balance:.8f}')}",
            f"💎 Vault: {vault_c(f'{profit_vault:.8f}')}", 36, W
        ),
        col_row(
            f"🎁 Net P/L: {pnl_c(f'{total_profit:+.8f}')} ({pnl_c(f'{total_profit/start_balance*100:+.2f}%')})",
            f"🎲 Next:  {yel_c(f'{next_bet:.8f}')} ({next_chance:.1f}%)", 36, W
        ),
        col_row(
            f"🏆 W/L: {pos_c(str(win_count))}/{neg_c(str(lose_count))} ({w_pct:.1f}%)",
            f"Streak: {neg_c(str(loss_streak))} (Max {max_loss_streak})", 36, W
        ),
        pad_line("─" * W, W),
    ]

    if main_mode == 1:
        if mode == "WAGER":
            wager_pb = progress_bar(total_wagered, wager_target, 14) if wager_target > 0 else "N/A"
            loss_pb = progress_bar(current_loss_pct, loss_cut_pct, 14)
            lines.append(col_row(
                f"📈 Wagered:  {cya_c(f'{total_wagered:.2f}')}/{_gr(f'{wager_target:.2f}')}",
                wager_pb, 36, W
            ))
            lines.append(col_row(
                f"📉 Loss Cut: {neg_c(f'{current_loss_pct:.2f}%')}/{_gr(f'{loss_cut_pct:.2f}%')}",
                loss_pb, 36, W
            ))
        else:
            rec_pb = progress_bar(max(0.0, current_gain), max(0.0001, recover_needed), 14)
            con_pb = progress_bar(consecutive_losses, allowed_losses, 14)
            lines.append(col_row(
                f"♻  Recovery: {pos_c(f'{current_gain:+.4f}')}/{yel_c(f'{recover_needed:.4f}')}",
                rec_pb, 36, W
            ))
            lines.append(col_row(
                f"⚡ Con.Loss: {neg_c(str(consecutive_losses))}/{_gr(str(allowed_losses))}",
                con_pb, 36, W
            ))
    else:
        con_pb = progress_bar(consecutive_losses, allowed_losses, 14)
        lines.append(col_row(
            f"📈 Wagered:  {cya_c(f'{total_wagered:.4f}')}",
            f"Allowed: {_wc(str(allowed_losses))}", 36, W
        ))
        lines.append(col_row(
            f"⚡ Con.Loss: {neg_c(str(consecutive_losses))}/{_gr(str(allowed_losses))}",
            con_pb, 36, W
        ))

    lines.append(col_row(f"🔢 Progress: {_wc(str(rnd))}/{_gr(str(max_rnd))}", round_pb, 36, W))
    lines.append(footer_line(W + 2))
    return lines


# ══════════════════════════════════════════════════════════════════
# [6] MAIN SIMULATION LOGIC
# ══════════════════════════════════════════════════════════════════
def run_simulation():
    global _user_stop

    cfg = load_env_config()
    args = parse_args(cfg)

    if args.monitor:
        try:
            from fusion_live_hud import main as monitor_main
        except ImportError:
            from bin.fusion_live_hud import main as monitor_main
        monitor_main()
        return

    if args.seed is not None:
        random.seed(args.seed)

    quiet = args.quiet
    round_delay = 0.0 if quiet else max(0.0, args.delay)
    max_rounds = args.rounds
    main_mode = args.mode

    def cv(key, default, cast=str):
        return _cv(cfg, key, default, cast)

    # ── CONFIG PARAMETERS (100% Alignment with fusion_bot_gamblerbot.py) ──
    balance             = float(args.balance)
    wager_chance        = cv("FUSION_WAGER_CHANCE",       98.0,  float)
    wager_bet_percent   = cv("FUSION_WAGER_BET_PCT",      2.5,   float)
    loss_cut_percent    = cv("FUSION_LOSS_CUT_PCT",       4.0,   float)
    recover_profit_pct  = cv("FUSION_RECOVER_PROFIT_PCT", 1.0,   float)
    wager_target        = cv("FUSION_WAGER_TARGET",       cv("WAGER_TARGET", 1000.0, float), float)
    enable_wager_target = cv("FUSION_ENABLE_WAGER_TARGET", 1,    int) != 0

    auto_chance         = cv("FUSION_AUTO_CHANCE",        1,     int) != 0
    chance_min          = cv("FUSION_CHANCE_MIN",         30.0,  float)
    chance_max          = cv("FUSION_CHANCE_MAX",         40.0,  float)
    chance_fixed        = cv("FUSION_CHANCE_FIXED",       0.5,   float)
    random_on_win       = cv("FUSION_RANDOM_ON_WIN",      1,     int) != 0
    random_on_lose      = cv("FUSION_RANDOM_ON_LOSE",     0,     int) != 0

    risk_bonus_pct        = cv("FUSION_RISK_BONUS_PCT",     10.0,  float)
    house_edge            = cv("HE",                        1.0,   float)
    auto_cal_allowed_loss = cv("AUTO_CAL_ALLOWED_LOSS", cv("FUSION_AUTO_CAL_ALLOWED_LOSS", 1, int), int) != 0
    risk_alpha            = cv("FUSION_RISK_ALPHA", cv("RISK_ALPHA", 0.001, float), float)
    manual_allowed_losses = cv("FUSION_ALLOWED_LOSSES",     14,    int)
    allowed_losses        = manual_allowed_losses
    min_bet               = cv("FUSION_MIN_BET",            0.00000001, float)
    stop_profit_ratio   = cv("FUSION_STOP_PROFIT",        0.2,   float)
    stop_loss_ratio     = cv("FUSION_STOP_LOSS",          0.0,   float)
    stop_max_streak     = cv("FUSION_STOP_LOSS_STREAK",   0,     int)

    # ── RUNTIME STATE ──────────────────────────────────────────────
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
    bethigh                 = True  # Stake dice: High=True (Roll Over 100 - chance)
    stop_reason             = "max_rounds"

    csv_path = get_csv_path()
    init_csv(csv_path)

    # ── ROCK SOLID DUAL-LAYER TUI ENGINE ─────────────────────────
    # Keeps HUD at bottom and streams roll lines above without jitter
    hud_rendered_lines: int = 0
    scroll_buffer: list[str] = []

    def buffer_scroll(msg: str):
        """Buffers an event or roll line for batch rendering above HUD."""
        nonlocal scroll_buffer
        if quiet:
            return
        scroll_buffer.append(msg)

    def render_frame(hud_lines: list[str]):
        """Atomic batch rendering: Repositions cursor, emits scroll items, then draws HUD."""
        nonlocal hud_rendered_lines, scroll_buffer
        if quiet:
            return

        out: list[str] = []
        if hud_rendered_lines > 0:
            out.append(f"\033[{hud_rendered_lines}A")

        # Emit all buffered scroll lines cleanly (clearing line with \r\033[2K)
        for msg in scroll_buffer:
            out.append(f"\r\033[2K{msg}\n")
        scroll_buffer.clear()

        # Emit pinned HUD box
        for line in hud_lines:
            out.append(f"\r\033[2K{line}\n")

        # Erase below if previous HUD was taller
        diff = hud_rendered_lines - len(hud_lines)
        if diff > 0:
            out.append("\033[J")

        sys.stdout.write("".join(out))
        sys.stdout.flush()
        hud_rendered_lines = len(hud_lines)

    # ── HELPER FUNCTIONS ──────────────────────────────────────────
    def update_base(active_chance: float | None = None):
        nonlocal base_bet, divisor, allowed_losses
        if active_chance is not None:
            ref = active_chance
        else:
            ref = chance_min if auto_chance else chance_fixed
        if auto_cal_allowed_loss:
            allowed_losses = solve_dynamic_allowed_losses(ref, risk_alpha)
        else:
            allowed_losses = manual_allowed_losses
        use_he = (main_mode == 2)
        base_bet, divisor = solve_base_bet(
            cycle_start_balance, ref, risk_bonus_pct,
            allowed_losses, min_bet, use_he, house_edge
        )

    def separate_profit_reset():
        nonlocal profit_vault, working_balance, cycle_start_balance
        nonlocal original_cycle_balance, balance
        cp = balance - original_cycle_balance
        if cp > 0:
            profit_vault += cp
            buffer_scroll(f"  {pos_c('✅ Cycle Complete!')} Profit: {pos_c(f'{cp:.8f}')} │ 💎 Vault: {pos_c(f'{profit_vault:.8f}')}")
            balance = original_cycle_balance
            working_balance = balance
            cycle_start_balance = original_cycle_balance
        else:
            buffer_scroll(f"  {yel_c('⚠️  Cycle ended without profit')} ({cp:.8f})")
            working_balance = balance

    def switch_to_wager():
        nonlocal mode, loss_streak, consecutive_losses
        nonlocal wager_cycle_start, wager_base_bet, wager_loss_amount
        nonlocal current_chance, nextbet, bethigh
        mode = "WAGER"
        loss_streak = 0
        consecutive_losses = 0
        wager_cycle_start = balance
        wager_base_bet = wager_cycle_start * (wager_bet_percent / 100.0)
        wager_loss_amount = 0.0
        current_chance = wager_chance
        bethigh = True
        nextbet = max(wager_base_bet, min_bet)
        buffer_scroll(f"  {pos_c('🟢 → WAGER MODE')} base_bet={yel_c(f'{wager_base_bet:.8f}')} chance={cya_c(f'{wager_chance:.2f}%')}")

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

        mul, payout = get_payout_and_multiplier(
            current_chance, risk_bonus_pct, (main_mode == 2), house_edge
        )
        bethigh = True
        nextbet = max(base_bet, min_bet)
        buffer_scroll(f"  {yel_c('🟡 → PROFIT MODE')} base={yel_c(f'{base_bet:.8f}')} chance={cya_c(f'{current_chance:.2f}%')} N={allowed_losses} mul={mul:.4f}x")

    def roll_stake_dice(chance_pct: float, high: bool = True) -> tuple[float, bool, float]:
        """
        Simulate real Stake Dice:
          Roll: 0.00 to 99.99
          Target when High=True (Roll Over): target = 100.0 - chance_pct
          Win if roll >= target
          Payout: (1 - house_edge/100) / (chance_pct/100)
        """
        roll = round(random.uniform(0.00, 99.99), 2)
        if high:
            target = round(100.0 - chance_pct, 2)
            won = roll >= target
        else:
            target = round(chance_pct, 2)
            won = roll < target

        cd = max(0.0001, min(0.9999, chance_pct / 100.0))
        payout = (1.0 - house_edge / 100.0) / cd
        if payout <= 1.0:
            payout = 1.0001
        return roll, won, payout

    # ── STARTUP BANNER ─────────────────────────────────────────────
    update_base()
    if main_mode == 1:
        switch_to_wager()
    else:
        switch_to_profit()

    if not quiet:
        print(cn(51, "═" * 74, True))
        print(cn(255, "  💎 FUSION BOT v4.1 — Real Simulation Engine (fusion_bot_gamblerbot.py)", True))
        print(cn(51, "═" * 74, True))
        print(f"  Strategy       : {pos_c('WAGER FOCUS + RECOVERY') if main_mode == 1 else yel_c('PROFIT FOCUS')}")
        print(f"  Starting Bal   : {_wc(f'{session_start_balance:.8f}')}")
        print(f"  Loss Cut Pct   : {neg_c(f'{loss_cut_percent:.2f}%')}  │  Recover Pct: {yel_c(f'{recover_profit_pct:.2f}%')}")
        print(f"  Wager Target   : {cya_c(f'{wager_target:.2f}')} (Enabled: {enable_wager_target})")
        loss_info = f"Auto (Risk {risk_alpha*100:.2f}%)" if auto_cal_allowed_loss else f"Fixed ({allowed_losses})"
        print(f"  Allowed Losses : {_wc(loss_info)}  │  Stop Profit: {pos_c(f'{stop_profit_ratio*100:.1f}%')}")
        print(f"  Roll Delay     : {_wc(f'{round_delay}s')}  │  Max Rounds: {_wc(str(max_rounds))}")
        print(cn(240, "  💡 Press Ctrl+C or type 'q' + Enter at any time to stop"))
        print(cn(51, "═" * 74, True))
        print()

    # Terminal stdin listener for interactive stop
    if not quiet and sys.stdin.isatty():
        w_thread = threading.Thread(target=_stdin_watcher, daemon=True)
        w_thread.start()

    # ─────────────────────────────────────────────────────────────
    # SIMULATION LOOP (Runs round by round)
    # ─────────────────────────────────────────────────────────────
    for rnd in range(1, max_rounds + 1):
        if _user_stop:
            stop_reason = "USER_STOP"
            break

        total_bets += 1
        current_bet = nextbet
        current_roll_chance = current_chance
        current_high = bethigh
        total_wagered += current_bet

        # Roll Dice on Stake
        roll_val, won, payout = roll_stake_dice(current_roll_chance, current_high)

        if won:
            round_pnl = current_bet * (payout - 1.0)
        else:
            round_pnl = -current_bet

        balance += round_pnl
        working_balance = balance
        net_pnl = profit_vault + (balance - original_cycle_balance)

        # ── WIN BRANCH ───────────────────────────────────────────
        if won:
            win_count += 1
            loss_streak = 0
            consecutive_losses = 0

            if mode == "WAGER":
                nextbet = max(wager_base_bet, min_bet)
                current_chance = wager_chance

                # Target reached check
                if main_mode == 1 and enable_wager_target and total_wagered >= wager_target:
                    buffer_scroll(f"  {cya_c('🎯 Wager Target')} {wager_target:.2f} reached!")
                    separate_profit_reset()
                    stop_reason = "WAGER_TARGET_REACHED"
                    _user_stop = True

            else:  # PROFIT mode WIN
                if auto_chance and random_on_win:
                    current_chance = random_chance(chance_min, chance_max)
                else:
                    current_chance = chance_fixed

                update_base(current_chance)
                nextbet = max(base_bet, min_bet)

                # Mode 1 recovery check
                if main_mode == 1:
                    need = wager_loss_amount + (original_cycle_balance * recover_profit_pct / 100.0)
                    gain = balance - profit_cycle_start
                    if gain >= need:
                        buffer_scroll(f"  {pos_c('✅ Recovery WIN')} gain={pos_c(f'{gain:+.8f}')} (needed {need:.8f})")
                        separate_profit_reset()
                        switch_to_wager()

        # ── LOSE BRANCH ──────────────────────────────────────────
        else:
            lose_count += 1
            loss_streak += 1
            consecutive_losses += 1
            if loss_streak > max_loss_streak:
                max_loss_streak = loss_streak

            if mode == "WAGER":
                cycle_loss = wager_cycle_start - balance
                loss_pct = cycle_loss / wager_cycle_start * 100.0 if wager_cycle_start > 0 else 0.0

                if main_mode == 1 and loss_pct >= loss_cut_percent:
                    wager_loss_amount = cycle_loss
                    buffer_scroll(f"  {neg_c('⚠️  Loss Cut')} {loss_pct:.2f}% (loss: {cycle_loss:.8f}) → SWITCH TO PROFIT")
                    switch_to_profit()
                else:
                    nextbet = max(wager_base_bet, min_bet)
                    current_chance = wager_chance

            else:  # PROFIT mode LOSE
                if auto_chance and random_on_lose:
                    current_chance = random_chance(chance_min, chance_max)

                use_he = (main_mode == 2)
                mul, _ = get_payout_and_multiplier(
                    current_chance, risk_bonus_pct, use_he, house_edge
                )
                new_bet = current_bet * mul
                if new_bet > balance:
                    new_bet = balance * 0.9

                nextbet = max(new_bet, min_bet)

                if consecutive_losses >= allowed_losses:
                    buffer_scroll(f"  {ora_c('⛔')} {allowed_losses} losses reached → reset base bet")
                    update_base(current_chance)
                    consecutive_losses = 0
                    nextbet = max(base_bet, min_bet)

                if main_mode == 1:
                    need = wager_loss_amount + (original_cycle_balance * recover_profit_pct / 100.0)
                    gain = balance - profit_cycle_start
                    if gain >= need:
                        buffer_scroll(f"  {pos_c('✅ Recovery on Loss')} gain={pos_c(f'{gain:+.8f}')}")
                        separate_profit_reset()
                        switch_to_wager()

        # Enforce minimum bet
        if nextbet < min_bet:
            nextbet = min_bet

        # ── STOP RULES ───────────────────────────────────────────
        total_pnl = profit_vault + (balance - original_cycle_balance)
        profit_ratio = total_pnl / session_start_balance if session_start_balance > 0 else 0.0

        if stop_profit_ratio > 0 and profit_ratio >= stop_profit_ratio:
            buffer_scroll(f"  {pos_c('🎉 Profit Target Hit!')} ({profit_ratio * 100:.1f}% >= {stop_profit_ratio * 100:.1f}%)")
            separate_profit_reset()
            stop_reason = "PROFIT_TARGET_HIT"
            _user_stop = True

        elif stop_loss_ratio > 0 and profit_ratio <= -stop_loss_ratio:
            buffer_scroll(f"  {neg_c('🚨 Loss Limit Hit!')} ({profit_ratio * 100:.1f}%)")
            stop_reason = "LOSS_LIMIT_HIT"
            _user_stop = True

        elif stop_max_streak > 0 and loss_streak >= stop_max_streak:
            buffer_scroll(f"  {neg_c('🚨 Max Streak Hit!')} ({loss_streak})")
            stop_reason = "MAX_STREAK_HIT"
            _user_stop = True

        elif balance < min_bet * 2:
            buffer_scroll(f"  {neg_c('🚨 Busted: Balance too low!')} ({balance:.8f})")
            stop_reason = "BUSTED"
            _user_stop = True

        # ── CSV LOGGING ──────────────────────────────────────────
        log_csv_row(
            csv_path, rnd, mode, "win" if won else "lose",
            roll_val, current_bet, round_pnl, total_pnl, balance,
            loss_streak, profit_vault, consecutive_losses
        )

        # ── ATOMIC DUAL-LAYER TUI FRAME (Zero Jitter / Zero Flicker)
        if not quiet:
            tag = pos_c("🏆 WIN ") if won else neg_c("💀 LOSE")
            pnl_disp = pos_c(f"+{round_pnl:11.8f}") if round_pnl >= 0 else neg_c(f"{round_pnl:11.8f}")

            # Strictly 68 visible characters (never line-wraps on 80+ column terminal)
            roll_line = (
                f"  [{_wc(f'#{rnd:<5d}')}] {tag} │ Roll: {_wc(f'{roll_val:5.2f}')} │ "
                f"Bet: {yel_c(f'{current_bet:11.8f}')} │ PnL: {pnl_disp}"
            )
            buffer_scroll(roll_line)

            # Build fixed 11-line pinned HUD
            rt = time.time() - session_start_time
            if mode == "WAGER":
                cur_lpct = max(0.0, (wager_cycle_start - balance) / wager_cycle_start * 100.0) if wager_cycle_start > 0 else 0.0
            else:
                cur_lpct = 0.0

            need_r = wager_loss_amount + original_cycle_balance * recover_profit_pct / 100.0
            gain_r = balance - profit_cycle_start

            hud_box = build_pinned_hud(
                rnd=rnd, max_rnd=max_rounds, mode=mode, main_mode=main_mode,
                balance=balance, start_balance=session_start_balance,
                profit_vault=profit_vault, total_profit=total_pnl,
                next_bet=nextbet, next_chance=current_chance,
                win_count=win_count, lose_count=lose_count,
                loss_streak=loss_streak, max_loss_streak=max_loss_streak,
                total_wagered=total_wagered, wager_target=wager_target,
                allowed_losses=allowed_losses, consecutive_losses=consecutive_losses,
                loss_cut_pct=loss_cut_percent, current_loss_pct=cur_lpct,
                runtime=rt, recover_needed=need_r, current_gain=gain_r
            )
            render_frame(hud_box)

        if round_delay > 0:
            time.sleep(round_delay)

        if _user_stop:
            break

    # ─────────────────────────────────────────────────────────────
    # CLEANUP HUD & SHOW FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────
    if not quiet and hud_rendered_lines > 0:
        sys.stdout.write(f"\033[{hud_rendered_lines}A\033[J")
        sys.stdout.flush()

    runtime = time.time() - session_start_time
    total_pnl_final = profit_vault + (balance - original_cycle_balance)

    if quiet:
        import json
        res = {
            "rounds": total_bets,
            "stop_reason": stop_reason,
            "start_balance": session_start_balance,
            "final_balance": balance,
            "profit_vault": profit_vault,
            "total_profit": total_pnl_final,
            "win_count": win_count,
            "lose_count": lose_count,
            "max_loss_streak": max_loss_streak,
            "total_wagered": total_wagered,
            "runtime_s": runtime,
        }
        print(f"__RESULT_JSON__{json.dumps(res)}__RESULT_JSON__")
        return

    W = 74
    pnl_color = pos_c if total_pnl_final >= 0 else neg_c
    roi_pct = total_pnl_final / session_start_balance * 100.0 if session_start_balance > 0 else 0.0

    print()
    print(cn(51, "═" * W, True))
    print(cn(255, f"  💎 FUSION BOT v4.1 — SIMULATION SUMMARY  [{stop_reason.upper()}]", True))
    print(cn(51, "═" * W, True))
    print(f"  Strategy      : {pos_c('WAGER FOCUS+RECOVERY') if main_mode == 1 else yel_c('PROFIT FOCUS')}")
    print(f"  Total Rounds  : {_wc(f'{total_bets:,}')} / {max_rounds:,}")
    print(f"  Runtime       : {_wc(f'{runtime:.2f}s')} ({total_bets / max(0.001, runtime):.1f} rolls/sec)")
    print(f"  Start Balance : {session_start_balance:14.8f}")
    print(f"  Final Balance : {_wc(f'{balance:14.8f}')}")
    print(f"  Profit Vault  : {pos_c(f'{profit_vault:+14.8f}')}")
    print(f"  Net Total PnL : {pnl_color(f'{total_pnl_final:+14.8f}')} (ROI: {pnl_color(f'{roi_pct:+.2f}%')})")
    print(f"  Win / Loss    : {pos_c(str(win_count))} W  /  {neg_c(str(lose_count))} L  ({win_count / max(1, total_bets) * 100:.2f}%)")
    print(f"  Max Streak    : {neg_c(str(max_loss_streak))} consecutive losses")
    print(f"  Total Wagered : {cya_c(f'{total_wagered:.4f}')} / {wager_target:.2f}")
    print(f"  Session CSV   : {_gr(str(csv_path))}")
    print(cn(51, "═" * W, True))


if __name__ == "__main__":
    run_simulation()
