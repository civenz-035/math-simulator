------------------------------------------------------------
-- 💰 AUTO BET SYSTEM (Full Fusion + Safe Roll + Summary)
-- 🧩 รวม WAGER MODE + PROFIT MODE + สรุปผลอัตโนมัติ
-- 🧠 พร้อมใช้งานบน DiceBot | เวอร์ชันเสถียรสุด 2025
------------------------------------------------------------


------------------------------------------------------------
-- ⚙️ CONFIG (ตั้งค่าง่าย)
------------------------------------------------------------

-- 🔘 เลือกโหมดหลัก
-- 1 = Wagering + Recovering Mode
-- 2 = Profit Aiming Mode (กำไรอย่างเดียว)
main_mode = 1


------------------------------------------------------------
-- 🎯 WAGER MODE CONFIG
------------------------------------------------------------

wager_chance            = 99
wager_bet_percent       = 2.5
loss_cut_percent        = 4
recover_profit_percent  = 1
wager_target            = 5


------------------------------------------------------------
-- 🧠 PROFIT MODE CONFIG
------------------------------------------------------------

auto_chance        = true
chance_min         = 0.45
chance_max         = 0.55
chance_fixed       = 49.95
random_on_win      = true
random_on_lose     = false

constant_divisor   = 0
manual_base        = 0.00002

multiplier_win     = 1.0
multiplier_lose    = 1.006
auto_multiplier    = true

bethigh            = true
auto_switch        = true
switch_on_win      = true
switch_on_lose     = false

stop_profit_target     = 0.05
stop_loss_limit        = 0.0
stop_max_loss_streak   = 0
reset_profit_level     = 0.00000001


------------------------------------------------------------
-- 🧩 GLOBAL VARIABLES
------------------------------------------------------------
mode = "wager"
start_balance = balance
session_start = os.time()
active_profit_mode = false
total_wagered = 0
chance = wager_chance
nextbet = balance * (wager_bet_percent / 100)
base = manual_base
win_count, lose_count, loss_streak = 0, 0, 0


------------------------------------------------------------
-- 🧮 UTILITY FUNCTIONS
------------------------------------------------------------

-- ✅ ป้องกัน math.random error (ต้องเป็น integer)
function randomChance()
    local minInt = math.floor(chance_min * 100)
    local maxInt = math.floor(chance_max * 100)
    if minInt >= maxInt then maxInt = minInt + 1 end
    return math.random(minInt, maxInt) / 100
end

-- ✅ ดึงผล Roll ล่าสุด (รองรับ DiceBot ทุกเวอร์ชัน)
function getLastRoll()
    if lastBet ~= nil then
        return lastBet.roll or lastBet.Roll or 0
    elseif lastRoll ~= nil then
        return lastRoll
    else
        return 0
    end
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

-- ✅ ฟังก์ชันจับเวลา
function formatTime(sec)
    local h = math.floor(sec / 3600)
    local m = math.floor((sec % 3600) / 60)
    local s = sec % 60
    return string.format("%02d:%02d:%02d", h, m, s)
end

-- ✅ แสดงสรุปตอน Stop
function printSummary()
    local elapsed = os.time() - session_start
    local profit_abs = balance - start_balance
    local profit_percent = (profit_abs / start_balance) * 100
    local total_bets = win_count + lose_count
    local winrate = (total_bets > 0) and (win_count / total_bets * 100) or 0

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
    print("🛑 " .. reason)
    stop()
end

-- ✅ เปลี่ยนโหมดหลัก (Wager <-> Profit)
function switchMode(newMode)
    if newMode == "wager" then
        mode = "wager"
        active_profit_mode = false
        chance = wager_chance
        nextbet = start_balance * (wager_bet_percent / 100)
        print("🟢 เข้าสู่โหมด WAGERING")
    elseif newMode == "profit" then
        mode = "profit"
        active_profit_mode = true
        if auto_chance then
            chance = randomChance()
        else
            chance = chance_fixed
        end
        if constant_divisor > 0 then
            base = balance / constant_divisor
        else
            base = manual_base
        end
        nextbet = base
        print("🟡 เข้าสู่โหมด PROFIT MODE")
    end
end


------------------------------------------------------------
-- 🎲 MAIN LOOP
------------------------------------------------------------
function dobet()

    total_wagered = total_wagered + previousbet

    -- 🛑 หยุดเมื่อยอดเดิมพันรวมครบเป้า
    if wager_target > 0 and total_wagered >= wager_target then
        stopAndSummary(string.format("🎯 ถึงเป้ายอดเดิมพันรวม %.0f", wager_target))
        return
    end

    --------------------------------------------------------
    -- 🟢 WAGER MODE
    --------------------------------------------------------
    if main_mode == 1 and mode == "wager" then
        nextbet = start_balance * (wager_bet_percent / 100)

        print(string.format(
            "🎲 Wager bet %.8f on %s at %.2f%% → Roll: %.2f %s | Bal: %.8f | Total: %.8f",
            previousbet,
            (bethigh and "HIGH" or "LOW"),
            chance,
            getLastRoll(),
            (win and "✅ Win" or "❌ Lost"),
            balance,
            total_wagered
        ))

        local loss_threshold = start_balance * (1 - loss_cut_percent / 100)
        if balance <= loss_threshold then
            print(string.format("⚠️ ขาดทุน %.2f%% → เข้าสู่ PROFIT MODE", loss_cut_percent))
            switchMode("profit")
            return
        end
        return
    end

    --------------------------------------------------------
    -- 🪙 PROFIT MODE
    --------------------------------------------------------
    if mode == "profit" then
        if win then
            win_count = win_count + 1
            loss_streak = 0
            nextbet = previousbet * multiplier_win
            if profit >= reset_profit_level then nextbet = base end
            updateChanceOnResult(true)
            updateBetHighOnResult(true)
        else
            lose_count = lose_count + 1
            loss_streak = loss_streak + 1
            nextbet = previousbet * multiplier_lose
            updateChanceOnResult(false)
            updateBetHighOnResult(false)
        end

        print(string.format(
            "🪙 Bet %.8f on %s at %.2f%% → Roll: %.2f %s | Bal: %.8f | Total: %.8f",
            previousbet,
            (bethigh and "HIGH" or "LOW"),
            chance,
            getLastRoll(),
            (win and "✅ Win" or "❌ Lost"),
            balance,
            total_wagered
        ))

        if stop_profit_target > 0 and balance >= start_balance * (1 + stop_profit_target) then
            stopAndSummary("💹 ได้กำไรตามเป้า")
            return
        end

        if stop_loss_limit > 0 and balance <= start_balance * (1 - stop_loss_limit) then
            stopAndSummary("⚠️ ขาดทุนถึงขีดจำกัด")
            return
        end

        if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak then
            stopAndSummary("🚫 แพ้ติดกันถึงจำนวนสูงสุด")
            return
        end

        if main_mode == 1 and balance >= start_balance * (1 + recover_profit_percent / 100) then
            print(string.format("🟢 ฟื้นทุนพร้อมกำไร %.2f%% → กลับโหมด WAGER", recover_profit_percent))
            start_balance = balance
            switchMode("wager")
            return
        end
    end
end


------------------------------------------------------------
-- 🚀 STARTUP
------------------------------------------------------------
if main_mode == 1 then
    switchMode("wager")
else
    switchMode("profit")
end

print("🎬 เริ่มระบบ AUTO BET (Fusion Stable 2025)")
print(string.format("💵 Start balance: %.8f | Mode: %s", balance, mode))
