------------------------------------------------------------
-- 🎯 SIMPLE AUTO BET SCRIPT (Wager + Profit Recovery)
-- 💬 ปรับค่าที่ส่วน CONFIG ได้เลย ไม่ต้องเป็นโปรแกรมเมอร์
-- ⚠️ ใช้เพื่อการทดลองเท่านั้น โปรดระวังการขาดทุน
------------------------------------------------------------


------------------------------------------------------------
-- 🧩 CONFIG (ตั้งค่าหลัก)
------------------------------------------------------------

-- 🎲 โหมดเก็บยอด WAGER
wager_chance        = 99      -- โอกาสชนะ (%) เช่น 99 = เล่นต่ำกว่า 99
wager_bet_percent   = 2.5     -- เดิมพันเป็นกี่ % ของยอดเริ่มต้น
wager_loss_cut      = 4       -- หยุดเก็บ wager และเข้าสู่ profit mode เมื่อขาดทุนเกิน % นี้

-- 💰 โหมดกู้กำไร (เลือกแบบสุ่มระหว่างชุดที่กำหนดไว้)
profit_modes = {
    {
        name   = "แบบที่ 1",
        chance = 0.5,       -- โอกาสชนะ (%) ใน profit mode
        base   = 0.002,     -- ยอดเดิมพันเริ่มต้น
        multi  = 1.0055     -- ถ้าแพ้ให้คูณยอดเดิมพันเพิ่มเท่านี้
    },
    {
        name   = "แบบที่ 2",
        chance = 0.45,
        base   = 0.002,
        multi  = 1.005
    }
}

-- ⚙️ ค่าระบบทั่วไป
house_edge = 1                -- ค่าความเสียเปรียบเจ้ามือ (ไม่ต้องแก้)
recover_buffer = 1.01         -- ฟื้นกำไรเกิน 1% ถึงจะกลับไป wager mode


------------------------------------------------------------
-- 🧠 MAIN VARIABLES (ไม่ต้องแก้)
------------------------------------------------------------
start_balance = balance
mode = "wager"                -- เริ่มต้นที่โหมดเก็บยอด
active_profit_mode = nil

chance = wager_chance
bethigh = false               -- เล่นฝั่ง LOW (ถ้าอยากสลับให้ true)
nextbet = 0


------------------------------------------------------------
-- 🧮 UTILITY FUNCTION
------------------------------------------------------------
function payoutMultiplier(ch)
    return (100 - house_edge) / ch
end


------------------------------------------------------------
-- 🔄 SWITCH MODE FUNCTION
------------------------------------------------------------
function switchMode(newMode)
    if newMode == "wager" then
        mode = "wager"
        chance = wager_chance
        nextbet = start_balance * (wager_bet_percent / 100)
        print("🟢 เข้าสู่โหมดเก็บยอด WAGER MODE")
        return
    end

    if newMode == "profit" then
        mode = "profit"
        local pick = math.random(1, #profit_modes)
        active_profit_mode = profit_modes[pick]

        chance = active_profit_mode.chance
        nextbet = active_profit_mode.base
        print("🟡 เข้าสู่โหมดกู้กำไร PROFIT MODE: " .. active_profit_mode.name)
        return
    end
end


------------------------------------------------------------
-- 💰 MAIN BET LOOP (ระบบหลัก)
------------------------------------------------------------
function dobet()

    -- ถ้าเงินหมด → หยุด
    if balance <= 0 then
        print("⛔️ Balance หมด หยุดทำงาน")
        stop()
        return
    end

    --------------------------------------------------------
    -- 🟢 WAGER MODE
    --------------------------------------------------------
    if mode == "wager" then
        -- เดิมพันคงที่ตามเปอร์เซ็นต์ที่ตั้งไว้
        nextbet = start_balance * (wager_bet_percent / 100)

        -- ตรวจว่าเริ่มขาดทุนเกินที่กำหนดหรือยัง
        local loss_threshold = start_balance * (1 - wager_loss_cut / 100)
        if balance <= loss_threshold then
            print(string.format("⚠️ ขาดทุน %.1f%% → เปลี่ยนไปโหมดกู้กำไร (PROFIT MODE)", wager_loss_cut))
            switchMode("profit")
            return
        end

        return
    end


    --------------------------------------------------------
    -- 🟡 PROFIT MODE
    --------------------------------------------------------
    if mode == "profit" then
        -- ถ้าชนะ → เริ่มใหม่จาก base
        if win then
            nextbet = active_profit_mode.base
        else
            -- ถ้าแพ้ → เพิ่มยอดตามตัวคูณ
            nextbet = previousbet * active_profit_mode.multi
        end

        -- เมื่อฟื้นเกิน 1% → กลับไปเก็บยอด
        if balance >= start_balance * recover_buffer then
            print("✅ ฟื้นกำไรครบ → กลับไปโหมดเก็บยอด (WAGER MODE)")
            start_balance = balance -- ตั้งต้นใหม่
            switchMode("wager")
            return
        end

        return
    end
end


------------------------------------------------------------
-- 🚀 START (เริ่มทำงาน)
------------------------------------------------------------
switchMode("wager")
nextbet = start_balance * (wager_bet_percent / 100)
print("🎬 เริ่มระบบ WAGER → PROFIT AUTO BET พร้อมทำงาน!")
