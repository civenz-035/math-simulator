------------------------------------------------------------
-- 💎 FUSION BOT – SMART MARTINGALE CLEAN ADAPTIVE EDITION
-- 🔧 DiceBot Compatible Version (Production v2.1 - FIXED)
-- 🧠 Auto Chance + Smart Multiplier + Dynamic Basebet + Vault System
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------

main_mode = 2   -- 1 = Wager+Recover | 2 = Profit Only

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 99               
wager_bet_percent       = 2.5              
loss_cut_percent        = 4                
recover_profit_percent  = 1                
wager_target            = 1000             
enable_wager_target     = true             

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = true   

chance_min    = 0.35      
chance_max    = 0.55      
chance_fixed  = 49.95     

random_on_win      = true     
random_on_lose     = false    

------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
risk_bonus_percent = 1.0       
allowed_losses     = 8         
constant_divisor   = 0         
bethigh            = true      
auto_switch        = true      
switch_on_win      = true
switch_on_lose     = false

------------------------------------------------------------
-- 🏦 VAULT SYSTEM CONFIG
------------------------------------------------------------
vault_mode1             = 0
vault_trigger_mode1     = 1.05      
vault_fraction_mode1    = 0.25      

vault_mode2             = 0
vault_trigger_mode2     = 1.10      
vault_fraction_mode2    = 0.50      

------------------------------------------------------------
-- 🛑 STOP RULES
------------------------------------------------------------
stop_profit_target   = 0.0     
stop_loss_limit      = 0.0      
stop_max_loss_streak = 0         
min_bet_size         = 0.00000001  -- ✅ เพิ่ม: ป้องกัน bet เล็กเกินไป

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
consecutive_losses_in_cycle = 0  -- ✅ เพิ่ม: นับแพ้ในรอบปัจจุบัน

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
    
    -- ✅ ป้องกัน base เล็กเกินไป
    if base < min_bet_size then
        base = min_bet_size
    end
    
    nextbet = base
end

------------------------------------------------------------
-- 🏦 VAULT SYSTEM
------------------------------------------------------------
function checkVault(modeType)
    local vault_triggered = false
    
    if modeType == 1 then
        if balance >= start_balance * vault_trigger_mode1 then
            local profit = balance - start_balance
            local dep = profit * vault_fraction_mode1
            vault_mode1 = vault_mode1 + dep
            balance = balance - dep
            print(string.format("🏦 Mode1 Vault +%.8f | Total %.8f | Balance %.8f",
                dep, vault_mode1, balance))
            start_balance = balance
            vault_triggered = true
        end
    elseif modeType == 2 then
        if balance >= start_balance * vault_trigger_mode2 then
            local profit = balance - start_balance
            local dep = profit * vault_fraction_mode2
            vault_mode2 = vault_mode2 + dep
            balance = balance - dep
            print(string.format("🏦 Mode2 Vault +%.8f | Total %.8f | Balance %.8f",
                dep, vault_mode2, balance))
            start_balance = balance
            vault_triggered = true
        end
    end
    
    -- ✅ คำนวณ base ใหม่หลัง vault
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
    consecutive_losses_in_cycle = 0  -- ✅ reset cycle
    
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
    
    -- ✅ ป้องกัน bet เล็กเกินไป
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
    
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(string.format("⏱️  Runtime: %ds | Mode: %s", runtime, mode:upper()))
    print(string.format("💰 Balance: %.8f (%.2f%%)", balance, profit_pct))
    print(string.format("🎲 Next Bet: %.8f | Chance: %.2f%%", nextbet, chance))
    print(string.format("🎯 W/L: %d/%d | Streak: %d (Max: %d)", 
        win_count, lose_count, loss_streak, max_loss_streak))
    print(string.format("📈 Wagered: %.4f / %.2f", total_wagered, wager_target))
    print(string.format("🏦 Vault1: %.8f | Vault2: %.8f", vault_mode1, vault_mode2))
    print(string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print("🎬 FUSION BOT - Starting...")
print(string.format("💵 Start Balance: %.8f", balance))

-- ✅ เริ่มต้นระบบให้สมบูรณ์
if main_mode == 1 then
    switchMode("wager")
else
    switchMode("profit")
end

print(string.format("🎯 First Bet: %.8f | Chance: %.2f%%", nextbet, chance))

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLERS
------------------------------------------------------------

function dobet()
    
    -- ✅ นับ wager หลังจาก bet เสร็จ
    total_wagered = total_wagered + previousbet
    
    -- ✅ เมื่อชนะ
    if win then
        win_count = win_count + 1
        loss_streak = 0
        consecutive_losses_in_cycle = 0  -- ✅ reset cycle
        
        -- Mode: WAGER
        if mode == "wager" then
            nextbet = balance * (wager_bet_percent / 100)
            
            -- ตรวจสอบเป้า wager
            if enable_wager_target and total_wagered >= wager_target then
                print("🎯 ถึงเป้า Wager Target!")
                showStatus()
                stop()
                return
            end
            
            checkVault(1)
            
        -- Mode: PROFIT
        else
            -- สุ่ม chance ใหม่ถ้าต้องการ
            if auto_chance and random_on_win then
                chance = randomChance() * 100
            end
            
            -- reset เป็น base bet
            nextbet = base
            
            checkVault(2)
        end
        
        -- สลับด้านถ้าเปิดใช้งาน
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
            
            -- ขาดทุนเกิน loss_cut_percent → สลับไป profit mode
            if loss_pct >= loss_cut_percent then
                print(string.format("⚠️ ขาดทุน %.2f%% → สลับไป Profit Mode", loss_pct))
                switchMode("profit")
            else
                nextbet = balance * (wager_bet_percent / 100)
            end
            
        -- Mode: PROFIT
        else
            -- สุ่ม chance ใหม่ถ้าต้องการ
            if auto_chance and random_on_lose then
                chance = randomChance() * 100
            end
            
            -- คำนวณ multiplier
            local c_decimal = (chance > 1) and (chance / 100) or chance
            local multiplier = getAutoMultiplierByChance(c_decimal, risk_bonus_percent)
            
            -- เพิ่ม bet ตาม martingale
            nextbet = nextbet * multiplier
            
            -- ✅ ป้องกัน bet เกิน balance
            if nextbet > balance then
                print("⚠️ Next bet > Balance → ปรับเป็น 90% ของ balance")
                nextbet = balance * 0.9
            end
            
            -- ตรวจสอบไม้ติดต่อกันในรอบนี้
            if consecutive_losses_in_cycle >= allowed_losses then
                print(string.format("⛔ แพ้ครบ %d ไม้ → Reset + คำนวณ Base ใหม่", allowed_losses))
                updateBaseAndDivisor()
                consecutive_losses_in_cycle = 0  -- ✅ reset cycle แต่ไม่ reset loss_streak
            end
            
            -- ตรวจสอบว่ากลับมาฟื้นทุนแล้วหรือยัง
            local profit_from_start = balance - start_balance
            local profit_pct = (profit_from_start / start_balance) * 100
            
            if profit_pct >= recover_profit_percent then
                print(string.format("✅ ฟื้นทุนแล้ว %.2f%% → กลับไป Wager Mode", profit_pct))
                switchMode("wager")
            end
        end
        
        -- สลับด้านถ้าเปิดใช้งาน
        if auto_switch and switch_on_lose then
            bethigh = not bethigh
        end
    end
    
    -- ✅ ป้องกัน bet เล็กเกินไป (double check)
    if nextbet < min_bet_size then
        nextbet = min_bet_size
    end
    
    -- 🛑 STOP CONDITIONS
    local current_profit = balance - start_balance
    local profit_ratio = current_profit / start_balance
    
    -- หยุดเมื่อกำไรถึงเป้า
    if stop_profit_target > 0 and profit_ratio >= stop_profit_target then
        print(string.format("🎉 ถึงเป้ากำไร %.2f%%!", profit_ratio * 100))
        showStatus()
        stop()
        return
    end
    
    -- หยุดเมื่อขาดทุนเกินลิมิต
    if stop_loss_limit > 0 and profit_ratio <= -stop_loss_limit then
        print(string.format("🚨 ขาดทุนเกินลิมิต %.2f%%!", math.abs(profit_ratio) * 100))
        showStatus()
        stop()
        return
    end
    
    -- หยุดเมื่อแพ้ติดต่อกันเกินกำหนด
    if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak then
        print(string.format("🚨 แพ้ติดต่อกัน %d ไม้!", loss_streak))
        showStatus()
        stop()
        return
    end
    
    -- ✅ หยุดฉุกเฉินถ้า balance เหลือน้อยเกินไป
    if balance < min_bet_size * 2 then
        print("🚨 Balance ต่ำเกินไป! หยุดระบบ")
        showStatus()
        stop()
        return
    end
    
    -- แสดงสถานะทุกๆ 50 รอบ (เปลี่ยนจาก 100)
    if bets % 50 == 0 then
        showStatus()
    end
end

------------------------------------------------------------
-- 🏁 END OF SCRIPT
------------------------------------------------------------