print("Hello, World!")

-- 🔹 ตั้งค่าพื้นฐาน
atmul = true
mul = 1               -- คูณเมื่อแพ้
atC = true            -- ให้สุ่มค่า chance ทุกครั้งที่รีเซ็ต
minC = 3
maxC = 8

-- 🔹 ตั้งค่าพื้นฐานของ bet
base = 0.001
atB = true           -- ปรับ base ตาม balance
constant = 2500

-- 🔹 ตั้งค่าเป้าหมายหยุด
stop_profit = 1000      -- หยุดเมื่อกำไรถึงจำนวนนี้
stop_loss = -50000      -- หยุดเมื่อขาดทุนถึงจำนวนนี้
max_balance = 250000    -- หยุดเมื่อยอดเงินมากกว่าค่านี้
min_balance = 100000    -- หยุดเมื่อยอดเงินน้อยกว่าค่านี้

-- 🔹 บันทึกค่าเริ่มต้น
balance = 2.43900429   -- สมมติยอดเงินเริ่มต้น
starting_balance = balance
previousbet = base  -- กำหนดการเดิมพันก่อนหน้า

-- 🔹 ฟังก์ชันรีเซ็ตเมื่อชนะหรือเริ่มใหม่
function reset()
    if atC then
        chance = math.random(minC * 100, maxC * 100) / 100
        if chance <= 0 then chance = 1 end -- กัน error chance = 0
    else
        chance = 1
    end

    if atB then
        base = balance / constant
    end

    nextbet = base
    bethigh = true
    mul = 1
    previousbet = nextbet
    print(string.format("🔄 Reset! chance: %.4f%% base bet: %.8f", chance, base))
end

-- 🔹 ฟังก์ชันหลัก
function dobet()
    -- สุ่มผลชนะ 30%
    local r = math.random()
    if r < 0.3 then
        win = true
        print("🎉 You Win!")
        -- สมมติเพิ่มยอดเงินเมื่อชนะ
        balance = balance + previousbet * (98 / chance - 1)
    else
        win = false
        print("😞 You Lose!")
    end
    
    -- เช็คหยุดตามเป้าหมาย
    local profit = balance - starting_balance
    if profit >= stop_profit then
        print("🟢 ถึงกำไรเป้าหมาย: " .. profit)
        return
    elseif profit <= stop_loss then
        print("🔴 ขาดทุนถึงขีดจำกัด: " .. profit)
        return
    elseif balance >= max_balance then
        print("🟡 ยอดเงินเกินเป้า: " .. balance)
        return
    elseif balance <= min_balance then
        print("🔻 ยอดเงินต่ำเกินไป: " .. balance)
        return
    end

    if win then
        print("ชนะ รีเซ็ตเดิมพัน")
        reset()
    else
        if atmul == true then
            print("แพ้ คูณเดิมพัน")
            mul = ((100 / chance) - 1) * 1.02   -- คูณเพิ่มเล็กน้อยเพื่อป้องกันขาดทุน
            nextbet = previousbet * mul
        else
            nextbet = previousbet
        end

        -- เดิมพันขั้นต่ำ 0.0001 ตามแพลตฟอร์ม
        if nextbet < 0.0001 then
            nextbet = 0.0001
        end

        previousbet = nextbet
        balance = balance - nextbet

        print(string.format("Placing Dice Bet: %.8f at %.4f%% chance to win, High", nextbet, chance))
        print(string.format("เดิมพันต่อไป: %.8f ยอดเงิน: %.8f", nextbet, balance))
    end
end

-- เริ่มต้นครั้งแรก
reset()
