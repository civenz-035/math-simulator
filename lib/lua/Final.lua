------------------------------------------------------------
-- 💰 FUSION BOT – SMART MARTINGALE CLEAN ADAPTIVE EDITION (2026)
-- 🧠 Auto Chance + Smart Multiplier + Dynamic Basebet + Safe Divisor
------------------------------------------------------------

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------

main_mode = 1   -- 1 = Wager+Recover | 2 = Profit Only

-- 🎯 WAGER MODE
wager_chance            = 99
wager_bet_percent       = 2.5
loss_cut_percent        = 4
recover_profit_percent  = 1
wager_target            = 1000

-- 🧠 PROFIT MODE
auto_chance        = true
chance_min         = 0.35      -- ใช้เป็น base คำนวณ worst-case
chance_max         = 0.55
chance_fixed       = 49.95     -- ใช้เมื่อ auto_chance=false
random_on_win      = true
random_on_lose     = false

-- ⚙️ Multiplier / Base config
risk_bonus_percent = 1.0
allowed_losses     = 8
constant_divisor   = 0         -- ระบบคำนวณอัตโนมัติ
multiplier_win     = 1.0
bethigh            = true
auto_switch        = true
switch_on_win      = true
switch_on_lose     = false

-- 🛑 Stop rules
stop_profit_target   = 0.03
stop_loss_limit      = 0.03
stop_max_loss_streak = 0
reset_profit_level   = 0.00000001

------------------------------------------------------------
-- 🌐 GLOBAL VARS
------------------------------------------------------------
mode = "wager"
start_balance = balance
session_start = os.time()
total_wagered, win_count, lose_count, loss_streak = 0,0,0,0
chance = wager_chance
nextbet = balance * (wager_bet_percent/100)
base = 0

------------------------------------------------------------
-- 🧮 UTILITIES
------------------------------------------------------------
function randomChance()
    local minInt = math.floor(chance_min * 100)
    local maxInt = math.floor(chance_max * 100)
    if minInt >= maxInt then maxInt = minInt + 1 end
    return math.random(minInt, maxInt) / 100
end

function getLastRoll()
    if lastBet then return lastBet.roll or lastBet.Roll or 0
    elseif lastRoll then return lastRoll else return 0 end
end

function getAutoMultiplierByChance(chance, bonus)
    return 1 + ((1 + (bonus / 100)) / ((1 / chance) - 1))
end

function getConstantDivisor(chance_ref, bonus_percent, allowed_losses)
    local mul = getAutoMultiplierByChance(chance_ref, bonus_percent)
    local sum = 0
    for i = 0, allowed_losses - 1 do
        sum = sum + (mul ^ i)
    end
    return sum
end

-- ✅ คำนวณ Divisor และ Base ตามโหมด Chance
function updateBaseAndDivisor()
    local refChance
    if auto_chance then
        refChance = chance_min
    else
        refChance = chance_fixed / 100
    end

    constant_divisor = getConstantDivisor(refChance, risk_bonus_percent, allowed_losses)
    base = balance / constant_divisor
    nextbet = base

    print(string.format("💵 Base recalculated → %.8f | Divisor=%.2f | ChanceRef=%.2f%%",
        base, constant_divisor, refChance*100))
end

function updateChanceOnResult(win)
    if auto_chance then
        if (win and random_on_win) or (not win and random_on_lose) then
            chance = randomChance()
        end
    end
end

function updateBetHighOnResult(win)
    if auto_switch then
        if (win and switch_on_win) or (not win and switch_on_lose) then
            bethigh = not bethigh
        end
    end
end

function formatTime(sec)
    local h = math.floor(sec / 3600)
    local m = math.floor((sec % 3600) / 60)
    local s = sec % 60
    return string.format("%02d:%02d:%02d", h, m, s)
end

function printSummary()
    local elapsed = os.time() - session_start
    local profit_abs = balance - start_balance
    local profit_percent = (profit_abs / start_balance) * 100
    local total_bets = win_count + lose_count
    local winrate = (total_bets>0) and (win_count/total_bets*100) or 0
    print("\n-------------------------------------")
    print("📊 SESSION SUMMARY")
    print("-------------------------------------")
    print(string.format("🪙 Total Wagered : %.8f", total_wagered))
    print(string.format("💰 Profit/Loss   : %.8f (%.2f%%)", profit_abs, profit_percent))
    print(string.format("🏆 Wins / Losses : %d / %d (%.2f%% win rate)", win_count, lose_count, winrate))
    print(string.format("⏱️ Session Time  : %s", formatTime(elapsed)))
    print("-------------------------------------\n")
end

function stopAndSummary(reason)
    printSummary()
    print("🛑 "..reason)
    stop()
end

------------------------------------------------------------
-- 🔄 MODE SWITCH
------------------------------------------------------------
function switchMode(newMode)
    if newMode=="wager" then
        mode="wager"
        chance=wager_chance
        nextbet=start_balance*(wager_bet_percent/100)
        print("🟢 เข้าสู่โหมด WAGERING")

    elseif newMode=="profit" then
        mode="profit"
        if auto_chance then chance=randomChance()
        else chance=chance_fixed/100 end

        updateBaseAndDivisor()
        multiplier_lose=getAutoMultiplierByChance(chance,risk_bonus_percent)

        print(string.format("⚙️ Auto Multiplier → %.6f (chance %.2f%% bonus %.2f%%)",
            multiplier_lose, chance*100, risk_bonus_percent))
        print("🟡 เข้าสู่โหมด PROFIT MODE")
    end
end

------------------------------------------------------------
-- 🎲 MAIN LOOP
------------------------------------------------------------
function dobet()
    local profit = balance - start_balance
    total_wagered = total_wagered + previousbet

    -- stop เมื่อครบเป้า wager
    if wager_target>0 and total_wagered>=wager_target then
        stopAndSummary(string.format("🎯 ถึงเป้ายอดเดิมพัน %.0f",wager_target))
        return
    end

    -- 🟢 WAGER MODE
    if main_mode==1 and mode=="wager" then
        nextbet=start_balance*(wager_bet_percent/100)
        print(string.format("🎲 Wager %.8f on %s at %.2f%% → Roll: %.2f %s | Bal: %.8f | Total: %.8f",
            previousbet,(bethigh and"HIGH"or"LOW"),chance,getLastRoll(),
            (win and"✅ Win"or"❌ Lost"),balance,total_wagered))
        local loss_threshold=start_balance*(1-loss_cut_percent/100)
        if balance<=loss_threshold then
            print(string.format("⚠️ ขาดทุน %.2f%% → เข้าสู่ PROFIT MODE",loss_cut_percent))
            switchMode("profit") return end
        return
    end

    -- 🪙 PROFIT MODE
    if mode=="profit" then
        if win then
            win_count=win_count+1; loss_streak=0
            updateBaseAndDivisor()  -- recalculated each win
            updateChanceOnResult(true)
            updateBetHighOnResult(true)
        else
            lose_count=lose_count+1; loss_streak=loss_streak+1
            nextbet=previousbet*multiplier_lose
            updateChanceOnResult(false)
            updateBetHighOnResult(false)
        end

        print(string.format("🪙 Bet %.8f on %s at %.2f%% → Roll: %.2f %s | Bal: %.8f | Mul: %.6f",
            previousbet,(bethigh and"HIGH"or"LOW"),chance,getLastRoll(),
            (win and"✅ Win"or"❌ Lost"),balance,multiplier_lose))

        if stop_profit_target>0 and balance>=start_balance*(1+stop_profit_target) then
            stopAndSummary("💹 ได้กำไรตามเป้า") return end
        if stop_loss_limit>0 and balance<=start_balance*(1-stop_loss_limit) then
            stopAndSummary("⚠️ ขาดทุนถึงขีดจำกัด") return end
        if stop_max_loss_streak>0 and loss_streak>=stop_max_loss_streak then
            stopAndSummary("🚫 แพ้ติดกันถึงจำนวนสูงสุด") return end
        if main_mode==1 and balance>=start_balance*(1+recover_profit_percent/100) then
            print(string.format("🟢 ฟื้นทุนพร้อมกำไร %.2f%% → กลับโหมด WAGER",recover_profit_percent))
            start_balance=balance; switchMode("wager") return end
    end
end

------------------------------------------------------------
-- 🚀 STARTUP
------------------------------------------------------------
if main_mode==1 then switchMode("wager") else switchMode("profit") end
print("🎬 เริ่มระบบ AUTO BET (Fusion Smart Martingale Clean Adaptive Edition)")
print(string.format("💵 Start balance: %.8f | Mode: %s",balance,mode))
