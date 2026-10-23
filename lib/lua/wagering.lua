----- ⚙ CONFIG ตั้งค่าได้ตามต้องการ

-- 💰 Wager Mode Settings
wager_chance = 98
wager_bet_percent = 0.025      -- 10% ของยอดเงิน
max_drawdown = 0.0250           -- ขาดทุน 20% จากทุนเริ่มต้น → เข้าสู่ Profit Mode

-- 💰 Profit Mode Settings
profit_chance = 4.5
profit_base = 0.005          -- เบทเริ่มตอน profit mode
profit_mul = 1.055            -- คูณเมื่อแพ้

-- 🧱 Stop Conditions
stop_profit_target = 0.50     -- หยุดเมื่อกำไรถึง +50% ของทุนเริ่มต้น
stop_loss_limit = 0.30        -- หยุดเมื่อขาดทุนเกิน 30%
stop_balance_high = 9999      -- หยุดเมื่อยอดเงินมากกว่า (ถ้าไม่ใช้ ให้ใส่ค่ามาก)
stop_balance_low  = 0.00001   -- หยุดเมื่อยอดเงินน้อยกว่าที่กำหนด
stop_wager_target = 10        -- หยุดเมื่อ wagered (ยอดเดิมพันสะสม) ถึง 10 เท่าของทุนเริ่มต้น

------------------------------------------------------------
-- 🧮 ตัวแปรระบบ
------------------------------------------------------------
mode = "wager"
start_balance = balance
totalWagered = 0               -- ⭐ นับยอดเดิมพันสะสมเอง
nextbet = balance * wager_bet_percent
chance = wager_chance
bethigh = true

------------------------------------------------------------
-- ⛔ ฟังก์ชันตรวจหยุด
------------------------------------------------------------
function checkStop()
    local profit_now = balance - start_balance

    -- 📊 หยุดเมื่อได้กำไรถึงเป้า
    if profit_now >= start_balance * stop_profit_target then
        print("🟩 หยุด: กำไรถึงเป้าหมาย +", string.format("%.2f%%", stop_profit_target * 100))
        stop()

    -- 📉 หยุดเมื่อขาดทุนเกินเป้า
    elseif profit_now <= -(start_balance * stop_loss_limit) then
        print("🟥 หยุด: ขาดทุนเกินเป้าหมาย -", string.format("%.2f%%", stop_loss_limit * 100))
        stop()

    -- 💎 Balance สูง/ต่ำ
    elseif balance >= stop_balance_high then
        print("🟦 หยุด: ยอดเงินสูงกว่าเป้ากำหนด")
        stop()
    elseif balance <= stop_balance_low then
        print("🟧 หยุด: ยอดเงินต่ำกว่าเป้ากำหนด")
        stop()

    -- ⭐ หยุดเมื่อยอด WAGER สะสมถึงเป้าที่กำหนด
    elseif totalWagered >= start_balance * stop_wager_target then
        print("🟨 หยุด: เดิมพันสะสมครบ ", string.format("%.2fx", stop_wager_target))
        stop()
    end
end

------------------------------------------------------------
-- 🎯 ฟังก์ชันหลัก
------------------------------------------------------------
function dobet()
    -- ⭐ เพิ่มยอด wager สะสมทุกครั้งก่อนเช็ค stop
    if previousbet ~= nil then
        totalWagered = totalWagered + previousbet
    end

    checkStop()

    if mode == "wager" then
        nextbet = balance * wager_bet_percent

        -- ขาดทุน 20% → เข้า profit mode
        if balance <= start_balance * (1 - max_drawdown) then
            switchMode("profit")
        end

    elseif mode == "profit" then
        if win then
            nextbet = profit_base
        else
            nextbet = previousbet * profit_mul
        end

        -- ฟื้นทุนครบ → กลับโหมด WAGER
        if balance >= start_balance then
            switchMode("wager")
        end
    end
end