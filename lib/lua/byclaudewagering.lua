------------------------------------------------------------
-- CONFIG (ตั้งตามต้องการ)
------------------------------------------------------------
wager_chance       = 98
wager_bet_percent  = 2  -- 2.5% ของ balance
wager_loss_cut     = 5   -- หยุด wager เมื่อขาดทุน 5%

-- ⭐ เพิ่ม: เป้าหมาย wager
max_wager_target   = 300  -- หยุดเมื่อ wager ครบ 100
stop_on_wager      = true -- เปิด/ปิด ฟีเจอร์หยุดตาม wager

-- ⭐ เพิ่ม: เป้าหมายกำไร
profit_target      = 10   -- หยุดเมื่อกำไรถึง 10
stop_on_profit     = false -- เปิด/ปิด ฟีเจอร์หยุดตามกำไร

-- สร้าง PROFIT MODE สองชุด
profit_modes = {
    [1] = {
        name  = "profit1",
        chance = 4,
        base   = 0.002,
        multi  = 1.05
    },

    [2] = {
        name  = "profit2",
        chance = 0.88,
        base   = 0.002,
        multi  = 1.01
    }
}

house_edge = 1  -- 1% house edge

------------------------------------------------------------
-- MAIN VARIABLES
------------------------------------------------------------
start_balance = balance
total_wagered = 0  -- ⭐ เพิ่ม: ติดตามยอด wager รวม

mode = "wager"
active_profit_mode = nil

chance = wager_chance
bethigh = false

-- กำหนดค่าเริ่มต้น nextbet และ previousbet ถ้ายังไม่มี
if nextbet == nil then
    nextbet = start_balance * (wager_bet_percent / 100)
end
if previousbet == nil then
    previousbet = nextbet
end

------------------------------------------------------------
-- UTILITY
------------------------------------------------------------
function payoutMultiplier(ch)
    return (100 - house_edge) / ch
end

------------------------------------------------------------
-- ฟังก์ชันหยุด bot
------------------------------------------------------------
function stop()
    print("⏹️ Bot stopped.")
    os.exit()
end

------------------------------------------------------------
-- SWITCH MODE
------------------------------------------------------------
function switchMode(newMode)

    if newMode == "wager" then
        mode   = "wager"
        chance = wager_chance
        nextbet = start_balance * (wager_bet_percent / 100)
        print("🟢 เข้าสู่ WAGER MODE")
        return
    end

    if newMode == "profit" then
        mode = "profit"

        -- เลือก PROFIT MODE แบบสุ่ม
        local pick = math.random(1, #profit_modes)
        active_profit_mode = profit_modes[pick]

        chance = active_profit_mode.chance
        nextbet = active_profit_mode.base
        print("🟡 เข้าสู่ PROFIT MODE: " .. active_profit_mode.name)

        return
    end
end

------------------------------------------------------------
-- MAIN BET LOOP
------------------------------------------------------------
function dobet()

    -- ⭐ เพิ่ม: นับยอด wager
    total_wagered = total_wagered + previousbet

    -- ป้องกันเงินหมด
    if balance <= 0 then
        print("🚨 Balance หมด!")
        stop()
        return
    end

    -- ⭐ เพิ่ม: เช็คเป้าหมาย wager
    if stop_on_wager and total_wagered >= max_wager_target then
        print(string.format("🎯 Wager ถึงเป้าหมาย! (%.4f/%.4f)", total_wagered, max_wager_target))
        print(string.format("💰 Balance สุดท้าย: %.4f | กำไร: %.4f", balance, balance - start_balance))
        stop()
        return
    end

    -- ⭐ เพิ่ม: เช็คเป้าหมายกำไร
    if stop_on_profit then
        local current_profit = balance - start_balance
        if current_profit >= profit_target then
            print(string.format("🎉 กำไรถึงเป้าหมาย! (%.4f/%.4f)", current_profit, profit_target))
            print(string.format("💰 Balance สุดท้าย: %.4f | Wager รวม: %.4f", balance, total_wagered))
            stop()
            return
        end
    end

    --------------------------------------------------------
    -- WAGER MODE
    --------------------------------------------------------
    if mode == "wager" then

        if win then
            -- ชนะ: reset bet เป็นเบสเท่าเดิม
            nextbet = start_balance * (wager_bet_percent / 100)
        else
            -- แพ้: ยังใช้เบสเท่าเดิม (หรือจะปรับรูปแบบได้)
            nextbet = start_balance * (wager_bet_percent / 100)
        end

        -- เข้าสู่ profit mode เมื่อขาดทุนตามสัดส่วน
        local loss_threshold = start_balance * (1 - wager_loss_cut / 100)
        
        if balance <= loss_threshold then
            print(string.format("⚠ ขาดทุน %.2f%% → switch ไป PROFIT MODE", wager_loss_cut))
            switchMode("profit")
            return
        end

        return
    end

    --------------------------------------------------------
    -- PROFIT MODE
    --------------------------------------------------------
    if mode == "profit" then

        if win then
            nextbet = active_profit_mode.base     -- reset
        else
            nextbet = previousbet * active_profit_mode.multi
        end

        -- Recover ครบ → กลับ WAGER (เพิ่ม buffer 1%)
        if balance >= start_balance * 1.05 then
            print("🟢 Recovery สำเร็จ → กลับไป WAGER MODE")
            start_balance = balance  -- อัพเดท start_balance ใหม่
            switchMode("wager")
            return
        end

        return
    end
end

------------------------------------------------------------
-- START
------------------------------------------------------------
print("=" .. string.rep("=", 50))
print("🎲 เริ่มต้น Betting System")
print(string.format("💵 Start Balance: %.4f", start_balance))
if stop_on_wager then
    print(string.format("🎯 Wager Target: %.4f", max_wager_target))
end
if stop_on_profit then
    print(string.format("💰 Profit Target: %.4f", profit_target))
end
print("=" .. string.rep("=", 50))

switchMode("wager")
nextbet = start_balance * (wager_bet_percent / 100)

