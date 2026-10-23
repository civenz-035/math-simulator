------------------------------------------------------------
-- 💎 FUSION BOT – SMART MARTINGALE CLEAN ADAPTIVE EDITION
-- 🔧 DiceBot Compatible Version (Production v2.2)
-- 🎯 แบบที่ 1: Wager Focus | แบบที่ 2: Profit Focus
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------

main_mode = 2   -- 1 = Wager Focus (สลับโหมด + ใช้ Vault1)
                -- 2 = Profit Focus (ไม่สลับ + ใช้ Vault2)

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG (ใช้เฉพาะ main_mode = 1)
------------------------------------------------------------
wager_chance            = 99               
wager_bet_percent       = 2.5              
loss_cut_percent        = 4                -- % ขาดทุนที่จะสลับไป profit mode
recover_profit_percent  = 1                -- % กำไรที่ต้องการก่อนกลับ wager
wager_target            = 1000             
enable_wager_target     = true             

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = true   

chance_min    = 0.005      
chance_max    = 0.0075      
chance_fixed  = 49.95     

random_on_win      = true     
random_on_lose     = false    

------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
risk_bonus_percent = 1.0       
allowed_losses     = 600         
constant_divisor   = 0         
bethigh            = true      
auto_switch        = true      
switch_on_win      = true
switch_on_lose     = false

------------------------------------------------------------
-- 🏦 VAULT SYSTEM CONFIG
------------------------------------------------------------
-- Vault Mode 1: สำหรับ main_mode = 1 (Wager Focus)
vault_mode1             = 0
vault_trigger_mode1     = 1.05      
vault_fraction_mode1    = 0.25      

-- Vault Mode 2: สำหรับ main_mode = 2 (Profit Focus)
vault_mode2             = 0
vault_trigger_mode2     = 1.10      
vault_fraction_mode2    = 0.50      

------------------------------------------------------------
-- 🛑 STOP RULES
------------------------------------------------------------
stop_profit_target   = 2      
stop_loss_limit      = 0.0     
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

------------------------------------------------------------
-- 🧮 UTILITIES
------------------------------------------------------------
function randomChance()
    local c = (math.random() * (chance_max - chance_min)) + chance_min
    if c <= 0.01 then c = 0.01 end
    if c >= 0.99 then c = 0.99 end
    return c
end

function getAutoMultiplierByChance(c, bonus)
    local chance_decimal = (c > 1) and (c / 100) or c
    if chance_decimal <= 0.0001 or chance_decimal >= 0.9999 then
        return 1.0
    end
    return 1 + ((1 + (bonus / 100)) / ((1 / chance_decimal) - 1))
end

function getConstantDivisor(chance_ref, bonus_percent, losses)
    local mul = getAutoMultiplierByChance(chance_ref, bonus_percent)
    local sum = 0
    for i = 0, losses - 1 do
        sum = sum + (mul ^ i)
    end
    return sum
end

function updateBaseAndDivisor()
    local refChance = auto_chance and chance_min or (chance_fixed / 100)
    constant_divisor = getConstantDivisor(refChance, risk_bonus_percent, allowed_losses)
    base = balance / constant_divisor
    
    if base < min_bet_size then
        base = min_bet_size
    end
    
    nextbet = base
end

------------------------------------------------------------
-- 🏦 VAULT SYSTEM
------------------------------------------------------------
function checkVault()
    local vault_triggered = false
    
    -- ✅ แบบที่ 1: Wager Focus → ใช้ Vault Mode 1
    if main_mode == 1 then
        if balance >= start_balance * vault_trigger_mode1 then
            local profit = balance - start_balance
            local dep = profit * vault_fraction_mode1
            vault_mode1 = vault_mode1 + dep
            balance = balance - dep
            print(string.format("🏦 Vault1 +%.8f | Total %.8f | Balance %.8f",
                dep, vault_mode1, balance))
            start_balance = balance
            vault_triggered = true
        end
    
    -- ✅ แบบที่ 2: Profit Focus → ใช้ Vault Mode 2
    elseif main_mode == 2 then
        if balance >= start_balance * vault_trigger_mode2 then
            local profit = balance - start_balance
            local dep = profit * vault_fraction_mode2
            vault_mode2 = vault_mode2 + dep
            balance = balance - dep
            print(string.format("🏦 Vault2 +%.8f | Total %.8f | Balance %.8f",
                dep, vault_mode2, balance))
            start_balance = balance
            vault_triggered = true
        end
    end
    
    -- คำนวณ base ใหม่หลัง vault (สำหรับ profit mode)
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
        chance = wager_chance
        nextbet = balance * (wager_bet_percent / 100)
    else
        print("🟡 เข้าสู่ PROFIT MODE")
        updateBaseAndDivisor()
        
        if auto_chance then
            chance = randomChance() * 100
        else
            chance = chance_fixed
        end
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
    local profit = balance - start_balance
    local profit_pct = (profit / start_balance) * 100
    
    -- แสดง vault ที่เกี่ยวข้อง
    local vault_display = (main_mode == 1) and vault_mode1 or vault_mode2
    local vault_label = (main_mode == 1) and "Vault1" or "Vault2"
    
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(string.format("⏱️  Runtime: %ds | Strategy: %s | Mode: %s", 
        runtime, 
        (main_mode == 1) and "WAGER FOCUS" or "PROFIT FOCUS",
        mode:upper()))
    print(string.format("💰 Balance: %.8f (%.2f%%)", balance, profit_pct))
    print(string.format("🎲 Next Bet: %.8f | Chance: %.2f%%", nextbet, chance))
    print(string.format("🎯 W/L: %d/%d | Streak: %d (Max: %d)", 
        win_count, lose_count, loss_streak, max_loss_streak))
    
    -- แสดง wager เฉพาะแบบที่ 1
    if main_mode == 1 then
        print(string.format("📈 Wagered: %.4f / %.2f", total_wagered, wager_target))
    end
    
    print(string.format("🏦 %s: %.8f", vault_label, vault_display))
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT - Starting...")
print(string.format("💵 Start Balance: %.8f", balance))

-- ✅ เลือกโหมดเริ่มต้นตาม main_mode
if main_mode == 1 then
    print("🎯 Strategy: WAGER FOCUS (สลับโหมด + Vault1)")
    switchMode("wager")
elseif main_mode == 2 then
    print("🎯 Strategy: PROFIT FOCUS (ไม่สลับโหมด + Vault2)")
    switchMode("profit")
end

print(string.format("🎲 First Bet: %.8f | Chance: %.2f%%", nextbet, chance))

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLERS
------------------------------------------------------------

function dobet()
    
    total_wagered = total_wagered + previousbet
    
    -- ✅ เมื่อชนะ
    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0
        
        -- Mode: WAGER
        if mode == "wager" then
            nextbet = balance * (wager_bet_percent / 100)
            
            -- ✅ ตรวจสอบเป้า wager (เฉพาะ main_mode = 1)
            if main_mode == 1 and enable_wager_target and total_wagered >= wager_target then
                print("🎯 ถึงเป้า Wager Target!")
                showStatus()
                stop()
                return
            end
            
            checkVault()
            
        -- Mode: PROFIT
        else
            if auto_chance and random_on_win then
                chance = randomChance() * 100
            end
            
            nextbet = base
            checkVault()
        end
        
        if auto_switch and switch_on_win then
            bethigh = not bethigh
        end
        
    -- ❌ เมื่อแพ้
    else
        lose_count = lose_count + 1
        loss_streak = loss_streak + 1
        consecutive_losses_in_cycle = consecutive_losses_in_cycle + 1
        
        if loss_streak > max_loss_streak then
            max_loss_streak = loss_streak
        end
        
        -- Mode: WAGER
        if mode == "wager" then
            local loss_from_start = start_balance - balance
            local loss_pct = (loss_from_start / start_balance) * 100
            
            -- ✅ สลับโหมดเฉพาะ main_mode = 1
            if main_mode == 1 and loss_pct >= loss_cut_percent then
                print(string.format("⚠️ ขาดทุน %.2f%% → สลับไป Profit Mode", loss_pct))
                switchMode("profit")
            else
                nextbet = balance * (wager_bet_percent / 100)
            end
            
        -- Mode: PROFIT
        else
            if auto_chance and random_on_lose then
                chance = randomChance() * 100
            end
            
            local c_decimal = (chance > 1) and (chance / 100) or chance
            local multiplier = getAutoMultiplierByChance(c_decimal, risk_bonus_percent)
            
            nextbet = nextbet * multiplier
            
            if nextbet > balance then
                print("⚠️ Next bet > Balance → ปรับเป็น 90% ของ balance")
                nextbet = balance * 0.9
            end
            
            if consecutive_losses_in_cycle >= allowed_losses then
                print(string.format("⛔ แพ้ครบ %d ไม้ → Reset + คำนวณ Base ใหม่", allowed_losses))
                updateBaseAndDivisor()
                consecutive_losses_in_cycle = 0
            end
            
            -- ✅ กลับ wager mode เฉพาะ main_mode = 1
            if main_mode == 1 then
                local profit_from_start = balance - start_balance
                local profit_pct = (profit_from_start / start_balance) * 100
                
                if profit_pct >= recover_profit_percent then
                    print(string.format("✅ ฟื้นทุนแล้ว %.2f%% → กลับไป Wager Mode", profit_pct))
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
        print("🚨 Balance ต่ำเกินไป! หยุดระบบ")
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
