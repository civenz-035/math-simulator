#!/usr/bin/env bash
# ─────────────────────────────────────────────
# d-menu — เมนูคุมเครื่องจำลอง DICE แบบกดเลข ไม่ต้องพิมพ์ flag เอง
# กติกา SSOT: บันทึกถาวร → config/dice.env ตัวเดียวเท่านั้น
#             ลองร่อนสาธิต → ใช้ temp file ผ่าน DICE_CONFIG ไม่แตะตัวจริง
# ─────────────────────────────────────────────
set -u

DICE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
ROLLER="$DICE_ROOT/bin/roll.py"
CONFIG="$DICE_ROOT/config/dice.env"
SETTER="$DICE_ROOT/bin/set-config.py"
TMP_ENV="$(mktemp /tmp/opencode/dmenu.XXXXXX.env 2>/dev/null || mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT

pause() { printf '\nกด Enter เพื่อกลับเมนูหลัก…'; read -r _; }

show_current() {
    echo "════════ config ปัจจุบัน ($CONFIG) ════════"
    grep -E '^(GAME_MODE|GLOBAL_BASE_BET|GLOBAL_WIN_CHANCE|CUSTOM_LOSS_MUL|CUSTOM_LOSS_MUL_EVERY|CUSTOM_LOSS_RESET_FIRST|CUSTOM_WIN_MUL|CUSTOM_WIN_RESET_BASE|BRAVE_LOSSES_ALLOWED|BRAVE_LOSS_MUL)=' "$CONFIG" 2>/dev/null \
        || echo "(ไม่พบค่าหลัก — เช็คไฟล์ config ผ่าน bash check-deps.sh)"
}

# ออกทาง stdout: <บรรทัดแรก>=name, <2>=blurb, ที่เหลือ = KEY=VALUE
preset_meta() {
    python3 - "$DICE_ROOT" "$1" <<'PY'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("presets", sys.argv[1] + "/bin/presets.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = m.PRESETS[sys.argv[2]]
print(p["name"]); print(p["blurb"])
for k, v in p["keys"].items():
    print(f"{k}={v}")
PY
}

# ผสม preset ลงบนสำเนา dice.env → รันสาธิตได้ โดยไม่แตะตัวจริง
make_env_from_preset() {
    cp "$CONFIG" "$TMP_ENV" 2>/dev/null || : > "$TMP_ENV"
    python3 "$SETTER" --file "$TMP_ENV" "$@"
}

pick_preset() {
    echo
    echo "╭──────── 🎛️ เลือกสายเล่น (3 พระโซน) ────────╮"
    echo "│  1) 🛡️ ปลอดภัย — Survivor (โหมด 5)          │"
    echo "│  2) ⚖️ สมดุล — Balanced (โหมด 4, มู 1.015)  │"
    echo "│  3) 🔥 เข้มข้น — Aggressive (โหมด 4, 1.06)   │"
    echo "│  b) ย้อนกลับ                                 │"
    echo "╰─────────────────────────────────────────────╯"
    printf 'เลือก [1-3/b]: '
    read -r choice
    local tag
    case "$choice" in
        1) tag="safe";;
        2) tag="balanced";;
        3) tag="aggressive";;
        b) return;;
        *) echo "ใส่ 1-3 หรือ b ครับ"; return;;
    esac

    local meta blurb name
    meta="$(preset_meta "$tag")" || { echo "อ่าน presets.py ไม่สำเร็จ"; return; }
    name="$(printf '%s\n' "$meta" | sed -n '1p')"
    blurb="$(printf '%s\n' "$meta" | sed -n '2p')"
    local kv_pairs=()
    while IFS= read -r line; do kv_pairs+=("$line"); done < <(printf '%s\n' "$meta" | tail -n +3)
    local mode_alive=""; mode_alive="$(printf '%s\n' "${kv_pairs[@]}" | grep '^GAME_MODE=' | head -1 || true)"
    local mode="${mode_alive#GAME_MODE=}"

    echo
    echo "$name"
    echo "  $blurb"
    echo "  เจาะจงเขียนค่า:"; printf '    %s\n' "${kv_pairs[@]}"

    echo
    echo "  ต้องการทำอะไรต่อ?"
    echo "   a) ลองรันก่อน (ไม่เปลี่ยน dice.env จริง)"
    echo "   b) บันทึกเป็นค่าเริ่มต้นลง dice.env (ถาวร, คง comment เดิม)"
    echo "   c) ยกเลิก"
    printf 'เลือก [a/b/c]: '
    read -r action
    case "$action" in
        a)
            make_env_from_preset "${kv_pairs[@]}" || return
            printf '\nจำนวนรอบ (default 1000): '
            read -r rounds_in
            local rounds="${rounds_in:-1000}"
            rounds="${rounds//[!0-9]/}"; rounds="${rounds:-1000}"
            echo "── สาธิต · $rounds รอบ · mode $mode (config ชั่วคราวเท่านั้น) ──"
            DICE_CONFIG="$TMP_ENV" python3 "$ROLLER" -m "$mode" -r "$rounds" -d 0
            echo
            echo "ถ้าค่าโอเคจะเก็บลง dice.env แบบถาวรเลยไหม? [y/N]"
            read -r confirm
            if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                python3 "$SETTER" "${kv_pairs[@]}" && echo "✅ บันทึก dice.env ถาวรแล้ว"
            fi
            ;;
        b)
            python3 "$SETTER" "${kv_pairs[@]}" && echo "✅ บันทึก dice.env ถาวรแล้ว"
            ;;
        *) echo "ยกเลิก";;
    esac
}

main_menu() {
    printf '\nจำนวนรอบ (default 1000): '
    read -r rounds_in
    local rounds="${rounds_in:-1000}"
    rounds="${rounds//[!0-9]/}"; rounds="${rounds:-1000}"
    printf 'โหมด 1-5 (ค่าว่าง = ตาม config): '
    read -r mode_in
    local mode="${mode_in//[!1-5]/}"
    if [[ -n "$mode" ]]; then
        python3 "$ROLLER" -m "$mode" -r "$rounds"
    else
        python3 "$ROLLER" -r "$rounds"
    fi
}

while :; do
    echo
    echo "╭─────────────── 🎲 d-menu · ศูนย์ควบคุม ───────────────╮"
    echo "│  1) เลือกสายเล่น (preset 3 พระโซน)                     │"
    echo "│  2) ดู config ปัจจุบัน (ค่าหลักใน dice.env)             │"
    echo "│  3) รันจำลอง (ใช้ config ปัจจุบัน)                      │"
    echo "│  4) เปิดห้องทดลองเว็บ (localhost:7373)                  │"
    echo "│  q) ออก                                                │"
    echo "╰────────────────────────────────────────────────────────╯"
    printf 'เลือก [1-4/q]: '
    read -r top
    case "$top" in
        1) pick_preset;;
        2) show_current; pause;;
        3) main_menu;;
        4)
            echo "กด Ctrl+C เพื่อหยุด server"
            python3 "$DICE_ROOT/server/dice-server.py"
            ;;
        q) exit 0;;
        *) echo "ใส่เลข 1-4 หรือ q ครับ";;
    esac
done
