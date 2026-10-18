#!/usr/bin/env python3
"""set-config.py — write KEY=VALUE pairs into dice.env, comment-safe.

SSOT entry point for everything that mutates config programmatically
(web server's POST /set, d-menu, future wizards). Uses the same
conventions the whole repo relies on:

  - inline comments after the value are PRESERVED (KEY=VALUE # note)
  - unknown keys are appended at the end (no comment)
  - values are written bare (no quotes) — both engines strip quotes
    when parsing, so quotes are never needed

Usage:
  set-config.py KEY=VALUE [KEY=VALUE ...]
  set-config.py --file /path/to/env KEY=VALUE ...

Exit code 0 on success; refuses empty KEY.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def config_path(override: str | None) -> Path:
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parent.parent
    env_override = os.environ.get("DICE_CONFIG")
    return Path(env_override) if env_override else repo_root / "config" / "dice.env"


def apply(path: Path, updates: dict[str, str]) -> None:
    if not path.is_file():
        # Nothing to preserve — create from scratch
        lines = [""]
        trailing: dict[str, str] = {}
    else:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        # Recover inline comments ("KEY=VALUE # note") so a value rewrite
        # never silently deletes a comment — mirrors dice-server.write_env.
        trailing = {}
        for raw in lines:
            s = raw.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, rest = s.partition("=")
            _, cmt_sep, cmt = rest.partition("#")
            if cmt_sep:
                trailing[key.strip()] = cmt.strip()

    pending = dict(updates)
    out: list[str] = []

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            out.append(raw)
            continue
        key, _, _rest = s.partition("=")
        key = key.strip()
        if key in pending:
            new_line = f"{key}={pending.pop(key)}"
            if key in trailing:
                new_line += f"  #{trailing[key]}"
            out.append(new_line)
        else:
            out.append(raw)

    # Append new keys not present in the file
    for key, val in pending.items():
        out.append(f"{key}={val}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main() -> None:
    args = sys.argv[1:]
    path_override = None
    if len(args) >= 2 and args[0] == "--file":
        path_override = args[1]
        args = args[2:]

    updates: dict[str, str] = {}
    for arg in args:
        if "=" not in arg:
            print(f"ผิดรูปแบบ ต้องเป็น KEY=VALUE: {arg}", file=sys.stderr)
            sys.exit(1)
        key, _, val = arg.partition("=")
        key = key.strip()
        if not key:
            print(f"ผิดพลาด — ชื่อ key ว่าง: {arg!r}", file=sys.stderr)
            sys.exit(1)
        updates[key] = val.strip()

    if not updates:
        print("ตัดหาย — ไม่ได้ให้ค่า KEY=VALUE อะไรเลย", file=sys.stderr)
        sys.exit(1)

    target = config_path(path_override)
    apply(target, updates)
    for key, val in updates.items():
        print(f"✓ {key}={val}")


if __name__ == "__main__":
    main()
