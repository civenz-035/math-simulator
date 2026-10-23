------------------------------------------------------------
-- 💎 FUSION BOT v3.2 - FINAL FIX
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
wager_target            = 100             
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
risk_bonus_percent = 5.0       
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

wager_cycle_start = balance
profit_cycle_start = balance

------------------------------------------------------------
-- 🧮 UTILITIES
------------------------------------------------------------
function randomChance()
    local c = (math.random() * (chance_max - chance_min)) + chance_min
    if c <= 0.01 then c = 0.01 end
    if c >= 99 then c = 99 end
    return c
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
    local mul, _ = getAutoMultiplierByChance(chance_ref, bonus_percent, use_he)
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
    
    base = cycle_start_balance / constant_divisor
    
    if base < min_bet_size then
        base = min_bet_size
    end
    
    nextbet = base
    
    print(string.format("📊 Base: %.8f | Cycle Start: %.8f | Div: %.2f", 
        base, cycle_start_balance, constant_divisor))
end

------------------------------------------------------------
-- 💰 PROFIT SEPARATION SYSTEM
------------------------------------------------------------
function separateProfitAndResetCycle()
    local cycle_profit = balance - cycle_start_balance
    
    if cycle_profit > 0 then
        profit_vault = profit_vault + cycle_profit
        balance = cycle_start_balance
        working_balance = cycle_start_balance
        
        print(string.format("💰 ═══════════════════════════════════════"))
        print(string.format("✅ Cycle Complete! Profit: %.8f", cycle_profit))
        print(string.format("🏦 Profit Vault: %.8f (Total)", profit_vault))
        print(string.format("🔄 Reset Balance: %.8f", working_balance))
        print(string.format("💰 ═══════════════════════════════════════"))
    else
        print(string.format("⚠️  Cycle ended without profit (%.8f)", cycle_profit))
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
        print("🟢 เข้าสู่โหมด WAGERING")
        
        wager_cycle_start = working_balance
        wager_base_bet = wager_cycle_start * (wager_bet_percent / 100)
        
        print(string.format("   📍 Wager Cycle Start: %.8f", wager_cycle_start))
        print(string.format("   💰 Wager Base Bet: %.8f (%.2f%%)", wager_base_bet, wager_bet_percent))
        
        chance = wager_chance
        nextbet = wager_base_bet
        
    else
        print("🟡 เข้าสู่ PROFIT MODE")
        
        profit_cycle_start = working_balance
        print(string.format("   📍 Profit Cycle Start: %.8f", profit_cycle_start))
        
        updateBaseAndDivisor()
        
        if auto_chance then
            chance = randomChance()
        else
            chance = chance_fixed
        end
        
        local use_he = (main_mode == 2)
        local mul, payout = getAutoMultiplierByChance(chance, risk_bonus_percent, use_he)
        
        print(string.format("🎯 Chance: %.2f%% | Payout: %.2fx | Mult: %.4fx", 
            chance, payout, mul))
    end
    
    if nextbet < min_bet_size then
        nextbet = min_bet_size
    end
end

------------------------------------------------------------
-- 📊 STATUS DISPLAY
------------------------------------------------------------
function showStatus()
    local runtime = os.time() - session_start
    
    local cycle_profit
    if mode == "wager" then
        cycle_profit = working_balance - wager_cycle_start
    else
        cycle_profit = working_balance - profit_cycle_start
    end
    
    local total_profit = profit_vault + cycle_profit
    
    print(string.format("┌────────────────────────────────────────┐"))
    print(string.format("⏱️  Runtime: %ds | Strategy: %s | Mode: %s", 
        runtime, 
        (main_mode == 1) and "WAGER FOCUS" or "PROFIT FOCUS",
        mode:upper()))
    print(string.format("💰 Working Balance: %.8f", working_balance))
    print(string.format("💎 Profit Vault: %.8f", profit_vault))
    print(string.format("📊 Cycle Profit: %.8f", cycle_profit))
    print(string.format("🎁 Total Profit: %.8f", total_profit))
    print(string.format("🎲 Next Bet: %.8f | Chance: %.2f%%", nextbet, chance))
    print(string.format("🎯 W/L: %d/%d | Streak: %d (Max: %d)", 
        win_count, lose_count, loss_streak, max_loss_streak))
    
    if main_mode == 1 then
        print(string.format("📈 Wagered: %.4f / %.2f", total_wagered, wager_target))
        
        if mode == "wager" then
            local wager_loss = wager_cycle_start - working_balance
            local wager_loss_pct = (wager_loss / wager_cycle_start) * 100
            print(string.format("📉 Wager Loss: %.2f%% / %.2f%%", 
                wager_loss_pct, loss_cut_percent))
        else
            local total_cycle_profit = working_balance - cycle_start_balance
            local total_profit_pct = (total_cycle_profit / cycle_start_balance) * 100
            local recovery_gain = working_balance - profit_cycle_start
            local recovery_pct = (recovery_gain / profit_cycle_start) * 100
            print(string.format("📈 Recovery: %.2f%% | Total: %.2f%% / %.2f%%", 
                recovery_pct, total_profit_pct, recover_profit_percent))
        end
    end
    
    print(string.format("└────────────────────────────────────────┘"))
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT v3.2 - FINAL FIX")
print(string.format("💵 Start Balance: %.8f", balance))

working_balance = balance
cycle_start_balance = balance

if main_mode == 1 then
    print("🎯 Strategy: WAGER FOCUS + Profit Separation")
    print(string.format("   Loss Cut: %.2f%% | Recover: %.2f%%", loss_cut_percent, recover_profit_percent))
    switchMode("wager")
elseif main_mode == 2 then
    print("🎯 Strategy: PROFIT FOCUS")
    print(string.format("🏠 House Edge: %.2f%%", house_edge))
    switchMode("profit")
end

print(string.format("🎲 First Bet: %.8f | Chance: %.2f%%", nextbet, chance))

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLERS
------------------------------------------------------------

function dobet()
    
    total_wagered = total_wagered + previousbet
    working_balance = balance
    
    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0
        
        if mode == "wager" then
            nextbet = wager_base_bet
            
            if main_mode == 1 and enable_wager_target and total_wagered >= wager_target then
                print("🎯 ถึงเป้า Wager Target!")
                separateProfitAndResetCycle()
                showStatus()
                stop()
                return
            end
            
        else
            if auto_chance and random_on_win then
                chance = randomChance()
            else
                chance = chance_fixed
            end
            
            nextbet = base
        end
        
        if auto_switch and switch_on_win then
            bethigh = not bethigh
        end
        
    else
        lose_count = lose_count + 1
        loss_streak = loss_streak + 1
        consecutive_losses_in_cycle = consecutive_losses_in_cycle + 1
        
        if loss_streak > max_loss_streak then
            max_loss_streak = loss_streak
        end
        
        if mode == "wager" then
            local cycle_loss = wager_cycle_start - working_balance
            local loss_pct = (cycle_loss / wager_cycle_start) * 100
            
            print(string.format("   📉 Wager Loss: %.2f%% / %.2f%%", loss_pct, loss_cut_percent))
            
            if main_mode == 1 and loss_pct >= loss_cut_percent then
                print(string.format("⚠️  ขาดทุน %.2f%% → สลับไป Profit Mode", loss_pct))
                switchMode("profit")
            else
                nextbet = wager_base_bet
            end
            
        else
            if auto_chance and random_on_lose then
                chance = randomChance()
            end
            
            local use_he = (main_mode == 2)
            local multiplier, payout = getAutoMultiplierByChance(chance, risk_bonus_percent, use_he)
            
            nextbet = nextbet * multiplier
            
            print(string.format("📈 Loss #%d | Next: %.8f (x%.4f, pay %.2fx)", 
                consecutive_losses_in_cycle, nextbet, multiplier, payout))
            
            if nextbet > working_balance then
                print("⚠️  Next bet > Balance → 90%")
                nextbet = working_balance * 0.9
            end
            
            if consecutive_losses_in_cycle >= allowed_losses then
                print(string.format("⛔ แพ้ครบ %d ไม้ → Reset", allowed_losses))
                updateBaseAndDivisor()
                consecutive_losses_in_cycle = 0
            end
            
            if main_mode == 1 then
                local total_cycle_profit = working_balance - cycle_start_balance
                local total_profit_pct = (total_cycle_profit / cycle_start_balance) * 100
                
                local recovery_gain = working_balance - profit_cycle_start
                local recovery_pct = (recovery_gain / profit_cycle_start) * 100
                
                print(string.format("   📈 Recovery: %.2f%% | Total: %.2f%% (need: %.2f%%)", 
                    recovery_pct, total_profit_pct, recover_profit_percent))
                
                if total_profit_pct >= recover_profit_percent then
                    print(string.format("✅ ฟื้นทุนครบ %.2f%% → กลับ Wager Mode", total_profit_pct))
                    
                    separateProfitAndResetCycle()
                    cycle_start_balance = balance
                    switchMode("wager")
                end
            end
        end
        
        if auto_switch and switch_on_lose then
            bethigh = not bethigh
        end
    end
    
    if nextbet < min_bet_size then
        nextbet = min_bet_size
    end
    
    local total_profit_all = profit_vault + (working_balance - cycle_start_balance)
    local profit_ratio = total_profit_all / start_balance
    
    if stop_profit_target > 0 and profit_ratio >= stop_profit_target then
        print(string.format("🎉 ถึงเป้ากำไร %.2f%%!", profit_ratio * 100))
        separateProfitAndResetCycle()
        showStatus()
        stop()
        return
    end
    
    if stop_loss_limit > 0 and profit_ratio <= -stop_loss_limit then
        print(string.format("🚨 ขาดทุนเกินลิมิต %.2f%%!", math.abs(profit_ratio) * 100))
        showStatus()
        stop()
        return
    end
    
    if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak then
        print(string.format("🚨 แพ้ติดต่อกัน %d ไม้!", loss_streak))
        showStatus()
        stop()
        return
    end
    
    if working_balance < min_bet_size * 2 then
        print("🚨 Working Balance ต่ำเกินไป!")
        showStatus()
        stop()
        return
    end
    
    if bets % 50 == 0 then
        showStatus()
    end
end

------------------------------------------------------------
-- 🏁 END OF SCRIPT
------------------------------------------------------------