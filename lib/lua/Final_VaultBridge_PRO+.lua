------------------------------------------------------------
-- 💎 FUSION BOT - VaultBridge PRO+ (Stable 1.0)
-- Simulation Ready Build
-- Mode 1 = Wager + Recover + Vault + Wagered Target
-- Mode 2 = Profit Only + Vault + Profit Target
------------------------------------------------------------

math.randomseed(os.time())

------------------------------------------------------------
-- ⚙️ CONFIGURATION
------------------------------------------------------------
main_mode            = 1           -- 1=Wager+Recover | 2=ProfitOnly
simulate_mode         = true        -- true=simulation, false=API
balance               = 100.0
vault_trigger         = 1.05
vault_fraction        = 0.25
risk_bonus_percent    = 1.0
allowed_losses        = 15
chance_min            = 40
chance_max            = 60
auto_chance           = true
save_interval         = 20

-- 🎯 WAGER TARGET (Mode 1)
wagered_target        = 500.0      -- หยุดเมื่อยอดเดิมพันสะสมครบ
stop_on_complete      = true

-- 💰 PROFIT TARGET (Mode 2)
profit_target_percent = 10.0        -- หยุดเมื่อกำไรถึง +10%
use_profit_target     = true

------------------------------------------------------------
-- 📦 INTERNAL VARIABLES
------------------------------------------------------------
vault           = 0.0
start_balance   = balance
constant_divisor = 0
base            = 0
mul             = 0
chance          = 49.5
mode            = (main_mode == 1) and "wager" or "profit"
profit_cycle    = 0
loss_cycle      = 0
total_wagered   = 0.0
rounds          = 0

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
-- 💰 BASEBET SYSTEM
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
-- 🏦 VAULT BRIDGE
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
    total_wagered = total_wagered + base

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
    base = calcBase()
    total_wagered = total_wagered + base

    if not win then
        mode = "profit"
        print("⚠️ Switching to Profit Mode for recovery...")
    else
        balance = balance + base * 0.01
    end
    checkVaultTrigger()
end

------------------------------------------------------------
-- 🧮 MAIN SIMULATION LOOP
------------------------------------------------------------
for i = 1, 1000 do
    rounds = i
    if mode == "profit" then
        profitModeLoop()
    else
        wagerModeLoop()
    end

    -- 🎯 STOP CONDITIONS
    if main_mode == 1 and stop_on_complete and total_wagered >= wagered_target then
        print("\n🎯 Wager target reached!")
        print(string.format("📊 Total wagered: %.6f / %.6f", total_wagered, wagered_target))
        break
    end
    if main_mode == 2 and use_profit_target and balance >= start_balance * (1 + profit_target_percent / 100) then
        print(string.format("🎯 Profit target reached! +%.2f%%", profit_target_percent))
        break
    end
end

------------------------------------------------------------
-- 📊 SESSION SUMMARY
------------------------------------------------------------
print("\n-------------------------------------")
print("📊 SESSION SUMMARY")
print("-------------------------------------")
print(string.format("🧮 Rounds: %d", rounds))
print(string.format("💰 Final Balance  : %.6f", balance))
print(string.format("🏦 Vault Stored   : %.6f", vault))
print(string.format("📈 Total Assets   : %.6f", balance + vault))
print(string.format("💫 Total Wagered  : %.6f", total_wagered))
print("-------------------------------------")
print("✅ Simulation Completed.")
