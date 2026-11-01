# -*- coding: utf-8 -*-
# ==============================================================================
# 📘 FUSION BOT v4.1 — GAMBLER.BOT EDITION
#    "ฉบับอ่านโค้ด" (ANNOTATED EDITION) — คำอธิบายภาษาไทยละเอียด
# ==============================================================================
# ไฟล์ต้นฉบับ : bin/fusion_bot_gamblerbot.py
# ไฟล์นี้      : bin/fusion_bot_gamblerbot_annotated.py
#
# ⚠️  ไฟล์นี้ "ไม่มีการแก้ logic" — ตรวจแล้วว่า AST (โครงสร้างโค้ด)
#     เหมือนต้นฉบับ 100% ต่างกันแค่คอมเมนต์/คำอธิบาย
#     สิ่งที่เพิ่มคือคอมเมนต์ภาษาไทย + ตารางเทียบกับ Bash
#     ถ้าจะเอาไปรันกับ Gambler.Bot ให้ใช้ไฟล์ต้นฉบับ
#
# วิธีอ่านไฟล์นี้:
#   [BASH]   = เทียบความคิดกับ Bash ให้เห็นภาพ
#   [ระวัง]  = จุดที่มือใหม่มักเข้าใจผิด
#   [เทคนิค] = กลเม็ดที่โค้ดใช้แก้ปัญหา
#   [สูตร]   = อธิบายคณิตศาสตร์ตรงนั้น
# ==============================================================================


# ==============================================================================
# 📚 สารบัญ
# ------------------------------------------------------------------------------
#   0. ภาพรวม: บอทนี้ทำอะไร + มันถูกเรียกอย่างไร
#   1. SSOT CONFIG LOADER      — อ่านไฟล์ config/dice.env (หรือ fusion.env)
#   2. CSV LOGGER              — บันทึกผลแต่ละรอบลง CSV
#   3. FUSION BOT MATH ENGINE  — สูตรคำนวณ payout / multiplier / base bet
#   4. GLOBAL STATE            — ตัวแปรสถานะทั้งหมด (เทียบเท่า shell variables)
#   5. INTERNAL HELPERS        — ฟังก์ชันช่วย: สลับโหมด, อัปเดต base, โชว์สถานะ
#   6. GAMBLER.BOT CALLBACKS   — Reset() และ CalculateBet() ที่บอทเรียกเอง
#   7. ภาคผนวก                 — ผังการทำงาน, ตาราง config, ข้อสังเกต
# ==============================================================================


# ==============================================================================
# [0] ภาพรวมก่อนอ่านโค้ด
# ==============================================================================
#
# ── 0.1 บอทนี้ทำอะไร ──────────────────────────────────────────────────────────
#
#   เป็นกลยุทธ์เดิมพัน "dice" (ลูกเต๋าเสมือน) ของเว็บ Stake/Gambler.Bot
#   มี 2 โหมดสลับกัน:
#
#   (1) WAGER MODE — โหมดปั่นยอดเดิมพัน (turnover)
#       • ตั้ง Chance สูงมาก (98%) → ชนะบ่อย แต่ payout ต่ำ (~1.01x)
#       • เดิมพัน 2.5% ของ balance ต่อไม้
#       • เป้าหมายคือ "ปั่นยอด" ให้ครบ FUSION_WAGER_TARGET (เช่น 100)
#         เพราะโปรโมชันของคาสิโนมักกำหนดยอดเทิร์นโอเวอร์
#       • ถ้าขาดทุนสะสมจากจุดเริ่ม cycle ถึง 4% → ตัดขาดทุน
#         แล้วสลับไปโหมด PROFIT เพื่อ "กู้ทุน"
#
#   (2) PROFIT MODE — โหมดทำกำไร/กู้ทุน
#       • ตั้ง Chance ต่ำ (0.5–0.75%) → ชนะยาก แต่ payout สูง (~132–198x)
#       • คำนวณ base bet จากสูตร เพื่อให้รับแพ้ติดกันได้ N ไม้
#         โดยเงินใน cycle ไม่หมดก่อน
#       • ถ้าแพ้ → ไม้ถัดไป = ไม้ก่อนหน้า × multiplier (martingale)
#       • ถ้าชนะ → กลับไปเริ่มที่ base bet ใหม่
#       • ถ้ากำไรครอบ "ยอดที่เสียตอนตัด + 1%" → เก็บกำไรเข้า Profit Vault
#         แล้วกลับไป WAGER (เฉพาะโหมด 1)
#
#   โหมด 1 = WAGER FOCUS + RECOVERY (ปั่นยอด → ตัด → กู้ → กลับไปปั่น)
#   โหมด 2 = PROFIT FOCUS (ทำกำไรล้วน ไม่กลับไปปั่น)
#
#   ⚠️ นี่คือกลยุทธ์การพนัน ไม่ใช่การลงทุน — โค้ดนี้เพื่อการศึกษา/จำลอง
#
#
# ── 0.2 ไฟล์นี้ "ไม่ใช่โปรแกรมที่รันเอง" ───────────────────────────────────────
#
#   ปกติเวลาเขียน Python เราจะสั่ง `python file.py` แล้วโค้ดบรรทัดล่าง ๆ รัน
#   แต่ไฟล์นี้เป็น "สคริปต์เสียบ" (plugin) ของโปรแกรม Gambler.Bot
#   ตัวบอทจะเป็นคน import/exec ไฟล์นี้ แล้วเรียกฟังก์ชันที่ชื่อกำหนดตายตัว:
#
#       Reset()         → เรียกตอนเริ่ม session (หรือกด Start ใหม่)
#       CalculateBet()  → เรียก "ก่อนวางเดิมพันไม้ถัดไป"
#                          (หลังรู้ผลไม้ก่อนหน้าแล้ว)
#
#   ตัวแปรที่ตัวบอท "ฉีด" (inject) เข้ามาให้ เราไม่ได้ประกาศเอง:
#
#       Balance       = เงินในบัญชีปัจจุบัน
#       PreviousBet   = ข้อมูลไม้ที่เพิ่งจบ (TotalAmount, Profit, Roll, ...)
#       NextBet       = ไม้ที่จะวางถัดไป (Amount, Chance, High)
#       Win           = True/False ผลของไม้ก่อนหน้า
#       Print(...)    = ฟังก์ชันพิมพ์ log ของบอท (ไม่ใช่ print ของ Python)
#       Stop()        = สั่งให้บอทหยุดทำงาน
#
#   [BASH] เทียบได้กับสคริปต์ที่ถูก `source` เข้าไปในบอท:
#          บอทมีตัวแปรอย่าง $Balance, $Win อยู่แล้ว
#          เรามาเขียนฟังก์ชันทับ/ใช้งานต่อ
#          เหมือนเวลาเราใช้ $HOME โดยไม่ต้องประกาศ $HOME เอง
#
#   เพราะฉะนั้นถ้าเอาไฟล์นี้ไปรันด้วย `python` ตรง ๆ มันจะ "เฉย ๆ"
#   (แค่ประกาศฟังก์ชัน ไม่มีอะไรเกิดขึ้น) และถ้าเรียก Reset() จะพัง
#   เพราะไม่มีตัวแปร Balance / NextBet ให้ใช้
#
#
# ── 0.3 ตารางเทียบแนวคิด Python กับ Bash ─────────────────────────────────────
#
#   Python                          Bash
#   ──────────────────────────────  ─────────────────────────────────────────
#   ตัวแปร global ระดับไฟล์          ตัวแปร shell ทั่วไป
#   global x  (ในฟังก์ชัน)           ไม่ต้องประกาศ — ฟังก์ชันแก้ global ได้เลย
#   local x   (ในฟังก์ชัน)           local x  (ตรงข้าม: จำกัดให้อยู่ในฟังก์ชัน)
#   None                            ตัวแปรที่ยังไม่ถูก set / ค่าว่าง
#   dict = {}                       declare -A dict
#   list = []                       array=(...)
#   tuple (a, b)                    อ่านค่าหลายค่าพร้อมกัน (ไม่มี tuple จริง)
#   f(a, b)                         f "$a" "$b"
#   len(x)                          ${#x[@]} หรือ ${#x}
#   "สวัสดี %s" % name              printf "สวัสดี %s" "$name"
#   "{0:.8f}".format(x)             printf "%.8f" "$x"
#   x += 1                          ((x++))   (จำนวนเต็ม)
#   x % 50                          $((x % 50))
#   if x:                           if [ -n "$x" ]
#   if not x:                       if [ -z "$x" ]
#   try / except                    if ! cmd; then ...; fi
#   os.path.isfile(p)               [ -f "$p" ]
#   os.path.isdir(p)                [ -d "$p" ]
#   os.path.join(a, b)              "$a/$b"
#   open(f).readlines()             mapfile -t lines < "$f"
#   for line in lines:              for line in "${lines[@]}"; do
#   line.split("=", 1)              ${line%%=*}  และ  ${line#*=}
#   v.split("#", 1)[0]              ${v%%#*}
#   re.sub(pattern, repl, v)        sed -E 's/pattern/repl/g'
#   math.log(x)                     awk "BEGIN { print log($x) }"
#   sys.exit() / Stop()             exit 1 / kill
#
#   หมายเหตุ: Bash ไม่มี "ตัวเลขทศนิยม" ใน arithmetic ($(( )) เป็นจำนวนเต็ม)
#   เวลาคำนวณเงินใน Bash มักต้องใช้ awk หรือ bc
#   Python คำนวณทศนิยมได้ตรง ๆ แต่ก็มีข้อจำกัดเรื่องความแม่นยำ (float)
#
# ==============================================================================


# ==============================================================================
# [1] SSOT CONFIG LOADER — โหลดค่าตั้งต้นจากไฟล์เดียว (Single Source of Truth)
# ==============================================================================
# แนวคิด SSOT: ค่าพารามิเตอร์ทุกอย่างอยู่ในไฟล์ config ที่เดียว
# ไม่ hardcode กระจายในโค้ด เพราะแก้ที่เดียวแล้วทุกเครื่องมือเห็นตรงกัน
# (fusion_bot.py, fusion_live_hud.py, fusion_bot_gamblerbot.py ใช้ร่วมกัน)

import os       # จัดการ path / ไฟล์ / environment variables
import re       # regular expression สำหรับแทนที่ ${VAR}
import csv      # เขียนไฟล์ CSV
import math     # log, pow, ceil
import time     # จับเวลา (time.time() = วินาทีตั้งแต่ epoch)

# [BASH] import os   ≈ ใช้คำสั่ง built-in ของ shell เกี่ยวกับไฟล์/path
#        import math ≈ เรียก awk/bc มาช่วยคำนวณ
#
# ------------------------------------------------------------------------------
# หา "โฟลเดอร์ของไฟล์นี้" เพื่อใช้เป็นฐานในการหา config
# ------------------------------------------------------------------------------
# __file__ คือ path ของไฟล์ที่กำลังรัน
# แต่บางครั้ง Gambler.Bot อาจ exec โค้ดโดยไม่มี __file__ → ใช้ os.getcwd() แทน
#
# [BASH] ${BASH_SOURCE[0]} คือ path ของไฟล์สคริปต์
#        ถ้าไม่มี (เช่น source จาก stdin) ก็ใช้ $PWD แทน
#        ประโยคนี้เทียบได้กับ:
#          _base_dir=$(cd "$(dirname "${BASH_SOURCE[0]:-$PWD}")" && pwd)
_base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

# ให้ผู้ใช้ override path ของ config ได้ผ่าน environment variable
# ลำดับความสำคัญ: FUSION_CONFIG ก่อน แล้วค่อย DICE_CONFIG
# [BASH] _env_override="${FUSION_CONFIG:-$DICE_CONFIG}"
#        (ถ้า FUSION_CONFIG ว่าง/ไม่ตั้ง → ใช้ DICE_CONFIG)
_env_override = os.environ.get("FUSION_CONFIG") or os.environ.get("DICE_CONFIG")

# รายการ path ที่จะลองหาไฟล์ config ตามลำดับ
# ตัวแรกที่ "มีอยู่จริง" จะถูกใช้ (break)
# มีทั้งกรณีรันจาก bin/, รันจาก simulator/, รันจาก root และ path ตายตัวบน Windows
#
# [BASH] for p in "${CANDIDATES[@]}"; do
#            if [ -f "$p" ]; then found="$p"; break; fi
#        done
#
# [ระวัง] การ hardcode path แบบ c:\Users\User\... ทำให้ย้ายเครื่องแล้วอาจไม่เจอ
#        แต่มันเป็นแค่ "ตัวเลือกท้าย ๆ" ไม่ใช่ทางหลัก
ENV_FILE_CANDIDATES = [
    _env_override,  # อาจเป็น None → ถูกกรองด้วย `if p` ตอน loop
    os.path.normpath(os.path.join(_base_dir, "..", "config", "fusion.env")),
    os.path.normpath(os.path.join(_base_dir, "..", "simulator", "config", "fusion.env")),
    os.path.normpath(os.path.join(_base_dir, "config", "fusion.env")),
    r"c:\Users\User\simulator\config\fusion.env",
    os.path.normpath(os.path.join(_base_dir, "..", "config", "dice.env")),
    os.path.normpath(os.path.join(_base_dir, "..", "simulator", "config", "dice.env")),
    os.path.normpath(os.path.join(_base_dir, "config", "dice.env")),
    r"c:\Users\User\simulator\config\dice.env",
]

# regex สำหรับแทนที่ตัวแปรในค่า config เช่น ${START_BALANCE} หรือ $HE
#
# แยกส่วน:
#   \$\{(\w+)(?::-)?}   → จับ ${NAME}  หรือ ${NAME:-}  (group 1 = NAME)
#   |                    → หรือ
#   \$(\w+)              → จับ $NAME                    (group 2 = NAME)
#
# [BASH] Bash มี parameter expansion ในตัว:
#          ${START_BALANCE}          → ค่าของตัวแปร
#          ${START_BALANCE:-100}     → ถ้าว่าง/ไม่ตั้ง ใช้ 100
#
# [ระวัง] regex นี้ "รองรับรูปร่าง" ${VAR:-default} แต่ "ไม่ทำงานเหมือน Bash"
#         เพราะโค้ดข้างล่างจะแทนด้วย cfg.get(name, "") เฉย ๆ
#         คือถ้าไม่พบตัวแปร → ได้ค่าว่าง ไม่ใช่ค่า default ที่เขียนไว้
_ENV_REF_RE = re.compile(r"\$\{(\w+)(?::-)?}|\$(\w+)")


def load_dice_env():
    """
    อ่านไฟล์ config แล้วคืนค่าเป็น (dict ของ key→value, path ที่เจอ)

    รูปแบบไฟล์ที่รองรับ (เหมือน .env ทั่วไป):
        KEY=VALUE
        KEY=VALUE   # comment
        # บรรทัดคอมเมนต์
        KEY="ข้อความในเครื่องหมายคำพูด"

    [BASH] ฟังก์ชันนี้เทียบได้กับ:
        declare -A cfg
        while IFS='=' read -r k v; do
            [[ -z "$k" || "$k" == \#* ]] && continue
            v=${v%%#*}; v=${v%\"}; v=${v#\"}
            cfg["$k"]="$v"
        done < "$found_path"
    """
    cfg = {}          # dict ว่าง — เทียบเท่า declare -A cfg ใน Bash
    found_path = None  # ยังไม่เจอไฟล์

    # ── หาไฟล์ config แรกที่มีอยู่จริง ─────────────────────────────────────
    for p in ENV_FILE_CANDIDATES:
        # `if p` กรอง None และสตริงว่างออก
        # [BASH] [[ -n "$p" ]] && [[ -f "$p" ]]
        if p and os.path.isfile(p):
            found_path = p
            break  # เจอแล้วหยุดหา (เหมือน break ใน Bash)

    if found_path:
        lines = []
        # ── อ่านไฟล์ทั้งไฟล์เป็น list ของบรรทัด ───────────────────────────
        # encoding="utf-8", errors="replace" = อ่านแบบ UTF-8
        # ถ้าเจอ byte เสียให้แทนด้วยอักขระแทน (ไม่ crash)
        #
        # [BASH] mapfile -t lines < "$found_path"
        #
        # [เทคนิค] IronPython 2.7 (Python เก่า) ไม่รองรับ argument encoding=
        #          จึงต้องมี try/except แล้วเปิดไฟล์แบบธรรมดาแทน
        #          นี่คือเหตุผลที่เห็น try ซ้อน try
        try:
            with open(found_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (TypeError, ValueError, Exception):
            # TypeError = Python 2 ไม่รู้จัก encoding=
            # ที่เขียน Exception ไว้ด้วยคือ "กันพลาดทุกกรณี" (กว้างมาก)
            try:
                with open(found_path, "r") as f:
                    lines = f.readlines()
            except Exception:
                # อ่านไม่ได้ก็ปล่อยผ่าน — ใช้ค่า default ทั้งหมด
                # [BASH] 2>/dev/null || true
                pass

        # ── แปลงแต่ละบรรทัดเป็น key/value ───────────────────────────────
        for line in lines:
            line = line.strip()  # ตัดช่องว่างหัวท้าย + \n
            # ข้ามบรรทัดว่าง, บรรทัดคอมเมนต์ (#), และบรรทัดที่ไม่มี =
            if line and not line.startswith("#") and "=" in line:
                # split("=", 1) = แยกแค่ "=" ตัวแรก
                # เช่น "KEY=a=b" → k="KEY", v="a=b"
                #
                # [BASH] k=${line%%=*}; v=${line#*=}
                k, v = line.split("=", 1)

                # v.split("#", 1)[0] = ตัดคอมเมนต์ท้ายบรรทัด
                # .strip() = ตัดช่องว่าง
                # .strip("\"'") = ตัดเครื่องหมายคำพูดหัวท้าย (ทั้ง ' และ ")
                #
                # [BASH] v=${v%%#*}; v=$(echo "$v" | sed -e 's/^["'\'']//' -e 's/["'\'']$//')
                #
                # [ระวัง] ถ้าค่าจริงมี # อยู่ข้างใน (เช่นรหัสผ่าน) จะถูกตัดทิ้ง
                v = v.split("#", 1)[0].strip().strip("\"'")
                cfg[k.strip()] = v

    # ── ขยายตัวแปรอ้างอิง เช่น A=${B} ────────────────────────────────────
    # วนซ้ำสูงสุด 5 รอบ เพราะค่าอาจอ้างต่อกันเป็นลูกโซ่:
    #   A=${B}, B=${C}, C=10
    # รอบ 1: A=${C}, B=10
    # รอบ 2: A=10
    # ถ้ารอบไหนไม่มีอะไรเปลี่ยน (changed == False) → หยุด
    #
    # [BASH] ประมาณ:
    #        for pass in 1 2 3 4 5; do
    #            changed=0
    #            for k in "${!cfg[@]}"; do
    #                new=$(eval echo "${cfg[$k]}")   # อันตราย! อย่าทำจริง
    #                ...
    #            done
    #            [ $changed -eq 0 ] && break
    #        done
    for _ in range(5):
        changed = False
        # list(cfg) = copy รายชื่อ key เพื่อวนแก้ค่าได้ปลอดภัย
        # [BASH] for k in "${!cfg[@]}"; do
        for k in list(cfg):
            v = cfg[k]
            # re.sub แทนที่ทุกจุดที่ match
            # lambda m: ... = ฟังก์ชันเล็ก ๆ ที่รับ match object
            #   m.group(1) = ชื่อจาก ${NAME}
            #   m.group(2) = ชื่อจาก $NAME
            #   cfg.get(name, "") = ถ้าไม่พบ key ใช้สตริงว่าง
            #
            # [BASH] new_v=$(echo "$v" | sed -E 's/\$\{?([A-Za-z0-9_]+)\}?/\${cfg[\1]}/g')
            new_v = _ENV_REF_RE.sub(
                lambda m: cfg.get(m.group(1) or m.group(2), ""),
                v
            )
            if new_v != v:
                cfg[k] = new_v
                changed = True
        if not changed:
            break  # นิ่งแล้ว ไม่ต้องวนต่อ

    return cfg, found_path


def _get_val(cfg, key, default, cast_type=str):
    """
    อ่านค่าจาก dict พร้อมแปลงชนิด (int/float/str) และมีค่า default

    กติกา SSOT ของโปรเจกต์นี้:
        KEY=            (ค่าว่าง)  → ใช้ default ไม่ใช่ 0
        KEY=abc (ผิดชนิด)          → ใช้ default (ไม่ crash)

    [BASH] _get_val() { local v="${cfg[$1]}"; echo "${v:-$3}"; }
           แต่ Python ตรงนี้พยายาม cast ก่อน ถ้า cast ไม่ได้ค่อยใช้ default
    """
    # `key in cfg` = มี key นี้ไหม
    # `cfg[key] != ""` = ค่าไม่ว่าง
    if key in cfg and cfg[key] != "":
        try:
            return cast_type(cfg[key])  # int("14") / float("0.5") / str(...)
        except (ValueError, TypeError):
            # แปลงไม่ได้ เช่น FUSION_CHANCE_MAX="ุ1" (มีอักษรไทยปน)
            # → ตกไปใช้ default ด้านล่าง
            pass
    return default


# ==============================================================================
# [2] CSV LOGGER — บันทึกผลทุกรอบลงไฟล์ CSV
# ==============================================================================
# ทำไมต้องมี CSV?
#   - เอาไปเปิดใน Excel / Google Sheets เพื่อวิเคราะห์
#   - fusion_live_hud.py อาจอ่านไฟล์นี้ไปทำ dashboard
#   - เก็บประวัติแม้บอทจะหยุดไปแล้ว
#
# ไฟล์ปลายทาง: logs/dice_session_latest.csv
# ถูก "เขียนทับ" ทุกครั้งที่ Reset() (header ใหม่) แล้ว append ทีละรอบ

CSV_FILE_CANDIDATES = [
    os.path.normpath(os.path.join(_base_dir, "..", "logs", "dice_session_latest.csv")),
    os.path.normpath(os.path.join(_base_dir, "..", "simulator", "logs", "dice_session_latest.csv")),
    os.path.normpath(os.path.join(_base_dir, "logs", "dice_session_latest.csv")),
    r"c:\Users\User\simulator\logs\dice_session_latest.csv",
]

_csv_path = None  # path ที่เลือกได้ (กำหนดตอน _init_csv)


def _init_csv():
    """
    เลือกโฟลเดอร์ logs ที่มีอยู่จริง แล้วสร้างไฟล์ใหม่พร้อม header

    [BASH] for p in "${CSV_CANDIDATES[@]}"; do
               [ -d "$(dirname "$p")" ] && { csv_path="$p"; break; }
           done
           printf 'Round,Mode,...\n' > "$csv_path"
    """
    global _csv_path
    # หา path ที่ "โฟลเดอร์แม่" มีอยู่จริง (ไม่ต้องมีไฟล์ก็ได้)
    for p in CSV_FILE_CANDIDATES:
        d = os.path.dirname(p)
        if os.path.isdir(d):
            _csv_path = p
            break

    # ถ้าไม่เจอโฟลเดอร์ไหนเลย → ใช้ตัวสุดท้าย (path ตายตัว) แล้วพยายามสร้าง
    if _csv_path is None:
        _csv_path = CSV_FILE_CANDIDATES[-1]

    try:
        logs_dir = os.path.dirname(_csv_path)
        # os.makedirs = mkdir -p (สร้างโฟลเดอร์แม่ทั้งหมด)
        # [BASH] mkdir -p "$logs_dir"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # เปิดโหมด "w" = เขียนทับ (truncate) แล้วเขียน header
        #
        # [เทคนิค] newline="" จำเป็นบน Windows เพื่อไม่ให้ csv module
        #          เติม \r\n ซ้ำจนกลายเป็นบรรทัดว่าง
        #          แต่ Python 2/IronPython ไม่รับ argument นี้ → fallback
        try:
            with open(_csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Round", "Mode", "Result", "Roll", "Bet", "RoundPnL",
                    "NetPnL", "Balance", "LossStreak", "ProfitVault",
                    "ConsecutiveLosses"
                ])
        except TypeError:
            with open(_csv_path, "w") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Round", "Mode", "Result", "Roll", "Bet", "RoundPnL",
                    "NetPnL", "Balance", "LossStreak", "ProfitVault",
                    "ConsecutiveLosses"
                ])
    except Exception:
        # เขียนไม่ได้ (สิทธิ์ไม่พอ / path แปลก) ก็ไม่เป็นไร
        # ห้ามให้ logging ทำให้บอทหยุด
        pass


def _log_csv(*args):
    """
    เขียนหนึ่งแถวลง CSV

    รับ argument ได้ 2 แบบ (เพื่อความเข้ากันได้กับโค้ดเวอร์ชันเก่า):
        9 ตัว  → ไม่มีค่า Roll (ใส่ 0.0 ให้)
        10+ ตัว → มี Roll ครบ

    [BASH] _log_csv() { echo "$1,$2,..." >> "$csv_path"; }

    [เทคนิค] *args = รับ argument กี่ตัวก็ได้ เป็น tuple
             เทียบเท่า "$@" ใน Bash
    """
    if not _csv_path:
        return  # ยังไม่ init → ไม่ต้องทำอะไร

    try:
        # ── แกะ argument ตามจำนวน ────────────────────────────────────────
        if len(args) == 9:
            rnd, mode, result, bet, round_pnl, net_pnl, bal, streak, vault = args
            roll = 0.0
            con_losses = 0
        elif len(args) >= 10:
            rnd = args[0]
            mode = args[1]
            result = args[2]
            roll = args[3]
            bet = args[4]
            round_pnl = args[5]
            net_pnl = args[6]
            bal = args[7]
            streak = args[8]
            vault = args[9]
            con_losses = args[10] if len(args) > 10 else 0
        else:
            return  # จำนวน argument ไม่ถูกต้อง → ข้าม

        # ── จัดรูปแบบตัวเลข ──────────────────────────────────────────────
        # "{0:.8f}".format(x) = ทศนิยม 8 ตำแหน่ง
        # [BASH] printf "%.8f" "$x"
        #
        # float(...) กันกรณีค่าที่รับมาเป็นสตริง
        row = [
            rnd, mode, result,
            "{0:.2f}".format(float(roll)),
            "{0:.8f}".format(float(bet)),
            "{0:.8f}".format(float(round_pnl)),
            "{0:.8f}".format(float(net_pnl)),
            "{0:.8f}".format(float(bal)),
            streak,
            "{0:.8f}".format(float(vault)),
            con_losses,
        ]

        # เปิดโหมด "a" = append ต่อท้ายไฟล์
        # [BASH] >> "$csv_path"
        try:
            with open(_csv_path, "a", newline="") as f:
                csv.writer(f).writerow(row)
        except TypeError:
            with open(_csv_path, "a") as f:
                csv.writer(f).writerow(row)
    except Exception:
        # logging ผิดพลาดต้องไม่ทำให้การเดิมพันหยุด
        pass


# ==============================================================================
# [3] FUSION BOT MATH ENGINE — สูตรคณิตศาสตร์ทั้งหมด
# ==============================================================================
# ส่วนนี้คือ "สมอง" ของกลยุทธ์ อธิบายทีละสูตร


def _random_chance(chance_min, chance_max):
    """
    สุ่ม Chance ระหว่าง chance_min ถึง chance_max (หน่วย %)

    ตัวอย่าง: _random_chance(0.5, 0.75) → ได้ค่าประมาณ 0.63%

    [BASH] awk -v a=0.5 -v b=0.75 'BEGIN{srand(); print a+rand()*(b-a)}'
           (Bash เองสุ่มทศนิยมไม่ได้ ต้องใช้ awk)

    [ทำไมต้องมี try/except]
      IronPython (Python บน .NET ที่ Gambler.Bot ใช้) สามารถเรียก System.Random
      ได้โดยตรง ซึ่งเสถียรกว่า module random ของ Python 2
      ถ้ารันด้วย Python ปกติ (CPython) จะ import System ไม่ได้
      → ตกไปใช้ random.uniform แทน
    """
    try:
        import System  # .NET library (มีเฉพาะ IronPython)
        rng = System.Random()
        # NextDouble() คืนค่า 0.0 ≤ x < 1.0
        # แปลงเป็นช่วง [min, max): min + rand*(max-min)
        c = chance_min + rng.NextDouble() * (chance_max - chance_min)
    except Exception:
        import random as _r
        c = _r.uniform(chance_min, chance_max)

    # clamp = บังคับค่าให้อยู่ในช่วงที่ปลอดภัย
    # [BASH] c=$(awk -v c="$c" 'BEGIN{ if(c<0.01) c=0.01; if(c>99) c=99; print c }')
    if c < 0.01:
        c = 0.01
    if c > 99.0:
        c = 99.0
    return c


def _get_payout_and_multiplier(chance_pct, bonus_pct, use_house_edge, house_edge):
    """
    คำนวณ payout และ multiplier ของ "ไม้ถัดไป" จาก Chance

    พารามิเตอร์:
        chance_pct      = โอกาสชนะเป็นเปอร์เซ็นต์ (0.5 = 0.5%)
        bonus_pct       = โบนัสที่ต้องการบวกเพิ่ม (%) เช่น 10 = กำไรเกินทุน 10%
        use_house_edge  = True → ใช้ค่า house_edge ที่ส่งมา
                          False → ใช้ 0.99 ตายตัว (เท่ากับ house edge 1%)
        house_edge      = house edge ของคาสิโน (%) เช่น 1.0

    [สูตร] payout (ตัวคูณเงินรางวัล) = (1 - HE/100) / chance_decimal
           chance_decimal = chance_pct / 100

    ตัวอย่าง (HE = 1%):
        chance 98%   → payout = 0.99 / 0.98   = 1.0102x
        chance 2%    → payout = 0.99 / 0.02   = 49.5x
        chance 0.5%  → payout = 0.99 / 0.005  = 198x

    [สูตร] multiplier = 1 + (1 + bonus/100) / (payout - 1)

    ทำไมต้องเป็นสูตรนี้?
        สมมติเดิมพัน b แล้วแพ้ → ไม้ต่อไปต้องเดิมพัน b × multiplier
        ถ้าชนะ กำไรจากไม้ใหม่ = (b × multiplier) × (payout - 1)
        ต้องการให้กำไรนั้น = ขาดทุนเดิม (b) + โบนัส
        → multiplier × (payout - 1) = 1 + bonus
        → multiplier = 1 + (1 + bonus) / (payout - 1)
        (พอชนะจะได้ทุนที่เสียมาทั้งหมดคืน + กำไรอย่างน้อย bonus%
         ถ้าแพ้หลายไม้ติด กำไรที่ได้จะมากกว่า bonus% ด้วย)

    ตัวอย่าง:
        chance 0.5%, bonus 10% → payout 198 → mul = 1 + 1.1/197 ≈ 1.00558
        chance 2%,   bonus 10% → payout 49.5 → mul ≈ 1.02268
        chance 98%,  bonus 10% → payout 1.0102 → mul ≈ 108.8  (โหดมาก)

    [BASH] ใช้ awk:
        payout=$(awk -v c=0.5 -v he=1 'BEGIN{print (1-he/100)/(c/100)}')
        mul=$(awk -v p="$payout" -v b=10 'BEGIN{print 1+(1+b/100)/(p-1)}')
    """
    # แปลง % → สัดส่วนทศนิยม และ clamp ให้อยู่ในช่วง (0, 1)
    # กัน division by zero และค่าแปลก ๆ
    cd = max(0.0001, min(0.9999, chance_pct / 100.0))

    if use_house_edge and house_edge > 0:
        # คาสิโนหักส่วนแบ่งตาม HE จริง
        payout = (1.0 - house_edge / 100.0) / cd
    else:
        # ใช้ค่ามาตรฐาน 99% (HE 1%) แบบตายตัว
        payout = 0.99 / cd

    # payout ต้องมากกว่า 1 เสมอ ไม่งั้น (payout - 1) เป็น 0 → หารศูนย์
    if payout <= 1.0:
        payout = 1.0001

    multiplier = 1.0 + (1.0 + bonus_pct / 100.0) / (payout - 1.0)
    return multiplier, payout


def _get_constant_divisor(chance_ref, bonus_pct, losses, use_house_edge, house_edge):
    """
    คำนวณ "ตัวหาร" ของเงินทุน สำหรับแก้สมการหา base bet

    [สูตร] divisor = 1 + mul + mul² + ... + mul^(losses-1)
            = ผลรวมอนุกรมเรขาคณิต (geometric series)

    แนวคิด:
        ถ้าเริ่มที่ base bet = b และแพ้ติดกัน N ไม้
        เงินที่ต้องใช้ทั้งหมด = b × (1 + mul + mul² + ... + mul^(N-1))
        เราอยากให้ผลรวมนี้ "พอดี" กับเงินทุนใน cycle
        → b = เงินทุน / divisor

    ตัวอย่าง (mul ≈ 1.00558, N = 700):
        divisor ≈ (1.00558^700 - 1) / 0.00558 ≈ 8,649
        ถ้าเงินทุน 31.7 → base bet ≈ 0.00367

    [BASH] total=0; p=1
           for ((i=0; i<N; i++)); do total=$(awk -v t="$total" -v p="$p" 'BEGIN{print t+p}'); p=$(awk -v p="$p" -v m="$mul" 'BEGIN{print p*m}'); done
           (ช้าและต้องใช้ awk เพราะ bash arithmetic เป็นจำนวนเต็ม)

    [เทคนิค] ใช้ math.pow(mul, i) ตรง ๆ ในลูป — เข้าใจง่าย
             แม้จะมีสูตรปิด (closed form) ที่เร็วกว่า แต่ N ไม่ใหญ่มาก
             แต่โค้ดเวอร์ชันนี้เพิ่ม "overflow protection" เพราะ
             ถ้า mul ใหญ่หรือ N มาก ค่าอาจระเบิดเป็น infinity

    [เทคนิค] กัน overflow 4 ชั้น:
        1. ถ้า mul <= 1.0 → อนุกรมไม่โต ใช้จำนวน loss ตรง ๆ
        2. ถ้า (N-1) × log(mul) > 700 → คืน inf ทันที
           (เพราะ e^700 ≈ 1e304 ใกล้ขอบ float 64-bit แล้ว)
        3. ระหว่างบวกลูกบาศก์ทีละ term ถ้าติด inf → คืน inf
        4. ถ้า math.pow โยน OverflowError/ValueError → คืน inf
    """
    # ดึง multiplier จาก Chance อ้างอิง
    mul, _ = _get_payout_and_multiplier(chance_ref, bonus_pct, use_house_edge, house_edge)

    # ชั้นที่ 1: mul <= 1 → divisor ควรเป็น losses (อย่างน้อย 1)
    if mul <= 1.0:
        return float(max(1, losses))

    try:
        # ชั้นที่ 2: ตรวจล่วงหน้าด้วย log
        # [สูตร] mul^(N-1) = e^((N-1)×ln(mul))
        # ถ้า exponent > 700 → เกินขอบเขต float → ไม่ต้องคำนวณให้เสียเวลา
        if (losses - 1) * math.log(mul) > 700.0:
            return float("inf")

        total = 0.0
        # range(losses) = 0, 1, 2, ..., losses-1
        # [BASH] for ((i=0; i<losses; i++))
        for i in range(losses):
            term = math.pow(mul, i)
            total += term
            # ชั้นที่ 3: ถ้าผลรวมกลายเป็น inf ระหว่างทาง
            if math.isinf(total):
                return float("inf")
        return total
    except (OverflowError, ValueError):
        # ชั้นที่ 4: math.pow ระเบิด
        return float("inf")


def _solve_base_bet(cycle_bal, chance_ref, bonus_pct, losses, min_bet, use_he, he):
    """
    แก้สมการหา base bet ที่ทำให้เงินทุนรับ loss ได้ครบ N ไม้

    [สูตร] base = cycle_bal / divisor
           โดย divisor มาจาก _get_constant_divisor()

    คืนค่า (base_bet, divisor) — คืนทั้งสองค่าเป็น tuple
    [BASH] จะต้อง echo สองบรรทัดแล้วใช้ read หรือใช้ global variables

    [ระวัง] ถ้า divisor เป็น infinity (mul ใหญ่เกินไป)
            base = เงินทุน / infinity = 0 → ใช้ min_bet แทน
            ถ้า divisor <= 0 (ไม่ควรเกิด) ก็ใช้ min_bet เช่นกัน
    สุดท้ายบังคับ base ≥ min_bet เพราะคาสิโนมีขั้นต่ำ
    """
    d = _get_constant_divisor(chance_ref, bonus_pct, losses, use_he, he)

    # math.isinf(d) = d เป็น infinity หรือ -infinity
    # [BASH] เทียบด้วย awk: if (d == "inf" || d <= 0)
    if math.isinf(d) or d <= 0:
        return min_bet, d

    base = cycle_bal / d
    return max(base, min_bet), d


def _solve_dynamic_allowed_losses(chance_pct, risk_alpha):
    """
    คำนวณจำนวน loss ติดกันที่ "ยอมรับได้" จากความน่าจะเป็นที่ยอมให้เจอ

    [สูตร] n = ceil( log(alpha) / log(1 - p) )

    ความหมาย:
        p = chance ที่จะชนะ (ทศนิยม)
        q = 1 - p = chance ที่จะแพ้
        q^n = ความน่าจะเป็นที่จะแพ้ติดกัน n ไม้
        อยากให้ q^n ≤ alpha (เช่น alpha = 0.001 = 0.1%)
        → n ≥ log(alpha) / log(q)

    ตัวอย่าง (alpha = 0.001):
        chance 0.5%  → q=0.995  → n ≈ 1379 ไม้
        chance 0.75% → q=0.9925 → n ≈ 918 ไม้
        chance 2%    → q=0.98   → n ≈ 342 ไม้
        chance 98%   → q=0.02   → n ≈ 1.77 → ceil = 2 → บังคับขั้นต่ำ 3

    ยิ่ง chance ต่ำ → แพ้ติดกันได้ยาวขึ้น → ต้องเตรียมทุนรับได้มากกว่า
    (แต่ payout ก็สูงขึ้นด้วย)

    [BASH] n=$(awk -v a="$alpha" -v q="$q" 'BEGIN{print int(log(a)/log(q))+1}')
           (ไม่ตรงเป๊ะเพราะต้อง ceil; ใช้ int แล้ว +1 ถ้าไม่ลงตัว)
    """
    p = max(0.0001, min(0.9999, chance_pct / 100.0))
    q = 1.0 - p

    # ถ้า q >= 1 (p ≈ 0) → แพ้แน่นอน → คืนค่าสูงสุดแบบกันพัง
    if q >= 1.0:
        return 999

    # math.ceil = ปัดขึ้นเป็นจำนวนเต็ม
    n = math.ceil(math.log(risk_alpha) / math.log(q))
    # บังคับขั้นต่ำ 3 ไม้ — กันค่าแปลก ๆ จาก config
    return max(3, int(n))


# ==============================================================================
# [4] GLOBAL STATE — ตัวแปรสถานะทั้งหมด
# ==============================================================================
# ใน Python ตัวแปรที่ประกาศที่ระดับไฟล์ (ไม่มี indent) เป็น "global"
# ฟังก์ชันสามารถ "อ่าน" ได้เลย แต่ถ้าจะ "เขียนทับ" ต้องประกาศ global ก่อน
#
# [BASH] ตัวแปร shell ก็เป็น global โดยธรรมชาติ
#        ฟังก์ชันแก้ค่าได้เลยโดยไม่ต้องประกาศอะไร
#        (ถ้าอยากให้เป็น local ต้องใช้คำสั่ง `local`)
#
# [ระวัง] Python ไม่มี `local` สำหรับตัวแปรระดับไฟล์
#        ถ้าในฟังก์ชันเขียน `x = 5` โดยไม่ประกาศ global x
#        Python จะสร้างตัวแปร local ชื่อ x ขึ้นมาใหม่
#        แล้วค่าข้างนอกจะไม่เปลี่ยน — นี่คือ bug ที่มือใหม่เจอบ่อยมาก

_cfg = {}          # dict ของ config ที่โหลดมา
_env_path = None    # path ของไฟล์ config ที่ใช้จริง (None = ใช้ default)

# ── Fusion config (ค่าตั้งต้น; Reset() จะโหลดทับจากไฟล์) ──────────────────────
_main_mode          = 1       # 1 = WAGER FOCUS+RECOVERY, 2 = PROFIT FOCUS
_wager_chance       = 98.0    # Chance ตอนปั่นยอด (%)
_wager_bet_percent  = 2.5     # เดิมพันกี่ % ของ balance ต่อไม้ (โหมด WAGER)
_loss_cut_percent   = 4.0     # ขาดทุนกี่ % แล้วตัดเข้าโหมดกู้ทุน
_recover_profit_pct = 1.0     # เป้ากำไรตอนกู้ = ยอดเสีย + balance×N%
_wager_target       = 100.0   # เป้ายอดเทิร์นโอเวอร์รวม
_enable_wager_target= True    # เปิด/ปิดการหยุดเมื่อถึงเป้า wager
_auto_chance        = True    # True = สุ่ม chance, False = ใช้ค่าคงที่
_chance_min         = 0.5     # ขอบล่างของการสุ่ม (%)
_chance_max         = 0.75    # ขอบบนของการสุ่ม (%)
_chance_fixed       = 0.5     # Chance คงที่เมื่อปิด auto
_random_on_win      = True    # ชนะแล้วสุ่ม chance ใหม่ไหม
_random_on_lose     = False   # แพ้แล้วสุ่ม chance ใหม่ไหม
_risk_bonus_pct     = 5.0     # โบนัสที่บวกเข้า multiplier (%)
_house_edge         = 1.0     # House edge ของคาสิโน (%)
_auto_cal_allowed_loss = True # True = คำนวณจำนวน loss ที่รับได้อัตโนมัติ
_risk_alpha         = 0.001   # ความเสี่ยงที่ยอมรับ (0.001 = 0.1%)
_manual_allowed_losses = 14   # จำนวน loss ที่รับได้ (เมื่อปิด auto)
_allowed_losses     = 14      # ค่าที่ใช้จริง (อาจถูกคำนวณใหม่)
_min_bet            = 0.00000001  # เดิมพันขั้นต่ำของระบบ
_stop_profit_ratio  = 0.2     # หยุดเมื่อกำไรถึง N× ของทุนเริ่ม (0.2 = +20%)
_stop_loss_ratio    = 0.0     # หยุดเมื่อขาดทุนถึง N× (0 = ปิด)
_stop_max_streak    = 0       # หยุดเมื่อแพ้ติดกัน N ไม้ (0 = ปิด)

# ── Runtime state (สถานะระหว่างเล่น; Reset() เซ็ตใหม่ทุกครั้ง) ───────────────
_session_start_balance  = 0.0  # balance ตอนเริ่ม session
_start_time             = 0.0  # เวลาเริ่ม (time.time())
_total_bets             = 0    # จำนวนไม้ทั้งหมด
_total_wagered          = 0.0  # ยอดเดิมพันสะสม (turnover)
_win_count              = 0    # จำนวนครั้งที่ชนะ
_lose_count             = 0    # จำนวนครั้งที่แพ้
_loss_streak            = 0    # แพ้ติดกันกี่ไม้ (ปัจจุบัน)
_max_loss_streak        = 0    # แพ้ติดกันสูงสุดที่เคยเจอ
_consecutive_losses     = 0    # ตัวนับ loss สำหรับ reset base ในโหมด PROFIT

_mode                   = "WAGER"  # โหมดปัจจุบัน: "WAGER" หรือ "PROFIT"
_working_balance        = 0.0  # balance ที่ใช้คิด (ถูก set แต่ไม่ค่อยได้ใช้)
_profit_vault           = 0.0  # กำไรที่ "เก็บเข้ากรุ" แล้ว (bookkeeping)
_cycle_start_balance    = 0.0  # balance ตอนเริ่ม cycle ปัจจุบัน (ใช้คำนวณ base)
_original_cycle_balance = 0.0  # balance ตั้งต้นของ cycle (ใช้วัดกำไรสะสม)
_wager_cycle_start      = 0.0  # balance ตอนเริ่มรอบปั่นยอด
_profit_cycle_start     = 0.0  # balance ตอนเริ่มรอบกู้ทุน
_wager_loss_amount      = 0.0  # ยอดที่เสียตอนตัด loss (ใช้เป็นเป้ากู้)

_base_bet               = 0.0  # base bet ที่คำนวณได้
_divisor                = 1.0  # ตัวหารที่คำนวณได้ (เก็บไว้ดู)
_wager_base_bet         = 0.0  # base bet ของโหมด WAGER
_current_chance         = 98.0 # Chance ที่ใช้อยู่


# ==============================================================================
# [5] INTERNAL HELPERS — ฟังก์ชันช่วยภายใน
# ==============================================================================

def _update_base(active_chance=None):
    """
    คำนวณ base bet + จำนวน loss ที่รับได้ ใหม่จากเงินทุนปัจจุบัน

    เรียกเมื่อ:
        - Reset() ครั้งแรก
        - เปลี่ยน chance ตอนชนะในโหมด PROFIT
        - แพ้ครบ N ไม้ (reset base)
        - เปลี่ยนโหมด

    active_chance:
        ถ้าส่งมา → ใช้ chance นั้นเป็นตัวอ้างอิง
        ถ้าไม่ส่ง  → ใช้ chance_min (ถ้า auto) หรือ chance_fixed

    [BASH] _update_base() {
               local ref="${1:-...}"
               _base_bet=$(awk ...)
           }
    """
    global _base_bet, _divisor, _cycle_start_balance, _allowed_losses

    # เลือก chance อ้างอิง
    if active_chance is not None:
        ref = active_chance
    else:
        # ใช้ขอบล่าง (ระวังที่สุด) เมื่อสุ่ม chance
        ref = _chance_min if _auto_chance else _chance_fixed

    # จำนวน loss ที่รับได้: อัตโนมัติ หรือ ใช้ค่าที่ตั้งไว้
    if _auto_cal_allowed_loss:
        _allowed_losses = _solve_dynamic_allowed_losses(ref, _risk_alpha)
    else:
        _allowed_losses = _manual_allowed_losses

    # ใช้ house edge จริงเฉพาะโหมด 2 (PROFIT FOCUS)
    # โหมด 1 ใช้ 0.99 ตายตัว (ซึ่งเท่ากับ HE 1% อยู่แล้ว)
    use_he = (_main_mode == 2)

    # คำนวณ base bet จาก "เงินทุนตอนเริ่ม cycle" (ไม่ใช่ balance ปัจจุบัน)
    # [ระวัง] ถ้า balance ลดลงมากระหว่าง cycle, base bet จะยังอิงยอดเดิม
    _base_bet, _divisor = _solve_base_bet(
        _cycle_start_balance, ref, _risk_bonus_pct,
        _allowed_losses, _min_bet, use_he, _house_edge
    )


def _separate_profit_reset():
    """
    "เก็บกำไรเข้า vault แล้ว reset cycle" — แบบ A (แยก Profit + Reset Balance)

    ในตัวจำลอง (fusion_bot.py) ทำได้จริง: ตั้ง balance กลับไปที่ยอดตั้งต้น
    แต่ใน Gambler.Bot จริง เรา "แก้ยอดเงินในบัญชีคาสิโนไม่ได้"
    โค้ดนี้จึงทำได้แค่:
        - บันทึกกำไรลง _profit_vault (เป็นตัวเลขทางบัญชี)
        - ตั้ง _working_balance / _cycle_start_balance กลับไปที่ยอดตั้งต้น
          (เพื่อให้การคำนวณรอบถัดไปคิดจากฐานเดิม)

    [BASH] Profit Vault ≈ กระปุกที่แยกเงินกำไรออกมา
           ไม่ใช่เงินในบัญชีจริง แต่เป็นตัวเลขที่เราจำไว้

    [สำคัญ] บรรทัด `_original_cycle_balance = cur_bal`
            คือการ "เลื่อนเส้นฐาน" (baseline) ไปที่ยอดปัจจุบัน
            เพื่อไม่ให้นับกำไรของ cycle เก่าซ้ำอีก
            หลัง reset: total_pnl = vault + (balance - balance) = vault
            (ดูภาคผนวก ข้อ 7.4 ประกอบ)
    """
    global _profit_vault, _working_balance, _cycle_start_balance
    global _original_cycle_balance

    cur_bal = float(Balance)  # อ่านยอดเงินจริงจากบอท

    # กำไรของ cycle นี้ = ยอดปัจจุบัน - ยอดตั้งต้นของ cycle
    cp = cur_bal - _original_cycle_balance

    if cp > 0:
        # มีกำไร → เก็บเข้า vault
        _profit_vault += cp

        Print("=" * 50)
        Print("✅ Cycle Complete! Profit: {0:.8f}".format(cp))
        Print("💎 Profit Vault: {0:.8f}".format(_profit_vault))
        Print("🔄 Reset to: {0:.8f}".format(_original_cycle_balance))
        Print("=" * 50)

        # Type A: reset balance back (simulation — on real bot cannot change balance)
        # We track working_balance as the "virtual" reset
        _working_balance        = _original_cycle_balance
        _cycle_start_balance    = _original_cycle_balance
        # เลื่อนเส้นฐานมาที่ balance ปัจจุบัน (แก้การนับกำไรซ้ำ)
        _original_cycle_balance = cur_bal
    else:
        # จบ cycle แบบไม่ได้กำไร → แค่เตือน ไม่รีเซ็ต
        Print("⚠️  Cycle ended without profit ({0:.8f})".format(cp))
        _working_balance = cur_bal


def _switch_to_wager():
    """
    เปลี่ยนเข้าสู่โหมด WAGER (ปั่นยอด)

    หลักการ:
        - base bet = 2.5% ของ balance ปัจจุบัน
        - Chance = 98% (ชนะบ่อย)
        - High = True → เดิมพันฝั่ง "สูง" (roll > threshold)
          ที่ chance 98% threshold จะอยู่ราว 2.0
          หมายความว่าชนะเมื่อ roll > 2.0 (โอกาส 98%)

    [BASH] NextBet.Amount=... ; NextBet.Chance=98 ; NextBet.High=1
    """
    global _mode, _loss_streak, _consecutive_losses
    global _wager_cycle_start, _wager_base_bet, _wager_loss_amount
    global _current_chance

    _mode             = "WAGER"
    _loss_streak      = 0
    _consecutive_losses = 0
    # จำยอดเงินตอนเริ่มรอบปั่น เพื่อวัด "% ขาดทุน"
    _wager_cycle_start  = float(Balance)
    # เดิมพัน 2.5% ของยอด ณ ตอนนี้
    _wager_base_bet     = _wager_cycle_start * (_wager_bet_percent / 100.0)
    _wager_loss_amount  = 0.0
    _current_chance     = _wager_chance

    # สั่งไม้ถัดไปให้บอท
    NextBet.Chance = _wager_chance
    NextBet.Amount = max(_wager_base_bet, _min_bet)  # ห้ามต่ำกว่าขั้นต่ำ
    NextBet.High   = True

    Print("🟢 → WAGER MODE  base_bet={0:.8f}  chance={1:.2f}%".format(
        _wager_base_bet, _wager_chance))


def _switch_to_profit():
    """
    เปลี่ยนเข้าสู่โหมด PROFIT (กู้ทุน/ทำกำไร)

    หลักการ:
        - เริ่ม cycle ใหม่ที่ balance ปัจจุบัน
        - สุ่ม chance (หรือใช้ค่าคงที่)
        - คำนวณ base bet ให้รับ loss ได้ N ไม้
        - ตั้งไม้แรกที่ base bet

    [BASH] คล้าย _switch_to_wager แต่คำนวณ base bet จากสูตร
    """
    global _mode, _loss_streak, _consecutive_losses
    global _profit_cycle_start, _cycle_start_balance
    global _base_bet, _divisor, _current_chance

    _mode             = "PROFIT"
    _loss_streak      = 0
    _consecutive_losses = 0
    # จุดเริ่มต้นของรอบกู้ = balance หลังตัดขาดทุน
    _profit_cycle_start  = float(Balance)
    _cycle_start_balance = float(Balance)

    # เลือก chance
    if _auto_chance:
        _current_chance = _random_chance(_chance_min, _chance_max)
    else:
        _current_chance = _chance_fixed

    # คำนวณ base bet จากเงินทุนที่เหลือ
    _update_base(_current_chance)

    # คำนวณ multiplier ไว้แสดงผล (ไม่ได้ใช้ตัดสินใจตรงนี้)
    mul, payout = _get_payout_and_multiplier(
        _current_chance, _risk_bonus_pct, (_main_mode == 2), _house_edge
    )

    # ตั้งไม้แรกของโหมด PROFIT
    NextBet.Chance = _current_chance
    NextBet.Amount = max(_base_bet, _min_bet)
    NextBet.High   = True

    Print("🟡 → PROFIT MODE  base={0:.8f}  chance={1:.2f}%  mul={2:.4f}x".format(
        _base_bet, _current_chance, mul))


def _show_status():
    """
    พิมพ์สรุปสถานะลง log (ไม่ได้เปลี่ยนการเดิมพัน)

    คำนวณ:
        cycle_pnl = กำไร/ขาดทุนของ cycle ปัจจุบัน
        total_pnl = vault + (balance - ยอดตั้งต้น)
        ROI       = total_pnl / ทุนเริ่ม session × 100

    [BASH] echo "Balance: ..."; awk สำหรับคำนวณ %
    """
    bal = float(Balance)
    runtime = time.time() - _start_time  # เวลาที่เล่นมา (วินาที)

    # กำไรของ cycle ปัจจุบัน ต่างกันตามโหมด
    if _mode == "WAGER":
        cycle_pnl = bal - _wager_cycle_start
    else:
        cycle_pnl = bal - _profit_cycle_start

    # กำไรรวม = ที่เก็บเข้ากรุ + ที่ยังอยู่ในบัญชี
    total_pnl = _profit_vault + (bal - _original_cycle_balance)

    Print("┌──────────────────────────────────────────────┐")
    Print("⏱  {0:.0f}s | Strategy: {1} | Mode: {2}".format(
        runtime,
        "WAGER FOCUS+RECOVERY" if _main_mode == 1 else "PROFIT FOCUS",
        _mode
    ))
    Print("💰 Balance:      {0:.8f}".format(bal))
    Print("💎 Profit Vault: {0:.8f}".format(_profit_vault))
    # "{0:+.8f}" = บังคับแสดงเครื่องหมาย + สำหรับค่าบวก
    Print("📊 Cycle P/L:    {0:+.8f}".format(cycle_pnl))
    Print("🎁 Total P/L:    {0:+.8f}  ROI: {1:+.2f}%".format(
        total_pnl, total_pnl / _session_start_balance * 100 if _session_start_balance > 0 else 0.0
    ))
    Print("🎲 Next Bet:     {0:.8f} | Chance: {1:.2f}%".format(
        float(NextBet.Amount), float(NextBet.Chance)
    ))
    Print("🏆 W/L: {0}/{1} | Streak: {2} (Max: {3})".format(
        _win_count, _lose_count, _loss_streak, _max_loss_streak
    ))
    Print("⚡ ConLoss/Cycle: {0}/{1}".format(_consecutive_losses, _allowed_losses))

    # รายละเอียดเพิ่มเติมเฉพาะโหมด 1
    if _main_mode == 1:
        Print("📈 Wagered: {0:.2f} / {1:.2f}".format(_total_wagered, _wager_target))
        if _mode == "WAGER":
            # % ขาดทุนจากจุดเริ่มปั่น
            wl = _wager_cycle_start - bal
            pct = wl / _wager_cycle_start * 100 if _wager_cycle_start > 0 else 0.0
            Print("📉 Wager Loss: {0:.2f}% / {1:.2f}%".format(pct, _loss_cut_percent))
        else:
            # ต้องกู้อีกเท่าไร: ยอดที่เสีย + 1% ของยอดตั้งต้น
            need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
            gain = bal - _profit_cycle_start
            need_pct = need / _profit_cycle_start * 100 if _profit_cycle_start > 0 else 0.0
            gain_pct = gain / _profit_cycle_start * 100 if _profit_cycle_start > 0 else 0.0
            Print("♻  Recovery: {0:.2f}% / {1:.2f}%".format(gain_pct, need_pct))

    Print("└──────────────────────────────────────────────┘")


# ==============================================================================
# [6] GAMBLER.BOT CALLBACKS — ฟังก์ชันที่บอทเรียกเอง
# ==============================================================================
# สองฟังก์ชันนี้คือ "ทางเข้า" ของสคริปต์
# บอทจะเรียกตามจังหวะด้านล่าง:
#
#   เริ่มโปรแกรม
#        │
#        ▼
#   Reset()  ──► โหลด config, เซ็ตสถานะ, ตั้งไม้แรก
#        │
#        ▼
#   วางเดิมพันไม้ที่ 1
#        │
#        ▼
#   รู้ผล → CalculateBet()  ──► คำนวณและตั้งไม้ที่ 2
#        │
#        ▼
#   วางเดิมพันไม้ที่ 2
#        │
#        ▼
#   ... วนซ้ำจนกว่าจะ Stop()
#
# [BASH] เหมือนฟังก์ชัน hook ที่ถูกเรียกโดยโปรแกรมแม่
#        เราไม่ต้องเขียน while loop เอง บอทจัดการ loop ให้


def Reset():
    """
    เรียกครั้งเดียวตอนเริ่ม session (หรือกด Start ใหม่)

    หน้าที่:
        1. โหลด config จากไฟล์
        2. เซ็ตค่าตัวแปรทั้งหมดเป็นค่าเริ่มต้น
        3. เปิดไฟล์ CSV ใหม่
        4. พิมพ์ banner
        5. คำนวณ base bet และตั้งไม้แรก

    [BASH] reset() { source config.env; ...; }
    """
    # ── ประกาศ global ทุกตัวที่จะเขียนทับ ──────────────────────────────────
    # [ระวัง] ถ้าลืมประกาศ global ตัวใดตัวหนึ่ง
    #         การ assign ข้างล่างจะสร้างตัวแปร local ขึ้นมาแทน
    #         แล้วค่าจริงข้างนอกจะไม่เปลี่ยน (bug ยอดฮิต)
    global _cfg, _env_path
    global _main_mode, _wager_chance, _wager_bet_percent, _loss_cut_percent
    global _recover_profit_pct, _wager_target, _enable_wager_target
    global _auto_chance, _chance_min, _chance_max, _chance_fixed
    global _random_on_win, _random_on_lose, _risk_bonus_pct, _house_edge
    global _allowed_losses, _min_bet, _stop_profit_ratio, _stop_loss_ratio
    global _stop_max_streak
    global _session_start_balance, _start_time, _total_bets, _total_wagered
    global _win_count, _lose_count, _loss_streak, _max_loss_streak, _consecutive_losses
    global _mode, _working_balance, _profit_vault
    global _cycle_start_balance, _original_cycle_balance
    global _wager_cycle_start, _profit_cycle_start, _wager_loss_amount
    global _base_bet, _divisor, _wager_base_bet, _current_chance

    # ── โหลด SSOT config ──────────────────────────────────────────────────
    _cfg, _env_path = load_dice_env()
    g = _cfg  # ชื่อสั้น ๆ ให้อ่านง่าย

    def gv(key, default, cast=str):
        """
        ฟังก์ชันช่วยอ่านค่า (closure)
        จับ g จาก scope ข้างนอกได้เลย ไม่ต้องส่งเป็น argument
        [BASH] ใช้ตัวแปร global g ได้เลย
        """
        return _get_val(g, key, default, cast)

    # ── อ่านค่า FUSION_* (มี GLOBAL_* เป็น fallback) ──────────────────────
    # รูปแบบ gv(key, default, cast)
    # ตัวเลข int/float ต้องระบุ cast ให้ชัด ไม่งั้นจะได้เป็นสตริง
    _main_mode           = gv("FUSION_MAIN_MODE",        1,    int)
    _wager_chance        = gv("FUSION_WAGER_CHANCE",     98.0, float)
    _wager_bet_percent   = gv("FUSION_WAGER_BET_PCT",    2.5,  float)
    _loss_cut_percent    = gv("FUSION_LOSS_CUT_PCT",     4.0,  float)
    _recover_profit_pct  = gv("FUSION_RECOVER_PROFIT_PCT", 1.0, float)
    # fallback ซ้อน: ถ้าไม่มี FUSION_WAGER_TARGET → ไปดู WAGER_TARGET → 100.0
    _wager_target        = gv("FUSION_WAGER_TARGET",     gv("WAGER_TARGET", 100.0, float), float)
    # != 0 แปลงตัวเลขเป็น boolean: 0=False, อื่น ๆ=True
    _enable_wager_target = gv("FUSION_ENABLE_WAGER_TARGET", 1, int) != 0
    _auto_chance         = gv("FUSION_AUTO_CHANCE",      1,    int) != 0
    _chance_min          = gv("FUSION_CHANCE_MIN",       0.5,  float)
    _chance_max          = gv("FUSION_CHANCE_MAX",       0.75, float)
    _chance_fixed        = gv("FUSION_CHANCE_FIXED",     0.5,  float)
    _random_on_win       = gv("FUSION_RANDOM_ON_WIN",    1,    int) != 0
    _random_on_lose      = gv("FUSION_RANDOM_ON_LOSE",   0,    int) != 0
    _risk_bonus_pct      = gv("FUSION_RISK_BONUS_PCT",   5.0,  float)
    _house_edge          = gv("HE",                      1.0,  float)
    # ลำดับ fallback: AUTO_CAL_ALLOWED_LOSS → FUSION_AUTO_CAL_ALLOWED_LOSS → 1
    _auto_cal_allowed_loss = gv("AUTO_CAL_ALLOWED_LOSS", gv("FUSION_AUTO_CAL_ALLOWED_LOSS", 1, int), int) != 0
    _risk_alpha          = gv("FUSION_RISK_ALPHA",       gv("RISK_ALPHA", 0.001, float), float)
    _manual_allowed_losses = gv("FUSION_ALLOWED_LOSSES", 14,   int)
    _allowed_losses      = _manual_allowed_losses  # ค่าชั่วคราว (จะถูกคำนวณใหม่)
    _min_bet             = gv("FUSION_MIN_BET",          0.00000001, float)
    _stop_profit_ratio   = gv("FUSION_STOP_PROFIT",      0.2,  float)
    _stop_loss_ratio     = gv("FUSION_STOP_LOSS",        0.0,  float)
    _stop_max_streak     = gv("FUSION_STOP_LOSS_STREAK", 0,    int)

    # ── Reset state ───────────────────────────────────────────────────────
    _session_start_balance  = float(Balance)
    _start_time             = time.time()
    _total_bets             = 0
    _total_wagered          = 0.0
    _win_count              = 0
    _lose_count             = 0
    _loss_streak            = 0
    _max_loss_streak        = 0
    _consecutive_losses     = 0

    _mode                   = "WAGER"
    _working_balance        = _session_start_balance
    _profit_vault           = 0.0
    _cycle_start_balance    = _session_start_balance
    _original_cycle_balance = _session_start_balance
    _wager_cycle_start      = _session_start_balance
    _profit_cycle_start     = _session_start_balance
    _wager_loss_amount      = 0.0

    # ── เปิด CSV ใหม่ (เขียนทับของเก่า) ──────────────────────────────────
    _init_csv()

    # ── พิมพ์ banner ──────────────────────────────────────────────────────
    # os.path.basename = เอาเฉพาะชื่อไฟล์จาก path
    # [BASH] basename "$path"
    Print("=" * 60)
    Print("  💎 FUSION BOT v4.1 — Gambler.Bot Edition")
    Print("  SSOT: {0}".format(os.path.basename(_env_path) if _env_path else "defaults"))
    Print("  CSV: {0}".format(_csv_path or "N/A"))
    Print("=" * 60)
    Print("  Strategy: {0}".format(
        "WAGER FOCUS + RECOVERY" if _main_mode == 1 else "PROFIT FOCUS"
    ))
    Print("  Balance:  {0:.8f}".format(_session_start_balance))
    Print("  Loss Cut: {0:.2f}% | Recover: Loss + {1:.2f}%".format(
        _loss_cut_percent, _recover_profit_pct
    ))
    Print("  Allowed Losses: {0} | Stop Profit: {1:.0f}%".format(
        _allowed_losses, _stop_profit_ratio * 100
    ))
    Print("=" * 60)

    # ── ตั้งไม้แรก ────────────────────────────────────────────────────────
    # คำนวณ base bet ล่วงหน้า (ถึงจะยังอยู่โหมด WAGER ก็ตาม)
    # [ระวัง] _update_base() ใช้ _cycle_start_balance ซึ่งตอนนี้ = ทุนเริ่มต้น
    _update_base()  # pre-calculate even for wager mode

    # เลือกโหมดแรกตาม main_mode
    if _main_mode == 1:
        _switch_to_wager()
    else:
        _switch_to_profit()


def CalculateBet():
    """
    เรียก "ก่อนวางเดิมพันไม้ถัดไป" หลังรู้ผลไม้ก่อนหน้าแล้ว

    ลำดับการทำงาน:
        1. อ่านผลไม้ก่อนหน้า (PreviousBet, Win, Balance)
        2. อัปเดตสถิติ
        3. ถ้าชนะ → ตั้งไม้ถัดไปตามโหมด
        4. ถ้าแพ้  → ตั้งไม้ถัดไปตามโหมด (อาจคูณไม้)
        5. ตรวจกฎหยุด (stop rules)
        6. บันทึก CSV + แสดงสถานะทุก 50 ไม้

    [BASH] calculate_bet() { ... } ที่ถูกเรียกจาก loop ของบอท
    """
    global _total_bets, _total_wagered, _win_count, _lose_count
    global _loss_streak, _max_loss_streak, _consecutive_losses
    global _mode, _working_balance, _profit_vault
    global _wager_loss_amount, _current_chance
    global _base_bet, _divisor

    # ── อ่านข้อมูลไม้ก่อนหน้า ─────────────────────────────────────────────
    _total_bets += 1
    bet_amt  = float(PreviousBet.TotalAmount)  # ยอดที่เพิ่งเดิมพันไป
    round_pnl = float(PreviousBet.Profit)      # กำไร/ขาดทุนของไม้นั้น
    try:
        roll_val = float(PreviousBet.Roll)     # ค่าลูกเต๋าที่ออก (0-100)
    except Exception:
        roll_val = 0.0                         # บางโหมดอาจไม่มีค่า Roll
    cur_bal  = float(Balance)                  # ยอดเงินปัจจุบัน
    # net_pnl คำนวณ "ก่อน" มีการ reset ใด ๆ ในฟังก์ชันนี้
    # ใช้ตอน log กรณีจบ recovery (จะได้ไม่นับกำไรซ้ำ)
    net_pnl  = _profit_vault + (cur_bal - _original_cycle_balance)
    won      = bool(Win)                       # True = ชนะ

    _total_wagered += bet_amt                  # สะสมยอดเทิร์นโอเวอร์
    _working_balance = cur_bal

    # ══════════════════════════════════════════════════════════════════════
    # กรณีชนะ
    # ══════════════════════════════════════════════════════════════════════
    if won:
        _win_count += 1
        _loss_streak = 0             # แพ้ติดกัน → reset เป็น 0
        _consecutive_losses = 0      # ตัวนับ reset base ก็resetด้วย

        if _mode == "WAGER":
            # โหมดปั่น: เดิมพันเท่าเดิมไปเรื่อย ๆ
            NextBet.Amount = max(_wager_base_bet, _min_bet)
            NextBet.Chance = _wager_chance

            # ถ้าถึงเป้ายอดเทิร์น → หยุดทั้ง session
            if _main_mode == 1 and _enable_wager_target and _total_wagered >= _wager_target:
                Print("🎯 Wager Target {0:.2f} reached!".format(_wager_target))
                _separate_profit_reset()
                _show_status()
                Stop()
                return  # ออกทันที ไม่ต้องคำนวณอะไรต่อ

        else:  # PROFIT mode win
            # ชนะแล้วอาจสุ่ม chance ใหม่ (ถ้าเปิด _random_on_win)
            if _auto_chance and _random_on_win:
                _current_chance = _random_chance(_chance_min, _chance_max)
            else:
                _current_chance = _chance_fixed

            # คำนวณ base bet ใหม่จาก chance ใหม่
            _update_base(_current_chance)
            NextBet.Chance = _current_chance
            NextBet.Amount = max(_base_bet, _min_bet)  # กลับไปเริ่มที่ base

            # โหมด 1: ตรวจว่ากำไรครอบยอดที่เสียตอนตัดหรือยัง
            if _main_mode == 1:
                # ต้องกู้ = ยอดที่เสีย + 1% ของยอดตั้งต้น
                need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
                # กำไรจากจุดเริ่มรอบกู้
                gain = cur_bal - _profit_cycle_start
                if gain >= need:
                    Print("✅ Recovery WIN  gain={0:+.8f}".format(gain))
                    _separate_profit_reset()
                    _switch_to_wager()   # กลับไปปั่นยอด
                    # log ด้วย net_pnl ที่คำนวณไว้ก่อน reset
                    _log_csv(_total_bets, "PROFIT", "win", roll_val, bet_amt, round_pnl, net_pnl,
                             cur_bal, _loss_streak, _profit_vault, _consecutive_losses)
                    return

            elif _main_mode == 2:
                # ── โหมด 2 (PROFIT FOCUS) ────────────────────────────────
                # ไม่มีโหมด WAGER ให้กลับไป จึงใช้วิธี "ล็อกกำไรเป็นรอบ ๆ":
                # ถ้ายอดปัจจุบันสูงกว่ายอดตั้งต้นของ cycle (cp > 0)
                # → เก็บกำไรเข้า vault, reset แล้วเล่นรอบใหม่ต่อทันที
                # (ไม่ได้ Stop() เหมือนกรณีถึง wager target)
                cp = cur_bal - _original_cycle_balance
                if cp > 0:
                    _separate_profit_reset()

                    # reset แล้วสุ่ม chance ใหม่ (ถ้าเปิด _random_on_win)
                    if _auto_chance and _random_on_win:
                        _current_chance = _random_chance(_chance_min, _chance_max)
                    else:
                        _current_chance = _chance_fixed

                    # [ระวัง] _update_base() ใช้ _cycle_start_balance
                    # ซึ่ง _separate_profit_reset() เพิ่งตั้งกลับไปที่
                    # ยอดตั้งต้น "ก่อน" อัปเดต baseline
                    # → base bet ของรอบใหม่อิงยอดเก่า (มักเล็กกว่าที่ควร)
                    #   แล้วค่อยมาอัปเดตถูกอีกครั้งตอน reset รอบถัดไป
                    _update_base(_current_chance)
                    NextBet.Amount = max(_base_bet, _min_bet)
                    NextBet.Chance = _current_chance

                    _log_csv(_total_bets, "PROFIT", "win", roll_val, bet_amt, round_pnl, net_pnl,
                             cur_bal, _loss_streak, _profit_vault, _consecutive_losses)
                    return

    # ══════════════════════════════════════════════════════════════════════
    # กรณีแพ้
    # ══════════════════════════════════════════════════════════════════════
    else:
        _lose_count += 1
        _loss_streak += 1
        _consecutive_losses += 1
        # อัปเดตสถิติแพ้ติดกันสูงสุด
        if _loss_streak > _max_loss_streak:
            _max_loss_streak = _loss_streak

        if _mode == "WAGER":
            # วัดขาดทุนสะสมจากจุดเริ่มปั่น
            cycle_loss = _wager_cycle_start - cur_bal
            loss_pct   = cycle_loss / _wager_cycle_start * 100.0 if _wager_cycle_start > 0 else 0.0
            Print("   📉 Wager Loss: {0:.2f}% / {1:.2f}%".format(loss_pct, _loss_cut_percent))

            # ถึงจุดตัดขาดทุน → จำยอดที่เสีย แล้วเข้าโหมดกู้
            if _main_mode == 1 and loss_pct >= _loss_cut_percent:
                _wager_loss_amount = cycle_loss
                Print("⚠️  Loss cut {0:.2f}% | loss={1:.8f}".format(loss_pct, cycle_loss))
                _switch_to_profit()
            else:
                # ยังไม่ถึงจุดตัด → เดิมพันเท่าเดิม
                NextBet.Amount = max(_wager_base_bet, _min_bet)
                NextBet.Chance = _wager_chance

        else:  # PROFIT mode lose
            # แพ้แล้วอาจสุ่ม chance ใหม่ (ปกติปิดไว้)
            if _auto_chance and _random_on_lose:
                _current_chance = _random_chance(_chance_min, _chance_max)

            use_he = (_main_mode == 2)
            # คำนวณ multiplier ของ chance ปัจจุบัน
            mul, _ = _get_payout_and_multiplier(
                _current_chance, _risk_bonus_pct, use_he, _house_edge
            )
            # ไม้ถัดไป = ไม้ก่อนหน้า × multiplier (martingale)
            # [ระวัง] ใช้ PreviousBet.TotalAmount (ไม้ที่เพิ่งแพ้)
            new_bet = float(PreviousBet.TotalAmount) * mul

            # ถ้าไม้ใหม่เกินเงินที่มี → ลดเหลือ 90% ของ balance
            # (กันบอทส่งเดิมพันที่เงินไม่พอ)
            if new_bet > cur_bal:
                new_bet = cur_bal * 0.9

            NextBet.Amount = max(new_bet, _min_bet)
            NextBet.Chance = _current_chance

            Print("📈 Loss #{0} | Next: {1:.8f} (x{2:.4f})".format(
                _consecutive_losses, new_bet, mul
            ))

            # แพ้ครบจำนวนที่รับได้ → reset base กลับไปเริ่มใหม่
            if _consecutive_losses >= _allowed_losses:
                Print("⛔ {0} losses → reset base".format(_allowed_losses))
                _update_base(_current_chance)
                _consecutive_losses = 0
                NextBet.Amount = max(_base_bet, _min_bet)

            # โหมด 1: ตรวจ recovery เช่นเดียวกับตอนชนะ
            # (อาจครบเป้าได้ถ้าไม้ก่อน ๆ ทำกำไรไว้มาก)
            if _main_mode == 1:
                need = _wager_loss_amount + (_original_cycle_balance * _recover_profit_pct / 100.0)
                gain = cur_bal - _profit_cycle_start
                if gain >= need:
                    Print("✅ Recovery LOSE  gain={0:+.8f}".format(gain))
                    _separate_profit_reset()
                    _switch_to_wager()
                    _log_csv(_total_bets, "PROFIT", "lose", roll_val, bet_amt, round_pnl, net_pnl,
                             cur_bal, _loss_streak, _profit_vault, _consecutive_losses)
                    return

    # ── บังคับขั้นต่ำอีกครั้ง (กันทุกเส้นทาง) ─────────────────────────────
    if float(NextBet.Amount) < _min_bet:
        NextBet.Amount = _min_bet

    # ══════════════════════════════════════════════════════════════════════
    # STOP RULES — กฎหยุดฉุกเฉิน
    # ══════════════════════════════════════════════════════════════════════
    total_pnl    = _profit_vault + (cur_bal - _original_cycle_balance)
    profit_ratio = total_pnl / _session_start_balance if _session_start_balance > 0 else 0.0

    # 1) ถึงเป้ากำไร → เก็บกำไรแล้วหยุด
    if _stop_profit_ratio > 0 and profit_ratio >= _stop_profit_ratio:
        Print("🎉 Profit target {0:.0f}% reached!".format(_stop_profit_ratio * 100))
        _separate_profit_reset()
        _show_status()
        Stop()
        return

    # 2) ถึงขีดขาดทุน → หยุด
    if _stop_loss_ratio > 0 and profit_ratio <= -_stop_loss_ratio:
        Print("🚨 Loss limit {0:.0f}% hit!".format(_stop_loss_ratio * 100))
        _show_status()
        Stop()
        return

    # 3) แพ้ติดกันเกินกำหนด → หยุด
    if _stop_max_streak > 0 and _loss_streak >= _stop_max_streak:
        Print("🚨 Max streak {0} reached!".format(_stop_max_streak))
        _show_status()
        Stop()
        return

    # 4) เงินเหลือน้อยเกินไป (น้อยกว่า 2 เท่าของขั้นต่ำ) → หยุด
    if cur_bal < _min_bet * 2:
        Print("🚨 Balance too low!")
        _show_status()
        Stop()
        return

    # ── บันทึก CSV ────────────────────────────────────────────────────────
    # คำนวณ total_pnl ใหม่ (อาจเปลี่ยนถ้ามีการ reset ข้างบน)
    total_pnl = _profit_vault + (cur_bal - _original_cycle_balance)
    _log_csv(_total_bets, _mode, "win" if won else "lose",
             roll_val, bet_amt, round_pnl, total_pnl, cur_bal, _loss_streak, _profit_vault, _consecutive_losses)

    # ── แสดงสถานะทุก 50 ไม้ ───────────────────────────────────────────────
    # % = modulo (เศษจากการหาร) [BASH] $((_total_bets % 50))
    if _total_bets % 50 == 0:
        _show_status()


# ==============================================================================
# [7] ภาคผนวก (APPENDIX) — สรุปเพื่อทบทวน
# ==============================================================================
#
# ── 7.1 ผังการทำงานแบบย่อ ────────────────────────────────────────────────────
#
#   Reset()
#     ├─ load_dice_env()            อ่าน config
#     ├─ _init_csv()                เปิด CSV ใหม่
#     ├─ _update_base()             คำนวณ base bet ล่วงหน้า
#     └─ switch mode
#          ├─ mode 1 → _switch_to_wager()    (chance 98%, bet 2.5%)
#          └─ mode 2 → _switch_to_profit()   (chance 0.5-0.75%, base จากสูตร)
#
#   CalculateBet()   ← เรียกหลังผลรอบก่อนหน้า
#     ├─ อ่าน PreviousBet / Balance / Win
#     ├─ ชนะ
#     │    ├─ WAGER  → เดิมพันเท่าเดิม; ถ้าถึง wager target → reset + Stop
#     │    └─ PROFIT → สุ่ม chance ใหม่ + กลับไป base; ถ้าครบเป้ากู้ → กลับ WAGER
#     │                (โหมด 2: ถ้ากำไรของ cycle > 0 → เก็บ vault + reset + เล่นต่อ)
#     ├─ แพ้
#     │    ├─ WAGER  → ถ้าขาดทุน ≥ 4% → จำยอดเสีย + เข้า PROFIT
#     │    │             ไม่งั้นเดิมพันเท่าเดิม
#     │    └─ PROFIT → ไม้ถัดไป = ไม้ก่อนหน้า × multiplier
#     │                ถ้าแพ้ครบ N ไม้ → reset base
#     ├─ Stop rules (profit / loss / streak / เงินหมด)
#     └─ log CSV + status ทุก 50 ไม้
#
#
# ── 7.2 ตาราง config ที่เกี่ยวข้อง ───────────────────────────────────────────
#
#   Key                          Default      ความหมาย
#   ───────────────────────────  ───────────  ─────────────────────────────────
#   FUSION_MAIN_MODE             1            1=WAGER+RECOVERY, 2=PROFIT
#   FUSION_WAGER_CHANCE          98.0         Chance ตอนปั่นยอด (%)
#   FUSION_WAGER_BET_PCT         2.5          % ของ balance ที่เดิมพันตอนปั่น
#   FUSION_WAGER_TARGET          100.0        เป้ายอดเทิร์นโอเวอร์
#   FUSION_LOSS_CUT_PCT          4.0          ขาดทุนกี่ % แล้วตัดเข้าโหมดกู้
#   FUSION_RECOVER_PROFIT_PCT    1.0          เป้ากำไรตอนกู้ (ยอดเสีย + N%)
#   FUSION_AUTO_CHANCE           1            สุ่ม chance หรือใช้ค่าคงที่
#   FUSION_CHANCE_MIN/MAX        0.5 / 0.75   ช่วงสุ่ม chance
#   FUSION_RANDOM_ON_WIN/LOSE    1 / 0        สุ่ม chance ใหม่ตอนชนะ/แพ้
#   FUSION_RISK_BONUS_PCT        5.0          โบนัสในสูตร multiplier (%)
#   HE                           1.0          House edge (%)
#   AUTO_CAL_ALLOWED_LOSS        1            คำนวณ N อัตโนมัติ
#   FUSION_ALLOWED_LOSSES        14           N (เมื่อปิด auto)
#   FUSION_RISK_ALPHA            0.001        ความเสี่ยงที่ยอมรับ (0.1%)
#   FUSION_MIN_BET               1e-8         เดิมพันขั้นต่ำ
#   FUSION_STOP_PROFIT           0.2          หยุดเมื่อ ROI ≥ N (0=ปิด)
#   FUSION_STOP_LOSS             0.0          หยุดเมื่อ ROI ≤ -N (0=ปิด)
#   FUSION_STOP_LOSS_STREAK      0            หยุดเมื่อแพ้ติด N ไม้ (0=ปิด)
#
#   หมายเหตุ: ค่าจริงใน config/fusion.env อาจไม่ตรงกับ default ในโค้ด
#             ให้ยึดไฟล์ config เป็นหลัก (SSOT)
#
#
# ── 7.3 ตัวเลขตัวอย่างที่ควรจำ ───────────────────────────────────────────────
#
#   chance 98%   → payout ≈ 1.0102x → ชนะ 1 ครั้งได้กำไร ~1.02% ของไม้
#   chance 2%    → payout ≈ 49.5x
#   chance 0.75% → payout ≈ 132x
#   chance 0.5%  → payout ≈ 198x
#
#   WAGER mode:
#       เดิมพัน 2.5% ของ balance
#       ชนะได้กำไร ≈ 2.5% × 1.02% ≈ 0.0255% ของ balance
#       แพ้เสีย 2.5% ของ balance
#       → ต้องชนะประมาณ 98 ครั้งเพื่อชดเชยแพ้ 1 ครั้ง
#       นี่คือธรรมชาติของ chance สูง: ชนะบ่อยแต่กำไรต่อครั้งน้อยมาก
#       จุดประสงค์จริง ๆ คือ "ปั่นยอด" ไม่ใช่ "ทำกำไร"
#
#   PROFIT mode:
#       ถ้า chance 0.5% และ mul ≈ 1.0056
#       แพ้ 10 ไม้ติด → ไม้ที่ 11 สูงกว่าไม้แรกแค่ ~5.7%
#       เพราะ payout สูงมาก ไม้เดียวที่ชนะก็คืนทุนได้แล้ว
#
#
# ── 7.4 ข้อสังเกตจากการอ่านโค้ด (ไม่ใช่คำสั่งให้แก้) ─────────────────────────
#
#   (1) การ reset ใช้วิธี "เลื่อน baseline" ไม่ได้รีเซ็ตเงินจริง
#       _separate_profit_reset() เก็บกำไรเข้า vault แล้วตั้ง
#           _original_cycle_balance = cur_bal
#       ทำให้ total_pnl = vault + (balance - baseline) ไม่นับกำไรซ้ำ
#       (ถ้าไม่เลื่อน baseline จะนับซ้ำ เพราะ balance จริงแก้ไม่ได้)
#
#       [ข้อควรรู้] ในฟังก์ชันเดียวกัน _cycle_start_balance ถูกตั้งกลับไปที่
#       ยอดเดิม "ก่อน" baseline จะเลื่อน → ในโหมด 2 (PROFIT FOCUS)
#       base bet ของรอบใหม่จึงอิงยอดเก่าไป 1 รอบ
#       (โหมด 1 ไม่กระทบ เพราะ _switch_to_wager() ตั้งยอดใหม่จาก Balance)
#
#       เปรียบเทียบ: fusion_bot.py (simulator) ทำได้จริงคือ
#           balance = original_cycle_balance
#
#   (2) CSV ของรอบที่ "ตัดขาดทุน" อาจบันทึก Mode ผิด
#       เพราะ _switch_to_profit() เปลี่ยน _mode เป็น "PROFIT" ก่อนถึงบรรทัด log
#       แถวนั้นจึงถูกบันทึกเป็น PROFIT ทั้งที่เดิมพันจริงเป็น WAGER
#
#   (3) รอบที่ถึง wager target จะไม่ถูกบันทึก CSV
#       เพราะ return ก่อนถึง _log_csv (แต่รอบที่ถึง profit target ก็ return
#       ก่อน log เช่นกัน)
#
#   (4) _random_chance() สร้าง System.Random ใหม่ทุกครั้ง
#       .NET Random() อาจใช้ seed จาก tick count
#       ถ้าเรียกถี่มาก ๆ ภายในเวลาใกล้กัน อาจได้ค่าเดิมซ้ำ
#       (ในทางปฏิบัติมีความเสี่ยงเล็กน้อย แต่ควรรู้ไว้)
#
#   (5) base bet ไม่ถูก cap ด้วย balance ปัจจุบัน
#       _update_base() คำนวณจาก _cycle_start_balance (ยอดตอนเริ่ม cycle)
#       ถ้าแพ้ต่อเนื่องจนเงินเหลือน้อย base bet อาจใหญ่เกินเงินที่มี
#       การ cap 90% มีเฉพาะไม้ martingale (new_bet) ไม่ใช่ base
#
#   (6) _working_balance ถูก assign แต่ไม่ถูกใช้ตัดสินใจ
#       เป็นตัวแปร "เผื่อไว้" เฉย ๆ
#
#   (7) ตัวแปร _divisor ถูกเก็บไว้แต่ไม่ได้ใช้คำนวณต่อ
#       (มีประโยชน์ตอน debug ดูว่าสูตรให้ค่าอะไร)
#
#   (8) ตัวแปรสภาพแวดล้อมรุ่นเก่า
#       _auto_cal_allowed_loss อ่าน key "AUTO_CAL_ALLOWED_LOSS" ก่อน
#       แล้วค่อย fallback ไป "FUSION_AUTO_CAL_ALLOWED_LOSS"
#       (สังเกตว่าลำดับ fallback ต่างจาก key อื่นที่ขึ้นต้น FUSION_ ก่อน)
#
#   (9) overflow guard ทำงานแบบ "เงียบ"
#       ถ้า mul ใหญ่หรือ N มากจน divisor เป็น infinity
#       _solve_base_bet() จะคืน min_bet แทน (ไม่ error)
#       ผลคือบอทจะเดิมพันขั้นต่ำโดยไม่แจ้งเตือน
#       ถ้าเห็น Next Bet = 0.00000001 ตลอด ให้สงสัยว่ามาถึงจุดนี้
#
#
# ── 7.5 แบบฝึกหัดอ่านโค้ด (ลองตอบเองก่อนดูเฉลย) ─────────────────────────────
#
#   Q1: ทำไม Reset() ต้องมี `global` ยาว ๆ ทั้งที่เป็นฟังก์ชันเดียว?
#       A: เพราะมันเขียนทับตัวแปรระดับไฟล์เกือบทั้งหมด
#          ถ้าไม่ประกาศ Python จะสร้าง local ใหม่ แล้วค่าเดิมไม่เปลี่ยน
#
#   Q2: ทำไม load_dice_env() ต้องวนขยาย ${VAR} ถึง 5 รอบ?
#       A: เผื่อค่าอ้างต่อกันเป็นลูกโซ่ (A→B→C) ต้องค่อย ๆ แทนทีละชั้น
#          ถ้ารอบไหนไม่มีอะไรเปลี่ยนก็ break ก่อนครบ 5
#
#   Q3: ถ้า chance = 0.5% และ payout = 198x
#       ทำไม multiplier ถึงแค่ ~1.0056 ไม่ใช่ 198?
#       A: multiplier ใช้กับ "ขนาดเดิมพัน" ไม่ใช่เงินรางวัล
#          payout 198 หมายถึงเดิมพัน 1 ได้คืน 198 (กำไร 197)
#          ดังนั้นเพิ่มเดิมพันแค่ 0.56% ก็คุ้มกับเงินที่เสียไปแล้ว
#
#   Q4: ทำไมตอนแพ้ในโหมด PROFIT ต้อง cap new_bet ที่ 90% ของ balance?
#       A: กันบอทส่งเดิมพันเกินเงินที่มี (คาสิโนจะ reject)
#          แต่การ cap ทำให้ martingale ขาดตอน → กู้ไม่ครบได้
#
#   Q5: _total_wagered กับ _total_bets ต่างกันอย่างไร?
#       A: _total_bets = จำนวนไม้ (นับครั้ง)
#          _total_wagered = ผลรวมเงินที่เดิมพัน (ใช้เทียบเป้า turnover)
#
#
# ── 7.6 สรุปหนึ่งประโยค ──────────────────────────────────────────────────────
#
#   "บอทจะปั่นยอดด้วย chance สูงจนขาดทุนถึงจุดตัด
#    แล้วสลับไปทบไม้ด้วย chance ต่ำเพื่อกู้ทุน
#    พอกู้ได้ครบเป้าก็เก็บกำไรเข้ากรุแล้วกลับไปปั่นใหม่"
#
#   ทั้งหมดนี้ทำงานผ่าน 2 ฟังก์ชันที่บอทเรียก: Reset() และ CalculateBet()
#
# ==============================================================================
