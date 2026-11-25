#!/usr/bin/env bash
# Dice Lab launcher — Linux / WSL / macOS
# Starts the local server on 0.0.0.0:7373 (DICE_PORT overrides), prints the
# Tailscale/LAN address, then opens the default browser. Simulation only:
# this launcher never enables live betting.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${DICE_PORT:-7373}"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "❌ ไม่พบ $PYTHON — ติดตั้ง Python 3.9+ ก่อนแล้วลองใหม่"
  exit 1
fi

TS_IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
URL="http://localhost:${PORT}/"

echo "🎲 Dice Lab"
echo "   Local     : ${URL}"
if [ -n "${TS_IP}" ]; then
  echo "   Tailscale : http://${TS_IP}:${PORT}/"
else
  echo "   Tailscale : (ไม่พบ tailscale — ใช้ LAN IP ด้านล่าง)"
fi
if [ -n "${LAN_IP}" ]; then
  echo "   LAN       : http://${LAN_IP}:${PORT}/"
fi
echo

is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null
}

open_browser() {
  # WSL: prefer wslview, then Windows cmd.exe. Fall back to Linux/macOS.
  if is_wsl; then
    if command -v wslview >/dev/null 2>&1; then
      wslview "$URL" >/dev/null 2>&1 && return 0
    fi
    if command -v cmd.exe >/dev/null 2>&1; then
      cmd.exe /c start "" "$URL" >/dev/null 2>&1 && return 0
    fi
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 && return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 && return 0
  fi
  echo "ℹ  เปิดเบราว์เซอร์อัตโนมัติไม่ได้ — เปิดลิงก์ด้านบนด้วยตัวเอง"
}

ping_server() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 1 "http://127.0.0.1:${PORT}/ping" >/dev/null 2>&1
  else
    "$PYTHON" - "$PORT" <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/ping", timeout=1).read()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
  fi
}

if ping_server; then
  echo "✓ เซิร์ฟเวอร์รันอยู่แล้ว — เปิดเบราว์เซอร์"
  open_browser
  exit 0
fi

echo "▶ กำลังเริ่มเซิร์ฟเวอร์ (Ctrl+C เพื่อหยุด)…"
DICE_PORT="$PORT" "$PYTHON" server/dice-server.py &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Wait up to ~10s for the HTTP server to answer.
for _ in $(seq 1 50); do
  if ping_server; then
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "❌ เซิร์ฟเวอร์หยุดก่อนพร้อมใช้งาน — ดูข้อความ error ด้านบน"
    exit 1
  fi
  sleep 0.2
done

open_browser
wait "$SERVER_PID"
