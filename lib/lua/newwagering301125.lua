math.randomseed(os.time())

-----------------------------------------------------------
-- CONFIG (ตั้งค่าได้)
------------------------------------------------------------
wager_chance       = 99
wager_bet_percent  = 0.0250       -- % ของ balance ตอนเริ่มโหมด wager
wager_loss_cut     = 0.049       -- ขาดทุน 4.9% → เข้า profit mode

profit_chance      = 4.5
profit_base        = 0.0025   -- เบทเริ่มต้นของ profit mode
profit_multiplier  = 1.05      -- คูณเมื่อแพ้
profit_recover_gap = 100 -- ความคลาดเคลื่อนในการ recover

max_total_wagered  = 200    -- Stop เมื่อ wagered รวมครบ (หน่วย=เหรียญ)

------------------------------------------------------------
-- ตัวแปรหลัก
------------------------------------------------------------
balance = 5        -- กำหนดทุนเริ่มต้น
mode = "wager"
start_balance = balance
nextbet = balance * wager_bet_percent
chance = wager_chance

total_wagered = 0
win = false

------------------------------------------------------------
-- ฟังก์ชัน STOP CONDITION
------------------------------------------------------------
function stop()
    print("🚨 หยุดสคริปต์")
    os.exit()
end

function checkStop()
    if total_wagered >= max_total_wagered then
        print("🚨 หยุดเพราะครบยอด wagered ที่กำหนด")
        stop()
    end
end

------------------------------------------------------------
-- ฟังก์ชันสลับโหมด
------------------------------------------------------------
function switchMode(newMode)
    mode = newMode
    
    if mode == "wager" then
        print("🟢 เข้าสู่ WAGER MODE")
        chance = wager_chance
        nextbet = balance * wager_bet_percent
        start_balance = balance

    elseif mode == "profit" then
        print("🟡 เข้าสู่ PROFIT MODE")
        chance = profit_chance
        nextbet = profit_base
        -- ในที่นี้ไม่เปลี่ยน start_balance เพราะต้องการเทียบกับทุนเริ่มต้นสคริป
    end
end

------------------------------------------------------------
-- LOOP หลัก
------------------------------------------------------------
function dobet()
    -- รวมยอด wager (ไม่พึ่ง Stats.wagered)
    total_wagered = total_wagered + nextbet

    -- เช็ค stop ก่อน
    checkStop()

    -- สุ่มเลขเดิมพัน 0-99
    local dice_roll = math.random(0, 99)
    print(string.format("🎲 Dice rolled: %d (chance to win: %.4f%%)", dice_roll, chance))

    -- ตรวจสอบผลแพ้ชนะ สมมติว่าเลขที่ออก < chance คือชนะ
    win = (dice_roll < chance)

    if mode == "wager" then
        chance = wager_chance

        -- ขาดทุน ??% → เข้า profit mode
        if balance <= start_balance * (1 - wager_loss_cut) then
            print("🔄 ย้ายไป PROFIT MODE (ขาดทุนตามเงื่อนไข)")
            switchMode("profit")
            return
        end

        if win then
            balance = balance + nextbet * (100 / chance - 1)
            print(string.format("✅ Result: WIN | Balance: %.4f", balance))
        else
            balance = balance - nextbet
            print(string.format("❌ Result: LOSE | Balance: %.4f", balance))
        end

        nextbet = balance * wager_bet_percent

    elseif mode == "profit" then
        chance = profit_chance

        if win then
            balance = balance + nextbet * (100 / chance - 1)
            nextbet = profit_base
            print(string.format("✅ Result: WIN | Balance: %.4f", balance))
        else
            balance = balance - nextbet
            nextbet = nextbet * profit_multiplier
            print(string.format("❌ Result: LOSE | Balance: %.4f", balance))
        end

        -- เมื่อ recover กลับมาระดับทุนตอนเริ่มสคริป (start_balance)
        if balance >= start_balance then
            print("🟢 Recovery สำเร็จ → กลับไป WAGER MODE")
            switchMode("wager")
            return
        end
    end
end
