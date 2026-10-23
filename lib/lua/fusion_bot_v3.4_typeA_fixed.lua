
------------------------------------------------------------
-- 💎 FUSION BOT v3.4 - แบบ A (Fixed Cycle Reset + Clean Variables)
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------
main_mode = 1

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 99
wager_bet_percent       = 2.5
loss_cut_percent        = 4
recover_profit_percent  = 1
wager_target            = 80.51
enable_wager_target     = true

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = false
chance_min    = 0.5
chance_max    = 0.75
chance_fixed  = 39.6
random_on_win      = true
random_on_lose     = false

------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
risk_bonus_percent = 10.0
house_edge         = 1.0
allowed_losses     = 10
constant_divisor   = 0
bethigh            = true
auto_switch        = true
switch_on_win      = false
switch_on_lose     = false

------------------------------------------------------------
-- 🛑 STOP RULES
------------------------------------------------------------
stop_profit_target   = 0.2
stop_loss_limit      = 0
stop_max_loss_streak = 0
min_bet_size         = 0.00000001

------------------------------------------------------------
-- 🌐 GLOBAL VARIABLES
------------------------------------------------------------
mode = "wager"
start_balance = balance
session_start = os.time()
total_wagered = 0
win_count = 0
lose_count = 0
loss_streak = 0
max_loss_streak = 0
base = 0
wager_base_bet = 0
consecutive_losses_in_cycle = 0

working_balance = balance
profit_vault = 0
cycle_start_balance = balance
original_cycle_balance = balance

wager_cycle_start = balance
profit_cycle_start = balance
wager_loss_amount = 0

------------------------------------------------------------
-- 💰 PROFIT SEPARATION SYSTEM (✅ แบบ A: Fixed)
------------------------------------------------------------
function separateProfitAndResetCycle()
    local cycle_profit = balance - original_cycle_balance

    if cycle_profit > 0 then
        profit_vault = profit_vault + cycle_profit

        print(string.format("💰 ═══════════════════════════════════════"))
        print(string.format("✅ Cycle Complete! Profit: %.8f", cycle_profit))
        print(string.format("🏦 Profit Vault: %.8f (Total)", profit_vault))
        print(string.format("🔄 Reset to Original: %.8f", original_cycle_balance))
        print(string.format("💰 ═══════════════════════════════════════"))

        -- ✅ Reset balance กลับไปที่เดิม (จำลอง)
        balance = original_cycle_balance
        working_balance = original_cycle_balance
        cycle_start_balance = original_cycle_balance

        -- ✅ แก้บั๊ก: reset ตัวแปร cycle เก่าที่ค้างไว้
        wager_cycle_start = original_cycle_balance
        profit_cycle_start = original_cycle_balance
        total_wagered = 0
        wager_loss_amount = 0
        consecutive_losses_in_cycle = 0
        loss_streak = 0
        max_loss_streak = 0

        print("♻️ Variables reset — new cycle will start fresh.")

    else
        print(string.format("⚠️  Cycle ended without profit (%.8f)", cycle_profit))
        working_balance = balance
    end
end

------------------------------------------------------------
-- 🏁 REMAINDER OF CODE (unchanged from v3.3)
--  คุณสามารถใช้ส่วนที่เหลือจากสคริปต์เดิมได้เลย
--  ฟังก์ชันหลัก dobet(), switchMode(), showStatus() ฯลฯ ไม่ต้องแก้
------------------------------------------------------------
