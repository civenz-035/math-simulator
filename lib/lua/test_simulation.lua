------------------------------------------------------------
-- 🧪 FUSION BOT SIMULATION TESTER
-- ทดสอบระบบ Fusion Smart Martingale Clean Adaptive Edition (2026)
-- ไม่ใช้เงินจริง — จำลองผลลัพธ์ win/lose
------------------------------------------------------------
balance = 0.70     -- กำหนดทุนเริ่มต้นจำลอง (เช่น 1.0 = 1 หน่วย)

-- เพิ่มฟังก์ชัน stop() ปลอม เพื่อกัน error ตอนจบ
function stop()
    print("🛑 Simulation stopped (end of test).")
end
-- โหลดฟังก์ชันจาก Final.lua (ต้องอยู่ในโฟลเดอร์เดียวกัน)
dofile("Final.lua")

------------------------------------------------------------
-- ⚙️ CONFIG การทดสอบ
------------------------------------------------------------
SIM_ROUNDS = 1000        -- จำนวนรอบจำลองทั้งหมด
EXPORT_CSV = true        -- true = บันทึกผลเป็นไฟล์ .csv
SHOW_LOGS  = true        -- true = แสดงผลแต่ละรอบ

------------------------------------------------------------
-- 🧩 ตั้งค่าเริ่มต้นจำลอง
------------------------------------------------------------
balance = 0.7            -- ทุนเริ่มต้นจำลอง (1 = 1หน่วย)
start_balance = balance
previousbet = 0
win = false

-- เริ่มใน Profit Mode ทันที
switchMode("profit")

------------------------------------------------------------
-- 🧮 เตรียมไฟล์ CSV สำหรับ export
------------------------------------------------------------
local csv
if EXPORT_CSV then
    csv = io.open("simulation_result.csv", "w")
    csv:write("round,chance,multiplier,divisor,base,bet,win,balance\n")
end

------------------------------------------------------------
-- 🔁 LOOP จำลองผลลัพธ์
------------------------------------------------------------
for i = 1, SIM_ROUNDS do
    previousbet = nextbet

    -- ✅ จำลองผลลัพธ์ win/lose
    local roll = math.random()
    win = roll < chance

    if win then
        -- คำนวณกำไรจาก win
        balance = balance + (previousbet * ((1 / chance) - 1))
    else
        -- หักเงินจากการแพ้
        balance = balance - previousbet
    end

    -- เรียก logic จริงของระบบ (ไม่แตะเงินจริง)
    dobet()

    -- แสดง log แต่ละรอบ
    if SHOW_LOGS then
        print(string.format(
            "🧮 Round %03d | %s | Chance %.2f%% | Mul %.5f | Base %.6f | Bet %.6f | Bal %.6f",
            i,
            (win and "✅ Win" or "❌ Lose"),
            chance * 100,
            multiplier_lose,
            base,
            previousbet,
            balance
        ))
    end

    -- บันทึก CSV
    if EXPORT_CSV then
        csv:write(string.format("%d,%.4f,%.6f,%.6f,%.8f,%.8f,%s,%.8f\n",
            i, chance*100, multiplier_lose, constant_divisor,
            base, previousbet, tostring(win), balance))
    end

    -- หยุดถ้า balance หมด
    if balance <= 0 then
        print("💀 Simulation stopped — Balance depleted.")
        break
    end
end

------------------------------------------------------------
-- 🔚 ปิดการทดสอบ
------------------------------------------------------------
if EXPORT_CSV then
    csv:close()
    print("📁 Exported simulation_result.csv (เปิดดูใน Excel ได้)")
end

printSummary()
print("✅ Simulation completed.")
