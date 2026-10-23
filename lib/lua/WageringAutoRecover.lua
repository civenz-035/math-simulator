-- ================================
-- 🚀 REALTIME SOCKET
-- ================================
local socket = require("socket")
local host = "127.0.0.1"
local port = 3001
local client = nil
local last_send_time = 0

function connectSocket()
    client = socket.tcp()
    client:settimeout(0)

    local res, err = client:connect(host, port)

    if err and err ~= "timeout" then
        print("❌ Socket connect fail:", err)
        client = nil
    end
end

function sendData()
    if not client then
        connectSocket()
        return
    end

    local now = socket.gettime()
    if now - last_send_time < 0.03 then return end
    last_send_time = now

    local profit = profit_vault + (working_balance - original_cycle_balance)

    local json = string.format(
        '{"balance":%.8f,"profit":%.8f,"nextbet":%.8f,"chance":%.2f,"win":%s,"mode":"%s","streak":%d}',
        balance, profit, nextbet, chance, tostring(win), mode, loss_streak
    )

    local ok, err = client:send(json .. "\n")

    if not ok then
        print("⚠️ Send fail:", err)
        client:close()
        client = nil
    end
end
------------------------------------------------------------
-- 💎FinalfixByAntigravity HIGH/LOW setting (Optimized by Coach)
-- 🚀 เพิ่มฟีเจอร์ External HTML Dashboard (รองรับ Mobile Server)
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------
main_mode = 2

------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------
wager_chance            = 99
wager_bet_percent       = 3
loss_cut_percent        = 3.99
recover_profit_percent  = 1
wager_target            = 50
enable_wager_target     = true

------------------------------------------------------------
-- 💹 PROFIT MODE CONFIG
------------------------------------------------------------
auto_chance   = true
chance_min    = 0.45
chance_max    = 0.55
chance_fixed  = false
random_on_win      = false
random_on_lose     = false

use_fix_basebet      = false  
fix_basebet_amount   = 0.002 


------------------------------------------------------------
-- ⚙️ MULTIPLIER / BASE CONFIG
------------------------------------------------------------
use_fixed_multiplier = false 
fixed_multiplier     = 1.006   
risk_bonus_percent   = 5.0    
house_edge           = 1.0
allowed_losses       = 700
constant_divisor     = 0
bethigh              = true
auto_switch          = false
switch_on_win        = false
switch_on_lose       = false

------------------------------------------------------------
-- 🎯 BET HIGH/LOW CONFIG (แยกตาม Mode)
------------------------------------------------------------
wager_bethigh_mode   = "fix"
wager_bethigh        = true   

profit_bethigh_mode  = "fix"
profit_bethigh       = true   

------------------------------------------------------------
-- 🛑 STOP RULES & UI CONFIG
------------------------------------------------------------
stop_profit_target   = 0.1
stop_loss_limit      = 0.0
stop_max_loss_streak = 0
min_bet_size         = 0.00000001

-- 🛠️ ปรับเป็น 1 เพื่อให้อัปเดต Dashboard ทุกๆ ไม้แบบ Real-time
dashboard_update_every = 1

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
last_bet_details = "รอการเดิมพันไม้แรก..." -- ✅ เก็บข้อความผลการเดิมพันล่าสุด

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
    local current_mode = mode
    
    if current_mode == "wager" then
        if wager_bethigh_mode == "fix" then
            bethigh = wager_bethigh
        else
            local result = math.random() >= 0.5
            bethigh = result
        end
    else
        if profit_bethigh_mode == "fix" then
            bethigh = profit_bethigh
        else
            local result = math.random() >= 0.5
            bethigh = result
        end
    end
    
    return bethigh
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
        randomBethigh()  
        wager_cycle_start = working_balance 
        wager_base_bet = wager_cycle_start * (wager_bet_percent / 100)
        wager_loss_amount = 0
        chance = wager_chance
        nextbet = wager_base_bet
    else
        randomBethigh()  
        profit_cycle_start = working_balance 
        cycle_start_balance = working_balance 
        updateBaseAndDivisor()
        if auto_chance then chance = randomChance() else chance = chance_fixed end
        
        local mul, payout
        if use_fixed_multiplier then
            mul = fixed_multiplier
            payout = 0  
        else
            local use_he = (main_mode == 2)
            mul, payout = getAutoMultiplierByChance(chance, risk_bonus_percent, use_he)
        end
    end
    if nextbet < min_bet_size then nextbet = min_bet_size end
end

------------------------------------------------------------
-- 📊 HTML DASHBOARD GENERATOR (🛠️ อัปเดตไฟล์เป็น index.html)
------------------------------------------------------------
function updateHTMLDashboard(runtime, cycle_profit, total_profit, vault_pct, mode_info)
    -- ✅ สร้างไฟล์ index.html สำหรับรัน Web Server
    local file = io.open("index.html", "w")
    if file then
        local current_time = os.date("%H:%M:%S")
        local is_wager = (mode == "wager")
        local mode_color = is_wager and "#00d2ff" or "#ffb300"
        local status_color = (total_profit >= 0) and "#00ff88" or "#ff4d4d"
        local last_bet_color = string.find(last_bet_details, "Win") and "#00ff88" or "#ff4d4d"

        local html_content = string.format([[
        <!DOCTYPE html>
        <html lang="th">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0"> <!-- ✅ รองรับจอโทรศัพท์ -->
            <meta http-equiv="refresh" content="1"> <!-- ⏳ รีเฟรชอัตโนมัติทุก 1 วินาที -->
            <title>Fusion Bot Dashboard</title>
            <style>
                body { background-color: #12121a; color: #ffffff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 15px; }
                .container { max-width: 800px; margin: auto; background: #1e1e2d; border-radius: 12px; padding: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.5); }
                .header { text-align: center; border-bottom: 2px solid #32324e; padding-bottom: 15px; margin-bottom: 20px; }
                .header h1 { margin: 0; font-size: 24px; color: #00d2ff; }
                .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
                /* ปรับให้เรียงแถวเดียวเมื่อดูบนมือถือ */
                @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
                .box { background: #2a2a3f; padding: 15px; border-radius: 8px; border-left: 4px solid #4a4a6a; }
                .box h3 { margin: 0 0 5px 0; font-size: 13px; color: #a0a0b8; text-transform: uppercase; }
                .value { font-size: 20px; font-weight: bold; margin: 0; word-break: break-all;}
                .highlight-mode { color: %s; }
                .highlight-profit { color: %s; }
                .last-bet { background: #222233; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; font-family: monospace; font-size: 14px; color: %s; word-break: break-all;}
                .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 FUSION BOT v3.4</h1>
                    <p style="margin:5px 0 0 0; color:#888;">อัปเดตล่าสุด: %s | รันไทม์: %ds</p>
                </div>
                
                <div class="grid">
                    <div class="box" style="border-left-color: %s;">
                        <h3>สถานะปัจจุบัน (Mode)</h3>
                        <p class="value highlight-mode">%s | Cycle: %d</p>
                    </div>
                    <div class="box">
                        <h3>เงินทุนในระบบ (Working)</h3>
                        <p class="value">%.8f</p>
                    </div>
                    <div class="box">
                        <h3>ห้องนิรภัยกำไร (Vault)</h3>
                        <p class="value" style="color:#ffb300;">%.8f (%.2f%%)</p>
                    </div>
                    <div class="box">
                        <h3>กำไรสุทธิทั้งหมด (Total Profit)</h3>
                        <p class="value highlight-profit">%+.8f</p>
                    </div>
                    <div class="box">
                        <h3>รายละเอียดไม้ต่อไป (Next Bet)</h3>
                        <p class="value">%.8f | โอกาส: %.2f%%</p>
                    </div>
                    <div class="box">
                        <h3>สถิติการเดิมพัน (Stats)</h3>
                        <p class="value" style="font-size: 16px;">W: <span style="color:#00ff88">%d</span> | L: <span style="color:#ff4d4d">%d</span> | สตรีคแพ้: %d (Max: %d)</p>
                    </div>
                    <div class="box">
                        <h3>สถานะโหมดเป้าหมาย (Targets)</h3>
                        <p class="value" style="font-size: 15px;">เทิร์น: %.4f / %.2f<br>%s</p>
                    </div>
                    <div class="box">
                        <h3>แอคชันล่าสุด (Last Action)</h3>
                        <p class="value" style="font-size: 15px; color:#cba6f7;">%s</p>
                    </div>
                </div>

                <div class="last-bet">
                    <strong>🎲 ผลไม้ล่าสุด:</strong><br>%s
                </div>

                <div class="footer">
                    ออกแบบ Dashboard โดย Coach (Software Engineer)
                </div>
            </div>
        </body>
        </html>
        ]], mode_color, status_color, last_bet_color, current_time, runtime, mode_color, string.upper(mode), cycle_count, working_balance, profit_vault, vault_pct, total_profit, nextbet, chance, win_count, lose_count, loss_streak, max_loss_streak, total_wagered, wager_target, mode_info, last_action, last_bet_details)

        file:write(html_content)
        file:close()
    end
end

------------------------------------------------------------
-- 📊 STATUS DISPLAY
------------------------------------------------------------
function showStatus()
    local runtime = os.time() - session_start
    local cycle_profit
    if mode == "wager" then cycle_profit = working_balance - wager_cycle_start
    else cycle_profit = working_balance - profit_cycle_start end
    local total_profit = profit_vault + (working_balance - original_cycle_balance)
    local vault_pct = (profit_vault / start_balance) * 100
    local bethigh_str = bethigh and "HIGH" or "LOW"
    
    local mode_info = ""
    if main_mode == 1 then
        if mode == "wager" then
            local wager_loss = wager_cycle_start - working_balance
            local wager_loss_pct = (wager_loss / original_cycle_balance) * 100
            mode_info = string.format("Loss: %.2f%%/%.2f%%", wager_loss_pct, loss_cut_percent)
        else
            local need_recover_amount = wager_loss_amount + (original_cycle_balance * recover_profit_percent / 100)
            local current_gain = working_balance - profit_cycle_start
            local need_recover_pct = (need_recover_amount / original_cycle_balance) * 100
            local current_gain_pct = (current_gain / original_cycle_balance) * 100
            mode_info = string.format("Recv: %.2f%%/%.2f%% | L#%d", current_gain_pct, need_recover_pct, consecutive_losses_in_cycle)
        end
    else
        mode_info = string.format("L#%d/%d", consecutive_losses_in_cycle, allowed_losses)
    end
    
    -- 🛠️ HACK ทางวิศวกรรมแบบ "ไฟท์บังคับ" ใน Console (เผื่อยังอยากดูในโปรแกรม)
    print(string.rep("\n", 40))
    print("==================================================")
    print("🎬 FUSION BOT v3.4 - TRUE Balance Reset")
    print(string.format("⏱️ %ds | %s | %s | Cyc:%d", runtime, (main_mode == 1) and "WAGER" or "PROFIT", mode:upper(), cycle_count))
    print(string.format("🎯 Action: %s | ล่าสุด: %s", last_action, last_bet_details))
    print("==================================================")

    -- 🚀 เรียกฟังก์ชันสร้าง HTML หน้าเว็บแยก
    updateHTMLDashboard(runtime, cycle_profit, total_profit, vault_pct, mode_info)
end

------------------------------------------------------------
-- 🎲 INITIALIZATION
------------------------------------------------------------
print(string.rep("\n", 40))
print("🎬 FUSION BOT v3.4 - แบบ A (TRUE Balance Reset) [External UI]")
print(string.format("💵 Start Balance: %.8f", balance))
working_balance = balance
cycle_start_balance = balance
original_cycle_balance = balance  

if main_mode == 1 then
    switchMode("wager")
elseif main_mode == 2 then
    switchMode("profit")
end

------------------------------------------------------------
-- 🎲 DICEBOT EVENT HANDLER
------------------------------------------------------------
function dobet()
    local dir_str = bethigh and "High" or "Low "
    local payout_amount = previousbet * (99 / chance)  
    local result_str = ""
    
    if win then
        result_str = string.format("BET %s | %.2f%% | roll %6.2f | Win ✅ +%.8f", 
            dir_str, chance, lastBet.Roll, payout_amount - previousbet)
    else
        local wrong_side = false
        if bethigh then
            wrong_side = lastBet.Roll >= (100 - chance)
        else
            wrong_side = lastBet.Roll < chance
        end
        
        if wrong_side then
            result_str = string.format("BET %s | %.2f%% | roll %6.2f | Wrong ☠️ -%.8f", 
                dir_str, chance, lastBet.Roll, previousbet)
        else
            result_str = string.format("BET %s | %.2f%% | roll %6.2f | Lose 🚫 -%.8f", 
                dir_str, chance, lastBet.Roll, previousbet)
        end
    end
    
    last_bet_details = result_str
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
    
    if bets % dashboard_update_every == 0 or string.find(last_action, "MODE") then 
        showStatus() 
    end
    sendData()
end