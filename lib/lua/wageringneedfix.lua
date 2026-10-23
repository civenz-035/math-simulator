------------------------------------------------------------
-- CONFIG (ตั้งค่าได้)
------------------------------------------------------------
wager_chance       = 98
wager_bet_percent  = 0.050       -- 10% ของ balance ตอนเริ่มโหมด wager
wager_loss_cut     = 0.05       -- ขาดทุน 20% → เข้า profit mode

profit_chance      = 4.5
profit_base        = balance/11201   -- เบทเริ่มต้นของ profit mode
profit_multiplier  = 1.055      -- คูณเมื่อแพ้
profit_recover_gap = 0.00000001 -- ความคลาดเคลื่อนในการ recover

max_total_wagered  = 1000      -- Stop เมื่อ wagered รวมครบ (หน่วย=เหรียญ)

------------------------------------------------------------
-- ตัวแปรหลัก
------------------------------------------------------------
mode = "wager"
start_balance = balance
nextbet = balance * wager_bet_percent
chance = wager_chance

total_wagered = 0

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
        start_balance = balance
    end
end

------------------------------------------------------------
-- ฟังก์ชัน STOP CONDITION
------------------------------------------------------------
function checkStop()
    if total_wagered >= max_total_wagered then
        print("🚨 หยุดเพราะครบยอด wagered ที่กำหนด")
        stop()
    end
end

------------------------------------------------------------
-- LOOP หลัก
------------------------------------------------------------
function dobet()

    --------------------------------------------------------
    -- รวมยอด wager (ไม่พึ่ง Stats.wagered)
    --------------------------------------------------------
    total_wagered = total_wagered + nextbet

    --------------------------------------------------------
    -- เช็ค stop ก่อน
    --------------------------------------------------------
    checkStop()

    --------------------------------------------------------
    -- 🔵 WAGER MODE
    --------------------------------------------------------
    if mode == "wager" then
        chance = wager_chance

        -- ขาดทุน ??% → เข้า profit mode
        if balance <= start_balance * (1 - wager_loss_cut) then
            print("🔄 ย้ายไป PROFIT MODE (ขาดทุนตามเงื่อนไข)")
            switchMode("profit")
            return
        end

        nextbet = balance * wager_bet_percent
    end

    --------------------------------------------------------
    -- 🔴 PROFIT MODE (ฟื้นทุน)
    --------------------------------------------------------
    if mode == "profit" then
        chance = profit_chance

        if win then
            nextbet = profit_base
        else
            nextbet = nextbet * profit_multiplier
        end

        -- เมื่อ recover กลับมาระดับทุนตอนเริ่ม profit mode
        if balance >= start_balance - profit_recover_gap then
            print("🟢 Recovery สำเร็จ → กลับไป WAGER MODE")
            switchMode("wager")
            return
        end
    end
end