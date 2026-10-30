#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  💎 FUSION BOT v4.1 — Real-Time Live Terminal Dashboard          ║
║  Tails logs/dice_session_latest.csv from Gambler.Bot in real-time║
║  Live ANSI Box HUD · Equity Curve · Milestone Stream · SSOT      ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
  python bin/fusion_live_hud.py
  python bin/fusion_live_hud.py --history 12
  python bin/fusion_live_hud.py --csv logs/dice_session_latest.csv
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
import time
import unicodedata

# ── Force UTF-8 on Windows Consoles ─────────────────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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

# ── Graceful Stop ────────────────────────────────────────────────────────────
_user_stop = False
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

# ── CSV Path Locator ─────────────────────────────────────────────────────────
def find_csv_file(repo_root: Path, custom_path: str | None = None) -> Path:
    if custom_path:
        return Path(custom_path)
    candidates = [
        repo_root / "logs" / "dice_session_latest.csv",
        repo_root.parent / "logs" / "dice_session_latest.csv",
        Path.cwd() / "logs" / "dice_session_latest.csv",
        Path.cwd() / "dice_session_latest.csv",
        Path(r"c:\Users\User\simulator\logs\dice_session_latest.csv"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]

# ══════════════════════════════════════════════════════════════════════════════
# MAIN HUD MONITOR
# ══════════════════════════════════════════════════════════════════════════════
def main():
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="FUSION BOT Live ANSI Dashboard")
    parser.add_argument("--csv", type=str, default=None, help="Path to dice_session_latest.csv")
    parser.add_argument("--history", "-n", type=int, default=10, help="Number of recent bets to show in live stream (default: 10)")
    args = parser.parse_args()

    max_milestones = max(4, min(30, args.history))

    cfg = load_env_config(repo_root)
    wager_target = _gv(cfg, "FUSION_WAGER_TARGET", _gv(cfg, "WAGER_TARGET", 100.0, float), float)
    loss_cut_pct = _gv(cfg, "FUSION_LOSS_CUT_PCT", 4.0, float)
    recover_profit_pct = _gv(cfg, "FUSION_RECOVER_PROFIT_PCT", 1.0, float)
    allowed_losses = _gv(cfg, "FUSION_ALLOWED_LOSSES", 600, int)
    main_mode = _gv(cfg, "FUSION_MAIN_MODE", 1, int)

    csv_path = find_csv_file(repo_root, args.csv)

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
        lines.append(header_line(cn(51, "💎 FUSION BOT v4.1 — Gambler.Bot Live Monitor", True), W + 2))
        lines.append(col_row(f"Mode: {mode_badge}", f"Round: {_wc(str(round_num))}", 42, W))
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

        lines.append(footer_line(W + 2))

        # ANSI Home Cursor (Zero Flicker, No Repetition)
        sys.stdout.write("\033[H")
        for line in lines:
            sys.stdout.write(f"\r\033[2K{line}\n")
        sys.stdout.write("\033[J")  # Clear any leftover trailing lines
        sys.stdout.flush()

    fp = None
    header_map: dict[str, int] = {}

    try:
        while not _user_stop:
            if not csv_path.is_file():
                time.sleep(0.3)
                continue

            try:
                curr_size = csv_path.stat().st_size
            except OSError:
                curr_size = 0

            # File created or reopened
            if fp is None:
                fp = open(csv_path, "r", encoding="utf-8", errors="replace")

            # Check if file was truncated/restarted by Gambler.Bot
            if curr_size < fp.tell():
                fp.close()
                fp = open(csv_path, "r", encoding="utf-8", errors="replace")
                header_map.clear()
                start_balance = None
                equity_bins = [None] * equity_width
                equity_history.clear()
                last_processed_round = 0
                milestones.clear()
                continue

            line = fp.readline()
            if not line:
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
            except Exception:
                continue

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
                round_pnl, net_pnl, balance, streak, vault
            )

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        if fp:
            try: fp.close()
            except Exception: pass
        print(cn(51, "  Live Monitor stopped gracefully."))

if __name__ == "__main__":
    main()
