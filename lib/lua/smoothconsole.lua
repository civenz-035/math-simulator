------------------------------------------------------------
-- 💎FinalfixByAntigravity  ( console_fixed_4 ) ✅ SMOOTH VERSION
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------
main_mode = 1

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 97
wager_bet_percent       = 3
loss_cut_percent        = 4
recover_profit_percent  = 1
wager_target            = 1
enable_wager_target     = true

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = true
chance_min    = 0.4
chance_max    = 0.49
chance_fixed  = 0.5
random_on_win      = true
random_on_lose     = false

use_fix_basebet      = false
fix_basebet_amount   = 0.00185251005


------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
use_fixed_multiplier = true
fixed_multiplier     = 1.006
risk_bonus_percent   = 10.0
house_edge           = 1.0
allowed_losses       = 700
constant_divisor     = 0
bethigh              = true
auto_switch          = true
switch_on_win        = false
switch_on_lose       = false

------------------------------------------------------------
-- 🛑 STOP RULES
------------------------------------------------------------
stop_profit_target   = 0.5
stop_loss_limit      = 0
stop_max_loss_streak = 700
min_bet_size         = 0.00000001
dashboard_update_every = 10 -- ✅ เปลี่ยนจาก 1 → 10 (ลดการสั่น 90%)

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
cycle_count = 1
last_action = "INIT"
last_result = "-"

-- ✅ ตัวแปรใหม่สำหรับ Buffer System
result_buffer = {}
buffer_size = 5 -- เก็บผลล่าสุด 5 ไม้

------------------------------------------------------------
-- 🧮 UTILITIES
------------------------------------------------------------
function randomChance()
    local c = (math.random() * (chance_max - chance_min)) + chance_min
    if c <= 0.01 then c = 0.01 end
    if c >= 99 then c = 99 end
    return c
end

function randomBethigh()
    local result = math.random() >= 0.5
    bethigh = result
    return result
end

function getAutoMultiplierByChance(c, bonus, use_house_edge)
    local chance_decimal = c / 100
    if chance_decimal <= 0.0001 then chance_decimal = 0.0001 end
    if chance_decimal >= 0.9999 then chance_decimal = 0.9999 end
    
    local payout
    if use_house_edge and house_edge > 0 then
        payout = (1 - (house_edge / 100)) / chance_decimal
    else
        payout = 0.99 / chance_decimal
    end
    
    local multiplier = 1 + ((1 + (bonus / 100)) / (payout - 1))
    return multiplier, payout
end

function getConstantDivisor(chance_ref, bonus_percent, losses, use_he)
    local mul
    if use_fixed_multiplier then
        mul = fixed_multiplier
    else
        mul, _ = getAutoMultiplierByChance(chance_ref, bonus_percent, use_he)
    end
    
    local sum = 0
    for i = 0, losses - 1 do
        sum = sum + (mul ^ i)
    end
    return sum
end

function updateBaseAndDivisor()
    local refChance = auto_chance and chance_min or chance_fixed
    local use_he = (main_mode == 2)
    constant_divisor = getConstantDivisor(refChance, risk_bonus_percent, allowed_losses, use_he)
    
    if use_fix_basebet then
        base = fix_basebet_amount
    else
        base = cycle_start_balance / constant_divisor
    end
    
    if base < min_bet_size then
        base = min_bet_size
    end
    
    nextbet = base
end

------------------------------------------------------------
-- 💰 PROFIT SEPARATION SYSTEM
------------------------------------------------------------
function separateProfitAndResetCycle()
    local current_working_balance = balance - profit_vault
    local surplus = current_working_balance - original_cycle_balance

    if surplus > 0 then
        profit_vault = profit_vault + surplus
        working_balance = original_cycle_balance 
        
        cycle_start_balance = original_cycle_balance
        wager_cycle_start = original_cycle_balance
        profit_cycle_start = original_cycle_balance

        wager_loss_amount = 0
        consecutive_losses_in_cycle = 0
        loss_streak = 0
        max_loss_streak = 0
        
        cycle_count = cycle_count + 1
    end
end

------------------------------------------------------------
-- 🔄 MODE SWITCH
------------------------------------------------------------
function switchMode(newMode)
    mode = newMode
    loss_streak = 0
    consecutive_losses_in_cycle = 0
    
    if mode == "wager" then
        chance = wager_chance
        wager_base_bet = original_cycle_balance * (wager_bet_percent / 100)
        nextbet = wager_base_bet
        wager_cycle_start = working_balance
    else
        if auto_chance then chance = randomChance() else chance = chance_fixed end
        profit_cycle_start = working_balance
        updateBaseAndDivisor()
    end
end

------------------------------------------------------------
-- 📊 DASHBOARD (✅ CLEAN OUTPUT)
------------------------------------------------------------
function showStatus()
    local runtime = os.time() - session_start
    local cycle_profit = working_balance - cycle_start_balance
    local total_profit = profit_vault + (working_balance - original_cycle_balance)
    local vault_pct = (profit_vault / start_balance) * 100
    local bethigh_str = bethigh and "High" or "Low"
    
    local mode_info
    if mode == "wager" then
        mode_info = string.format("Bet: %.2f%%", wager_bet_percent)
    else
        mode_info = string.format("L#%d/%d", consecutive_losses_in_cycle, allowed_losses)
    end
    
    -- ✅ แสดง Buffer (5 ไม้ล่าสุด) ถ้ามีข้อมูล
    if #result_buffer > 0 then
        print("╔══════════════ RECENT BETS ═══════════════╗")
        for i = 1, math.min(#result_buffer, buffer_size) do
            print(result_buffer[i])
        end
        print("╚═══════════════════════════════════════════╝")
    end
    
    -- ✅ Dashboard หลัก
    print("--------------------------------------------------")
    print(string.format("⏱️ %ds | %s | %s | Cyc:%d | %s",
        runtime, (main_mode == 1) and "WAGER" or "PROFIT", mode:upper(), cycle_count, last_result))
    print(string.format("💰 Work: %.8f | 🏦 Vault: %.8f (%.2f%%)",
        working_balance, profit_vault, vault_pct))
    print(string.format("📊 Cycle: %+.8f | 🎁 Total: %+.8f",
        cycle_profit, total_profit))
    print(string.format("🎲 Bet: %.8f | Ch: %.2f%% | %s",
        nextbet, chance, bethigh_str))
    print(string.format("🎯 W:%d L:%d | Streak:%d (Max:%d)",
        win_count, lose_count, loss_streak, max_loss_streak))
    print(string.format("📈 Wager: %.4f/%.2f | %s",
        total_wagered, wager_target, mode_info))
    print(string.format("🔄 %s", last_action))
    print("--------------------------------------------------")
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT v3.4 - SMOOTH CONSOLE VERSION")
print(string.format("💵 Start Balance: %.8f", balance))
working_balance = balance
cycle_start_balance = balance
original_cycle_balance = balance

if main_mode == 1 then
    print("🎯 Strategy: WAGER FOCUS + Profit Separation (TYPE A)")
    print(string.format("   Loss Cut: %.2f%% | Recover: Loss + %.2f%%", loss_cut_percent, recover_profit_percent))
    switchMode("wager")
elseif main_mode == 2 then
    print("🎯 Strategy: PROFIT FOCUS")
    print(string.format("🏠 House Edge: %.2f%%", house_edge))
    switchMode("profit")
end

print(string.format("🎲 First Bet: %.8f | Chance: %.2f%%", nextbet, chance))

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLER
------------------------------------------------------------
function dobet()
    -- ✅ สร้างข้อความผลการเดิมพัน
    local dir_str = bethigh and "High" or "Low "
    local payout_amount = previousbet * (99 / chance)
    local result_str = ""
    
    if win then
        result_str = string.format("BET %s | %.2f%% | roll %6.2f |   Win   ✅  +%.8f", 
            dir_str, chance, lastBet.Roll, payout_amount - previousbet)
    else
        local wrong_side = false
        if bethigh then
            wrong_side = lastBet.Roll >= (100 - chance)
        else
            wrong_side = lastBet.Roll < chance
        end
        
        if wrong_side then
            result_str = string.format("BET %s | %.2f%% | roll %6.2f | WrongSide ☠️  -%.8f", 
                dir_str, chance, lastBet.Roll, previousbet)
        else
            result_str = string.format("BET %s | %.2f%% | roll %6.2f |  Lose   🚫  -%.8f", 
                dir_str, chance, lastBet.Roll, previousbet)
        end
    end
    
    -- ✅ เก็บผลล่าสุดใน Buffer (แทนการ print ทันที)
    table.insert(result_buffer, 1, result_str) -- ใส่ด้านหน้าสุด
    if #result_buffer > buffer_size then
        table.remove(result_buffer) -- ลบตัวเก่าสุดออก
    end
    
    total_wagered = total_wagered + previousbet
    
    if main_mode == 2 then
        local current_excess = balance - profit_vault - start_balance
        if current_excess > 0 then
            profit_vault = profit_vault + current_excess
        end
    end

    working_balance = balance - profit_vault
    
    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0
        last_result = "WIN"
        if mode == "wager" then
            last_action = "WIN → Base Bet"
            nextbet = wager_base_bet
            if main_mode == 1 and enable_wager_target and total_wagered >= wager_target then
            end
        else
            randomBethigh()
            last_action = "WIN → Random Bethigh"
            if auto_chance and random_on_win then chance = randomChance() end
            nextbet = base
        end
    else
        lose_count = lose_count + 1
        loss_streak = loss_streak + 1
        last_result = "LOSE"
        consecutive_losses_in_cycle = consecutive_losses_in_cycle + 1
        if loss_streak > max_loss_streak then max_loss_streak = loss_streak end
        if mode == "wager" then
            if main_mode == 1 then
                randomBethigh()
                last_action = "LOSE → Random Bethigh"
            else
                last_action = "LOSE"
            end
            local cycle_loss = wager_cycle_start - working_balance
            local loss_pct = (cycle_loss / original_cycle_balance) * 100
            if main_mode == 1 and loss_pct >= loss_cut_percent then
                wager_loss_amount = cycle_loss
                last_action = string.format("LOSE %.2f%% → PROFIT MODE", loss_pct)
                switchMode("profit")
            else nextbet = wager_base_bet end
        else
            if auto_chance and random_on_lose then chance = randomChance() end
            
            local multiplier, payout
            if use_fixed_multiplier then
                multiplier = fixed_multiplier
                payout = 0
            else
                local use_he = (main_mode == 2)
                multiplier, payout = getAutoMultiplierByChance(chance, risk_bonus_percent, use_he)
            end
            
            nextbet = nextbet * multiplier
            last_action = string.format("LOSE #%d → x%.4f", consecutive_losses_in_cycle, multiplier)
            if nextbet > working_balance then nextbet = working_balance * 0.9 end
            if consecutive_losses_in_cycle >= allowed_losses then
                updateBaseAndDivisor()
                consecutive_losses_in_cycle = 0
            end
            if main_mode == 1 then
                local need_recover_amount = wager_loss_amount + (original_cycle_balance * recover_profit_percent / 100)
                local current_gain = working_balance - profit_cycle_start
                if current_gain >= need_recover_amount then
                    separateProfitAndResetCycle()
                    switchMode("wager")
                end
            end
        end
    end

    if nextbet < min_bet_size then nextbet = min_bet_size end
    
    if enable_wager_target and total_wagered >= wager_target then
        separateProfitAndResetCycle()
        showStatus()
        stop()
        return
    end
    local total_profit_all = profit_vault + (working_balance - original_cycle_balance)
    local profit_ratio = total_profit_all / start_balance
    if stop_profit_target > 0 and profit_ratio >= stop_profit_target then
        separateProfitAndResetCycle()
        showStatus()
        stop()
        return
    end
    if stop_loss_limit > 0 and profit_ratio <= -stop_loss_limit then
        showStatus()
        stop()
        return
    end
    if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak then
        showStatus()
        stop()
        return
    end
    if working_balance < min_bet_size * 2 then
        showStatus()
        stop()
        return
    end
    
    -- ✅ แสดง Dashboard ตามช่วงที่กำหนด + ทุกครั้งที่มี Event สำคัญ
    if bets % dashboard_update_every == 0 then 
        showStatus() 
    end
end
