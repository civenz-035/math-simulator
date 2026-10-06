# Dice Probability Simulator

A Monte-Carlo probability laboratory for studying risk, bankroll behaviour and
expected value under adjustable outcome probabilities. Pure Python standard
library — no third-party packages, no network access, no accounts, no real
money anywhere in this project.

---

## What this actually is

A **simulator**. Every "round" draws a uniform random number from a generator
in the Python standard library (`random`) and compares it against a threshold.
Nothing is connected to anything. There is no API client, no browser automation,
no credential handling, and no code path that could place a wager or move funds.

Its purpose is to answer questions of the form:

- How long does a bankroll last under a 96% loss rate if stakes escalate 6% per
  consecutive loss?
- What fraction of strategies survive a 50-loss drawdown given a 1.06 growth
  multiplier?
- How is the expected value of a stake-sizing rule affected by the house edge?

The answer to the last one is always: negatively. That is the point of the tool.
Martingale-style escalation does not recover a negative expected value; it only
changes the *shape* of the loss distribution — from frequent small losses to
rare catastrophic ones. Simulating it makes that visible, which is exactly the
kind of thing the math is for.

## Modes

| # | Name | What it models |
|:--:|---|---|
| 1 | **Escalation** | Loss-probability > 50%. Stakes multiply after each consecutive loss. Demonstrates why escalation does not change expected value. |
| 2 | **High-Frequency** | Win-probability 98%, flat stake. Accumulates round volume while the balance drifts down. |
| 3 | **Dual-Strategy** | High-frequency mode until the balance crosses a threshold, then switches to escalation mode, then returns. |
| 4 | **Configurable** | Fully customisable multipliers, reset rules, stop rules and zig-zag patterns. |
| 5 | **Survivor** | Given a tolerance of N consecutive losses and a growth multiplier, computes the exact initial stake at which N consecutive losses consume the whole bankroll. |

Mode 5 is a closed-form calculator. `N` consecutive losses at multiplier `m`
expose `s₀·(m^N − 1)/(m − 1)`. Setting that equal to the bankroll solves for
`s₀`. It answers "how small can my stake be before this strategy fails" — a
risk-sizing question, not a prediction.

## Prerequisite check

The check script only **reports**. It never installs packages, never calls a
package manager, and never requires elevated privileges.

```bash
bash check-deps.sh          # unix
.\check-deps.ps1            # Windows PowerShell
```

Requirements:

| Platform | Needs |
|---|---|
| Linux / macOS / WSL | `bash` 4+, `python3` 3.9+, coreutils |
| Windows | PowerShell 5.1+ (built in), `python` 3.9+ |

Python 3.9 is the minimum because the engine uses PEP 585 annotations
(`-> dict[str, str]`).

If something is missing, the script prints the command to run yourself. Python
can be installed from <https://www.python.org/downloads/>.

The bash engine is **not available on Windows** — use the Python engine, which
provides the same models.

## Usage

```bash
# Bash engine (unix)
bash bin/roll.sh -m 2 -r 1000

# Python engine (any platform)
python3 bin/roll.py -m 2 -r 1000

# Survivor mode: what stake survives 50 consecutive losses at 1.06x?
python3 bin/roll.py -m 5 -r 1000 -n 50

# Reverse solver: initial stake for a given loss tolerance
python3 bin/roll.py calc --balance 10000 --mul 1.06 --chance 3.96 -n 50
```

On Windows:

```powershell
python bin\roll.py -m 2 -r 1000
.\dice.ps1 -m 2 -r 1000
.\dice.ps1 calc --balance 10000 --mul 1.06 --chance 3.96 -n 50
.\dice.ps1 -server
```

### Options

| Flag | Long | Meaning |
|---|---|---|
| `-m` | `--mode` | Model to run: `1` escalation, `2` high-frequency, `3` dual, `4` configurable, `5` survivor |
| `-b` | `--basebet` | Initial stake, overriding the config file |
| `-c` | `--chance` | Win probability as a percentage, e.g. `3.96` or `98.0` |
| `-sb` | `--startbalance` | Starting bankroll (default `10000`) |
| `-r` | `--rounds` | Maximum simulated rounds |
| `-ml` | `--maxloss` | Stop after N consecutive losses |
| `-sw` | `--stop-win` | Stop once cumulative PnL reaches this value |
| `-sl` | `--stop-wagered` | Stop once accumulated volume reaches this value |
| `-n` | `--max-loss-n` | Survivor mode: tolerated consecutive losses |
| `-d` | `--delay` | Seconds between rounds, for watching the live display |
| `--rare` | `--hunt-rare` | Track long-tail outcomes (990×–9900×) |

Run `python3 bin/roll.py --help` for the full list.

## Live terminal display

Each model renders an in-place status block using ANSI cursor control, so the
numbers update in place instead of scrolling:

```text
┌────────────────────────── SURVIVOR MODEL ──────────────────────────┐
│ ROUND : 10 / 100 (10.0%)             PROB   : 3.96% / 25.00x     │
│ DRAW  : 8794  [LOSS]                STREAK : 10 (limit: 50)      │
├────────────────────────────────────────────────────────────────────┤
│ CURRENT STAKE:  58.19049357                 BANKROLL: 9546.01567583│
│ ROUND PnL   : -58.19049357                 NET PnL : -453.98432417 │
│ REMAINING   : [█████████████░░░]  80.0%  40 more losses tolerated  │
└────────────────────────────────────────────────────────────────────┘
```

Milestone events are printed above the block so they remain in the scrollback.
Every round can be logged to `logs/dice_session_latest.csv` for plotting in
Excel or a notebook.

## Web lab (ตั้งค่า + รัน + ดูกราฟในเบราว์เซอร์)

```bash
python3 server/dice-server.py     # → http://localhost:7373/
```

ห้องทดลอง 4 แท็บเต็มจอ ไม่ต้องเลื่อนหน้า ไม่ต้องกลับไป terminal:

- **🎛️ ตั้งค่า** — การ์ดเลือกโหมด 1–5, slider/dropdown ครบทุก key ใน `config/dice.env`, กลุ่ม advanced พับได้
- **🧪 ห้องทดลอง** — ตั้งรอบ/seed/override แล้วกดรัน ดู KPI + กราฟ equity + ตารางรอบล่าสุด + เหตุการณ์ทันที (ตั้ง seed เพื่อทดลองซ้ำได้ผลเดิม)
- **🛡️ Survivor** — เครื่องคำนวณเบทรอด N ไม้แดง (`s₀ = B·(m−1)/(m^N − 1)`) พร้อมปุ่มบันทึกเข้า config
- **📐 ทฤษฎี** — สูตร EV, payout, วิธีทดลองแบบวิทยาศาสตร์

อ่าน/เขียน `config/dice.env` ผ่านเบราว์เซอร์คง comment และ format เดิม ผูก `127.0.0.1` เท่านั้น รันจำลองผ่าน `POST /run` โดยไม่แตะไฟล์ config ที่ติดตามใน git (ใช้ไฟล์ชั่วคราว) ดาวน์โหลดประวัติรอบได้ที่ `GET /csv`

## Configuration

All parameters live in `config/dice.env` as `KEY=VALUE` lines, grouped by model:

- **`[0] GLOBAL DEFAULTS`** — `GAME_MODE`, `START_BALANCE`, `HE` (house edge),
  `GLOBAL_BASE_BET`, `GLOBAL_WIN_CHANCE`, `GLOBAL_BET_TARGET`, `GLOBAL_MAX_ROUNDS`
- **`[MODE 1]`** — `PROFIT_BASE_BET`, `PROFIT_WIN_CHANCE`, `PROFIT_STOP_TARGET`, `PROFIT_MAX_LOSS_STREAK`
- **`[MODE 2]`** — `WAGER_BET_PCT`, `WAGER_WIN_CHANCE`, `WAGER_TARGET`
- **`[MODE 3]`** — `HYBRID_LOSS_TRIGGER`, `HYBRID_PROFIT_TRIGGER`
- **`[MODE 4]`** — `CUSTOM_LOSS_MUL`, `CUSTOM_WIN_MUL`, `CUSTOM_RESET_*`, `CUSTOM_STOP_*`, `CUSTOM_ZIGZAG_EVERY`
- **`[MODE 5]`** — `BRAVE_LOSSES_ALLOWED`, `BRAVE_LOSS_MUL`, `BRAVE_WIN_CHANCE`, `BRAVE_STOP_PROFIT`

`HE` is the house edge in percent. It is what makes expected value negative;
change it to study how stake-sizing interacts with it.

## Layout

```
dice-simulator/
├── bin/
│   ├── roll.py        # Python engine — all models, live display, solver
│   └── roll.sh        # Bash engine — unix only
├── config/
│   └── dice.env       # single source of truth for all parameters
├── lib/
│   └── maths.sh       # vendored mth() helper (bash engine)
├── logs/              # optional CSV output
├── server/
│   └── dice-server.py # localhost HTTP API + config editor
├── web/
│   └── dice-ui.html   # browser configuration UI
├── check-deps.sh      # prerequisite report (unix)
├── check-deps.ps1     # prerequisite report (Windows)
├── dice.ps1           # PowerShell convenience wrapper
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project exists for mathematical study: probability distributions, expected
value, and bankroll risk modelling.

It is **not** connected to any gambling service, contains no wagering or
financial functionality, and simulates nothing but a standard-library random
number generator. No simulation output predicts real-world outcomes.

Staking systems do not overcome a negative expected value. If gambling is a
concern for you or someone you know, support is available in most countries
through national helplines.