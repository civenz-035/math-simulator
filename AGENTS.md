# AGENTS.md — dice-simulator

Monte-Carlo bankroll simulator (`bin/roll.py`) plus a separate "fusion" bot family
(`bin/fusion_*`). Pure Python stdlib + bash; no package manager, test suite, lint,
build, or CI. Python >= 3.9; bash >= 4 for the bash engine.

`README.md` documents only the `roll.py` simulator. It is stale for the fusion
engines and the live Stake connector — trust the code and this file.

## Live-money safety (read first)

- Real bets can be placed by `bin/fusion_native.py --live` (through
  `lib/stake_api.py` / `place_dice_bet`) and by the Gambler.Bot scripts
  (`bin/fusion_bot_gamblerbot.py`, `bin/dice_script.py`, `bin/DICE.lua`) when run
  inside Gambler.Bot. `fusion_native.py` defaults to mock; do not run `--live`,
  and avoid `--status` (it opens a network session), unless the user explicitly
  asks.
- A live Stake token is committed in `config/fusion.env` and several
  Gambler.Bot scripts (`bin/fusion_bot_gamblerbot.py`, `bin/dice_script.py`,
  `bin/DICE.lua`), plus a fallback in `bin/fusion_native.py`. Never print, copy,
  or commit it; prefer the `STAKE_API_KEY` environment variable.
- `gmm` / `gbb` are shell aliases from `lib/alias.sh`, not repo executables.
  `gmm -n --live` is the real-money path that `--status` prints.
- README's "no network / no wagering" disclaimer covers only `bin/roll.py`; it
  does not describe the fusion/live code.

## Architecture

Two independent stacks:

- `bin/roll.py` — main simulator: modes 1–5, `calc` solver, live ANSI HUD, CSV.
  Reads `config/dice.env` (`DICE_CONFIG` override). Prefer it everywhere.
- `bin/roll.sh` — bash port of modes 1–3 only. `-m 4/5` silently runs PROFIT and
  there is no `calc`; use `roll.py` for anything else. Unix only.
- `bin/fusion_bot.py` — fusion simulator (mock only), modes 1–2, reads
  `config/fusion.env` then `config/dice.env`.
- `bin/fusion_native.py` — copy of `fusion_bot.py` plus the live Stake client;
  same CLI, default mock.
- `bin/fusion_bot_gamblerbot.py` — IronPython/Gambler.Bot edition. No `__main__`
  or CLI; it exposes `Reset()` / `CalculateBet()` callbacks and runs inside
  Gambler.Bot. `..._annotated.py` is a documentation copy.
- `bin/dice_script.py` / `bin/DICE.lua` — additional Gambler.Bot ports
  (`dice_script.py` reads `dice.env`; `DICE.lua` has inline config).
- `lib/stake_api.py` — real Stake GraphQL client; `lib/maths.sh` — bash engine
  math; `lib/lua/` — historical Lua copies, not referenced by current engines.
- Fusion strategy math is duplicated in `fusion_bot.py`, `fusion_native.py`, and
  `fusion_bot_gamblerbot.py`; there is no shared module. Mirror logic changes.

## Commands

```bash
bash check-deps.sh                                  # report-only, exits non-zero if missing
python3 bin/roll.py -m 2 -r 1000
python3 bin/roll.py -m 5 -r 1000 -n 50
python3 bin/roll.py calc -b 10000 -m 1.06 -c 3.96 -n 50
python3 bin/roll.py calc -b 10000 -m 2.0 -c 49.5 --risk 0.0001
python3 bin/roll.py -m 2 -r 50 -d 0 -q --seed 42    # emits __RESULT_JSON__
bash bin/roll.sh -m 2 -r 1000                       # modes 1-3 only
python3 bin/fusion_bot.py -m 2 -r 500 -d 0 -q --seed 42
python3 bin/fusion_live_hud.py sim                  # or real / auto
python3 server/dice-server.py                       # http://localhost:7373/
bash bin/menu.sh                                    # interactive config/preset menu
python3 bin/set-config.py KEY=VALUE                 # comment-safe dice.env writer
```

- `roll.py calc` has its own parser: `-b` = balance, `-m` = multiplier,
  `-r` = risk, `-n` = tolerated losses (not basebet/mode/rounds). Don't paste
  run-mode flags into `calc`.
- Windows: `python bin\roll.py ...` or `.\dice.ps1 ...`; `.\dice.ps1 -server`
  starts the lab; `.\check-deps.ps1` reports prerequisites. `dice.ps1` does not
  wrap the fusion engines.
- Don't run `install.sh` to "set up" (it appends to `~/.bashrc` / `~/.zshrc`),
  and don't run `update.sh` (it overwrites `lib/maths.sh` via external
  `gclone` / `g` aliases). Neither is needed to use the repo.

## Config

- Two SSOT files: `config/dice.env` for `roll.py`, `dice_script.py`, the web lab,
  and `menu.sh`; `config/fusion.env` for `fusion_*`. Fusion loads `fusion.env`
  first, then `dice.env`; `FUSION_CONFIG` (or `DICE_CONFIG`) overrides.
  `config/fusion profit_setting.env` is not loaded by any engine — edit
  `config/fusion.env`. Both configs are tracked; don't retune values
  opportunistically.
- `roll.py` precedence: CLI flags > process env (`CUSTOM_*`, `BRAVE_*`,
  `GLOBAL_*`, or any already-known key) > `dice.env` > built-in defaults. An
  empty value in `dice.env` means "fall back", not zero — preserve empties.
- Inline comments (`KEY=val # note`) are stripped on parse. Keep the
  `KEY=VALUE # comment` line shape; edit through `bin/set-config.py`, `POST /set`,
  or `POST /calc` with `save`, not by reformatting.
- `bin/set-config.py` defaults to `dice.env` (or `DICE_CONFIG`); pass
  `--file config/fusion.env` for fusion. The web lab and `menu.sh` only touch
  `dice.env`, never `fusion.env`.
- `roll.py calc --save` ignores `DICE_CONFIG`, writes only `config/dice.env`,
  and uses a naive regex. The tracked `CUSTOM_BASE_BET="${GLOBAL_BASE_BET:-}""`
  line gets mangled (the number is spliced before the quote and the value then
  fails to parse). Prefer `set-config.py`, or verify/revert `dice.env` after
  using `--save`.
- `bin/roll.sh` `source`s `dice.env`, so keep it shell-parseable. `roll.py`
  handles `KEY=VALUE` plus `${VAR}` expansion; `dice-server.py` only strips
  comments and quotes.

## Web lab

- `python3 server/dice-server.py` → `http://localhost:7373/` (bind 127.0.0.1;
  `DICE_PORT` overrides). `ThreadingHTTPServer`; no CDN; charts are hand-drawn
  canvas.
- Endpoints: `GET /get`, `POST /set`, `POST /run`, `POST /calc`,
  `GET /presets`, `GET /csv`. `POST /run` shells out to `roll.py -q` and parses
  `__RESULT_JSON__`.
- `POST /run` merges an optional `config` dict into a temp env (`DICE_CONFIG`),
  so lab runs never modify tracked config. Rounds are capped at 200000; timeout
  is 120s; `--seed` makes runs reproducible.
- Preset definitions live only in `bin/presets.py`; both `menu.sh` and the web
  UI read it via `GET /presets`. Don't duplicate preset values in the UI.

## Output

- `roll.py` truncates `logs/dice_session_latest.csv` on every run, even `-q`.
- `fusion_bot.py` writes `logs/dice_session_sim.csv` plus latest;
  `fusion_native.py` writes `logs/dice_session_real.csv` plus latest.
- HUDs tail these files: `bin/dice_live_hud.py` → latest;
  `bin/fusion_live_hud.py sim|real|auto`.
- `logs/` is gitignored; never commit it.

## Gotchas

- With the tracked `dice.env`, mode 4 can stop at round 0 because
  `CUSTOM_UPPER_LIMIT_BALANCE=10` is below `START_BALANCE=32.36`. Pass `-sb`
  below the cap or adjust the cap.
- Fusion vault mode is virtual: `profit_vault` is not a separate Stake account.
  In `fusion_native.py --live`, sizing/P&L must use
  `api_balance - profit_vault`; the raw API balance still includes skimmed profit.
- `dice.ps1` intentionally has no `param()` block: PowerShell would split
  `--balance` into `-b` + `alance`. Forward `$args` verbatim; `-server` is the
  only intercepted token.
- Python floor is 3.9 (PEP 585 `dict[str, str]` annotations). Python entrypoints
  force UTF-8 on stdout/stderr for box-drawing output — don't remove.
