------------------------------------------------------------
-- ⚙ CONFIG ตั้งค่าได้ตามต้องการ
------------------------------------------------------------
--# stake_api_key=522fe34470a71f0662cfc2ec39b887f54e34459125cdc8ed646b366f7a997635d9a75e03b162df944ceaa9cc644be544

-- 💰 Wager Mode Settings
wager_chance = 98
wager_bet_percent = 0.10      -- 10% ของยอดเงิน
max_drawdown = 0.05           -- ขาดทุน 20% จากทุนเริ่มต้น → เข้าสู่ Profit Mode

-- 💰 Profit Mode Settings
profit_chance = 5
profit_base = 0.000002          -- เบทเริ่มตอน profit mode
profit_mul = 1.052            -- คูณเมื่อแพ้

-- 🧱 Stop Conditions
stop_profit_target = 50     -- หยุดเมื่อกำไรถึง +50% ของทุนเริ่มต้น
stop_loss_limit = 0.0        -- หยุดเมื่อขาดทุนรวมเกิน 30%
stop_balance_high = 9999      -- หยุดเมื่อยอดเงินมากกว่า (ถ้าไม่ใช้ ให้ใส่ค่ามาก ๆ)
stop_balance_low  = 0.00001   -- หยุดเมื่อยอดเงินน้อยกว่านี้

------------------------------------------------------------
-- 🧮 ตัวแปรระบบ
------------------------------------------------------------
mode = "wager"
start_balance = balance
nextbet = balance * wager_bet_percent
chance = wager_chance
bethigh = true

------------------------------------------------------------
-- 🔁 สลับโหมด
------------------------------------------------------------
function switchMode(newMode)
    mode = newMode
    if mode == "wager" then
        print("🟢 เข้าสู่โหมด WAGER - ปั้นยอดเดิมพัน")
        chance = wager_chance
        nextbet = balance * wager_bet_percent
        start_balance = balance
    elseif mode == "profit" then
        print("🟡 เข้าสู่โหมด PROFIT - ฟื้นทุน")
        chance = profit_chance
        nextbet = profit_base
    end
end

------------------------------------------------------------
-- ⛔ ฟังก์ชันตรวจหยุด
------------------------------------------------------------
function checkStop()
    local profit_now = balance - start_balance

    if profit_now >= start_balance * stop_profit_target then
        print("🟩 หยุด: ได้กำไรถึงเป้าหมาย +", string.format("%.2f%%", stop_profit_target * 100))
        stop()
    elseif profit_now <= -(start_balance * stop_loss_limit) then
        print("🟥 หยุด: ขาดทุนเกินเป้าหมาย -", string.format("%.2f%%", stop_loss_limit * 100))
        stop()
    elseif balance >= stop_balance_high then
        print("🟦 หยุด: ยอดเงินมากกว่าที่กำหนด")
        stop()
    elseif balance <= stop_balance_low then
        print("🟧 หยุด: ยอดเงินต่ำกว่าที่กำหนด")
        stop()
    end
end

------------------------------------------------------------
-- 🎯 ฟังก์ชันหลัก
------------------------------------------------------------
function dobet()
    local profit_now = balance - start_balance

    checkStop()  -- ตรวจว่าควรหยุดไหม

    if mode == "wager" then
        -- 🟢 โหมดปั้น wager
        nextbet = balance * wager_bet_percent
        if profit_now <= -(start_balance * max_drawdown) then
            switchMode("profit")
        end

    elseif mode == "profit" then
        -- 🟡 โหมดฟื้นทุน
        if win then
            nextbet = profit_base
        else
            nextbet = previousbet * profit_mul
        end

        if balance >= start_balance then
            switchMode("wager")
        end
    end
end

------------------------------------------------------------
-- 🚀 เริ่มต้นระบบ
------------------------------------------------------------
print("🚀 เริ่มระบบ WAGER + PROFIT + STOP อัตโนมัติ")
switchMode("wager")