
------------------------------------------------------------
-- 💎 FUSION BOT v4.0 - แบบ A (True Loss Detection + Safe Mode Switching + last_balance Fix)
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------
main_mode = 1

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 99
wager_bet_percent       = 4.0
loss_cut_percent        = 4.0
recover_profit_percent  = 1
wager_target            = 50.00
enable_wager_target     = true

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = false
chance_min    = 0.5
chance_max    = 0.75
chance_fixed  = 35
random_on_win      = true
random_on_lose     = false

------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
risk_bonus_percent = 10.0
house_edge         = 1.0
allowed_losses     = 12
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
wager_base_bet = 0
consecutive_losses_in_cycle = 0

working_balance = balance
profit_vault = 0
cycle_start_balance = balance
original_cycle_balance = balance

wager_cycle_start = balance
profit_cycle_start = balance
wager_loss_amount = 0

-- ✅ เพิ่มตัวแปรจำลอง previousbalance
last_balance = balance

------------------------------------------------------------
-- 🔄 MODE SWITCH
------------------------------------------------------------
function switchMode(newMode)
    mode = newMode
    loss_streak = 0
    consecutive_losses_in_cycle = 0

    if mode == "wager" then
        print("🟢 เข้าสู่โหมด WAGERING")
        working_balance = balance
        wager_cycle_start = balance
        wager_loss_amount = 0
        wager_base_bet = wager_cycle_start * (wager_bet_percent / 100)
        chance = wager_chance
        nextbet = wager_base_bet
        print(string.format("   📍 Wager Cycle Start: %.8f", wager_cycle_start))
        print(string.format("   💰 Wager Base Bet: %.8f (%.2f%%)", wager_base_bet, wager_bet_percent))
    else
        print("🟡 เข้าสู่ PROFIT MODE")
        profit_cycle_start = balance
        cycle_start_balance = balance
        print(string.format("   📍 Profit Cycle Start: %.8f", profit_cycle_start))
        print(string.format("   💸 Wager Loss: %.8f (%.2f%%)", wager_loss_amount, wager_loss_amount / original_cycle_balance * 100))
        nextbet = profit_cycle_start * 0.01
        if nextbet < min_bet_size then nextbet = min_bet_size end
    end
end

------------------------------------------------------------
-- 💰 PROFIT SEPARATION SYSTEM
------------------------------------------------------------
function separateProfitAndResetCycle()
    local cycle_profit = balance - original_cycle_balance
    if cycle_profit > 0 then
        profit_vault = profit_vault + cycle_profit
        print("💰 ═══════════════════════════════════════")
        print(string.format("✅ Cycle Complete! Profit: %.8f", cycle_profit))
        print(string.format("🏦 Profit Vault: %.8f (Total)", profit_vault))
        print(string.format("🔄 Reset to Original: %.8f", original_cycle_balance))
        print("💰 ═══════════════════════════════════════")
        balance = original_cycle_balance
        working_balance = original_cycle_balance
        wager_cycle_start = original_cycle_balance
        profit_cycle_start = original_cycle_balance
        total_wagered = 0
        wager_loss_amount = 0
        loss_streak = 0
        max_loss_streak = 0
        resetseed()
        print("♻️ Variables reset — new cycle will start fresh.")
    else
        print(string.format("⚠️  Cycle ended without profit (%.8f)", cycle_profit))
        working_balance = balance
    end
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT v4.0 - แบบ A (True Loss Detection + Safe Mode Switching + last_balance Fix)")
print(string.format("💵 Start Balance: %.8f", balance))
working_balance = balance
cycle_start_balance = balance
original_cycle_balance = balance
switchMode("wager")

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLER
------------------------------------------------------------
function dobet()
    total_wagered = total_wagered + previousbet
    working_balance = balance

    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0
        if mode == "wager" then nextbet = wager_base_bet end
    else
        lose_count = lose_count + 1
        loss_streak = loss_streak + 1
        consecutive_losses_in_cycle = consecutive_losses_in_cycle + 1

        if mode == "wager" then
            -- ✅ ใช้ last_balance (จำลอง previousbalance)
            local prev_balance = last_balance or balance
            local real_loss_value = wager_cycle_start - prev_balance
            local real_loss_percent = (real_loss_value / wager_cycle_start) * 100

            print(string.format("📉 Wager Loss: %.2f%% / %.2f%%", real_loss_percent, loss_cut_percent))

            if main_mode == 1 and real_loss_percent >= loss_cut_percent then
                wager_loss_amount = real_loss_value
                print(string.format("🚨 TRUE LOSS %.2f%% (%.8f) → Switching to Profit Mode", real_loss_percent, wager_loss_amount))
                nextbet = 0  -- ✅ เคลียร์ bet queue ป้องกันยิงต่อ
                switchMode("profit")
            else
                nextbet = wager_base_bet
            end
        else
            nextbet = profit_cycle_start * 0.01
        end
    end

    -- ✅ อัปเดตค่า last_balance หลังจากทุก bet
    last_balance = balance

    -- ✅ หยุดเมื่อถึงเป้า Wager Target
    if enable_wager_target and total_wagered >= wager_target then
        print("🎯 Wager Target reached! Stopping...")
        separateProfitAndResetCycle()
        stop()
        return
    end
end
