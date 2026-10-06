# AGENTS.md — dice-simulator

Monte-Carlo bankroll simulator. Pure Python stdlib + bash. No dependencies, no tests, no lint, no CI, no network calls in simulation paths.

## Layout

- `bin/roll.py` — main engine (all 5 modes, `calc` solver, live ANSI HUD, CSV log). Prefer this; works everywhere.
- `bin/roll.sh` + `lib/maths.sh` — bash engine, unix only. Never works on Windows.
- `config/dice.env` — single source of truth for all parameters. Tracked in git; do not retune values opportunistically.
- `server/dice-server.py` + `web/dice-ui.html` — localhost web lab (`http://localhost:7373/`): tabbed UI (setup / run+charts / survivor calc / theory), no page scroll, no external CDN. Server uses `ThreadingHTTPServer`.
- `dice.ps1` — Windows wrapper. `check-deps.sh` / `check-deps.ps1` — prerequisite reporters.
- `logs/` — gitignored runtime output (`dice_session_latest.csv`, overwritten every run).

## Commands

```bash
bash check-deps.sh                                   # report-only; never installs
python3 bin/roll.py -m 2 -r 1000                     # run mode 2, 1000 rounds
python3 bin/roll.py -m 5 -r 1000 -n 50               # survivor mode, 50-loss tolerance
python3 bin/roll.py calc -b 10000 -m 1.06 -c 3.96 -n 50          # solver, manual N
python3 bin/roll.py calc -b 10000 -m 2.0 -c 49.5 --risk 0.0001   # solver, auto N from risk
python3 server/dice-server.py                        # web lab → http://localhost:7373/
bash bin/roll.sh -m 2 -r 1000                        # bash engine (unix only)
python3 bin/roll.py -m 2 -r 50 -d 0 -q --seed 42      # headless (web-lab mode): emits __RESULT_JSON__
```

Windows: `python bin\roll.py ...` or `.\dice.ps1 -m 2 -r 1000`; `.\dice.ps1 -server` starts the editor.

## Config rules (non-obvious)

- Precedence: CLI flags > `config/dice.env` > built-in defaults. Empty value in `dice.env` (e.g. `WAGER_BASE_BET=`) means "fall back", not zero — preserve empties.
- Override file without editing tracked config: `DICE_CONFIG=/path/to.env python3 bin/roll.py ...` (both engines and server honor it). Server port: `DICE_PORT=7373`.
- `roll.py` also accepts any `CUSTOM_*` / `BRAVE_*` / `GLOBAL_*` (or already-known key) directly from process env as overrides.
- `dice.env` inline comments (`KEY=val # note`) are stripped on parse in both `roll.py` and `dice-server.py`. The server's writer recovers comments from disk — edit via `POST /set` or keep `KEY=VALUE # comment` line shape when hand-editing so comments survive.
- `roll.py calc --save` rewrites `GLOBAL_BASE_BET`, `CUSTOM_BASE_BET`, `BRAVE_LOSSES_ALLOWED`, `BRAVE_LOSS_MUL`, `BRAVE_WIN_CHANCE` in place via regex. Never reformat the file around it.
- `dice.ps1` intentionally has no `param()` block — PowerShell's binder would split `--balance` into `-b` + `alance`. Forward `$args` verbatim; `-server` is the only intercepted token.
- Python floor is 3.9 (PEP 585 `dict[str, str]` annotations). Both Python entrypoints force UTF-8 on stdout/stderr for box-drawing output; don't remove.
- Every `roll.py` run creates/truncates `logs/dice_session_latest.csv` (header + one row per round). Don't commit it.
- Web lab API (same-origin; no CDN in the UI, canvas charts are hand-drawn): `GET /get`, `POST /set`, `POST /run` (headless sim → `{summary, equity≤600pts, recent≤120rows}`; rounds capped 200000, 120s timeout), `POST /calc` (solver JSON, optional `save`), `GET /csv`.
- `POST /run` with a `config` dict merges over `dice.env` into a temp file (`DICE_CONFIG`) so lab runs never touch the tracked config. `--seed` makes runs reproducible; same seed → identical output.
