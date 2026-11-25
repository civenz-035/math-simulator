#!/usr/bin/env python3
"""
dice-server.py — Dice Lab API + PWA server (local / Tailscale).

Binds 0.0.0.0:7373 by default (override with DICE_PORT) so phones and
tablets on the same Tailscale network can open the dashboard.

Endpoints
  GET  /                     web/dice-ui.html (PWA shell)
  GET  /ping                 liveness probe
  GET  /get?file=dice|fusion parsed config (secrets are always redacted)
  POST /set?file=dice|fusion comment-safe config writer (secrets ignored)
  POST /run                  roll.py or fusion_bot.py, sync or async
  GET  /run/status?id=...    async job progress / final result
  POST /calc                 survivor/basebet solver
  GET  /presets              preset definitions from bin/presets.py
  GET  /csv?file=latest|sim|real
  GET  /manifest.json        PWA manifest
  GET  /service-worker.js    PWA service worker
  GET  /icons/<file>.png     PWA icons

Safety
  - Never passes --live to any engine; simulation only.
  - Secrets (API keys / tokens) are never returned by /get and are never
    written back by /set. Only non-secret keys are editable from the UI.
  - Simulation runs use temporary config files, so tracked configs are not
    modified by the Lab tab.
"""

from __future__ import annotations  # PEP 604 (str | None) on the 3.9 floor

import csv
import json
import math
import mimetypes
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Windows consoles default to a legacy code page (cp1252) and raise
# UnicodeEncodeError on any non-ASCII character. Force UTF-8 with replacement.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

VERSION = "2.0.0"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
WEB_DIR = os.path.join(REPO_ROOT, "web")
UI_FILE = os.path.join(WEB_DIR, "dice-ui.html")
MANIFEST_FILE = os.path.join(WEB_DIR, "manifest.json")
SW_FILE = os.path.join(WEB_DIR, "service-worker.js")
ICONS_DIR = os.path.join(WEB_DIR, "icons")

DICE_PY = os.path.join(REPO_ROOT, "bin", "roll.py")
FUSION_PY = os.path.join(REPO_ROOT, "bin", "fusion_bot.py")

LOG_DIR = os.path.join(REPO_ROOT, "logs")
CSV_LATEST = os.path.join(LOG_DIR, "dice_session_latest.csv")
CSV_SIM = os.path.join(LOG_DIR, "dice_session_sim.csv")
CSV_REAL = os.path.join(LOG_DIR, "dice_session_real.csv")

# DICE_CONFIG / FUSION_CONFIG are existing SSOT overrides used by the
# engines; honour them here too so QA can point the server at temp copies.
ENV_DICE = os.path.abspath(
    os.environ.get("DICE_CONFIG") or os.path.join(REPO_ROOT, "config", "dice.env")
)
ENV_FUSION = os.path.abspath(
    os.environ.get("FUSION_CONFIG") or os.path.join(REPO_ROOT, "config", "fusion.env")
)

PORT = int(os.environ.get("DICE_PORT", "7373"))

CDN = False  # no external CDN anywhere; charts are hand-drawn on <canvas>

MAX_ROUNDS = 200000
RUN_TIMEOUT = 120
EQUITY_POINTS = 600
PREVIEW_POINTS = 240
RECENT_ROWS = 120
MAX_JOBS = 15
JOB_TTL = 900.0

# Key names we must never expose or write from the browser.
SECRET_RE = re.compile(
    r"(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_?KEY|CREDENTIAL)",
    re.IGNORECASE,
)
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_secret_key(key: str) -> bool:
    return bool(SECRET_RE.search(str(key or "")))


def load_presets() -> dict:
    """3-พระโซน presets — อ่านจาก bin/presets.py เท่านั้น (นิยามเดียว, SSOT)."""
    global _PRESETS_CACHE
    if _PRESETS_CACHE is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "dice_presets", os.path.join(REPO_ROOT, "bin", "presets.py")
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _PRESETS_CACHE = {
            tag: {"name": p["name"], "blurb": p["blurb"], "keys": p["keys"]}
            for tag, p in m.PRESETS.items()
        }
    return _PRESETS_CACHE


_PRESETS_CACHE = None


# ──────────────────────────────────────────────────────────────
# [1] CONFIG PARSING / COMMENT-SAFE WRITING
# ──────────────────────────────────────────────────────────────
def config_path(name: str) -> str:
    """Map a UI-friendly config name to its SSOT path."""
    name = (name or "dice").strip().lower()
    if name in ("dice", "dice.env"):
        return ENV_DICE
    if name in ("fusion", "fusion.env"):
        return ENV_FUSION
    raise ValueError("file must be dice or fusion")


def config_label(name: str) -> str:
    return "fusion.env" if (name or "").lower().startswith("fusion") else "dice.env"


def parse_env(path: str) -> dict:
    """Parse KEY=VALUE lines, ignoring full-line and inline comments.

    Inline comments must be stripped or a line like
    "START_BALANCE=10000   # note" yields the value "10000   # note",
    which then fails float() downstream. roll.py already strips these;
    keep both parsers consistent.
    """
    result = {}
    if not os.path.exists(path):
        return result
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.split("#", 1)[0].strip().strip("\"'")
            result[key.strip()] = val
    return result


def public_env(path: str) -> dict:
    """parse_env without secret keys — safe to send to a browser."""
    return {k: v for k, v in parse_env(path).items() if not is_secret_key(k)}


def _clean_kv(key, value):
    """Validate one key/value pair; return None when it must be skipped."""
    key = str(key or "").strip()
    if not KEY_RE.fullmatch(key) or is_secret_key(key):
        return None
    value = "" if value is None else str(value)
    value = value.replace("\r", " ").replace("\n", " ").strip()
    return key, value


def write_env(path: str, data: dict) -> int:
    """Write non-secret keys back, preserving comments and line order.

    Returns the number of keys actually written. Secret keys are silently
    ignored so a browser can never overwrite an API token.
    """
    clean = {}
    for k, v in (data or {}).items():
        pair = _clean_kv(k, v)
        if pair:
            clean[pair[0]] = pair[1]
    if not clean:
        return 0

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            for k, v in clean.items():
                f.write(f"{k}={v}\n")
        return len(clean)

    lines_out = []
    updated_keys = set()

    # parse_env() strips inline comments before the value reaches us, so the
    # comment text has to be recovered from the file on disk here. Without
    # this, saving from the web UI would silently delete every comment.
    trailing_comments = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.rstrip("\n")
            if raw.startswith("#") or "=" not in raw:
                continue
            k, _, rest = raw.partition("=")
            _, sep, cmt = rest.partition("#")
            if sep:
                trailing_comments[k.strip()] = cmt.strip()

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.rstrip("\n")
            if raw.startswith("#") or "=" not in raw:
                lines_out.append(raw)
                continue
            key, _, _rest = raw.partition("=")
            key = key.strip()
            if key in clean:
                new_line = f"{key}={clean[key]}"
                cmt = trailing_comments.get(key)
                if cmt:
                    new_line += f"  #{cmt}"
                lines_out.append(new_line)
                updated_keys.add(key)
            else:
                lines_out.append(raw)

    # Append any new non-secret keys not originally in the file.
    new_keys = set(clean.keys()) - updated_keys
    if new_keys:
        lines_out.append("")
        lines_out.append("# [New keys added by dice-ui]")
        for k in sorted(new_keys):
            lines_out.append(f"{k}={clean[k]}")

    # Atomic replace so a crash cannot leave a half-written SSOT file.
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".dice_env_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_out) + "\n")
        try:
            os.chmod(tmp_path, os.stat(path).st_mode & 0o777)
        except OSError:
            pass
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return len(clean)


def _write_temp_env(cfg: dict) -> str:
    """Write a throw-away env file for one simulation run."""
    fd, path = tempfile.mkstemp(prefix="dice_lab_", suffix=".env")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for k, v in cfg.items():
            pair = _clean_kv(k, v)
            if pair:
                f.write(f"{pair[0]}={pair[1]}\n")
    return path


def _merge_config(base: dict, overrides) -> dict:
    """Merge browser-supplied overrides without ever copying secrets."""
    merged = dict(base)
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            pair = _clean_kv(k, v)
            if pair:
                merged[pair[0]] = pair[1]
    return merged


# ──────────────────────────────────────────────────────────────
# [2] NUMERIC HELPERS
# ──────────────────────────────────────────────────────────────
def _num(body: dict, *names, default=None, cast=float):
    for n in names:
        if n in body and body[n] not in (None, ""):
            try:
                return cast(body[n])
            except (ValueError, TypeError):
                pass
    return default


def _env_float(cfg: dict, key: str, default: float) -> float:
    try:
        v = cfg.get(key, "")
        return float(v) if v != "" else default
    except (ValueError, TypeError):
        return default


def _env_int(cfg: dict, key: str, default: int) -> int:
    try:
        v = cfg.get(key, "")
        return int(float(v)) if v != "" else default
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────────────────────────
# [3] CSV SERIES / DRAWDOWN
# ──────────────────────────────────────────────────────────────
def read_run_series(
    path: str,
    start_balance: float,
    points: int = EQUITY_POINTS,
    recent_limit: int = RECENT_ROWS,
) -> dict:
    """Read a session CSV and return sampled equity + drawdown + recent rows.

    Both engines share the same latest CSV path but roll.py and fusion_bot.py
    write slightly different columns. Read by header name so either schema
    works, and derive `account` (balance + vault) from NetPnL so drawdown also
    includes profit skimmed into the fusion vault.
    """
    out = {
        "equity": [],
        "recent": [],
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "max_loss_streak": 0,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
    }
    if not os.path.exists(path):
        return out

    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            line_count = max(0, sum(1 for _ in f) - 1)
    except OSError:
        return out

    step = max(1, line_count // max(1, points))
    peak = None
    max_dd = 0.0
    max_dd_pct = 0.0
    recent: list[dict] = []
    i = 0
    last_point = None

    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return out
            idx = {h.strip(): i for i, h in enumerate(header)}

            def cell(row, name, default=""):
                j = idx.get(name)
                return row[j] if j is not None and j < len(row) else default

            for row in reader:
                if not row or not any(x.strip() for x in row):
                    continue
                i += 1
                result = cell(row, "Result").strip().lower()
                if result == "win":
                    out["wins"] += 1
                elif result in ("lose", "loss"):
                    out["losses"] += 1

                try:
                    streak = int(float(cell(row, "LossStreak") or 0))
                except (ValueError, TypeError):
                    streak = 0
                if streak > out["max_loss_streak"]:
                    out["max_loss_streak"] = streak

                try:
                    balance = float(cell(row, "Balance"))
                except (ValueError, TypeError):
                    continue
                try:
                    net_pnl = float(cell(row, "NetPnL"))
                except (ValueError, TypeError):
                    net_pnl = balance - start_balance

                # Account = working balance + skimmed vault. fusion_bot.py
                # writes ProfitVault explicitly; roll.py has no vault column,
                # so fall back to start + NetPnL (which already includes it).
                vault_raw = cell(row, "ProfitVault")
                vault = None
                if vault_raw != "":
                    try:
                        vault = float(vault_raw)
                    except (ValueError, TypeError):
                        vault = None
                account = balance + vault if vault is not None else start_balance + net_pnl
                if peak is None or account > peak:
                    peak = account
                dd = account - peak
                dd_pct = (dd / peak * 100.0) if peak else 0.0
                if dd < max_dd:
                    max_dd = dd
                if dd_pct < max_dd_pct:
                    max_dd_pct = dd_pct

                try:
                    point = {
                        "round": int(float(cell(row, "Round") or i)),
                        "balance": balance,
                        "netPnl": net_pnl,
                        "bet": float(cell(row, "Bet") or 0),
                        "account": account,
                        "vault": vault or 0.0,
                        "drawdown": dd,
                        "ddPct": dd_pct,
                    }
                except (ValueError, TypeError):
                    continue
                last_point = point
                if i % step == 0 or i == line_count:
                    out["equity"].append(point)

                if recent_limit:
                    recent.append(
                        {
                            "Round": cell(row, "Round"),
                            "Roll": cell(row, "Roll"),
                            "Result": cell(row, "Result"),
                            "Bet": cell(row, "Bet"),
                            "RoundPnL": cell(row, "RoundPnL"),
                            "Balance": cell(row, "Balance"),
                            "LossStreak": cell(row, "LossStreak"),
                        }
                    )
                    if len(recent) > recent_limit:
                        recent.pop(0)

            # Ensure the final row is always present even when line_count was
            # approximate (blank lines / a partially flushed last line).
            if last_point is not None and (
                not out["equity"] or out["equity"][-1]["round"] != last_point["round"]
            ):
                out["equity"].append(last_point)
    except (OSError, csv.Error):
        pass

    out["rows"] = i
    out["max_drawdown"] = abs(max_dd)
    out["max_drawdown_pct"] = abs(max_dd_pct)
    out["recent"] = recent
    return out


# ──────────────────────────────────────────────────────────────
# [4] SIMULATION RUNNER (roll.py / fusion_bot.py)
# ──────────────────────────────────────────────────────────────
class BusyError(RuntimeError):
    """Another simulation is already writing the shared latest CSV."""


RUN_LOCK = threading.Lock()


def _extract_result_json(stdout: str):
    """Handle both roll.py's bare JSON and fusion_bot.py's wrapped marker."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("__RESULT_JSON__"):
            continue
        payload = line[len("__RESULT_JSON__"):]
        if payload.endswith("__RESULT_JSON__"):
            payload = payload[: -len("__RESULT_JSON__")]
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue
    return None


def _normalise_summary(
    engine: str, mode: int, raw: dict, series: dict, seed, start_balance: float
) -> dict:
    """Give both engines the summary shape web/dice-ui.html expects."""
    summary = dict(raw or {})

    if engine == "fusion":
        wins = int(summary.get("win_count", series["wins"]) or 0)
        losses = int(summary.get("lose_count", series["losses"]) or 0)
        final_working = float(summary.get("final_balance", 0.0) or 0.0)
        vault = float(summary.get("profit_vault", 0.0) or 0.0)
        summary.update(
            {
                "engine": "fusion",
                "mode": mode,
                "engine_mode": (
                    "FUSION — WAGER FOCUS + RECOVERY"
                    if mode == 1
                    else "FUSION — PROFIT FOCUS"
                ),
                "rounds": int(summary.get("rounds", series["rows"]) or 0),
                "wins": wins,
                "losses": losses,
                "start_balance": float(summary.get("start_balance", start_balance) or start_balance),
                # Account balance = working balance + skimmed vault.
                "balance": final_working + vault,
                "working_balance": final_working,
                "profit_vault": vault,
                "net_pnl": float(summary.get("total_profit", 0.0) or 0.0),
                "wagered": float(summary.get("total_wagered", 0.0) or 0.0),
                "max_loss_streak": int(
                    summary.get("max_loss_streak", series["max_loss_streak"]) or 0
                ),
                "top_wins": [],
                "rare_hits": [],
                "rare_counts": {},
                "events": [],
            }
        )
        if summary["rounds"] == 0:
            summary["rounds"] = series["rows"]
    else:
        summary.update(
            {
                "engine": "roll",
                "mode": mode,
                "engine_mode": summary.get("engine_mode") or f"MODE {mode}",
                "wins": int(summary.get("wins", series["wins"]) or 0),
                "losses": int(summary.get("losses", series["losses"]) or 0),
                "start_balance": float(
                    summary.get("start_balance", start_balance) or start_balance
                ),
                "max_loss_streak": int(
                    summary.get("max_loss_streak", series["max_loss_streak"]) or 0
                ),
                "top_wins": summary.get("top_wins") or [],
                "rare_hits": summary.get("rare_hits") or [],
                "rare_counts": summary.get("rare_counts") or {},
                "events": summary.get("events") or [],
            }
        )

    total = summary.get("wins", 0) + summary.get("losses", 0)
    summary["win_rate"] = (
        summary["wins"] / total * 100.0 if total else float(summary.get("win_rate", 0.0) or 0.0)
    )
    summary["seed"] = summary.get("seed", seed)
    summary["max_drawdown"] = series["max_drawdown"]
    summary["max_drawdown_pct"] = series["max_drawdown_pct"]
    return summary


def run_simulation_job(body: dict, job: dict | None = None) -> dict:
    """Run one simulation process and return summary + equity series.

    The caller must hold RUN_LOCK. Both engines write logs/dice_session_latest.csv;
    serialising runs keeps that file (and the /csv download) consistent.
    """
    engine = str(body.get("engine") or "roll").strip().lower()
    if engine not in ("roll", "fusion"):
        raise ValueError("engine must be 'roll' or 'fusion'")

    if engine == "roll":
        base_cfg = parse_env(ENV_DICE)
        cfg = _merge_config(base_cfg, body.get("config"))
        mode = _num(
            body,
            "mode",
            default=_env_int(cfg, "GAME_MODE", 3),
            cast=int,
        )
        if mode not in (1, 2, 3, 4, 5):
            raise ValueError("mode must be 1-5")

        rounds = _num(
            body,
            "rounds",
            "maxRounds",
            default=_env_int(cfg, "GLOBAL_MAX_ROUNDS", 1000),
            cast=int,
        )
        rounds = max(1, min(int(rounds), MAX_ROUNDS))

        start_balance = _num(
            body,
            "startBalance",
            "startbalance",
            default=_env_float(cfg, "START_BALANCE", 10000.0),
        )

        cmd = [
            sys.executable,
            DICE_PY,
            "-m",
            str(mode),
            "-r",
            str(rounds),
            "-sb",
            str(start_balance),
            "-d",
            "0",
            "-q",
        ]
        opt = [
            ("baseBet", "basebet", ["-b"], float),
            ("chance", "chance", ["-c"], float),
            ("strategy", "strategy", ["-s"], str),
            ("maxLoss", "maxloss", ["-ml"], int),
            ("stopWin", "stopwin", ["-sw"], float),
            ("stopWagered", "stopwagered", ["-sl"], float),
            ("onWin", "onwin", ["-ow"], int),
            ("wagerChance", "wagerchance", ["-wc"], float),
            ("seed", "seed", ["--seed"], int),
        ]
        for _label, _internal, flags, cast in opt:
            v = _num(body, _label, _internal, default=None, cast=cast)
            if v is not None and (cast is not str or v in ("low", "high")):
                cmd += [flags[0], str(v)]
        if body.get("rare") in (True, 1, "1", "true"):
            cmd += ["--rare"]

    else:
        base_cfg = parse_env(ENV_FUSION)
        cfg = _merge_config(base_cfg, body.get("config"))
        mode = _num(
            body,
            "mode",
            "fusionMode",
            default=_env_int(cfg, "FUSION_MAIN_MODE", 1),
            cast=int,
        )
        if mode not in (1, 2):
            raise ValueError("fusion mode must be 1-2")

        rounds = _num(
            body,
            "rounds",
            "maxRounds",
            default=_env_int(cfg, "GLOBAL_MAX_ROUNDS", 1000),
            cast=int,
        )
        rounds = max(1, min(int(rounds), MAX_ROUNDS))

        start_balance = _num(
            body,
            "balance",
            "startBalance",
            default=_env_float(cfg, "START_BALANCE", 10000.0),
        )
        seed = _num(body, "seed", default=None, cast=int)
        vault = _num(body, "vault", default=None, cast=int)

        cmd = [
            sys.executable,
            FUSION_PY,
            "-m",
            str(mode),
            "-r",
            str(rounds),
            "-b",
            str(start_balance),
            "-d",
            "0",
            "-q",
        ]
        if seed is not None:
            cmd += ["--seed", str(seed)]
        if vault in (0, 1):
            cmd += ["--vault", str(vault)]

    # Fresh CSV per run: /run/status uses it for live progress, and a stale
    # previous session must never be mistaken for the current one.
    try:
        if os.path.exists(CSV_LATEST):
            os.remove(CSV_LATEST)
    except OSError:
        pass

    if job is not None:
        job["state"] = "running"
        job["started"] = time.time()
        job["start_balance"] = float(start_balance)
        job["target_rounds"] = int(rounds)
        job["engine"] = engine
        job["mode"] = mode

    tmp_path = None
    run_env = dict(os.environ)
    run_env["PYTHONIOENCODING"] = "utf-8"
    run_env["PYTHONUNBUFFERED"] = "1"
    try:
        # Always point the engine at the config the server manages. When the
        # browser sends overrides, merge them into a temp file instead.
        if body.get("config"):
            merged = _merge_config(base_cfg, body.get("config"))
            tmp_path = _write_temp_env(merged)
            if engine == "fusion":
                run_env["FUSION_CONFIG"] = tmp_path
                run_env.pop("DICE_CONFIG", None)
            else:
                run_env["DICE_CONFIG"] = tmp_path
        else:
            if engine == "fusion":
                run_env["FUSION_CONFIG"] = ENV_FUSION
                run_env.pop("DICE_CONFIG", None)
            else:
                run_env["DICE_CONFIG"] = ENV_DICE

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            cwd=REPO_ROOT,
            env=run_env,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-1500:]
        raise RuntimeError(f"{engine} engine exited {proc.returncode}: {err}")

    raw = _extract_result_json(proc.stdout)
    if raw is None:
        raise RuntimeError("engine did not emit __RESULT_JSON__ (unexpected output)")

    series = read_run_series(CSV_LATEST, float(start_balance))
    summary = _normalise_summary(
        engine,
        int(mode),
        raw,
        series,
        _num(body, "seed", default=None, cast=int),
        float(start_balance),
    )
    return {"summary": summary, "equity": series["equity"], "recent": series["recent"]}


# ──────────────────────────────────────────────────────────────
# [5] ASYNC JOB REGISTRY
# ──────────────────────────────────────────────────────────────
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _prune_jobs() -> None:
    now = time.time()
    with JOBS_LOCK:
        for jid, job in list(JOBS.items()):
            if job.get("state") in ("done", "error"):
                if now - job.get("finished", now) > JOB_TTL:
                    JOBS.pop(jid, None)
        if len(JOBS) > MAX_JOBS:
            ordered = sorted(JOBS.items(), key=lambda kv: kv[1].get("created", 0))
            for jid, _ in ordered[: len(JOBS) - MAX_JOBS]:
                JOBS.pop(jid, None)


def start_job(body: dict) -> str:
    if not RUN_LOCK.acquire(blocking=False):
        raise BusyError("มี simulation รันอยู่แล้ว — รอให้เสร็จก่อนแล้วลองใหม่")

    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "state": "queued",
        "created": time.time(),
        "started": None,
        "finished": None,
        "engine": str(body.get("engine") or "roll").lower(),
        "mode": _num(body, "mode", "fusionMode", default=0, cast=int),
        "target_rounds": _num(body, "rounds", default=0, cast=int) or 0,
        "start_balance": 0.0,
        "result": None,
        "error": None,
    }
    _prune_jobs()
    with JOBS_LOCK:
        JOBS[job_id] = job

    def worker():
        try:
            job["result"] = run_simulation_job(body, job)
            job["state"] = "done"
        except Exception as exc:  # keep the server alive for the next run
            job["state"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            job["finished"] = time.time()
            try:
                RUN_LOCK.release()
            except RuntimeError:
                pass

    threading.Thread(target=worker, name=f"dice-job-{job_id}", daemon=True).start()
    return job_id


def job_preview(job: dict) -> dict:
    """Live progress + sampled equity while the subprocess is still running."""
    started = job.get("started") or job.get("created") or 0
    try:
        stale = os.path.getmtime(CSV_LATEST) < started - 0.5
    except OSError:
        stale = True
    if stale:
        series = {
            "equity": [],
            "rows": 0,
            "wins": 0,
            "losses": 0,
            "max_loss_streak": 0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
        }
    else:
        series = read_run_series(
            CSV_LATEST,
            float(job.get("start_balance") or 0.0),
            points=PREVIEW_POINTS,
            recent_limit=0,
        )
    last = series["equity"][-1] if series["equity"] else {}
    total = max(1, int(job.get("target_rounds") or 0))
    summary = {
        "engine": job.get("engine"),
        "mode": job.get("mode"),
        "engine_mode": (
            "FUSION — LIVE"
            if job.get("engine") == "fusion"
            else f"MODE {job.get('mode')} — LIVE"
        ),
        "rounds": series["rows"],
        "wins": series["wins"],
        "losses": series["losses"],
        "start_balance": job.get("start_balance") or 0.0,
        "balance": last.get("balance", job.get("start_balance") or 0.0),
        "net_pnl": last.get("netPnl", 0.0),
        "max_loss_streak": series["max_loss_streak"],
        "max_drawdown": series["max_drawdown"],
        "max_drawdown_pct": series["max_drawdown_pct"],
        "wagered": 0.0,
        "win_rate": (
            series["wins"] / (series["wins"] + series["losses"]) * 100.0
            if (series["wins"] + series["losses"])
            else 0.0
        ),
        "seed": None,
        "top_wins": [],
        "events": [],
        "rare_hits": [],
    }
    return {
        "summary": summary,
        "equity": series["equity"],
        "recent": [],
        "progress": {"rounds": series["rows"], "total": total},
    }


def jobs_status(job_id: str):
    with JOBS_LOCK:
        job = dict(JOBS.get(job_id) or {})
    if not job:
        return None
    now = time.time()
    elapsed = round(now - (job.get("started") or job.get("created") or now), 2)
    state = job.get("state")
    if state == "done":
        return {
            "ok": True,
            "jobId": job_id,
            "state": "done",
            "elapsed": elapsed,
            "result": job.get("result"),
        }
    if state == "error":
        return {
            "ok": True,
            "jobId": job_id,
            "state": "error",
            "elapsed": elapsed,
            "error": job.get("error") or "run failed",
        }
    preview = job_preview(job)
    return {
        "ok": True,
        "jobId": job_id,
        "state": "running",
        "elapsed": elapsed,
        "preview": {
            "summary": preview["summary"],
            "equity": preview["equity"],
            "recent": [],
        },
        "progress": preview["progress"],
    }


# ──────────────────────────────────────────────────────────────
# [6] CALCULATOR (same math as `roll.py calc`)
# ──────────────────────────────────────────────────────────────
def solve_calc(body: dict, save: bool = False) -> dict:
    env_cfg = parse_env(ENV_DICE)

    balance = _num(body, "balance", default=_env_float(env_cfg, "START_BALANCE", 10.0))
    mul = _num(
        body,
        "mul",
        "multiplier",
        default=_env_float(
            env_cfg, "BRAVE_LOSS_MUL", _env_float(env_cfg, "CUSTOM_LOSS_MUL", 1.06)
        ),
    )
    chance = _num(
        body,
        "chance",
        "winChance",
        default=_env_float(
            env_cfg, "BRAVE_WIN_CHANCE", _env_float(env_cfg, "GLOBAL_WIN_CHANCE", 3.96)
        ),
    )
    n_in = _num(body, "n", "maxLossN", default=None, cast=int)
    risk = _num(body, "risk", default=0.001)
    coverage = _num(body, "coverage", default=1.0)

    if not (balance and balance > 0):
        raise ValueError("balance must be > 0")
    if not (mul and mul >= 1.0):
        raise ValueError("mul must be >= 1.0")
    if not (0 < chance < 100):
        raise ValueError("chance must be in (0, 100)")
    if not (0 < risk < 1):
        raise ValueError("risk must be in (0, 1)")
    if not (0 < coverage <= 1):
        raise ValueError("coverage must be in (0, 1]")

    loss_p = 1.0 - chance / 100.0
    if n_in is not None:
        if n_in < 1:
            raise ValueError("n must be >= 1")
        n_cover, n_auto = int(n_in), None
    else:
        if loss_p >= 1.0:
            n_auto = 999
        elif loss_p <= 0.0:
            n_auto = 1
        else:
            n_auto = math.ceil(math.log(risk) / math.log(loss_p))
        n_cover = n_auto

    def basebet_for(n: int, bal: float, m: float) -> float:
        if m == 1.0:
            return (bal * coverage) / n
        try:
            log_mn = n * math.log(m)
            if log_mn > 700:
                return math.exp(math.log(bal * coverage * (m - 1.0)) - log_mn)
            denom = math.exp(log_mn) - 1.0
            return (bal * coverage * (m - 1.0)) / denom if denom > 0 else 0.0
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

    MIN_PRACTICAL_BET = 1e-8
    if mul == 1.0:
        max_coverable_n = int(balance * coverage / MIN_PRACTICAL_BET)
    else:
        try:
            max_coverable_n = int(
                math.log(balance * coverage * (mul - 1.0) / MIN_PRACTICAL_BET + 1.0)
                / math.log(mul)
            )
        except (ValueError, ZeroDivisionError):
            max_coverable_n = 0

    base = basebet_for(n_cover, balance, mul)
    feasible = base >= MIN_PRACTICAL_BET
    rec_base = None
    if not feasible:
        n_cover = max_coverable_n
        rec_base = basebet_for(max_coverable_n, balance, mul)
        base = rec_base
    exposure = total_exposure(n_cover, base, mul)

    progression = []
    acc, b = 0.0, base
    for i in range(1, min(n_cover, 20) + 1):
        acc += b
        progression.append({"level": i, "bet": b, "cumulative": acc})
        b *= mul

    out = {
        "balance": balance,
        "mul": mul,
        "chance": chance,
        "n": n_cover,
        "n_auto": n_auto,
        "risk": risk,
        "coverage": coverage,
        "streak_prob": loss_p ** n_cover if loss_p < 1.0 else 1.0,
        "base": base,
        "exposure": exposure,
        "exposure_pct": (exposure / balance * 100.0) if exposure != float("inf") else None,
        "feasible": feasible,
        "max_coverable_n": max_coverable_n,
        "rec_base": rec_base,
        "progression": progression,
        "truncated": n_cover > 20,
    }
    if save:
        current = parse_env(ENV_DICE)
        current.update(
            {
                "GLOBAL_BASE_BET": f"{base:.8f}",
                "CUSTOM_BASE_BET": f"{base:.8f}",
                "BRAVE_LOSSES_ALLOWED": str(n_cover),
                "BRAVE_LOSS_MUL": f"{mul:.4f}",
                "BRAVE_WIN_CHANCE": f"{chance:.2f}",
            }
        )
        write_env(ENV_DICE, current)
        out["saved"] = True
    return out


# ──────────────────────────────────────────────────────────────
# [7] HTTP HANDLER
# ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {self.address_string()} {format % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _serve_file(
        self,
        filepath: str,
        download_name: str | None = None,
        mime: str | None = None,
        cache: str = "no-cache",
    ):
        """Serve a static file from the repository web directory."""
        if not os.path.isfile(filepath):
            self._json(404, {"error": "file not found: " + os.path.basename(filepath)})
            return
        guessed, _ = mimetypes.guess_type(filepath)
        mime = mime or guessed or "application/octet-stream"
        with open(filepath, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        if download_name:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download_name}"'
            )
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/dice-ui.html", "/index.html"):
            self._serve_file(UI_FILE, cache="no-cache")
        elif path == "/ping":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "dice-lab",
                    "version": VERSION,
                    "engines": ["roll", "fusion"],
                    "bind": "0.0.0.0",
                    "port": PORT,
                },
            )
        elif path == "/get":
            try:
                name = (query.get("file", ["dice"])[0] or "dice").lower()
                self._json(200, public_env(config_path(name)))
            except ValueError as e:
                self._json(400, {"ok": False, "error": str(e)})
        elif path == "/presets":
            self._json(200, load_presets())
        elif path == "/csv":
            wanted = (query.get("file", ["latest"])[0] or "latest").lower()
            files = {
                "latest": (CSV_LATEST, "dice_session_latest.csv"),
                "sim": (CSV_SIM, "dice_session_sim.csv"),
                "real": (CSV_REAL, "dice_session_real.csv"),
            }
            if wanted not in files:
                self._json(400, {"error": "file must be latest, sim or real"})
            else:
                csv_path, name = files[wanted]
                self._serve_file(csv_path, name, mime="text/csv; charset=utf-8")
        elif path == "/manifest.json":
            self._serve_file(
                MANIFEST_FILE, mime="application/manifest+json; charset=utf-8"
            )
        elif path == "/service-worker.js":
            self._serve_file(
                SW_FILE, mime="application/javascript; charset=utf-8", cache="no-cache"
            )
        elif path.startswith("/icons/"):
            name = path[len("/icons/"):]
            if name != os.path.basename(name) or not re.fullmatch(
                r"[A-Za-z0-9._-]+", name
            ):
                self._json(404, {"error": "not found"})
            else:
                self._serve_file(
                    os.path.join(ICONS_DIR, name), cache="public, max-age=86400"
                )
        elif path == "/run/status":
            job_id = (query.get("id", [""])[0] or "").strip()
            status = jobs_status(job_id) if job_id else None
            if status is None:
                self._json(404, {"ok": False, "error": "unknown job id"})
            else:
                self._json(200, status)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/set":
            data = self._body()
            try:
                target = config_path((query.get("file", ["dice"])[0] or "dice").lower())
                saved = write_env(target, data)
                print(f"  Saved {saved} keys -> {target}")
                self._json(
                    200,
                    {
                        "ok": True,
                        "file": config_label(
                            (query.get("file", ["dice"])[0] or "dice").lower()
                        ),
                        "saved": saved,
                    },
                )
            except ValueError as e:
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
        elif path == "/run":
            body = self._body()
            try:
                if body.get("async") in (True, 1, "1", "true"):
                    job_id = start_job(body)
                    self._json(
                        200, {"ok": True, "async": True, "jobId": job_id, "state": "running"}
                    )
                else:
                    if not RUN_LOCK.acquire(blocking=False):
                        raise BusyError(
                            "มี simulation รันอยู่แล้ว — รอให้เสร็จก่อนแล้วลองใหม่"
                        )
                    try:
                        out = run_simulation_job(body)
                    finally:
                        RUN_LOCK.release()
                    self._json(200, {"ok": True, **out})
            except BusyError as e:
                self._json(409, {"ok": False, "error": str(e)})
            except (ValueError, RuntimeError) as e:
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:  # subprocess timeout etc.
                self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif path == "/calc":
            body = self._body()
            try:
                out = solve_calc(body, save=bool(body.get("save")))
                self._json(200, {"ok": True, **out})
            except (ValueError, RuntimeError) as e:
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:
                self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        else:
            self._json(404, {"error": "not found"})


# ──────────────────────────────────────────────────────────────
# [8] STARTUP
# ──────────────────────────────────────────────────────────────
def local_addresses() -> list[str]:
    """Find Tailscale / LAN IPs without contacting the internet."""
    found: list[str] = []

    def add(ip: str):
        ip = (ip or "").strip()
        # Keep the printed URLs simple and valid: IPv4 only.
        if not ip or ":" in ip or ip.startswith("127."):
            return
        if ip not in found:
            found.append(ip)

    # Tailscale is the primary access path for this user.
    try:
        proc = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        for line in (proc.stdout or "").splitlines():
            add(line)
    except (OSError, subprocess.SubprocessError):
        pass

    # Linux / WSL LAN addresses.
    try:
        proc = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=2
        )
        for part in (proc.stdout or "").split():
            add(part)
    except (OSError, subprocess.SubprocessError):
        pass

    # Portable fallback (Windows/macOS).
    if not found:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                add(info[4][0])
        except OSError:
            pass
    return found


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print(f"🎲 Dice Lab {VERSION} — server started on 0.0.0.0:{PORT}")
    print(f"   ENV dice   : {ENV_DICE}")
    print(f"   ENV fusion : {ENV_FUSION}")
    print(f"   Open UI    : http://localhost:{PORT}/")
    for ip in local_addresses():
        print(f"   Tailscale/LAN: http://{ip}:{PORT}/")
    print("   Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
