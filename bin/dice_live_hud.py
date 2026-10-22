#!/usr/bin/env python3
"""
DICEBOT LIVE HUD MONITOR
============================================================
Live Terminal Dashboard for DiceBot (Gambler.Bot 5.35)
Tails logs/dice_session_latest.csv in real-time and renders
the exact same Live ANSI Box HUD & Equity Curve Graph as roll.py!
============================================================
"""

from __future__ import annotations

import csv
import math
import os
import re
import signal
import sys
import time
import unicodedata
from pathlib import Path

# Force UTF-8 on Windows Consoles
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ANSI Color Helpers
def cn(code: int, text: str, bold: bool = False) -> str:
    style = "1;" if bold else ""
    return f"\033[{style}38;5;{code}m{text}\033[0m"

def _wc(text: str) -> str: return cn(255, str(text), True)
def _gr(text: str) -> str: return cn(235, str(text), False)
def pos_c(text: str) -> str: return cn(82, str(text), True)
def neg_c(text: str) -> str: return cn(124, str(text), True)

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def char_width(ch: str) -> int:
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1

def visual_len(s: str) -> int:
    clean = _ANSI_REGEX.sub("", s)
    return sum(char_width(c) for c in clean)

def pad_line(content: str, target_width: int = 70) -> str:
    v_len = visual_len(content)
    pad = max(0, target_width - v_len)
    return f"│ {content}{' ' * pad} │"

def make_fixed_row(left: str, right: str, left_w: int = 34, total_w: int = 70) -> str:
    l_v = visual_len(left)
    l_pad = max(0, left_w - l_v)
    r_v = visual_len(right)
    r_pad = max(0, (total_w - left_w) - r_v)
    return pad_line(f"{left}{' ' * l_pad}{right}{' ' * r_pad}", total_w)

def make_header_border(title: str, total_width: int = 72) -> str:
    t_len = visual_len(title)
    tot = max(0, total_width - t_len - 2)
    l_d = tot // 2
    r_d = tot - l_d
    return f"┌{'─' * l_d} {title} {'─' * r_d}┐"

def progress_bar(val: float, total: float, width: int = 16) -> str:
    if total <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, val / total))
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"

# Graceful stop
_user_stop = False
def _handle_sigint(sig, frame):
    global _user_stop
    _user_stop = True

signal.signal(signal.SIGINT, _handle_sigint)

def main():
    repo_root = Path(__file__).resolve().parent.parent
    csv_file = repo_root / "logs" / "dice_session_latest.csv"

    # State variables
    hud_rendered_lines = 0
    equity_graph_width = 54
    equity_graph_bins = [None] * equity_graph_width
    equity_graph_max_round = 0
    equity_history = []
    start_balance = None

    def print_milestone(msg: str):
        nonlocal hud_rendered_lines
        if hud_rendered_lines > 0:
            sys.stdout.write(f"\033[{hud_rendered_lines}A")
            sys.stdout.write("\033[J")
            hud_rendered_lines = 0
        sys.stdout.write(f"{msg}\n")
        sys.stdout.flush()

    def _equity_display_max(round_n: int) -> int:
        step = 5000
        horizon = max(step, math.ceil(round_n / step) * step)
        return horizon

    def _put_equity_in_bin(round_n: int, value: float, horizon: int):
        x = min(equity_graph_width - 1, round_n * (equity_graph_width - 1) // max(1, horizon))
        equity_graph_bins[x] = (round_n, value)

    def record_equity_point(round_n: int, value: float):
        nonlocal equity_graph_bins, equity_graph_max_round
        equity_history.append((round_n, value))
        horizon = _equity_display_max(round_n)
        if horizon != equity_graph_max_round:
            equity_graph_bins = [None] * equity_graph_width
            for p_rnd, p_val in equity_history:
                _put_equity_in_bin(p_rnd, p_val, horizon)
            equity_graph_max_round = horizon
        else:
            _put_equity_in_bin(round_n, value, horizon)

    def render_equity_graph(r_num: int, current_mode: str, cur_bal: float) -> list[str]:
        samples = [(x, pt) for x, pt in enumerate(equity_graph_bins) if pt is not None]
        if not samples:
            return []
        values = [pt[1] for _, pt in samples]
        low = min(values)
        high = max(values)
        baseline_visible = (start_balance is not None) and (low <= start_balance <= high)
        if high == low:
            padding = max(abs(start_balance or 1.0) * 0.005, 0.01)
        else:
            padding = (high - low) * 0.08
        low -= padding
        high += padding
        span = high - low or 1.0

        graph_height = 7
        def y_for(val: float) -> int:
            scaled = (high - val) / span
            return max(0, min(graph_height - 1, round(scaled * (graph_height - 1))))

        grid = [[" " for _ in range(equity_graph_width)] for _ in range(graph_height)]
        if baseline_visible:
            baseline_y = y_for(start_balance)
            for x in range(equity_graph_width):
                grid[baseline_y][x] = "┄"

        x_pos = [x for x, _ in samples]
        y_pos = [y_for(v) for v in values]
        for i in range(1, len(samples)):
            x0, x1 = x_pos[i-1], x_pos[i]
            y0, y1 = y_pos[i-1], y_pos[i]
            if x1 <= x0: continue
            for x in range(x0, x1 + 1):
                t = (x - x0) / (x1 - x0)
                y = round(y0 + (y1 - y0) * t)
                grid[y][x] = "─" if y0 == y1 else ("╲" if y1 > y0 else "╱")

        for x, y in zip(x_pos, y_pos): grid[y][x] = "·"
        grid[y_pos[-1]][x_pos[-1]] = "●"

        equity_now = values[-1]
        delta_pct = ((equity_now / start_balance) - 1.0) * 100.0 if start_balance else 0.0
        title = _wc("LIVE DICEBOT REAL-TIME EQUITY")
        header = make_header_border(title)
        stats = f"BOT: {current_mode}  EQUITY {equity_now:.6g}  Δ {delta_pct:+.5g}%"
        lines = [header, pad_line(stats, 70)]

        line_color = pos_c if (start_balance and equity_now >= start_balance) else neg_c
        ticks = (high, (high + low) / 2.0, low)
        for row, tick in enumerate(ticks):
            label = cn(242, f"{tick:>10.4g}")
            plot = line_color("".join(grid[row]))
            lines.append(pad_line(f"{label} │ {plot}", 70))

        axis = f"R 0{'─'*22} LIVE BET #{r_num:,} {'─'*22}MAX ~{equity_graph_max_round:,}"
        lines.append(pad_line(axis, 70))
        lines.append("└" + "─" * 72 + "┘")
        return lines

    def render_hud(r_num: int, mode_name: str, roll_val: int, res_str: str, bet: float, round_pnl: float, net_pnl: float, bal: float, loss_streak: int):
        nonlocal hud_rendered_lines
        bal_c = neg_c(f"{bal:13.8f}") if (start_balance and bal < start_balance) else cn(28, f"{bal:13.8f}", True)
        icon = pos_c("WIN ") if res_str == "win" else neg_c("LOSS")
        round_pnl_c = pos_c(f"+{round_pnl:11.8f}") if round_pnl > 0 else (neg_c(f"{round_pnl:11.8f}") if round_pnl < 0 else _gr(f"{round_pnl:11.8f}"))
        net_pnl_c = pos_c(f"+{net_pnl:11.8f}") if net_pnl > 0 else (neg_c(f"{net_pnl:11.8f}") if net_pnl < 0 else _gr(f"{net_pnl:11.8f}"))
        roll_c = cn(45, f"{roll_val:4d}", True)

        lines = []
        lines.append(make_header_border(cn(196 if mode_name=="BRAVE" else 39, f"{mode_name} REAL-TIME BOT HUD", True)))
        l1 = f"{_wc('LIVE ROUND')} : {r_num}"
        r1 = f"{_wc('ACTIVE MODE')} : {cn(208, mode_name, True)}"
        lines.append(make_fixed_row(l1, r1, 34, 70))

        l2 = f"{_wc('LAST ROLL')}  : {roll_c}  [{icon}]"
        r2 = f"{_wc('LOSS STREAK')}: {loss_streak}"
        lines.append(make_fixed_row(l2, r2, 34, 70))

        lines.append("├" + "─" * 72 + "┤")
        l3 = f"{_wc('CURRENT BET')}: {bet:12.8f}"
        r3 = f"{_wc('BALANCE')}    : {bal_c}"
        lines.append(make_fixed_row(l3, r3, 34, 70))

        l4 = f"{_wc('ROUND PnL')}  : {round_pnl_c}"
        r4 = f"{_wc('NET PnL')}    : {net_pnl_c}"
        lines.append(make_fixed_row(l4, r4, 34, 70))
        lines.append("└" + "─" * 72 + "┘")

        eq_lines = render_equity_graph(r_num, mode_name, bal)
        all_lines = eq_lines + lines

        if hud_rendered_lines > 0:
            sys.stdout.write(f"\033[{hud_rendered_lines}A")
        for line in all_lines:
            sys.stdout.write(f"\r\033[2K{line}\n")
        sys.stdout.flush()
        hud_rendered_lines = len(all_lines)

    # Main Monitor Loop
    print(cn(136, "=" * 74))
    print(cn(255, "  DICEBOT LIVE HUD MONITOR (Real-Time Terminal Dashboard)"))
    print(cn(136, "=" * 74))
    print(cn(245, f"  Watching: {csv_file}"))
    print(cn(245, "  Waiting for DiceBot bets... (Press Ctrl+C to exit)"))
    print(cn(136, "=" * 74))

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    last_processed_round = 0
    fp = None

    try:
        while not _user_stop:
            if not csv_file.is_file():
                time.sleep(0.5)
                continue

            if fp is None:
                fp = open(csv_file, "r", encoding="utf-8", errors="replace")

            line = fp.readline()
            if not line:
                time.sleep(0.05)
                continue

            parts = line.strip().split(",")
            if len(parts) < 8 or parts[0] == "Round":
                continue

            try:
                r_num = int(parts[0])
                mode_name = parts[1]
                roll_val = int(parts[2])
                res_str = parts[3]
                bet_amt = float(parts[4])
                round_pnl = float(parts[5])
                net_pnl = float(parts[6])
                bal_amt = float(parts[7])
                loss_streak = int(parts[8]) if len(parts) > 8 and parts[8] else 0
                rare_tag = parts[9] if len(parts) > 9 and parts[9] else None
                won_amt = float(parts[10]) if len(parts) > 10 and parts[10] else 0.0
            except (ValueError, IndexError):
                continue

            if r_num <= last_processed_round:
                continue
            last_processed_round = r_num

            if start_balance is None:
                start_balance = bal_amt - net_pnl
                record_equity_point(0, start_balance)

            record_equity_point(r_num, bal_amt)

            # Emit milestone event feed
            if rare_tag:
                print_milestone(cn(226, f"  [#{r_num:>6d}] 🎯 {rare_tag:<5s} │ Roll: {roll_val:>4d} │ Bet: {bet_amt:>12.8f} │ Won: +{won_amt:.8f}", True))
            elif res_str == "win":
                print_milestone(pos_c(f"  [#{r_num:>6d}] 🏆 WIN   │ Roll: {roll_val:>4d} │ Bet: {bet_amt:>12.8f} │ Won: +{won_amt:.8f}"))
            else:
                print_milestone(neg_c(f"  [#{r_num:>6d}] 💀 LOSS  │ Roll: {roll_val:>4d} │ Bet: {bet_amt:>12.8f} │ Lose: -{bet_amt:.8f}"))

            render_hud(r_num, mode_name, roll_val, res_str, bet_amt, round_pnl, net_pnl, bal_amt, loss_streak)

    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        if fp:
            try: fp.close()
            except Exception: pass
        print(cn(136, "  Monitor stopped."))

if __name__ == "__main__":
    main()
