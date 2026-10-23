-- 🔹 ตั้งค่าพื้นฐาน
atmul = false
mul = 1.0055
atC = false
chance = 0.5
minC = 0.3
maxC = 1

-- 🔹 ตั้งค่าพื้นฐานของ bet
base = 0.001
atB = true
constant = 4920.657497
safety_margin = 0.01  -- เพิ่ม 2% เพื่อ cover house edge

-- 🔹 ตั้งค่าเป้าหมายหยุด
stop_profit = 1000
stop_loss = -50000
max_balance = 250000
min_balance = 0

-- 🔹 บันทึกค่าเริ่มต้น
starting_balance = balance
previousbet = base

-- 🔹 ฟังก์ชันรีเซ็ต
function reset()
    if atC then
        chance = math.random(minC * 100, maxC * 100) / 100
        if chance <= 0 then chance = 1 end
    else
        chance = chance
    end

    if atB then
        base = balance / constant
    end

    nextbet = base
    bethigh = false
    previousbet = nextbet
    print(string.format("🔄 Reset! chance: %.4f%% base bet: %.8f", chance, base))
end

-- 🔹 ฟังก์ชันหลัก
function dobet()
    -- เช็คหยุดตามเป้าหมาย
    local profit = balance - starting_balance
    
    if profit >= stop_profit then
        print("🟢 ถึงกำไรเป้าหมาย: " .. profit)
        stop()
        return
    elseif profit <= stop_loss then
        print("🔴 ขาดทุนถึงขีดจำกัด: " .. profit)
        stop()
        return
    elseif balance >= max_balance then
        print("🟡 ยอดเงินเกินเป้า: " .. balance)
        stop()
        return
    elseif balance <= min_balance then
        print("🔻 ยอดเงินต่ำเกินไป: " .. balance)
        stop()
        return
    end

    if win then
        print("🎉 ชนะ! รีเซ็ตเดิมพัน")
        reset()
    else
        print("😞 แพ้! คูณเดิมพัน")
        
        if atmul then
            -- คำนวณ payout multiplier
            local payout = 100 / chance
            
            -- สูตร Martingale พื้นฐาน + safety margin
            local base_mul = payout / (payout - 1)
            mul = base_mul + safety_margin  -- บวก 2% แบบตรงๆ
            
            nextbet = previousbet * mul
            
            print(string.format("📊 Payout: %.2fx | Base Mul: %.6f | Final Mul: %.6f", payout, base_mul, mul))
        else
        	mul = mul
            nextbet = previousbet * mul
        end

        -- เดิมพันขั้นต่ำ
        if nextbet < 0.0001 then
            nextbet = 0.0002
        end

        previousbet = nextbet
        print(string.format("💰 เดิมพันต่อไป: %.8f | ยอดเงิน: %.8f | กำไร: %.2f", nextbet, balance, profit))
    end
end

-- เริ่มต้นครั้งแรก
reset()