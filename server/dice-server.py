#!/usr/bin/env python3
"""
dice-server.py — Local API server for the dice-simulator web lab.
Runs on http://localhost:7373 (override with DICE_PORT).

Endpoints:
  GET  /           → serves web/dice-ui.html
  GET  /ping       → {"ok": true}
  GET  /get        → {KEY: VALUE, ...} parsed from config/dice.env
  POST /set        → writes JSON body back to config/dice.env preserving comments
  POST /run        → headless simulation via bin/roll.py -q; returns summary + series
  POST /calc       → survivor/basebet solver (same math as `roll.py calc`)
  GET  /csv        → downloads logs/dice_session_latest.csv
"""

import csv
import json
import math
import mimetypes
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows consoles default to a legacy code page (cp1252) and raise
# UnicodeEncodeError on any non-ASCII character. Force UTF-8 with replacement.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.environ.get(
    "DICE_CONFIG", os.path.join(REPO_ROOT, "config", "dice.env")
)
UI_FILE = os.path.join(REPO_ROOT, "web", "dice-ui.html")
ROLL_PY = os.path.join(REPO_ROOT, "bin", "roll.py")
CSV_FILE = os.path.join(REPO_ROOT, "logs", "dice_session_latest.csv")
PORT = int(os.environ.get("DICE_PORT", "7373"))

MAX_ROUNDS = 200000
RUN_TIMEOUT = 120
EQUITY_POINTS = 600
RECENT_ROWS = 120


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
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.split("#", 1)[0].strip().strip("\"'")
            result[key.strip()] = val
    return result


def write_env(path: str, data: dict) -> None:
    """Write data back to env file, preserving comments and line order."""
    if not os.path.exists(path):
        # Create from scratch
        with open(path, "w", encoding="utf-8") as f:
            for k, v in data.items():
                f.write(f"{k}={v}\n")
        return

    lines_out = []
    updated_keys = set()

    # parse_env() strips inline comments before the value reaches us, so the
    # comment text has to be recovered from the file on disk here. Without
    # this, saving from the web UI would silently delete every comment.
    trailing_comments = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if raw.startswith("#") or "=" not in raw:
                continue
            k, _, rest = raw.partition("=")
            _, sep, cmt = rest.partition("#")
            if sep:
                trailing_comments[k.strip()] = cmt.strip()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if raw.startswith("#") or "=" not in raw:
                lines_out.append(raw)
                continue
            key, _, _rest = raw.partition("=")
            key = key.strip()
            if key in data:
                new_line = f"{key}={data[key]}"
                cmt = trailing_comments.get(key)
                if cmt:
                    new_line += f"  #{cmt}"
                lines_out.append(new_line)
                updated_keys.add(key)
            else:
                lines_out.append(raw)

    # Append any new keys not originally in the file
    new_keys = set(data.keys()) - updated_keys
    if new_keys:
        lines_out.append("")
        lines_out.append("# [New keys added by dice-ui]")
        for k in sorted(new_keys):
            lines_out.append(f"{k}={data[k]}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")


def _num(body: dict, *names, default=None, cast=float):
    for n in names:
        if n in body and body[n] not in (None, ""):
            try:
                return cast(body[n])
            except (ValueError, TypeError):
                pass
    return default


def run_simulation_job(body: dict) -> dict:
    """Run bin/roll.py headless and return summary + sampled series."""
    env_cfg = parse_env(ENV_FILE)

    def env_float(key: str, default: float) -> float:
        try:
            v = env_cfg.get(key, "")
            return float(v) if v != "" else default
        except (ValueError, TypeError):
            return default

    mode = _num(body, "mode", default=int(env_cfg.get("GAME_MODE") or 3), cast=int)
    if mode not in (1, 2, 3, 4, 5):
        raise ValueError("mode must be 1-5")
    rounds = _num(body, "rounds", "maxRounds",
                  default=int(env_float("GLOBAL_MAX_ROUNDS", 1000)), cast=int)
    rounds = max(1, min(int(rounds), MAX_ROUNDS))

    cmd = [sys.executable, ROLL_PY, "-m", str(mode), "-r", str(rounds), "-d", "0", "-q"]
    opt = [
        ("startBalance", "startbalance", ["-sb"], float),
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

    # Full custom-parameter runs: merge the lab's config over dice.env
    # into a temp file so the tracked config is never touched by a run.
    tmp_path = None
    run_env = dict(os.environ)
    try:
        cfg_override = body.get("config")
        if isinstance(cfg_override, dict) and cfg_override:
            merged = dict(env_cfg)
            for k, v in cfg_override.items():
                if isinstance(k, str) and k.strip():
                    merged[k.strip()] = "" if v is None else str(v)
            fd, tmp_path = tempfile.mkstemp(prefix="dice_lab_", suffix=".env")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for k, v in merged.items():
                    f.write(f"{k}={v}\n")
            run_env["DICE_CONFIG"] = tmp_path

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT,
            cwd=REPO_ROOT, env=run_env,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-1500:]
        raise RuntimeError(f"roll.py exited {proc.returncode}: {err}")

    summary = None
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT_JSON__"):
            try:
                summary = json.loads(line[len("__RESULT_JSON__"):])
            except json.JSONDecodeError:
                pass
    if summary is None:
        raise RuntimeError("roll.py did not emit __RESULT_JSON__ (unexpected output)")

    equity: list[dict] = []
    recent: list[dict] = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        n = len(rows)
        if n:
            step = max(1, n // EQUITY_POINTS)
            for i in range(0, n, step):
                r = rows[i]
                try:
                    equity.append({
                        "round": int(r["Round"]),
                        "balance": float(r["Balance"]),
                        "netPnl": float(r["NetPnL"]),
                        "bet": float(r["Bet"]),
                    })
                except (KeyError, ValueError):
                    continue
            if equity and equity[-1]["round"] != n:
                r = rows[-1]
                try:
                    equity.append({
                        "round": int(r["Round"]),
                        "balance": float(r["Balance"]),
                        "netPnl": float(r["NetPnL"]),
                        "bet": float(r["Bet"]),
                    })
                except (KeyError, ValueError):
                    pass
            recent = rows[-RECENT_ROWS:]

    total = summary.get("rounds", 0) or 0
    wins = summary.get("wins", 0) or 0
    summary["win_rate"] = (wins / total * 100.0) if total else 0.0
    return {"summary": summary, "equity": equity, "recent": recent}


def solve_calc(body: dict, save: bool = False) -> dict:
    """Survivor/basebet solver — same math as `roll.py calc`."""
    env_cfg = parse_env(ENV_FILE)

    def env_float(key: str, default: float) -> float:
        try:
            v = env_cfg.get(key, "")
            return float(v) if v != "" else default
        except (ValueError, TypeError):
            return default

    balance = _num(body, "balance", default=env_float("START_BALANCE", 10.0))
    mul = _num(body, "mul", "multiplier",
               default=env_float("BRAVE_LOSS_MUL", env_float("CUSTOM_LOSS_MUL", 1.06)))
    chance = _num(body, "chance", "winChance",
                  default=env_float("BRAVE_WIN_CHANCE", env_float("GLOBAL_WIN_CHANCE", 3.96)))
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
        write_env(ENV_FILE, {
            **parse_env(ENV_FILE),
            "GLOBAL_BASE_BET": f"{base:.8f}",
            "CUSTOM_BASE_BET": f"{base:.8f}",
            "BRAVE_LOSSES_ALLOWED": str(n_cover),
            "BRAVE_LOSS_MUL": f"{mul:.4f}",
            "BRAVE_WIN_CHANCE": f"{chance:.2f}",
        })
        out["saved"] = True
    return out


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
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
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

    def _serve_file(self, filepath: str, download_name: str | None = None):
        """Serve a static file from the repository web directory."""
        if not os.path.exists(filepath):
            self._json(404, {"error": "file not found: " + filepath})
            return
        mime, _ = mimetypes.guess_type(filepath)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        if download_name:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download_name}"')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/dice-ui.html", "/index.html"):
            self._serve_file(UI_FILE)
        elif self.path == "/ping":
            self._json(200, {"ok": True})
        elif self.path == "/get":
            data = parse_env(ENV_FILE)
            self._json(200, data)
        elif self.path == "/csv":
            self._serve_file(CSV_FILE, "dice_session_latest.csv")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/set":
            data = self._body()
            try:
                write_env(ENV_FILE, data)
                print(f"  Saved {len(data)} keys -> {ENV_FILE}")
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
        elif self.path == "/run":
            try:
                out = run_simulation_job(self._body())
                self._json(200, {"ok": True, **out})
            except (ValueError, RuntimeError) as e:
                self._json(500, {"ok": False, "error": str(e)})
            except Exception as e:  # subprocess timeout etc.
                self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif self.path == "/calc":
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


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"dice-server.py running on http://localhost:{PORT}")
    print(f"   ENV file : {ENV_FILE}")
    print(f"   Open UI  : http://localhost:{PORT}/")
    print("   Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
