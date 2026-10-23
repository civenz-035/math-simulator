------------------------------------------------------------
-- 💎 FUSION BOT - VAULT BRIDGE EDITION (Simulation Mode)
-- Mode 1 = Wager + Recover + Vault
-- Mode 2 = Profit Only + Vault + Reset
------------------------------------------------------------

math.randomseed(os.time())

-- ⚙️ CONFIGURATION
main_mode          = 1           -- 1 = Wager+Recover | 2 = Profit Only
auto_chance        = true
chance_min         = 30
chance_max         = 60
risk_bonus_percent = 1.0
allowed_losses     = 8
vault_trigger      = 1.05        -- เก็บกำไรเมื่อ balance ≥ 120% ของ start_balance
vault_fraction     = 0.25        -- เก็บกำไร 25% ของกำไรส่วนเกิน

-- 📦 INTERNAL VARIABLES
balance        = 100.0
start_balance  = balance
vault          = 0.0
base           = 0
mul            = 0
chance         = 49.5
constant_divisor = 0
mode           = (main_mode == 1) and "wager" or "profit"
profit_cycle   = 0
loss_cycle     = 0
rounds         = 0

------------------------------------------------------------
-- 📘 UTILS
------------------------------------------------------------
function calcMultiplier(ch)
    return 1 + ((1 + risk_bonus_percent / 100) / ((1 / ch) - 1))
end

function getRandomChance()
    return chance_min + math.random() * (chance_max - chance_min)
end

------------------------------------------------------------
-- 💰 AUTO BASE SYSTEM
------------------------------------------------------------
function calcBase()
    local ref = auto_chance and chance_min or (chance / 100)
    constant_divisor = ((1 / ref) - 1) * (allowed_losses + 2)
    return balance / constant_divisor
end

------------------------------------------------------------
-- 🧩 RESET SYSTEMS
------------------------------------------------------------
function resetProfitMode()
    print("🔄 Resetting Profit Mode after vault deposit...")
    start_balance = balance
    profit_cycle = 0
    loss_cycle = 0
    base = calcBase()
    if auto_chance then chance = getRandomChance() end
end

function resetAfterVaultToWager()
    print("🔁 Vault deposit done, returning to WAGER MODE...")
    mode = "wager"
    base = calcBase()
    profit_cycle = 0
    loss_cycle = 0
    start_balance = balance
end

------------------------------------------------------------
-- 🔁 VAULT & TRANSITION BRIDGE
------------------------------------------------------------
function checkVaultTrigger()
    if balance >= start_balance * vault_trigger then
        local profit = balance - start_balance
        local deposit = profit * vault_fraction
        vault = vault + deposit
        balance = balance - deposit
        print(string.format("🏦 Vault deposit %.6f | Vault total %.6f | Balance %.6f", deposit, vault, balance))

        if main_mode == 2 then
            resetProfitMode()
        elseif main_mode == 1 then
            resetAfterVaultToWager()
        end
    end
end

------------------------------------------------------------
-- 🎯 PROFIT MODE LOOP
------------------------------------------------------------
function profitModeLoop()
    if auto_chance then chance = getRandomChance() end
    mul = calcMultiplier(chance / 100)
    base = calcBase()

    local win = math.random() < (chance / 100)
    if win then
        balance = balance + base * (mul - 1)
        profit_cycle = profit_cycle + 1
    else
        balance = balance - base
        loss_cycle = loss_cycle + 1
    end

    checkVaultTrigger()
end

------------------------------------------------------------
-- 🎯 WAGER MODE LOOP
------------------------------------------------------------
function wagerModeLoop()
    local win = math.random() < 0.5
    if not win then
        mode = "profit"
        print("⚠️ Switching to Profit Mode for recovery...")
    else
        balance = balance + 0.001  -- จำลองเล็กน้อยว่ามีกำไรสะสม
    end
    checkVaultTrigger()
end

------------------------------------------------------------
-- 🧮 MAIN SIMULATION LOOP
------------------------------------------------------------
for i = 1, 500 do
    rounds = i
    if mode == "profit" then
        profitModeLoop()
    else
        wagerModeLoop()
    end
    if balance <= 0 then
        print("💀 Balance depleted. Stopping simulation.")
        break
    end
end

------------------------------------------------------------
-- 📊 FINAL REPORT
------------------------------------------------------------
print("\n-------------------------------------")
print("📊 SESSION SUMMARY")
print("-------------------------------------")
print(string.format("🧮 Total rounds   : %d", rounds))
print(string.format("💰 Final Balance  : %.6f", balance))
print(string.format("🏦 Vault Stored   : %.6f", vault))
print(string.format("📈 Total Assets   : %.6f", balance + vault))
print("-------------------------------------")
print("✅ Simulation Completed.")
