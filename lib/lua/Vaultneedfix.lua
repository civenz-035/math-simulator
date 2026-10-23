
------------------------------------------------------------
-- 💎 FUSION BOT v2.5.1 - SAFE MARTINGALE EDITION
-- 🛡️ Mode 1: Basic Martingale - ปลอดภัยสุด
-- 📝 ชื่อไฟล์: FusionBot_v2_5_Safe.lua
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------

main_mode = 2   -- 1 = Wager Focus | 2 = Profit Focus

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 99               
wager_bet_percent       = 2.5              
loss_cut_percent        = 4                
recover_profit_percent  = 2.5                
wager_target            = 100             
enable_wager_target     = true             

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = true

chance_min    = 0.5       
chance_max    = 0.75      
chance_fixed  = 0.5     

random_on_win      = true     
random_on_lose     = false    

------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
multiplier_mode     = 1
bonus      	    = 0.05  
house_edge          = 1.0    
allowed_losses      = 500   
constant_divisor    = 0         
bethigh             = true      
auto_switch         = true      
switch_on_win       = true
switch_on_lose      = false

------------------------------------------------------------
-- 🏦 VAULT SYSTEM CONFIG
------------------------------------------------------------
vault_mode1             = 0
vault_trigger_mode1     = 1.05      
vault_fraction_mode1    = 0.5      

vault_mode2             = 0
vault_trigger_mode2     = 1.10      
vault_fraction_mode2    = 0.50

mode1_start_balance     = 0
mode2_start_balance     = 0

------------------------------------------------------------
-- 🛑 STOP RULES
------------------------------------------------------------
stop_profit_target   = 0.2      
stop_loss_limit      = 0.5      
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
consecutive_losses_in_cycle = 0

-- ✅ เพิ่ม: ต้องมีการกำหนด chance และ nextbet ก่อน
chance = 50  -- ค่าเริ่มต้นชั่วคราว
nextbet = 0.00000001  -- ค่าเริ่มต้นชั่วคราว

------------------------------------------------------------
-- 🧮 UTILITIES
------------------------------------------------------------
function randomChance()
    local c = (math.random() * (chance_max - chance_min)) + chance_min
    if c <= 0.01 then c = 0.01 end
    if c >= 99 then c = 99 end
    return c
end

function getAutoMultiplierByChance(c, use_house_edge)
    local chance_decimal = c / 100
    
    if chance_decimal <= 0.0001 then chance_decimal = 0.0001 end
    if chance_decimal >= 0.9999 then chance_decimal = 0.9999 end
    
    local payout
    if use_house_edge and house_edge > 0 then
        payout = (1 - (house_edge / 100)) / chance_decimal
    else
        payout = 1 / chance_decimal
    end
    
    local multiplier = 1+((1+bonus) / (payout - 1))
    
    if multiplier < 1.001 then
        multiplier = 1.001
    end
    
    return multiplier, payout
end

function getConstantDivisor(chance_ref, losses, use_he)
    local mul, _ = getAutoMultiplierByChance(chance_ref, use_he)
    local sum = 0
    for i = 0, losses - 1 do
        sum = sum + (mul ^ i)
    end
    return sum
end

function updateBaseAndDivisor()
    local refChance = auto_chance and chance_min or chance_fixed
    local use_he = (main_mode == 2)
    
    constant_divisor = getConstantDivisor(refChance, allowed_losses, use_he)
    base = balance / constant_divisor
    
    if base < min_bet_size then
        base = min_bet_size
    end
    
    nextbet = base
    
    print(string.format("📊 Base: %.8f | Divisor: %.2f%s", 
        base, constant_divisor, use_he and " (HE)" or ""))
end

------------------------------------------------------------
-- 🏦 VAULT SYSTEM
------------------------------------------------------------
function checkVault()
    local vault_triggered = false
    
    if main_mode == 1 then
        local profit = balance - mode1_start_balance
        
        if balance >= mode1_start_balance * vault_trigger_mode1 and profit > 0 then
            local dep = profit * vault_fraction_mode1
            
            if dep > profit then
                dep = profit * 0.99
            end
            
            vault_mode1 = vault_mode1 + dep
            balance = balance - dep
            
            print(string.format("🏦 Vault1 +%.8f | Total %.8f | Balance %.8f", 
                dep, vault_mode1, balance))
            
            vault_triggered = true
        end
    
    elseif main_mode == 2 then
        local profit = balance - mode2_start_balance
        
        if balance >= mode2_start_balance * vault_trigger_mode2 and profit > 0 then
            local dep = profit * vault_fraction_mode2
            
            if dep > profit then
                dep = profit * 0.99
            end
            
            vault_mode2 = vault_mode2 + dep
            balance = balance - dep
            
            print(string.format("🏦 Vault2 +%.8f | Total %.8f | Balance %.8f", 
                dep, vault_mode2, balance))
            
            vault_triggered = true
        end
    end
    
    if vault_triggered and mode == "profit" then
        updateBaseAndDivisor()
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
        
        if mode1_start_balance == 0 then
            mode1_start_balance = balance
        end
        
        chance = wager_chance
        nextbet = balance * (wager_bet_percent / 100)
        
    else
        print("🟡 เข้าสู่ PROFIT MODE")
        
        if mode2_start_balance == 0 then
            mode2_start_balance = balance
        end
        
        updateBaseAndDivisor()
        
        if auto_chance then
            chance = randomChance()
        else
            chance = chance_fixed
        end
        
        local use_he = (main_mode == 2)
        local mul, payout = getAutoMultiplierByChance(chance, use_he)
        
        print(string.format("🎯 Chance: %.2f%% | Payout: %.2fx%s", 
            chance, payout, use_he and " (HE)" or ""))
        print(string.format("🛡️ Multiplier: %.4fx (Mode 1: Safe)", mul))
    end
    
    if nextbet < min_bet_size then
        nextbet = min_bet_size
    end
    
    -- ✅ ตรวจสอบค่าก่อน return
    if chance <= 0 or chance > 100 then
        chance = 50
        print("⚠️ Chance ผิดปกติ! รีเซ็ตเป็น 50%")
    end
    
    if nextbet <= 0 then
        nextbet = min_bet_size
        print("⚠️ Nextbet ผิดปกติ! รีเซ็ตเป็น min_bet_size")
    end
end

------------------------------------------------------------
-- 📊 STATUS DISPLAY
------------------------------------------------------------
function showStatus()
    local runtime = os.time() - session_start
    local profit = balance - start_balance
    local profit_pct = (profit / start_balance) * 100
    
    local vault_display = (main_mode == 1) and vault_mode1 or vault_mode2
    local vault_label = (main_mode == 1) and "Vault1" or "Vault2"
    
    local current_start = (main_mode == 1) and mode1_start_balance or mode2_start_balance
    if current_start == 0 then current_start = start_balance end
    
    local real_profit = balance - current_start
    local total_profit = real_profit + vault_display
    
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(string.format("⏱️  Runtime: %ds | Strategy: %s | Mode: %s", 
        runtime, 
        (main_mode == 1) and "WAGER FOCUS" or "PROFIT FOCUS",
        mode:upper()))
    print(string.format("💰 Balance: %.8f (%.2f%%)", balance, profit_pct))
    print(string.format("📊 Real Profit: %.8f | Vault: %.8f | Total: %.8f", 
        real_profit, vault_display, total_profit))
    print(string.format("🎲 Next Bet: %.8f | Chance: %.2f%%", nextbet, chance))
    print(string.format("🎯 W/L: %d/%d | Streak: %d (Max: %d)", 
        win_count, lose_count, loss_streak, max_loss_streak))
    
    if main_mode == 1 then
        print(string.format("📈 Wagered: %.4f / %.2f", total_wagered, wager_target))
    end
    
    print(string.format("🏦 %s: %.8f", vault_label, vault_display))
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT v2.5.1 - Starting...")
print(string.format("💵 Start Balance: %.8f", balance))

if main_mode == 1 then
    print("🎯 Strategy: WAGER FOCUS")
    print("🛡️ Multiplier: Mode 1 (Safe Martingale)")
    switchMode("wager")
elseif main_mode == 2 then
    print("🎯 Strategy: PROFIT FOCUS")
    print(string.format("🏠 House Edge: %.2f%%", house_edge))
    print("🛡️ Multiplier: Mode 1 (Safe Martingale)")
    switchMode("profit")
else
    print("❌ ERROR: main_mode ต้องเป็น 1 หรือ 2")
    stop()
end

print(string.format("✅ Initialized | Bet: %.8f | Chance: %.2f%%", nextbet, chance))

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLERS
------------------------------------------------------------

function dobet()
    
    total_wagered = total_wagered + previousbet
    
    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0
        
        if mode == "wager" then
            nextbet = balance * (wager_bet_percent / 100)
            
            if main_mode == 1 and enable_wager_target and total_wagered >= wager_target then
                print("🎯 ถึงเป้า Wager Target!")
                showStatus()
                stop()
                return
            end
            
            checkVault()
            
        else
            if auto_chance and random_on_win then
                chance = randomChance()
                
                local use_he = (main_mode == 2)
                local mul, payout = getAutoMultiplierByChance(chance, use_he)
                
                print(string.format("🔄 New: %.2f%% | Payout: %.2fx | Mul: %.4fx", 
                    chance, payout, mul))
            end
            
            nextbet = base
            checkVault()
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
            local loss_from_start = start_balance - balance
            local loss_pct = (loss_from_start / start_balance) * 100
            
            if main_mode == 1 and loss_pct >= loss_cut_percent then
                print(string.format("⚠️ ขาดทุน %.2f%% → สลับไป Profit Mode", loss_pct))
                switchMode("profit")
            else
                nextbet = balance * (wager_bet_percent / 100)
            end
            
        else
            if auto_chance and random_on_lose then
                chance = randomChance()
                
                local use_he = (main_mode == 2)
                local mul, payout = getAutoMultiplierByChance(chance, use_he)
                
                print(string.format("🔄 New: %.2f%% | Payout: %.2fx | Mul: %.4fx", 
                    chance, payout, mul))
            end
            
            local use_he = (main_mode == 2)
            local multiplier, payout = getAutoMultiplierByChance(chance, use_he)
            
            local prev_bet = nextbet
            nextbet = nextbet * multiplier
            
            print(string.format("📈 Loss #%d | %.8f → %.8f (×%.4fx)", 
                consecutive_losses_in_cycle, prev_bet, nextbet, multiplier))
            
            if nextbet > balance then
                print("⚠️ Next bet > Balance → ปรับเป็น 90%")
                nextbet = balance * 0.9
            end
            
            if consecutive_losses_in_cycle >= allowed_losses then
                print(string.format("⛔ แพ้ครบ %d ไม้ → Reset", allowed_losses))
                updateBaseAndDivisor()
                consecutive_losses_in_cycle = 0
            end
            
            if main_mode == 1 then
                local profit_from_start = balance - start_balance
                local profit_pct = (profit_from_start / start_balance) * 100
                
                if profit_pct >= recover_profit_percent then
                    print(string.format("✅ ฟื้นทุนแล้ว %.2f%%", profit_pct))
                    switchMode("wager")
                end
            end
        end
        
        if auto_switch and switch_on_lose then
            bethigh = not bethigh
        end
    end
    
    -- ✅ ป้องกัน nextbet และ chance ผิดปกติ
    if nextbet < min_bet_size then
        nextbet = min_bet_size
    end
    
    if nextbet > balance then
        nextbet = balance * 0.95
    end
    
    if chance <= 0 or chance > 100 then
        print("⚠️ Chance error! Reset to safe value")
        chance = (main_mode == 1) and wager_chance or chance_fixed
    end
    
    -- 🛑 STOP CONDITIONS
    local current_profit = balance - start_balance
    local profit_ratio = current_profit / start_balance
    
    if stop_profit_target > 0 and profit_ratio >= stop_profit_target then
        print(string.format("🎉 ถึงเป้ากำไร %.2f%%!", profit_ratio * 100))
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
    
    if balance < min_bet_size * 2 then
        print("🚨 Balance ต่ำเกินไป!")
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