#!/usr/bin/env python3
"""presets.py — shared definitions for the "3-พระโซน" preset system.

One single source of truth for presets, consumed by:
  - bin/menu.sh          (terminal menu, prints & saves into dice.env)
  - web/dice-ui.html     (preset buttons, POST /set to the server)

Preset contract:
  keys     — dict of dice.env keys that this preset hard-writes
  blurb    — คำอธิบายโหมด (ภาษาคน, ไม่ใช่ bytecode)
"""

from __future__ import annotations


PRESETS: dict[str, dict] = {
    "safe": {
        "name": "🛡️ ปลอดภัย — Survivor",
        "blurb": (
            "โหมด 5 สูตรรอดตาย: เบทเล็ก × ทนแดง 60 ไม้ ตัวคูณ 1.015 "
            "เหมาะเซสชันยาว เน้นรอดก่อน"
        ),
        "keys": {
            "GAME_MODE": "5",
            "BRAVE_LOSSES_ALLOWED": "60",
            "BRAVE_LOSS_MUL": "1.015",
            "BRAVE_WIN_CHANCE": "3.96",
            "BRAVE_WIN_RESET_BASE": "1",
        },
    },
    "balanced": {
        "name": "⚖️ สมดุล — Balanced",
        "blurb": (
            "โหมด 4 แบบที่เวลากลับโค้งมาเริ่มทบในไม้บ้างไม้คร่อม: "
            "ตัวคูณ 1.015 · ชนะแล้วรีเซ็ต basebet"
        ),
        "keys": {
            "GAME_MODE": "4",
            "CUSTOM_LOSS_MUL": "1.015",
            "CUSTOM_LOSS_MUL_EVERY": "1",
            "CUSTOM_LOSS_RESET_FIRST": "0",
            "CUSTOM_WIN_MUL": "1.0",
            "CUSTOM_WIN_RESET_BASE": "1",
        },
    },
    "aggressive": {
        "name": "🔥 เข้มข้น — Aggressive",
        "blurb": (
            "โหมด 4 สายมือหนัก: ตัวคูณ 1.06 ทบแรงขึ้นทันทีหลังแพ้ไม้แรก "
            "ความเสี่ยงพังพอร์ตสูงกว่า แต่กำไรไล่เร็วเมื่อล็องวินชนะติดกัน"
        ),
        "keys": {
            "GAME_MODE": "4",
            "CUSTOM_LOSS_MUL": "1.06",
            "CUSTOM_LOSS_MUL_EVERY": "1",
            "CUSTOM_LOSS_RESET_FIRST": "0",
            "CUSTOM_WIN_MUL": "1.0",
            "CUSTOM_WIN_RESET_BASE": "1",
        },
    },
}


def main() -> None:
    for tag, p in PRESETS.items():
        print(f"{p['name']}")
        print(f"  {p['blurb']}")
        for k, v in p["keys"].items():
            print(f"  {k}={v}")
        print()


if __name__ == "__main__":
    main()
