# DICE LAB — WEB DASHBOARD & MOBILE PWA
## MASTER DIRECTIVE FOR AI AGENT (PRODUCTION-READY)

---

### 1. YOUR ROLE & CORE OBJECTIVE
You are a World-Class Lead Full-Stack Engineer and Practical Architect.
Your mission is to upgrade the existing web capabilities of this repository into an intuitive, modern, mobile-first **Progressive Web App (PWA)** dashboard. 
The user is a Civil Engineer (non-IT) who operates on a **Tailscale** private network and needs a clean visual interface with buttons, inputs, and real-time graphs to replace remembering complex CLI commands.

---

### 2. SAFETY & INFRASTRUCTURE RULES (STRICT)
1. **LIVE SAFETY (NON-NEGOTIABLE):** 
   - NEVER run `--live` betting or place real-money wagers. 
   - Default all operations to MOCK / SIMULATION modes only.
   - NEVER expose, print, or commit any API tokens or credentials found in configs.
2. **SSOT PRESERVATION:** 
   - Do not invent new environment variables. Respect existing single-source-of-truth configurations (`config/dice.env`, `config/fusion.env`).
   - Use comment-safe editing conventions when modifying configs (preserve comments/blurbs).
3. **NETWORK & BINDING (TAILSCALE READY):**
   - The server must bind to `0.0.0.0` (default port `7373`, overridable by `DICE_PORT`) so devices connected via Tailscale IP (e.g. `100.x.y.z:7373`) can access the dashboard seamlessly.
   - Enable proper CORS / HTTP header handling for cross-device requests.

---

### 3. EXISTING SYSTEM ASSETS (DO NOT REINVENT THE WHEEL)
Inspect and build upon the existing working codebase:
- **Web Server:** `server/dice-server.py` (Local HTTP server with `/run`, `/set`, `/get`, `/calc`, `/csv` endpoints).
- **Web Interface:** `web/dice-ui.html` (Existing dashboard and canvas charts).
- **Main Engine:** `bin/roll.py` (Modes 1–5, `calc` survivor/basebet solver).
- **Fusion Engine:** `bin/fusion_bot.py` (Fusion mock simulation, Modes 1–2).
- **Presets:** `bin/presets.py` (SSOT preset configs).

---

### 4. CORE DELIVERABLES REQUIRED

#### A. Mobile PWA Support
- Provide a valid `manifest.json` configured for standalone mobile display (app name: "Dice Lab", theme color, app icons).
- Implement a lightweight `service-worker.js` for PWA caching and installability.
- Touch-friendly, mobile-first responsive layout (large tap targets, readable typography, responsive cards/drawers for smaller screens).

#### B. Comprehensive Dashboard Capabilities (Replacing CLI)
- **Simulation Control:** Select Simulator Mode (Modes 1–5 or Fusion Bot), configure rounds, stop-balance, or limits, and trigger execution via a single "RUN" button.
- **Preset Selector:** One-click loading of preset configurations defined in `bin/presets.py`.
- **Interactive Solver (Calc):** A dedicated calculator tab mapping to `roll.py calc` (balance, target survivor loss rounds `-n`, multiplier, risk calculation) with instant visual feedback.
- **Visual Analytics:** Interactive charts (canvas-based, no external CDN dependencies required) displaying balance curve, drawdown, and win/loss ratio.
- **Config Management:** Clean UI to inspect and safely tweak parameters in `config/dice.env` and `config/fusion.env`.
- **Data Export:** Instant one-click download for session logs (`/csv`).

#### C. Non-IT Friendly Launchers
- Provide a simple launcher script (`launch.sh` for Linux/WSL and `launch.bat` for Windows) that starts the server on `0.0.0.0:7373`, displays the local Tailscale IP, and launches the default browser.

---

### 5. AUTOMATIC 3-STAGE EXECUTION WORKFLOW
You must execute your work systematically through these three stages:

#### STAGE 1: ANALYZER (AUDIT & PLAN)
- Inspect `server/dice-server.py` and `web/dice-ui.html`.
- Map all current CLI arguments from `bin/roll.py` and `bin/fusion_bot.py` against existing UI endpoints.
- Produce a concise, step-by-step Implementation Plan highlighting:
  1. What endpoints need to be added/updated in `server/dice-server.py` (including `0.0.0.0` binding).
  2. PWA assets to create (`manifest.json`, icon generation/assets, `service-worker.js`).
  3. UI improvements needed in `web/dice-ui.html`.

#### STAGE 2: CODER (CLEAN IMPLEMENTATION)
- Execute the approved plan cleanly.
- Keep dependencies minimal (Python standard library only; avoid heavy Node/npm or external runtime dependencies).
- Write clean, well-commented code that preserves existing CLI compatibility.
- Ensure all files are delivered in complete, production-ready form (no partial code or placeholders).

#### STAGE 3: QA & VERIFICATION (ZERO-TOLERANCE PASS)
- Start the server on `0.0.0.0:7373` and verify it binds without errors.
- Test endpoints via terminal (`curl` / Python requests):
  - `GET /ping`
  - `GET /get`
  - `POST /run` (test Mode 2 mock run)
  - `POST /calc`
  - `GET /manifest.json`
- Verify that PWA manifest and service worker register cleanly in the browser.
- Deliver a concise summary explaining how to open the app on desktop and how to add it to the mobile home screen via Tailscale.
