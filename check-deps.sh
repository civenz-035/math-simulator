#!/usr/bin/env bash
# ============================================================
# check-deps.sh — report whether dice-simulator's prerequisites are met
#
#   bash check-deps.sh
#
# This script ONLY inspects and reports. It never installs anything,
# never calls a package manager, and never needs elevated privileges.
# If something is missing it tells you what to do — you run the install.
# ============================================================

set -uo pipefail

if ! declare -F cn >/dev/null 2>&1; then
    cn() {
        local code="$1" style="$2"; shift 2
        local bold="" dim=""
        [[ "$style" == "b" ]] && bold="1;"
        [[ "$style" == "d" ]] && dim="2;"
        printf "\033[%s38;5;%sm%s\033[0m" "$bold" "$code" "$*"
    }
fi
_ok()  { cn 82 b  "  [ok]   $*"; }
_warn(){ cn 214 b "  [warn] $*"; }
_err() { cn 203 b "  [need] $*"; }

printf '\n'
cn 141 b "dice-simulator — prerequisite check"
printf '\n'

MISSING=0

# ── bash ──
V="${BASH_VERSINFO[0]:-0}"
if [[ "$V" -ge 4 ]]; then
    _ok "bash $V (needs >= 4)"
else
    _err "bash $V — needs >= 4"
    MISSING=1
fi

# ── python3 ──
# The Python engine uses PEP 585 annotations (-> dict[str, str]), which
# require Python 3.9 or newer.
PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
            PY="$c"; _ok "$c $("$c" -c 'import platform;print(platform.python_version())')"; break
        else
            _err "$c found but older than 3.9 — the Python engine needs >= 3.9"
            MISSING=1
        fi
    fi
done
[[ -z "$PY" ]] && { _err "python3 not found — the Python engine needs Python >= 3.9"; MISSING=1; }

# ── standard shell tools used by the bash engine ──
for t in awk sed grep sort head wc dirname; do
    if command -v "$t" >/dev/null 2>&1; then _ok "$t"; else _err "$t not found"; MISSING=1; fi
done

# ── portability ──
if printf 'x\n' | sed 's/x/y/gI' >/dev/null 2>&1; then
    _ok "GNU toolchain detected"
else
    _ok "BSD/POSIX toolchain — lib/maths.sh is portable, this is fine"
fi

printf '\n'
if [[ "$MISSING" -eq 0 ]]; then
    cn 82 b "All prerequisites are satisfied."
else
    cn 214 b "Some prerequisites are missing."
    cat <<'EOF'

  Suggested next steps (run these yourself if needed):

    Debian/Ubuntu   sudo apt install python3
    Fedora          sudo dnf install python3
    Arch            sudo pacman -S python
    macOS (Homebrew) brew install python
    Windows         winget install Python.Python.3.12

  Python must be >= 3.9. Verify with:  python3 --version
EOF
fi
printf '\n'

echo "Usage once ready:"
echo "  bash bin/roll.sh -m 2 -r 1000        # bash engine (unix)"
echo "  python3 bin/roll.py -m 2 -r 1000     # python engine (any platform)"
printf '\n'

exit "$MISSING"