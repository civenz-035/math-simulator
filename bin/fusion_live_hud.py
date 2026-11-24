#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  💎 FUSION BOT v4.2 — Real-Time Live Terminal Dashboard          ║
║  Real Gambler.Bot & Local Simulator Live Projection Monitor      ║
║  Live ANSI Box HUD · Equity Curve · Milestone Stream · SSOT      ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
  python bin/fusion_live_hud.py                  # Interactive selector (Real / Sim / Auto)
  python bin/fusion_live_hud.py real             # Direct projection to Real Gambler.Bot
  python bin/fusion_live_hud.py sim              # Direct projection to Simulator (fusion_bot.py)
  python bin/fusion_live_hud.py auto             # Auto-detect latest active session
  python bin/fusion_live_hud.py -t real -n 12    # Flag syntax with 12 history rows
  python bin/fusion_live_hud.py --sim            # Shortcut flag for simulator
  python bin/fusion_live_hud.py --csv path.csv   # Custom CSV file path
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
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

# ── Windows non-blocking keyboard support ───────────────────────────────────
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# ── ANSI Color Helpers (identical to roll.py & fusion_bot.py) ───────────────
def cn(code: int, text: str, bold: bool = False) -> str:
    style = "1;" if bold else ""
    return f"\033[{style}38;5;{code}m{text}\033[0m"

def _wc(t: str | int | float) -> str: return cn(255, str(t), True)
def _gr(t: str | int | float) -> str: return cn(240, str(t), False)
def _dim(t: str | int | float) -> str: return cn(238, str(t), False)
def pos_c(t: str | int | float) -> str: return cn(82, str(t), True)
def neg_c(t: str | int | float) -> str: return cn(196, str(t), True)
def yel_c(t: str | int | float) -> str: return cn(220, str(t), True)
def cya_c(t: str | int | float) -> str: return cn(51, str(t), True)
def pur_c(t: str | int | float) -> str: return cn(171, str(t), True)
def blu_c(t: str | int | float) -> str: return cn(75, str(t), True)

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

# ── Graceful Stop & Command Switch ──────────────────────────────────────────
_user_stop = False
_target_switch: str | None = None

def _handle_sigint(sig, frame):
    global _user_stop
    _user_stop = True

signal.signal(signal.SIGINT, _handle_sigint)

# ── SSOT Config Reader ───────────────────────────────────────────────────────
_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?\}|\$(\w+)")

def load_env_config(repo_root: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    env_override = os.environ.get("FUSION_CONFIG") or os.environ.get("DICE_CONFIG")
    candidates = [
        Path(env_override) if env_override else None,
        repo_root / "config" / "fusion.env",
        repo_root / "fusion.env",
        repo_root / "config" / "dice.env",
        repo_root / "dice.env",
    ]
    for p in candidates:
        if p and p.is_file():
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            v = v.split("#", 1)[0].strip().strip("\"'")
                            cfg[k.strip()] = v
                break
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
    return cfg

def _gv(cfg: dict[str, str], key: str, default, cast_type=str):
    v = cfg.get(key, "").strip()
    if not v:
        return default
    try:
        return cast_type(v)
    except Exception:
        return default

# ── Target Resolution & CSV Path Locator ─────────────────────────────────────
def normalize_target_name(t: str | None) -> str:
    if not t:
        return "real"
    t_low = t.strip().lower()
    if t_low in ("1", "real", "bot", "gamblerbot", "gbb", "live"):
        return "real"
    if t_low in ("2", "sim", "simu", "simulator", "fusion_bot", "test"):
        return "sim"
    if t_low in ("3", "auto", "detect", "latest"):
        return "auto"
    return "real"

def resolve_target_file(repo_root: Path, target_norm: str, custom_path: str | None = None) -> tuple[Path, str, str]:
    """
    Resolves the target CSV file and returns: (path, display_badge, short_label)
    """
    if custom_path:
        p = Path(custom_path)
        return p, f"📄 CUSTOM [{p.name}]", "CUSTOM"

    logs_dir = repo_root / "logs"

    real_candidates = [
        logs_dir / "dice_session_real.csv",
        logs_dir / "dice_session_gamblerbot.csv",
        repo_root.parent / "logs" / "dice_session_real.csv",
        Path(r"c:\Users\User\simulator\logs\dice_session_real.csv"),
    ]

    sim_candidates = [
        logs_dir / "dice_session_sim.csv",
        repo_root.parent / "logs" / "dice_session_sim.csv",
        Path(r"c:\Users\User\simulator\logs\dice_session_sim.csv"),
    ]

    latest_candidates = [
        logs_dir / "dice_session_latest.csv",
        repo_root.parent / "logs" / "dice_session_latest.csv",
        Path.cwd() / "logs" / "dice_session_latest.csv",
        Path(r"c:\Users\User\simulator\logs\dice_session_latest.csv"),
    ]

    if target_norm == "real":
        for c in real_candidates:
            if c.is_file():
                return c, "🤖 GAMBLER.BOT [REAL]", "REAL"
        for c in latest_candidates:
            if c.is_file():
                return c, "🤖 GAMBLER.BOT [REAL*]", "REAL"
        return real_candidates[0], "🤖 GAMBLER.BOT [REAL]", "REAL"

    elif target_norm == "sim":
        for c in sim_candidates:
            if c.is_file():
                return c, "🎲 FUSION SIMU [SIM]", "SIM"
        for c in latest_candidates:
            if c.is_file():
                return c, "🎲 FUSION SIMU [SIM*]", "SIM"
        return sim_candidates[0], "🎲 FUSION SIMU [SIM]", "SIM"

    else:  # auto
        all_existing: list[tuple[float, Path, str]] = []
        for c in real_candidates:
            if c.is_file():
                try: all_existing.append((c.stat().st_mtime, c, "REAL"))
                except OSError: pass
        for c in sim_candidates:
            if c.is_file():
                try: all_existing.append((c.stat().st_mtime, c, "SIM"))
                except OSError: pass
        for c in latest_candidates:
            if c.is_file():
                try: all_existing.append((c.stat().st_mtime, c, "LATEST"))
                except OSError: pass

        if all_existing:
            all_existing.sort(key=lambda x: x[0], reverse=True)
            _, best_p, kind = all_existing[0]
            if kind == "REAL":
                return best_p, "⚡ AUTO [REAL BOT]", "REAL"
            elif kind == "SIM":
                return best_p, "⚡ AUTO [SIMULATOR]", "SIM"
            else:
                return best_p, "⚡ AUTO [LATEST CSV]", "AUTO"

        return latest_candidates[0], "⚡ AUTO [WAITING]", "AUTO"

def prompt_target_selection() -> str:
    """Interactive TTY target selection menu."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    W = 68
    print(header_line(cn(51, "💎 FUSION BOT v4.2 — Select Live Dashboard Target", True), W + 2))
    print(pad_line(f"Choose which instance to project live dashboard to:", W))
    print(pad_line("─" * W, W))
    print(pad_line(f"  {yel_c('[1]')} {pos_c('🤖 Gambler.Bot (Real / External Bot)')}", W))
    print(pad_line(f"      Source: logs/dice_session_real.csv", W))
    print(pad_line(f"  {yel_c('[2]')} {cya_c('🎲 Fusion Simu (Simulator: bin/fusion_bot.py)')}", W))
    print(pad_line(f"      Source: logs/dice_session_sim.csv", W))
    print(pad_line(f"  {yel_c('[3]')} {pur_c('⚡ Auto-Detect (Latest Active Session)')}", W))
    print(pad_line("─" * W, W))
    print(pad_line(f"Tip: You can switch live anytime with keys {yel_c('[1]')}, {yel_c('[2]')}, {yel_c('[3]')}", W))
    print(footer_line(W + 2))

    try:
        ans = input(cn(51, "\n  Select Target [1/2/3] (Press Enter for [1] Real Bot): ", True)).strip()
    except (EOFError, KeyboardInterrupt):
        return "real"

    if ans in ("2", "sim", "s", "simu"):
        return "sim"
    elif ans in ("3", "auto", "a"):
        return "auto"
    return "real"

# ══════════════════════════════════════════════════════════════════════════════
# MAIN HUD MONITOR
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global _user_stop, _target_switch
    repo_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="💎 FUSION BOT Live ANSI Dashboard")
    parser.add_argument("target_pos", nargs="?", default=None,
                        help="Target mode: 'real' (Gambler.Bot), 'sim' (fusion_bot.py), or 'auto'")
    parser.add_argument("--target", "-t", type=str, default=None,
                        help="Target mode: 'real', 'sim', or 'auto'")
    parser.add_argument("--real", action="store_true", help="Monitor Gambler.Bot (Real)")
    parser.add_argument("--sim", action="store_true", help="Monitor Fusion Simu (Simulator)")
    parser.add_argument("--auto", action="store_true", help="Auto-detect latest active session")
    parser.add_argument("--csv", type=str, default=None, help="Explicit path to dice session CSV")
    parser.add_argument("--history", "-n", type=int, default=10,
                        help="Number of recent bets to show in live stream (default: 10)")
    args = parser.parse_args()

    max_milestones = max(4, min(30, args.history))

    # Resolve target from flags or interactive prompt
    explicit_target: str | None = None
    if args.real:
        explicit_target = "real"
    elif args.sim:
        explicit_target = "sim"
    elif args.auto:
        explicit_target = "auto"
    elif args.target:
        explicit_target = normalize_target_name(args.target)
    elif args.target_pos:
        explicit_target = normalize_target_name(args.target_pos)

    if explicit_target is None and args.csv is None:
        if sys.stdin.isatty():
            current_target = prompt_target_selection()
        else:
            current_target = "real"
    else:
        current_target = explicit_target or "real"

    cfg = load_env_config(repo_root)
    wager_target = _gv(cfg, "FUSION_WAGER_TARGET", _gv(cfg, "WAGER_TARGET", 100.0, float), float)
    loss_cut_pct = _gv(cfg, "FUSION_LOSS_CUT_PCT", 4.0, float)
    allowed_losses = _gv(cfg, "FUSION_ALLOWED_LOSSES", 600, int)

    # Resolve target file
    csv_path, target_badge, target_label = resolve_target_file(repo_root, current_target, args.csv)

    # State tracking
    start_balance: float | None = None
    last_processed_round = 0
    total_wagered = 0.0
    win_count = 0
    lose_count = 0
    max_loss_streak = 0
    profit_vault = 0.0
    consecutive_losses = 0

    # Equity Graph State (width 54 chars, height 5)
    equity_width = 54
    equity_bins: list[tuple[int, float] | None] = [None] * equity_width
    equity_max_round = 0
    equity_history: list[tuple[int, float]] = []

    def _equity_display_max(round_n: int) -> int:
        step = 500
        return max(step, math.ceil(round_n / step) * step)

    def _put_equity_bin(round_n: int, val: float, horizon: int):
        x = min(equity_width - 1, round_n * (equity_width - 1) // max(1, horizon))
        equity_bins[x] = (round_n, val)

    def record_equity(round_n: int, val: float):
        nonlocal equity_bins, equity_max_round
        equity_history.append((round_n, val))
        horizon = _equity_display_max(round_n)
        if horizon != equity_max_round:
            equity_bins = [None] * equity_width
            for r, v in equity_history:
                _put_equity_bin(r, v, horizon)
            equity_max_round = horizon
        else:
            _put_equity_bin(round_n, val, horizon)

    def render_equity_graph() -> list[str]:
        samples = [(x, pt) for x, pt in enumerate(equity_bins) if pt is not None]
        if not samples:
            return []
        values = [pt[1] for _, pt in samples]
        low = min(values)
        high = max(values)
        if high == low:
            pad = max(abs(start_balance or 1.0) * 0.005, 0.01)
        else:
            pad = (high - low) * 0.08
        low -= pad
        high += pad
        span = high - low or 1.0

        graph_height = 5
        def y_for(val: float) -> int:
            scaled = (high - val) / span
            return max(0, min(graph_height - 1, round(scaled * (graph_height - 1))))

        grid = [[" " for _ in range(equity_width)] for _ in range(graph_height)]

        # Baseline
        if start_balance is not None and low <= start_balance <= high:
            base_y = y_for(start_balance)
            for x in range(equity_width):
                grid[base_y][x] = _dim("·")

        # Plot curve
        for x, (_, val) in samples:
            y = y_for(val)
            color_fn = pos_c if (start_balance and val >= start_balance) else neg_c
            grid[y][x] = color_fn("█")

        out = []
        W = 70
        out.append(pad_line(f"  {_wc('EQUITY CURVE')}  {_gr(f'Hi: {high:.4f} │ Lo: {low:.4f}')}", W))
        for row in grid:
            out.append(pad_line("  " + "".join(row), W))
        return out

    # Milestone history buffer
    milestones: list[str] = []

    def add_milestone(msg: str):
        nonlocal milestones
        milestones.append(msg)
        if len(milestones) > max_milestones:
            milestones = milestones[-max_milestones:]

    # Screen clear on launch
    sys.stdout.write("\033[2J\033[H\033[?25l")
    sys.stdout.flush()

    def render_waiting_box():
        W = 70
        lines: list[str] = []
        lines.append(header_line(cn(51, f"💎 FUSION BOT v4.2 — {target_badge}", True), W + 2))
        lines.append(pad_line(f"Source File: {cya_c(str(csv_path.name))}", W))
        lines.append(pad_line("─" * W, W))
        lines.append(pad_line("", W))
        lines.append(pad_line(f"  {yel_c('⏳ Waiting for bets to start stream...')} ", W))
        if target_label == "REAL":
            lines.append(pad_line(f"  {_wc('Target :')} External Gambler.Bot (Real Play)", W))
            lines.append(pad_line(f"  {_gr('Path   :')} {_dim(str(csv_path))}", W))
            lines.append(pad_line(f"  {_wc('Action :')} Start your bot in Gambler.Bot app", W))
        else:
            lines.append(pad_line(f"  {_wc('Target :')} Simulator (bin/fusion_bot.py)", W))
            lines.append(pad_line(f"  {_gr('Path   :')} {_dim(str(csv_path))}", W))
            lines.append(pad_line(f"  {_wc('Action :')} Run simulator: {cya_c('py bin/fusion_bot.py')}", W))
        lines.append(pad_line("", W))
        lines.append(pad_line("─" * W, W))
        lines.append(pad_line(f"Hotkeys: {yel_c('[1] Real Bot')}  {yel_c('[2] Simu')}  {yel_c('[3] Auto')}  {neg_c('[Q] Quit')}", W))
        lines.append(footer_line(W + 2))

        sys.stdout.write("\033[H")
        for line in lines:
            sys.stdout.write(f"\r\033[2K{line}\n")
        sys.stdout.write("\033[J")
        sys.stdout.flush()

    def render_hud(
        round_num: int,
        mode_str: str,
        res_str: str,
        roll_val: float,
        bet_amt: float,
        round_pnl: float,
        net_pnl: float,
        balance: float,
        streak: int,
        vault: float,
        chance: float = 0.0,
        payout: float = 0.0,
        loss_mul: float = 1.0,
    ):
        W = 70

        mode_clean = mode_str.upper()
        if "WAGER" in mode_clean:
            mode_badge = f"{pos_c('● WAGER FOCUS')} {_gr('(98% farming)')}"
        elif "PROFIT" in mode_clean:
            mode_badge = f"{yel_c('▲ PROFIT FOCUS')} {_gr('(Martingale)')}"
        elif "RECOVER" in mode_clean:
            mode_badge = f"{pur_c('♻ RECOVERY')} {_gr('(Catch-up)')}"
        else:
            mode_badge = cya_c(mode_clean)

        pnl_c = pos_c if net_pnl >= 0 else neg_c
        roi_pct = (net_pnl / start_balance * 100.0) if start_balance and start_balance > 0 else 0.0

        lines: list[str] = []
        lines.append(header_line(cn(51, f"💎 FUSION BOT v4.2 — {target_badge}", True), W + 2))
        lines.append(col_row(f"Mode: {mode_badge}", f"Round: {_wc(str(round_num))}", 42, W))
        lines.append(col_row(f"Src : {cya_c(csv_path.name)} ({target_label})", f"Win/Loss: {pos_c(str(win_count))}/{neg_c(str(lose_count))}", 42, W))
        lines.append(pad_line("─" * W, W))

        lines.append(col_row(
            f"💰 Balance: {_wc(f'{balance:.8f}')}",
            f"Start: {_gr(f'{start_balance:.4f}') if start_balance else '---'}", 36, W
        ))
        lines.append(col_row(
            f"💎 Vault:   {cya_c(f'{vault:.8f}')}",
            f"Net P/L: {pnl_c(f'{net_pnl:+.8f}')}", 36, W
        ))
        lines.append(col_row(
            f"📈 Wagered: {cya_c(f'{total_wagered:.4f}')}",
            f"ROI:     {pnl_c(f'{roi_pct:+.2f}%')}", 36, W
        ))
        lines.append(col_row(
            f"🎯 Chance:  {cya_c(f'{chance:.2f}%')} │ Payout: {_wc(f'{payout:.4f}x')}",
            f"Loss Mul: {yel_c(f'{loss_mul:.4f}x')}", 42, W
        ))
        lines.append(pad_line("─" * W, W))

        # Mode Specific target progress bar
        if "WAGER" in mode_clean:
            wager_pb = progress_bar(total_wagered, wager_target, 16)
            lines.append(col_row(
                f"🎯 Wager Target: {cya_c(f'{total_wagered:.2f}')}/{_gr(f'{wager_target:.2f}')}",
                wager_pb, 40, W
            ))
            cycle_loss = max(0.0, (start_balance or balance) - balance)
            cycle_loss_pct = (cycle_loss / start_balance * 100.0) if start_balance else 0.0
            loss_pb = progress_bar(cycle_loss_pct, loss_cut_pct, 16)
            lines.append(col_row(
                f"📉 Loss Cut:     {neg_c(f'{cycle_loss_pct:.2f}%')}/{_gr(f'{loss_cut_pct:.2f}%')}",
                loss_pb, 40, W
            ))
        else:
            con_pb = progress_bar(consecutive_losses, allowed_losses, 16)
            lines.append(col_row(
                f"⚡ Allowed Loss: {neg_c(str(consecutive_losses))}/{_gr(str(allowed_losses))}",
                con_pb, 40, W
            ))
            lines.append(col_row(
                f"🎲 Last Bet:     {yel_c(f'{bet_amt:.8f}')}",
                f"Streak: {neg_c(str(streak))} (Max {max_loss_streak})", 40, W
            ))

        lines.append(pad_line("─" * W, W))

        # Equity Graph
        eq_lines = render_equity_graph()
        lines.extend(eq_lines)
        lines.append(pad_line("─" * W, W))

        # Recent Milestones Feed (Live Bet Stream)
        lines.append(pad_line(f"  {_wc(f'LIVE BET STREAM (Last {len(milestones)})')}", W))
        for m in milestones:
            lines.append(pad_line("  " + m, W))

        lines.append(pad_line("─" * W, W))
        lines.append(pad_line(f"Hotkeys: {yel_c('[1] Real Bot')}  {yel_c('[2] Simu')}  {yel_c('[3] Auto')}  {neg_c('[Q] Quit')}", W))
        lines.append(footer_line(W + 2))

        # ANSI Home Cursor (Zero Flicker, No Repetition)
        sys.stdout.write("\033[H")
        for line in lines:
            sys.stdout.write(f"\r\033[2K{line}\n")
        sys.stdout.write("\033[J")  # Clear any leftover trailing lines
        sys.stdout.flush()

    fp = None
    header_map: dict[str, int] = {}
    last_render_time = 0.0

    def reset_state():
        nonlocal start_balance, last_processed_round, total_wagered
        nonlocal win_count, lose_count, max_loss_streak, profit_vault, consecutive_losses
        nonlocal equity_bins, equity_max_round, equity_history, milestones, fp, header_map
        if fp:
            try: fp.close()
            except Exception: pass
            fp = None
        header_map.clear()
        start_balance = None
        last_processed_round = 0
        total_wagered = 0.0
        win_count = 0
        lose_count = 0
        max_loss_streak = 0
        profit_vault = 0.0
        consecutive_losses = 0
        equity_bins = [None] * equity_width
        equity_max_round = 0
        equity_history.clear()
        milestones.clear()

    try:
        while not _user_stop:
            # ── Check Non-Blocking Keyboard Input (Hotkeys: 1, 2, 3, Q) ──
            if HAS_MSVCRT and msvcrt.kbhit():
                try:
                    ch = msvcrt.getch()
                    ch_str = ch.decode("utf-8", errors="ignore").lower()
                except Exception:
                    ch_str = ""
                if ch_str == "q":
                    _user_stop = True
                    break
                elif ch_str in ("1", "r"):
                    if current_target != "real":
                        current_target = "real"
                        csv_path, target_badge, target_label = resolve_target_file(repo_root, "real", args.csv)
                        reset_state()
                        continue
                elif ch_str in ("2", "s"):
                    if current_target != "sim":
                        current_target = "sim"
                        csv_path, target_badge, target_label = resolve_target_file(repo_root, "sim", args.csv)
                        reset_state()
                        continue
                elif ch_str in ("3", "a"):
                    if current_target != "auto":
                        current_target = "auto"
                        csv_path, target_badge, target_label = resolve_target_file(repo_root, "auto", args.csv)
                        reset_state()
                        continue

            # Auto mode re-check latest file periodically
            if current_target == "auto" and (time.time() - last_render_time > 2.0):
                new_p, new_badge, new_label = resolve_target_file(repo_root, "auto", args.csv)
                if new_p != csv_path:
                    csv_path, target_badge, target_label = new_p, new_badge, new_label
                    reset_state()
                    continue

            if not csv_path.is_file():
                if time.time() - last_render_time > 0.5:
                    render_waiting_box()
                    last_render_time = time.time()
                time.sleep(0.1)
                continue

            try:
                curr_size = csv_path.stat().st_size
            except OSError:
                curr_size = 0

            # File created or reopened
            if fp is None:
                try:
                    fp = open(csv_path, "r", encoding="utf-8", errors="replace")
                except OSError:
                    time.sleep(0.1)
                    continue

            # Check if file was truncated/restarted by Bot
            if curr_size < fp.tell():
                reset_state()
                continue

            line = fp.readline()
            if not line:
                if last_processed_round == 0 and (time.time() - last_render_time > 0.5):
                    render_waiting_box()
                    last_render_time = time.time()

                # Flush CRT EOF cache on Windows
                try:
                    fp.seek(fp.tell())
                except Exception:
                    pass
                time.sleep(0.08)
                continue

            line_str = line.strip()
            if not line_str:
                continue

            # Header detection
            if line_str.startswith("Round,") or line_str.startswith('"Round",'):
                parts = [p.strip().strip("\"'") for p in line_str.split(",")]
                header_map = {col.lower(): idx for idx, col in enumerate(parts)}
                continue

            parts = [p.strip().strip("\"'") for p in line_str.split(",")]
            if len(parts) < 5:
                continue

            def get_col(name: str, idx: int, default: str = "") -> str:
                if name.lower() in header_map:
                    col_idx = header_map[name.lower()]
                    if col_idx < len(parts):
                        return parts[col_idx]
                if idx < len(parts):
                    return parts[idx]
                return default

            try:
                r_num = int(get_col("round", 0, "0"))
                mode_str = get_col("mode", 1, "WAGER")
                res_str = get_col("result", 2, "win").lower()
                roll_val = float(get_col("roll", 3, "0.0") or 0.0)
                bet_amt = float(get_col("bet", 4 if "roll" in header_map else 3, "0.0") or 0.0)
                round_pnl = float(get_col("roundpnl", 5 if "roll" in header_map else 4, "0.0") or 0.0)
                net_pnl = float(get_col("netpnl", 6 if "roll" in header_map else 5, "0.0") or 0.0)
                balance = float(get_col("balance", 7 if "roll" in header_map else 6, "0.0") or 0.0)
                streak = int(get_col("lossstreak", 8 if "roll" in header_map else 7, "0") or 0)
                vault = float(get_col("profitvault", 9 if "roll" in header_map else 8, "0.0") or 0.0)
                con_loss = int(get_col("consecutivelosses", 10, "0") or 0)
                chance_val = float(get_col("chance", 11, "0.0") or 0.0)
                payout_val = float(get_col("payout", 12, "0.0") or 0.0)
                loss_mul_val = float(get_col("lossmul", 13, "0.0") or 0.0)
            except Exception:
                continue

            if chance_val <= 0:
                if "WAGER" in mode_str.upper():
                    chance_val = _gv(cfg, "FUSION_WAGER_CHANCE", 98.0, float)
                    loss_mul_val = 1.0
                else:
                    chance_val = _gv(cfg, "FUSION_CHANCE_FIXED", 35.0, float)
                    if _gv(cfg, "AUTO_CAL_LOSS_MUL", 1, int) != 0:
                        risk_bonus = _gv(cfg, "FUSION_RISK_BONUS_PCT", 10.0, float)
                        he = _gv(cfg, "HE", 1.0, float)
                        p_win = max(0.0001, min(0.9999, chance_val / 100.0))
                        mult = (1.0 - he / 100.0) / p_win
                        loss_mul_val = 1.0 + (mult - 1.0) * (1.0 + risk_bonus / 100.0)
                    else:
                        loss_mul_val = _gv(cfg, "FUSION_MANUAL_LOSS_MUL", 1.05, float)
            if payout_val <= 0 and chance_val > 0:
                he = _gv(cfg, "HE", 1.0, float)
                payout_val = (100.0 - he) / chance_val

            if r_num <= last_processed_round and last_processed_round > 0:
                continue
            last_processed_round = r_num

            # Detect initial starting balance accurately from first row
            if start_balance is None:
                start_balance = balance - round_pnl
                record_equity(0, start_balance)

            total_wagered += bet_amt
            if res_str == "win":
                win_count += 1
            else:
                lose_count += 1

            if streak > max_loss_streak:
                max_loss_streak = streak
            consecutive_losses = con_loss

            record_equity(r_num, balance)

            # Build milestone entry
            ts = time.strftime("%H:%M:%S")
            roll_disp = f"Roll: {roll_val:5.2f}" if roll_val > 0 else "           "
            if res_str == "win":
                tag = pos_c("[WIN] ")
                pnl_disp = pos_c(f"+{round_pnl:.8f}")
            else:
                tag = neg_c("[LOSE]")
                pnl_disp = neg_c(f"{round_pnl:.8f}")

            mode_tag = yel_c("[P]") if "PROFIT" in mode_str.upper() else pos_c("[W]")
            ms_entry = f"{_gr(ts)} {mode_tag} #{r_num:<5d} {tag} {roll_disp} │ Bet: {bet_amt:.8f} │ PnL: {pnl_disp}"
            add_milestone(ms_entry)

            render_hud(
                r_num, mode_str, res_str, roll_val, bet_amt,
                round_pnl, net_pnl, balance, streak, vault,
                chance=chance_val, payout=payout_val, loss_mul=loss_mul_val
            )
            last_render_time = time.time()

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        if fp:
            try: fp.close()
            except Exception: pass
        print(cn(51, f"  Live Monitor stopped gracefully. (Target was: {target_label})"))

if __name__ == "__main__":
    main()
