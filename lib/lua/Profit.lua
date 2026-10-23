------------------------------------------------------------
-- 💰 PROFIT MODE (เวอร์ชันปรับสมบูรณ์)
-- ✅ เตรียมไว้สำหรับรวมกับระบบ WAGER MODE ภายหลัง
-- 👩‍💻 ใช้งานง่าย: แก้ไขค่า CONFIG ด้านบนเท่านั้น
------------------------------------------------------------


------------------------------------------------------------
-- ⚙️ CONFIG (ตั้งค่าหลัก)
------------------------------------------------------------

-- 🎯 โอกาสชนะ (Chance)
auto_chance        = true       -- true = ให้สุ่ม chance อัตโนมัติ
chance_min         = 0.45       -- ค่าต่ำสุดของ chance ที่สุ่มได้
chance_max         = 0.55       -- ค่าสูงสุดของ chance ที่สุ่มได้
chance_fixed       = 49.95      -- ถ้า auto_chance = false ใช้ค่านี้แทน

-- 🔁 สุ่ม chance ใหม่เมื่อชนะ / แพ้
random_on_win      = true
random_on_lose     = false

-- 💰 ฐานเดิมพัน (Base bet)
constant_divisor   = 0          -- ถ้า > 0 ระบบจะคำนวณ base = balance / constant_divisor
manual_base        = 0.002      -- ถ้า constant_divisor = 0 ใช้ค่านี้เป็น base เอง

-- 📈 ตัวคูณ (Multipliers)
multiplier_win     = 1.0        -- คูณเมื่อชนะ (1 = ไม่เพิ่ม)
multiplier_lose    = 1.006      -- คูณเมื่อแพ้ (เพิ่มทีละ 0.6%)
auto_multiplier    = false      -- true = ให้ระบบปรับคูณอัตโนมัติ (ยังไม่ใช้)

-- 🎲 การเล่นสูง/ต่ำ
bethigh            = true       -- true = เล่นสูง, false = เล่นต่ำ
auto_switch        = true       -- สลับฝั่งอัตโนมัติหรือไม่
switch_on_win      = true       -- ชนะแล้วสลับฝั่ง
switch_on_lose     = false      -- แพ้แล้วสลับฝั่ง

-- 🧾 เงื่อนไขหยุดระบบ (Stop conditions)
start_balance      = balance
stop_profit_target = 0.03       -- หยุดเมื่อกำไรถึง 3% ของ start_balance (0 = ปิด)
stop_loss_limit    = 0.03       -- หยุดเมื่อขาดทุนถึง 3% ของ start_balance (0 = ปิด)
stop_max_loss_streak = 0        -- หยุดเมื่อแพ้ติดกันตามจำนวนนี้ (0 = ปิด)

-- 🔄 รีเซ็ตกลับ base
reset_profit_level = 0.00000001 -- ถ้ากำไรเกินค่านี้ให้รีเซ็ต bet เป็น base


------------------------------------------------------------
-- 🧠 MAIN VARIABLES (ไม่ต้องแก้)
------------------------------------------------------------
chance  = chance_fixed
base    = manual_base
nextbet = base
win_count = 0
lose_count = 0
loss_streak = 0
profit_total = 0


------------------------------------------------------------
-- 🎲 ฟังก์ชันช่วย (UTILITY FUNCTIONS)
------------------------------------------------------------

-- สุ่มค่า chance ใหม่ในช่วง min–max
function randomChance()
    return math.random(chance_min * 100, chance_max * 100) / 100
end

-- อัปเดต chance ตามโหมด
function updateChanceOnResult(win)
    if auto_chance then
        if (win and random_on_win) or (not win and random_on_lose) then
            chance = randomChance()
        end
    end
end

-- เปลี่ยนฝั่งเล่น High / Low ตามผล
function updateBetHighOnResult(win)
    if auto_switch then
        if (win and switch_on_win) or (not win and switch_on_lose) then
            bethigh = not bethigh
        end
    end
end


------------------------------------------------------------
-- 💰 ฟังก์ชันเดิมพันหลัก (PROFIT MODE LOOP)
------------------------------------------------------------
function dobet()

    -- ✅ คำนวณ base bet (ตาม config)
    if constant_divisor > 0 then
        base = balance / constant_divisor
    else
        base = manual_base
    end

    -- ✅ ตรวจสถานะชนะ / แพ้
    if win then
        win_count = win_count + 1
        loss_streak = 0
        nextbet = previousbet * multiplier_win

        -- รีเซ็ต base เมื่อได้กำไรพอ
        if profit >= reset_profit_level then
            nextbet = base
        end

        updateChanceOnResult(true)
        updateBetHighOnResult(true)
    else
        lose_count = lose_count + 1
        loss_streak = loss_streak + 1
        nextbet = previousbet * multiplier_lose

        updateChanceOnResult(false)
        updateBetHighOnResult(false)
    end


    --------------------------------------------------------
    -- 🛑 เงื่อนไขหยุดระบบ
    --------------------------------------------------------

    -- หยุดเมื่อถึงเป้ากำไร
    if stop_profit_target > 0 and balance >= start_balance * (1 + stop_profit_target) then
        print("💹 ถึงเป้ากำไรที่ตั้งไว้ → หยุดระบบ")
        stop()
        return
    end

    -- หยุดเมื่อขาดทุนเกินที่กำหนด
    if stop_loss_limit > 0 and balance <= start_balance * (1 - stop_loss_limit) then
        print("⚠️ ขาดทุนถึงขีดจำกัด → หยุดระบบ")
        stop()
        return
    end

    -- หยุดเมื่อแพ้ติดกันถึงจำนวนที่ตั้งไว้
    if stop_max_loss_streak > 0 and loss_streak >= stop_max_loss_streak then
        print("🚫 แพ้ติดกันถึงจำนวนสูงสุด → หยุดระบบ")
        stop()
        return
    end
end


------------------------------------------------------------
-- 🚀 เริ่มต้นระบบ PROFIT MODE
------------------------------------------------------------
if auto_chance then
    chance = randomChance()
end

if constant_divisor > 0 then
    base = balance / constant_divisor
else
    base = manual_base
end

nextbet = base

print("🟡 เริ่มโหมด PROFIT MODE (เวอร์ชันสมบูรณ์) พร้อมทำงาน!")
print(string.format("เริ่มต้น balance: %.8f | base bet: %.8f | chance: %.2f%%", balance, base, chance))
